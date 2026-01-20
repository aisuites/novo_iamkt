from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Apps
    path('', include('apps.core.urls')),
    path('dashboard/', include('apps.core.urls')),
    path('knowledge/', include('apps.knowledge.urls')),
    path('content/', include('apps.content.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
