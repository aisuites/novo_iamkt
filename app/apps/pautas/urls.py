from django.urls import path
from . import views
from . import views_gerar_pauta

app_name = 'pautas'

urlpatterns = [
    # Página principal
    path('', views.pautas_list_view, name='list'),
    
    # Ações AJAX
    path('gerar/', views_gerar_pauta.gerar_pauta_n8n, name='gerar'),
    path('editar/<uuid:pauta_id>/', views.editar_pauta_view, name='editar'),
    path('excluir/<uuid:pauta_id>/', views.excluir_pauta_view, name='excluir'),
    path('gerar-post/<uuid:pauta_id>/', views.gerar_post_view, name='gerar_post'),
    
    # Webhook N8N
    path('webhook/n8n/', views.n8n_webhook_view, name='n8n_webhook'),
]
