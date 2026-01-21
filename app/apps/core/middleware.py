"""
IAMKT - Tenant Isolation Middleware

Detecta a organization do usuário logado e disponibiliza no request.
Garante que todas as views tenham acesso à organization atual.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
from apps.core.models import Organization


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware que detecta e injeta a organization atual no request.
    
    Funcionalidades:
    1. Detecta organization do usuário logado
    2. Disponibiliza em request.organization
    3. Bloqueia acesso se usuário não tiver organization
    4. Permite acesso público a URLs específicas
    """
    
    # URLs que não precisam de tenant (login, logout, etc)
    PUBLIC_URLS = [
        '/admin/login/',
        '/admin/logout/',
        '/login/',
        '/logout/',
        '/static/',
        '/media/',
        '/health/',
    ]
    
    def process_request(self, request):
        """
        Processa request e injeta organization.
        """
        # Inicializar organization como None
        request.organization = None
        
        # Verificar se é URL pública
        if self._is_public_url(request.path):
            return None
        
        # Verificar se usuário está autenticado
        if not request.user.is_authenticated:
            return None
        
        # Buscar organization do usuário
        if hasattr(request.user, 'organization') and request.user.organization:
            request.organization = request.user.organization
        else:
            # Usuário sem organization - bloquear acesso
            # (exceto para superusers que podem acessar admin)
            if not request.user.is_superuser:
                return HttpResponseForbidden(
                    "Acesso negado: Usuário não está vinculado a nenhuma organização."
                )
        
        return None
    
    def _is_public_url(self, path):
        """
        Verifica se URL é pública (não precisa de tenant).
        """
        return any(path.startswith(url) for url in self.PUBLIC_URLS)


class TenantIsolationMiddleware(MiddlewareMixin):
    """
    Middleware adicional para garantir isolamento de tenant.
    
    Funcionalidades:
    1. Valida que organization existe no request
    2. Adiciona headers de segurança
    3. Log de acesso por tenant (futuro)
    """
    
    def process_request(self, request):
        """
        Valida isolamento de tenant.
        """
        # Apenas para usuários autenticados em URLs não-públicas
        if not request.user.is_authenticated:
            return None
        
        if self._is_public_url(request.path):
            return None
        
        # Garantir que organization está presente
        if not hasattr(request, 'organization'):
            # TenantMiddleware deve ter rodado antes
            request.organization = None
        
        return None
    
    def process_response(self, request, response):
        """
        Adiciona headers de segurança relacionados a tenant.
        """
        if hasattr(request, 'organization') and request.organization:
            # Adicionar header indicando tenant (útil para debugging)
            response['X-Tenant-ID'] = str(request.organization.id)
            response['X-Tenant-Slug'] = request.organization.slug
        
        return response
    
    def _is_public_url(self, path):
        """
        Verifica se URL é pública.
        """
        public_urls = [
            '/admin/login/',
            '/admin/logout/',
            '/login/',
            '/logout/',
            '/static/',
            '/media/',
            '/health/',
        ]
        return any(path.startswith(url) for url in public_urls)
