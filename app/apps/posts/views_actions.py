"""
Views de Ações para Posts
APIs para rejeitar, editar, gerar imagem, solicitar alterações, etc.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import requests

from .models import Post

logger = logging.getLogger(__name__)


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
    
    Implementação completa com:
    - PostChangeRequest (rastreamento de alterações)
    - Webhook N8N para geração de imagem
    - Email de notificação
    - Audit log
    """
    from .models import PostChangeRequest
    from .utils import (
        _notify_image_request_email,
        _notify_revision_request,
        _post_audit,
        _resolve_user_name
    )
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Buscar post com related data
        post = Post.objects.select_related(
            'organization',
            'user'
        ).prefetch_related(
            'change_requests'
        ).get(
            id=post_id,
            organization=request.organization
        )
        
        # Parse body (suporta JSON e form-data)
        payload_data = {}
        if request.content_type and request.content_type.startswith('application/json'):
            try:
                payload_data = json.loads(request.body.decode('utf-8'))
            except (TypeError, ValueError):
                payload_data = {}
        elif request.method == 'POST':
            payload_data = request.POST.dict()
        
        message = (payload_data.get('mensagem') or payload_data.get('message') or '').strip()
        
        # Verificar limite de alterações de imagem
        image_change_count = post.change_requests.filter(
            change_type=PostChangeRequest.ChangeType.IMAGE,
            is_initial=False
        ).count()
        
        if message and image_change_count >= 1:
            return JsonResponse({
                'success': False,
                'error': 'Limite de solicitações de imagem atingido.'
            }, status=400)
        
        # Atualizar status para image_generating se necessário
        if post.status != 'image_generating':
            post.status = 'image_generating'
            post.save(update_fields=['status', 'updated_at'])
        
        # Resolver nome e email do solicitante
        requester_name = _resolve_user_name(payload_data, request.user, post.organization)
        requester_email = ''
        if request.user and request.user.is_authenticated:
            requester_email = getattr(request.user, 'email', '') or ''
        
        # Criar PostChangeRequest
        change_request = PostChangeRequest.objects.create(
            post=post,
            message=message or 'Solicitação de geração de imagem',
            requester_name=requester_name[:160],
            requester_email=requester_email[:254],
            change_type=PostChangeRequest.ChangeType.IMAGE,
            is_initial=not bool(message),
        )
        
        if not change_request.is_initial:
            image_change_count += 1
        
        # Log de auditoria
        _post_audit(post, 'image_requested', request.user, meta={
            'message': message,
            'is_initial': change_request.is_initial
        })
        
        # Enviar email de notificação
        try:
            if change_request.is_initial:
                # Solicitação INICIAL de imagem (sem mensagem)
                _notify_image_request_email(post, request=request)
            else:
                # Solicitação de ALTERAÇÃO de imagem (com mensagem)
                _notify_revision_request(
                    post,
                    message,
                    payload=payload_data,
                    user=request.user,
                    request=request
                )
        except Exception as exc:
            logger.warning(f'Erro ao enviar email de solicitação: {exc}')
        
        return JsonResponse({
            'success': True,
            'id': post.id,
            'serverId': post.id,
            'status': post.status,
            'statusLabel': post.get_status_display(),
            'imageStatus': 'generating',
            'imageChanges': image_change_count,
            'imageRequestedAt': change_request.created_at.isoformat(),
        })
        
    except Post.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Post não encontrado'
        }, status=404)
    except Exception as e:
        logger.error(f'Erro ao gerar imagem: {e}', exc_info=True)
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
        
        # Integrar com N8N para solicitar alteração
        n8n_success = False
        n8n_error = None
        
        if settings.N8N_WEBHOOK_GERAR_POST:
            try:
                logger.info(f"Enviando solicitação de alteração do post {post.id} para N8N...")
                
                # Preparar payload para N8N
                n8n_payload = {
                    'action': 'request_changes',
                    'post_id': str(post.id),
                    'thread_id': post.thread_id or '',
                    'empresa': request.user.email,
                    'usuario': request.user.email,
                    'organization_id': post.organization.id,
                    'mensagem': mensagem,
                    'rede': post.social_network.capitalize() if post.social_network else 'Instagram',
                    'formato': post.content_type or 'post'
                }
                
                logger.debug(f"Payload N8N (alteração): {n8n_payload}")
                
                # Enviar para N8N
                response = requests.post(
                    settings.N8N_WEBHOOK_GERAR_POST,
                    json=n8n_payload,
                    timeout=settings.N8N_WEBHOOK_TIMEOUT,
                    headers={
                        'Content-Type': 'application/json',
                        'X-Webhook-Secret': settings.N8N_WEBHOOK_SECRET
                    }
                )
                
                response.raise_for_status()
                n8n_success = True
                logger.info(f"Solicitação de alteração do post {post.id} enviada para N8N com sucesso")
                
            except requests.exceptions.Timeout:
                n8n_error = 'Timeout ao enviar para N8N'
                logger.error(f"Timeout ao enviar alteração do post {post.id} para N8N")
            except requests.exceptions.RequestException as e:
                n8n_error = f'Erro ao enviar para N8N: {str(e)}'
                logger.error(f"Erro ao enviar alteração do post {post.id} para N8N: {e}", exc_info=True)
            except Exception as e:
                n8n_error = f'Erro inesperado: {str(e)}'
                logger.error(f"Erro inesperado ao enviar alteração do post {post.id} para N8N: {e}", exc_info=True)
        else:
            logger.warning("N8N_WEBHOOK_GERAR_POST não configurado - alteração registrada mas não enviada para processamento")
        
        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display(),
            'revisoesRestantes': post.revisions_remaining,
            'n8n_success': n8n_success,
            'n8n_error': n8n_error
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
            'message': 'Post atualizado com sucesso',
            'titulo': post.title,
            'subtitulo': post.subtitle,
            'legenda': post.caption,
            'hashtags': post.hashtags,
            'cta': post.cta,
            'descricaoImagem': post.image_prompt,
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
