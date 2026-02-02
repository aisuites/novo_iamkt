"""
Views para gerar pautas via N8N
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.conf import settings
import requests
from apps.core.models import Organization
from django.utils import timezone

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
@login_required
def gerar_pauta_n8n(request):
    """
    View para enviar dados do formulário de geração de pautas para o N8N
    """
    try:
        # Parse dados do formulário
        data = json.loads(request.body)
        rede_social = data.get('rede_social')
        tema = data.get('tema', '')
        
        if not rede_social:
            return JsonResponse({
                'success': False,
                'error': 'Rede social é obrigatória'
            }, status=400)
        
        # Obter organização do usuário
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({
                'success': False,
                'error': 'Usuário sem organização definida'
            }, status=400)
        
        # Obter marketing_input_summary da base estratégica
        marketing_input_summary = ''
        try:
            from apps.knowledge.models import KnowledgeBase
            
            kb = KnowledgeBase.objects.filter(organization=organization).first()
            
            if kb and kb.n8n_compilation and isinstance(kb.n8n_compilation, dict):
                marketing_input_summary = kb.n8n_compilation.get('marketing_input_summary', '')
                        
        except Exception as e:
            logger.error(f"Erro ao obter marketing_input_summary: {str(e)}")
        
        # Preparar payload para N8N
        payload = {
            'organization': organization.name,
            'organization_id': organization.id,
            'user_id': request.user.id,
            'user_email': request.user.email,
            'rede_social': rede_social,
            'tema': tema,
            'marketing_input_summary': marketing_input_summary,
            'timestamp': timezone.now().isoformat(),
            'source': 'pautas_gerar_form',
            'webhook_return_url': f'https://iamkt-femmeintegra.aisuites.com.br/pautas/webhook/n8n/?organization_id={organization.id}&user_id={request.user.id}&rede_social={rede_social}'
        }
        
        # Enviar para N8N
        webhook_url = settings.N8N_WEBHOOK_GERAR_PAUTA
        if not webhook_url:
            logger.error("N8N_WEBHOOK_GERAR_PAUTA não configurado")
            return JsonResponse({
                'success': False,
                'error': 'Webhook N8N não configurado'
            }, status=500)
        
        headers = {
            'Content-Type': 'application/json',
            'X-INTERNAL-TOKEN': settings.N8N_WEBHOOK_SECRET,
            'User-Agent': 'IAMKT-Pautas/1.0'
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=settings.N8N_WEBHOOK_TIMEOUT
        )
        
        if response.status_code == 200:
            logger.info(f"N8N response: {response.status_code} - {response.text}")
            return JsonResponse({
                'success': True,
                'message': 'Pauta enviada para processamento com sucesso!',
                'data': payload
            })
        else:
            logger.error(f"N8N error: {response.status_code} - {response.text}")
            return JsonResponse({
                'success': False,
                'error': f'Erro ao enviar para N8N: {response.status_code}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
        
    except requests.RequestException as e:
        logger.error(f"Erro de conexão com N8N: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro de conexão com o serviço de processamento'
        }, status=500)
        
    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)
