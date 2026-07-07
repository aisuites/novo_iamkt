"""
Pipeline EXCLUSIVO da VB Gastronomia (org slug='vb-gastronomia').

Fluxo: skill_brain (Claude: texto das zonas + receita da ilustração relacionada
ao tema) -> render_vb (Pillow determinístico: bg + texto + ilustração + logo).
100% isolado da TODXS e do pipeline genérico.
"""
import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)


def _fmt_meta(post):
    formats = [f.lower() for f in (post.formats or [])]
    is_story = ('stories' in formats or 'story' in formats
                or (post.social_network or '').lower() in ('stories', 'story'))
    return ('story', '1080x1920') if is_story else ('feed', '1080x1350')


def _region_name(cx, cy, W=1080, H=1350):
    """Nome humano da regiao (terços) a partir do centro (px)."""
    col = 'left' if cx < W / 3 else ('right' if cx > 2 * W / 3 else 'center')
    row = 'top' if cy < H / 3 else ('bottom' if cy > 2 * H / 3 else 'middle')
    return f'{row}-{col}'


def _reserved_regions(spec) -> list:
    """Regioes (top-left, middle-right...) ocupadas por grafismos/logo no arquetipo,
    que precisam ficar LIMPAS na foto."""
    regs = []
    gc = spec.get('grafismo_cluster')
    if gc:
        b = gc['box']
        regs.append(_region_name(b['x'] + b['w'] / 2, b['y'] + b['h'] / 2))
    lg = spec.get('logo')
    if lg:
        regs.append(_region_name(lg['x'] + lg.get('w', 150) / 2, lg['y'] + lg.get('h', 100) / 2))
    # dedup preservando ordem
    seen, out = set(), []
    for r in regs:
        if r not in seen:
            seen.add(r); out.append(r)
    return out


def build_vb_photo_prompt(conceito: str, spec=None) -> str:
    """Prompt de FOTO de comida no estilo VB seguindo a REGRA DE COMPOSIÇÃO da marca:
    cena única e contínua, assunto deslocado à esquerda, margem direita ~30% e
    esquerda ~15% limpas (mesma superfície), high-key, sem linhas/objetos nas margens.
    SEM texto/logo (entram no Pillow)."""
    return (
        'Editorial food photograph for a corporate catering brand. '
        f'SUBJECT: {conceito}. '
        'BACKGROUND: the WHOLE frame is ONE uniform, smooth, seamless LIGHT surface '
        '(a single pale off-white / light infinity-sweep backdrop) filling the entire '
        'frame edge to edge — there is NO wall meeting a table, NO horizon line, NO '
        'surface edges, NO seams, and NO vertical or horizontal lines anywhere. '
        'HIGH-KEY lighting: bright, soft, diffuse, even — no vignette, no dark corners, '
        'no strong shadows. '
        'PLACEMENT: position the dish LEFT of center. Leave the RIGHT THIRD of the '
        'frame as smooth EMPTY uniform light background (clean negative space), and a '
        'smaller empty light area on the far left. These empty areas are the EXACT '
        'SAME uniform surface — identical tone, perfectly smooth, with NOTHING on them '
        '(no objects, loose utensils, glasses, crumbs, ingredients, patterns or '
        'texture). The image must read as ONE continuous photo, never divided. '
        'FORBIDDEN: panels / columns / split-screen / two-tone background; any border, '
        'frame, divider or vertical line; dark background, dark gradient or shadow at '
        'the edges. '
        'Fresh and appetizing, vibrant natural colors of the ingredients, shallow '
        'depth of field. STRICT: photograph only — NO text, NO letters, NO logos, NO '
        'graphic overlays. Vertical 4:5 framing.'
    )


def build_vb_framed_photo_prompt(conceito: str) -> str:
    """Prompt de foto VERTICAL que PREENCHE uma moldura (arquetipo 03). Cena de
    comida/cozinha, luz natural, apetitosa. Preenche o quadro (sem margens). SEM
    texto/logo (entram no Pillow)."""
    return (
        'Editorial vertical food/cooking photograph for a corporate catering brand. '
        f'SUBJECT: {conceito}. '
        'STYLE: bright, natural daylight, fresh and appetizing, vibrant natural colors '
        'of the ingredients, shallow depth of field, authentic kitchen/cooking moment '
        '(e.g. hands preparing or seasoning the food), light neutral surroundings. '
        'COMPOSITION: the food/action FILLS the vertical frame as the protagonist, '
        'well framed, tall 3:4-ish vertical crop. '
        'STRICT: photograph only — NO text, NO letters, NO logos, NO graphic overlays. '
        'Vertical framing.'
    )


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_post_vb_task(self, post_id: int):
    from apps.posts.models import Post, PostImage
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.tasks import _upload_image_to_s3, _record_ai_usage
    from apps.posts.services.vb.skill_brain import run_vb_brain
    from apps.posts.services.vb.render import render_vb
    from apps.posts.services.vb.specs import SP
    from apps.posts.services.vb.catalog import apply_org_specs
    from django.db.models import Max

    post = Post.objects.get(id=post_id)
    org = post.organization
    kb = KnowledgeBase.objects.filter(organization=org).first()

    # Data-driven: specs do banco (PostArchetype) sobrepoem o codigo (como todxs).
    apply_org_specs(org)

    ctx = post.local_pipeline_context or {}
    vb_ctx = ctx.get('vb') or {}
    fmt, _px = _fmt_meta(post)

    archetype = (vb_ctx.get('force_archetype') or '').strip()
    if archetype not in SP():
        # fallback: primeiro arquetipo do formato
        from apps.posts.services.vb.specs import archetypes_for_format
        opts = archetypes_for_format(fmt) or list(SP().keys())
        archetype = opts[0]

    brand = {
        'tom_voz': getattr(kb, 'tom_voz_externo', '') or '',
        'palavras_recomendadas': getattr(kb, 'palavras_recomendadas', []) or [],
        'palavras_evitar': getattr(kb, 'palavras_evitar', []) or [],
    }

    # ---- Etapa 1: skill brain (Claude) ----
    try:
        brain = run_vb_brain(tema=post.requested_theme, archetype=archetype, brand=brand)
    except Exception as exc:
        logger.exception('[vb] skill_brain falhou post=%s', post_id)
        raise self.retry(exc=exc)

    structured = brain.get('structured') or {}
    content = dict(structured.get('content') or {})
    content['ilustracao'] = structured.get('ilustracao')

    _record_ai_usage(post, step='text_generation', model=brain.get('model'),
                     usage_dict=brain.get('usage') or {}, purpose='vb_skill_brain')

    # ---- Etapa 1b: FOTO (Gemini) para arquetipos com fundo de foto ----
    # Upload de imagem (futuro) entra aqui como drop-in: se houver imagem enviada,
    # usa ela em vez do Gemini (e aplica efeito/ajuste).
    photo_png = None
    _sp = SP().get(archetype) or {}
    _needs_photo = (_sp.get('bg', {}).get('type') == 'photo') or bool(_sp.get('foto_frame'))
    if _needs_photo:
        from apps.posts.services.artkit.gemini import generate_singleshot
        conceito = structured.get('foto') or f'prato de comida fresca sobre {post.requested_theme}'
        prompt = (build_vb_framed_photo_prompt(conceito) if _sp.get('foto_frame')
                  else build_vb_photo_prompt(conceito, _sp))
        try:
            bg = generate_singleshot(prompt_text=prompt, image_inputs=[])
            photo_png = bg['png_bytes']
            _record_ai_usage(post, step='image_generation', model=bg.get('model'),
                             usage_dict=bg.get('usage') or {}, purpose='vb_photo',
                             images_generated=1)
            vb_ctx['foto_conceito'] = conceito
        except Exception as exc:
            logger.exception('[vb] foto (Gemini) falhou post=%s', post_id)
            raise self.retry(exc=exc)

    # ---- Etapa 2: render (Pillow) ----
    try:
        pr = render_vb(archetype, content, color_hex=vb_ctx.get('force_color'),
                       fmt=fmt, kb=kb, photo_png=photo_png)
    except Exception as exc:
        logger.exception('[vb] render falhou post=%s', post_id)
        raise self.retry(exc=exc)

    raw_key, raw_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['raw_png'], mime_type='image/png')
    s3_key, s3_url = _upload_image_to_s3(
        org_id=org.id, post_id=post.id, png_bytes=pr['final_png'], mime_type='image/png')

    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(post=post, s3_key=s3_key, s3_url=s3_url,
                             order=(max_order if max_order is not None else -1) + 1)

    post.raw_image_s3_key = raw_key
    post.raw_image_s3_url = raw_url
    # designer_payload -> a edicao avancada consome estes elementos de texto
    dp = post.designer_payload if isinstance(post.designer_payload, dict) else {}
    dp['_layout_elements'] = pr.get('elements') or []
    post.designer_payload = dp
    vb_ctx.update({'archetype': archetype, 'content': content,
                   'objeto_ilustracao': structured.get('objeto_ilustracao'),
                   'debug_images': {'fundo': raw_url, 'final': s3_url},
                   'updated_at': dj_tz.now().isoformat()})
    ctx['vb'] = vb_ctx
    post.local_pipeline_context = ctx
    post.title = (content.get('titulo') or '').replace('\n', ' ') or post.title
    post.subtitle = content.get('apoio') or ''
    post.caption = structured.get('caption') or ''
    post.hashtags = structured.get('hashtags') or []
    post.image_prompt = f'VB arquetipo {archetype} ({fmt}) — render Pillow deterministico'
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_provider = 'anthropic'
    post.ia_model_text = brain.get('model')
    post.ia_model_image = 'vb-pillow'
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing
    post.status = 'image_ready'
    post.save()

    logger.info('[vb] post=%s OK arquetipo=%s objeto=%s', post_id, archetype,
                structured.get('objeto_ilustracao'))
    return {'success': True, 'post_id': post_id, 'archetype': archetype}
