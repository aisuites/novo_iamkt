from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Project, Approval


@login_required
def projects_list(request):
    """Listar projetos do usuário"""
    projects = Project.objects.filter(owner=request.user).order_by('-created_at')
    context = {'projects': projects}
    return render(request, 'campaigns/projects_list.html', context)


@login_required
def project_create(request):
    """Criar novo projeto"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return redirect('campaigns:projects')


@login_required
def approvals_list(request):
    """Listar aprovações pendentes"""
    if request.user.profile in ['gestor', 'admin']:
        approvals = Approval.objects.filter(
            approver=request.user,
            decision='pending'
        ).order_by('-requested_at')
    else:
        approvals = Approval.objects.filter(
            requested_by=request.user
        ).order_by('-requested_at')
    
    context = {'approvals': approvals}
    return render(request, 'campaigns/approvals_list.html', context)
