from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.knowledge.models import KnowledgeBase
from apps.content.models import Pauta, GeneratedContent, TrendMonitor
from apps.campaigns.models import Project, Approval
from apps.core.models import UsageLimit


@login_required
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
    posts_total = GeneratedContent.objects.filter(user=user).count()
    posts_draft = GeneratedContent.objects.filter(user=user, status='draft').count()
    posts_aprovados = GeneratedContent.objects.filter(user=user, status='approved').count()
    
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
    
    # Limites de uso (se existir área)
    limite_info = None
    if user_area:
        try:
            current_month = timezone.now().date().replace(day=1)
            limite = UsageLimit.objects.get(area=user_area, month=current_month)
            limite_info = {
                'current': limite.current_generations,
                'max': limite.max_generations,
                'percentual': (limite.current_generations / limite.max_generations * 100) if limite.max_generations > 0 else 0,
                'cost_current': limite.current_cost_usd,
                'cost_max': limite.max_cost_usd
            }
        except UsageLimit.DoesNotExist:
            pass
    
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
    ultimos_posts = GeneratedContent.objects.filter(user=user).order_by('-created_at')[:3]
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
        'limite_info': limite_info,
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
