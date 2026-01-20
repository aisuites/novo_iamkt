"""
IAMKT - Perplexity AI Integration
Funções para pesquisa web e insights em tempo real
"""
import logging
import httpx
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class PerplexityManager:
    """Gerenciador de operações com Perplexity AI"""
    
    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY
        self.model = settings.PERPLEXITY_MODEL
        self.base_url = "https://api.perplexity.ai/chat/completions"
    
    def search_web(self, query, max_tokens=1500):
        """
        Realiza pesquisa web e retorna insights
        
        Args:
            query: Pergunta ou tema de pesquisa
            max_tokens: Máximo de tokens na resposta
        
        Returns:
            dict: {
                'success': bool,
                'answer': str,
                'sources': list,
                'tokens_total': int,
                'model': str,
                'error': str
            }
        """
        try:
            started_at = datetime.now()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é um assistente de pesquisa especializado. Forneça informações precisas e atualizadas com base em fontes confiáveis da web."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "return_citations": True
            }
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            answer = data['choices'][0]['message']['content']
            
            # Extrair citações se disponíveis
            sources = []
            if 'citations' in data:
                sources = data['citations']
            
            result = {
                'success': True,
                'answer': answer,
                'sources': sources,
                'tokens_total': data.get('usage', {}).get('total_tokens', 0),
                'model': self.model,
                'execution_time': execution_time,
                'error': None
            }
            
            logger.info(f"Pesquisa web realizada com Perplexity em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao realizar pesquisa com Perplexity: {e}")
            return {
                'success': False,
                'answer': None,
                'sources': [],
                'tokens_total': 0,
                'model': self.model,
                'execution_time': 0,
                'error': str(e)
            }
    
    def research_for_pauta(self, theme, audience, objective):
        """
        Realiza pesquisa web para enriquecer pauta
        
        Args:
            theme: Tema da pauta
            audience: Público-alvo
            objective: Objetivo do conteúdo
        
        Returns:
            dict: Resultado da pesquisa
        """
        query = f"""Pesquise informações atualizadas sobre o tema "{theme}" 
considerando o público-alvo "{audience}" e objetivo "{objective}".

Forneça:
1. Tendências atuais relacionadas ao tema
2. Dados e estatísticas relevantes
3. Exemplos de sucesso
4. Insights do mercado
5. Palavras-chave em alta

Seja específico e cite as fontes."""
        
        return self.search_web(query, max_tokens=2000)
    
    def research_competitor(self, competitor_name, focus_areas=None):
        """
        Pesquisa informações sobre concorrente
        
        Args:
            competitor_name: Nome do concorrente
            focus_areas: Lista de áreas de foco (opcional)
        
        Returns:
            dict: Resultado da pesquisa
        """
        focus = ""
        if focus_areas:
            focus = f"Foque especialmente em: {', '.join(focus_areas)}."
        
        query = f"""Pesquise informações atualizadas sobre a empresa "{competitor_name}".

Forneça:
1. Posicionamento de mercado
2. Principais produtos/serviços
3. Estratégias de marketing recentes
4. Presença em redes sociais
5. Diferenciais competitivos

{focus}

Cite as fontes das informações."""
        
        return self.search_web(query, max_tokens=2000)
    
    def get_trending_topics(self, industry, region="Brasil"):
        """
        Busca tópicos em alta em determinada indústria
        
        Args:
            industry: Setor/indústria
            region: Região geográfica
        
        Returns:
            dict: Resultado da pesquisa
        """
        query = f"""Quais são os tópicos e tendências mais relevantes no setor de {industry} 
em {region} atualmente?

Liste:
1. Top 5 tendências do momento
2. Hashtags populares relacionadas
3. Eventos ou notícias recentes importantes
4. Oportunidades de conteúdo

Seja específico e atual."""
        
        return self.search_web(query, max_tokens=1500)
    
    def validate_information(self, claim):
        """
        Valida uma informação ou afirmação
        
        Args:
            claim: Afirmação a ser validada
        
        Returns:
            dict: Resultado da validação
        """
        query = f"""Verifique a veracidade da seguinte afirmação:

"{claim}"

Forneça:
1. Verificação (verdadeiro/falso/parcialmente verdadeiro)
2. Fontes confiáveis que confirmam ou refutam
3. Contexto adicional relevante
4. Data das informações

Seja objetivo e cite fontes."""
        
        return self.search_web(query, max_tokens=1000)


# Instância global
perplexity_manager = PerplexityManager()


def search_web_perplexity(query, max_tokens=1500):
    """Atalho para pesquisa web"""
    return perplexity_manager.search_web(query, max_tokens)


def research_for_content(theme, audience, objective):
    """Atalho para pesquisa para pauta"""
    return perplexity_manager.research_for_pauta(theme, audience, objective)
