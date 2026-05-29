from django.urls import path
from . import views, views_upload, views_gerar, views_gerar_local, views_actions, views_webhook, views_api, views_overlay

app_name = 'posts'

urlpatterns = [
    path('', views.posts_list, name='list'),
    
    # API
    path('api/formatos/', views_api.get_post_formats, name='api_formatos'),
    path('api/org-assets/', views_api.get_org_assets, name='api_org_assets'),
    
    # Gerar Post
    path('gerar/', views_gerar.gerar_post, name='gerar'),

    # Pipeline interna (Celery + Claude + Gemini) — homol/dev apenas
    path('gerar-local/', views_gerar_local.gerar_post_local, name='gerar_local'),
    
    # N8N Webhook - Receber post processado
    path('webhook/callback/', views_webhook.n8n_post_callback, name='n8n_post_callback'),
    
    # Preview de Imagens
    path('preview-url/', views_upload.get_preview_url, name='preview_url'),
    
    # Upload S3 - Imagens de Referência
    path('reference/upload-url/', views_upload.generate_reference_upload_url, name='reference_upload_url'),
    path('reference/create/', views_upload.create_reference_image, name='reference_create'),
    
    # Ações de Posts
    path('<int:post_id>/reject/', views_actions.reject_post, name='reject'),
    path('<int:post_id>/approve/', views_actions.approve_post, name='approve'),
    path('<int:post_id>/generate-image/', views_actions.generate_image, name='generate_image'),
    path('<int:post_id>/request-text-change/', views_actions.request_text_change, name='request_text_change'),
    path('<int:post_id>/request-image-change/', views_actions.request_image_change, name='request_image_change'),
    path('<int:post_id>/edit/', views_actions.edit_post, name='edit'),
    path('<int:post_id>/images/<int:image_id>/delete/', views_actions.delete_post_image, name='delete_image'),

    # HTML Overlay — preview com textos + export PNG
    path('<int:post_id>/overlay-data/', views_overlay.overlay_data, name='overlay_data'),
    path('<int:post_id>/export-png/', views_overlay.export_png, name='export_png'),
    path('<int:post_id>/save-elements/', views_overlay.save_elements, name='save_elements'),
    path('<int:post_id>/fonts/<str:role>/', views_overlay.font_file, name='font_file'),
]
