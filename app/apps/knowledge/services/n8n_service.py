"""
Service Layer para integração com N8N
Responsável por enviar dados da Knowledge Base para análise
"""
import hmac
import hashlib
import time
import json
import uuid
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class N8NService:
    """
    Service para integração segura com N8N
    Implementa autenticação HMAC SHA-256 + Timestamp
    """
    
    @staticmethod
    def _generate_signature(payload: dict, timestamp: int) -> str:
        """
        Gera assinatura HMAC SHA-256 do payload
        
        Args:
            payload: Dados a serem enviados
            timestamp: Unix timestamp
            
        Returns:
            Assinatura hexadecimal
        """
        payload_string = json.dumps(payload, sort_keys=True)
        message = f"{payload_string}{timestamp}"
        
        signature = hmac.new(
            settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    @staticmethod
    def _check_rate_limit(organization_id: int) -> bool:
        """
        Verifica rate limit por organização
        
        Args:
            organization_id: ID da organização
            
        Returns:
            True se dentro do limite, False se excedido
        """
        cache_key = f"n8n_rate_limit_org_{organization_id}"
        current_count = cache.get(cache_key, 0)
        
        limit_str = settings.N8N_RATE_LIMIT_PER_ORG
        max_requests = int(limit_str.split('/')[0])
        
        if current_count >= max_requests:
            logger.warning(
                f"Rate limit exceeded for organization {organization_id}. "
                f"Current: {current_count}, Max: {max_requests}"
            )
            return False
        
        cache.set(cache_key, current_count + 1, 60)
        return True
    
    @staticmethod
    def send_fundamentos(kb_instance) -> dict:
        """
        Envia dados da KB para análise N8N (Fundamentos)
        
        Args:
            kb_instance: Instância de KnowledgeBase
            
        Returns:
            dict com success, revision_id ou error
        """
        try:
            # 1. Verificar rate limit
            if not N8NService._check_rate_limit(kb_instance.organization_id):
                return {
                    'success': False,
                    'error': 'Rate limit exceeded. Try again later.'
                }
            
            # 2. Gerar revision_id (UUID v4 truncado para 16 chars)
            revision_id = uuid.uuid4().hex[:16]
            
            # 3. Atualizar KB com revision_id ANTES de enviar
            kb_instance.analysis_status = 'processing'
            kb_instance.analysis_revision_id = revision_id
            kb_instance.analysis_requested_at = timezone.now()
            kb_instance.save(update_fields=[
                'analysis_status',
                'analysis_revision_id',
                'analysis_requested_at'
            ])
            
            # 4. Montar payload COMPLETO com revision_id
            payload = {
                # Metadados
                'kb_id': kb_instance.id,
                'organization_id': kb_instance.organization_id,
                'organization_name': kb_instance.organization.name,
                'revision_id': revision_id,
                
                # BLOCO 1: Identidade Institucional
                'company_name': kb_instance.nome_empresa or '',
                'mission': kb_instance.missao or '',
                'vision': kb_instance.visao or '',
                'values': kb_instance.valores or '',
                'description': kb_instance.descricao_produto or '',
                
                # BLOCO 2: Públicos & Segmentos
                'target_audience': kb_instance.publico_externo or '',
                'internal_audience': kb_instance.publico_interno or '',
                'internal_segments': kb_instance.segmentos_internos or [],
                
                # BLOCO 3: Posicionamento & Diferenciais
                'positioning': kb_instance.posicionamento or '',
                'value_proposition': kb_instance.proposta_valor or '',
                'differentials': kb_instance.diferenciais or '',
                
                # BLOCO 4: Tom de Voz
                'tone_of_voice': kb_instance.tom_voz_externo or '',
                'internal_tone_of_voice': kb_instance.tom_voz_interno or '',
                'recommended_words': kb_instance.palavras_recomendadas or [],
                'words_to_avoid': kb_instance.palavras_evitar or [],
                
                # BLOCO 5: Identidade Visual
                'palette_colors': [c.hex_code for c in kb_instance.colors.all()],
                'logo_files': [l.s3_url for l in kb_instance.logos.all() if l.s3_url],
                'fonts': [{'name': t.google_font_name or t.custom_font.name if t.custom_font else '', 'url': t.google_font_url or (t.custom_font.s3_url if t.custom_font else '')} for t in kb_instance.typography_settings.all()],
                
                # BLOCO 6: Sites e Redes Sociais
                'website_url': kb_instance.site_institucional or '',
                'social_networks': [{'platform': s.network_type, 'url': s.url} for s in kb_instance.social_networks.all()],
                'competitors': kb_instance.concorrentes or [],
                
                # BLOCO 7: Dados & Insights
                'reference_images': [r.s3_url for r in kb_instance.reference_images.all() if r.s3_url],
                'trusted_sources': kb_instance.fontes_confiaveis or [],
                'trend_channels': kb_instance.canais_trends or [],
            }
            
            # 3. Gerar timestamp e assinatura
            timestamp = int(time.time())
            signature = N8NService._generate_signature(payload, timestamp)
            
            # 4. Preparar headers
            headers = {
                'Content-Type': 'application/json',
                'X-INTERNAL-TOKEN': settings.N8N_WEBHOOK_SECRET,
                'X-Signature': signature,
                'X-Timestamp': str(timestamp),
                'X-Organization-ID': str(kb_instance.organization_id),
                'X-KB-ID': str(kb_instance.id),
            }
            
            # 5. Enviar requisição com retry
            max_retries = settings.N8N_MAX_RETRIES
            retry_delay = settings.N8N_RETRY_DELAY
            
            for attempt in range(max_retries):
                try:
                    logger.info(
                        f"Sending to N8N (attempt {attempt + 1}/{max_retries}). "
                        f"KB: {kb_instance.id}, Org: {kb_instance.organization_id}"
                    )
                    
                    response = requests.post(
                        settings.N8N_WEBHOOK_FUNDAMENTOS,
                        json=payload,
                        headers=headers,
                        timeout=settings.N8N_WEBHOOK_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        # KB já foi atualizada antes do envio
                        logger.info(
                            f"N8N fundamentos sent successfully. "
                            f"KB: {kb_instance.id}, "
                            f"Org: {kb_instance.organization_id}, "
                            f"Revision: {revision_id}"
                        )
                        
                        return {
                            'success': True,
                            'revision_id': revision_id,
                            'message': 'Análise solicitada com sucesso'
                        }
                    
                    # Se não for 200, tentar novamente
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"N8N returned {response.status_code}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                        continue
                    
                    # Última tentativa falhou
                    logger.error(
                        f"N8N fundamentos failed after {max_retries} attempts. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    
                    return {
                        'success': False,
                        'error': f'N8N returned status {response.status_code}'
                    }
                    
                except requests.Timeout:
                    if attempt < max_retries - 1:
                        logger.warning(f"Request timeout. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    
                    logger.error(f"N8N fundamentos timeout after {max_retries} attempts")
                    return {
                        'success': False,
                        'error': 'Request timeout. Try again later.'
                    }
                    
        except Exception as e:
            logger.exception(f"Error sending to N8N: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def send_for_compilation(kb_instance, has_accepted_suggestions: bool) -> dict:
        """
        Envia dados da KB para compilação N8N (após aplicar sugestões).
        
        Args:
            kb_instance: Instância de KnowledgeBase
            has_accepted_suggestions: True se pelo menos 1 sugestão foi aceita
            
        Returns:
            dict com success, flow_type ou error
        """
        try:
            # 1. Verificar rate limit
            if not N8NService._check_rate_limit(kb_instance.organization_id):
                return {
                    'success': False,
                    'error': 'Rate limit exceeded. Try again later.'
                }
            
            # 2. Escolher endpoint baseado em sugestões aceitas
            if has_accepted_suggestions:
                webhook_url = settings.N8N_WEBHOOK_COMPILE_COMSUGEST
                flow_type = "comsugest"
            else:
                webhook_url = settings.N8N_WEBHOOK_COMPILE_SEMSUGEST
                flow_type = "semsugest"
            
            if not webhook_url:
                logger.error(f"Endpoint N8N não configurado para fluxo {flow_type}")
                return {
                    'success': False,
                    'error': f'Endpoint N8N não configurado para fluxo {flow_type}'
                }
            
            # 3. Usar revision_id existente ou gerar novo
            revision_id = kb_instance.analysis_revision_id or uuid.uuid4().hex[:16]
            
            # 4. Montar payload (mesmo formato do fundamentos)
            payload = {
                # Metadados
                'kb_id': kb_instance.id,
                'organization_id': kb_instance.organization_id,
                'organization_name': kb_instance.organization.name,
                'revision_id': revision_id,
                'flow_type': flow_type,
                
                # BLOCO 1: Identidade Institucional
                'company_name': kb_instance.nome_empresa or '',
                'mission': kb_instance.missao or '',
                'vision': kb_instance.visao or '',
                'values': kb_instance.valores or '',
                'description': kb_instance.descricao_produto or '',
                
                # BLOCO 2: Públicos & Segmentos
                'target_audience': kb_instance.publico_externo or '',
                'internal_audience': kb_instance.publico_interno or '',
                'internal_segments': kb_instance.segmentos_internos or [],
                
                # BLOCO 3: Posicionamento & Diferenciais
                'positioning': kb_instance.posicionamento or '',
                'value_proposition': kb_instance.proposta_valor or '',
                'differentials': kb_instance.diferenciais or '',
                
                # BLOCO 4: Tom de Voz
                'tone_of_voice': kb_instance.tom_voz_externo or '',
                'internal_tone_of_voice': kb_instance.tom_voz_interno or '',
                'recommended_words': kb_instance.palavras_recomendadas or [],
                'words_to_avoid': kb_instance.palavras_evitar or [],
                
                # BLOCO 5: Identidade Visual
                'palette_colors': [c.hex_code for c in kb_instance.colors.all()],
                'logo_files': [l.s3_url for l in kb_instance.logos.all() if l.s3_url],
                'fonts': [{'name': t.google_font_name or t.custom_font.name if t.custom_font else '', 'url': t.google_font_url or (t.custom_font.s3_url if t.custom_font else '')} for t in kb_instance.typography_settings.all()],
                
                # BLOCO 6: Sites e Redes Sociais
                'website_url': kb_instance.site_institucional or '',
                'social_networks': [{'platform': s.network_type, 'url': s.url} for s in kb_instance.social_networks.all()],
                'competitors': kb_instance.concorrentes or [],
                
                # BLOCO 7: Dados & Insights
                'reference_images': [r.s3_url for r in kb_instance.reference_images.all() if r.s3_url],
                'trusted_sources': kb_instance.fontes_confiaveis or [],
                'trend_channels': kb_instance.canais_trends or [],
            }
            
            # 5. Gerar timestamp e assinatura
            timestamp = int(time.time())
            signature = N8NService._generate_signature(payload, timestamp)
            
            # 6. Preparar headers
            headers = {
                'Content-Type': 'application/json',
                'X-INTERNAL-TOKEN': settings.N8N_WEBHOOK_SECRET,
                'X-Signature': signature,
                'X-Timestamp': str(timestamp),
                'X-Organization-ID': str(kb_instance.organization_id),
                'X-KB-ID': str(kb_instance.id),
            }
            
            # 7. Atualizar status ANTES de enviar
            kb_instance.compilation_status = 'processing'
            kb_instance.compilation_requested_at = timezone.now()
            kb_instance.save(update_fields=[
                'compilation_status',
                'compilation_requested_at'
            ])
            
            # 8. Enviar requisição com retry
            max_retries = settings.N8N_MAX_RETRIES
            retry_delay = settings.N8N_RETRY_DELAY
            
            for attempt in range(max_retries):
                try:
                    logger.info(
                        f"📤 [N8N_COMPILATION] Enviando para compilação (tentativa {attempt + 1}/{max_retries}). "
                        f"KB: {kb_instance.id}, Org: {kb_instance.organization_id}, Fluxo: {flow_type}"
                    )
                    
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers=headers,
                        timeout=settings.N8N_WEBHOOK_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        logger.info(
                            f"✅ [N8N_COMPILATION] Enviado com sucesso. "
                            f"KB: {kb_instance.id}, "
                            f"Org: {kb_instance.organization_id}, "
                            f"Fluxo: {flow_type}, "
                            f"Revision: {revision_id}"
                        )
                        
                        return {
                            'success': True,
                            'flow_type': flow_type,
                            'revision_id': revision_id,
                            'message': f'Dados enviados para compilação ({flow_type})'
                        }
                    
                    # Se não for 200, tentar novamente
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️ [N8N_COMPILATION] N8N retornou {response.status_code}. "
                            f"Tentando novamente em {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                        continue
                    
                    # Última tentativa falhou
                    logger.error(
                        f"❌ [N8N_COMPILATION] Falhou após {max_retries} tentativas. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    
                    kb_instance.compilation_status = 'error'
                    kb_instance.save(update_fields=['compilation_status'])
                    
                    return {
                        'success': False,
                        'error': f'N8N retornou status {response.status_code}'
                    }
                    
                except requests.Timeout:
                    if attempt < max_retries - 1:
                        logger.warning(f"⏱️ [N8N_COMPILATION] Timeout. Tentando novamente em {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    
                    logger.error(f"❌ [N8N_COMPILATION] Timeout após {max_retries} tentativas")
                    
                    kb_instance.compilation_status = 'error'
                    kb_instance.save(update_fields=['compilation_status'])
                    
                    return {
                        'success': False,
                        'error': 'Request timeout. Tente novamente mais tarde.'
                    }
                    
        except Exception as e:
            logger.exception(f"❌ [N8N_COMPILATION] Erro ao enviar para N8N: {str(e)}")
            
            kb_instance.compilation_status = 'error'
            kb_instance.save(update_fields=['compilation_status'])
            
            return {
                'success': False,
                'error': str(e)
            }
