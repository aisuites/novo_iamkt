"""
Views de Ações para Posts
APIs para rejeitar, editar, gerar imagem, solicitar alterações, etc.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Post


@login_required
@require_http_methods(["POST"])
def reject_post(request, post_id):
    """
    Rejeitar um post
    
    POST /posts/<id>/reject/
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Atualizar status
        post.status = 'rejected'
        post.save()
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display(),
            'revisoesRestantes': post.revisions_remaining
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generate_image(request, post_id):
    """
    Iniciar geração de imagem para um post
    
    POST /posts/<id>/generate-image/
    Body: { "mensagem": "..." } (opcional)
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Parse body
        data = json.loads(request.body) if request.body else {}
        mensagem = data.get('mensagem', '')
        
        # Atualizar status
        post.status = 'generating'  # Usar status existente
        post.save()
        
        # TODO: Integrar com N8N para geração de imagem
        # webhook_url = settings.N8N_WEBHOOK_GENERATE_IMAGE
        # requests.post(webhook_url, json={
        #     'post_id': post.id,
        #     'organization_id': post.organization.id,
        #     'mensagem': mensagem
        # })
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display()
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def request_text_change(request, post_id):
    """
    Solicitar alteração no texto do post
    
    POST /posts/<id>/request-text-change/
    Body: { "mensagem": "..." }
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Parse body
        data = json.loads(request.body)
        mensagem = data.get('mensagem', '').strip()
        
        if not mensagem:
            return JsonResponse({
                'success': False,
                'error': 'Mensagem é obrigatória'
            }, status=400)
        
        # Verificar limite de revisões
        if post.revisions_remaining <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Limite de revisões atingido'
            }, status=400)
        
        # Atualizar status
        post.status = 'generating'
        post.revisions_remaining -= 1
        post.save()
        
        # TODO: Integrar com N8N para regeneração de texto
        # webhook_url = settings.N8N_WEBHOOK_REGENERATE_TEXT
        # requests.post(webhook_url, json={
        #     'post_id': post.id,
        #     'organization_id': post.organization.id,
        #     'mensagem': mensagem
        # })
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display(),
            'revisoesRestantes': post.revisions_remaining
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def request_image_change(request, post_id):
    """
    Solicitar alteração na imagem do post
    
    POST /posts/<id>/request-image-change/
    Body: { "mensagem": "..." }
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Parse body
        data = json.loads(request.body)
        mensagem = data.get('mensagem', '').strip()
        
        if not mensagem:
            return JsonResponse({
                'success': False,
                'error': 'Mensagem é obrigatória'
            }, status=400)
        
        # Atualizar status
        post.status = 'generating'  # Usar status existente
        post.save()
        
        # TODO: Integrar com N8N para regeneração de imagem
        # webhook_url = settings.N8N_WEBHOOK_REGENERATE_IMAGE
        # requests.post(webhook_url, json={
        #     'post_id': post.id,
        #     'organization_id': post.organization.id,
        #     'mensagem': mensagem
        # })
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display()
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def edit_post(request, post_id):
    """
    Editar campos do post manualmente
    
    POST /posts/<id>/edit/
    Body: {
        "titulo": "...",
        "subtitulo": "...",
        "legenda": "...",
        "hashtags": "...",
        "cta": "...",
        "descricaoImagem": "..."
    }
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Parse body
        data = json.loads(request.body)
        
        # Atualizar campos se fornecidos
        if 'titulo' in data:
            post.title = data['titulo']
        if 'subtitulo' in data:
            post.subtitle = data['subtitulo']
        if 'legenda' in data:
            post.caption = data['legenda']
        if 'hashtags' in data:
            post.hashtags = data['hashtags']
        if 'cta' in data:
            post.cta = data['cta']
        if 'descricaoImagem' in data:
            post.image_prompt = data['descricaoImagem']
        
        post.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Post atualizado com sucesso'
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def approve_post(request, post_id):
    """
    Aprovar um post (mudar status para approved)
    
    POST /posts/<id>/approve/
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )
        
        # Atualizar status
        post.status = 'approved'
        post.save()
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display()
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
