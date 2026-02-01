"""
URLs do app knowledge
"""
from django.urls import path
from . import views
from . import views_segments
from . import views_tags
from . import views_upload
from . import views_n8n
from . import views_perfil
from . import views_perfil_colors
from . import views_perfil_fonts

app_name = 'knowledge'

urlpatterns = [
    # Visualização e edição (página única)
    path('', views.knowledge_view, name='view'),
    path('perfil/', views.perfil_view, name='perfil_view'),
    path('perfil/apply-suggestions/', views_perfil.perfil_apply_suggestions, name='perfil_apply_suggestions'),
    path('perfil/add-color/', views_perfil_colors.perfil_add_color, name='perfil_add_color'),
    path('perfil/remove-color/', views_perfil_colors.perfil_remove_color, name='perfil_remove_color'),
    path('perfil/add-font/', views_perfil_fonts.perfil_add_font, name='perfil_add_font'),
    path('perfil/remove-font/', views_perfil_fonts.perfil_remove_font, name='perfil_remove_font'),
    
    # Salvamento
    path('save-block/<int:block_number>/', views.knowledge_save_block, name='save_block'),
    path('save-all/', views.knowledge_save_all, name='save_all'),
    path('save-tags/', views_tags.knowledge_save_tags, name='save_tags'),
    
    # Uploads (legado - manter por compatibilidade)
    path('upload/image/', views.knowledge_upload_image, name='upload_image'),
    path('upload/logo/', views.knowledge_upload_logo, name='upload_logo'),
    path('upload/font/', views.knowledge_upload_font, name='upload_font'),
    
    # Upload S3 - View Genérica de Preview (seguindo guia)
    path('preview-url/', views_upload.get_preview_url, name='preview_url'),
    
    # Upload S3 - Logos
    path('logo/upload-url/', views_upload.generate_logo_upload_url, name='logo_upload_url'),
    path('logo/create/', views_upload.create_logo, name='logo_create'),
    path('logo/<int:logo_id>/delete/', views_upload.delete_logo, name='logo_delete'),
    
    # Upload S3 - Imagens de Referência
    path('reference/upload-url/', views_upload.generate_reference_upload_url, name='reference_upload_url'),
    path('reference/create/', views_upload.create_reference_image, name='reference_create'),
    path('reference/<int:reference_id>/delete/', views_upload.delete_reference_image, name='reference_delete'),
    
    # Upload S3 - Fontes Customizadas
    path('font/upload-url/', views_upload.generate_font_upload_url, name='font_upload_url'),
    path('font/create/', views_upload.create_custom_font, name='font_create'),
    path('font/<int:font_id>/delete/', views_upload.delete_custom_font, name='font_delete'),
    
    # Segmentos Internos (AJAX)
    path('segment/create/', views_segments.segment_create, name='segment_create'),
    path('segment/<int:segment_id>/', views_segments.segment_get, name='segment_get'),
    path('segment/<int:segment_id>/update/', views_segments.segment_update, name='segment_update'),
    path('segment/<int:segment_id>/delete/', views_segments.segment_delete, name='segment_delete'),
    path('segment/<int:segment_id>/restore/', views_segments.segment_restore, name='segment_restore'),
    
    # N8N Webhooks
    path('webhook/fundamentos/', views_n8n.n8n_webhook_fundamentos, name='n8n_webhook_fundamentos'),
    path('webhook/compilation/', views_n8n.n8n_compilation_webhook, name='n8n_compilation_webhook'),
]
