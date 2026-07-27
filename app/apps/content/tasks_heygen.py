"""
Tasks Celery da integração HeyGen (Vídeos Avatar).

Fluxo canônico (skill heygen-django):
  view cria VideoAvatar(pending) → create_heygen_video_task (202, grava video_id,
  worker volta ao pool) → webhook assinado → process_heygen_event_task (baixa MP4
  pré-assinado p/ storage do tenant, fecha duração/custo, notifica solicitante).
"""
import logging
from decimal import Decimal

import requests
from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)


def _status(code, label=None):
    from apps.content.models import VideoAvatarStatus
    obj, _ = VideoAvatarStatus.objects.get_or_create(
        code=code, defaults={'label': label or code.title()})
    return obj


@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=600)
def create_heygen_video_task(self, video_id):
    """Cria o job na HeyGen. Retry só para erros retentáveis da matriz."""
    from apps.content.models import VideoAvatar
    from apps.content.services import heygen

    video = VideoAvatar.objects.select_related(
        'organization', 'avatar', 'look').get(pk=video_id)
    if video.heygen_video_id:
        logger.info('[heygen] vídeo %s já tem heygen_video_id, ignorando', video_id)
        return video.heygen_video_id
    if not video.avatar or not video.look:
        video.status = _status('failed', 'Falhou')
        video.error_code = 'no_avatar'
        video.error_message = 'Vídeo sem apresentador/look do catálogo associado.'
        video.save(update_fields=['status', 'error_code', 'error_message'])
        return None

    key = video.idempotency_key or heygen.make_idempotency_key(video)
    try:
        heygen_id = heygen.create_avatar_video(video, key)
    except heygen.HeygenInProgress as exc:
        # mesma chave em voo: a resposta original chega pelo webhook
        logger.info('[heygen] request_in_progress para vídeo %s: %s', video_id, exc)
        return None
    except heygen.HeygenError as exc:
        if exc.retryable:
            raise self.retry(exc=exc)
        video.status = _status('failed', 'Falhou')
        video.error_code = exc.code
        video.error_message = str(exc)
        video.save(update_fields=['status', 'error_code', 'error_message'])
        if exc.needs_operator:
            logger.error('[heygen] AÇÃO DO OPERADOR necessária (%s) — vídeo %s',
                         exc.code, video_id)
        return None

    video.heygen_video_id = heygen_id or ''
    video.idempotency_key = key
    video.estimated_duration = heygen.estimate_seconds(video.script_text)
    video.status = _status('processing', 'Processando')
    video.save(update_fields=['heygen_video_id', 'idempotency_key',
                              'estimated_duration', 'status'])
    return heygen_id


@shared_task(bind=True, max_retries=5, autoretry_for=(requests.RequestException,),
             retry_backoff=True)
def process_heygen_event_task(self, event_id, event):
    """Processa avatar_video.success/.fail já verificado e deduplicado na view."""
    from apps.content.models import VideoAvatar
    from apps.content.services import heygen
    from apps.core.services.ai_usage import record_ai_event

    event_type = event.get('event_type', '')
    data = event.get('event_data', {})
    heygen_id = data.get('video_id', '')
    org_slug, _, pk = (data.get('callback_id') or '').partition(':')

    qs = VideoAvatar.objects.select_related('organization', 'avatar', 'created_by')
    video = None
    if heygen_id:
        video = qs.filter(heygen_video_id=heygen_id).first()
    if video is None and pk.isdigit():
        video = qs.filter(pk=int(pk), organization__slug=org_slug).first()
    if video is None:
        logger.error('[heygen] evento %s sem VideoAvatar correspondente '
                     '(video_id=%s callback_id=%s)', event_id, heygen_id,
                     data.get('callback_id'))
        return

    if event_type.endswith('.fail'):
        video.status = _status('failed', 'Falhou')
        video.error_code = 'render_failed'
        video.error_message = data.get('msg', 'sem mensagem')
        video.save(update_fields=['status', 'error_code', 'error_message'])
        return

    # URL pré-assinada expira: baixa AGORA para o storage do tenant
    url = data.get('url')
    if url and not video.video_file:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        video.video_file.save(f'heygen_{video.pk}.mp4',
                              ContentFile(resp.content), save=False)

    # duração real (base de cobrança) e thumbnail vêm do GET
    duration = 0
    try:
        detail = heygen.get_video(video.heygen_video_id or heygen_id)
        duration = float(detail.get('duration') or 0)
        thumb_url = detail.get('thumbnail_url')
        if thumb_url and not video.video_thumbnail:
            t = requests.get(thumb_url, timeout=60)
            if t.ok:
                video.video_thumbnail.save(f'heygen_{video.pk}.jpg',
                                           ContentFile(t.content), save=False)
    except heygen.HeygenError:
        logger.exception('[heygen] falha ao ler detalhe do vídeo %s', video.pk)

    engine = video.avatar.engine if video.avatar else 'avatar_iv'
    rate = heygen.PRICE_USD_PER_SECOND.get(engine, Decimal('0.0667'))
    cost_usd = (rate * Decimal(str(duration))).quantize(Decimal('0.000001'))

    video.video_duration = duration
    video.cost_usd = cost_usd
    video.status = _status('ready', 'Pronto')
    video.delivered_at = timezone.now()
    video.save()

    record_ai_event(
        video.organization,
        step='heygen_render',
        model=f'heygen-{engine}',
        usage_dict={'cost_usd': cost_usd},
        purpose=f'video_avatar #{video.pk} ({duration:.1f}s)',
        source='videos_avatar',
    )

    from apps.core.emails import send_video_avatar_ready
    send_video_avatar_ready(video)
