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


def _refund_credit(record, field):
    """Falha definitiva devolve o crédito — só se este registro consumiu um
    (credit_consumed), e desmarca para nunca devolver duas vezes."""
    if not getattr(record, 'credit_consumed', False):
        return
    from django.db.models import F
    from apps.core.models import Organization
    Organization.objects.filter(pk=record.organization_id).update(
        **{field: F(field) + 1})
    record.credit_consumed = False
    record.save(update_fields=['credit_consumed'])
    logger.info('[credits] devolvido 1 %s para org %s', field, record.organization_id)


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
        video.error_message = 'Vídeo sem avatar/look do catálogo associado.'
        video.save(update_fields=['status', 'error_code', 'error_message'])
        _refund_credit(video, 'video_avatar_credits')
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
        _refund_credit(video, 'video_avatar_credits')
        if exc.needs_operator:
            logger.error('[heygen] AÇÃO DO OPERADOR necessária (%s) — vídeo %s',
                         exc.code, video_id)
        return None

    video.heygen_video_id = heygen_id or ''
    video.idempotency_key = key
    video.estimated_duration = heygen.estimate_seconds(
        video.script_text, video.voice_speed or 1.0)
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
        _refund_credit(video, 'video_avatar_credits')
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


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def create_presenter_task(self, avatar_id):
    """
    Cria o digital twin na HeyGen a partir do footage do HeygenAvatar:
    upload do asset → POST /v3/avatars → agenda o poll de treino.
    (Treino não tem webhook; poll com backoff é o caminho aceito aqui.)
    """
    from apps.content.models import HeygenAvatar
    from apps.content.services import heygen

    avatar = HeygenAvatar.objects.get(pk=avatar_id)
    if avatar.group_id:
        logger.info('[heygen twin] %s já tem group_id, ignorando', avatar_id)
        return avatar.group_id
    if not avatar.source_video:
        avatar.status = 'failed'
        avatar.error_message = 'Sem vídeo de origem.'
        avatar.save(update_fields=['status', 'error_message'])
        _refund_credit(avatar, 'avatar_creation_credits')
        return None

    try:
        # URL assinada do nosso S3 (a HeyGen baixa na hora — sem asset upload)
        footage_url = avatar.source_video.url
        group_id, look_id = heygen.create_digital_twin(avatar.name, footage_url)
        if not group_id and not look_id:
            raise heygen.HeygenError('twin_create_failed',
                                     'API não retornou group/look')
    except heygen.HeygenError as exc:
        if exc.retryable:
            raise self.retry(exc=exc)
        avatar.status = 'failed'
        avatar.error_message = str(exc)
        avatar.save(update_fields=['status', 'error_message'])
        _refund_credit(avatar, 'avatar_creation_credits')
        logger.error('[heygen twin] falha ao criar %s: %s', avatar_id, exc)
        return None

    avatar.group_id = group_id
    avatar.status = 'training'
    avatar.save(update_fields=['group_id', 'status'])
    poll_presenter_training_task.apply_async(args=[avatar_id], countdown=120)
    return group_id


@shared_task(bind=True, max_retries=90)
def poll_presenter_training_task(self, avatar_id):
    """
    Acompanha o treino do twin (sem webhook na HeyGen p/ isso): checa a cada
    2 min por até ~3h. Ao concluir: captura a voz automática do look
    (default_voice_id), ativa o look e marca o apresentador como pronto.
    """
    from django.utils import timezone

    from apps.content.models import HeygenAvatar
    from apps.content.services import heygen

    avatar = HeygenAvatar.objects.get(pk=avatar_id)
    if avatar.status != 'training':
        return avatar.status

    try:
        looks = heygen.list_looks(avatar.group_id)
    except heygen.HeygenError as exc:
        logger.warning('[heygen twin] poll %s falhou: %s', avatar_id, exc)
        looks = []

    completed = [l for l in looks if l.get('status') == 'completed']
    failed = [l for l in looks if l.get('status') == 'failed']

    if completed:
        first = completed[0]
        if not avatar.voice_id:
            try:
                detail = heygen.get_look(first['id'])
                avatar.voice_id = detail.get('default_voice_id', '') or ''
            except heygen.HeygenError:
                logger.exception('[heygen twin] detalhe do look falhou')
        avatar.status = 'ready'
        avatar.trained_at = timezone.now()
        avatar.is_active = True
        avatar.save(update_fields=['voice_id', 'status', 'trained_at', 'is_active'])
        try:
            heygen.sync_group_looks(avatar, activate_new=True)
            look0 = avatar.looks.filter(is_active=True).first()
            if look0 and not avatar.looks.filter(is_default=True).exists():
                look0.is_default = True
                look0.save(update_fields=['is_default'])
        except heygen.HeygenError:
            logger.exception('[heygen twin] sync pós-treino falhou')
        logger.info('[heygen twin] apresentador %s PRONTO (voz=%s)',
                    avatar_id, avatar.voice_id or '?')
        return 'ready'

    if failed and not completed and len(failed) == len(looks) and looks:
        avatar.status = 'failed'
        avatar.error_message = 'Treino do avatar falhou na HeyGen.'
        avatar.save(update_fields=['status', 'error_message'])
        _refund_credit(avatar, 'avatar_creation_credits')
        return 'failed'

    raise self.retry(countdown=120)
