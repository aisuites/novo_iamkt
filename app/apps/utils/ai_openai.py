"""
IAMKT - OpenAI Integration
Funções para GPT-4 (texto) e DALL-E 3 (imagens)
"""
import logging
from openai import OpenAI
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenAIManager:
    """Gerenciador de operações com OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_text = settings.OPENAI_MODEL_TEXT
        self.model_image = settings.OPENAI_MODEL_IMAGE
    
    def generate_text(self, prompt, system_prompt=None, max_tokens=2000, temperature=0.7):
        """
        Gera texto usando GPT-4
        
        Args:
            prompt: Prompt do usuário
            system_prompt: Instruções do sistema
            max_tokens: Máximo de tokens na resposta
            temperature: Criatividade (0-2)
        
        Returns:
            dict: {
                'success': bool,
                'text': str,
                'tokens_input': int,
                'tokens_output': int,
                'tokens_total': int,
                'model': str,
                'error': str
            }
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            started_at = datetime.now()
            
            response = self.client.chat.completions.create(
                model=self.model_text,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            result = {
                'success': True,
                'text': response.choices[0].message.content,
                'tokens_input': response.usage.prompt_tokens,
                'tokens_output': response.usage.completion_tokens,
                'tokens_total': response.usage.total_tokens,
                'model': response.model,
                'execution_time': execution_time,
                'error': None
            }
            
            logger.info(f"Texto gerado com GPT-4: {result['tokens_total']} tokens em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao gerar texto com OpenAI: {e}")
            return {
                'success': False,
                'text': None,
                'tokens_input': 0,
                'tokens_output': 0,
                'tokens_total': 0,
                'model': self.model_text,
                'execution_time': 0,
                'error': str(e)
            }
    
    def generate_image(self, prompt, size="1024x1024", quality="standard", style="vivid"):
        """
        Gera imagem usando DALL-E 3
        
        Args:
            prompt: Descrição da imagem
            size: Tamanho (1024x1024, 1024x1792, 1792x1024)
            quality: Qualidade (standard, hd)
            style: Estilo (vivid, natural)
        
        Returns:
            dict: {
                'success': bool,
                'url': str,
                'revised_prompt': str,
                'model': str,
                'error': str
            }
        """
        try:
            started_at = datetime.now()
            
            response = self.client.images.generate(
                model=self.model_image,
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1
            )
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            result = {
                'success': True,
                'url': response.data[0].url,
                'revised_prompt': response.data[0].revised_prompt,
                'model': self.model_image,
                'size': size,
                'quality': quality,
                'execution_time': execution_time,
                'error': None
            }
            
            logger.info(f"Imagem gerada com DALL-E 3 em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao gerar imagem com OpenAI: {e}")
            return {
                'success': False,
                'url': None,
                'revised_prompt': None,
                'model': self.model_image,
                'size': size,
                'quality': quality,
                'execution_time': 0,
                'error': str(e)
            }
    
    def generate_pauta(self, theme, audience, objective, knowledge_base_context):
        """
        Gera pauta de conteúdo baseada na Base FEMME
        
        Args:
            theme: Tema da pauta
            audience: Público-alvo
            objective: Objetivo do conteúdo
            knowledge_base_context: Contexto da Base de Conhecimento FEMME
        
        Returns:
            dict: Resultado da geração
        """
        system_prompt = f"""Você é um especialista em marketing de conteúdo da FEMME.
        
Contexto da Empresa:
{knowledge_base_context}

Sua tarefa é criar uma pauta de conteúdo estratégica e alinhada com a identidade da FEMME."""
        
        user_prompt = f"""Crie uma pauta de conteúdo com os seguintes parâmetros:

Tema: {theme}
Público-alvo: {audience}
Objetivo: {objective}

A pauta deve conter:
1. Título atrativo
2. Descrição detalhada (3-4 parágrafos)
3. Pontos-chave a abordar (5-7 itens)
4. Formatos sugeridos (posts, stories, vídeos, etc.)
5. Hashtags relevantes

Mantenha o tom de voz e linguagem da FEMME."""
        
        return self.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.8
        )
    
    def generate_caption(self, pauta_content, social_network, knowledge_base_context):
        """
        Gera legenda para post baseada na pauta
        
        Args:
            pauta_content: Conteúdo da pauta
            social_network: Rede social (instagram, linkedin, facebook)
            knowledge_base_context: Contexto da Base FEMME
        
        Returns:
            dict: Resultado da geração
        """
        network_specs = {
            'instagram': 'Instagram (máx 2200 caracteres, use emojis, hashtags no final)',
            'linkedin': 'LinkedIn (tom profissional, máx 3000 caracteres)',
            'facebook': 'Facebook (tom conversacional, máx 63206 caracteres)',
            'twitter': 'Twitter/X (máx 280 caracteres, direto ao ponto)'
        }
        
        network_spec = network_specs.get(social_network, network_specs['instagram'])
        
        system_prompt = f"""Você é um copywriter especializado em redes sociais da FEMME.

Contexto da Empresa:
{knowledge_base_context}

Crie legendas autênticas e engajadoras que reflitam a identidade da FEMME."""
        
        user_prompt = f"""Com base na seguinte pauta, crie uma legenda para {network_spec}:

{pauta_content}

A legenda deve:
- Ser autêntica e alinhada com o tom de voz da FEMME
- Gerar engajamento
- Incluir call-to-action quando apropriado
- Usar hashtags estratégicas (se aplicável)"""
        
        return self.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=800,
            temperature=0.7
        )


# Instância global
openai_manager = OpenAIManager()


def generate_text_gpt(prompt, system_prompt=None, max_tokens=2000, temperature=0.7):
    """Atalho para geração de texto"""
    return openai_manager.generate_text(prompt, system_prompt, max_tokens, temperature)


def generate_image_dalle(prompt, size="1024x1024", quality="standard"):
    """Atalho para geração de imagem"""
    return openai_manager.generate_image(prompt, size, quality)
