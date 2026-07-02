"""
Pipeline EXCLUSIVO da Samsung Healthcare (org slug='samsung-healthcare').

  Etapa 1 — skill_brain (1 Claude): mapeia o tema nas zonas do arquétipo.
  Etapa 2 — foto: usa uma imagem de referência da KB (ou Gemini, futuro).
  Etapa 3 — render Pillow determinístico (arquétipos Relentless/Samsung Medison).

Isolado do fluxo genérico. Reusa helpers de KB/S3/custo sem alterar nada.
"""
import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)

_GEMINI_STYLE_PHOTO = (
    ' Photographic, realistic, editorial quality. Clean, bright clinical/hospital '
    'or training environment, generous negative space, discreet technology, calm '
    'and professional mood, cool neutral palette. Wide horizontal composition. '
    'Absolutely NO text, NO letters, NO logos, NO watermarks, NO brand names.')

_GEMINI_STYLE_PRODUCT = (
    ' Product render of a medical ultrasound system, large and centered, on a dark '
    'navy gradient background with dramatic studio lighting. Absolutely NO text, NO '
    'letters, NO logos, NO watermarks, NO brand names.')


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_post_samsung_task(self, post_id: int):
    from apps.posts.models import Post, PostImage
    from apps.knowledge.models import KnowledgeBase, Logo, ReferenceImage
    from apps.core.services.s3_service import S3Service
    from apps.posts.tasks import (
        _kb_colors, _build_kb_summary, _upload_image_to_s3, _record_ai_usage,
    )
    from apps.posts.services.samsung.skill_brain import run_skill_brain
    from apps.posts.services.samsung.render import render_samsung
    from apps.posts.services.samsung.wireframes import WF, archetypes_for_format
    from django.db.models import Max

    post = Post.objects.get(id=post_id)
    org = post.organization
    kb = KnowledgeBase.objects.filter(organization=org).first()

    ctx = post.local_pipeline_context or {}
    s_ctx = ctx.get('samsung') or {}
    trace = s_ctx.get('trace') or []
    fmt = 'feed'  # Samsung: formato único 4:5 por ora

    # Arquétipo escolhido no modal (force_archetype) ou default 'A'.
    archetype = (s_ctx.get('force_archetype') or 'A').strip().upper()
    if archetype not in WF() or archetype not in archetypes_for_format(fmt):
        archetype = archetypes_for_format(fmt)[0]

    # ---------------- Etapa 1: skill brain (Claude) ----------------
    try:
        brand = {
            'kb_summary': _build_kb_summary(org),
            'tom_voz': getattr(kb, 'tom_voz_externo', '') or '',
            'palavras_recomendadas': getattr(kb, 'palavras_recomendadas', []) or [],
            'palavras_evitar': getattr(kb, 'palavras_evitar', []) or [],
        }
        brief = {
            'tema': post.requested_theme,
            'rede': post.social_network,
            'archetype': archetype,
            'cta_requested': bool(post.cta_requested),
        }
        brain = run_skill_brain(brief=brief, brand=brand)
    except Exception as exc:
        logger.exception('[samsung] etapa 1 (skill_brain) falhou post=%s', post_id)
        raise self.retry(exc=exc)

    structured = brain.get('structured') or {}
    content = structured.get('content') or {}

    trace.append({
        'etapa': '1_skill_brain', 'model': brain.get('model'),
        'request': brain['debug']['request'], 'response_raw': brain['debug']['response_raw'],
        'parsed': structured, 'usage': brain.get('usage'), 'at': dj_tz.now().isoformat(),
    })
    _record_ai_usage(post, step='text_generation', model=brain.get('model'),
                     usage_dict=brain.get('usage') or {}, purpose='samsung_skill_brain')

    # ---------------- Etapa 2: imagem ----------------
    from apps.posts.services.samsung.render import _fetch as _samsung_fetch
    assets = {}
    photo_origin = None
    ref = None
    img_prompt = (structured.get('image_prompt') or '').strip()

    def _selected_ref():
        ids = ctx.get('selected_reference_ids') or []
        return ReferenceImage.objects.filter(knowledge_base=kb, id__in=ids).first() if ids else None

    def _ref_url(r):
        if r and r.s3_key:
            try:
                return S3Service.generate_presigned_download_url(r.s3_key, expires_in=3600)
            except Exception:
                return r.s3_url or None
        return None

    def _is_transparent(url):
        try:
            return _samsung_fetch(url).getchannel('A').getextrema()[0] < 245
        except Exception:
            return False

    def _gemini(prompt, style):
        from apps.posts.services.todxs.gemini_singleshot import generate_singleshot
        g = generate_singleshot(prompt_text=prompt + style, image_inputs=[])
        _record_ai_usage(post, step='image_generation', model=g.get('model'),
                         usage_dict=g.get('usage') or {}, purpose='samsung_background',
                         images_generated=1)
        return g['png_bytes']

    if archetype == 'B':
        ref = _selected_ref()
        url = _ref_url(ref)
        if url and _is_transparent(url):
            assets['product_hero'] = url            # (2) PNG transparente -> compõe no navy
            photo_origin = 'kb_product_transparent'
        elif url:
            assets['background_image'] = url         # (1) imagem opaca -> fundo inteiro
            photo_origin = 'kb_product_opaque'
        elif img_prompt:                             # (3) nada escolhido -> Gemini gera
            try:
                assets['background_image'] = _gemini(img_prompt, _GEMINI_STYLE_PRODUCT)
                photo_origin = 'gemini_product'
            except Exception:
                logger.exception('[samsung] gemini produto (B) falhou post=%s', post_id)
    else:
        # A: foto via Gemini seguindo o tema; fallback ref da KB.
        if img_prompt:
            try:
                assets['photo'] = _gemini(img_prompt, _GEMINI_STYLE_PHOTO)
                photo_origin = 'gemini'
            except Exception:
                logger.exception('[samsung] gemini foto (A) falhou post=%s', post_id)
        if 'photo' not in assets:
            ref = (_selected_ref() or ReferenceImage.objects.filter(knowledge_base=kb)
                   .order_by('-importance', 'id').first())
            url = _ref_url(ref)
            if url:
                assets['photo'] = url
                photo_origin = photo_origin or 'kb_reference'

    # lockup Relentless branco (FIXO) — id/nome conhecido na KB
    lockup_url = None
    lk = Logo.objects.filter(knowledge_base=kb, name='Relentless Innovation (Branco)').first()
    if lk and lk.s3_key:
        try:
            lockup_url = S3Service.generate_presigned_download_url(lk.s3_key, expires_in=3600)
        except Exception:
            lockup_url = lk.s3_url or None
    assets['brand_lockup'] = lockup_url

    # ---------------- Etapa 3: render Pillow ----------------
    try:
        pr = render_samsung(archetype=archetype, content=content, kb=kb, assets=assets)
    except Exception as exc:
        logger.exception('[samsung] render falhou post=%s', post_id)
        raise self.retry(exc=exc)

    raw_key, raw_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['raw_png'], mime_type='image/png')
    s3_key, s3_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['final_png'], mime_type='image/png')

    # ---------------- Persistência ----------------
    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )

    dp = post.designer_payload if isinstance(post.designer_payload, dict) else {}
    dp['_layout_elements'] = pr['elements']
    post.designer_payload = dp
    post.raw_image_s3_key = raw_key

    trace.append({'etapa': '3_render', 'archetype': archetype, 'elements': pr['elements'],
                  'fonts': pr['fonts_resolved'], 'photo_origin': photo_origin,
                  'photo_ref_id': ref.id if ref else None,
                  'final_s3_key': s3_key, 'at': dj_tz.now().isoformat()})
    s_ctx.update({
        'archetype': archetype, 'content': content, 'trace': trace,
        'debug_images': {'fundo': raw_url, 'pillow': s3_url},
        'updated_at': dj_tz.now().isoformat(),
    })
    ctx['samsung'] = s_ctx

    post.title = (content.get('title') or '').replace('\n', ' ') or post.title
    post.subtitle = content.get('body') or content.get('kicker') or ''
    post.caption = structured.get('caption') or ''
    post.hashtags = structured.get('hashtags') or []
    post.image_prompt = f'Samsung arquetipo {archetype} ({fmt}) — render Pillow deterministico'
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_provider = 'anthropic'
    post.ia_model_text = brain.get('model')
    post.ia_model_image = 'samsung-pillow'
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing
    post.local_pipeline_context = ctx
    post.status = 'image_ready'
    post.save()

    logger.info('[samsung] post=%s OK arquetipo=%s render=pillow', post_id, archetype)
    return {'success': True, 'post_id': post_id, 'archetype': archetype}
