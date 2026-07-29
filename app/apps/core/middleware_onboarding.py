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
    # Inclui endpoints de API usados pelas proprias paginas permitidas
    # (ex: lazy-load de imagens, preview de posts). Todos validam organization.
    ALLOWED_PATHS = [
        '/knowledge/',               # Base de Conhecimento
        '/accounts/logout/',         # Logout
        '/accounts/profile/',        # Perfil do usuário
        '/static/',                  # Static files
        '/media/',                   # Media files
        '/admin/',                   # Admin (para staff)
        '/posts/preview-url/',       # Preview de imagens (usado pelo lazy-loader no Perfil)
    ]
    
    def process_request(self, request):
        # Pular se não autenticado
        if not request.user.is_authenticated:
            return None
        
        # Pular se é superuser ou staff
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        organization = getattr(request, 'organization', None)

        # Org só de Vídeos Avatar: NÃO passa por onboarding de KB e fica
        # cercada no módulo de vídeos (antes do ALLOWED_PATHS global, senão
        # /knowledge/ e afins escapam da cerca).
        if organization and organization.is_videos_avatar_only:
            if request.path.startswith('/content/videos-avatar/'):
                return None
            if any(request.path.startswith(p) for p in
                   ('/accounts/', '/static/', '/media/')):
                return None
            print(f"🔄 [MIDDLEWARE] Org avatar-only: {request.path} → Vídeos Avatar", flush=True)
            return redirect('content:videos_avatar')

        # Pular se é URL permitida
        if any(request.path.startswith(path) for path in self.ALLOWED_PATHS):
            return None

        # Verificar onboarding
        print(f"🔍 [MIDDLEWARE] Path: {request.path} | Organization: {organization}", flush=True)

        if organization:
            from apps.knowledge.models import KnowledgeBase

            try:
                kb = KnowledgeBase.objects.filter(organization=organization).first()
                print(f"🔍 [MIDDLEWARE] KB encontrado: {kb is not None}", flush=True)
                
                if kb:
                    print(f"🔍 [MIDDLEWARE] Onboarding completo: {kb.onboarding_completed}", flush=True)
                    print(f"🔍 [MIDDLEWARE] Sugestões revisadas: {kb.suggestions_reviewed}", flush=True)
                    
                    # FLUXO 1: Onboarding não concluído - apenas Base de Conhecimento
                    if not kb.onboarding_completed:
                        if not request.path.startswith('/knowledge/'):
                            print(f"🔄 [MIDDLEWARE] FLUXO 1: Redirecionando para Base de Conhecimento", flush=True)
                            return redirect('knowledge:view')
                    
                    # FLUXO 2: Onboarding completo mas sugestões não revisadas - apenas Perfil
                    elif kb.onboarding_completed and not kb.suggestions_reviewed:
                        # Permitir acesso apenas a /knowledge/perfil/ e URLs permitidas
                        if not request.path.startswith('/knowledge/perfil'):
                            print(f"🔄 [MIDDLEWARE] FLUXO 2: Redirecionando para Perfil (Edição)", flush=True)
                            return redirect('knowledge:perfil_view')
                        else:
                            print(f"✅ [MIDDLEWARE] FLUXO 2: Permitindo acesso a Perfil", flush=True)
                    
                    # FLUXO 3: Onboarding completo e sugestões revisadas - acesso total
                    else:
                        # Redirecionar apenas a raiz para dashboard
                        if request.path == '/':
                            print(f"🔄 [MIDDLEWARE] FLUXO 3: Redirecionando raiz para Dashboard", flush=True)
                            return redirect('core:dashboard')
                        else:
                            print(f"✅ [MIDDLEWARE] FLUXO 3: Permitindo acesso a {request.path}", flush=True)
            except Exception as e:
                # Em caso de erro, permitir acesso (fail-safe)
                print(f"❌ [MIDDLEWARE] Erro: {e}", flush=True)
                pass
        
        return None
