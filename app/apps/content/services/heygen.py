"""
Client HeyGen API v3 — geração de vídeo avatar (docs-aplicacao/skills/heygen).

Decisões herdadas da skill:
- v3 sempre; POST /v3/videos com avatar_id (LOOK) + voice_id + script explícitos.
- Webhook, nunca polling em worker (callback_url + callback_id na criação).
- Idempotency-Key determinística (uuid5) — retry do Celery replica a resposta
  original em vez de criar outro job cobrado.
- Erro é classificado pelo `code` do corpo, não pelo status HTTP.
"""
import logging
import uuid
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = 'https://api.heygen.com'
TIMEOUT = 30

# ~150 palavras/min em pt-BR; recalibrar contra video_duration real
WORDS_PER_SECOND_PTBR = 2.5

# US$/segundo de vídeo renderizado (tabela self-serve da skill).
# Avatar IV não tem preço público — assumimos a tarifa do V (conservador)
# até calibrar contra a fatura real.
PRICE_USD_PER_SECOND = {
    'avatar_iv': Decimal('0.0667'),
    'avatar_v': Decimal('0.0667'),
}

# Matriz de retry da skill: a classe do erro decide, não o HTTP.
RETRYABLE_CODES = {
    'rate_limit_exceeded', 'service_unavailable', 'internal_error',
    'voice_provider_error', 'gateway_timeout', 'resource_not_ready',
}
# Exigem ação externa (crédito/plano/consentimento): alertar operador, sem retry.
OPERATOR_ACTION_CODES = {
    'insufficient_credit', 'quota_exceeded', 'plan_upgrade_required',
    'avatar_consent_required', 'trial_limit_exceeded',
}


class HeygenError(Exception):
    """Erro estruturado da API HeyGen."""

    def __init__(self, code, message, http_status=None):
        self.code = code or 'unknown'
        self.http_status = http_status
        super().__init__(f'{self.code}: {message}')

    @property
    def retryable(self):
        return self.code in RETRYABLE_CODES

    @property
    def needs_operator(self):
        return self.code in OPERATOR_ACTION_CODES


class HeygenInProgress(Exception):
    """request_in_progress (409): mesma Idempotency-Key em voo. Espere e releia."""


def _headers(idempotency_key=None):
    api_key = getattr(settings, 'HEYGEN_API_KEY', '')
    if not api_key:
        raise HeygenError('no_api_key', 'HEYGEN_API_KEY não configurada no ambiente')
    headers = {'X-Api-Key': api_key, 'Content-Type': 'application/json'}
    if idempotency_key:
        headers['Idempotency-Key'] = idempotency_key
    return headers


def _request(method, path, *, json=None, params=None, idempotency_key=None):
    resp = requests.request(
        method, f'{BASE_URL}{path}',
        json=json, params=params,
        headers=_headers(idempotency_key),
        timeout=TIMEOUT,
    )
    if resp.ok:
        return resp.json().get('data', {})

    try:
        error = resp.json().get('error', {})
    except ValueError:
        error = {}
    code = error.get('code', '')
    message = error.get('message', resp.text[:300])
    if code == 'request_in_progress':
        raise HeygenInProgress(message)
    raise HeygenError(code, message, http_status=resp.status_code)


def make_idempotency_key(video):
    """uuid5 estável sobre org + pk + roteiro — retry nunca duplica cobrança."""
    seed = f'{video.organization_id}:{video.pk}:{video.script_text}'
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'iamkt-heygen:{seed}'))


def estimate_seconds(script, speed=1.0):
    return len(script.split()) / (WORDS_PER_SECOND_PTBR * speed)


def estimate_cost_usd(script, engine='avatar_iv', speed=1.0):
    rate = PRICE_USD_PER_SECOND.get(engine, PRICE_USD_PER_SECOND['avatar_iv'])
    return (rate * Decimal(str(estimate_seconds(script, speed)))).quantize(
        Decimal('0.000001'))


def create_avatar_video(video, idempotency_key):
    """
    POST /v3/videos para um VideoAvatar com avatar do catálogo. Retorna video_id.
    202 + callback via webhook; o worker NÃO espera o render.
    """
    avatar = video.avatar
    payload = {
        'type': 'avatar',
        'avatar_id': avatar.look_id,
        'voice_id': avatar.voice_id,
        'script': video.script_text,
        'aspect_ratio': 'auto',
        'resolution': '1080p',
        'voice_settings': {'locale': 'pt-BR', 'speed': 1.0},
        'title': f'iamkt {video.organization.slug} video#{video.pk}',
        'callback_id': f'{video.organization.slug}:{video.pk}',
    }
    if avatar.engine and avatar.engine != 'avatar_iv':
        payload['engine'] = {'type': avatar.engine}
    callback_url = getattr(settings, 'HEYGEN_CALLBACK_URL', '')
    if callback_url:
        payload['callback_url'] = callback_url

    data = _request('POST', '/v3/videos', json=payload,
                    idempotency_key=idempotency_key)
    video_id = data.get('video_id') or data.get('id')
    logger.info('[heygen] vídeo criado org=%s video=%s heygen_id=%s',
                video.organization.slug, video.pk, video_id)
    return video_id


def get_video(video_id):
    """GET /v3/videos/{id} — status, video_url, thumbnail_url, duration."""
    return _request('GET', f'/v3/videos/{video_id}')


def get_look(look_id):
    """GET /v3/avatars/looks/{id} — traz supported_api_engines."""
    return _request('GET', f'/v3/avatars/looks/{look_id}')


# --- Helpers do heygen_setup (equipe interna descobre IDs) ---

def _paginate(path, params=None, limit=50, max_pages=10):
    params = dict(params or {}, limit=limit)
    items = []
    for _ in range(max_pages):
        data = _request('GET', path, params=params)
        page = (data.get('items') or data.get('avatars') or data.get('looks')
                or data.get('voices') or [])
        items.extend(page)
        if not data.get('has_more'):
            break
        params['next_token'] = data.get('next_token')
    return items


def list_avatar_groups():
    return _paginate('/v3/avatars')


def list_looks(group_id=None):
    params = {'group_id': group_id} if group_id else None
    return _paginate('/v3/avatars/looks', params=params)


def list_voices(language='Portuguese'):
    return _paginate('/v3/voices', params={'language': language}, limit=100)
