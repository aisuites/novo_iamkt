"""
IAMKT - Context Processors

Adiciona variáveis globais aos templates.
"""


def tenant_context(request):
    """
    Adiciona organization atual ao contexto de todos os templates.
    
    Uso nos templates:
        {{ organization.name }}
        {{ organization.slug }}
        {% if organization %}
            ...
        {% endif %}
    """
    context = {
        'organization': getattr(request, 'organization', None),
        'tenant': getattr(request, 'organization', None),  # Alias
    }
    
    if hasattr(request, 'organization') and request.organization:
        context['organization'] = request.organization
        context['tenant'] = request.organization
    
    # ETAPA 5: Adicionar status de onboarding ao contexto
    # Disponível em todos os templates (incluindo sidebar)
    if request.user.is_authenticated:
        from apps.knowledge.models import KnowledgeBase
        try:
            kb = KnowledgeBase.objects.filter(
                organization=getattr(request, 'organization', None)
            ).first()
            context['kb_onboarding_completed'] = kb.onboarding_completed if kb else False
        except:
            context['kb_onboarding_completed'] = False
    else:
        context['kb_onboarding_completed'] = False
    
    return context
