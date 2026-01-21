from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views_auth import login_view, logout_view, register_view

# Handler para página 404
handler404 = 'apps.core.views_errors.custom_404'

urlpatterns = [
    # Auth
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Apps
    path('', include('apps.core.urls')),
    path('content/', include('apps.content.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
    path('knowledge/', include('apps.knowledge.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
