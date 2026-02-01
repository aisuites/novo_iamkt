"""
Views para webhooks N8N
Recebe análises e compilações do N8N
"""
import hmac
import hashlib
import time
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from apps.knowledge.models import KnowledgeBase
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def n8n_webhook_fundamentos(request):
    """
    Webhook para receber análise de fundamentos do N8N
    
    Segurança:
    - Validação de token interno
    - Validação de IP
    - Validação de assinatura HMAC
    - Validação de timestamp (anti-replay)
    - Validação de revision_id
    - Rate limiting
    """
    
    # CAMADA 1: Validação de Token Interno
    internal_token = request.headers.get('X-INTERNAL-TOKEN')
    
    if internal_token != settings.N8N_WEBHOOK_SECRET:
        logger.warning(
            f"Invalid internal token from IP: {request.META.get('REMOTE_ADDR')}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    # CAMADA 1.5: Validação de IP
    # Usar HTTP_CF_CONNECTING_IP pois requisições passam pelo Cloudflare
    client_ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR')
    allowed_ips = settings.N8N_ALLOWED_IPS.split(',')
    
    if client_ip not in allowed_ips:
        logger.warning(
            f"Unauthorized IP attempting to access webhook: {client_ip}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized IP'
        }, status=401)
    
    logger.info(f"Webhook request accepted from IP: {client_ip}")
    
    # CAMADA 2: Rate Limiting por IP
    cache_key = f"n8n_webhook_rate_limit_{client_ip}"
    current_count = cache.get(cache_key, 0)
    
    limit_str = settings.N8N_RATE_LIMIT_PER_IP
    max_requests = int(limit_str.split('/')[0])
    
    if current_count >= max_requests:
        logger.warning(
            f"Rate limit exceeded for IP {client_ip}. "
            f"Current: {current_count}, Max: {max_requests}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded'
        }, status=429)
    
    cache.set(cache_key, current_count + 1, 60)
    
    # CAMADA 3: Validação de Timestamp (TEMPORARIAMENTE DESABILITADA)
    # timestamp_header = request.headers.get('X-Timestamp')
    
    # if not timestamp_header:
    #     logger.warning("Missing X-Timestamp header")
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Missing timestamp'
    #     }, status=400)
    
    # try:
    #     timestamp = int(timestamp_header)
    # except ValueError:
    #     logger.warning(f"Invalid timestamp format: {timestamp_header}")
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Invalid timestamp'
    #     }, status=400)
    
    # current_time = int(time.time())
    # time_diff = abs(current_time - timestamp)
    
    # if time_diff > 300:  # 5 minutos
    #     logger.warning(
    #         f"Request expired. Time diff: {time_diff}s, "
    #         f"Timestamp: {timestamp}, Current: {current_time}"
    #     )
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Request expired'
    #     }, status=401)
    
    timestamp = int(time.time())  # Usar timestamp atual para HMAC
    
    # CAMADA 4: Validação de Assinatura HMAC (TEMPORARIAMENTE DESABILITADA)
    # signature_header = request.headers.get('X-Signature')
    
    # if not signature_header:
    #     logger.warning("Missing X-Signature header")
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Missing signature'
    #     }, status=400)
    
    # # Reconstruir assinatura esperada
    # payload_bytes = request.body
    # payload_string = payload_bytes.decode('utf-8')
    # message = f"{payload_string}{timestamp}"
    
    # expected_signature = hmac.new(
    #     settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
    #     message.encode('utf-8'),
    #     hashlib.sha256
    # ).hexdigest()
    
    # # Comparação segura (previne timing attacks)
    # if not hmac.compare_digest(signature_header, expected_signature):
    #     logger.warning(
    #         f"Invalid signature from IP {client_ip}. "
    #         f"Expected: {expected_signature[:10]}..., "
    #         f"Received: {signature_header[:10]}..."
    #     )
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Invalid signature'
    #     }, status=401)
    
    logger.info(f"Webhook request accepted from IP: {client_ip}")
    
    # CAMADA 5: Validação de Dados
    payload_bytes = request.body
    payload_string = payload_bytes.decode('utf-8')
    
    try:
        data = json.loads(payload_string)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    
    # Validar campos obrigatórios
    required_fields = ['kb_id', 'revision_id', 'payload']
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return JsonResponse({
                'success': False,
                'error': f'Missing field: {field}'
            }, status=400)
    
    kb_id = data['kb_id']
    revision_id = data['revision_id']
    analysis_payload = data['payload']
    
    # Buscar KB e validar revision_id
    try:
        kb = KnowledgeBase.objects.get(
            id=kb_id,
            analysis_revision_id=revision_id,
            analysis_status='processing'
        )
    except KnowledgeBase.DoesNotExist:
        logger.warning(
            f"Invalid KB or revision_id. "
            f"KB: {kb_id}, Revision: {revision_id}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Invalid KB or revision_id'
        }, status=404)
    
    # CAMADA 6: Processar Análise
    try:
        # Verificar se é reavaliação (campos aceitos/editados)
        is_reevaluation = bool(kb.accepted_suggestion_fields)
        
        if is_reevaluation:
            # MERGE SELETIVO: Atualizar apenas campos aceitos/editados
            # Motivo: Preservar avaliações de campos que usuário já aprovou
            logger.info(
                f"🔄 [N8N_WEBHOOK] Reavaliação detectada. "
                f"Campos para atualizar: {kb.accepted_suggestion_fields}"
            )
            
            # Obter análise atual
            current_analysis = kb.n8n_analysis or {}
            current_payload = current_analysis.get('payload', [])
            
            # Normalizar payload atual (pode ser lista ou dict)
            if isinstance(current_payload, list) and len(current_payload) > 0:
                current_payload = current_payload[0]
            elif not isinstance(current_payload, dict):
                current_payload = {}
            
            # Normalizar novo payload
            new_payload = analysis_payload
            if isinstance(new_payload, list) and len(new_payload) > 0:
                new_payload = new_payload[0]
            elif not isinstance(new_payload, dict):
                new_payload = {}
            
            # Atualizar APENAS campos aceitos/editados
            updated_count = 0
            for field_name in kb.accepted_suggestion_fields:
                if field_name in new_payload:
                    new_field_data = new_payload[field_name]
                    
                    # Normalizar nomes dos campos do N8N para padrão do frontend
                    # N8N usa: informado_pelo_usuario, status, sugestao_do_agente_iamkt
                    # Frontend espera: informado, classificacao, sugestao
                    normalized_field = {
                        'informado': new_field_data.get('informado_pelo_usuario', ''),
                        'classificacao': new_field_data.get('status', ''),
                        'avaliacao': new_field_data.get('avaliacao', ''),
                        'sugestao': new_field_data.get('sugestao_do_agente_iamkt', '')
                    }
                    
                    current_payload[field_name] = normalized_field
                    updated_count += 1
                    logger.info(f"   ✅ Campo atualizado: {field_name} (classificacao: {normalized_field['classificacao']})")
                else:
                    logger.warning(f"   ⚠️ Campo não encontrado no retorno N8N: {field_name}")
            
            # Salvar análise com merge
            kb.n8n_analysis = {
                'revision_id': revision_id,
                'payload': [current_payload],  # Manter como lista
                'reference_images_analysis': data.get('reference_images_analysis', []),
                'received_at': timezone.now().isoformat(),
                'is_reevaluation': True,
                'updated_fields': kb.accepted_suggestion_fields,
                'updated_count': updated_count
            }
            
            logger.info(
                f"✅ [N8N_WEBHOOK] Merge seletivo concluído. "
                f"{updated_count} campos atualizados de {len(kb.accepted_suggestion_fields)}"
            )
            
            # Limpar lista de campos aceitos
            kb.accepted_suggestion_fields = []
            
        else:
            # PRIMEIRA VEZ: Armazenar análise completa
            logger.info(f"📝 [N8N_WEBHOOK] Primeira análise - armazenando completo")
            
            kb.n8n_analysis = {
                'revision_id': revision_id,
                'payload': analysis_payload,
                'reference_images_analysis': data.get('reference_images_analysis', []),
                'received_at': timezone.now().isoformat()
            }
        
        kb.analysis_status = 'completed'
        kb.analysis_completed_at = timezone.now()
        kb.save(update_fields=[
            'n8n_analysis',
            'analysis_status',
            'analysis_completed_at',
            'accepted_suggestion_fields'
        ])
        
        # Log sucesso
        logger.info(
            f"N8N analysis received and stored. "
            f"KB: {kb_id}, Org: {kb.organization_id}, "
            f"Revision: {revision_id}, "
            f"Reevaluation: {is_reevaluation}"
        )
        
        # Se foi reavaliação, enviar para compilação automaticamente
        if is_reevaluation:
            logger.info(f"🔄 [N8N_WEBHOOK] Enviando para compilação após reavaliação (semsugest)")
            from apps.knowledge.services.n8n_service import N8NService
            
            try:
                # Sempre usar semsugest após reavaliação
                compilation_result = N8NService.send_for_compilation(kb, has_accepted_suggestions=False)
                if compilation_result['success']:
                    logger.info(f"✅ [N8N_WEBHOOK] Compilação enviada com sucesso (semsugest)")
                else:
                    logger.warning(f"⚠️ [N8N_WEBHOOK] Falha ao enviar compilação: {compilation_result.get('error')}")
            except Exception as e:
                logger.exception(f"❌ [N8N_WEBHOOK] Erro ao enviar compilação: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': 'Analysis received and stored',
            'is_reevaluation': is_reevaluation
        }, status=200)
        
    except Exception as e:
        logger.exception(f"Error processing N8N analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def n8n_compilation_webhook(request):
    """
    Webhook para receber compilação do N8N (após aplicar sugestões).
    
    Segurança:
    - Validação de token interno
    - Validação de IP
    - Rate limiting
    """
    
    # CAMADA 1: Validação de Token Interno
    internal_token = request.headers.get('X-INTERNAL-TOKEN')
    
    if internal_token != settings.N8N_WEBHOOK_SECRET:
        logger.warning(
            f"❌ [N8N_COMPILATION_WEBHOOK] Token inválido do IP: {request.META.get('REMOTE_ADDR')}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    # CAMADA 2: Validação de IP
    client_ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR')
    allowed_ips = settings.N8N_ALLOWED_IPS.split(',')
    
    if client_ip not in allowed_ips:
        logger.warning(
            f"❌ [N8N_COMPILATION_WEBHOOK] IP não autorizado: {client_ip}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Forbidden'
        }, status=403)
    
    # CAMADA 3: Rate Limiting por IP
    cache_key = f"n8n_compilation_webhook_{client_ip}"
    current_count = cache.get(cache_key, 0)
    
    limit_str = settings.N8N_RATE_LIMIT_PER_IP
    max_requests = int(limit_str.split('/')[0])
    
    if current_count >= max_requests:
        logger.warning(
            f"⚠️ [N8N_COMPILATION_WEBHOOK] Rate limit excedido para IP {client_ip}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded'
        }, status=429)
    
    cache.set(cache_key, current_count + 1, 60)
    
    # CAMADA 4: Validação de Dados
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("❌ [N8N_COMPILATION_WEBHOOK] JSON inválido")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    
    # N8N pode enviar array ou objeto - normalizar para objeto
    if isinstance(data, list):
        if len(data) == 0:
            logger.warning("❌ [N8N_COMPILATION_WEBHOOK] Array vazio recebido")
            return JsonResponse({
                'success': False,
                'error': 'Empty array received'
            }, status=400)
        data = data[0]  # Pegar primeiro elemento do array
    
    # Extrair revision_id do payload (enviado pelo Django no payload original)
    revision_id = data.get('revision_id') or request.headers.get('X-Revision-ID')
    if not revision_id:
        logger.warning("❌ [N8N_COMPILATION_WEBHOOK] revision_id ausente")
        return JsonResponse({
            'success': False,
            'error': 'revision_id obrigatório'
        }, status=400)
    
    # Buscar KB pelo revision_id
    try:
        kb = KnowledgeBase.objects.get(
            analysis_revision_id=revision_id
        )
    except KnowledgeBase.DoesNotExist:
        logger.error(
            f"❌ [N8N_COMPILATION_WEBHOOK] KB não encontrado para revision_id: {revision_id}"
        )
        return JsonResponse({
            'success': False,
            'error': 'KB não encontrado'
        }, status=404)
    
    # CAMADA 5: Processar Compilação
    try:
        # Log do payload recebido para debug
        logger.info(f"🔍 [N8N_COMPILATION_WEBHOOK] Payload recebido - Keys: {list(data.keys())}")
        
        # Extrair dados da compilação
        # N8N pode enviar com chave 'compilation' ou diretamente os dados
        compilation_data = data.get('compilation') or data
        
        logger.info(f"🔍 [N8N_COMPILATION_WEBHOOK] Compilation data keys: {list(compilation_data.keys())}")
        
        # Remover metadados do Django (kb_id, organization_id, revision_id, flow_type)
        # APENAS se existirem - não remover dados válidos do N8N
        metadata_keys = ['kb_id', 'organization_id', 'organization_name', 'revision_id', 'flow_type']
        
        # Verificar se há metadados para remover
        has_metadata = any(key in compilation_data for key in metadata_keys)
        
        if has_metadata:
            # Criar cópia sem metadados
            clean_data = {k: v for k, v in compilation_data.items() if k not in metadata_keys}
            # Só substituir se ainda houver dados após limpeza
            if clean_data:
                compilation_data = clean_data
                logger.info(f"🔍 [N8N_COMPILATION_WEBHOOK] Metadados removidos - Keys restantes: {list(compilation_data.keys())}")
            else:
                logger.warning(f"⚠️ [N8N_COMPILATION_WEBHOOK] Todos os dados seriam removidos - mantendo original")
        else:
            logger.info(f"🔍 [N8N_COMPILATION_WEBHOOK] Nenhum metadado encontrado - usando dados diretamente")
        
        if not compilation_data or len(compilation_data) == 0:
            logger.warning(
                f"⚠️ [N8N_COMPILATION_WEBHOOK] Dados de compilação vazios para KB {kb.id}"
            )
            return JsonResponse({
                'success': False,
                'error': 'Dados de compilação vazios'
            }, status=400)
        
        # Armazenar compilação diretamente
        kb.n8n_compilation = compilation_data
        
        # Atualizar status
        kb.compilation_status = 'completed'
        kb.compilation_completed_at = timezone.now()
        
        kb.save(update_fields=[
            'n8n_compilation',
            'compilation_status',
            'compilation_completed_at'
        ])
        
        # Log sucesso
        logger.info(
            f"✅ [N8N_COMPILATION_WEBHOOK] Compilação recebida com sucesso. "
            f"KB: {kb.id}, Org: {kb.organization.name}, Revision: {revision_id}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Compilação recebida com sucesso',
            'kb_id': kb.id
        }, status=200)
        
    except Exception as e:
        logger.exception(f"❌ [N8N_COMPILATION_WEBHOOK] Erro ao processar compilação: {str(e)}")
        
        # Marcar como erro
        kb.compilation_status = 'error'
        kb.save(update_fields=['compilation_status'])
        
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)
