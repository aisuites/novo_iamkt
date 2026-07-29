"""
URLs do app content
"""
from django.urls import path
from . import views, views_videos, views_heygen

app_name = 'content'

urlpatterns = [
    path('pautas/', views.pautas_list, name='pautas'),
    path('pautas/nova/', views.pauta_create, name='pauta_create'),
    # NOTA: Rotas de posts movidas para apps.posts.urls
    path('trends/', views.trends_list, name='trends'),

    # Vídeos Avatar (HeyGen) — gate: videos_avatar_enabled
    path('videos-avatar/', views_videos.videos_list, name='videos_avatar'),
    path('videos-avatar/novo/', views_videos.video_create, name='video_avatar_create'),
    path('videos-avatar/<int:pk>/', views_videos.video_detail, name='video_avatar_detail'),
    path('videos-avatar/<int:pk>/status/', views_videos.video_status, name='video_avatar_status'),
    path('videos-avatar/apresentadores/', views_videos.presenters_list, name='heygen_presenters'),
    path('videos-avatar/apresentadores/novo/', views_videos.presenter_create, name='heygen_presenter_create'),
    path('videos-avatar/apresentadores/status/', views_videos.presenters_status, name='heygen_presenters_status'),
    path('videos-avatar/apresentadores/<int:pk>/looks/novo/', views_videos.presenter_look_create, name='heygen_look_create'),
    path('webhooks/heygen/', views_heygen.heygen_webhook, name='heygen_webhook'),
]
