"""
Celery tasks da pipeline interna de geracao de post.

Substitui os workflows N8N (gerar-post-appiamkt e gerarimagem-appiamkt)
quando o usuario clica em "Enviar Fluxo interno" no modal.

Tasks:
    - generate_post_text_task(post_id): gera texto via Claude Sonnet 4.5
    - generate_post_image_task(post_id, message): gera imagem via Gemini 3 Pro
"""

import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_post_text_task(self, post_id: int):
    """
    Gera o texto do post (title, subtitle, image_prompt, caption, hashtags,
    visual_brief, cta_text) via Claude Sonnet 4.5. Atualiza o Post no banco.

    Substitui o N8N workflow 'gerar-post-appiamkt'. Disparada quando o user
    clica em 'Enviar Fluxo interno' no modal.

    Fluxo:
        1. Carrega Post + KB
        2. Monta resumo da KB (preferindo n8n_compilation)
        3. Chama Claude via service
        4. Salva campos do Post (caption, hashtags, title, subtitle,
           image_prompt, visual_brief, cta)
        5. Loga em AIUsageLog
        6. Status final: 'awaiting_image' (user pode disparar imagem depois)
    """
    from apps.posts.models import Post
    from apps.posts.services.claude_post_generator import generate_post_text

    logger.info('[posts.local] generate_post_text_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    # Marca em progresso
    post.status = 'generating'
    post.save(update_fields=['status'])

    # Resumo da KB (igual ao fallback do N8N)
    kb_summary = _build_kb_summary(post.organization)

    # Formato (PostFormat ou dict legado)
    formato = _format_to_dict(post.post_format) if post.post_format else {
        'name': post.formats[0] if post.formats else 'feed',
        'aspect_ratio': '1:1',
    }

    # Logos da KB (filtrados pelos selecionados, se houver)
    logo_urls = list(_logos_from_org(post.organization, post=post))

    # Reference images do Post (PostReferenceImage) + descricao geral
    reference_images = list(_reference_images_from_post(post))
    ctx = post.local_pipeline_context or {}
    refs_usage_general = ctx.get('references_usage_description', '') or ''

    # Anexa observacao geral como linha extra na primeira referencia, OU
    # passa via knowledge_base_summary se nao houver refs (mais facil para o LLM)
    if refs_usage_general:
        kb_summary = (
            f'{kb_summary}\n\n'
            f'== Observacao sobre uso das referencias visuais ==\n'
            f'{refs_usage_general}'
        )

    try:
        result = generate_post_text(
            knowledge_base_summary=kb_summary,
            rede_social=post.social_network,
            formato=formato,
            tema=post.requested_theme,
            cta_requested=post.cta_requested,
            is_carousel=post.is_carousel,
            image_count=post.image_count,
            reference_images=reference_images,
            logo_urls=logo_urls,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Claude post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    structured = result['structured']
    usage = result['usage']

    # Normaliza hashtags: garante prefixo '#' em cada item (Claude as vezes esquece)
    raw_hashtags = structured.get('hashtags') or []
    normalized_hashtags = [
        h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
        for h in raw_hashtags if h
    ]
    structured['hashtags'] = normalized_hashtags

    # Aplica resultado no Post
    if post.is_carousel and isinstance(structured.get('slides'), list):
        # Carrossel: salva slides em campo dedicado (se existir) ou em caption
        slides = structured['slides']
        post.caption = structured.get('caption') or ''
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text') or ''
        # Slides ficam disponiveis para o gerador de imagem via primeiro slide
        if slides:
            first = slides[0]
            post.title = first.get('title', '')
            post.subtitle = first.get('subtitle', '')
            post.image_prompt = first.get('image_prompt', '')
            post.visual_brief = first.get('visual_brief', '')
        # Guarda todos os slides no JSON do post para a etapa de imagem
        post.slides_data = slides
    else:
        post.title = structured.get('title', '')
        post.subtitle = structured.get('subtitle', '')
        post.image_prompt = structured.get('image_prompt', '')
        post.visual_brief = structured.get('visual_brief', '')
        post.caption = structured.get('caption', '')
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text', '')

    post.ia_provider = 'anthropic'
    post.ia_model_text = result['model']
    # Status final 'pending' segue mesma semantica do callback N8N:
    # texto pronto, aguardando user clicar em "Gerar Imagem" depois.
    post.status = 'pending'
    post.save()

    # Loga custo
    _log_usage(post, result['model'], usage, purpose='generate_post_text')

    logger.info(
        '[posts.local] generate_post_text_task OK post_id=%s tokens_in=%s tokens_out=%s cost=$%s',
        post_id, usage.get('input_tokens'), usage.get('output_tokens'),
        usage.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        'model': result['model'],
        'usage': usage,
    }


# ---- Helpers ----------------------------------------------------------------


def _build_kb_summary(organization) -> str:
    """
    Constroi resumo textual da KB usado como contexto no prompt.
    Prefere `n8n_compilation.marketing_input_summary`; se vazio, monta string
    com 6 campos da KB.
    """
    from apps.knowledge.models import KnowledgeBase

    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return f'(Organizacao {organization.name} sem base de conhecimento)'

    # n8n_compilation pode ser dict (atual) ou string (legado)
    compilation = getattr(kb, 'n8n_compilation', None)
    summary_text = ''
    if isinstance(compilation, dict):
        summary_text = (compilation.get('marketing_input_summary') or '').strip()
    elif isinstance(compilation, str):
        summary_text = compilation.strip()
    if summary_text and len(summary_text) > 50:
        return summary_text

    # Fallback manual
    parts = [
        f'Empresa: {kb.nome_empresa or organization.name}',
    ]
    if kb.missao:
        parts.append(f'Missao: {kb.missao}')
    if kb.posicionamento:
        parts.append(f'Posicionamento: {kb.posicionamento}')
    if kb.tom_voz_externo:
        parts.append(f'Tom de voz: {kb.tom_voz_externo}')
    if kb.publico_externo:
        parts.append(f'Publico-alvo: {kb.publico_externo}')
    if kb.proposta_valor:
        parts.append(f'Proposta de valor: {kb.proposta_valor}')
    return '\n'.join(parts)


def _format_to_dict(post_format) -> dict:
    return {
        'name': post_format.name,
        'width': post_format.width,
        'height': post_format.height,
        'aspect_ratio': post_format.aspect_ratio,
    }


def _logos_from_org(organization, post=None):
    """
    Retorna URLs dos logos cadastrados na KB da org.
    Se post tiver local_pipeline_context.selected_logo_ids, filtra.
    """
    from apps.knowledge.models import KnowledgeBase, Logo
    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return []
    qs = Logo.objects.filter(knowledge_base=kb)
    if post is not None:
        ctx = post.local_pipeline_context or {}
        selected_ids = ctx.get('selected_logo_ids') or []
        if selected_ids:
            qs = qs.filter(id__in=selected_ids)
    return [l.s3_url for l in qs if l.s3_url]


def _reference_images_from_post(post):
    """Retorna lista de dicts com URL e descricao de uso de cada PostReferenceImage."""
    from apps.posts.models import PostReferenceImage
    refs = PostReferenceImage.objects.filter(post=post).order_by('order', 'id')
    out = []
    for ref in refs:
        out.append({
            'url': ref.s3_url,
            's3_key': ref.s3_key,
            'name': ref.original_name,
            'usage_description': getattr(ref, 'usage_description', '') or '',
            'aspects_to_use': getattr(ref, 'aspects_to_use', '') or '',
            'usage_type': getattr(ref, 'usage_type', '') or '',
        })
    return out


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_post_image_task(self, post_id: int, message: str = ''):
    """
    Gera a imagem do post via Gemini 3 Pro Image e salva no S3.

    Substitui o N8N workflow 'gerarimagem-appiamkt'. Disparada quando o user
    clica em 'Gerar Imagem' no detalhe do post (para posts com pipeline=local).

    Fluxo:
        1. Carrega Post + KB
        2. Coleta paleta, tipografia, referencias (logos, ref_kb, ref_post)
        3. Gera presigned URLs (24h) para todas as referencias
        4. Chama Gemini via service (multimodal: prompt + inline_data das refs)
        5. Faz upload do PNG no S3
        6. Atualiza Post (post_images, image_s3_url, status='image_ready')
        7. Loga em AIUsageLog
    """
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.models import Post
    from apps.posts.services.gemini_image_generator import generate_post_image

    logger.info('[posts.local] generate_post_image_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format', 'user'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'image_generating'
    post.save(update_fields=['status'])

    # KB + dados de design
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    paleta = _kb_colors(kb)
    tipografia = _kb_typography(kb)
    publico_alvo = (kb.publico_externo if kb else '') or ''
    marketing_input_summary = _kb_summary_marketing(kb)
    formato_px = _formato_px(post)

    ctx = post.local_pipeline_context or {}
    refs_usage_general = ctx.get('references_usage_description', '') or ''

    # text_render_mode determinado AGORA (precisa antes de _collect_references
    # para decidir se inclui logo ou nao)
    import os as _os
    text_render_mode = (
        ctx.get('text_render_mode')
        or _os.environ.get('POST_TEXT_RENDER_MODE', 'pillow')
    ).lower()

    # Coleta logos + uploads como image_parts (refs KB NAO sao mais
    # incluidas — viram dossie textual lido de visual_analysis, ver abaixo)
    references = _collect_references(kb=kb, post=post, text_render_mode=text_render_mode)

    # ============================================================
    # DOSSIE DAS REFS DA KB — lookup puro (sem reanalise por Vision)
    # ============================================================
    # Le o dossie visual ja gravado em ReferenceImage.visual_analysis das
    # refs selecionadas. Gatilho 3: se alguma ainda nao foi analisada,
    # analisa inline AGORA e persiste (a info fica garantida para sempre).
    # O dossie + a intencao do user vao para o ORCHESTRATOR, que decide o
    # quanto de cada aspecto entra no prompt final do Gemini. kb_translations
    # so e usado como fallback quando o orchestrator nao roda.
    kb_dossiers = _collect_kb_dossiers(kb=kb, post=post)
    kb_translations = []

    # Adiciona references_usage_description ao marketing_input_summary
    if refs_usage_general:
        marketing_input_summary = (
            f'{marketing_input_summary}\n\n'
            f'OBSERVACAO sobre uso das imagens de referencia anexadas: '
            f'{refs_usage_general}'
        )

    # Etapa 4.16: desativado o Claude Vision em favor de dereferenciacao
    # simples por imagem
    product_analyses = []

    # brand_keywords: usado em mode='sanitized'
    brand_keywords = _brand_keywords_from_kb(kb)

    # ============================================================
    # ORCHESTRATOR — analisa briefing + imagens e produz prompt otimizado
    # + layout_plan + spatial_instructions
    # ============================================================
    orchestrator_disabled = _os.environ.get('POST_DISABLE_ORCHESTRATOR', '').lower() in ('1', 'true', 'yes')
    orchestration_output = None
    spatial_instructions = ''
    layout_document = None
    # Orchestrator roda quando ha imagens (logos/uploads) OU dossies de refs
    # da KB selecionadas — ele e quem filtra os dossies pela intencao do user.
    if not orchestrator_disabled and (references or kb_dossiers):
        try:
            from apps.posts.services.post_orchestrator import orchestrate_post
            aspect = (post.post_format.aspect_ratio if post.post_format else '') or ''
            orch_result = orchestrate_post(
                post=post,
                references=references,
                kb_summary=marketing_input_summary,
                paleta=paleta,
                tipografia=tipografia,
                references_usage_description=ctx.get('references_usage_description', '') or '',
                formato_px=formato_px,
                aspect_ratio=aspect,
                kb_dossiers=kb_dossiers,
            )
            if orch_result:
                orchestration_output = orch_result['orchestration']
                # Persiste para auditoria
                ctx['orchestration'] = orchestration_output
                ctx['orchestration_usage'] = orch_result.get('usage', {})
                post.local_pipeline_context = ctx
                post.save(update_fields=['local_pipeline_context'])

                # Aplica decisoes do orchestrator
                final_prompt = orchestration_output.get('image_prompt_final', '')
                if final_prompt:
                    post.image_prompt = final_prompt
                    post.save(update_fields=['image_prompt'])
                mode_decided = orchestration_output.get('text_render_mode')
                if mode_decided in ('inline', 'sanitized', 'pillow'):
                    text_render_mode = mode_decided
                spatial_instructions = orchestration_output.get(
                    'spatial_instructions_for_gemini', ''
                ) or ''
                # layout_document = "divs" do texto decididas pelo diretor de arte
                # (base do canvas editavel). Se presente, o texto vai via Pillow.
                ld = orchestration_output.get('layout_document') or None
                if ld and ld.get('elements'):
                    layout_document = ld
                    text_render_mode = 'pillow'
                logger.info(
                    '[posts.local] orchestrator -> mode=%s, layout_doc_els=%s, spatial_len=%d',
                    text_render_mode,
                    len((layout_document or {}).get('elements', [])),
                    len(spatial_instructions),
                )
        except Exception:
            logger.exception('[orchestrator] falhou — segue com prompt cru')

    # Fallback (orchestrator off/falhou): injeta dossies como directives
    # textuais no prompt do Gemini, SEM IA extra (lookup puro).
    if kb_dossiers and orchestration_output is None:
        kb_translations = _dossiers_to_translations(kb_dossiers)

    # Se ha uma ref marcada com aspecto 'layout_composicao', queremos replicar
    # o layout dela com as FONTES da KB — isso exige modo pillow.
    layout_dossier = _layout_dossier(kb_dossiers)
    if layout_dossier:
        text_render_mode = 'pillow'
    # ============================================================

    # Smart Pillow overlay — prepara layout_spec, fonts e logo se mode='pillow'
    # Ordem de precedencia (modal vence): brand_spec (base) < orchestrator <
    # dossie do aspecto 'layout_composicao' selecionado no modal.
    pillow_kwargs = {}
    if text_render_mode == 'pillow':
        pillow_kwargs = _prepare_pillow_overlay(post, kb, formato_px)
        # Sobrescreve layout_spec com layout_plan do orchestrator (se houver)
        layout_plan = (orchestration_output or {}).get('layout_plan') or {}
        if layout_plan:
            pillow_kwargs['pillow_layout_spec'] = _layout_plan_to_spec(
                layout_plan, fallback=pillow_kwargs.get('pillow_layout_spec', {}),
            )
        # OVERRIDE final — dossie da ref de layout vence (alinhamento por bloco,
        # zonas %, peso/caixa). Fontes e cores continuam vindo da KB.
        if layout_dossier:
            dossier_spec = _dossier_to_layout_spec(layout_dossier, paleta=paleta)
            # Adaptacao inteligente de formato (LLM) quando a ref de layout
            # nasceu num aspect ratio diferente do post (ex: 1:1 -> 9:16).
            src_ar = layout_dossier.get('_source_ar')
            tgt_ar = _aspect_ratio_to_float(
                post.post_format.aspect_ratio if post.post_format else ''
            )
            if src_ar and tgt_ar and abs(float(src_ar) - tgt_ar) / max(float(src_ar), tgt_ar) > 0.15:
                try:
                    from apps.posts.services.post_orchestrator import adapt_layout_spec
                    adapted = adapt_layout_spec(dossier_spec, float(src_ar), tgt_ar, formato_px)
                    if adapted:
                        dossier_spec = adapted
                        logger.info('[posts.local] layout adaptado AR %s -> %s', src_ar, tgt_ar)
                except Exception:
                    logger.exception('[posts.local] adaptacao de layout falhou — usa spec original')
            pillow_kwargs['pillow_layout_spec'] = {
                **(pillow_kwargs.get('pillow_layout_spec') or {}),
                **dossier_spec,
            }

        # Posicao do logo escolhida no modal vence (override do dossie/spec)
        user_logo_pos = (ctx.get('logo_position') or '').strip()
        if user_logo_pos:
            _spec = pillow_kwargs.get('pillow_layout_spec') or {}
            _spec['logo_position'] = user_logo_pos
            pillow_kwargs['pillow_layout_spec'] = _spec

    # Grafismos DETERMINISTICOS (fideis ao dossie): para cada KB ref com
    # aspecto 'grafismos', constroi elementos role='grafismo' usando posicoes
    # exatas de grid.zonas + cores reais de assets_grafismos + faixa branca de
    # logo_na_referencia. Remove quaisquer grafismos emitidos pelo orquestrador.
    if layout_document and kb_dossiers:
        deterministic_grafismos = []
        for d in kb_dossiers:
            if 'grafismos' in (d.get('aspects') or []):
                deterministic_grafismos.extend(
                    _grafismos_from_dossier(d.get('dossier') or {})
                )
        if deterministic_grafismos:
            elements = layout_document.get('elements') or []
            elements = [
                e for e in elements
                if (e.get('role') or '').lower() != 'grafismo'
            ]
            layout_document['elements'] = deterministic_grafismos + elements
            logger.info(
                '[posts.local] %d grafismos deterministicos injetados',
                len(deterministic_grafismos),
            )

    # Roteamento de PRODUTOS (cutout-composite): refs de produto sao composta-
    # das via Pillow, NAO enviadas a Gemini (a cena vem sem o produto). Mapeia
    # image_n (1-based no orchestrator) -> url do produto, e remove esses refs
    # da lista que vai ao Gemini.
    product_urls = {}
    for i, ref in enumerate(references, 1):
        if str(ref.get('tipo', '')).lower() == 'produto' and ref.get('url'):
            product_urls[i] = ref['url']
    gemini_references = [
        r for r in references
        if str(r.get('tipo', '')).lower() != 'produto'
    ]
    # Anexa URL aos elementos 'produto' do layout_document (image_n -> url)
    if layout_document and product_urls:
        elements = layout_document.get('elements') or []
        for el in elements:
            if (el.get('role') or '').lower() == 'produto':
                n = el.get('image_n')
                if n in product_urls:
                    el['image_url'] = product_urls[n]
        # Se o orquestrador esqueceu de emitir elementos produto, injeta um
        # default por produto (bottom-right) p/ nao perder o produto.
        existing_n = {e.get('image_n') for e in elements
                      if (e.get('role') or '').lower() == 'produto'}
        for n, url in product_urls.items():
            if n not in existing_n:
                elements.append({
                    'role': 'produto', 'image_n': n, 'image_url': url,
                    'x_pct': 70, 'y_pct': 70, 'width_pct': 25,
                })
        layout_document['elements'] = elements

    try:
        result = generate_post_image(
            post=post,
            references=gemini_references,
            paleta=paleta,
            tipografia=tipografia,
            publico_alvo=publico_alvo,
            marketing_input_summary=marketing_input_summary,
            formato_px=formato_px,
            product_analyses=product_analyses,
            text_render_mode=text_render_mode,
            brand_keywords=brand_keywords,
            spatial_instructions=spatial_instructions,
            references_usage_general=refs_usage_general,
            kb_translations=kb_translations,
            layout_document=layout_document,
            product_urls=product_urls,
            **pillow_kwargs,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Gemini post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    # Upload PNG no S3
    s3_key, s3_url = _upload_image_to_s3(
        org_id=post.organization.id,
        post_id=post.id,
        png_bytes=result['png_bytes'],
        mime_type=result.get('mime_type', 'image/png'),
    )

    # Upload do PNG CRU (cena do Gemini SEM texto) — base do canvas editavel
    raw_bytes = result.get('raw_png_bytes')
    if raw_bytes:
        try:
            raw_key, raw_url = _upload_image_to_s3(
                org_id=post.organization.id,
                post_id=post.id,
                png_bytes=raw_bytes,
                mime_type='image/png',
            )
            post.raw_image_s3_key = raw_key
            post.raw_image_s3_url = raw_url
        except Exception:
            logger.exception('[posts.local] falha upload raw png')

    # Cria PostImage (model FK que o frontend le via post.images.all())
    # Equivalente ao que o callback N8N faz em views_webhook.py
    from apps.posts.models import PostImage
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    next_order = (max_order if max_order is not None else -1) + 1
    PostImage.objects.create(
        post=post,
        s3_key=s3_key,
        s3_url=s3_url,
        order=next_order,
    )

    # Atualiza Post (campos principais + lista json)
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = result['model']
    img_entry = {
        's3_key': s3_key,
        'url': s3_url,
        'width': post.image_width or None,
        'height': post.image_height or None,
    }
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append(img_entry)
    post.generated_images = existing
    post.status = 'image_ready'
    post.save()

    # Loga custo
    _log_usage_gemini(
        post,
        result['model'],
        result.get('cost_usd', 0),
        usage_metadata=result.get('usage') or {},
    )

    logger.info(
        '[posts.local] generate_post_image_task OK post_id=%s s3_key=%s cost=$%s',
        post_id, s3_key, result.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        's3_key': s3_key,
        's3_url': s3_url,
        'cost_usd': result.get('cost_usd'),
    }


def _analyze_products_in_references(references, brand_context: str = '') -> list:
    """
    Para cada referencia com tipo contendo 'produto', baixa a imagem e
    chama Claude Vision para gerar descricao estruturada (subject preservation).
    brand_context: string descrevendo a marca/segmento (ajuda Claude a
        identificar modelo/versao exato do produto).
    Retorna lista de dicts (1 por produto, na mesma ordem em que aparecem
    nas references), cada um com:
      {product_name, distinctive_features, keep_unchanged_list, ...}

    Custo: ~$0.005 por produto. Falhas individuais nao quebram a task
    (descricao vazia entra como fallback no prompt).
    """
    from apps.posts.services.claude_post_generator import (
        analyze_product_image, download_image_bytes,
    )
    analyses = []
    for ref in references:
        tipo = str(ref.get('tipo', '')).lower()
        if 'produto' not in tipo:
            continue
        url = ref.get('url')
        if not url:
            analyses.append({})
            continue
        try:
            img_bytes, mime = download_image_bytes(url)
            if not img_bytes:
                analyses.append({})
                continue
            result = analyze_product_image(
                img_bytes, mime_type=mime, brand_context=brand_context,
            )
            analyses.append(result.get('structured') or {})
            logger.info(
                '[posts.local] product vision analysis: %s (%s tokens)',
                (result.get('structured') or {}).get('product_name', '?'),
                (result.get('usage') or {}).get('total_tokens', '?'),
            )
        except Exception:
            logger.exception('[posts.local] Falha em analyze_product_image')
            analyses.append({})
    return analyses


def _layout_plan_to_spec(layout_plan: dict, fallback: dict = None) -> dict:
    """
    Converte layout_plan (formato do orchestrator) em layout_spec (formato
    consumido pelo apply_text_overlay do Pillow).

    Schema layout_plan (do orchestrator):
      {
        "title_zone": {"position": "top-left", "width_pct": 60, "height_pct": 22, ...},
        "subtitle_zone": {...},
        "logo_zone": {"position": "top-right", "width_pct": 12, "height_pct": 8},
        "cta_zone": {"position": "bottom-center", ...},
        "main_subject_zone": {...}
      }

    Schema layout_spec (do Pillow):
      {
        "title_position": "top-left", "title_size_pct": 8, "title_weight": "bold",
        "subtitle_offset": "below_title", "subtitle_size_pct": 3,
        "logo_position": "top-right", "logo_size_pct": 12,
        "cta_style": "pill", "cta_position": "bottom-center",
        "alignment": "left", "padding_pct": 5,
      }
    """
    base = dict(fallback or {})

    title_zone = layout_plan.get('title_zone') or {}
    if title_zone:
        base['title_position'] = title_zone.get('position', base.get('title_position', 'top-left'))
        # height_pct da zona vira title_size_pct (proporcional, com cap)
        h = float(title_zone.get('height_pct', 22))
        base['title_size_pct'] = max(6, min(h * 0.35, 12))  # 35% da altura da zona = tamanho da fonte

    subtitle_zone = layout_plan.get('subtitle_zone') or {}
    if subtitle_zone:
        h_sub = float(subtitle_zone.get('height_pct', 8))
        base['subtitle_size_pct'] = max(2.5, min(h_sub * 0.35, 5))

    logo_zone = layout_plan.get('logo_zone') or {}
    if logo_zone:
        base['logo_position'] = logo_zone.get('position', base.get('logo_position', 'top-right'))
        base['logo_size_pct'] = float(logo_zone.get('width_pct', 12))

    cta_zone = layout_plan.get('cta_zone') or {}
    if cta_zone:
        base['cta_position'] = cta_zone.get('position', base.get('cta_position', 'bottom-center'))

    # Defaults pra completar
    base.setdefault('title_weight', 'bold')
    base.setdefault('title_color_hint', 'auto_contrast')
    base.setdefault('subtitle_offset', 'below_title')
    base.setdefault('subtitle_weight', 'regular')
    base.setdefault('cta_style', 'pill')
    base.setdefault('alignment', 'left')
    base.setdefault('padding_pct', 5)
    base.setdefault('background_treatment', 'none')

    base['source'] = 'orchestrator_layout_plan'
    return base


# ---- Layout a partir do dossie da ref marcada com aspecto 'layout' ----------

_ALIGN_MAP = {
    'esquerda': 'left', 'left': 'left',
    'centro': 'center', 'center': 'center', 'centralizado': 'center',
    'direita': 'right', 'right': 'right',
    'justificado': 'left',  # Pillow nao justifica — trata como left
}


def _norm_align(value, default='left') -> str:
    return _ALIGN_MAP.get(str(value or '').strip().lower(), default)


def _anchor_from_pct(x_pct, y_pct):
    """Mapeia x%/y% da zona para uma das 9 ancoras (logo/cta)."""
    try:
        x, y = float(x_pct), float(y_pct)
    except (TypeError, ValueError):
        return None
    h = 'left' if x < 38 else ('center' if x < 60 else 'right')
    v = 'top' if y < 33 else ('middle' if y < 60 else 'bottom')
    return f'{v}-{h}'


def _find_zone(zonas, *keywords):
    for z in zonas or []:
        name = (z.get('nome') or '').lower()
        cont = (z.get('conteudo') or '').lower()
        if any(k in name or k in cont for k in keywords):
            return z
    return None


def _zone_pct(z):
    if not z:
        return None
    return {
        'x_pct': z.get('x_pct', 0),
        'y_pct': z.get('y_pct', 0),
        'width_pct': z.get('largura_pct') or z.get('width_pct') or 90,
    }


def _aspect_ratio_to_float(ar):
    """'9:16' -> 0.5625 ; '1:1' -> 1.0. None se invalido."""
    try:
        s = str(ar or '')
        if ':' in s:
            w, h = s.split(':', 1)
            h = float(h)
            return round(float(w) / h, 3) if h else None
    except Exception:
        return None
    return None


def _layout_dossier(kb_dossiers):
    """Retorna o dossie da ref marcada com aspecto 'layout_composicao' (ou None)."""
    for d in kb_dossiers or []:
        if 'layout_composicao' in (d.get('aspects') or []):
            return d.get('dossier') or {}
    return None


def _grafismos_from_dossier(dossier: dict) -> list:
    """Constroi elementos role='grafismo' deterministicos do dossie:
      - assets_grafismos[].tipo -> forma (faixa/selo/linha).
      - grid.zonas mapeia funcao -> coords (faixa_titulo, selo_cta, rodape_logo).
      - estilo "inferior direito arredondado" -> cantos orgânico (so br).
      - logo_na_referencia.fundo branco -> faixa branca de rodape (full-width).
    Cor EXATA do dossie (sem snap a paleta da marca).
    """
    if not isinstance(dossier, dict):
        return []
    out: list = []
    grid = dossier.get('grid') or {}
    zonas = {(z.get('nome') or '').lower(): z for z in (grid.get('zonas') or [])}

    def _coord(z, key, default):
        if not z:
            return default
        v = z.get(key)
        return v if v is not None else default

    for g in (dossier.get('assets_grafismos') or []):
        tipo = (g.get('tipo') or '').lower()
        cor = g.get('cor') or ''
        funcao = (g.get('funcao') or '').lower()
        estilo = (g.get('estilo') or '').lower()
        # mapeia funcao -> zona do grid p/ posicao real
        zona = None
        if 'titulo' in funcao:
            zona = zonas.get('faixa_titulo')
        elif 'call' in funcao or 'cta' in funcao:
            zona = zonas.get('selo_cta')
        elif 'rodape' in funcao or 'footer' in funcao:
            zona = zonas.get('rodape_logo') or zonas.get('rodape')
        if any(t in tipo for t in ('faixa', 'banda', 'background', 'retangulo')):
            cantos = None
            if 'inferior direito arredondado' in estilo or 'br arredondado' in estilo:
                cantos = {'tl': False, 'tr': False, 'br': True, 'bl': False}
            elif 'inferior esquerdo arredondado' in estilo:
                cantos = {'tl': False, 'tr': False, 'br': False, 'bl': True}
            el = {
                'role': 'grafismo', 'forma': 'faixa', 'cor': cor,
                'x_pct': _coord(zona, 'x_pct', 0),
                'y_pct': _coord(zona, 'y_pct', 0),
                'width_pct': _coord(zona, 'largura_pct', 70),
                'height_pct': _coord(zona, 'altura_pct', 16),
                'raio_pct': 6,
            }
            if cantos:
                el['cantos'] = cantos
            out.append(el)
        elif any(t in tipo for t in ('selo', 'circulo', 'badge')):
            out.append({
                'role': 'grafismo', 'forma': 'selo', 'cor': cor,
                'x_pct': _coord(zona, 'x_pct', 8),
                'y_pct': _coord(zona, 'y_pct', 58),
                'width_pct': _coord(zona, 'largura_pct', 22),
                'height_pct': _coord(zona, 'altura_pct', 22),
            })
        elif any(t in tipo for t in ('linha', 'divisor', 'rule')):
            out.append({
                'role': 'grafismo', 'forma': 'linha', 'cor': cor,
                'x_pct': _coord(zona, 'x_pct', 30),
                'y_pct': _coord(zona, 'y_pct', 94),
                'width_pct': _coord(zona, 'largura_pct', 40),
                'height_pct': _coord(zona, 'altura_pct', 0.3),
            })

    # Faixa branca de rodape (extraida de logo_na_referencia)
    lnr = dossier.get('logo_na_referencia') or {}
    if lnr.get('presente') and 'branco' in (lnr.get('fundo') or '').lower():
        rod = zonas.get('rodape_logo') or {}
        out.append({
            'role': 'grafismo', 'forma': 'faixa', 'cor': '#FFFFFF',
            'x_pct': 0,
            'y_pct': _coord(rod, 'y_pct', 88),
            'width_pct': 100,
            'height_pct': _coord(rod, 'altura_pct', 12),
            'raio_pct': 1,
        })
    return out


def _hex_to_rgb_t(h):
    h = (h or '').lstrip('#')
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _nearest_palette_hex(hex_str, paleta):
    """Cor observada -> cor mais proxima da paleta da KB (consistencia de marca)."""
    rgb = _hex_to_rgb_t(hex_str)
    if not rgb or not paleta:
        return None
    best, best_d = None, 1e18
    for c in paleta:
        prgb = _hex_to_rgb_t(c.get('hex'))
        if not prgb:
            continue
        d = sum((a - b) ** 2 for a, b in zip(rgb, prgb))
        if d < best_d:
            best_d, best = d, c.get('hex')
    return best


def _dossier_to_layout_spec(dossier: dict, paleta: list = None) -> dict:
    """
    Converte o dossie de uma ref (aspecto layout) em spec parcial do Pillow:
    zonas % de titulo/subtitulo, alinhamento/peso/caixa POR BLOCO, posicao de
    logo/cta. Cores do texto = cor observada na ref SNAPADA na paleta da KB.
    Fontes vem da KB.
    """
    spec = {}
    tx = dossier.get('texto_x_imagem') or {}
    blocos = tx.get('blocos') or []

    def _bloco(papel):
        for b in blocos:
            if (b.get('papel') or '').lower() == papel:
                return b
        return {}

    tb, sb, cb = _bloco('titulo'), _bloco('subtitulo'), _bloco('cta')
    overall = _norm_align(tx.get('alinhamento_paragrafo'), 'left')
    spec['title_align'] = _norm_align(tb.get('alinhamento_paragrafo'), overall)
    spec['subtitle_align'] = _norm_align(sb.get('alinhamento_paragrafo'), overall)
    spec['cta_align'] = _norm_align(cb.get('alinhamento_paragrafo'), overall)
    spec['alignment'] = spec['title_align']
    # Cor do titulo = cor primaria da marca (KB), com fallback de contraste.
    spec['title_color_hint'] = 'brand_primary_safe'
    # Sem painel/overlay do Pillow atras do texto (o fundo limpo vem da cena).
    spec['background_treatment'] = 'none'
    # Subtitulo = neutro legivel (auto contraste), distinto do titulo de marca.
    spec['subtitle_color_hint'] = 'auto_contrast'
    # Se a ref informou a cor de cada bloco, snap na paleta da KB (a cor que a
    # marca usou na referencia, garantida dentro da identidade).
    if paleta:
        tcor = _nearest_palette_hex(tb.get('cor'), paleta)
        if tcor:
            spec['title_color'] = tcor
        scor = _nearest_palette_hex(sb.get('cor'), paleta)
        if scor:
            spec['subtitle_color'] = scor
    if (tb.get('peso') or '').lower() in ('bold', 'negrito', 'semibold', 'black'):
        spec['title_weight'] = 'bold'
    if (tb.get('caixa') or '').lower() in ('alta', 'maiuscula', 'uppercase'):
        spec['title_case'] = 'alta'
    if (sb.get('caixa') or '').lower() in ('alta', 'maiuscula', 'uppercase'):
        spec['subtitle_case'] = 'alta'

    zonas = (dossier.get('grid') or {}).get('zonas') or []
    tz = _find_zone(zonas, 'titulo', 'texto_principal', 'título', 'bloco_texto')
    sz = _find_zone(zonas, 'subtitulo', 'texto_secundario', 'subtítulo')
    # subtitulo so e bloco INDEPENDENTE se for uma zona distinta da do titulo
    # (quando titulo+subtitulo compartilham uma zona, ficam colados).
    if sz is not None and tz is not None and (
        sz is tz or (sz.get('x_pct') == tz.get('x_pct') and sz.get('y_pct') == tz.get('y_pct'))
    ):
        sz = None
    lz = _find_zone(zonas, 'logo')
    cz = _find_zone(zonas, 'cta', 'call', 'botao', 'botão')

    if tz:
        spec['title_zone_pct'] = _zone_pct(tz)
        if tz.get('altura_pct'):
            # zona de titulo isolada -> fonte maior; zona compartilhada
            # (titulo+subtitulo) -> fracao menor pra caber os dois. Teto baixo
            # pra o texto NAO dominar a arte (peso de ocupacao da referencia).
            frac = 0.32 if sz is not None else 0.18
            spec['title_size_pct'] = max(5, min(float(tz['altura_pct']) * frac, 10))
    elif tx.get('posicao_texto'):
        spec['title_position'] = tx.get('posicao_texto')

    if sz:
        spec['subtitle_zone_pct'] = _zone_pct(sz)
        if sz.get('altura_pct'):
            spec['subtitle_size_pct'] = max(2.5, min(float(sz['altura_pct']) * 0.45, 6))

    if lz:
        anc = _anchor_from_pct(lz.get('x_pct'), lz.get('y_pct'))
        if anc:
            spec['logo_position'] = anc
        if lz.get('largura_pct'):
            spec['logo_size_pct'] = max(6, min(float(lz['largura_pct']), 25))

    if cz:
        anc = _anchor_from_pct(cz.get('x_pct'), cz.get('y_pct'))
        if anc:
            spec['cta_position'] = anc

    spec['source'] = 'dossier_layout_aspect'
    return spec


def _prepare_pillow_overlay(post, kb, formato_px: str) -> dict:
    """
    Monta os argumentos opcionais do Smart Pillow Overlay:
      - pillow_layout_spec: kb.brand_layout_spec (cached) OU wireframe
        fallback baseado no aspect_ratio do PostFormat.
      - pillow_title_font_path / pillow_subtitle_font_path: fontes resolvidas
        via FontResolver (Typography da KB -> Google Font / CustomFont -> DejaVu)
      - pillow_logo_url: presigned URL do logo selecionado (primeiro do
        local_pipeline_context.selected_logo_ids, ou primary da KB)
    """
    from apps.posts.services.brand_layout_analyzer import analyze_brand_layout_from_references
    from apps.posts.services.layout_wireframes import wireframe_for_aspect
    from apps.posts.services.font_resolver import (
        resolve_font_for_kb, system_dejavu_path,
    )

    out = {}

    # ---- Layout spec --------------------------------------------------
    spec = None
    try:
        spec = analyze_brand_layout_from_references(kb)
    except Exception:
        logger.exception('[posts.local] brand_layout_analyzer falhou — fallback wireframe')
    if not spec:
        aspect = ''
        if post.post_format and post.post_format.aspect_ratio:
            aspect = post.post_format.aspect_ratio
        spec = wireframe_for_aspect(aspect, formato_px)
        spec['source'] = 'wireframe_fallback'
    else:
        spec.setdefault('source', 'analyzed_from_references')
    out['pillow_layout_spec'] = spec

    # ---- Fontes -------------------------------------------------------
    try:
        out['pillow_title_font_path'] = (
            resolve_font_for_kb(kb, usage_filter='titulo', weight='bold')
            or system_dejavu_path('bold')
        )
    except Exception:
        logger.exception('Erro resolvendo title font')
        out['pillow_title_font_path'] = system_dejavu_path('bold')

    try:
        out['pillow_subtitle_font_path'] = (
            resolve_font_for_kb(kb, usage_filter='subtitulo', weight='regular')
            or resolve_font_for_kb(kb, usage_filter='corpo', weight='regular')
            or resolve_font_for_kb(kb, usage_filter='texto', weight='regular')
            or system_dejavu_path('regular')
        )
    except Exception:
        logger.exception('Erro resolvendo subtitle font')
        out['pillow_subtitle_font_path'] = system_dejavu_path('regular')

    # ---- Logo URL -----------------------------------------------------
    out['pillow_logo_url'] = _resolve_logo_url_for_overlay(post, kb)

    return out


def _resolve_logo_url_for_overlay(post, kb):
    """Retorna presigned URL do logo selecionado pelo user (ou primario da KB)."""
    if not kb:
        return None
    from apps.core.services.s3_service import S3Service

    ctx = post.local_pipeline_context or {}
    selected_ids = ctx.get('selected_logo_ids') or []

    try:
        if selected_ids:
            logo = kb.logos.filter(id__in=selected_ids).first()
        else:
            logo = kb.logos.filter(is_primary=True).first() or kb.logos.first()
    except Exception:
        return None
    if not logo or not logo.s3_key:
        return None
    try:
        return S3Service.generate_presigned_download_url(logo.s3_key, expires_in=3600)
    except Exception:
        return logo.s3_url or None


def _brand_keywords_from_kb(kb) -> list:
    """
    Termos de MARCA/MODELO a sanitizar na CENA enviada ao Gemini (citar marca
    ativa priors). CONSERVADOR de proposito: nome da empresa + tokens com
    digito (modelos, ex: TM7) + acronimos all-caps curtos. NAO inclui palavras
    genericas (ex: "Cozinha", "Robot") pra nao quebrar a descricao do ambiente.
    Funciona para qualquer empresa (le da KB dinamicamente).
    """
    import re as _re
    if not kb:
        return []
    # Palavras genericas que NUNCA devem ser tratadas como marca
    stop = {
        'de', 'da', 'do', 'e', 'a', 'o', 'os', 'as', 'um', 'uma', 'que',
        'para', 'com', 'em', 'robot', 'robo', 'cozinha', 'kitchen', 'maquina',
        'aparelho', 'produto', 'equipamento', 'multifuncional', 'inteligente',
    }
    keywords = set()
    # Nome da empresa = marca por definicao (tokens com >=3 chars, nao-stop)
    for w in str(kb.nome_empresa or '').split():
        w = w.strip()
        if len(w) >= 3 and w.lower() not in stop:
            keywords.add(w)
    # Descricao do produto: SO modelos (token com digito) ou acronimos all-caps
    desc = (kb.descricao_produto or '')[:500]
    for tok in _re.findall(r'\b[A-Za-z0-9]{2,}\b', desc):
        if tok.lower() in stop:
            continue
        if any(c.isdigit() for c in tok):          # ex: TM7, TM6
            keywords.add(tok)
        elif tok.isupper() and 2 <= len(tok) <= 6:  # ex: acronimos de marca
            keywords.add(tok)
    return sorted(keywords)


def _brand_context_for_vision(post) -> str:
    """
    Monta uma string curta com contexto da marca para ajudar Claude Vision
    a identificar produto especifico (ex: 'Thermomix - robos de cozinha Vorwerk').
    Usa nome_empresa + descricao_produto da KB se disponivel.
    """
    from apps.knowledge.models import KnowledgeBase
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    if not kb:
        return ''
    parts = []
    if kb.nome_empresa:
        parts.append(kb.nome_empresa)
    if kb.descricao_produto:
        parts.append(kb.descricao_produto[:200])
    return ' — '.join(parts)


def _kb_colors(kb) -> list:
    if not kb:
        return []
    try:
        return [
            {
                'nome': c.name,
                'hex': c.hex_code,
                'tipo': c.color_type or 'primary',
            }
            for c in kb.colors.all().order_by('order')
        ]
    except Exception:
        return []


def _kb_typography(kb) -> list:
    if not kb:
        return []
    try:
        out = []
        for f in kb.typography_settings.all().order_by('order'):
            nome = (
                f.google_font_name if f.font_source == 'google'
                else (f.custom_font.name if f.custom_font else '')
            )
            out.append({
                'uso': f.usage,
                'origem': f.font_source or 'google',
                'nome': nome,
                'peso': f.google_font_weight if f.font_source == 'google' else 'regular',
            })
        return out
    except Exception:
        return []


def _kb_summary_marketing(kb) -> str:
    """Recupera marketing_input_summary do n8n_compilation, fallback string vazia."""
    if not kb:
        return ''
    compilation = getattr(kb, 'n8n_compilation', None)
    if isinstance(compilation, dict):
        return compilation.get('marketing_input_summary') or ''
    return ''


def _formato_px(post) -> str:
    if post.post_format and post.post_format.width and post.post_format.height:
        return f'{post.post_format.width}x{post.post_format.height}'
    if post.image_width and post.image_height:
        return f'{post.image_width}x{post.image_height}'
    return '1080x1080'


def dj_tz_now_iso() -> str:
    """Atalho para timezone-aware ISO timestamp."""
    from django.utils import timezone as dj_tz
    return dj_tz.now().isoformat()


def _collect_references(kb, post, text_render_mode: str = 'inline') -> list:
    """
    Coleta logos + PostReferenceImage como image_parts pro Gemini.

    NOVO comportamento:
    - Logos: em modo 'pillow' o logo e desenhado via Pillow overlay, entao
      e EXCLUIDO daqui (evita logo duplicado). Em outros modos, vai como
      image_part pra que Gemini renderize.
    - Refs da KB: NAO sao mais incluidas como image_parts. Em vez disso,
      passam pelo kb_reference_translator que extrai direcionamento textual.
      Use _collect_kb_refs_for_translation() para isso.
    - Uploads do post: sempre incluidos com fidelidade alta.

    Respeita post.local_pipeline_context:
      - selected_logo_ids: filtra logos
    """
    from apps.core.services.s3_service import S3Service

    ctx = post.local_pipeline_context or {}
    selected_logo_ids = set(ctx.get('selected_logo_ids') or [])

    out = []

    if kb and text_render_mode != 'pillow':
        # Logos — apenas em modo nao-pillow (em pillow, Pillow desenha)
        try:
            qs_logos = kb.logos.all().order_by('-is_primary', 'logo_type')
            for logo in qs_logos:
                if selected_logo_ids and logo.id not in selected_logo_ids:
                    continue
                if logo.s3_key:
                    try:
                        url = S3Service.generate_presigned_download_url(
                            logo.s3_key, expires_in=86400
                        )
                        out.append({'tipo': 'logotipo', 'url': url})
                    except Exception:
                        pass
        except Exception:
            pass

    # Post-specific references (uploads recentes — sempre incluidos)
    try:
        for ref in post.reference_image_files.all():
            if ref.s3_key:
                try:
                    url = S3Service.generate_presigned_download_url(
                        ref.s3_key, expires_in=86400
                    )
                    tipo = (ref.usage_type or 'referencia_post').strip().lower() or 'referencia_post'
                    out.append({
                        'tipo': tipo,
                        'url': url,
                        'usage_description': (ref.usage_description or '').strip(),
                    })
                except Exception:
                    pass
    except Exception:
        pass

    # Refs da KB marcadas com aspecto 'produto' — enviadas como IMAGEM ao Gemini
    # (fidelidade), NAO viram dossie de texto (ver _collect_kb_dossiers).
    try:
        reference_aspects = ctx.get('reference_aspects') or {}
        product_ref_ids = [
            rid for rid, asps in reference_aspects.items()
            if 'produto' in _normalize_aspects(asps)
        ]
        if kb and product_ref_ids:
            from apps.knowledge.models import ReferenceImage
            prod_refs = ReferenceImage.objects.filter(
                knowledge_base=kb, id__in=product_ref_ids
            )
            for ref in prod_refs:
                if not ref.s3_key:
                    continue
                try:
                    url = S3Service.generate_presigned_download_url(
                        ref.s3_key, expires_in=86400
                    )
                    out.append({'tipo': 'produto', 'url': url, 'usage_description': ''})
                except Exception:
                    pass
    except Exception:
        logger.exception('[posts.local] falha ao coletar refs KB de produto')

    return out


def _normalize_aspects(val) -> list:
    """Normaliza reference_aspects[ref] em lista de strings (aceita str legado)."""
    if isinstance(val, list):
        return [str(a).strip() for a in val if str(a).strip()]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _aspects_for_ref(reference_aspects: dict, ref_id) -> list:
    """Aspectos de uma ref (tenta chave str e int)."""
    return _normalize_aspects(
        reference_aspects.get(str(ref_id)) or reference_aspects.get(ref_id)
    )


def _collect_kb_dossiers(kb, post) -> list:
    """
    Le os dossies visuais (ReferenceImage.visual_analysis) das refs da KB
    selecionadas pelo user no modal. LOOKUP PURO — nao reanalisa o que ja
    tem dossie.

    Gatilho 3 (ultimo recurso): se uma ref selecionada ainda nao foi
    analisada (status != completed), analisa inline AGORA e PERSISTE — a
    info fica garantida para sempre, e da proxima vez e so leitura.

    Retorna lista de dicts {id, aspects, usage_description, dossier}:
      - aspects: lista de aspectos escolhidos no modal (multi-selecao) — a
        INTENCAO que o orchestrator usa para filtrar o dossie.
      - dossier: o JSON objetivo gravado em visual_analysis.

    NAO inclui logos (logo nao tem dossie nesta fase) nem refs marcadas como
    'produto' (essas vao como IMAGEM ao Gemini via _collect_references).
    """
    ctx = post.local_pipeline_context or {}
    selected_ref_ids = list(ctx.get('selected_reference_ids') or [])
    if not (kb and selected_ref_ids):
        return []

    general_guidance = (ctx.get('references_usage_description') or '').strip()
    # aspectos por ref: {ref_id(str/int): ['layout_composicao', 'grafismos', ...]}
    reference_aspects = ctx.get('reference_aspects') or {}

    from apps.knowledge.models import ReferenceImage
    from apps.knowledge.tasks import run_reference_image_analysis

    out = []
    refs = ReferenceImage.objects.filter(
        knowledge_base=kb, id__in=selected_ref_ids
    )
    for ref in refs:
        aspects = _aspects_for_ref(reference_aspects, ref.id)
        # Aspecto 'produto': a ref e enviada como IMAGEM ao Gemini
        # (_collect_references), NAO vira dossie de texto — preserva fidelidade.
        # So pula o dossie se 'produto' for o UNICO aspecto.
        if aspects == ['produto']:
            continue
        # Gatilho 3 — fallback inline: analisa e persiste se faltar dossie
        if ref.analysis_status != 'completed' or not ref.visual_analysis:
            try:
                logger.info('[posts.local] ref %s sem dossie — analisando inline', ref.id)
                run_reference_image_analysis(ref)
                ref.refresh_from_db(fields=['visual_analysis', 'analysis_status'])
            except Exception:
                logger.exception('[posts.local] fallback analise ref %s falhou', ref.id)

        dossier = ref.visual_analysis if isinstance(ref.visual_analysis, dict) else {}
        if not dossier:
            continue
        individual_desc = (getattr(ref, 'usage_description', '') or '').strip()
        # 'produto' nao e aspecto de dossie (a ref tambem vai como imagem)
        dossier_aspects = [a for a in aspects if a != 'produto']
        out.append({
            'id': ref.id,
            'aspects': dossier_aspects,
            'usage_description': individual_desc or general_guidance,
            'dossier': dossier,
        })
    return out


def _dossiers_to_translations(kb_dossiers: list) -> list:
    """
    Converte dossies em entradas kb_translations (formato consumido pelo
    gemini builder) SEM IA. Usado apenas como fallback quando o orchestrator
    nao roda — garante que o direcionamento das refs ainda chegue ao Gemini.
    """
    out = []
    for i, d in enumerate(kb_dossiers, 1):
        dossier = d.get('dossier') or {}
        bits = []
        recreation = (dossier.get('recreation_prompt') or '').strip()
        if recreation:
            bits.append(recreation)
        else:
            il = dossier.get('iluminacao') or {}
            comp = dossier.get('composicao') or {}
            il_txt = ' '.join(
                str(il.get(k, '')).strip()
                for k in ('tipo', 'direcao', 'temperatura', 'qualidade')
            ).strip()
            if il_txt:
                bits.append(f'Iluminacao: {il_txt}')
            if comp.get('enquadramento'):
                bits.append(f"Enquadramento: {comp.get('enquadramento')}")
        directives = ' '.join(b for b in bits if b).strip()
        if not directives:
            continue
        out.append({
            'ref_index': i,
            'category': (dossier.get('estilo_visual') or 'referencia').replace(' ', '_').lower(),
            'directives': directives,
            'kb_reference_id': d.get('id'),
            'usage_description_user': d.get('usage_description', ''),
        })
    return out


def _upload_image_to_s3(*, org_id: int, post_id: int, png_bytes: bytes, mime_type: str):
    """Faz upload do PNG gerado no S3 e retorna (s3_key, s3_url presigned)."""
    from apps.core.services.s3_service import S3Service
    from django.utils import timezone as dj_tz

    ext = 'png' if mime_type == 'image/png' else 'jpg'
    ts = int(dj_tz.now().timestamp() * 1000)
    s3_key = f'org-{org_id}/imagensgeradas/{ts}-post{post_id}-generated.{ext}'

    client = S3Service._get_s3_client()
    bucket = S3Service._get_bucket_name() if hasattr(S3Service, '_get_bucket_name') else None
    if not bucket:
        from django.conf import settings as dj_settings
        bucket = dj_settings.AWS_BUCKET_NAME

    client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=png_bytes,
        ContentType=mime_type,
    )

    s3_url = S3Service.generate_presigned_download_url(s3_key, expires_in=86400)
    return s3_key, s3_url


def _log_usage_gemini(post, model: str, cost_usd: float, usage_metadata: dict = None):
    """
    Loga custo Gemini no Post.ai_usage_log.
    usage_metadata: dict do response.usageMetadata do Gemini (tokens reais)
    """
    meta = usage_metadata or {}
    usage_dict = {
        'input_tokens': int(meta.get('promptTokenCount', 0) or 0),
        'output_tokens': int(meta.get('candidatesTokenCount', 0) or 0),
        'total_tokens': int(meta.get('totalTokenCount', 0) or 0),
        'cost_usd': float(cost_usd or 0),
    }
    _record_ai_usage(
        post,
        step='image_generation',
        model=model,
        usage_dict=usage_dict,
        images_generated=1,
    )


def _log_usage(post, model: str, usage: dict, purpose: str):
    """Wrapper retrocompativel — apenas redireciona para _record_ai_usage."""
    _record_ai_usage(
        post,
        step='text_generation',
        model=model,
        usage_dict=usage,
        images_generated=0,
    )


def _record_ai_usage(post, *, step: str, model: str, usage_dict: dict,
                     images_generated: int = 0):
    """
    Acumula custo de IA no Post + adiciona entry granular no ai_usage_log.

    step: 'text_generation' | 'image_generation'
    usage_dict: dict com input_tokens, output_tokens, cost_usd (e demais)
    images_generated: para Gemini, quantas imagens foram geradas (cobranca flat)
    """
    from django.conf import settings as dj_settings
    from django.utils import timezone as dj_tz

    rate = float(getattr(dj_settings, 'USD_TO_BRL_RATE', 5.80))
    cost_usd_dec = Decimal(str(usage_dict.get('cost_usd', 0) or 0))
    cost_brl_dec = cost_usd_dec * Decimal(str(rate))

    entry = {
        'timestamp': dj_tz.now().isoformat(),
        'step': step,
        'model': model,
        'input_tokens': int(usage_dict.get('input_tokens', 0) or 0),
        'output_tokens': int(usage_dict.get('output_tokens', 0) or 0),
        'cache_read_tokens': int(usage_dict.get('cache_read_input_tokens', 0) or 0),
        'cache_creation_tokens': int(usage_dict.get('cache_creation_input_tokens', 0) or 0),
        'total_tokens': int(usage_dict.get('total_tokens', 0) or 0),
        'images_generated': int(images_generated or 0),
        'cost_usd': float(cost_usd_dec),
        'cost_brl': float(cost_brl_dec.quantize(Decimal('0.0001'))),
        'usd_to_brl_rate': rate,
    }

    # Re-fetch para evitar race conditions (multiplas chamadas em paralelo)
    try:
        from apps.posts.models import Post
        post.refresh_from_db(fields=[
            'ai_usage_log', 'total_text_cost_usd', 'total_image_cost_usd',
            'total_cost_usd',
        ])
    except Exception:
        pass

    log = post.ai_usage_log if isinstance(post.ai_usage_log, list) else []
    log.append(entry)
    post.ai_usage_log = log

    if step == 'text_generation':
        post.total_text_cost_usd = (post.total_text_cost_usd or Decimal('0')) + cost_usd_dec
    elif step == 'image_generation':
        post.total_image_cost_usd = (post.total_image_cost_usd or Decimal('0')) + cost_usd_dec
    post.total_cost_usd = (post.total_cost_usd or Decimal('0')) + cost_usd_dec

    post.save(update_fields=[
        'ai_usage_log',
        'total_text_cost_usd',
        'total_image_cost_usd',
        'total_cost_usd',
    ])

    logger.info(
        '[ai_cost] post=%s step=%s model=%s tokens_in=%d tokens_out=%d images=%d cost=$%s (R$%s)',
        post.id, step, model,
        entry['input_tokens'], entry['output_tokens'], entry['images_generated'],
        entry['cost_usd'], entry['cost_brl'],
    )
