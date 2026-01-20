"""
IAMKT - Redis Cache Utilities
Funções para cache de respostas de IA e otimização de performance
"""
import logging
import hashlib
import json
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Gerenciador de cache Redis"""
    
    def __init__(self):
        self.default_ttl = getattr(settings, 'IA_CACHE_TTL', 2592000)  # 30 dias
    
    def generate_cache_key(self, prefix, *args, **kwargs):
        """
        Gera chave de cache única baseada nos parâmetros
        
        Args:
            prefix: Prefixo da chave (ex: 'openai', 'gemini')
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
        
        Returns:
            str: Chave de cache única
        """
        # Combinar todos os parâmetros
        params = {
            'args': args,
            'kwargs': kwargs
        }
        
        # Serializar e criar hash
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        
        return f"{prefix}:{params_hash}"
    
    def get_cached_response(self, cache_key):
        """
        Recupera resposta do cache
        
        Args:
            cache_key: Chave do cache
        
        Returns:
            dict ou None: Resposta cacheada ou None se não existir
        """
        try:
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.info(f"Cache HIT: {cache_key}")
                return cached_data
            
            logger.info(f"Cache MISS: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao recuperar cache: {e}")
            return None
    
    def set_cached_response(self, cache_key, data, ttl=None):
        """
        Armazena resposta no cache
        
        Args:
            cache_key: Chave do cache
            data: Dados a serem cacheados
            ttl: Tempo de vida em segundos (None = usar padrão)
        
        Returns:
            bool: True se armazenado com sucesso
        """
        try:
            if ttl is None:
                ttl = self.default_ttl
            
            cache.set(cache_key, data, ttl)
            logger.info(f"Cache SET: {cache_key} (TTL: {ttl}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao armazenar cache: {e}")
            return False
    
    def delete_cached_response(self, cache_key):
        """
        Remove resposta do cache
        
        Args:
            cache_key: Chave do cache
        
        Returns:
            bool: True se removido com sucesso
        """
        try:
            cache.delete(cache_key)
            logger.info(f"Cache DELETE: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao deletar cache: {e}")
            return False
    
    def clear_pattern(self, pattern):
        """
        Remove todas as chaves que correspondem ao padrão
        
        Args:
            pattern: Padrão de busca (ex: 'openai:*')
        
        Returns:
            int: Número de chaves removidas
        """
        try:
            # Nota: Esta funcionalidade depende do backend Redis
            from django.core.cache import caches
            redis_cache = caches['default']
            
            if hasattr(redis_cache, 'delete_pattern'):
                count = redis_cache.delete_pattern(pattern)
                logger.info(f"Cache CLEAR PATTERN: {pattern} ({count} chaves)")
                return count
            else:
                logger.warning("Backend de cache não suporta delete_pattern")
                return 0
                
        except Exception as e:
            logger.error(f"Erro ao limpar cache por padrão: {e}")
            return 0


# Instância global
cache_manager = CacheManager()


def cache_ai_response(provider, operation, params, response_data, ttl=None):
    """
    Cache de resposta de IA
    
    Args:
        provider: Provedor (openai, gemini, perplexity)
        operation: Operação (generate_text, generate_image, etc)
        params: Parâmetros da chamada
        response_data: Dados da resposta
        ttl: Tempo de vida (opcional)
    
    Returns:
        bool: True se cacheado com sucesso
    """
    cache_key = cache_manager.generate_cache_key(
        f"ai:{provider}:{operation}",
        **params
    )
    
    return cache_manager.set_cached_response(cache_key, response_data, ttl)


def get_cached_ai_response(provider, operation, params):
    """
    Recupera resposta de IA do cache
    
    Args:
        provider: Provedor (openai, gemini, perplexity)
        operation: Operação (generate_text, generate_image, etc)
        params: Parâmetros da chamada
    
    Returns:
        dict ou None: Resposta cacheada ou None
    """
    cache_key = cache_manager.generate_cache_key(
        f"ai:{provider}:{operation}",
        **params
    )
    
    return cache_manager.get_cached_response(cache_key)


def clear_ai_cache(provider=None):
    """
    Limpa cache de IA
    
    Args:
        provider: Provedor específico ou None para todos
    
    Returns:
        int: Número de chaves removidas
    """
    if provider:
        pattern = f"ai:{provider}:*"
    else:
        pattern = "ai:*"
    
    return cache_manager.clear_pattern(pattern)
