"""
Views de Autenticação (Login, Register, Password Reset)
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    View de login
    GET: Exibe formulário de login
    POST: Processa autenticação
    """
    # Se já está autenticado, redirecionar para dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Autenticar usuário
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Verificar se usuário tem organização
            if not hasattr(user, 'organization') or user.organization is None:
                messages.error(request, 'Sua conta não está associada a nenhuma organização. Entre em contato com o suporte.')
                return render(request, 'auth/login.html')
            
            # Verificar status da organização
            org = user.organization
            
            if not org.is_active:
                if org.approved_at:
                    # Organização foi suspensa
                    messages.error(request, 'Sua organização está suspensa. Para mais detalhes, entre em contato com o suporte: suporte@aisuites.com.br')
                else:
                    # Organização aguardando aprovação
                    messages.warning(request, 'Sua organização está aguardando aprovação. Você será notificado por e-mail quando for aprovada.')
                return render(request, 'auth/login.html')
            
            # Login bem-sucedido - organização ativa
            auth_login(request, user)
            
            # Sempre mostrar modal de boas-vindas no primeiro login da sessão
            # (a flag será setada no dashboard após exibir o modal)
            request.session['show_welcome_modal'] = True
            
            # Redirecionar para página solicitada ou dashboard
            next_url = request.GET.get('next', 'core:dashboard')
            return redirect(next_url)
        else:
            # Credenciais inválidas
            messages.error(request, 'E-mail ou senha incorretos. Tente novamente.')
    
    return render(request, 'auth/login.html')


@never_cache
def logout_view(request):
    """View de logout"""
    auth_logout(request)
    messages.success(request, 'Você saiu com sucesso.')
    return redirect('login')


@never_cache
@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    View de registro (temporária - apenas exibe mensagem)
    TODO: Implementar formulário de registro completo
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    # Por enquanto, apenas renderiza página informativa
    return render(request, 'auth/register.html')
