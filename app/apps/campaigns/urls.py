"""
URLs do app campaigns
"""
from django.urls import path
from . import views

app_name = 'campaigns'

urlpatterns = [
    path('projects/', views.projects_list, name='projects'),
    path('projects/novo/', views.project_create, name='project_create'),
    path('approvals/', views.approvals_list, name='approvals'),
]
