from django.urls import path
from . import views, views_upload, views_gerar, views_actions, views_webhook

app_name = 'posts'

urlpatterns = [
    path('', views.posts_list, name='list'),
    
    # Gerar Post
    path('gerar/', views_gerar.gerar_post, name='gerar'),
    
    # N8N Webhook - Receber post processado
    path('webhook/callback/', views_webhook.n8n_post_callback, name='n8n_post_callback'),
    
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
]
