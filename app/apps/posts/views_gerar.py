"""
Views para geração de posts
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.conf import settings
from apps.posts.models import Post
import json
import requests
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def gerar_post(request):
    """
    Cria um novo Post no banco de dados
    
    POST params (JSON):
        - rede_social: str (instagram, facebook, linkedin, whatsapp)
        - formato: str (feed, stories, both)
        - cta_requested: bool
        - is_carousel: bool
        - image_count: int (2-5)
        - tema: str (required)
        - reference_images: list[dict] (opcional)
    
    Returns:
        {
            'success': bool,
            'data': {
                'post_id': int,
                'message': str
            }
        }
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        
        # Validações
        rede_social = data.get('rede_social')
        formato = data.get('formato', 'feed')
        cta_requested = data.get('cta_requested', True)
        is_carousel = data.get('is_carousel', False)
        image_count = data.get('image_count', 1)
        tema = data.get('tema', '').strip()
        reference_images = data.get('reference_images', [])
        
        # Validar campos obrigatórios
        if not rede_social:
            return JsonResponse({
                'success': False,
                'error': 'Rede social é obrigatória'
            }, status=400)
        
        if not tema:
            return JsonResponse({
                'success': False,
                'error': 'Tema é obrigatório'
            }, status=400)
        
        # Validar rede social
        valid_networks = ['instagram', 'facebook', 'linkedin', 'whatsapp']
        if rede_social not in valid_networks:
            return JsonResponse({
                'success': False,
                'error': f'Rede social inválida. Opções: {", ".join(valid_networks)}'
            }, status=400)
        
        # Validar formato
        valid_formats = ['feed', 'stories', 'both']
        if formato not in valid_formats:
            return JsonResponse({
                'success': False,
                'error': f'Formato inválido. Opções: {", ".join(valid_formats)}'
            }, status=400)
        
        # Validar quantidade de imagens
        if is_carousel:
            if image_count < 2 or image_count > 5:
                return JsonResponse({
                    'success': False,
                    'error': 'Quantidade de imagens deve ser entre 2 e 5'
                }, status=400)
        
        # Preparar formatos (lista)
        if formato == 'both':
            formats = ['feed', 'stories']
        else:
            formats = [formato]
        
        # Determinar content_type baseado no formato
        if is_carousel:
            content_type = 'carrossel'
        elif formato == 'stories':
            content_type = 'story'
        else:
            content_type = 'post'
        
        # Criar Post com transaction
        with transaction.atomic():
            post = Post.objects.create(
                # Multi-tenant - CRÍTICO
                organization=request.user.organization,
                user=request.user,
                
                # Dados do formulário
                requested_theme=tema,
                social_network=rede_social,
                content_type=content_type,
                formats=formats,
                cta_requested=cta_requested,
                is_carousel=is_carousel,
                image_count=image_count if is_carousel else 1,
                reference_images=reference_images,
                
                # Status inicial - 'generating' ao enviar para N8N
                status='generating',
                
                # Campos vazios (serão preenchidos pelo agente)
                caption='',
                hashtags=[],
                ia_provider='openai',
                ia_model_text='gpt-4',
            )
        
        # Enviar para N8N (se configurado)
        n8n_success = False
        n8n_error = None
        
        if settings.N8N_WEBHOOK_GERAR_POST:
            try:
                logger.info(f"Enviando post {post.id} para N8N...")
                
                # Buscar KnowledgeBase da organização
                from apps.knowledge.models import KnowledgeBase
                try:
                    kb = KnowledgeBase.objects.filter(
                        organization=post.organization
                    ).first()
                    
                    knowledge_base_data = None
                    if kb and kb.n8n_compilation:
                        # Extrair apenas marketing_input_summary do JSON n8n_compilation
                        marketing_summary = ''
                        if isinstance(kb.n8n_compilation, dict):
                            marketing_summary = kb.n8n_compilation.get('marketing_input_summary', '')
                        elif isinstance(kb.n8n_compilation, str):
                            try:
                                import json as json_lib
                                compilation_data = json_lib.loads(kb.n8n_compilation)
                                marketing_summary = compilation_data.get('marketing_input_summary', '')
                            except:
                                marketing_summary = kb.n8n_compilation
                        
                        if marketing_summary:
                            knowledge_base_data = {
                                'kb_id': kb.id,
                                'company_name': kb.nome_empresa or '',
                                'marketing_input_summary': marketing_summary,
                                'reference_images_analysis': ''
                            }
                            logger.debug(f"KnowledgeBase encontrado: {kb.id}")
                        else:
                            logger.warning(f"marketing_input_summary vazio no KB {kb.id}")
                    else:
                        logger.warning(f"KnowledgeBase não encontrado ou n8n_compilation vazio para organization {post.organization.id}")
                except Exception as e:
                    logger.error(f"Erro ao buscar KnowledgeBase: {e}", exc_info=True)
                    knowledge_base_data = None
                
                # Preparar payload para N8N (IDÊNTICO à aplicação antiga)
                n8n_payload = {
                    'action': 'create_suggestion',
                    'post_id': str(post.id),
                    'thread_id': post.thread_id or '',
                    'empresa': request.user.email,
                    'usuario': request.user.email,
                    'rede': rede_social.capitalize(),
                    'redes_sociais': rede_social.capitalize(),
                    'formato': formats[0] if formats else 'feed',
                    'formatos': formats[0] if formats else 'feed',
                    'carrossel': 'Sim' if is_carousel else 'Não',
                    'qtd_imagens': str(image_count if is_carousel else 1),
                    'tema': tema,
                    'organization_id': post.organization.id,
                    'cta_requested': 'Sim' if cta_requested else 'Não',
                    'knowledge_base': knowledge_base_data
                }
                
                logger.debug(f"Payload N8N: {n8n_payload}")
                
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
                logger.info(f"Post {post.id} enviado para N8N com sucesso")
                
            except requests.exceptions.Timeout:
                n8n_error = 'Timeout ao enviar para N8N'
                logger.error(f"Timeout ao enviar post {post.id} para N8N")
            except requests.exceptions.RequestException as e:
                n8n_error = f'Erro ao enviar para N8N: {str(e)}'
                logger.error(f"Erro ao enviar post {post.id} para N8N: {e}", exc_info=True)
            except Exception as e:
                n8n_error = f'Erro inesperado: {str(e)}'
                logger.error(f"Erro inesperado ao enviar post {post.id} para N8N: {e}", exc_info=True)
        else:
            logger.warning("N8N_WEBHOOK_GERAR_POST não configurado - post criado mas não enviado para processamento")
        
        # Retornar dados normalizados (compatível com frontend do resumo.html)
        return JsonResponse({
            'success': True,
            'id': post.id,
            'serverId': post.id,
            'rede': post.social_network,
            'formatos': post.formats,
            'carrossel': post.is_carousel,
            'qtdImagens': post.image_count,
            'tema': post.requested_theme,
            'titulo': post.title or f'Post gerado - {post.social_network}',
            'subtitulo': post.subtitle or '',
            'legenda': post.caption or '',
            'hashtags': post.hashtags,
            'cta': post.cta or '',
            'descricaoImagem': post.image_prompt or f'Gerar imagem com base em {tema}',
            'status': post.status,
            'revisoesRestantes': post.revisions_remaining,
            'referencias': reference_images,
            'createdAt': post.created_at.isoformat(),
            'n8n_sent': n8n_success,
            'n8n_error': n8n_error,
            'data': {
                'post_id': post.id,
                'message': 'Post criado com sucesso! Aguardando processamento.' if n8n_success else 'Post criado mas não enviado para processamento.'
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao criar post: {str(e)}", exc_info=True)
        
        return JsonResponse({
            'success': False,
            'error': f'Erro ao criar post: {str(e)}'
        }, status=500)
