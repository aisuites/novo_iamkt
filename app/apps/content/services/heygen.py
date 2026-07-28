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
    POST /v3/videos para um VideoAvatar com look do catálogo. Retorna video_id.
    202 + callback via webhook; o worker NÃO espera o render.
    """
    avatar = video.avatar
    speed = min(2.0, max(0.5, float(video.voice_speed or 1.0)))
    payload = {
        'type': 'avatar',
        'avatar_id': video.look.look_id,
        'voice_id': avatar.voice_id,
        'script': video.script_text,
        'aspect_ratio': video.aspect_ratio or 'auto',
        'resolution': '1080p',
        'voice_settings': {'locale': 'pt-BR', 'speed': speed},
        'title': f'iamkt {video.organization.slug} video#{video.pk}',
        'callback_id': f'{video.organization.slug}:{video.pk}',
    }
    if avatar.engine and avatar.engine != 'avatar_iv':
        payload['engine'] = {'type': avatar.engine}
    elif video.avatar_action:
        # motion_prompt é exclusivo do Avatar IV (a API rejeita no avatar_v)
        payload['motion_prompt'] = video.avatar_action
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
        if isinstance(data, list):  # alguns endpoints devolvem data como lista
            items.extend(data)
            break
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


ASSET_SIMPLE_UPLOAD_MAX = 32 * 1024 * 1024  # acima disso, direct upload


def upload_asset(fileobj, filename, content_type='video/mp4'):
    """
    Sobe um arquivo para a HeyGen e retorna o asset_id.
    ≤32MB: POST /v3/assets direto. Maior: fluxo direct-upload
    (init → PUT → complete).
    """
    data = fileobj.read()
    size = len(data)

    if size <= ASSET_SIMPLE_UPLOAD_MAX:
        resp = requests.post(
            f'{BASE_URL}/v3/assets',
            files={'file': (filename, data, content_type)},
            headers={'X-Api-Key': getattr(settings, 'HEYGEN_API_KEY', '')},
            timeout=300,
        )
        if not resp.ok:
            try:
                err = resp.json().get('error', {})
            except ValueError:
                err = {}
            raise HeygenError(err.get('code', ''), err.get('message', resp.text[:300]),
                              http_status=resp.status_code)
        body = resp.json().get('data', {})
        return body.get('asset_id') or body.get('id')

    # direct upload (arquivos grandes)
    init = _request('POST', '/v3/assets/direct-uploads',
                    json={'filename': filename, 'content_type': content_type,
                          'size': size})
    upload_url = init.get('upload_url') or init.get('url')
    asset_id = init.get('asset_id') or init.get('id')
    if not upload_url or not asset_id:
        raise HeygenError('direct_upload_init_failed',
                          f'resposta inesperada do init: {list(init.keys())}')
    put = requests.put(upload_url, data=data,
                       headers={'Content-Type': content_type}, timeout=600)
    put.raise_for_status()
    # complete pode devolver resource_not_ready enquanto o PUT aterrissa — retry
    for _ in range(5):
        try:
            _request('POST', f'/v3/assets/{asset_id}/complete')
            break
        except HeygenError as exc:
            if exc.code != 'resource_not_ready':
                raise
            import time
            time.sleep(3)
    return asset_id


def create_digital_twin(name, asset_id):
    """
    POST /v3/avatars type=digital_twin a partir do footage. Treino é
    assíncrono. Retorna (group_id, look_id) — ids podem vir em formatos
    diferentes conforme a versão da API, por isso o parse defensivo.
    """
    data = _request('POST', '/v3/avatars',
                    json={'type': 'digital_twin', 'name': name,
                          'asset_id': asset_id})
    group = data.get('avatar_group') or {}
    item = data.get('avatar_item') or {}
    group_id = (group.get('id') or data.get('group_id')
                or data.get('avatar_group_id') or '')
    look_id = item.get('id') or data.get('avatar_id') or data.get('id') or ''
    if not group_id and look_id:
        # fallback: o detalhe do look informa o grupo
        try:
            group_id = get_look(look_id).get('group_id', '')
        except HeygenError:
            pass
    logger.info('[heygen] digital twin criado name=%s group=%s look=%s',
                name, group_id, look_id)
    return group_id, look_id


def sync_group_looks(avatar, activate_new=False):
    """
    Sincroniza os looks do avatar group da HeyGen para o catálogo local.

    - Look novo: criado INATIVO por padrão (curadoria da equipe no admin),
      com preview baixado da HeyGen.
    - Look que sumiu do grupo: desativado (nunca deletado — vídeos antigos
      referenciam).
    Retorna dict com contadores.
    """
    from django.core.files.base import ContentFile

    from apps.content.models import HeygenLook

    if not avatar.group_id:
        raise HeygenError('no_group_id',
                          f'Apresentador "{avatar.name}" sem group_id configurado')

    remote = list_looks(avatar.group_id)
    remote_ids = set()
    created = updated = 0

    for item in remote:
        look_id = item.get('id')
        if not look_id or item.get('status') != 'completed':
            continue  # look ainda treinando não entra no catálogo
        remote_ids.add(look_id)
        look, was_created = HeygenLook.objects.get_or_create(
            avatar=avatar, look_id=look_id,
            defaults={
                'name': item.get('name') or look_id,
                'avatar_type': item.get('avatar_type', ''),
                'is_active': activate_new,
            },
        )
        if was_created:
            created += 1
            preview_url = item.get('preview_image_url')
            if preview_url:
                try:
                    resp = requests.get(preview_url, timeout=60)
                    if resp.ok:
                        look.preview_image.save(f'{look_id}.jpg',
                                                ContentFile(resp.content))
                except requests.RequestException:
                    logger.warning('[heygen sync] preview falhou p/ look %s', look_id)
        else:
            new_type = item.get('avatar_type', '')
            if new_type and look.avatar_type != new_type:
                look.avatar_type = new_type
                look.save(update_fields=['avatar_type'])
                updated += 1

    gone = avatar.looks.filter(is_active=True).exclude(look_id__in=remote_ids)
    deactivated = gone.update(is_active=False)

    logger.info('[heygen sync] %s: %d criados, %d atualizados, %d desativados',
                avatar.name, created, updated, deactivated)
    return {'created': created, 'updated': updated,
            'deactivated': deactivated, 'remote_total': len(remote_ids)}
