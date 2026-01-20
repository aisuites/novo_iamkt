from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pauta, GeneratedContent, TrendMonitor


@login_required
def pautas_list(request):
    """Listar pautas do usuário"""
    pautas = Pauta.objects.filter(user=request.user).order_by('-created_at')
    context = {'pautas': pautas}
    return render(request, 'content/pautas_list.html', context)


@login_required
def pauta_create(request):
    """Criar nova pauta"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return redirect('content:pautas')


@login_required
def posts_list(request):
    """Listar posts do usuário"""
    posts = GeneratedContent.objects.filter(user=request.user).order_by('-created_at')
    context = {'posts': posts}
    return render(request, 'content/posts_list.html', context)


@login_required
def post_create(request):
    """Criar novo post"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return redirect('content:posts')


@login_required
def trends_list(request):
    """Listar trends monitoradas"""
    trends = TrendMonitor.objects.filter(is_active=True).order_by('-created_at')
    context = {'trends': trends}
    return render(request, 'content/trends_list.html', context)
