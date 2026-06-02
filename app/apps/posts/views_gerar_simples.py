"""
Endpoint do PIPELINE SIMPLES (v2) — agente unico via OpenAI.
Disparado pelo seletor "Simples (OpenAI)" do modal Gerar Post.

Cria o Post com pipeline_used='simple' e dispara generate_post_simple_task.
Mesmo payload/validacoes do endpoint /posts/gerar-local/ (reaproveita o
mesmo modal), mudando apenas a pipeline e a task acionada.

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
from apps.posts.tasks import generate_post_simple_task

logger = logging.getLogger(__name__)

MAX_REF_IMAGES = 5
_VALID_REDES = ['instagram', 'facebook', 'linkedin', 'whatsapp']
_VALID_LOGO_POS = {
    'top-left', 'top-center', 'top-right',
    'middle-left', 'middle-center', 'middle-right',
    'bottom-left', 'bottom-center', 'bottom-right',
}
_NON_EXCLUSIVE = {'produto', 'pessoa_modelo'}


@login_required
@require_http_methods(['POST'])
def gerar_post_simples(request):
    """Cria Post com pipeline_used='simple' e dispara generate_post_simple_task."""
    if not getattr(settings, 'ENABLE_SIMPLE_PIPELINE', True):
        return JsonResponse(
            {'success': False, 'error': 'Pipeline simples desabilitada neste ambiente'},
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
    if isinstance(reference_images, list) and len(reference_images) > MAX_REF_IMAGES:
        reference_images = reference_images[:MAX_REF_IMAGES]

    post_format_id = data.get('post_format_id')
    formato_legado = (data.get('formato') or '').strip()

    # Selecoes da galeria (mesmo formato do pipeline local)
    selected_logo_ids = data.get('selected_logo_ids') or []
    if isinstance(selected_logo_ids, list) and len(selected_logo_ids) > 1:
        selected_logo_ids = selected_logo_ids[:1]
    selected_reference_ids = data.get('selected_reference_ids') or []
    references_usage_description = (data.get('references_usage_description') or '').strip()

    reference_aspects = data.get('reference_aspects') or {}
    if isinstance(reference_aspects, dict):
        _seen, _clean = {}, {}
        for _rid, _asps in reference_aspects.items():
            if isinstance(_asps, str):
                _asps = [_asps] if _asps.strip() else []
            elif not isinstance(_asps, list):
                _asps = []
            _kept = []
            for _a in _asps:
                _a = (_a or '').strip()
                if not _a:
                    continue
                if _a in _NON_EXCLUSIVE:
                    _kept.append(_a)
                    continue
                if _a in _seen:
                    continue
                _seen[_a] = str(_rid)
                _kept.append(_a)
            if _kept:
                _clean[str(_rid)] = _kept
        reference_aspects = _clean
    else:
        reference_aspects = {}

    logo_position = (data.get('logo_position') or '').strip()
    if logo_position and logo_position not in _VALID_LOGO_POS:
        logo_position = ''

    # ---- Validacoes ----
    if rede_social not in _VALID_REDES:
        return JsonResponse(
            {'success': False, 'error': f'Rede social invalida. Opcoes: {", ".join(_VALID_REDES)}'},
            status=400,
        )
    if not tema:
        return JsonResponse({'success': False, 'error': 'Tema obrigatorio'}, status=400)
    if is_carousel and not (2 <= image_count <= 5):
        return JsonResponse(
            {'success': False, 'error': 'Quantidade de imagens deve ser entre 2 e 5'},
            status=400,
        )

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
                {'success': False, 'error': 'Formato selecionado nao encontrado'}, status=400,
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
                ia_provider='openai',
                ia_model_text='gpt-4o-mini',
                pipeline_used='simple',
                copy_payload={},
                designer_payload={},
                local_pipeline_context={
                    'selected_logo_ids': list(selected_logo_ids or []),
                    'selected_reference_ids': list(selected_reference_ids or []),
                    'references_usage_description': references_usage_description,
                    'reference_aspects': reference_aspects,
                    'logo_position': logo_position,
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

            logger.info('[posts.simple] Post %s criado pipeline=simple refs=%d',
                        post.id, len(reference_images))

        generate_post_simple_task.delay(post.id)

        return JsonResponse({
            'success': True,
            'id': post.id,
            'post_id': post.id,
            'status': 'generating',
            'pipeline': 'simple',
            'message': 'Post criado. Texto sendo gerado via OpenAI gpt-4o-mini...',
        })

    except Exception:
        logger.exception('[posts.simple] Falha ao criar post simples')
        return JsonResponse({'success': False, 'error': 'Erro interno ao criar post'}, status=500)
