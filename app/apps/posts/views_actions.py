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
from apps.core.services.s3_service import S3Service

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
        
        # Verificar limite de alterações de imagem (configurável por organização)
        max_revisions = post.organization.max_image_revisions
        
        # Se max_revisions = 0, permite ilimitado
        if max_revisions > 0:
            image_change_count = post.change_requests.filter(
                change_type=PostChangeRequest.ChangeType.IMAGE,
                is_initial=False
            ).count()
            
            if message and image_change_count >= max_revisions:
                return JsonResponse({
                    'success': False,
                    'error': f'Limite de {max_revisions} alteração(ões) de imagem atingido para esta organização.'
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
        
        # Enviar para N8N (webhook de geração de imagem)
        if hasattr(settings, 'N8N_WEBHOOK_GERAR_IMAGEM') and settings.N8N_WEBHOOK_GERAR_IMAGEM:
            try:
                from .utils import _resolve_post_format
                from django.urls import reverse
                from apps.knowledge.models import KnowledgeBase
                
                logger.info(f"Enviando solicitação de geração de imagem do post {post.id} para N8N...")
                
                # Resolver formato da imagem
                format_data = _resolve_post_format(post)
                
                # Buscar Knowledge Base da organização
                kb = None
                try:
                    kb = KnowledgeBase.objects.filter(
                        organization=request.user.organization
                    ).first()
                except Exception as kb_error:
                    logger.warning(f"Erro ao buscar KB: {kb_error}")
                
                # Buscar dados de design da KB
                kb_id = None
                marketing_input_summary = ''
                publico_alvo = ''
                paleta = []
                tipografia = []
                referencias = []  # Array unificado de todas as referências
                
                if kb:
                    kb_id = str(kb.id)
                    
                    # Marketing Input Summary
                    if kb.n8n_compilation and isinstance(kb.n8n_compilation, dict):
                        marketing_input_summary = kb.n8n_compilation.get('marketing_input_summary', '')
                    
                    # Público Alvo
                    if kb.publico_alvo:
                        publico_alvo = kb.publico_alvo
                    
                    # Paleta de Cores
                    try:
                        colors = kb.colors.all().order_by('order')
                        for color in colors:
                            paleta.append({
                                'nome': color.name,
                                'hex': color.hex_code,
                                'tipo': color.color_type or 'primary'
                            })
                    except Exception as color_error:
                        logger.warning(f"Erro ao buscar cores: {color_error}")
                    
                    # Tipografia
                    try:
                        fonts = kb.typography_settings.all().order_by('order')
                        for font in fonts:
                            font_name = font.google_font_name if font.font_source == 'google' else (font.custom_font.name if font.custom_font else '')
                            font_weight = font.google_font_weight if font.font_source == 'google' else 'regular'
                            font_url = font.google_font_url if font.font_source == 'google' else ''
                            tipografia.append({
                                'uso': font.usage,
                                'origem': font.font_source or 'google',
                                'nome': font_name,
                                'peso': font_weight,
                                'url': font_url
                            })
                    except Exception as font_error:
                        logger.warning(f"Erro ao buscar fontes: {font_error}")
                    
                    # Referências - Logos (com URLs presigned)
                    try:
                        logos = kb.logos.all().order_by('-is_primary', 'logo_type')
                        for logo in logos:
                            if logo.s3_key:
                                try:
                                    # Gerar URL presigned (válida por 1 hora)
                                    presigned_url = S3Service.generate_presigned_download_url(logo.s3_key, expires_in=3600)
                                    referencias.append({
                                        'tipo': 'logotipo',
                                        'url': presigned_url
                                    })
                                except Exception as url_error:
                                    logger.warning(f"Erro ao gerar URL presigned para logo {logo.id}: {url_error}")
                    except Exception as logo_error:
                        logger.warning(f"Erro ao buscar logos: {logo_error}")
                    
                    # Referências - Imagens KB (com URLs presigned)
                    try:
                        kb_images = kb.reference_images.all()
                        for img in kb_images:
                            if img.s3_key:
                                try:
                                    # Gerar URL presigned (válida por 1 hora)
                                    presigned_url = S3Service.generate_presigned_download_url(img.s3_key, expires_in=3600)
                                    referencias.append({
                                        'tipo': 'referencia',
                                        'url': presigned_url
                                    })
                                except Exception as url_error:
                                    logger.warning(f"Erro ao gerar URL presigned para imagem KB {img.id}: {url_error}")
                    except Exception as ref_error:
                        logger.warning(f"Erro ao buscar imagens de referência: {ref_error}")
                
                # Referências do Post (se houver)
                if post.reference_images and isinstance(post.reference_images, list):
                    for ref_img in post.reference_images:
                        referencias.append({
                            'tipo': 'post_image',
                            'url': ref_img.get('url', '') if isinstance(ref_img, dict) else ref_img
                        })
                
                # Configurações S3
                s3_bucket = getattr(settings, 'AWS_BUCKET_NAME', '')
                s3_pasta = f"/org-{request.user.organization.id}/imagensgeradas/" if request.user.organization else '/imagensgeradas/'
                
                # Montar payload para N8N
                n8n_payload = {
                    'callback_url': f"{settings.SITE_URL}{reverse('posts:n8n_post_callback')}",
                    'post_id': post.id,
                    'thread_id': post.thread_id or '',
                    'kb_id': kb_id or '',
                    's3_bucket': s3_bucket,
                    's3_pasta': s3_pasta,
                    'quantidade': post.image_count or 1,
                    'rede_social': post.social_network or 'instagram',
                    'formato_px': format_data['formato_px'],
                    'aspect_ratio': format_data['aspect_ratio'],
                    'publico_alvo': publico_alvo,
                    'titulo': post.title or '',
                    'subtitulo': post.subtitle or '',
                    'cta': post.cta or '',
                    'prompt': post.image_prompt or '',
                    'marketing_input_summary': marketing_input_summary,
                    'paleta': paleta,
                    'tipografia': tipografia,
                    'referencias': referencias,
                }
                
                # Adicionar mensagem de alteração se houver
                if message:
                    n8n_payload['mensagem_alteracao'] = message
                
                logger.debug(f"Payload N8N (gerar imagem): {n8n_payload}")
                
                # Enviar para N8N
                timeout = getattr(settings, 'N8N_WEBHOOK_TIMEOUT', 30)
                headers = {
                    'Content-Type': 'application/json',
                }
                if hasattr(settings, 'N8N_WEBHOOK_SECRET') and settings.N8N_WEBHOOK_SECRET:
                    headers['X-Webhook-Secret'] = settings.N8N_WEBHOOK_SECRET
                
                response = requests.post(
                    settings.N8N_WEBHOOK_GERAR_IMAGEM,
                    json=n8n_payload,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"N8N respondeu com sucesso para post {post.id}")
                    # Atualizar thread_id se N8N retornar
                    try:
                        n8n_response = response.json()
                        if 'thread_id' in n8n_response and n8n_response['thread_id']:
                            post.thread_id = n8n_response['thread_id']
                            post.save(update_fields=['thread_id'])
                    except:
                        pass
                else:
                    logger.warning(f"N8N retornou status {response.status_code} para post {post.id}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"Timeout ao chamar N8N para post {post.id}")
            except Exception as n8n_exc:
                logger.error(f"Erro ao chamar N8N para post {post.id}: {n8n_exc}", exc_info=True)
        
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
