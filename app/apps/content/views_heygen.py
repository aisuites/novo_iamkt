"""
Webhook HeyGen — verifica, deduplica, enfileira. Nada mais (prazo de 2xx é 10 s).

FORMATO REAL observado em 2026-07-28 (difere da doc da skill): a HeyGen
entrega com um único header `Signature` (HMAC do corpo cru) e SEM
Heygen-Timestamp/Heygen-Event-Id — o event_id vem no CORPO do JSON.
Aceitamos ambos os formatos; dedup é pelo event_id do corpo.
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _candidate_digests(body: bytes):
    """HMACs possíveis do corpo cru, nos secrets vigente e anterior."""
    secrets = (getattr(settings, 'HEYGEN_WEBHOOK_SECRET', ''),
               getattr(settings, 'HEYGEN_WEBHOOK_SECRET_ANTERIOR', ''))
    for secret in filter(None, secrets):
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        yield mac.hexdigest()
        import base64
        yield base64.b64encode(mac.digest()).decode()


def _valid_signature(body: bytes, signature: str) -> bool:
    signature = signature.strip()
    # variantes comuns: hex puro, base64, prefixo "sha256="
    if signature.startswith('sha256='):
        signature = signature[7:]
    return any(hmac.compare_digest(signature, expected)
               for expected in _candidate_digests(body))


@csrf_exempt
@require_POST
def heygen_webhook(request):
    signature = (request.headers.get('Signature', '')
                 or request.headers.get('Heygen-Signature', ''))
    if not signature:
        logger.warning('[heygen webhook] entrega SEM assinatura; headers=%s ua=%s',
                       sorted(request.headers.keys()),
                       request.headers.get('User-Agent', '?'))
        return HttpResponseBadRequest('sem assinatura')

    body = request.body  # bytes crus, antes de qualquer parse
    if not _valid_signature(body, signature):
        # diagnóstico sem vazar o valor: formato/tamanho apenas
        logger.warning('[heygen webhook] assinatura NÃO confere '
                       '(len=%d, hex?=%s, prefixo_sha256?=%s)',
                       len(signature),
                       all(c in '0123456789abcdef' for c in signature.lower()[:16]),
                       signature.startswith('sha256='))
        return HttpResponseForbidden('assinatura inválida')

    try:
        event = json.loads(body)
    except ValueError:
        return HttpResponseBadRequest('json inválido')

    # event_id vem no corpo (formato real); headers como fallback
    event_id = (event.get('event_id')
                or request.headers.get('Heygen-Event-Id', ''))
    if not event_id:
        return HttpResponseBadRequest('sem event_id')

    # Dedup atômico: defesa primária contra replay
    from apps.content.models import HeygenWebhookEvent
    _, new = HeygenWebhookEvent.objects.get_or_create(event_id=event_id)
    if not new:
        return HttpResponse(status=200)  # 2xx para parar o retry de 24h

    from apps.content.tasks_heygen import process_heygen_event_task
    process_heygen_event_task.delay(event_id, event)
    return HttpResponse(status=200)
