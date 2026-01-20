"""
URLs do app knowledge
"""
from django.urls import path
from . import views
from . import views_segments
from . import views_tags

app_name = 'knowledge'

urlpatterns = [
    # Visualização e edição (página única)
    path('', views.knowledge_view, name='view'),
    
    # Salvamento
    path('save-block/<int:block_number>/', views.knowledge_save_block, name='save_block'),
    path('save-all/', views.knowledge_save_all, name='save_all'),
    path('save-tags/', views_tags.knowledge_save_tags, name='save_tags'),
    
    # Uploads
    path('upload/image/', views.knowledge_upload_image, name='upload_image'),
    path('upload/logo/', views.knowledge_upload_logo, name='upload_logo'),
    path('upload/font/', views.knowledge_upload_font, name='upload_font'),
    
    # Segmentos Internos (AJAX)
    path('segment/create/', views_segments.segment_create, name='segment_create'),
    path('segment/<int:segment_id>/', views_segments.segment_get, name='segment_get'),
    path('segment/<int:segment_id>/update/', views_segments.segment_update, name='segment_update'),
    path('segment/<int:segment_id>/delete/', views_segments.segment_delete, name='segment_delete'),
    path('segment/<int:segment_id>/restore/', views_segments.segment_restore, name='segment_restore'),
]
