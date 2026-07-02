"""
Entrada do fluxo EXCLUSIVO da Samsung Healthcare (org slug='samsung-healthcare').

Chamada por delegação a partir de gerar_post_simples. Espelha a criação do Post
do pipeline simples, mas com pipeline_used='samsung' e dispara
generate_post_samsung_task. Sem URL própria (auth/csrf já correram na delegante).
"""
import json
import logging

from django.db import transaction
from django.http import JsonResponse

from apps.posts.models import Post, PostFormat, PostReferenceImage

logger = logging.getLogger(__name__)

_VALID_REDES = {'instagram', 'facebook', 'linkedin', 'whatsapp'}
_MAX_REF_IMAGES = 5


def gerar_post_samsung(request):
    """Cria Post(pipeline_used='samsung') e dispara o pipeline Samsung."""
    from apps.posts.tasks_samsung import generate_post_samsung_task

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)

    rede_social = (data.get('rede_social') or '').lower().strip()
    tema = (data.get('tema') or '').strip()
    cta_requested = bool(data.get('cta_requested', False))
    is_carousel = bool(data.get('is_carousel', False))
    image_count = int(data.get('image_count') or 1)
    reference_images = data.get('reference_images') or []
    if isinstance(reference_images, list) and len(reference_images) > _MAX_REF_IMAGES:
        reference_images = reference_images[:_MAX_REF_IMAGES]

    post_format_id = data.get('post_format_id')
    formato_legado = (data.get('formato') or '').strip()
    selected_logo_ids = data.get('selected_logo_ids') or []
    selected_reference_ids = data.get('selected_reference_ids') or []
    references_usage_description = (data.get('references_usage_description') or '').strip()
    logo_position = (data.get('logo_position') or '').strip()

    # Modo "Usar template": usuário escolhe arquétipo + cor inspiração.
    force_archetype = (data.get('archetype') or '').strip().upper()
    force_color = (data.get('color_hex') or '').strip()
    force_color_name = (data.get('color_name') or '').strip()

    if rede_social not in _VALID_REDES:
        return JsonResponse(
            {'success': False, 'error': f'Rede social invalida. Opcoes: {", ".join(_VALID_REDES)}'},
            status=400,
        )
    if not tema:
        return JsonResponse({'success': False, 'error': 'Tema obrigatorio'}, status=400)

    post_format = None
    formato = formato_legado
    formats = []
    if post_format_id:
        try:
            post_format = PostFormat.objects.get(id=int(post_format_id), is_active=True)
            formato = post_format.name
            formats = [formato]
        except (PostFormat.DoesNotExist, ValueError):
            return JsonResponse({'success': False, 'error': 'Formato selecionado nao encontrado'}, status=400)
    elif formato_legado in ('feed', 'stories', 'both'):
        formats = ['feed', 'stories'] if formato_legado == 'both' else [formato_legado]
    else:
        return JsonResponse(
            {'success': False, 'error': 'Formato obrigatorio (post_format_id ou formato)'}, status=400)

    content_type = 'carrossel' if is_carousel else ('story' if formato == 'stories' else 'post')

    can_create, _qcode, qmsg = request.user.organization.can_create_post()
    if not can_create:
        return JsonResponse({'success': False, 'error': qmsg}, status=403)

    try:
        with transaction.atomic():
            post = Post.objects.create(
                organization=request.user.organization,
                user=request.user,
                requested_theme=tema,
                social_network=rede_social,
                content_type=content_type,
                formats=formats,
                post_format=post_format,
                cta_requested=cta_requested,
                is_carousel=is_carousel,
                image_count=image_count if is_carousel else 1,
                reference_images=reference_images,
                status='generating',
                caption='',
                hashtags=[],
                ia_provider='anthropic',
                ia_model_text='claude-sonnet-4-5',
                pipeline_used='samsung',
                copy_payload={},
                designer_payload={},
                local_pipeline_context={
                    'selected_logo_ids': list(selected_logo_ids or []),
                    'selected_reference_ids': list(selected_reference_ids or []),
                    'references_usage_description': references_usage_description,
                    'logo_position': logo_position,
                    'samsung': {
                        'force_archetype': force_archetype or None,
                        'force_color': force_color or None,
                        'force_color_name': force_color_name or None,
                    },
                },
            )
            for idx, ref_img in enumerate(reference_images):
                PostReferenceImage.objects.create(
                    post=post,
                    s3_key=ref_img.get('s3_key', ''),
                    s3_url=ref_img.get('url', ''),
                    original_name=ref_img.get('name', ''),
                    usage_type=ref_img.get('usage_type', '') or '',
                    usage_description=ref_img.get('usage_description', '') or '',
                    order=idx,
                )
            logger.info('[posts.samsung] Post %s criado pipeline=samsung', post.id)

        generate_post_samsung_task.delay(post.id)

        return JsonResponse({
            'success': True,
            'id': post.id,
            'post_id': post.id,
            'status': 'generating',
            'pipeline': 'samsung',
            'message': 'Post Samsung criado. Gerando arte (Claude + render Pillow determinístico)...',
        })
    except Exception:
        logger.exception('[posts.samsung] Falha ao criar post samsung')
        return JsonResponse({'success': False, 'error': 'Erro interno ao criar post'}, status=500)
