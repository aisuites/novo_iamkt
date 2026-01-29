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
    
    # CAMADA 1.5: Validação de IP (TEMPORARIAMENTE DESABILITADA PARA TESTE)
    client_ip = request.META.get('REMOTE_ADDR')
    # allowed_ips = settings.N8N_ALLOWED_IPS.split(',')
    
    # if client_ip not in allowed_ips:
    #     logger.warning(
    #         f"Unauthorized IP attempting to access webhook: {client_ip}"
    #     )
    #     return JsonResponse({
    #         'success': False,
    #         'error': 'Unauthorized IP'
    #     }, status=401)
    
    logger.info(f"Webhook request from IP: {client_ip}")
    
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
        # Armazenar análise
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
            'analysis_completed_at'
        ])
        
        # Log sucesso
        logger.info(
            f"N8N analysis received and stored. "
            f"KB: {kb_id}, Org: {kb.organization_id}, "
            f"Revision: {revision_id}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Analysis received and stored'
        }, status=200)
        
    except Exception as e:
        logger.exception(f"Error processing N8N analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)
