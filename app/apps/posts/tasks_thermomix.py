"""
Pipeline EXCLUSIVO da Thermomix (org slug='thermomix') — 1ª org V3-NATIVA.

  Etapa 1 — skill_brain (1 Claude): EXTRAI do tema os campos variáveis do
            template (título, data, horários, cidade/UF, telefone, nome);
            ausente = mantém o conteúdo-exemplo (DEFAULT_CONTENT).
  Etapa 2 — fotos POR TIPO do multi-upload do modal (usage_type):
            'fundo'  -> foto full-bleed (upload > ref da KB > Gemini pela
                        descrição > fundo sólido da spec)
            'pessoa' -> retrato da apresentadora (sem upload = zona ausente)
  Etapa 3 — render engine v3 direto da spec do banco (sem renderizador legado).

Espelha a estrutura da tasks_samsung (portão two-step incluído).
"""
import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)

def _gemini_style_food(spec) -> str:
    """Estilo do fundo Gemini; proporcao segue o canvas da spec (feed 4:5 /
    story 9:16)."""
    w, h = (spec or {}).get('canvas', [1080, 1350])
    aspect = '9:16 tall vertical (story)' if h > w * 1.5 else 'Vertical 4:5'
    return (
        ' Editorial food photography, appetizing, realistic, natural light, real '
        'everyday Brazilian home cooking, shallow depth of field, generous negative '
        f'space on the LEFT half of the frame for text overlay. {aspect} '
        'composition. Absolutely NO text, NO letters, NO logos, NO watermarks, NO '
        'brand names, NO faces.')


def _default_archetype():
    from apps.posts.services.thermomix.wireframes import WF
    return sorted(WF().keys())[0]


def _merge_content(defaults: dict, overrides: dict) -> dict:
    """DEFAULT_CONTENT + campos NAO-vazios extraidos pelo brain."""
    out = dict(defaults or {})
    for k, v in (overrides or {}).items():
        v = (str(v) if v is not None else '').strip()
        if v:
            out[k] = v
    return out


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_post_thermomix_task(self, post_id: int):
    from apps.posts.models import Post
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.tasks import _build_kb_summary, _record_ai_usage
    from apps.posts.services.thermomix.skill_brain import run_skill_brain
    from apps.posts.services.thermomix.wireframes import WF, DEFAULT_CONTENT
    from apps.posts.services.thermomix.catalog import apply_org_wireframes

    post = Post.objects.get(id=post_id)
    org = post.organization
    kb = KnowledgeBase.objects.filter(organization=org).first()
    apply_org_wireframes(org)

    ctx = post.local_pipeline_context or {}
    t_ctx = ctx.get('thermomix') or {}
    trace = t_ctx.get('trace') or []

    archetype = (t_ctx.get('force_archetype') or '').strip() or _default_archetype()
    if archetype not in WF():
        archetype = _default_archetype()
    defaults = dict(DEFAULT_CONTENT.get(archetype) or {})

    # ---------------- Etapa 1: skill brain (Claude extrator) ----------------
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
            'defaults': defaults,
        }
        brain = run_skill_brain(brief=brief, brand=brand)
    except Exception as exc:
        logger.exception('[thermomix] etapa 1 (skill_brain) falhou post=%s', post_id)
        raise self.retry(exc=exc)

    structured = brain.get('structured') or {}
    content = _merge_content(defaults, structured.get('content') or {})

    trace.append({
        'etapa': '1_skill_brain', 'model': brain.get('model'),
        'request': brain['debug']['request'], 'response_raw': brain['debug']['response_raw'],
        'parsed': structured, 'usage': brain.get('usage'), 'at': dj_tz.now().isoformat(),
    })
    _record_ai_usage(post, step='text_generation', model=brain.get('model'),
                     usage_dict=brain.get('usage') or {}, purpose='thermomix_skill_brain')

    t_ctx.update({
        'archetype': archetype,
        'content': content,
        'caption': structured.get('caption') or '',
        'hashtags': structured.get('hashtags') or [],
        'image_prompt': (structured.get('image_prompt') or '').strip(),
        'brain_model': brain.get('model'),
        'trace': trace,
        'updated_at': dj_tz.now().isoformat(),
    })
    ctx['thermomix'] = t_ctx
    post.local_pipeline_context = ctx
    post.ia_provider = 'anthropic'
    post.ia_model_text = brain.get('model')
    post.save(update_fields=['local_pipeline_context', 'ia_provider', 'ia_model_text'])

    # ---------------- PORTAO (duas etapas — flag por org, C1) ----------------
    if getattr(org, 'archetype_two_step', False):
        post.title = (content.get('titulo') or '').replace('\n', ' ') or post.title
        post.subtitle = ' · '.join(v for v in (content.get('data'),
                                               content.get('horarios')) if v)
        post.caption = structured.get('caption') or ''
        post.hashtags = structured.get('hashtags') or []
        # descricao de imagem so quando o FUNDO sera gerado por IA
        post.image_prompt = ('' if _has_user_fundo(post)
                             else (structured.get('image_prompt') or '').strip())
        t_ctx['gate_map'] = {'title': 'titulo', 'subtitle': None}
        t_ctx['gate'] = {'stage': 'awaiting_approval', 'at': dj_tz.now().isoformat()}
        ctx['thermomix'] = t_ctx
        post.local_pipeline_context = ctx
        post.status = 'pending'
        post.save()
        logger.info('[thermomix] post=%s PORTAO: textos prontos (arquetipo=%s)',
                    post_id, archetype)
        return {'success': True, 'post_id': post_id, 'gate': True,
                'archetype': archetype}

    return _thermomix_render_stage(self, post_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def render_post_thermomix_task(self, post_id: int):
    """Etapa B do portao (C1): renderiza apos aprovacao, com as edicoes."""
    return _thermomix_render_stage(self, post_id, from_gate=True)


def _uploads_by_type(post):
    """(fundo, pessoa) dos uploads do modal, roteados pelo usage_type.
    Tolerancia: upload sem tipo conta como FUNDO (comportamento legado)."""
    fundo = pessoa = None
    try:
        for up in post.reference_image_files.order_by('order'):
            ut = (up.usage_type or '').strip()
            if ut == 'pessoa' and pessoa is None:
                pessoa = up
            elif ut != 'pessoa' and fundo is None:
                fundo = up
    except Exception:
        pass
    return fundo, pessoa


def _has_user_fundo(post) -> bool:
    """True se o usuario ESCOLHEU a foto de fundo (upload tipo fundo ou ref da
    KB selecionada). Upload SO de pessoa nao suprime a geracao do fundo."""
    fundo, _pessoa = _uploads_by_type(post)
    if fundo:
        return True
    ctx = post.local_pipeline_context or {}
    return bool(ctx.get('selected_reference_ids'))


def _thermomix_render_stage(task, post_id: int, from_gate: bool = False):
    """Etapas 2+3 (fotos + render v3 + persistencia) — comum as duas rotas."""
    from apps.posts.models import Post
    from apps.knowledge.models import KnowledgeBase, ReferenceImage
    from apps.core.services.s3_service import S3Service
    from apps.posts.tasks import _record_ai_usage
    from apps.posts.services.thermomix.wireframes import WF
    from apps.posts.services.thermomix.catalog import apply_org_wireframes
    from apps.posts.services.thermomix.assets import (
        resolve_asset_urls, font_paths, font_loader)
    from apps.posts.services.artkit import spec3
    from apps.posts.services.artkit.engine import render_v3

    post = Post.objects.get(id=post_id)
    org = post.organization
    kb = KnowledgeBase.objects.filter(organization=org).first()
    apply_org_wireframes(org)

    ctx = post.local_pipeline_context or {}
    t_ctx = ctx.get('thermomix') or {}
    trace = t_ctx.get('trace') or []

    archetype = (t_ctx.get('archetype') or '').strip() or _default_archetype()
    if archetype not in WF():
        archetype = _default_archetype()
    content = dict(t_ctx.get('content') or {})
    structured = {'caption': t_ctx.get('caption') or '',
                  'hashtags': t_ctx.get('hashtags') or []}
    brain_model = t_ctx.get('brain_model') or post.ia_model_text
    img_prompt = (t_ctx.get('image_prompt') or '').strip()

    if from_gate:
        gm = t_ctx.get('gate_map') or {}
        if gm.get('title') and (post.title or '').strip():
            content[gm['title']] = post.title.strip()
        structured['caption'] = post.caption or structured['caption']
        structured['hashtags'] = post.hashtags or structured['hashtags']
        if (post.image_prompt or '').strip():
            img_prompt = post.image_prompt.strip()
        t_ctx['content'] = content
        t_ctx['gate'] = {'stage': 'approved', 'at': dj_tz.now().isoformat()}

    # ---------------- Etapa 2: fotos por TIPO ----------------
    def _presigned_up(up):
        if up and up.s3_key:
            try:
                return S3Service.generate_presigned_download_url(up.s3_key, expires_in=3600)
            except Exception:
                pass
        return (up.s3_url or None) if up else None

    assets = resolve_asset_urls(kb)
    photo_origin = None
    ref = None

    fundo_up, pessoa_up = _uploads_by_type(post)
    if pessoa_up:
        assets['retrato'] = _presigned_up(pessoa_up)

    url = _presigned_up(fundo_up)
    if url:
        assets['background_image'] = url
        photo_origin = 'user_upload'
    else:
        ids = ctx.get('selected_reference_ids') or []
        ref = (ReferenceImage.objects.filter(knowledge_base=kb, id__in=ids).first()
               if (ids and kb) else None)
        if ref and ref.s3_key:
            try:
                assets['background_image'] = S3Service.generate_presigned_download_url(
                    ref.s3_key, expires_in=3600)
            except Exception:
                assets['background_image'] = ref.s3_url or None
            photo_origin = 'kb_reference_selected'
    if 'background_image' not in assets and img_prompt:
        try:
            from apps.posts.services.artkit.gemini import generate_singleshot
            g = generate_singleshot(
                prompt_text=img_prompt + _gemini_style_food(WF().get(archetype)),
                image_inputs=[])
            _record_ai_usage(post, step='image_generation', model=g.get('model'),
                             usage_dict=g.get('usage') or {},
                             purpose='thermomix_background', images_generated=1)
            assets['background_image'] = g['png_bytes']
            photo_origin = 'gemini'
        except Exception:
            logger.exception('[thermomix] gemini fundo falhou post=%s', post_id)
    # sem nada: engine cai no fundo solido da spec (photo_origin None)

    # ---------------- Etapa 3: render engine v3 (spec do banco) ----------------
    try:
        spec = WF()[archetype]
        paths = font_paths(kb, spec.get('fonts') or {})
        norm = spec3.normalize(spec)
        pr = render_v3(norm, content=content,
                       ctx={'font': font_loader(paths), 'font_paths': paths,
                            'assets': assets, 'tokens': {}})
    except Exception as exc:
        logger.exception('[thermomix] render v3 falhou post=%s', post_id)
        raise task.retry(exc=exc)

    # ---------------- Persistência (nucleo comum: artkit.persist) ----------------
    from apps.posts.services.artkit.persist import persist_rendered_art
    up = persist_rendered_art(
        post,
        raw_png=pr['raw_png'], final_png=pr['final_png'], elements=pr['elements'],
        title=(content.get('titulo') or '').replace('\n', ' ') or post.title,
        subtitle=' · '.join(v for v in (content.get('data'),
                                        content.get('horarios')) if v),
        caption=structured.get('caption') or '',
        hashtags=structured.get('hashtags') or [],
        image_prompt=f'Thermomix arquetipo {archetype} — render engine v3',
        ia_provider='anthropic', ia_model_text=brain_model,
        ia_model_image='thermomix-pillow',
    )
    raw_url, s3_key, s3_url = up['raw_url'], up['s3_key'], up['s3_url']

    trace.append({'etapa': '3_render', 'archetype': archetype, 'engine': 'v3',
                  'elements': pr['elements'], 'fonts': pr['fonts_resolved'],
                  'photo_origin': photo_origin,
                  'photo_ref_id': ref.id if ref else None,
                  'final_s3_key': s3_key, 'at': dj_tz.now().isoformat()})
    t_ctx.update({
        'archetype': archetype, 'content': content, 'trace': trace,
        'debug_images': {'fundo': raw_url, 'pillow': s3_url},
        'updated_at': dj_tz.now().isoformat(),
    })
    ctx['thermomix'] = t_ctx
    post.local_pipeline_context = ctx
    post.status = 'image_ready'
    post.save()

    logger.info('[thermomix] post=%s OK arquetipo=%s engine=v3', post_id, archetype)
    return {'success': True, 'post_id': post_id, 'archetype': archetype}
