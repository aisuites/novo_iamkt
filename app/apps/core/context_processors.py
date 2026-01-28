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
            org = getattr(request, 'organization', None)
            print(f"🔍 CONTEXT PROCESSOR - User: {request.user.email}", flush=True)
            print(f"🔍 CONTEXT PROCESSOR - Organization: {org}", flush=True)
            
            kb = KnowledgeBase.objects.filter(organization=org).first()
            
            if kb:
                print(f"🔍 CONTEXT PROCESSOR - KB ID: {kb.id}", flush=True)
                print(f"🔍 CONTEXT PROCESSOR - onboarding_completed: {kb.onboarding_completed}", flush=True)
                context['kb_onboarding_completed'] = kb.onboarding_completed
            else:
                print(f"⚠️ CONTEXT PROCESSOR - KB não encontrada!", flush=True)
                context['kb_onboarding_completed'] = False
        except Exception as e:
            print(f"❌ CONTEXT PROCESSOR - Erro: {e}", flush=True)
            context['kb_onboarding_completed'] = False
    else:
        context['kb_onboarding_completed'] = False
    
    print(f"✅ CONTEXT PROCESSOR - kb_onboarding_completed final: {context.get('kb_onboarding_completed')}", flush=True)
    return context
