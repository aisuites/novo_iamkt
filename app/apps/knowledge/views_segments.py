"""
Views AJAX para gerenciamento de Segmentos Internos
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from .models import KnowledgeBase, InternalSegment


@login_required
@require_http_methods(["POST"])
def segment_create(request):
    """Criar novo segmento interno via AJAX"""
    try:
        data = json.loads(request.body)
        kb = KnowledgeBase.get_instance()
        
        segment = InternalSegment.objects.create(
            knowledge_base=kb,
            name=data['name'],
            description=data.get('description', ''),
            parent_id=data.get('parent') or None,
            order=data.get('order', 0),
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Segmento criado com sucesso',
            'segment': {
                'id': segment.id,
                'name': segment.name,
                'code': segment.code,
                'full_path': segment.get_full_path()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao criar segmento: {str(e)}'
        }, status=400)


@login_required
@require_http_methods(["GET"])
def segment_get(request, segment_id):
    """Obter dados de um segmento via AJAX"""
    try:
        segment = get_object_or_404(InternalSegment, id=segment_id)
        
        return JsonResponse({
            'id': segment.id,
            'name': segment.name,
            'code': segment.code,
            'description': segment.description,
            'parent': segment.parent_id,
            'order': segment.order,
            'is_active': segment.is_active,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao carregar segmento: {str(e)}'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def segment_update(request, segment_id):
    """Atualizar segmento existente via AJAX"""
    try:
        data = json.loads(request.body)
        segment = get_object_or_404(InternalSegment, id=segment_id)
        
        segment.name = data['name']
        segment.description = data.get('description', '')
        segment.parent_id = data.get('parent') or None
        segment.order = data.get('order', 0)
        segment.updated_by = request.user
        segment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Segmento atualizado com sucesso',
            'segment': {
                'id': segment.id,
                'name': segment.name,
                'code': segment.code,
                'full_path': segment.get_full_path()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao atualizar segmento: {str(e)}'
        }, status=400)


@login_required
@require_http_methods(["POST"])
def segment_delete(request, segment_id):
    """Desativar segmento (soft delete) via AJAX"""
    try:
        segment = get_object_or_404(InternalSegment, id=segment_id)
        segment.is_active = False
        segment.updated_by = request.user
        segment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Segmento desativado com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao desativar segmento: {str(e)}'
        }, status=400)


@login_required
@require_http_methods(["POST"])
def segment_restore(request, segment_id):
    """Reativar segmento inativo via AJAX"""
    try:
        segment = get_object_or_404(InternalSegment, id=segment_id)
        segment.is_active = True
        segment.updated_by = request.user
        segment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Segmento reativado com sucesso',
            'segment': {
                'id': segment.id,
                'name': segment.name,
                'code': segment.code,
                'full_path': segment.get_full_path()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao reativar segmento: {str(e)}'
        }, status=400)
