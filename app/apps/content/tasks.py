"""
IAMKT - Celery Tasks
Tasks assíncronas para geração de conteúdo
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db import models
from datetime import datetime

from apps.content.models import (
    Pauta, GeneratedContent, IAModelUsage, ContentMetrics, TrendMonitor
)
from apps.knowledge.models import KnowledgeBase
from apps.utils.ai_openai import openai_manager
from apps.utils.ai_gemini import gemini_manager
from apps.utils.ai_perplexity import perplexity_manager
from apps.utils.cache import get_cached_ai_response, cache_ai_response
from apps.utils.s3 import upload_to_s3

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_pauta_task(self, pauta_id):
    """
    Task assíncrona para geração de pauta
    
    Args:
        pauta_id: ID da pauta a ser gerada
    
    Returns:
        dict: Resultado da geração
    """
    try:
        pauta = Pauta.objects.get(id=pauta_id)
        pauta.status = 'processing'
        pauta.save()
        
        logger.info(f"Iniciando geração de pauta #{pauta_id}")
        
        # 1. Obter contexto da Base de Conhecimento
        try:
            kb = KnowledgeBase.objects.first()
            if not kb:
                raise Exception("Base de Conhecimento não encontrada")
            
            kb_context = f"""
Empresa: {kb.nome_empresa}
Missão: {kb.missao}
Visão: {kb.visao}
Valores: {kb.valores}
Posicionamento: {kb.posicionamento}
Tom de Voz Externo: {kb.tom_voz_externo}
Público Externo: {kb.publico_externo}
"""
        except Exception as e:
            logger.warning(f"Erro ao obter Base de Conhecimento: {e}")
            kb_context = "Contexto não disponível"
        
        # 2. Pesquisa web com Perplexity (se disponível)
        research_data = None
        if pauta.theme:
            cache_key_params = {
                'theme': pauta.theme,
                'audience': pauta.target_audience,
                'objective': pauta.objective
            }
            
            research_data = get_cached_ai_response('perplexity', 'research', cache_key_params)
            
            if not research_data:
                logger.info("Realizando pesquisa web com Perplexity")
                research_result = perplexity_manager.research_for_pauta(
                    pauta.theme,
                    pauta.target_audience,
                    pauta.objective
                )
                
                if research_result['success']:
                    research_data = research_result
                    cache_ai_response('perplexity', 'research', cache_key_params, research_data)
                    
                    # Registrar uso de IA
                    IAModelUsage.objects.create(
                        user=pauta.user,
                        area=pauta.area,
                        provider='perplexity',
                        model=research_result['model'],
                        operation='web_research',
                        tokens_total=research_result.get('tokens_total', 0),
                        cost_usd=0.0,  # Calcular custo real
                        started_at=timezone.now(),
                        completed_at=timezone.now(),
                        status='completed'
                    )
        
        # 3. Geração de pauta com OpenAI
        cache_key_params = {
            'theme': pauta.theme,
            'audience': pauta.target_audience,
            'objective': pauta.objective,
            'context': pauta.additional_context,
            'kb_hash': hash(kb_context)
        }
        
        pauta_result = get_cached_ai_response('openai', 'generate_pauta', cache_key_params)
        
        if not pauta_result:
            logger.info("Gerando pauta com OpenAI GPT-4")
            
            # Enriquecer prompt com pesquisa
            research_context = ""
            if research_data and research_data.get('answer'):
                research_context = f"\n\nPesquisa Web Recente:\n{research_data['answer']}"
            
            pauta_result = openai_manager.generate_pauta(
                theme=pauta.theme,
                audience=pauta.target_audience,
                objective=pauta.objective,
                knowledge_base_context=kb_context + research_context
            )
            
            if pauta_result['success']:
                cache_ai_response('openai', 'generate_pauta', cache_key_params, pauta_result)
                
                # Registrar uso de IA
                IAModelUsage.objects.create(
                    user=pauta.user,
                    area=pauta.area,
                    provider='openai',
                    model=pauta_result['model'],
                    operation='generate_pauta',
                    tokens_input=pauta_result['tokens_input'],
                    tokens_output=pauta_result['tokens_output'],
                    tokens_total=pauta_result['tokens_total'],
                    cost_usd=pauta_result['tokens_total'] * 0.00003,  # Custo aproximado GPT-4
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    status='completed'
                )
        
        # 4. Processar resultado e atualizar pauta
        if pauta_result and pauta_result['success']:
            generated_text = pauta_result['text']
            
            # Parse do texto gerado (simplificado)
            lines = generated_text.split('\n')
            title = lines[0].replace('#', '').strip() if lines else pauta.theme
            
            pauta.title = title[:200]
            pauta.description = generated_text
            pauta.status = 'completed'
            pauta.completed_at = timezone.now()
            
            # Adicionar fontes de pesquisa
            if research_data and research_data.get('sources'):
                pauta.research_sources = research_data['sources']
            
            pauta.save()
            
            logger.info(f"Pauta #{pauta_id} gerada com sucesso")
            
            return {
                'success': True,
                'pauta_id': pauta_id,
                'title': title
            }
        else:
            raise Exception(pauta_result.get('error', 'Erro desconhecido'))
        
    except Pauta.DoesNotExist:
        logger.error(f"Pauta #{pauta_id} não encontrada")
        return {'success': False, 'error': 'Pauta não encontrada'}
        
    except Exception as e:
        logger.error(f"Erro ao gerar pauta #{pauta_id}: {e}")
        
        try:
            pauta = Pauta.objects.get(id=pauta_id)
            pauta.status = 'error'
            pauta.error_message = str(e)
            pauta.save()
        except:
            pass
        
        # Retry com backoff exponencial
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def generate_post_task(self, content_id, provider='openai'):
    """
    Task assíncrona para geração de post (legenda + imagem)
    
    Args:
        content_id: ID do GeneratedContent
        provider: Provider de IA ('openai' ou 'gemini')
    
    Returns:
        dict: Resultado da geração
    """
    try:
        content = GeneratedContent.objects.get(id=content_id)
        content.status = 'processing'
        content.save()
        
        logger.info(f"Iniciando geração de post #{content_id} com {provider}")
        
        # Iniciar métricas
        metrics, _ = ContentMetrics.objects.get_or_create(content=content)
        metrics.creation_started_at = timezone.now()
        metrics.save()
        
        # 1. Obter contexto da Base de Conhecimento
        try:
            kb = KnowledgeBase.objects.first()
            kb_context = f"""
Empresa: {kb.nome_empresa}
Tom de Voz: {kb.tom_voz_externo}
Público: {kb.publico_externo}
Palavras Recomendadas: {kb.palavras_recomendadas}
Palavras a Evitar: {kb.palavras_evitar}
"""
        except:
            kb_context = "Contexto não disponível"
        
        # 2. Obter conteúdo da pauta (se existir)
        pauta_content = ""
        if content.pauta:
            pauta_content = f"{content.pauta.title}\n\n{content.pauta.description}"
        
        # 3. Gerar legenda
        if provider == 'openai':
            caption_result = openai_manager.generate_caption(
                pauta_content=pauta_content,
                social_network=content.social_network,
                knowledge_base_context=kb_context
            )
            content.ia_model_text = caption_result.get('model', 'gpt-4')
        else:  # gemini
            caption_result = gemini_manager.generate_caption(
                pauta_content=pauta_content,
                social_network=content.social_network,
                knowledge_base_context=kb_context
            )
            content.ia_model_text = caption_result.get('model', 'gemini-pro')
        
        if not caption_result['success']:
            raise Exception(f"Erro ao gerar legenda: {caption_result.get('error')}")
        
        content.caption = caption_result['text']
        
        # Registrar uso de IA (texto)
        IAModelUsage.objects.create(
            user=content.user,
            area=content.area,
            content=content,
            provider=provider,
            model=content.ia_model_text,
            operation='generate_caption',
            tokens_input=caption_result.get('tokens_input', 0),
            tokens_output=caption_result.get('tokens_output', 0),
            tokens_total=caption_result.get('tokens_total', 0),
            cost_usd=caption_result.get('tokens_total', 0) * 0.00003,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            status='completed'
        )
        
        # 4. Gerar imagem (sempre com DALL-E 3)
        if content.has_image:
            # Criar prompt de imagem
            image_prompt = f"Create a professional social media image for {content.social_network}. Theme: {pauta_content[:200]}"
            
            # Otimizar prompt com Gemini (opcional)
            if provider == 'gemini':
                optimized = gemini_manager.generate_image_description(image_prompt)
                if optimized['success']:
                    image_prompt = optimized['optimized_prompt']
            
            # Gerar imagem com DALL-E 3
            image_result = openai_manager.generate_image(
                prompt=image_prompt,
                size="1024x1024",
                quality="standard"
            )
            
            if image_result['success']:
                content.image_prompt = image_result['revised_prompt']
                content.ia_model_image = image_result['model']
                
                # Download e upload para S3 (simplificado - implementar download real)
                # Por enquanto, apenas salvar URL temporária
                content.image_s3_url = image_result['url']
                content.image_width = 1024
                content.image_height = 1024
                
                # Registrar uso de IA (imagem)
                IAModelUsage.objects.create(
                    user=content.user,
                    area=content.area,
                    content=content,
                    provider='openai',
                    model=content.ia_model_image,
                    operation='generate_image',
                    tokens_total=0,  # DALL-E não usa tokens
                    cost_usd=0.04,  # Custo fixo DALL-E 3 standard 1024x1024
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    status='completed'
                )
        
        # 5. Finalizar
        content.status = 'draft'
        content.save()
        
        # Atualizar métricas
        metrics.creation_completed_at = timezone.now()
        metrics.creation_duration_seconds = (
            metrics.creation_completed_at - metrics.creation_started_at
        ).total_seconds()
        
        # Calcular custo total
        total_cost = IAModelUsage.objects.filter(content=content).aggregate(
            total=models.Sum('cost_usd')
        )['total'] or 0
        metrics.total_cost_usd = total_cost
        
        # Calcular tokens total
        total_tokens = IAModelUsage.objects.filter(content=content).aggregate(
            total=models.Sum('tokens_total')
        )['total'] or 0
        metrics.total_tokens = total_tokens
        
        metrics.save()
        
        logger.info(f"Post #{content_id} gerado com sucesso")
        
        return {
            'success': True,
            'content_id': content_id,
            'caption_length': len(content.caption),
            'has_image': content.has_image
        }
        
    except GeneratedContent.DoesNotExist:
        logger.error(f"Content #{content_id} não encontrado")
        return {'success': False, 'error': 'Content não encontrado'}
        
    except Exception as e:
        logger.error(f"Erro ao gerar post #{content_id}: {e}")
        
        try:
            content = GeneratedContent.objects.get(id=content_id)
            content.status = 'error'
            content.save()
        except:
            pass
        
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def monitor_trends_task():
    """
    Task periódica para monitoramento de trends
    Executada diariamente via Celery Beat
    """
    try:
        logger.info("Iniciando monitoramento de trends")
        
        # Obter palavras-chave da Base de Conhecimento
        try:
            kb = KnowledgeBase.objects.first()
            keywords = kb.palavras_chave_trends if kb else []
        except:
            keywords = []
        
        if not keywords:
            logger.warning("Nenhuma palavra-chave configurada para monitoramento")
            return {'success': False, 'error': 'Sem palavras-chave'}
        
        trends_created = 0
        
        for keyword in keywords[:10]:  # Limitar a 10 por execução
            # Pesquisar tendências com Perplexity
            result = perplexity_manager.get_trending_topics(
                industry=keyword,
                region="Brasil"
            )
            
            if result['success']:
                # Criar registro de trend
                trend = TrendMonitor.objects.create(
                    keyword=keyword,
                    source='perplexity',
                    trend_score=80,  # Score fictício - implementar cálculo real
                    ia_analysis=result['answer'],
                    relevance='medium',
                    is_active=True
                )
                
                trends_created += 1
                logger.info(f"Trend criado: {keyword}")
        
        logger.info(f"Monitoramento concluído: {trends_created} trends criados")
        
        return {
            'success': True,
            'trends_created': trends_created
        }
        
    except Exception as e:
        logger.error(f"Erro no monitoramento de trends: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_cache_task():
    """
    Task periódica para limpeza de cache antigo
    Executada semanalmente
    """
    try:
        from apps.utils.cache import cache_manager
        
        logger.info("Iniciando limpeza de cache")
        
        # Limpar cache de IA com mais de 30 dias
        # Implementação depende do backend Redis
        
        logger.info("Limpeza de cache concluída")
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Erro na limpeza de cache: {e}")
        return {'success': False, 'error': str(e)}
