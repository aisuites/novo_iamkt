from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.decorators import require_organization
from .models import Project, Approval


@login_required
@require_organization
def projects_list(request):
    """Listar projetos da organization"""
    # OrganizationScopedManager filtra automaticamente por request.organization
    projects = Project.objects.all().order_by('-created_at')
    context = {'projects': projects}
    return render(request, 'campaigns/projects_list.html', context)


@login_required
@require_organization
def project_create(request):
    """Criar novo projeto"""
    # TODO: Implementar formulário
    messages.info(request, 'Funcionalidade em desenvolvimento')
    return render(request, 'campaigns/project_form.html')


@login_required
@require_organization
def approvals_list(request):
    """Listar aprovações pendentes da organization"""
    if request.user.profile in ['gestor', 'admin']:
        # Project já filtra por organization via OrganizationScopedManager
        approvals = Approval.objects.filter(
            status='pending'
        ).select_related('project').order_by('-created_at')
    else:
        approvals = []
    
    context = {'approvals': approvals}
    return render(request, 'campaigns/approvals_list.html', context)
