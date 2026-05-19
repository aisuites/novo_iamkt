"""
Endpoint da pipeline interna (Celery + Claude + Gemini).
Disparada pelo botao "Enviar Fluxo interno" do modal Gerar Post.

Em vez de chamar N8N, cria o Post com pipeline_used='local' e dispara
a task Celery generate_post_text_task. O usuario depois clica em "Gerar
Imagem" (pendente Etapa 3) para acionar generate_post_image_task.

Disponivel apenas quando settings.ENABLE_LOCAL_PIPELINE=True (homol/dev).
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.posts.models import Post, PostFormat, PostReferenceImage
from apps.posts.tasks import generate_post_text_task

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(['POST'])
def gerar_post_local(request):
    """
    Cria Post com pipeline_used='local' e dispara generate_post_text_task.

    Payload identico ao endpoint /posts/gerar/ original:
        - rede_social, post_format_id (ou formato legado), tema, cta_requested,
          is_carousel, image_count, reference_images
    """
    if not getattr(settings, 'ENABLE_LOCAL_PIPELINE', False):
        return JsonResponse(
            {'success': False, 'error': 'Pipeline interna desabilitada neste ambiente'},
            status=403,
        )

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
    post_format_id = data.get('post_format_id')
    formato_legado = (data.get('formato') or '').strip()

    # ---- Validacoes (mesmo padrao do gerar_post original) ----
    valid_redes = ['instagram', 'facebook', 'linkedin', 'whatsapp']
    if rede_social not in valid_redes:
        return JsonResponse(
            {'success': False, 'error': f'Rede social invalida. Opcoes: {", ".join(valid_redes)}'},
            status=400,
        )
    if not tema:
        return JsonResponse({'success': False, 'error': 'Tema obrigatorio'}, status=400)
    if is_carousel and not (2 <= image_count <= 5):
        return JsonResponse(
            {'success': False, 'error': 'Quantidade de imagens deve ser entre 2 e 5'},
            status=400,
        )

    # Resolve PostFormat (igual ao endpoint atual)
    post_format = None
    formato = formato_legado
    formats = []
    if post_format_id:
        try:
            post_format = PostFormat.objects.get(id=int(post_format_id), is_active=True)
            formato = post_format.name
            formats = [formato]
        except (PostFormat.DoesNotExist, ValueError):
            return JsonResponse(
                {'success': False, 'error': 'Formato selecionado nao encontrado'},
                status=400,
            )
    elif formato_legado in ('feed', 'stories', 'both'):
        formats = ['feed', 'stories'] if formato_legado == 'both' else [formato_legado]
    else:
        return JsonResponse(
            {'success': False, 'error': 'Formato obrigatorio (post_format_id ou formato)'},
            status=400,
        )

    content_type = (
        'carrossel' if is_carousel
        else ('story' if formato == 'stories' else 'post')
    )

    # ---- Cria Post + dispara task ----
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
                pipeline_used='local',
            )

            for idx, ref_img in enumerate(reference_images):
                PostReferenceImage.objects.create(
                    post=post,
                    s3_key=ref_img.get('s3_key', ''),
                    s3_url=ref_img.get('url', ''),
                    original_name=ref_img.get('name', ''),
                    order=idx,
                )

            logger.info(
                '[posts.local] Post %s criado pipeline=local refs=%d',
                post.id, len(reference_images),
            )

        # Dispara task fora da transacao para garantir que o Post foi commitado
        generate_post_text_task.delay(post.id)

        return JsonResponse({
            'success': True,
            'id': post.id,
            'post_id': post.id,
            'status': 'generating',
            'pipeline': 'local',
            'message': 'Post criado. Texto sendo gerado via Claude Sonnet 4.5...',
        })

    except Exception:
        logger.exception('[posts.local] Falha ao criar post local')
        return JsonResponse(
            {'success': False, 'error': 'Erro interno ao criar post'},
            status=500,
        )
