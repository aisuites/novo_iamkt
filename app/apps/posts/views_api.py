"""
API endpoints para posts
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import PostFormat


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
