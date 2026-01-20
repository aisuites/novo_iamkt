"""
Views para gerenciamento de tags via AJAX
Elimina necessidade de textareas hidden no HTML
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from .models import KnowledgeBase


@login_required
@require_http_methods(["POST"])
def knowledge_save_tags(request):
    """
    Salvar tags via AJAX (elimina necessidade de textareas hidden)
    
    Payload esperado:
    {
        "field_name": "palavras_recomendadas",
        "tags": ["tag1", "tag2", "tag3"]
    }
    """
    try:
        data = json.loads(request.body)
        field_name = data.get('field_name')
        tags = data.get('tags', [])
        
        # Validar field_name
        valid_fields = [
            'palavras_recomendadas',
            'palavras_evitar',
            'fontes_confiaveis',
            'canais_trends',
            'palavras_chave_trends'
        ]
        
        if field_name not in valid_fields:
            return JsonResponse({
                'success': False,
                'message': 'Campo inválido'
            }, status=400)
        
        # Validar tags
        if not isinstance(tags, list):
            return JsonResponse({
                'success': False,
                'message': 'Tags devem ser uma lista'
            }, status=400)
        
        # Validar cada tag
        for tag in tags:
            if not isinstance(tag, str):
                return JsonResponse({
                    'success': False,
                    'message': 'Todas as tags devem ser strings'
                }, status=400)
        
        # Obter instância
        kb = KnowledgeBase.get_instance()
        
        # Atualizar campo específico
        setattr(kb, field_name, tags)
        kb.last_updated_by = request.user
        kb.save(update_fields=[field_name, 'last_updated_by', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': f'{len(tags)} tag(s) salva(s) com sucesso',
            'tags': tags
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao salvar: {str(e)}'
        }, status=500)
