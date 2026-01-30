"""
Views específicas da página Perfil da Empresa
"""
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.utils import timezone
import json

from apps.knowledge.models import KnowledgeBase


@never_cache
@login_required
@require_POST
def perfil_apply_suggestions(request):
    """
    Aplica sugestões aceitas e salva campos editados pelo usuário
    """
    try:
        # Buscar KnowledgeBase
        kb = KnowledgeBase.objects.for_request(request).first()
        if not kb:
            return JsonResponse({
                'success': False,
                'error': 'Base de Conhecimento não encontrada.'
            }, status=404)
        
        # Parse do payload
        data = json.loads(request.body)
        accepted_suggestions = data.get('accepted_suggestions', [])
        edited_fields = data.get('edited_fields', {})
        
        print(f"📝 [PERFIL_APPLY] Sugestões aceitas: {accepted_suggestions}", flush=True)
        print(f"✏️ [PERFIL_APPLY] Campos editados: {list(edited_fields.keys())}", flush=True)
        
        if not accepted_suggestions and not edited_fields:
            return JsonResponse({
                'success': False,
                'error': 'Nenhuma alteração foi enviada.'
            }, status=400)
        
        # Mapeamento de campos N8N → campos do modelo
        field_mapping = {
            # BLOCO 1
            'company_name': 'nome_empresa',
            'mission': 'missao',
            'vision': 'visao',
            'values': 'valores',
            'description': 'descricao_produto',
            
            # BLOCO 2
            'target_audience': 'publico_externo',
            'internal_audience': 'publico_interno',
            # internal_segments é JSONField, tratar separado
            
            # BLOCO 3
            'positioning': 'posicionamento',
            'value_proposition': 'proposta_valor',
            'differentials': 'diferenciais',
            
            # BLOCO 4
            'tone_of_voice': 'tom_voz_externo',
            'internal_tone_of_voice': 'tom_voz_interno',
            # recommended_words e words_to_avoid são JSONField, tratar separado
            
            # BLOCO 5
            # palette_colors, fonts, logo_files, reference_images são relacionamentos, não campos diretos
            
            # BLOCO 6
            'website_url': 'site_institucional',
            # social_networks e competitors são relacionamentos/JSONField
        }
        
        with transaction.atomic():
            updated_fields = []
            
            # 1. APLICAR EDIÇÕES MANUAIS (prioridade)
            for field_n8n, new_value in edited_fields.items():
                model_field = field_mapping.get(field_n8n)
                
                if model_field and hasattr(kb, model_field):
                    setattr(kb, model_field, new_value)
                    updated_fields.append(model_field)
                    print(f"✅ [PERFIL_APPLY] Campo editado salvo: {model_field} = {new_value[:50]}...", flush=True)
            
            # 2. APLICAR SUGESTÕES ACEITAS
            if accepted_suggestions and kb.n8n_analysis:
                payload = kb.n8n_analysis.get('payload', [])
                if payload and len(payload) > 0:
                    campos_raw = payload[0]
                    
                    for field_n8n in accepted_suggestions:
                        # Pular se já foi editado manualmente
                        if field_n8n in edited_fields:
                            continue
                        
                        model_field = field_mapping.get(field_n8n)
                        
                        if model_field and hasattr(kb, model_field):
                            campo_data = campos_raw.get(field_n8n, {})
                            sugestao = campo_data.get('sugestao_do_agente_iamkt')
                            
                            if sugestao:
                                # Converter lista em string se necessário
                                if isinstance(sugestao, list):
                                    sugestao = '\n'.join(f"• {s}" for s in sugestao)
                                
                                setattr(kb, model_field, sugestao)
                                updated_fields.append(model_field)
                                print(f"✅ [PERFIL_APPLY] Sugestão aplicada: {model_field} = {str(sugestao)[:50]}...", flush=True)
                        
                        # Salvar em accepted_suggestions para histórico
                        if not kb.accepted_suggestions:
                            kb.accepted_suggestions = {}
                        kb.accepted_suggestions[field_n8n] = True
            
            # 3. MARCAR COMO REVISADO
            if not kb.suggestions_reviewed:
                kb.suggestions_reviewed = True
                kb.suggestions_reviewed_at = timezone.now()
                kb.suggestions_reviewed_by = request.user
                print(f"✅ [PERFIL_APPLY] Primeira revisão de sugestões marcada", flush=True)
            
            # 4. SALVAR ALTERAÇÕES
            kb.save()
            
            print(f"✅ [PERFIL_APPLY] Total de campos atualizados: {len(updated_fields)}", flush=True)
            print(f"✅ [PERFIL_APPLY] Campos: {updated_fields}", flush=True)
            
            return JsonResponse({
                'success': True,
                'updated_fields': updated_fields,
                'message': f'{len(updated_fields)} campo(s) atualizado(s) com sucesso!'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos.'
        }, status=400)
    
    except Exception as e:
        print(f"❌ [PERFIL_APPLY] Erro: {e}", flush=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
