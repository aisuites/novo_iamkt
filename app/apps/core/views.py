from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Organization, QuotaUsageDaily
from .decorators import require_organization
from apps.content.models import Pauta, Post, TrendMonitor
from apps.knowledge.models import KnowledgeBase
from apps.campaigns.models import Project, Approval

@login_required
@require_organization
def dashboard(request):
    """
    Dashboard principal do IAMKT.
    Mostra visão geral da base de conhecimento, ferramentas e atividades.
    """
    user = request.user
    
    # Verificar se existe Base de Conhecimento DA ORGANIZATION
    try:
        organization = getattr(request, 'organization', None)
        knowledge_base = KnowledgeBase.objects.filter(organization=organization).first()
        kb_exists = knowledge_base is not None
        kb_completude = knowledge_base.completude_percentual if knowledge_base else 0
        kb = knowledge_base
    except:
        kb_exists = False
        kb_completude = 0
        kb = None
    
    print(f"🔍 [DASHBOARD] KB: {kb is not None} | Onboarding: {kb.onboarding_completed if kb else 'N/A'} | Suggestions: {kb.suggestions_reviewed if kb else 'N/A'}", flush=True)
    
    # Estatísticas da organização (compartilhadas entre todos os usuários)
    user_area = user.areas.first() if user.areas.exists() else None
    
    # Pautas (da organização, não do usuário)
    pautas_total = Pauta.objects.for_request(request).count()
    pautas_pendentes = Pauta.objects.for_request(request).filter(status='pending').count()
    
    # Posts gerados (da organização, não do usuário)
    posts_total = Post.objects.for_request(request).count()
    posts_draft = Post.objects.for_request(request).filter(status='draft').count()
    posts_aprovados = Post.objects.for_request(request).filter(status='approved').count()
    
    # Projetos
    projetos_ativos = Project.objects.filter(
        owner=user,
        status='active'
    ).count()
    
    # Aprovações pendentes
    if user.profile in ['gestor', 'admin']:
        aprovacoes_pendentes = Approval.objects.filter(
            approver=user,
            decision='pending'
        ).count()
    else:
        aprovacoes_pendentes = 0
    
    # Trends recentes (da organização)
    trends_recentes = TrendMonitor.objects.for_request(request).filter(
        is_active=True
    ).order_by('-created_at')[:5]
    
    # Quotas da organization
    quota_info = None
    if hasattr(request, 'organization') and request.organization:
        org = request.organization
        today = timezone.now().date()
        
        # Buscar uso de hoje
        try:
            usage_today = QuotaUsageDaily.objects.get(
                organization=org,
                date=today
            )
        except QuotaUsageDaily.DoesNotExist:
            usage_today = None
        
        # Calcular uso do mês
        first_day_month = today.replace(day=1)
        usage_month = QuotaUsageDaily.objects.filter(
            organization=org,
            date__gte=first_day_month,
            date__lte=today
        ).aggregate(
            total_pautas=Sum('pautas_requested'),
            total_posts=Sum('posts_created'),
            total_cost=Sum('cost_usd')
        )
        
        pautas_hoje = usage_today.pautas_requested if usage_today else 0
        posts_hoje = usage_today.posts_created if usage_today else 0
        pautas_mes = usage_month['total_pautas'] or 0
        posts_mes = usage_month['total_posts'] or 0
        cost_mes = float(usage_month['total_cost'] or 0)
        
        quota_info = {
            # Quotas diárias
            'pautas_hoje': pautas_hoje,
            'pautas_dia_max': org.quota_pautas_dia,
            'pautas_dia_percentual': (pautas_hoje / org.quota_pautas_dia * 100) if org.quota_pautas_dia > 0 else 0,
            
            'posts_hoje': posts_hoje,
            'posts_dia_max': org.quota_posts_dia,
            'posts_dia_percentual': (posts_hoje / org.quota_posts_dia * 100) if org.quota_posts_dia > 0 else 0,
            
            # Quotas mensais
            'posts_mes': posts_mes,
            'posts_mes_max': org.quota_posts_mes,
            'posts_mes_percentual': (posts_mes / org.quota_posts_mes * 100) if org.quota_posts_mes > 0 else 0,
            
            # Custo mensal (apenas tracking, sem limite)
            'cost_mes': cost_mes,
        }
    
    # Atividades recentes
    atividades_recentes = []
    
    # Últimas pautas
    ultimas_pautas = Pauta.objects.filter(user=user).order_by('-created_at')[:3]
    for pauta in ultimas_pautas:
        atividades_recentes.append({
            'tipo': 'pauta',
            'titulo': pauta.title or pauta.theme,
            'data': pauta.created_at,
            'status': pauta.status
        })
    
    # Últimos posts
    ultimos_posts = Post.objects.filter(user=user).order_by('-created_at')[:3]
    for post in ultimos_posts:
        atividades_recentes.append({
            'tipo': 'post',
            'titulo': f"Post para {post.get_social_network_display()}",
            'data': post.created_at,
            'status': post.status
        })
    
    # Ordenar por data
    atividades_recentes.sort(key=lambda x: x['data'], reverse=True)
    atividades_recentes = atividades_recentes[:5]
    
    context = {
        'user_name': user.first_name or user.username,
        'user_initial': user.first_name[0].upper() if user.first_name else user.username[0].upper(),
        'kb_exists': kb_exists,
        'kb_completude': kb_completude,
        'kb_onboarding_completed': kb.onboarding_completed if kb else False,
        'kb_suggestions_reviewed': kb.suggestions_reviewed if kb else False,
        'pautas_total': pautas_total,
        'pautas_pendentes': pautas_pendentes,
        'posts_total': posts_total,
        'posts_draft': posts_draft,
        'posts_aprovados': posts_aprovados,
        'projetos_ativos': projetos_ativos,
        'aprovacoes_pendentes': aprovacoes_pendentes,
        'trends_recentes': trends_recentes,
        'quota_info': quota_info,
        'atividades_recentes': atividades_recentes,
    }
    
    return render(request, 'dashboard/dashboard.html', context)


def home(request):
    """Redireciona para dashboard se autenticado, senão para login"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('login')


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat()
    })


@require_http_methods(["GET"])
def terms_view(request):
    """
    Página de Termos de Uso
    """
    return render(request, 'legal/terms.html')
