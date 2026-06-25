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
    """Deriva (formato_label, ratio_label, formato_px) para feed 1:1 ou story 9:16."""
    from apps.posts.tasks import _formato_px
    px = _formato_px(post)
    formats = [f.lower() for f in (post.formats or [])]
    is_story = (
        'stories' in formats or 'story' in formats
        or (post.social_network or '').lower() in ('stories', 'story')
    )
    try:
        w, h = (int(x) for x in px.lower().split('x'))
        if h > w:
            is_story = True
    except Exception:
        pass
    if is_story:
        if px == '1080x1080':
            px = '1080x1920'
        return 'Story 9:16', '9:16', px
    return 'Feed 1:1', '1:1', px


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

    ctx = post.local_pipeline_context or {}
    todxs_ctx = ctx.get('todxs') or {}
    trace = todxs_ctx.get('trace') or []

    formato_label, ratio_label, formato_px = _formato_meta(post)

    # ---------------- Etapa 1: skill brain (Claude) ----------------
    try:
        brand = {
            'paleta': _kb_colors(kb),
            'palavras_recomendadas': getattr(kb, 'palavras_recomendadas', []) or [],
            'palavras_evitar': getattr(kb, 'palavras_evitar', []) or [],
            'kb_summary': _build_kb_summary(org),
            'tom_voz': getattr(kb, 'tom_voz_externo', '') or '',
        }
        brief = {
            'tema': post.requested_theme,
            'rede': post.social_network,
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
    content = structured.get('content_lock') or {}
    visual = structured.get('visual_lock') or {}
    todxs_ctx.update({
        'pilar': structured.get('pilar'),
        'archetype': visual.get('archetype'),
        'archetype_reason': visual.get('archetype_reason'),
        'color_name': visual.get('color_name'),
        'color_hex': visual.get('color_hex'),
        'content_lock': content,
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

    single_shot_prompt = structured.get('single_shot_prompt')
    if not single_shot_prompt:
        logger.error('[todxs] skill_brain sem single_shot_prompt post=%s', post_id)
        raise self.retry(exc=RuntimeError('skill_brain output invalido (sem single_shot_prompt)'))

    # ---------------- Etapa 2: single-shot (Gemini) ----------------
    image_inputs = []

    # contagem de posts todxs ja gerados -> rotaciona o grafismo
    post_count = Post.objects.filter(organization=org, pipeline_used='todxs').count()
    graf = todxs_assets.pick_grafismo_x(kb, rotate_seed=post_count)
    if graf:
        b64, mime = _download_to_base64(graf['url'])
        if b64:
            image_inputs.append({'b64': b64, 'mime': mime, 'role': 'GRAFISMO_X', 'name': graf['name']})

    logos = list(_logos_from_org(org, post=post))
    if logos:
        b64, mime = _download_to_base64(logos[0])
        if b64:
            image_inputs.append({'b64': b64, 'mime': mime, 'role': 'LOGO', 'name': 'logo primario'})

    specimen = todxs_assets.render_ana_banana_specimen(kb, content.get('manchete') or '')
    if specimen:
        image_inputs.append({
            'b64': base64.b64encode(specimen).decode('ascii'),
            'mime': 'image/png', 'role': 'FONT_SPECIMEN_ANA_BANANA',
            'name': 'specimen Ana Banana Black',
        })

    try:
        gem = generate_singleshot(prompt_text=single_shot_prompt, image_inputs=image_inputs)
    except Exception as exc:
        logger.exception('[todxs] etapa 2 (gemini single-shot) falhou post=%s', post_id)
        trace.append({
            'etapa': '2_gemini_singleshot', 'erro': str(exc),
            'at': dj_tz.now().isoformat(),
        })
        todxs_ctx['trace'] = trace
        ctx['todxs'] = todxs_ctx
        post.local_pipeline_context = ctx
        post.save(update_fields=['local_pipeline_context'])
        raise self.retry(exc=exc)

    trace.append({
        'etapa': '2_gemini_singleshot',
        'model': gem.get('model'),
        'request': gem['debug']['request'],
        'response': gem['debug']['response'],
        'usage': gem.get('usage'),
        'at': dj_tz.now().isoformat(),
    })

    # ---------------- Persistencia da arte ----------------
    s3_key, s3_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id,
        png_bytes=gem['png_bytes'], mime_type=gem.get('mime_type', 'image/png'),
    )
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )

    post.title = content.get('manchete') or post.title
    post.subtitle = content.get('corpo') or content.get('eyebrow') or ''
    post.caption = structured.get('caption') or ''
    post.hashtags = structured.get('hashtags') or []
    post.image_prompt = single_shot_prompt
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = gem.get('model')
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing

    todxs_ctx['trace'] = trace
    ctx['todxs'] = todxs_ctx
    post.local_pipeline_context = ctx
    post.status = 'image_ready'
    post.save()

    _record_ai_usage(post, step='image_generation', model=gem.get('model'),
                     usage_dict=gem.get('usage') or {}, purpose='todxs_singleshot',
                     images_generated=1)

    logger.info('[todxs] post=%s OK arquetipo=%s cor=%s', post_id,
                visual.get('archetype'), visual.get('color_hex'))
    return {'success': True, 'post_id': post_id, 'archetype': visual.get('archetype')}
