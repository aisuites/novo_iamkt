"""
Celery tasks do PIPELINE SIMPLES (v2).

Extraido de tasks.py para isolar o fluxo simples:
  1. Texto  -> agente unico OpenAI (gpt-4o-mini)
  2. Fundo  -> fluxo interno (orquestrador Claude + Gemini, cena sem texto)
  3. Texto aplicado -> Gemini (LLM), nao Pillow

As tasks sao re-importadas em tasks.py para que o autodiscovery do Celery as
registre. Os helpers de contexto compartilhados (montagem de KB, refs, custos,
upload S3) continuam em tasks.py e sao importados aqui de forma LAZY (dentro das
funcoes) para evitar import circular.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_post_simple_task(self, post_id: int):
    """Gera o TEXTO do post via agente unico OpenAI e salva no Post.

    Espelha generate_post_text_task, mas usa simple_post_agent.generate_simple_post
    (1 chamada, gpt-4o-mini). Status final 'pending' (texto pronto). Fase de
    imagem fica para depois.
    """
    from apps.posts.models import Post
    from apps.posts.services.simple_post_agent import generate_simple_post
    from apps.posts.tasks import (
        _build_kb_summary, _format_to_dict, _logos_from_org,
        _reference_images_from_post, _log_usage,
    )

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.simple] Post %s nao encontrado', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'generating'
    post.save(update_fields=['status'])

    # Contexto reaproveitado do pipeline local
    kb_summary = _build_kb_summary(post.organization)
    formato = _format_to_dict(post.post_format) if post.post_format else {
        'name': post.formats[0] if post.formats else 'feed',
        'aspect_ratio': '1:1',
    }
    logo_urls = list(_logos_from_org(post.organization, post=post))

    ctx = post.local_pipeline_context or {}
    refs_general = (ctx.get('references_usage_description', '') or '').strip()
    reference_descriptions = []
    if refs_general:
        reference_descriptions.append(f'Observacao geral: {refs_general}')
    for r in _reference_images_from_post(post):
        desc = (r.get('usage_description') or '').strip()
        utype = (r.get('usage_type') or '').strip()
        if desc or utype:
            reference_descriptions.append(
                f'{r.get("name") or "imagem"} ({utype or "uso nao informado"}): {desc}'
            )

    try:
        result = generate_simple_post(
            kb_summary=kb_summary,
            rede=post.social_network,
            formato=formato.get('name', 'feed'),
            is_carousel=post.is_carousel,
            image_count=post.image_count,
            tema=post.requested_theme,
            cta_requested=post.cta_requested,
            logo_urls=logo_urls,
            reference_descriptions=reference_descriptions,
        )
    except Exception as exc:
        logger.exception('[posts.simple] Falha OpenAI post_id=%s', post_id)
        # Nao usa status 'failed' (fora dos choices do model). Re-tenta; ao
        # esgotar retries mantem 'generating' para o usuario reabrir.
        raise self.retry(exc=exc)

    structured = result['structured']

    # Normaliza hashtags: garante prefixo '#'
    raw_hashtags = structured.get('hashtags') or []
    structured['hashtags'] = [
        h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
        for h in raw_hashtags if h
    ]

    post.title = structured.get('title', '') or ''
    post.subtitle = structured.get('subtitle', '') or ''
    post.image_prompt = structured.get('image_prompt', '') or ''
    post.visual_brief = structured.get('visual_brief', '') or ''
    post.caption = structured.get('caption', '') or ''
    post.hashtags = structured.get('hashtags') or []
    post.cta = structured.get('cta_text') or ''
    # Guarda o payload bruto do agente para auditoria/comparacao entre pipelines
    post.copy_payload = {'_simple_agent': structured}
    post.ia_provider = 'openai'
    post.ia_model_text = result['model']
    post.status = 'pending'
    post.save()

    _log_usage(post, result['model'], result['usage'], purpose='generate_post_simple')

    logger.info(
        '[posts.simple] generate_post_simple_task OK post_id=%s tokens_in=%s tokens_out=%s cost=$%s',
        post_id, result['usage'].get('input_tokens'),
        result['usage'].get('output_tokens'), result['usage'].get('cost_usd'),
    )
    return {'success': True, 'post_id': post_id, 'model': result['model'], 'usage': result['usage']}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_post_simple_image_task(self, post_id: int, message: str = ''):
    """Fase 2 do pipeline simples: gera imagem em 3 etapas.

    1. Fundo SEM texto (reuso do fluxo interno: generate_post_image em modo
       pillow -> usa raw_png_bytes, a cena limpa do Gemini).
    2. Agente de Regras (OpenAI) resolve o briefing (modal > KB > criatividade).
    3. Aplicacao de texto via Gemini (Nano Banana): envia fundo + fonte(s)
       .ttf/.otf + logo + textos exatos + briefing -> imagem final.

    Persiste fundo (raw_image_s3_key) e final (image_s3_key) + artefatos de
    debug em local_pipeline_context['simple_image'].
    """
    import base64 as _b64
    from django.utils import timezone as _tz
    from apps.posts.models import Post, PostImage
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.services.gemini_image_generator import (
        generate_post_image, _download_to_base64,
    )
    from apps.posts.services.simple_image_briefing import resolve_briefing
    from apps.posts.services.simple_image_text_apply import apply_text_to_image
    from apps.posts.services.font_resolver import resolve_font_for_kb
    from apps.posts.tasks import (
        _kb_colors, _kb_typography, _kb_summary_marketing, _formato_px,
        _brand_keywords_from_kb, _collect_references, _collect_kb_dossiers,
        _build_kb_summary, _reference_images_from_post, _logos_from_org,
        _upload_image_to_s3, _log_usage, _log_usage_gemini, _record_ai_usage,
    )

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.simple] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'image_generating'
    post.save(update_fields=['status'])

    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    paleta = _kb_colors(kb)
    tipografia = _kb_typography(kb)
    publico_alvo = (kb.publico_externo if kb else '') or ''
    marketing_input_summary = _kb_summary_marketing(kb)
    formato_px = _formato_px(post)
    # Termos da marca a sanitizar no prompt do fundo: citar a marca (ex.
    # "Thermomix") ativa priors do Gemini e degrada a fidelidade quando ha
    # imagem de produto selecionada. Mesma lista usada no pipeline local.
    brand_keywords = _brand_keywords_from_kb(kb)
    ctx = post.local_pipeline_context or {}

    # Coleta de referencias e dossies — IGUAL ao fluxo interno (sem reinventar).
    # _collect_references: produto/pessoa/uploads como imagem; logo fora em pillow.
    # _collect_kb_dossiers: dossies (luz/composicao/ambiente) consumidos pelo orquestrador.
    references = _collect_references(kb=kb, post=post, text_render_mode='pillow')
    kb_dossiers = _collect_kb_dossiers(kb=kb, post=post)

    # Cenario 2 (ref composta, sem asset isolado): anexa a imagem da ref KB de
    # 'grafismos'/'layout_composicao' ao Gemini como referencia_layout — ele
    # replica APENAS o grafismo de fundo (forma/curva/cor) e ignora
    # pessoa/produto/texto. O brief vem do DOSSIE (ja melhorado: geometria,
    # forma_detalhada, cobertura, atras_do_texto). Mesma logica do fluxo interno
    # (tasks.py); aqui o grafismo precisa nascer na ETAPA 1 (fundo), pois no
    # simples nao ha overlay Pillow. Anexado ANTES do orquestrador e do bg-gen
    # para que ambos vejam a imagem.
    if kb_dossiers:
        try:
            from apps.core.services.s3_service import S3Service
            from apps.knowledge.models import ReferenceImage
            for _d in kb_dossiers:
                _aspects = _d.get('aspects') or []
                if not any(a in _aspects for a in ('layout_composicao', 'grafismos')):
                    continue
                _kb_ref = ReferenceImage.objects.filter(id=_d.get('id')).first()
                if not _kb_ref or not _kb_ref.s3_key:
                    continue
                try:
                    _url = S3Service.generate_presigned_download_url(
                        _kb_ref.s3_key, expires_in=86400
                    )
                except Exception:
                    continue
                # SEM brief textual do grafismo: a fidelidade vem da IMAGEM em si
                # (role GRAPHIC REFERENCE) + reforco na scene. Nao descrevemos
                # forma/cor/posicao em texto — isso so faz o Gemini "inventar"
                # variacoes. O grafismo deve sair da imagem de referencia.
                references.append({
                    'tipo': 'referencia_layout',
                    'url': _url,
                    'usage_description': '',
                })
                logger.info('[posts.simple] ref KB %s anexada ao Gemini como '
                            'referencia_layout (grafismo da imagem, sem brief)', _kb_ref.id)
        except Exception:
            logger.exception('[posts.simple] falha ao anexar ref KB grafismo')

    try:
        # -------- Etapa 1: FUNDO SEM TEXTO — reuso do FLUXO INTERNO --------
        # O orquestrador (Claude) escreve a CENA (produto em cena + luz/composicao
        # via dossie). Usamos APENAS o image_prompt_final dele; ignoramos
        # text_render_mode/layout_document (no simples o texto vai por LLM, nao Pillow).
        scene_prompt = post.image_prompt or ''
        orchestration_dbg = None
        try:
            from apps.posts.services.post_orchestrator import orchestrate_post
            _aspect = (post.post_format.aspect_ratio if post.post_format else '') or ''
            orch = orchestrate_post(
                post=post,
                references=references,
                kb_summary=marketing_input_summary,
                paleta=paleta,
                tipografia=tipografia,
                references_usage_description=ctx.get('references_usage_description', '') or '',
                formato_px=formato_px,
                aspect_ratio=_aspect,
                kb_dossiers=kb_dossiers,
            )
            if orch and orch.get('orchestration'):
                orchestration_dbg = orch['orchestration']
                _scene = (orchestration_dbg.get('image_prompt_final') or '').strip()
                if _scene:
                    scene_prompt = _scene
                _record_ai_usage(
                    post, step='text_generation',
                    model=orch.get('model', 'claude-sonnet-4-6'),
                    usage_dict=orch.get('usage') or {}, purpose='orchestrator',
                )
        except Exception:
            logger.exception('[posts.simple] orquestrador falhou — usa image_prompt da Fase 1')

        # Gera a cena via Gemini em modo pillow e pega o RAW (sem texto/overlay).
        bg_result = generate_post_image(
            post=post,
            references=references,
            paleta=paleta,
            tipografia=tipografia,
            publico_alvo=publico_alvo,
            marketing_input_summary=marketing_input_summary,
            formato_px=formato_px,
            text_render_mode='pillow',
            brand_keywords=brand_keywords,
            image_prompt_override=scene_prompt,
        )
        bg_bytes = bg_result.get('raw_png_bytes') or bg_result.get('png_bytes')
        bg_prompt = bg_result.get('prompt_text', '')
        _log_usage_gemini(post, bg_result.get('model', ''), bg_result.get('cost_usd', 0),
                          bg_result.get('usage'))

        raw_key, raw_url = _upload_image_to_s3(
            org_id=post.organization.id, post_id=post.id,
            png_bytes=bg_bytes, mime_type='image/png',
        )
        post.raw_image_s3_key = raw_key
        post.raw_image_s3_url = raw_url
        post.save(update_fields=['raw_image_s3_key', 'raw_image_s3_url'])

        # -------- Etapa 2: agente de regras (briefing) --------
        ref_descs = []
        for r in _reference_images_from_post(post):
            d = (r.get('usage_description') or '').strip()
            t = (r.get('usage_type') or '').strip()
            if d or t:
                ref_descs.append(f'{r.get("name") or "imagem"} ({t or "uso?"}): {d}')
        modal_selections = {
            'has_logo': bool(ctx.get('selected_logo_ids')),
            'logo_position': ctx.get('logo_position') or '',
            'reference_aspects': ctx.get('reference_aspects') or {},
            'references_usage_description': ctx.get('references_usage_description') or '',
            'reference_descriptions': ref_descs,
        }
        textos = {'title': post.title or '', 'subtitle': post.subtitle or '', 'cta': post.cta or ''}
        # zona/alinhamento de texto DEVEM vir da referencia de layout quando houver:
        # extrai composicao + grid + texto_x_imagem (papel/alinhamento/cor/peso) dos
        # dossies das refs marcadas com aspecto 'layout_composicao'.
        reference_layout = []
        for d in kb_dossiers:
            if 'layout_composicao' in (d.get('aspects') or []):
                _dos = d.get('dossier') or {}
                reference_layout.append({
                    'composicao': _dos.get('composicao'),
                    'grid': _dos.get('grid'),
                    'texto_x_imagem': _dos.get('texto_x_imagem'),
                })
        brief_result = resolve_briefing(
            kb_summary=_build_kb_summary(post.organization),
            modal_selections=modal_selections, textos=textos, formato=formato_px,
            reference_layout=reference_layout,
        )
        briefing = brief_result['briefing']
        _log_usage(post, brief_result['model'], brief_result['usage'], purpose='simple_briefing')

        # -------- Etapa 3: aplicacao de texto via Gemini --------
        font_paths = []
        for usage, weight in (('titulo', 'bold'), ('corpo', 'regular')):
            fp = resolve_font_for_kb(kb, usage_filter=usage, weight=weight)
            if fp and fp not in font_paths:
                font_paths.append(fp)

        # Logo: aplicado SEMPRE que a org tiver um (igual ao fluxo interno).
        # _logos_from_org filtra pelos selected_logo_ids quando houver; senao
        # retorna todos ordenados por is_primary -> logos[0] = primario.
        # O LLM nao decide 'usar' (corrige logo indo como null). Posicao do modal = ouro.
        logo_cfg = briefing.get('logo') or {}
        logos = list(_logos_from_org(post.organization, post=post))
        use_logo = bool(logos)
        logo_position = (ctx.get('logo_position') or logo_cfg.get('posicao') or '')  # modal = ouro
        logo_png = None
        if use_logo:
            b64, _m = _download_to_base64(logos[0])
            if b64:
                logo_png = _b64.b64decode(b64)
        # Reflete a decisao real no briefing (debug coerente)
        if isinstance(briefing.get('logo'), dict):
            briefing['logo']['usar'] = use_logo
            briefing['logo']['posicao'] = logo_position or briefing['logo'].get('posicao')

        apply_result = apply_text_to_image(
            background_png=bg_bytes, font_paths=font_paths, logo_png=logo_png,
            textos=textos, briefing=briefing, formato_px=formato_px,
            logo_position=logo_position,
        )
        final_prompt = apply_result['prompt_text']
        _log_usage_gemini(post, apply_result['model'], apply_result['usage'].get('cost_usd', 0),
                          {'promptTokenCount': apply_result['usage'].get('input_tokens', 0)})

    except Exception as exc:
        logger.exception('[posts.simple] Falha na geracao de imagem post_id=%s', post_id)
        raise self.retry(exc=exc)

    # -------- Persistencia da imagem final --------
    s3_key, s3_url = _upload_image_to_s3(
        org_id=post.organization.id, post_id=post.id,
        png_bytes=apply_result['png_bytes'], mime_type='image/png',
    )
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = apply_result['model']
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing

    # Artefatos de debug (fundo+final+prompts+json) — area de validacao na tela
    _ctx = post.local_pipeline_context or {}
    _ctx['simple_image'] = {
        'bg_prompt': bg_prompt,
        'final_prompt': final_prompt,
        'rules': briefing,
        'orchestration': orchestration_dbg,
        'scene_prompt_final': scene_prompt,
        'model_bg': bg_result.get('model', ''),
        'model_final': apply_result['model'],
        'created_at': _tz.now().isoformat(),
    }
    post.local_pipeline_context = _ctx
    post.status = 'image_ready'
    post.save()

    logger.info('[posts.simple] generate_post_simple_image_task OK post_id=%s', post_id)
    return {'success': True, 'post_id': post_id, 'final_model': apply_result['model']}
