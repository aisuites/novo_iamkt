from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from apps.core.decorators import require_organization
from .models import Pauta, Post, TrendMonitor


@login_required
@require_organization
def pautas_list(request):
    """Listar pautas da organization"""
    # CRÍTICO: Filtrar explicitamente por organization do request
    pautas_list = Pauta.objects.for_request(request).select_related(
        'user', 'area'
    ).order_by('-created_at')
    
    # Paginação
    paginator = Paginator(pautas_list, 20)  # 20 pautas por página
    page_number = request.GET.get('page')
    pautas = paginator.get_page(page_number)
    
    context = {'pautas': pautas}
    return render(request, 'content/pautas_list.html', context)


@login_required
@require_organization
def pauta_create(request):
    """Criar nova pauta"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return redirect('content:pautas')


@login_required
@require_organization
def posts_list(request):
    """Listar posts da organization"""
    # CRÍTICO: Filtrar explicitamente por organization do request
    posts_list = Post.objects.for_request(request).select_related(
        'user', 'pauta', 'area'
    ).prefetch_related('assets').order_by('-created_at')
    
    # Paginação
    paginator = Paginator(posts_list, 20)  # 20 posts por página
    page_number = request.GET.get('page')
    posts = paginator.get_page(page_number)
    
    context = {'posts': posts}
    return render(request, 'content/posts_list.html', context)


@login_required
@require_organization
def post_create(request):
    """Criar novo post"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return redirect('content:posts')


@login_required
@require_organization
def trends_list(request):
    """Listar trends monitoradas da organization"""
    # CRÍTICO: Filtrar explicitamente por organization do request
    trends_list = TrendMonitor.objects.for_request(request).filter(
        is_active=True
    ).order_by('-created_at')
    
    # Paginação
    paginator = Paginator(trends_list, 30)  # 30 trends por página
    page_number = request.GET.get('page')
    trends = paginator.get_page(page_number)
    
    context = {'trends': trends}
    return render(request, 'content/trends_list.html', context)
