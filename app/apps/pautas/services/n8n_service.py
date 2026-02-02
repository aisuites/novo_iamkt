import json
import uuid
import requests
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.knowledge.models import KnowledgeBase

User = get_user_model()


class PautaN8NService:
    """Serviço para integração com N8N para geração de pautas"""
    
    # Endpoints N8N
    ENDPOINT_ENVIO = "https://n8n.srv812718.hstgr.cloud/webhook/gerar-pauta-wind"
    ENDPOINT_WEBHOOK = "https://n8n.srv1080437.hstgr.cloud/webhook/gerar-pauta-prod"
    
    @staticmethod
    def send_pauta_request(knowledge_base, tema, rede_social, user):
        """
        Envia solicitação de geração de pautas para N8N
        
        Args:
            knowledge_base: Instância de KnowledgeBase
            tema: Tema para geração das pautas
            rede_social: Rede social selecionada
            user: Usuário solicitante
            
        Returns:
            dict com success, data ou error
        """
        try:
            # 1. Gerar audit_log_id (simulado - implementar sistema real)
            audit_log_id = uuid.uuid4().hex[:8]
            
            # 2. Buscar marketing_input_summary do n8n_compilation
            marketing_input_summary = ''
            if knowledge_base.n8n_compilation and isinstance(knowledge_base.n8n_compilation, dict):
                marketing_input_summary = knowledge_base.n8n_compilation.get('marketing_input_summary', '')
            
            # 3. Montar payload seguindo formato exato
            payload = {
                "empresa": user.email,
                "usuario": user.email,
                "rede": rede_social,
                "tema": tema,
                "organization_id": knowledge_base.organization.id,
                "audit_log_id": audit_log_id,
                "knowledge_base": {
                    "kb_id": knowledge_base.id,
                    "company_name": knowledge_base.nome_empresa or "",
                    "marketing_input_summary": marketing_input_summary
                },
                "webhookUrl": PautaN8NService.ENDPOINT_WEBHOOK,
                "executionMode": "production"
            }
            
            # 3. Enviar para N8N
            response = requests.post(
                PautaN8NService.ENDPOINT_ENVIO,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': {
                        'payload_sent': payload,
                        'response': response.json() if response.content else {},
                        'audit_log_id': audit_log_id
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'Erro N8N: {response.status_code} - {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Erro de conexão N8N: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }
    
    @staticmethod
    def process_webhook_response(data, organization_id=None, user_id=None):
        """
        Processa resposta do webhook N8N e salva pautas
        
        Args:
            data: Payload recebido do webhook N8N (array de pautas)
            organization_id: ID da organização
            user_id: ID do usuário
            
        Returns:
            dict com success, pautas_salvas ou error
        """
        try:
            # Validar que é um array
            if not isinstance(data, list) or len(data) == 0:
                return {
                    'success': False,
                    'error': 'Payload inválido: esperado array de pautas'
                }
            
            # Buscar organização e usuário
            from apps.core.models import Organization
            from apps.knowledge.models import KnowledgeBase
            from apps.pautas.models import Pauta
            
            if not organization_id:
                return {
                    'success': False,
                    'error': 'organization_id não fornecido'
                }
            
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                return {
                    'success': False,
                    'error': f'Organização {organization_id} não encontrada'
                }
            
            # Buscar knowledge_base
            knowledge_base = KnowledgeBase.objects.filter(organization=organization).first()
            if not knowledge_base:
                return {
                    'success': False,
                    'error': 'Knowledge base não encontrada'
                }
            
            # Buscar usuário
            user = None
            if user_id:
                user = User.objects.filter(id=user_id).first()
            
            if not user:
                # Usar primeiro usuário da organização
                user = User.objects.filter(organization=organization).first()
            
            pautas_salvas = []
            
            # Processar cada pauta do array
            for pauta_info in data:
                # Extrair campos do formato N8N
                titulo = pauta_info.get('_texto_titulo_pauta_sugerido', '')
                descricao = pauta_info.get('_texto_descricao_pauta_sugerido', '')
                status_n8n = pauta_info.get('_status_pauta', 'gerado')
                
                # Criar pauta
                pauta = Pauta.objects.create(
                    organization=organization,
                    knowledge_base=knowledge_base,
                    user=user,
                    title=titulo,
                    content=descricao,
                    rede_social='FACEBOOK',  # TODO: Obter do payload original
                    status='generated',
                    n8n_data=pauta_info
                )
                
                pautas_salvas.append(pauta)
            
            return {
                'success': True,
                'pautas_salvas': pautas_salvas,
                'total': len(pautas_salvas)
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': f'Erro processando webhook: {str(e)}',
                'traceback': traceback.format_exc()
            }
