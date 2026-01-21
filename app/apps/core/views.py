from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Organization, QuotaUsageDaily
from apps.core.decorators import require_organization
from apps.knowledge.models import KnowledgeBase
from apps.content.models import Pauta, Post, TrendMonitor
from apps.campaigns.models import Project, Approval


@login_required
@require_organization
def dashboard(request):
    """
    Dashboard principal do IAMKT.
    Mostra visão geral da base de conhecimento, ferramentas e atividades.
    """
    user = request.user
    
    # Verificar se existe Base de Conhecimento
    try:
        knowledge_base = KnowledgeBase.objects.first()
        kb_exists = True
        kb_completude = knowledge_base.completude_percentual if knowledge_base else 0
    except:
        kb_exists = False
        kb_completude = 0
    
    # Estatísticas do usuário/área
    user_area = user.areas.first() if user.areas.exists() else None
    
    # Pautas
    pautas_total = Pauta.objects.filter(user=user).count()
    pautas_pendentes = Pauta.objects.filter(user=user, status='pending').count()
    
    # Posts gerados
    posts_total = Post.objects.filter(user=user).count()
    posts_draft = Post.objects.filter(user=user, status='draft').count()
    posts_aprovados = Post.objects.filter(user=user, status='approved').count()
    
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
    
    # Trends recentes
    trends_recentes = TrendMonitor.objects.filter(
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
            total_pautas=Sum('pautas_count'),
            total_posts=Sum('posts_count'),
            total_cost=Sum('cost_usd')
        )
        
        pautas_hoje = usage_today.pautas_count if usage_today else 0
        posts_hoje = usage_today.posts_count if usage_today else 0
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
            'posts_mes': pautas_mes,
            'posts_mes_max': org.quota_posts_mes,
            'posts_mes_percentual': (posts_mes / org.quota_posts_mes * 100) if org.quota_posts_mes > 0 else 0,
            
            # Custos
            'cost_mes': cost_mes,
            'cost_mes_max': float(org.quota_cost_mes_usd) if org.quota_cost_mes_usd else 0,
            'cost_mes_percentual': (cost_mes / float(org.quota_cost_mes_usd) * 100) if org.quota_cost_mes_usd and org.quota_cost_mes_usd > 0 else 0,
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
        'service': 'iamkt'
    })
