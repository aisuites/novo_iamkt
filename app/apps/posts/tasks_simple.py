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

# Quantas imagens do KB anexar como referencia visual quando o form nao traz
# nenhuma. Limite provisorio — a validacao de "uso de cada imagem" vem depois.
_KB_FALLBACK_REF_LIMIT = 5

# Quantas vezes o usuario pode pedir "Alterar Cena - IA" por post (espelha o
# limite de alteracao de imagem). Constante para nao exigir migration.
MAX_TEXT_REVISIONS = 1


def _aspects_to_tipo(aspects):
    """Mapeia os aspectos escolhidos no form -> papel (tipo) usado pelo
    orquestrador/Gemini para tratar a imagem (fidelidade de produto, grafismo
    de layout, pessoa ou referencia generica de estilo)."""
    aspects = [a for a in (aspects or []) if a]
    if 'produto' in aspects:
        return 'produto'
    if 'pessoa_modelo' in aspects:
        return 'pessoa'
    if any(a in aspects for a in ('grafismos', 'layout_composicao')):
        return 'referencia_layout'
    return 'referencia'


def _simple_build_references(post, kb):
    """Conjunto de referencias do pipeline simples, PERSISTIDO para que a
    Fase 1 (orquestrador) e a Fase 2 (Gemini) usem EXATAMENTE as mesmas
    imagens, na mesma ordem (a cena fala "IMAGEM 1/2..." — tem que casar).

    Prioridade:
      1. uploads de arquivo do form (PostReferenceImage);
      2. referencias do KB SELECIONADAS no form (selected_reference_ids), com o
         papel derivado do aspecto escolhido (produto/grafismo/pessoa/...);
      3. so se NADA for selecionado: ate N imagens do KB como referencia
         visual GENERICA (fallback).

    Guarda os s3_key em local_pipeline_context['simple_refs'] (URLs presignadas
    expiram — guardamos a key e geramos a URL na hora de usar).

    Retorna lista de dicts {s3_key, tipo, usage_description}.
    """
    from apps.posts.tasks import _reference_images_from_post

    ctx = post.local_pipeline_context or {}
    saved = ctx.get('simple_refs')
    if saved is not None:
        return saved

    refs = []
    # 1) uploads de arquivo do form (refs do proprio post)
    for r in _reference_images_from_post(post):
        if r.get('s3_key'):
            refs.append({
                's3_key': r['s3_key'],
                'tipo': (r.get('usage_type') or 'referencia').strip().lower() or 'referencia',
                'usage_description': (r.get('usage_description') or '').strip(),
            })

    # 2) referencias do KB SELECIONADAS no form (preserva a ordem de selecao)
    selected_ids = list(ctx.get('selected_reference_ids') or [])
    if selected_ids and kb:
        from apps.knowledge.models import ReferenceImage
        reference_aspects = ctx.get('reference_aspects') or {}
        by_id = {r.id: r for r in ReferenceImage.objects.filter(
            knowledge_base=kb, id__in=selected_ids)}
        for rid in selected_ids:
            ref = by_id.get(rid)
            if not ref or not ref.s3_key:
                continue
            aspects = reference_aspects.get(str(rid)) or reference_aspects.get(rid) or []
            refs.append({
                's3_key': ref.s3_key,
                'tipo': _aspects_to_tipo(aspects),
                'usage_description': (getattr(ref, 'usage_description', '') or '').strip(),
            })

    # 3) fallback: ate N imagens do KB, como referencia visual generica
    #    (SO quando o user nao selecionou nada no form)
    if not refs and kb:
        from apps.knowledge.models import ReferenceImage
        qs = ReferenceImage.objects.filter(knowledge_base=kb).order_by('id')[:_KB_FALLBACK_REF_LIMIT]
        for ref in qs:
            if ref.s3_key:
                refs.append({'s3_key': ref.s3_key, 'tipo': 'referencia',
                             'usage_description': ''})
        logger.info('[posts.simple] sem refs no form — usando %d refs genericas do KB', len(refs))

    ctx['simple_refs'] = refs
    post.local_pipeline_context = ctx
    post.save(update_fields=['local_pipeline_context'])
    return refs


def _simple_refs_to_payload(refs):
    """Presigna os s3_key guardados em refs -> payload {tipo, url, usage_description}
    pronto para o orquestrador e o gerador de imagem."""
    from apps.core.services.s3_service import S3Service
    out = []
    for r in refs or []:
        try:
            url = S3Service.generate_presigned_download_url(r['s3_key'], expires_in=86400)
        except Exception:
            logger.warning('[posts.simple] falha ao presignar ref %s', r.get('s3_key'))
            continue
        out.append({'tipo': r.get('tipo') or 'referencia', 'url': url,
                    'usage_description': r.get('usage_description') or ''})
    return out


def _simple_orchestrate_into_image_prompt(post):
    """FASE 1 — roda o orquestrador (Claude), FONTE UNICA da cena. Grava a CENA
    em post.image_prompt (texto que o usuario aprova) e PERSISTE a conversa em
    local_pipeline_context['orch_conversa'] para o "Alterar Cena - IA" continuar
    o contexto. NAO chama o Gemini. Nao salva (o caller persiste tudo no fim).
    Retorna True se gerou a cena, False caso contrario."""
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.services.post_orchestrator import orchestrate_post
    from apps.posts.tasks import (
        _kb_colors, _kb_typography, _formato_px, _build_kb_summary, _record_ai_usage,
    )

    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    references = _simple_refs_to_payload(_simple_build_references(post, kb))
    ctx = post.local_pipeline_context or {}
    orch = orchestrate_post(
        post=post,
        references=references,
        kb_summary=_build_kb_summary(post.organization),
        paleta=_kb_colors(kb),
        tipografia=_kb_typography(kb),
        references_usage_description=ctx.get('references_usage_description', '') or '',
        formato_px=_formato_px(post),
        aspect_ratio=(post.post_format.aspect_ratio if post.post_format else '') or '',
        kb_dossiers=[],
        gemini_only=True,
    )
    if not (orch and orch.get('orchestration')):
        logger.warning('[posts.simple] orquestrador (Fase 1) sem saida post=%s', post.id)
        return False

    _record_ai_usage(post, step='text_generation',
                     model=orch.get('model', 'claude-sonnet-4-6'),
                     usage_dict=orch.get('usage') or {}, purpose='orchestrator')

    scene = (orch['orchestration'].get('image_prompt_final') or '').strip()
    if not scene:
        return False

    post.image_prompt = scene
    # Persiste a conversa (sem base64 — user_text ja tem a descricao das imgs)
    ctx = post.local_pipeline_context or {}
    ctx['orch_conversa'] = {
        'user_text': orch.get('user_text') or '',
        'assistant_text': orch.get('assistant_text') or '',
    }
    post.local_pipeline_context = ctx
    logger.info('[posts.simple] orquestrador (Fase 1) gerou cena + conversa post=%s', post.id)
    return True


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

    # Define TODOS os campos em MEMORIA, sem salvar ainda. Enquanto o orquestrador
    # roda (status 'generating'), nenhum texto deve aparecer no front — so um
    # UNICO save no fim revela todos os campos juntos.
    post.title = structured.get('title', '') or ''
    post.subtitle = structured.get('subtitle', '') or ''
    post.image_prompt = ''  # sera a CENA do orquestrador (FONTE UNICA)
    post.caption = structured.get('caption', '') or ''
    post.hashtags = structured.get('hashtags') or []
    post.cta = structured.get('cta_text') or ''
    # Guarda o payload bruto do agente para auditoria/comparacao entre pipelines
    post.copy_payload = {'_simple_agent': structured}
    post.ia_provider = 'openai'
    post.ia_model_text = result['model']

    _log_usage(post, result['model'], result['usage'], purpose='generate_post_simple')

    # FASE 1 (parte 2): orquestrador cria a CENA (image_prompt) — FONTE UNICA.
    # Le os textos da MEMORIA (ainda nao salvos). NAO envia ao Gemini aqui.
    scene_ok = False
    try:
        scene_ok = _simple_orchestrate_into_image_prompt(post)
    except Exception:
        logger.exception('[posts.simple] orquestrador Fase 1 falhou post=%s', post_id)

    if not scene_ok or not (post.image_prompt or '').strip():
        # Sem fallback da OpenAI: o orquestrador e a fonte unica. Falha rara
        # (erro de API/parse) -> re-tenta a Fase 1 inteira.
        logger.error('[posts.simple] sem cena do orquestrador post=%s — retry', post_id)
        raise self.retry(countdown=30)

    # UM unico save: textos + cena + status, tudo de uma vez.
    post.status = 'pending'
    post.save()

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

    # Referencias: AS MESMAS persistidas na Fase 1 (uploads do form OU ate N do
    # KB). O Gemini precisa receber as mesmas imagens/ordem que o orquestrador
    # viu, pois a cena aprovada fala "IMAGEM 1/2..." e tem que casar.
    references = _simple_refs_to_payload(_simple_build_references(post, kb))

    try:
        # -------- Etapa 1: FUNDO SEM TEXTO --------
        # O orquestrador JA rodou na FASE 1 e gravou a CENA em post.image_prompt
        # (aprovada/editada pelo usuario no front). Aqui NAO re-orquestramos:
        # mandamos a cena aprovada direto ao Gemini.
        scene_prompt = post.image_prompt or ''
        orchestration_dbg = None

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
        # No fluxo simples atual nao usamos dossie de layout (refs sao genericas);
        # a zona/alinhamento de texto fica a cargo das regras do briefing + KB.
        reference_layout = []
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


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def revise_scene_task(self, post_id: int, message: str = ''):
    """ALTERAR CENA - IA: revisa a CENA (image_prompt) via orquestrador, LOCAL
    (sem n8n), continuando a conversa do orquestrador (text-only, com cache).
    Grava a nova cena, registra o custo (com cache) e volta o post para
    'pending' (reaprovacao). O limite de 1 alteracao e validado na view."""
    from apps.posts.models import Post
    from apps.posts.services.post_orchestrator import revise_scene
    from apps.posts.tasks import _record_ai_usage

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.simple] revise_scene_task: post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'generating'
    post.save(update_fields=['status'])

    try:
        result = revise_scene(post, message)
    except Exception:
        logger.exception('[posts.simple] revise_scene falhou post=%s', post_id)
        result = None

    if not result:
        # Falha (API/parse). Volta para 'pending' sem aplicar.
        post.status = 'pending'
        post.save(update_fields=['status'])
        return {'success': False, 'post_id': post_id, 'error': 'revise_failed'}

    # Registra o CUSTO da alteracao (com cache_status) no ai_usage_log.
    _record_ai_usage(post, step='text_generation',
                     model=result.get('model', 'claude-sonnet-4-6'),
                     usage_dict=result.get('usage') or {}, purpose='orchestrator_revision')

    scene = (result['orchestration'].get('image_prompt_final') or '').strip()
    if scene:
        post.image_prompt = scene
        # Atualiza a conversa (assistant_text) — util se um dia encadear revisoes.
        ctx = post.local_pipeline_context or {}
        conv = ctx.get('orch_conversa') or {}
        conv['assistant_text'] = result.get('assistant_text') or conv.get('assistant_text', '')
        ctx['orch_conversa'] = conv
        post.local_pipeline_context = ctx

    post.status = 'pending'
    post.save()
    logger.info('[posts.simple] revise_scene_task OK post_id=%s', post_id)
    return {'success': True, 'post_id': post_id}
