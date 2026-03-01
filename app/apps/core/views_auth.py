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
            print(f"🔍 [LOGIN] Usuário autenticado: {user.email}", flush=True)
            
            # Verificar se usuário tem organização
            if not hasattr(user, 'organization') or user.organization is None:
                print(f"❌ [LOGIN] Usuário sem organização: {user.email}", flush=True)
                messages.error(request, 'Sua conta não está associada a nenhuma organização. Entre em contato com o suporte.')
                return render(request, 'auth/login.html')
            
            # Verificar status da organização
            org = user.organization
            print(f"🔍 [LOGIN] Organização: {org.name} (id={org.id}, active={org.is_active})", flush=True)
            
            if not org.is_active:
                print(f"❌ [LOGIN] Organização inativa: {org.name}", flush=True)
                if org.approved_at:
                    # Organização foi suspensa
                    messages.error(request, f'Sua organização está suspensa. Para mais detalhes, entre em contato com o suporte: {settings.NOTIFICATION_EMAIL_SUPORTE}')
                else:
                    # Organização aguardando aprovação
                    messages.warning(request, 'Sua organização está aguardando aprovação. Você será notificado por e-mail quando for aprovada.')
                return render(request, 'auth/login.html')
            
            # Login bem-sucedido - organização ativa
            auth_login(request, user)
            print(f"✅ [LOGIN] Login bem-sucedido: {user.email}", flush=True)
            
            # Sempre mostrar modal de boas-vindas no primeiro login da sessão
            # (a flag será setada no dashboard após exibir o modal)
            request.session['show_welcome_modal'] = True
            
            # Verificar se tem parâmetro 'next' na URL
            next_url = request.GET.get('next')
            print(f"🔍 [LOGIN] Parâmetro 'next': {next_url}", flush=True)
            if next_url:
                print(f"🔄 [LOGIN] Redirecionando para 'next': {next_url}", flush=True)
                return redirect(next_url)
            
            # Verificar onboarding e suggestions_reviewed para decidir redirecionamento
            from apps.knowledge.models import KnowledgeBase
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                kb = KnowledgeBase.objects.filter(organization=org).first()
                
                # Criar KB automaticamente se não existir
                if not kb:
                    kb = KnowledgeBase.objects.create(
                        organization=org,
                        nome_empresa=org.name
                    )
                    logger.info(f"✅ [LOGIN] KB criado automaticamente para {org.name}")
                    print(f"✅ [LOGIN] KB criado automaticamente para {org.name}", flush=True)
                
                print(f"🔍 [LOGIN] KB encontrado: {kb is not None}", flush=True)
                
                if kb:
                    print(f"🔍 [LOGIN] Onboarding completo: {kb.onboarding_completed}", flush=True)
                    print(f"🔍 [LOGIN] Sugestões revisadas: {kb.suggestions_reviewed}", flush=True)
                    print(f"🔍 [LOGIN] Analysis status: {kb.analysis_status}", flush=True)
                    
                    # FLUXO 1: Onboarding não concluído
                    if not kb.onboarding_completed:
                        print(f"🔄 [LOGIN] FLUXO 1: Redirecionando para Base de Conhecimento", flush=True)
                        return redirect('knowledge:view')
                    
                    # FLUXO 2: Onboarding completo mas sugestões não revisadas
                    elif kb.onboarding_completed and not kb.suggestions_reviewed:
                        print(f"🔄 [LOGIN] FLUXO 2: Redirecionando para Perfil (Edição)", flush=True)
                        return redirect('knowledge:perfil_view')
                    
                    # FLUXO 3: Onboarding completo e sugestões revisadas
                    else:
                        print(f"� [LOGIN] FLUXO 3: Redirecionando para Dashboard", flush=True)
                        return redirect('core:dashboard')
                else:
                    print(f"🔍 [LOGIN] KB não encontrado, vai para dashboard", flush=True)
            except Exception as e:
                print(f"❌ [LOGIN] Erro ao verificar onboarding: {e}", flush=True)
                import traceback
                print(traceback.format_exc(), flush=True)
            
            # Padrão: redirecionar para dashboard
            print(f"🔄 [LOGIN] REDIRECIONANDO PARA DASHBOARD (padrão)", flush=True)
            return redirect('core:dashboard')
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
@csrf_protect
@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    View de registro de nova empresa + usuário
    GET: Exibe formulário de registro
    POST: Processa cadastro, cria organização e usuário, envia emails
    """
    # Se já está autenticado, redirecionar para dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        from django.utils.text import slugify
        from .models import User, Organization
        from .emails import send_registration_confirmation, send_registration_notification
        import re
        
        # Capturar dados do formulário
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        company_name = request.POST.get('company_name', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        phone = request.POST.get('phone', '').strip()
        accept_terms = request.POST.get('accept_terms') == 'on'
        
        # Validações
        errors = []
        
        # 1. Campos obrigatórios
        if not full_name or len(full_name) < 3:
            errors.append('Nome completo deve ter pelo menos 3 caracteres.')
        
        if not email:
            errors.append('Email é obrigatório.')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Email inválido.')
        
        if not company_name or len(company_name) < 3:
            errors.append('Nome da empresa deve ter pelo menos 3 caracteres.')
        
        if not password or len(password) < 8:
            errors.append('Senha deve ter pelo menos 8 caracteres.')
        
        if password != password_confirm:
            errors.append('As senhas não coincidem.')
        
        if not accept_terms:
            errors.append('Você deve aceitar os Termos de Uso para continuar.')
        
        # 2. Validar email único
        if email and User.objects.filter(email=email).exists():
            errors.append('Este email já está cadastrado.')
        
        # 3. Validar senha forte
        if password and len(password) >= 8:
            try:
                validate_password(password)
            except ValidationError as e:
                errors.extend(e.messages)
        
        # Se houver erros, retornar ao formulário
        if errors:
            for error in errors:
                messages.error(request, error)
            
            context = {
                'full_name': full_name,
                'email': email,
                'company_name': company_name,
                'phone': phone,
            }
            return render(request, 'auth/register.html', context)
        
        # Criar organização e usuário
        try:
            # 1. Criar Organization (pendente de aprovação)
            organization = Organization.objects.create(
                name=company_name,
                slug=slugify(company_name),
                is_active=False,  # Aguardando aprovação
                plan_type='pending',
                suspension_reason='pending_approval',
                quota_pautas_dia=0,
                quota_posts_dia=0,
                quota_posts_mes=0
            )
            
            # 2. Dividir nome completo em first_name e last_name
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            # 3. Criar User (inativo, vinculado à organização)
            user = User.objects.create(
                username=email,  # Email é o username
                email=email,
                first_name=first_name,
                last_name=last_name,
                organization=organization,
                profile='admin',  # Primeiro usuário é admin da organização
                is_active=False  # Aguardando aprovação
            )
            user.set_password(password)
            user.save()
            
            # 3.1. Definir usuário como owner da organização
            organization.owner = user
            organization.save()
            
            # 4. Enviar emails
            email_user_sent = send_registration_confirmation(user, organization)
            email_team_sent = send_registration_notification(user, organization)
            
            if not email_user_sent:
                messages.warning(request, 'Cadastro realizado, mas houve um problema ao enviar o email de confirmação.')
            
            if not email_team_sent:
                # Log interno, não mostrar ao usuário
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'Email de notificação não enviado para equipe - Cadastro: {email}')
            
            # 5. Redirecionar para página de sucesso
            return redirect('register_success')
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Erro ao criar cadastro: {str(e)}')
            messages.error(request, 'Ocorreu um erro ao processar seu cadastro. Tente novamente.')
            
            context = {
                'full_name': full_name,
                'email': email,
                'company_name': company_name,
                'phone': phone,
            }
            return render(request, 'auth/register.html', context)
    
    # GET: Exibir formulário vazio
    return render(request, 'auth/register.html')


@never_cache
@require_http_methods(["GET"])
def register_success_view(request):
    """
    Página de confirmação após cadastro bem-sucedido
    """
    return render(request, 'auth/register_success.html')
