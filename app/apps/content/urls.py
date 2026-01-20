"""
URLs do app content
"""
from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('pautas/', views.pautas_list, name='pautas'),
    path('pautas/nova/', views.pauta_create, name='pauta_create'),
    path('posts/', views.posts_list, name='posts'),
    path('posts/novo/', views.post_create, name='post_create'),
    path('trends/', views.trends_list, name='trends'),
]
