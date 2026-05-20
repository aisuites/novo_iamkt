"""
API endpoints para posts
"""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import PostFormat

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_post_formats(request):
    """
    Retorna formatos disponíveis para uma rede social
    
    GET /posts/api/formatos/?rede_social=instagram
    
    Returns:
        {
            'success': True,
            'formatos': [
                {
                    'id': 1,
                    'name': 'Feed Retrato',
                    'width': 1080,
                    'height': 1350,
                    'aspect_ratio': '4:5',
                    'dimensions': '1080x1350'
                },
                ...
            ]
        }
    """
    rede_social = request.GET.get('rede_social', '').strip().lower()
    
    if not rede_social:
        return JsonResponse({
            'success': False,
            'error': 'rede_social é obrigatório'
        }, status=400)
    
    # Buscar formatos ativos da rede social
    formatos = PostFormat.objects.filter(
        social_network=rede_social,
        is_active=True
    ).order_by('order', 'name')
    
    # Serializar
    formatos_data = [
        {
            'id': f.id,
            'name': f.name,
            'width': f.width,
            'height': f.height,
            'aspect_ratio': f.aspect_ratio,
            'dimensions': f.dimensions,
        }
        for f in formatos
    ]
    
    return JsonResponse({
        'success': True,
        'formatos': formatos_data
    })


@login_required
@require_http_methods(["GET"])
def get_org_assets(request):
    """
    Retorna logos e/ou imagens de referencia da KB da organizacao do user.
    Usado pelas galerias do modal Gerar Post.

    GET /posts/api/org-assets/?type=logos|references|all  (default: all)

    Resposta:
        {
          'success': True,
          'logos': [{id, name, logo_type, is_primary, url, file_format}],
          'references': [{id, name, url, category, file_format}]
        }
    URLs sao presigned (validas por 24h) e adequadas para exibir em
    thumbs no front (mesma URL pode ser usada num lightbox).
    """
    from apps.knowledge.models import KnowledgeBase
    from apps.core.services.s3_service import S3Service

    asset_type = (request.GET.get('type') or 'all').lower()
    org = getattr(request.user, 'organization', None)
    if not org:
        return JsonResponse(
            {'success': False, 'error': 'Usuario sem organizacao'},
            status=400,
        )

    kb = KnowledgeBase.objects.filter(organization=org).first()
    if not kb:
        return JsonResponse({
            'success': True,
            'logos': [],
            'references': [],
        })

    def _presign(s3_key):
        if not s3_key:
            return ''
        try:
            return S3Service.generate_presigned_download_url(s3_key, expires_in=86400)
        except Exception as exc:
            logger.warning('Falha ao gerar presigned para %s: %s', s3_key, exc)
            return ''

    logos_data = []
    refs_data = []

    if asset_type in ('logos', 'all'):
        try:
            for lg in kb.logos.all().order_by('-is_primary', 'logo_type'):
                logos_data.append({
                    'id': lg.id,
                    'name': lg.name or '',
                    'logo_type': lg.logo_type,
                    'is_primary': bool(lg.is_primary),
                    'file_format': lg.file_format or '',
                    'url': _presign(lg.s3_key),
                })
        except Exception:
            logger.exception('Falha ao listar logos')

    if asset_type in ('references', 'all'):
        try:
            qs = kb.reference_images.all().order_by('-id')
            for img in qs:
                refs_data.append({
                    'id': img.id,
                    'title': img.title or '',
                    'description': (img.description or '')[:200],
                    'usage_description': (getattr(img, 'usage_description', '') or '')[:200],
                    'width': img.width,
                    'height': img.height,
                    'url': _presign(img.s3_key),
                })
        except Exception:
            logger.exception('Falha ao listar references')

    return JsonResponse({
        'success': True,
        'logos': logos_data,
        'references': refs_data,
    })
