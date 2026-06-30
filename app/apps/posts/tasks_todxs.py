"""
Pipeline EXCLUSIVO da TODXS (org slug='todxs').

Fluxo da skill `todxs-social-posts`, 100% isolado do pipeline generico:
  Etapa 1 — skill_brain (1 chamada Claude): Content Lock + Visual Lock +
            single_shot_prompt + caption/hashtags.
  Etapa 2 — gemini_singleshot (1 chamada Gemini): arte FINAL com texto embutido.

Observabilidade: cada etapa grava o payload enviado (imagens como descritor, sem
base64) e o retorno cru do LLM em local_pipeline_context['todxs']['trace'].

Reusa helpers existentes (KB, S3, custo) sem alterar nada do fluxo atual.
"""
import base64
import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)


def _formato_meta(post):
    """Deriva (fmt, formato_label, ratio_label, formato_px).

    Conforme o sistema de wireframes da TODXS: feed = 4:5 (1080x1350),
    story = 9:16 (1080x1920). fmt e a chave usada pelo wireframe ('feed'/'story').
    """
    formats = [f.lower() for f in (post.formats or [])]
    is_story = (
        'stories' in formats or 'story' in formats
        or (post.social_network or '').lower() in ('stories', 'story')
    )
    if is_story:
        return 'story', 'Story 9:16', '9:16', '1080x1920'
    return 'feed', 'Feed 4:5', '4:5', '1080x1350'


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_post_todxs_task(self, post_id: int):
    """Gera um post da TODXS ponta a ponta (skill brain -> single-shot)."""
    from apps.posts.models import Post, PostImage
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.tasks import (
        _kb_colors, _build_kb_summary, _logos_from_org,
        _upload_image_to_s3, _record_ai_usage,
    )
    from apps.posts.services.gemini_image_generator import _download_to_base64
    from apps.posts.services.todxs.skill_brain import run_skill_brain
    from apps.posts.services.todxs.gemini_singleshot import generate_singleshot
    from apps.posts.services.todxs import assets as todxs_assets

    post = Post.objects.get(id=post_id)
    org = post.organization
    kb = KnowledgeBase.objects.filter(organization=org).first()

    # DATA-DRIVEN: carrega as specs dos arquetipos da org (banco sobre o codigo)
    # no contextvar que o renderizador (WF) le durante toda esta task.
    from apps.posts.services.todxs.catalog import apply_org_wireframes
    apply_org_wireframes(org)

    ctx = post.local_pipeline_context or {}
    todxs_ctx = ctx.get('todxs') or {}
    trace = todxs_ctx.get('trace') or []

    fmt, formato_label, ratio_label, formato_px = _formato_meta(post)

    # ---------------- Etapa 1: skill brain (Claude) ----------------
    try:
        brand = {
            'paleta': _kb_colors(kb),
            'palavras_recomendadas': getattr(kb, 'palavras_recomendadas', []) or [],
            'palavras_evitar': getattr(kb, 'palavras_evitar', []) or [],
            'kb_summary': _build_kb_summary(org),
            'tom_voz': getattr(kb, 'tom_voz_externo', '') or '',
            'references': todxs_assets.references_for_brain(kb),
        }
        brief = {
            'tema': post.requested_theme,
            'rede': post.social_network,
            'fmt': fmt,
            'force_archetype': todxs_ctx.get('force_archetype'),  # so p/ validacao
            'formato_label': formato_label,
            'ratio_label': ratio_label,
            'formato_px': formato_px,
            'cta_requested': bool(post.cta_requested),
            'last_color_hex': todxs_assets.last_todxs_color_hex(org),
        }
        brain = run_skill_brain(brief=brief, brand=brand)
    except Exception as exc:
        logger.exception('[todxs] etapa 1 (skill_brain) falhou post=%s', post_id)
        raise self.retry(exc=exc)

    structured = brain.get('structured') or {}
    trace.append({
        'etapa': '1_skill_brain',
        'model': brain.get('model'),
        'request': brain['debug']['request'],
        'response_raw': brain['debug']['response_raw'],
        'parsed': structured,
        'usage': brain.get('usage'),
        'at': dj_tz.now().isoformat(),
    })
    # Persiste o trace da etapa 1 ANTES de gerar imagem (inspecionavel mesmo se etapa 2 falhar)
    content = structured.get('content') or {}
    archetype = (structured.get('archetype') or '').strip().upper()  # ex.: 'B', 'B_DUO'
    color_hex = structured.get('color_hex') or '#000000'
    color_name = structured.get('color_name') or ''
    # Modo template: a cor inspiracao escolhida pelo usuario sobrepoe a da IA.
    _force_color = todxs_ctx.get('force_color')
    if _force_color:
        color_hex = _force_color
        color_name = todxs_ctx.get('force_color_name') or color_name
    todxs_ctx.update({
        'pilar': structured.get('pilar'),
        'archetype': archetype,
        'archetype_reason': structured.get('archetype_reason'),
        'color_name': color_name,
        'color_hex': color_hex,
        'content': content,
        'reference_id': structured.get('reference_id'),
        'reference_usage': structured.get('reference_usage'),
        'formato_label': formato_label,
        'ratio_label': ratio_label,
        'formato_px': formato_px,
        'trace': trace,
        'updated_at': dj_tz.now().isoformat(),
    })
    ctx['todxs'] = todxs_ctx
    post.local_pipeline_context = ctx
    post.ia_provider = 'anthropic'
    post.ia_model_text = brain.get('model')
    post.save(update_fields=['local_pipeline_context', 'ia_provider', 'ia_model_text'])
    _record_ai_usage(post, step='text_generation', model=brain.get('model'),
                     usage_dict=brain.get('usage') or {}, purpose='todxs_skill_brain')

    from apps.posts.services.todxs.wireframes import (
        WF, archetypes_for_format, background_mode,
        build_singleshot_prompt, build_background_prompt,
    )
    from apps.posts.services.todxs import pillow_render
    from django.db.models import Max

    if archetype not in WF() or archetype not in archetypes_for_format(fmt):
        archetype = archetypes_for_format(fmt)[0]  # fallback seguro
        todxs_ctx['archetype'] = archetype

    _titulo = content.get('titulo') or (content.get('blocos') or [''])[0] or ''
    paleta = _kb_colors(kb)
    mode = background_mode(archetype)

    # Simbolo oficial fixado (Grafismo X Preto 1) p/ o selo/simbolo.
    x_png_bytes = None
    simbolo_url = todxs_assets.todxs_simbolo_url(kb)
    if simbolo_url:
        gb64, _ = _download_to_base64(simbolo_url)
        if gb64:
            x_png_bytes = base64.b64decode(gb64)
    # Wordmark oficial fixado (TODXS Logotipo Preto 7); fallback p/ logo primario.
    logo_url = todxs_assets.todxs_wordmark_url(kb)
    if not logo_url:
        logos = list(_logos_from_org(org, post=post))
        logo_url = logos[0] if logos else None

    # ---------------- Etapa 2: FUNDO ----------------
    # solid -> Pillow desenha o campo de cor; photo/solid_photo/image -> Gemini gera
    # a foto/cena (sem texto), e o Pillow aplica faixa/texto por cima.
    photo_png = None
    bg_info = {'mode': mode}
    if mode in ('photo', 'solid_photo', 'image'):
        bg_prompt = build_background_prompt(
            archetype, content, color_hex, fmt, brand_summary=brand.get('kb_summary') or '')
        try:
            bg = generate_singleshot(prompt_text=bg_prompt, image_inputs=[])
            photo_png = bg['png_bytes']
            bg_info.update({'prompt': bg_prompt, 'model': bg.get('model'),
                            'usage': bg.get('usage'), 'response': bg['debug']['response']})
            _record_ai_usage(post, step='image_generation', model=bg.get('model'),
                             usage_dict=bg.get('usage') or {}, purpose='todxs_background',
                             images_generated=1)
        except Exception as exc:
            logger.exception('[todxs] fundo (Gemini) falhou post=%s', post_id)
            raise self.retry(exc=exc)

    # ---------------- Etapa 3: PILLOW (render publicado) ----------------
    try:
        pr = pillow_render.render_todxs(
            archetype=archetype, content=content, color_hex=color_hex, fmt=fmt,
            formato_px=formato_px, kb=kb, paleta=paleta,
            photo_png=photo_png, x_png_bytes=x_png_bytes, logo_url=logo_url,
        )
    except Exception as exc:
        logger.exception('[todxs] pillow render falhou post=%s', post_id)
        raise self.retry(exc=exc)

    raw_key, raw_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['raw_png'], mime_type='image/png')
    s3_key, s3_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['final_png'], mime_type='image/png')

    # ---------------- Persistencia ----------------
    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )

    # designer_payload -> a edicao avancada (canvas modal) consome estes elementos
    dp = post.designer_payload if isinstance(post.designer_payload, dict) else {}
    dp['_layout_elements'] = pr['elements']
    post.designer_payload = dp
    post.raw_image_s3_key = raw_key

    trace.append({'etapa': '2_background', **bg_info,
                  'raw_s3_key': raw_key, 'raw_url': raw_url, 'at': dj_tz.now().isoformat()})
    trace.append({'etapa': '3_pillow_render', 'elements': pr['elements'],
                  'fonts': pr['fonts_resolved'], 'final_s3_key': s3_key,
                  'final_url': s3_url, 'at': dj_tz.now().isoformat()})

    # imagens p/ inspecao no debug (sem Gemini-texto: o render e 100% Pillow)
    todxs_ctx['debug_images'] = {'fundo': raw_url, 'gemini_texto': None, 'pillow': s3_url}

    post.title = (_titulo or '').replace('\n', ' ') or post.title
    post.subtitle = content.get('apoio') or content.get('kicker') or ''
    post.caption = structured.get('caption') or ''
    post.hashtags = structured.get('hashtags') or []
    post.image_prompt = f"TODXS arquetipo {archetype} ({fmt}) — render Pillow deterministico"
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = 'todxs-pillow'
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing

    todxs_ctx['trace'] = trace
    ctx['todxs'] = todxs_ctx
    post.local_pipeline_context = ctx
    post.status = 'image_ready'
    post.save()

    logger.info('[todxs] post=%s OK arquetipo=%s cor=%s mode=%s render=pillow',
                post_id, archetype, color_hex, mode)
    return {'success': True, 'post_id': post_id, 'archetype': archetype}
