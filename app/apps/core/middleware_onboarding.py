"""
IAMKT - Onboarding Required Middleware

Restringe acesso ao sistema até que o onboarding seja concluído.
"""
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect


class OnboardingRequiredMiddleware(MiddlewareMixin):
    """
    Middleware que restringe acesso até conclusão do onboarding.
    
    Enquanto onboarding_completed = False:
    - Permite apenas: Base de Conhecimento, logout, perfil, static/media
    - Bloqueia: Dashboard, Pautas, Posts, Trends, etc.
    - Redireciona para Base de Conhecimento
    """
    
    # URLs permitidas sem onboarding completo
    ALLOWED_PATHS = [
        '/knowledge/',           # Base de Conhecimento
        '/accounts/logout/',     # Logout
        '/accounts/profile/',    # Perfil do usuário
        '/static/',              # Static files
        '/media/',               # Media files
        '/admin/',               # Admin (para staff)
    ]
    
    def process_request(self, request):
        # Pular se não autenticado
        if not request.user.is_authenticated:
            return None
        
        # Pular se é superuser ou staff
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        # Pular se é URL permitida
        if any(request.path.startswith(path) for path in self.ALLOWED_PATHS):
            return None
        
        # Verificar onboarding
        organization = getattr(request, 'organization', None)
        if organization:
            from apps.knowledge.models import KnowledgeBase
            
            try:
                kb = KnowledgeBase.objects.filter(organization=organization).first()
                
                if kb:
                    # Se onboarding não concluído, redirecionar para Base de Conhecimento
                    if not kb.onboarding_completed:
                        # Evitar loop de redirecionamento
                        if not request.path.startswith('/knowledge/'):
                            return redirect('knowledge:view')
                    else:
                        # Onboarding concluído: redirecionar para Perfil se tentar acessar dashboard
                        if request.path == '/':
                            return redirect('knowledge:perfil_view')
            except Exception:
                # Em caso de erro, permitir acesso (fail-safe)
                pass
        
        return None
