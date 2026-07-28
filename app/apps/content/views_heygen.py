"""
Webhook HeyGen — verifica, deduplica, enfileira. Nada mais (prazo de 2xx é 10 s).
Referência: docs-aplicacao/skills/heygen/webhook-django.md
"""
import hashlib
import hmac
import json
import logging
import time

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

MAX_SKEW = 300  # segundos


def _valid_signature(body: bytes, signature: str) -> bool:
    """Aceita o secret vigente e o anterior (janela de rotação)."""
    secrets = (getattr(settings, 'HEYGEN_WEBHOOK_SECRET', ''),
               getattr(settings, 'HEYGEN_WEBHOOK_SECRET_ANTERIOR', ''))
    for secret in filter(None, secrets):
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected):
            return True
    return False


@csrf_exempt
@require_POST
def heygen_webhook(request):
    signature = request.headers.get('Heygen-Signature', '')
    timestamp = request.headers.get('Heygen-Timestamp', '')
    event_id = request.headers.get('Heygen-Event-Id', '')

    if not (signature and timestamp and event_id):
        # diagnóstico: nomes dos headers recebidos (sem valores — podem ter secret)
        logger.warning('[heygen webhook] entrega sem headers de assinatura; '
                       'headers=%s ua=%s',
                       sorted(request.headers.keys()),
                       request.headers.get('User-Agent', '?'))
        return HttpResponseBadRequest('headers ausentes')

    try:
        if abs(time.time() - int(timestamp)) > MAX_SKEW:
            return HttpResponseBadRequest('timestamp velho')
    except ValueError:
        return HttpResponseBadRequest('timestamp inválido')

    body = request.body  # bytes crus, antes de qualquer parse
    if not _valid_signature(body, signature):
        logger.warning('[heygen webhook] assinatura inválida (event %s)', event_id)
        return HttpResponseForbidden('assinatura inválida')

    # Dedup atômico: defesa primária contra replay é o Event-Id
    from apps.content.models import HeygenWebhookEvent
    _, new = HeygenWebhookEvent.objects.get_or_create(event_id=event_id)
    if not new:
        return HttpResponse(status=200)  # 2xx para parar o retry de 24h

    try:
        event = json.loads(body)
    except ValueError:
        return HttpResponseBadRequest('json inválido')

    from apps.content.tasks_heygen import process_heygen_event_task
    process_heygen_event_task.delay(event_id, event)
    return HttpResponse(status=200)
