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
        or _os.environ.get('POST_TEXT_RENDER_MODE', 'inline')
    ).lower()

    # Coleta logos + uploads como image_parts (refs KB NAO sao mais
    # incluidas — viram direcionamento textual pelo translator abaixo)
    references = _collect_references(kb=kb, post=post, text_render_mode=text_render_mode)

    # ============================================================
    # KB REFERENCE TRANSLATOR — extrai directives das refs da KB
    # ============================================================
    # Refs selecionadas pelo user na galeria + usage_description -> Claude
    # multimodal analisa e produz texto estruturado por categoria. Vai
    # como bloco no prompt do Gemini, NAO como imagem.
    # Cache em local_pipeline_context.kb_refs_translations (hash dos inputs).
    kb_translations = []
    kb_refs_for_translation = _collect_kb_refs_for_translation(kb=kb, post=post)
    if kb_refs_for_translation:
        try:
            from apps.posts.services.kb_reference_translator import (
                translate_kb_references, _hash_inputs as _kb_hash_inputs,
            )
            input_hash = _kb_hash_inputs(kb_refs_for_translation)
            cached = ctx.get('kb_refs_translations') or {}
            if cached.get('input_hash') == input_hash and cached.get('translations'):
                kb_translations = cached.get('translations') or []
                logger.info('[kb_translator] cache HIT (%d translations)', len(kb_translations))
            else:
                tr_result = translate_kb_references(kb_refs_for_translation)
                if tr_result and tr_result.get('translations'):
                    kb_translations = tr_result['translations']
                    ctx['kb_refs_translations'] = {
                        'analyzed_at': dj_tz_now_iso(),
                        'input_hash': tr_result.get('input_hash'),
                        'translations': kb_translations,
                    }
                    post.local_pipeline_context = ctx
                    post.save(update_fields=['local_pipeline_context'])
                    _record_ai_usage(
                        post, step='kb_reference_translation',
                        model=tr_result.get('model', 'claude-sonnet-4-5'),
                        usage_dict=tr_result.get('usage') or {},
                    )
        except Exception:
            logger.exception('[kb_translator] falhou — segue sem directives')

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
    if not orchestrator_disabled and references:
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
                logger.info(
                    '[posts.local] orchestrator -> mode=%s, layout_plan=%s, spatial_len=%d',
                    text_render_mode,
                    bool(orchestration_output.get('layout_plan')),
                    len(spatial_instructions),
                )
        except Exception:
            logger.exception('[orchestrator] falhou — segue com prompt cru')
    # ============================================================

    # Smart Pillow overlay — prepara layout_spec, fonts e logo se mode='pillow'
    # Quando o orchestrator gerou layout_plan, usa-o (preferencia ao fallback)
    pillow_kwargs = {}
    if text_render_mode == 'pillow':
        pillow_kwargs = _prepare_pillow_overlay(post, kb, formato_px)
        # Sobrescreve layout_spec com layout_plan do orchestrator (se houver)
        layout_plan = (orchestration_output or {}).get('layout_plan') or {}
        if layout_plan:
            pillow_kwargs['pillow_layout_spec'] = _layout_plan_to_spec(
                layout_plan, fallback=pillow_kwargs.get('pillow_layout_spec', {}),
            )

    try:
        result = generate_post_image(
            post=post,
            references=references,
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
            resolve_font_for_kb(kb, usage_filter='corpo', weight='regular')
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
    Extrai termos da marca/produto que devem ser sanitizados no texto enviado
    ao Gemini (modo 'sanitized'). Pega nome da empresa + palavras-chave do
    descricao_produto (heuristica: palavras com inicial maiuscula ou
    contendo digito — indicam modelos).
    Funciona para qualquer empresa (le da KB dinamicamente).
    """
    import re as _re
    if not kb:
        return []
    keywords = set()
    # Nome da empresa (ex: "Thermomix")
    if kb.nome_empresa:
        for w in str(kb.nome_empresa).split():
            w = w.strip()
            if len(w) >= 2 and (w[0].isupper() or any(c.isdigit() for c in w)):
                keywords.add(w)
    # Descricao do produto — palavras com maiuscula seguida de letra/digito
    # (ex: "TM7", "iPhone", "Vorwerk") OU sequencias tipo "Modelo XYZ"
    desc = (kb.descricao_produto or '')[:500]
    for match in _re.findall(r'\b[A-Z][A-Za-z0-9]{1,}\b', desc):
        # Exclui palavras genericas curtas demais ou comuns
        if match.lower() not in {'a', 'o', 'de', 'da', 'do', 'um', 'uma', 'que', 'para', 'com', 'em'}:
            keywords.add(match)
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

    return out


def _collect_kb_refs_for_translation(kb, post) -> list:
    """
    Coleta refs da KB selecionadas pelo user no modal. Retorna lista
    de dicts {id, url, usage_description} para passar ao
    kb_reference_translator.

    Fallback: se a ref KB individual nao tem usage_description, usa o
    references_usage_description geral (textarea do modal) como guia
    para o translator. Garante que SEMPRE haja um foco indicado.

    NAO inclui logos (logo nunca passa pelo translator — vai literal).
    """
    from apps.core.services.s3_service import S3Service

    ctx = post.local_pipeline_context or {}
    selected_ref_ids = set(ctx.get('selected_reference_ids') or [])
    if not (kb and selected_ref_ids):
        return []

    general_guidance = (ctx.get('references_usage_description') or '').strip()

    out = []
    try:
        qs_refs = kb.reference_images.filter(id__in=selected_ref_ids)
        for img in qs_refs:
            if not img.s3_key:
                continue
            try:
                url = S3Service.generate_presigned_download_url(
                    img.s3_key, expires_in=86400
                )
                individual_desc = (
                    getattr(img, 'usage_description', '') or ''
                ).strip()
                effective_desc = individual_desc or general_guidance
                out.append({
                    'id': img.id,
                    'url': url,
                    'usage_description': effective_desc,
                })
            except Exception:
                pass
    except Exception:
        pass

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
