import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import Pauta
from .forms import PautaCreateForm, PautaEditForm
from .services.n8n_service import PautaN8NService
from apps.knowledge.models import KnowledgeBase

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def pautas_list_view(request):
    """View principal da página de pautas"""
    
    # Verificar se empresa tem módulo de pautas contratado
    if not hasattr(request.user.organization, 'has_pautas_module') or not request.user.organization.has_pautas_module:
        return render(request, 'pautas/module_not_available.html')
    
    # Buscar knowledge_base da organização
    try:
        knowledge_base = KnowledgeBase.objects.get(
            organization=request.user.organization,
            onboarding_completed=True
        )
    except KnowledgeBase.DoesNotExist:
        messages.warning(request, "Complete o perfil da sua empresa antes de gerar pautas.")
        knowledge_base = None
    
    # Aplicar filtros
    queryset = Pauta.objects.filter(organization=request.user.organization)
    
    # Filtro por rede social
    rede = request.GET.get('rede')
    if rede:
        queryset = queryset.filter(rede_social=rede)
    
    # Filtro por status
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)
    
    # Filtro por data
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    if data_inicio:
        queryset = queryset.filter(created_at__date__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(created_at__date__lte=data_fim)
    
    # Filtro por busca (título ou conteúdo)
    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(content__icontains=search)
        )
    
    # Ordenação e paginação
    queryset = queryset.order_by('-created_at')
    paginator = Paginator(queryset, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'knowledge_base': knowledge_base,
        'filtros': {
            'rede': rede,
            'status': status,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        },
        'rede_choices': Pauta.REDE_SOCIAL_CHOICES,
        'status_choices': Pauta.STATUS_CHOICES,
    }
    
    return render(request, 'pautas/pautas_list.html', context)


@login_required
@require_http_methods(["POST"])
def gerar_pauta_view(request):
    """View para gerar pautas via N8N"""
    
    # Verificar módulo contratado
    if not hasattr(request.user.organization, 'has_pautas_module') or not request.user.organization.has_pautas_module:
        return JsonResponse({'success': False, 'error': 'Módulo não contratado'})
    
    # Buscar knowledge_base
    try:
        knowledge_base = KnowledgeBase.objects.get(
            organization=request.user.organization,
            onboarding_completed=True
        )
    except KnowledgeBase.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Perfil da empresa não completado'})
    
    # Validar formulário
    form = PautaCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos',
            'errors': form.errors
        })
    
    tema = form.cleaned_data['tema']
    rede_social = form.cleaned_data['rede_social']
    
    # Enviar para N8N
    result = PautaN8NService.send_pauta_request(
        knowledge_base=knowledge_base,
        tema=tema,
        rede_social=rede_social,
        user=request.user
    )
    
    if result['success']:
        # Criar pauta com status 'requested'
        pauta = Pauta.objects.create(
            organization=request.user.organization,
            knowledge_base=knowledge_base,
            user=request.user,
            title=f"Pautas sobre {tema}",
            content=f"Pautas geradas para {rede_social} sobre o tema: {tema}",
            rede_social=rede_social,
            status='requested',
            generation_request=result['data']['payload_sent'],
            n8n_data=result['data']
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Solicitação enviada com sucesso!',
            'pauta_id': str(pauta.id)
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result['error']
        })


@login_required
@require_http_methods(["POST"])
def editar_pauta_view(request, pauta_id):
    """View para editar pauta (inline no card)"""
    
    pauta = get_object_or_404(Pauta, id=pauta_id, organization=request.user.organization)
    
    # Aceitar JSON ou form data
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    
    form = PautaEditForm(data, instance=pauta)
    if form.is_valid():
        pauta = form.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Pauta atualizada com sucesso!',
            'pauta': {
                'id': str(pauta.id),
                'title': pauta.title,
                'content': pauta.content
            }
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos',
            'errors': form.errors
        }, status=400)


@login_required
@require_http_methods(["POST"])
def excluir_pauta_view(request, pauta_id):
    """View para excluir pauta"""
    
    pauta = get_object_or_404(Pauta, id=pauta_id, organization=request.user.organization)
    
    # Adicionar entrada de exclusão no histórico antes de remover
    pauta.add_audit_entry(
        action='deleted',
        user=request.user,
        details={'reason': 'Exclusão solicitada pelo usuário'}
    )
    
    title = pauta.title
    pauta.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Pauta "{title}" excluída com sucesso!'
    })


@csrf_exempt
@xframe_options_sameorigin
@require_http_methods(["POST"])
def n8n_webhook_view(request):
    """Webhook para receber respostas do N8N"""
    
    try:
        body = json.loads(request.body)
        
        # Extrair parâmetros da query string OU do body
        organization_id = request.GET.get('organization_id')
        user_id = request.GET.get('user_id')
        rede_social = request.GET.get('rede_social')
        
        # Se não veio na query string, tentar extrair do body
        # O N8N pode enviar um objeto com metadata e array de pautas
        if isinstance(body, dict):
            # Formato do N8N: {"payload": [...], "organization_id": 10, "user_id": 12, "rede_social": "FACEBOOK"}
            if not organization_id:
                organization_id = body.get('organization_id')
            if not user_id:
                user_id = body.get('user_id')
            if not rede_social:
                rede_social = body.get('rede_social', 'FACEBOOK')
            
            # Extrair array de pautas - tentar várias chaves possíveis
            data = body.get('payload', body.get('pautas', body.get('data', [])))
            
            # Se não tem nenhuma dessas chaves e não tem organization_id, assumir que o body inteiro é o array
            if not data and not body.get('organization_id'):
                data = body if isinstance(body, list) else [body]
        else:
            # Body é diretamente o array de pautas
            data = body
        
        if not rede_social:
            rede_social = 'FACEBOOK'
        
        logger.info(f"[N8N_WEBHOOK] organization_id={organization_id}, user_id={user_id}, rede_social={rede_social}")
        logger.info(f"[N8N_WEBHOOK] Payload recebido: {len(data) if isinstance(data, list) else 'não é array'} pautas")
        
        # Processar resposta do N8N
        result = PautaN8NService.process_webhook_response(
            data, 
            organization_id=organization_id,
            user_id=user_id
        )
        
        if result['success']:
            # Atualizar rede_social nas pautas criadas
            if rede_social:
                from apps.pautas.models import Pauta
                for pauta in result['pautas_salvas']:
                    pauta.rede_social = rede_social
                    pauta.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{result["total"]} pautas salvas com sucesso'
            })
        else:
            logger.error(f"[N8N_WEBHOOK] Erro: {result.get('error')}")
            if 'traceback' in result:
                logger.error(f"[N8N_WEBHOOK] Traceback: {result['traceback']}")
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@login_required
def gerar_post_view(request, pauta_id):
    """View para gerar post a partir de pauta (fluxo diferente - definir depois)"""
    
    pauta = get_object_or_404(Pauta, id=pauta_id, organization=request.user.organization)
    
    # TODO: Implementar fluxo de geração de posts
    # Este fluxo será diferente do de pautas
    
    return JsonResponse({
        'success': False,
        'error': 'Fluxo de geração de posts ainda não implementado'
    })
