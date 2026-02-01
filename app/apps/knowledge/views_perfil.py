"""
Views específicas da página Perfil da Empresa
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
import json

from apps.knowledge.models import KnowledgeBase, ColorPalette
from apps.knowledge.services.n8n_service import N8NService
import logging

logger = logging.getLogger(__name__)


@never_cache
@login_required
@require_POST
@csrf_exempt  # TODO: Remover após debug - CSRF deve ser validado
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
        
        # PERMITIR envio mesmo sem alterações (para enviar dados atuais ao N8N)
        # if not accepted_suggestions and not edited_fields:
        #     return JsonResponse({
        #         'success': False,
        #         'error': 'Nenhuma alteração foi enviada.'
        #     }, status=400)
        
        # Mapeamento SIMPLES: nome frontend (EN) → campo do modelo Django
        # NOTA: site, redes sociais e concorrentes podem ser EDITADOS manualmente
        # mas NÃO podem aceitar sugestões (sem botões aceitar/rejeitar)
        field_to_model = {
            'mission': 'missao',
            'vision': 'visao',
            'values': 'valores',
            'description': 'descricao_produto',
            'target_audience': 'publico_externo',
            'internal_audience': 'publico_interno',
            'positioning': 'posicionamento',
            'value_proposition': 'proposta_valor',
            'differentials': 'diferenciais',
            'tone_of_voice': 'tom_voz_externo',
            'internal_tone_of_voice': 'tom_voz_interno',
            'recommended_words': 'palavras_recomendadas',
            'words_to_avoid': 'palavras_evitar',
            'website_url': 'site_institucional',
            'social_networks': 'redes_sociais',
            'competitors': 'concorrentes',
        }
        
        with transaction.atomic():
            updated_fields = []
            fields_for_reevaluation = []  # Campos que precisam ser reavaliados (editados + aceitos)
            
            # 1. APLICAR EDIÇÕES MANUAIS (campos editados em tela)
            for field_en, new_value in edited_fields.items():
                model_field = field_to_model.get(field_en)
                
                # Tratamento especial para redes sociais (social_*_domain)
                if field_en.startswith('social_') and field_en.endswith('_domain'):
                    network_type = field_en.replace('social_', '').replace('_domain', '')
                    if new_value:
                        new_value = new_value.strip()
                        if new_value and not new_value.startswith(('http://', 'https://')):
                            url = f'https://{new_value}'
                        else:
                            url = new_value
                        
                        # Atualizar ou criar SocialNetwork
                        from apps.knowledge.models import SocialNetwork
                        SocialNetwork.objects.update_or_create(
                            knowledge_base=kb,
                            network_type=network_type,
                            defaults={
                                'name': network_type.capitalize(),
                                'url': url,
                                'is_active': True
                            }
                        )
                        updated_fields.append(f'social_{network_type}')
                        print(f"✅ [PERFIL_APPLY] Rede social editada: {network_type} = {url}", flush=True)
                    continue
                
                # Tratamento especial para concorrentes (JSON)
                if field_en == 'competitors':
                    try:
                        competitors_list = json.loads(new_value) if new_value else []
                        if isinstance(competitors_list, list):
                            kb.concorrentes = competitors_list
                            updated_fields.append('concorrentes')
                            print(f"✅ [PERFIL_APPLY] Concorrentes editados: {len(competitors_list)} item(ns)", flush=True)
                    except json.JSONDecodeError as e:
                        print(f"❌ [PERFIL_APPLY] Erro ao parsear concorrentes: {e}", flush=True)
                    continue
                
                if model_field and hasattr(kb, model_field):
                    # Tratamento especial para website_url: adicionar https:// se não presente
                    if field_en == 'website_url' and new_value:
                        new_value = new_value.strip()
                        if new_value and not new_value.startswith(('http://', 'https://')):
                            new_value = f'https://{new_value}'
                    
                    setattr(kb, model_field, new_value)
                    updated_fields.append(model_field)
                    fields_for_reevaluation.append(field_en)  # Adicionar à lista de reavaliação
                    print(f"✅ [PERFIL_APPLY] Campo editado: {field_en} → {model_field} = {new_value}", flush=True)
            
            # 2. APLICAR SUGESTÕES ACEITAS (buscar do JSON N8N)
            if accepted_suggestions and kb.n8n_analysis:
                payload = kb.n8n_analysis.get('payload', [])
                if payload and len(payload) > 0:
                    campos_raw = payload[0]
                    print(f"📝 [PERFIL_APPLY] Payload keys: {list(campos_raw.keys())[:10]}", flush=True)
                    
                    for field_en in accepted_suggestions:
                        # Pular se já foi editado manualmente
                        if field_en in edited_fields:
                            print(f"⏭️ [PERFIL_APPLY] Pulando {field_en} (já editado)", flush=True)
                            continue
                        
                        model_field = field_to_model.get(field_en)
                        if not model_field or not hasattr(kb, model_field):
                            print(f"⚠️ [PERFIL_APPLY] Campo {field_en} não mapeado ou não existe no modelo", flush=True)
                            continue
                        
                        print(f"🔄 [PERFIL_APPLY] Processando: {field_en} → {model_field}", flush=True)
                        
                        # Buscar sugestão no payload (tentar vários nomes possíveis)
                        sugestao = None
                        for possible_key in [field_en, model_field]:
                            if possible_key in campos_raw:
                                campo_data = campos_raw[possible_key]
                                if isinstance(campo_data, dict):
                                    sugestao = campo_data.get('sugestao_do_agente_iamkt')
                                    if sugestao:
                                        print(f"✅ [PERFIL_APPLY] Sugestão encontrada em '{possible_key}'", flush=True)
                                        break
                        
                        if not sugestao:
                            print(f"⚠️ [PERFIL_APPLY] Nenhuma sugestão encontrada para {field_en}", flush=True)
                            continue
                        
                        # Converter lista em string se necessário
                        if isinstance(sugestao, list):
                            sugestao = '\n'.join(f"• {s}" for s in sugestao)
                        
                        # Salvar no modelo
                        setattr(kb, model_field, sugestao)
                        updated_fields.append(model_field)
                        fields_for_reevaluation.append(field_en)  # Adicionar à lista de reavaliação
                        print(f"✅ [PERFIL_APPLY] Sugestão aplicada: {field_en} → {model_field}", flush=True)
            
            # 2.1 GUARDAR TODOS OS CAMPOS PARA REAVALIAÇÃO (editados + aceitos)
            if fields_for_reevaluation:
                kb.accepted_suggestion_fields = fields_for_reevaluation
                print(f"📋 [PERFIL_APPLY] Campos para reavaliação: {fields_for_reevaluation}", flush=True)
                print(f"   └─ Editados manualmente: {[f for f in fields_for_reevaluation if f in edited_fields]}", flush=True)
                print(f"   └─ Sugestões aceitas: {[f for f in fields_for_reevaluation if f in accepted_suggestions]}", flush=True)
            
            # 3. MARCAR COMO REVISADO
            if not kb.suggestions_reviewed:
                kb.suggestions_reviewed = True
                kb.suggestions_reviewed_at = timezone.now()
                kb.suggestions_reviewed_by = request.user
                print(f"✅ [PERFIL_APPLY] Primeira revisão de sugestões marcada", flush=True)
            
            # 4. SALVAR ALTERAÇÕES
            kb.save()
            
            # Verificar no banco
            kb.refresh_from_db()
            print(f"✅ [PERFIL_APPLY] Total de campos atualizados: {len(updated_fields)}", flush=True)
            print(f"✅ [PERFIL_APPLY] Campos: {updated_fields}", flush=True)
            print(f"💾 [PERFIL_APPLY] Dados salvos no banco (KB id={kb.id})", flush=True)
        
        # 5. ENVIAR PARA N8N (fora da transação)
        # Se houver campos para reavaliar, enviar para fundamentos primeiro
        # Senão, enviar direto para compilação
        if fields_for_reevaluation:
            print(f"🔄 [PERFIL_APPLY] Enviando para FUNDAMENTOS (reavaliação de {len(fields_for_reevaluation)} campos)", flush=True)
            n8n_result = N8NService.send_fundamentos(kb)
            flow_type = 'fundamentos_reevaluation'
        else:
            print(f"🔄 [PERFIL_APPLY] Enviando para COMPILAÇÃO (sem reavaliação)", flush=True)
            has_accepted = len(accepted_suggestions) > 0
            n8n_result = N8NService.send_for_compilation(kb, has_accepted)
            flow_type = n8n_result.get('flow_type', 'compilation')
        
        if not n8n_result['success']:
            logger.warning(f"⚠️ [PERFIL_APPLY] Falha ao enviar para N8N: {n8n_result.get('error')}")
        else:
            logger.info(f"✅ [PERFIL_APPLY] Enviado para N8N - Fluxo: {flow_type}")
        
        # 6. RETORNAR SUCESSO (frontend redireciona)
        # Redirecionar para perfil-visualizacao que detecta compilation_status
        return JsonResponse({
            'success': True,
            'updated_fields': updated_fields,
            'message': f'{len(updated_fields)} campo(s) atualizado(s) com sucesso!',
            'redirect_url': '/knowledge/perfil-visualizacao/',
            'n8n_status': n8n_result['success'],
            'flow_type': flow_type,
            'is_reevaluation': bool(fields_for_reevaluation)
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
