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

from .models import Post, PostImage
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
        # Imagem-fonte da alteracao = a que esta no PREVIEW GRANDE (ativa) no front.
        source_s3_key = (payload_data.get('source_s3_key') or '').strip()

        # Verificar limite de alterações de imagem (configurável por organização)
        max_revisions = post.organization.max_image_revisions
        image_change_count = 0  # default — evita UnboundLocalError se max_revisions==0

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
        
        # Pipeline SIMPLES v2 (Celery + Gemini Nano Banana) — pipeline_used='simple'
        if post.pipeline_used == 'simple':
            from apps.posts.tasks import (
                generate_post_simple_image_task, revise_image_task,
            )
            if message:
                # ALTERACAO de imagem (image-to-image): gpt-4o-mini -> prompt ->
                # Gemini edita a imagem do preview. Local, sem n8n.
                revise_image_task.delay(post.id, message, source_s3_key)
                logger.info('[posts.simple] revise_image_task disparado post_id=%s key=%s',
                            post.id, source_s3_key or '(principal)')
            else:
                # Geracao INICIAL da imagem (cena aprovada -> Gemini).
                generate_post_simple_image_task.delay(post.id)
                logger.info('[posts.simple] generate_post_simple_image_task disparado post_id=%s', post.id)
            return JsonResponse({
                'success': True,
                'id': post.id,
                'serverId': post.id,
                'status': post.status,
                'statusLabel': post.get_status_display(),
                'imageStatus': 'generating',
                'imageChanges': image_change_count,
                'imageRequestedAt': change_request.created_at.isoformat(),
                'pipeline': 'simple',
            })

        # Pipeline INTERNA (Celery + Gemini) — disparada se o post foi criado
        # via "Enviar Fluxo interno" (pipeline_used='local')
        if post.pipeline_used == 'local':
            from apps.posts.tasks import generate_post_image_task
            generate_post_image_task.delay(post.id, message or '')
            logger.info(
                '[posts.local] generate_post_image_task disparado post_id=%s', post.id
            )
            return JsonResponse({
                'success': True,
                'id': post.id,
                'serverId': post.id,
                'status': post.status,
                'statusLabel': post.get_status_display(),
                'imageStatus': 'generating',
                'imageChanges': image_change_count,
                'imageRequestedAt': change_request.created_at.isoformat(),
                'pipeline': 'local',
            })

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
                    if kb.publico_externo:
                        publico_alvo = kb.publico_externo
                    
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
                    
                    # Referências - Logos (com URLs presigned - 24h)
                    try:
                        logos = kb.logos.all().order_by('-is_primary', 'logo_type')
                        for logo in logos:
                            if logo.s3_key:
                                try:
                                    # Gerar URL presigned (válida por 24 horas)
                                    presigned_url = S3Service.generate_presigned_download_url(logo.s3_key, expires_in=86400)
                                    print(f"🔍 [DEBUG] Logo presigned URL: {presigned_url}", flush=True)
                                    referencias.append({
                                        'tipo': 'logotipo',
                                        'url': presigned_url
                                    })
                                except Exception as url_error:
                                    logger.warning(f"Erro ao gerar URL presigned para logo {logo.id}: {url_error}")
                    except Exception as logo_error:
                        logger.warning(f"Erro ao buscar logos: {logo_error}")
                    
                    # Referências - Imagens KB (com URLs presigned - 24h)
                    try:
                        kb_images = kb.reference_images.all()
                        for img in kb_images:
                            if img.s3_key:
                                try:
                                    # Gerar URL presigned (válida por 24 horas)
                                    presigned_url = S3Service.generate_presigned_download_url(img.s3_key, expires_in=86400)
                                    referencias.append({
                                        'tipo': 'referencia_kb',
                                        'url': presigned_url
                                    })
                                except Exception as url_error:
                                    logger.warning(f"Erro ao gerar URL presigned para imagem KB {img.id}: {url_error}")
                    except Exception as ref_error:
                        logger.warning(f"Erro ao buscar imagens de referência KB: {ref_error}")
                
                # Referências do Post (PostReferenceImage - com URLs presigned - 24h)
                try:
                    post_ref_images = post.reference_image_files.all()
                    for ref_img in post_ref_images:
                        if ref_img.s3_key:
                            try:
                                # Gerar URL presigned (válida por 24 horas)
                                presigned_url = S3Service.generate_presigned_download_url(ref_img.s3_key, expires_in=86400)
                                referencias.append({
                                    'tipo': 'referencia_post',
                                    'url': presigned_url
                                })
                            except Exception as url_error:
                                logger.warning(f"Erro ao gerar URL presigned para imagem post {ref_img.id}: {url_error}")
                except Exception as post_ref_error:
                    logger.warning(f"Erro ao buscar imagens de referência do post: {post_ref_error}")
                
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
    ALTERAR CENA - IA: revisa a CENA (image_prompt) LOCALMENTE via orquestrador
    (Claude), continuando a conversa com cache. SEM n8n. Limitado a
    MAX_TEXT_REVISIONS por post.

    POST /posts/<id>/request-text-change/
    Body: { "mensagem": "..." }
    """
    try:
        post = Post.objects.get(
            id=post_id,
            organization=request.organization
        )

        data = json.loads(request.body)
        mensagem = (data.get('mensagem') or '').strip()
        if not mensagem:
            return JsonResponse({
                'success': False, 'error': 'Mensagem é obrigatória'
            }, status=400)

        from apps.posts.models import PostChangeRequest
        from apps.posts.tasks_simple import MAX_TEXT_REVISIONS, revise_scene_task

        # Limite: espelha a alteracao de imagem (conta pedidos de texto nao-iniciais)
        usadas = PostChangeRequest.objects.filter(
            post=post, change_type='text', is_initial=False
        ).count()
        if usadas >= MAX_TEXT_REVISIONS:
            return JsonResponse({
                'success': False, 'error': 'Limite de alterações de cena atingido'
            }, status=400)

        PostChangeRequest.objects.create(
            post=post, message=mensagem,
            change_type='text', is_initial=False,
            requester_email=getattr(request.user, 'email', '') or '',
        )

        post.status = 'generating'
        post.save(update_fields=['status'])

        # Dispara a revisao local (Celery). NAO chama n8n.
        revise_scene_task.delay(post.id, mensagem)

        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display(),
            'revisoesTextoRestantes': max(0, MAX_TEXT_REVISIONS - usadas - 1),
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
def regenerate_post(request, post_id):
    """GERAR NOVAMENTE: o usuario nao gostou de nada — reroda a Fase 1 (textos
    OpenAI + cena do orquestrador) do zero, LOCALMENTE. Conteudo novo zera o
    budget de "Alterar Cena - IA". Sem n8n.

    POST /posts/<id>/regenerate/
    """
    try:
        post = Post.objects.get(id=post_id, organization=request.organization)

        from apps.posts.models import PostChangeRequest
        from apps.posts.tasks_simple import generate_post_simple_task

        # Conteudo novo = novo budget de alteracao de cena
        PostChangeRequest.objects.filter(post=post, change_type='text').delete()

        post.status = 'generating'
        post.save(update_fields=['status'])

        generate_post_simple_task.delay(post.id)

        return JsonResponse({
            'success': True,
            'status': post.status,
            'statusLabel': post.get_status_display(),
        })
    except Post.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Post não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
            raw = data['hashtags']
            # Front manda string ("#a #b" ou "a, b"); o campo e JSONField (lista).
            # Sem normalizar, list(post.hashtags) vira lista de CARACTERES.
            if isinstance(raw, str):
                parts = raw.replace(',', ' ').split()
                raw = [p if p.startswith('#') else '#' + p.lstrip('#')
                       for p in parts if p.strip()]
            post.hashtags = raw
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



@login_required
@require_http_methods(["DELETE"])
def delete_post_image(request, post_id, image_id):
    """
    Deleta uma imagem gerada de um post (banco + S3).

    DELETE /posts/<post_id>/images/<image_id>/delete/

    Returns:
        {'success': bool, 'remaining': int}  # qtd de imagens restantes no post
    """
    try:
        image = PostImage.objects.select_related('post').get(
            id=image_id,
            post_id=post_id,
            post__organization=request.organization,
        )
    except PostImage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Imagem nao encontrada'}, status=404)

    post = image.post
    s3_key = image.s3_key

    try:
        if s3_key:
            S3Service.delete_file(s3_key)
    except Exception:
        logger.exception('[posts] falha S3 delete image=%s key=%s', image_id, s3_key)
        # nao bloqueia o delete do banco — orfaos em S3 sao lidos pelo cleanup

    image.delete()

    # Se a imagem principal apontava para essa key, limpa os campos do Post
    if post.image_s3_key and post.image_s3_key == s3_key:
        post.image_s3_key = ''
        post.image_s3_url = ''
        post.has_image = False
        post.save(update_fields=['image_s3_key', 'image_s3_url', 'has_image'])

    remaining = post.images.count()
    return JsonResponse({'success': True, 'remaining': remaining})
