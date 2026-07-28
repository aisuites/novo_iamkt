"""
Páginas do módulo Vídeos Avatar (gate: Organization.videos_avatar_enabled).

Fluxo: formulário (avatar do catálogo + script) → VideoAvatar(pending) →
task HeyGen → página de detalhe acompanha por polling do NAVEGADOR
(polling em worker é proibido — skill heygen-django).
"""
import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import require_organization

logger = logging.getLogger(__name__)

SCRIPT_MAX_CHARS = 500  # limite do modelo (HeyGen aceita 5.000)


def require_videos_avatar(view_func):
    """Org precisa da flag videos_avatar_enabled; staff sempre passa."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        org = request.organization
        if not (org.videos_avatar_enabled or request.user.is_staff):
            messages.error(request, 'Sua organização não tem o módulo de '
                                    'Vídeos Avatar habilitado.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@require_organization
@require_videos_avatar
def videos_list(request):
    from apps.content.models import VideoAvatar
    qs = VideoAvatar.objects.for_request(request).select_related(
        'status', 'avatar', 'look', 'created_by').order_by('-created_at')
    paginator = Paginator(qs, 12)
    videos = paginator.get_page(request.GET.get('page'))
    return render(request, 'content/videos_avatar_list.html', {'videos': videos})


@login_required
@require_organization
@require_videos_avatar
def video_create(request):
    from apps.content.models import HeygenLook, VideoAvatar, VideoAvatarStatus

    # Cards = LOOKS ativos de apresentadores ativos da org, agrupados por
    # apresentador no template. Catálogo vazio → o template mostra o aviso
    # (o app não renderiza django.messages nas páginas internas)
    looks = (HeygenLook.objects
             .filter(avatar__organization=request.organization,
                     avatar__is_active=True, is_active=True)
             .select_related('avatar')
             .order_by('avatar__name', '-is_default', 'name'))

    SPEED_CHOICES = {'0.85': 0.85, '1.0': 1.0, '1.15': 1.15}
    ASPECT_CHOICES = ('auto', '9:16', '16:9', '1:1')

    form_error = None
    if request.method == 'POST' and looks.exists():
        look_pk = request.POST.get('look')
        script = (request.POST.get('script_text') or '').strip()
        action = (request.POST.get('avatar_action') or '').strip()
        speed = SPEED_CHOICES.get(request.POST.get('voice_speed', '1.0'), 1.0)
        aspect = request.POST.get('aspect_ratio', 'auto')
        if aspect not in ASPECT_CHOICES:
            aspect = 'auto'

        look = looks.filter(pk=look_pk).first()
        if look is None:
            form_error = 'Escolha um visual do apresentador.'
        elif not script:
            form_error = 'Escreva o texto que o apresentador vai falar.'
        elif len(script) > SCRIPT_MAX_CHARS:
            form_error = f'O texto passou de {SCRIPT_MAX_CHARS} caracteres.'
        else:
            status, _ = VideoAvatarStatus.objects.get_or_create(
                code='pending', defaults={'label': 'Na fila'})
            video = VideoAvatar.objects.create(
                organization=request.organization,
                avatar=look.avatar,
                look=look,
                created_by=request.user,
                script_text=script,
                avatar_action=action,
                voice_speed=speed,
                aspect_ratio=aspect,
                status=status,
            )
            from apps.core.emails import send_video_avatar_received
            send_video_avatar_received(video)

            from apps.content.tasks_heygen import create_heygen_video_task
            create_heygen_video_task.delay(video.pk)

            return redirect('content:video_avatar_detail', pk=video.pk)

    context = {
        'looks': looks,
        'script_max': SCRIPT_MAX_CHARS,
        'form_error': form_error,
        'form_data': request.POST if request.method == 'POST' else {},
        'speed_options': [('0.85', '🐢 Calma'), ('1.0', 'Normal'),
                          ('1.15', '⚡ Acelerada')],
        'aspect_options': [('auto', 'Auto'), ('9:16', '9:16'),
                           ('16:9', '16:9'), ('1:1', '1:1')],
    }
    return render(request, 'content/videos_avatar_form.html', context)


@login_required
@require_organization
@require_videos_avatar
def video_detail(request, pk):
    from apps.content.models import VideoAvatar
    video = get_object_or_404(
        VideoAvatar.objects.for_request(request).select_related(
            'status', 'avatar', 'look', 'created_by'),
        pk=pk,
    )
    return render(request, 'content/videos_avatar_detail.html', {'video': video})


@login_required
@require_organization
@require_videos_avatar
def video_status(request, pk):
    """JSON consumido pelo polling da página de detalhe."""
    from apps.content.models import VideoAvatar
    video = get_object_or_404(VideoAvatar.objects.for_request(request)
                              .select_related('status'), pk=pk)
    return JsonResponse({
        'status': video.status.code,
        'status_label': video.status.label,
        'video_url': video.video_file.url if video.video_file else None,
        'thumbnail_url': (video.video_thumbnail.url
                          if video.video_thumbnail else None),
        'duration': video.video_duration,
        'error': video.error_message or None,
    })


FOOTAGE_MAX_BYTES = 100 * 1024 * 1024  # limite de vídeo de entrada da HeyGen
FOOTAGE_TYPES = ('video/mp4', 'video/webm', 'video/quicktime')


@login_required
@require_organization
@require_videos_avatar
def presenters_list(request):
    """Apresentadores da org com status de treino (página mobile-first)."""
    from apps.content.models import HeygenAvatar
    presenters = (HeygenAvatar.objects.for_request(request)
                  .prefetch_related('looks').order_by('-created_at'))
    return render(request, 'content/heygen_presenters.html',
                  {'presenters': presenters})


@login_required
@require_organization
@require_videos_avatar
def presenter_create(request):
    """Cria digital twin: grava pela câmera ou envia arquivo de vídeo."""
    from apps.content.models import HeygenAvatar

    form_error = None
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        footage = request.FILES.get('footage')

        if not name:
            form_error = 'Dê um nome ao apresentador.'
        elif footage is None:
            form_error = 'Grave ou envie o vídeo de treino.'
        elif footage.size > FOOTAGE_MAX_BYTES:
            form_error = ('O vídeo passou de 100 MB — grave um pouco mais '
                          'curto ou reduza a qualidade.')
        elif footage.content_type not in FOOTAGE_TYPES:
            form_error = 'Formato não suportado — envie MP4, WebM ou MOV.'
        else:
            presenter = HeygenAvatar.objects.create(
                organization=request.organization,
                name=name,
                status='pending',
                source_video=footage,
                created_by=request.user,
                is_active=False,  # ativa quando o treino conclui
            )
            from apps.content.tasks_heygen import create_presenter_task
            create_presenter_task.delay(presenter.pk)
            return redirect('content:heygen_presenters')

    return render(request, 'content/heygen_presenter_form.html',
                  {'form_error': form_error,
                   'form_data': request.POST if request.method == 'POST' else {}})


@login_required
@require_organization
@require_videos_avatar
def presenters_status(request):
    """JSON p/ polling da lista de apresentadores (treinos em andamento)."""
    from apps.content.models import HeygenAvatar
    data = [{'id': p.pk, 'status': p.status,
             'status_label': p.get_status_display(),
             'looks': p.looks.filter(is_active=True).count()}
            for p in HeygenAvatar.objects.for_request(request)]
    return JsonResponse({'presenters': data})
