"""
API de cadastro externo — chamada server-to-server pelo site iamkt.com.br.

Endpoints:
- POST /api/signup/            -> cria conta pendente (org + usuário admin)
- POST /api/signup/confirm-payment/ -> libera a conta após confirmação de pagamento

Autenticação (mesmo padrão dos webhooks N8N):
- Token interno no header X-INTERNAL-TOKEN (settings.SITE_WEBHOOK_SECRET)
- Whitelist de IP (settings.SITE_ALLOWED_IPS)
- Rate limiting por IP (settings.SITE_RATE_LIMIT_PER_IP)
"""
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.signup_service import (
    create_pending_signup,
    confirm_payment,
    SignupError,
)
from .models import Organization
from .emails import send_registration_confirmation, send_registration_notification

logger = logging.getLogger(__name__)


def _authenticate_site_request(request, rate_key):
    """
    Valida token, IP e rate limit de uma requisição vinda do site.
    Retorna um JsonResponse de erro quando rejeitada, ou None quando OK.
    """
    # CAMADA 1: Token interno
    token = request.headers.get('X-INTERNAL-TOKEN')
    if not settings.SITE_WEBHOOK_SECRET or token != settings.SITE_WEBHOOK_SECRET:
        logger.warning(f"❌ [SIGNUP_API] Token inválido do IP: {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    # CAMADA 2: Whitelist de IP (Cloudflare-aware)
    client_ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR')
    allowed_ips = [ip.strip() for ip in (settings.SITE_ALLOWED_IPS or '').split(',') if ip.strip()]
    if allowed_ips and client_ip not in allowed_ips:
        logger.warning(f"❌ [SIGNUP_API] IP não autorizado: {client_ip}")
        return JsonResponse({'success': False, 'error': 'Unauthorized IP'}, status=403)

    # CAMADA 3: Rate limit por IP
    cache_key = f"{rate_key}_{client_ip}"
    current = cache.get(cache_key, 0)
    max_requests = int(settings.SITE_RATE_LIMIT_PER_IP.split('/')[0])
    if current >= max_requests:
        logger.warning(f"⚠️ [SIGNUP_API] Rate limit excedido para IP {client_ip}")
        return JsonResponse({'success': False, 'error': 'Rate limit exceeded'}, status=429)
    cache.set(cache_key, current + 1, 60)

    return None


def _parse_json(request):
    try:
        return json.loads(request.body or b'{}'), None
    except json.JSONDecodeError:
        return None, JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def external_signup(request):
    """
    Cria uma conta pendente a partir dos dados preenchidos no site.

    Body esperado (JSON):
    {
        "full_name": "Maria Silva",
        "email": "maria@empresa.com",
        "company_name": "Empresa LTDA",
        "cpf": "123.456.789-09",
        "phone": "+5511999999999",   # opcional
        "password": "SenhaForte123!",
        "plan": "starter"             # "starter" ou "pro"
    }
    """
    auth_error = _authenticate_site_request(request, 'signup_api_create')
    if auth_error:
        return auth_error

    data, parse_error = _parse_json(request)
    if parse_error:
        return parse_error

    # Campos obrigatórios
    required = ['full_name', 'email', 'company_name', 'cpf', 'password', 'plan']
    missing = [f for f in required if not str(data.get(f, '')).strip()]
    if missing:
        return JsonResponse({
            'success': False,
            'error': f"Campos obrigatórios ausentes: {', '.join(missing)}",
        }, status=400)

    plan = str(data.get('plan', '')).strip().lower()
    if plan not in ('starter', 'pro'):
        return JsonResponse({
            'success': False,
            'error': "Plano inválido. Use 'starter' ou 'pro'.",
        }, status=400)

    try:
        organization, user = create_pending_signup(
            full_name=data.get('full_name', ''),
            email=data.get('email', ''),
            company_name=data.get('company_name', ''),
            password=data.get('password', ''),
            cpf=data.get('cpf', ''),
            phone=data.get('phone', ''),
            plan=plan,
        )
    except SignupError as e:
        # 409 para duplicidade, 400 para o resto
        status = 409 if e.code in ('email_exists', 'cpf_exists') else 400
        return JsonResponse({'success': False, 'error': e.message, 'code': e.code}, status=status)
    except Exception as e:
        logger.exception(f"❌ [SIGNUP_API] Erro inesperado ao criar conta: {e}")
        return JsonResponse({'success': False, 'error': 'Erro ao processar cadastro.'}, status=500)

    # Notificações (não bloqueiam o cadastro em caso de falha de email)
    try:
        send_registration_confirmation(user, organization)
        send_registration_notification(user, organization)
    except Exception as e:
        logger.warning(f"⚠️ [SIGNUP_API] Falha ao enviar emails de cadastro para {user.email}: {e}")

    return JsonResponse({
        'success': True,
        'message': 'Cadastro criado. Aguardando confirmação de pagamento.',
        'organization_id': organization.id,
        'user_id': user.id,
        'status': 'pending',
    }, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_payment_view(request):
    """
    Libera a conta após confirmação de pagamento no site (Mercado Pago).

    Body esperado (JSON):
    {
        "org_id": 123,
        "plan": "pro",                 # opcional; default = plano do cadastro
        "payment_ref": "MP-1234567890" # opcional; ID do pagamento no Mercado Pago
    }
    """
    auth_error = _authenticate_site_request(request, 'signup_api_confirm')
    if auth_error:
        return auth_error

    data, parse_error = _parse_json(request)
    if parse_error:
        return parse_error

    org_id = data.get('org_id')
    if not org_id:
        return JsonResponse({'success': False, 'error': 'org_id é obrigatório.'}, status=400)

    try:
        organization, activated = confirm_payment(
            org_id=org_id,
            plan=str(data.get('plan', '')).strip().lower(),
            payment_ref=data.get('payment_ref', ''),
        )
    except Organization.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Organização não encontrada.'}, status=404)
    except Exception as e:
        logger.exception(f"❌ [SIGNUP_API] Erro ao confirmar pagamento da org {org_id}: {e}")
        return JsonResponse({'success': False, 'error': 'Erro ao confirmar pagamento.'}, status=500)

    return JsonResponse({
        'success': True,
        'message': 'Conta liberada.' if activated else 'Conta já estava ativa.',
        'organization_id': organization.id,
        'activated': activated,
        'plan_type': organization.plan_type,
        'is_active': organization.is_active,
    })
