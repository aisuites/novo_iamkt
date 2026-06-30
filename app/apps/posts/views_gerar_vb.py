"""
Entrada do fluxo EXCLUSIVO da VB Gastronomia (delegação a partir de
gerar_post_simples quando a org é slug='vb-gastronomia'). Cria Post(pipeline_used=
'vb') e dispara generate_post_vb_task. Sem URL própria (auth/csrf já correram).
"""
import json
import logging

from django.db import transaction
from django.http import JsonResponse

from apps.posts.models import Post, PostFormat

logger = logging.getLogger(__name__)
_VALID_REDES = {'instagram', 'facebook', 'linkedin', 'whatsapp'}


def gerar_post_vb(request):
    from apps.posts.tasks_vb import generate_post_vb_task

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)

    rede = (data.get('rede_social') or '').lower().strip()
    tema = (data.get('tema') or '').strip()
    post_format_id = data.get('post_format_id')
    formato_legado = (data.get('formato') or '').strip()

    force_archetype = (data.get('archetype') or '').strip()
    force_color = (data.get('color_hex') or '').strip()

    if rede not in _VALID_REDES:
        return JsonResponse({'success': False, 'error': 'Rede social invalida'}, status=400)
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
            return JsonResponse({'success': False, 'error': 'Formato nao encontrado'}, status=400)
    elif formato_legado in ('feed', 'stories', 'both'):
        formats = ['feed', 'stories'] if formato_legado == 'both' else [formato_legado]
    else:
        return JsonResponse({'success': False, 'error': 'Formato obrigatorio'}, status=400)

    content_type = 'story' if formato == 'stories' else 'post'

    can_create, _code, qmsg = request.user.organization.can_create_post()
    if not can_create:
        return JsonResponse({'success': False, 'error': qmsg}, status=403)

    try:
        with transaction.atomic():
            post = Post.objects.create(
                organization=request.user.organization, user=request.user,
                requested_theme=tema, social_network=rede, content_type=content_type,
                formats=formats, post_format=post_format, status='generating',
                caption='', hashtags=[], ia_provider='anthropic',
                ia_model_text='claude-sonnet-4-6', pipeline_used='vb',
                copy_payload={}, designer_payload={},
                local_pipeline_context={'vb': {
                    'force_archetype': force_archetype or None,
                    'force_color': force_color or None,
                }},
            )
            logger.info('[posts.vb] Post %s criado pipeline=vb arquetipo=%s', post.id, force_archetype)

        generate_post_vb_task.delay(post.id)
        return JsonResponse({'success': True, 'id': post.id, 'post_id': post.id,
                             'status': 'generating', 'pipeline': 'vb',
                             'message': 'Post VB criado. Gerando arte...'})
    except Exception:
        logger.exception('[posts.vb] Falha ao criar post vb')
        return JsonResponse({'success': False, 'error': 'Erro interno ao criar post'}, status=500)
