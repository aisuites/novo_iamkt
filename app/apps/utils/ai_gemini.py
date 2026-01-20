"""
IAMKT - Google Gemini Integration
Funções para Gemini Pro (texto e visão)
"""
import logging
import google.generativeai as genai
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class GeminiManager:
    """Gerenciador de operações com Google Gemini"""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_text = genai.GenerativeModel(settings.GEMINI_MODEL_TEXT)
        self.model_vision = genai.GenerativeModel(settings.GEMINI_MODEL_IMAGE)
    
    def generate_text(self, prompt, max_tokens=2000, temperature=0.7):
        """
        Gera texto usando Gemini Pro
        
        Args:
            prompt: Prompt do usuário
            max_tokens: Máximo de tokens na resposta
            temperature: Criatividade (0-1)
        
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
            started_at = datetime.now()
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
            
            response = self.model_text.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            # Gemini não retorna contagem de tokens detalhada por padrão
            # Estimativa aproximada
            tokens_input = len(prompt.split()) * 1.3  # Aproximação
            tokens_output = len(response.text.split()) * 1.3
            
            result = {
                'success': True,
                'text': response.text,
                'tokens_input': int(tokens_input),
                'tokens_output': int(tokens_output),
                'tokens_total': int(tokens_input + tokens_output),
                'model': settings.GEMINI_MODEL_TEXT,
                'execution_time': execution_time,
                'error': None
            }
            
            logger.info(f"Texto gerado com Gemini Pro em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao gerar texto com Gemini: {e}")
            return {
                'success': False,
                'text': None,
                'tokens_input': 0,
                'tokens_output': 0,
                'tokens_total': 0,
                'model': settings.GEMINI_MODEL_TEXT,
                'execution_time': 0,
                'error': str(e)
            }
    
    def generate_image_description(self, prompt):
        """
        Gera descrição detalhada para criação de imagem
        Gemini não gera imagens diretamente, mas pode criar prompts otimizados
        
        Args:
            prompt: Descrição básica da imagem desejada
        
        Returns:
            dict: Resultado com prompt otimizado para DALL-E
        """
        try:
            enhanced_prompt = f"""Como especialista em prompts para geração de imagens, crie uma descrição detalhada e otimizada para DALL-E 3 baseada nesta solicitação:

{prompt}

A descrição deve:
- Ser específica e detalhada
- Incluir estilo visual, cores, composição
- Especificar qualidade e atmosfera
- Ser em inglês (idioma nativo do DALL-E)
- Ter entre 100-200 palavras

Retorne APENAS a descrição otimizada, sem explicações adicionais."""
            
            result = self.generate_text(enhanced_prompt, max_tokens=500, temperature=0.8)
            
            if result['success']:
                result['optimized_prompt'] = result['text']
                logger.info("Prompt de imagem otimizado com Gemini")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao otimizar prompt de imagem: {e}")
            return {
                'success': False,
                'text': None,
                'optimized_prompt': None,
                'error': str(e)
            }
    
    def generate_caption(self, pauta_content, social_network, knowledge_base_context):
        """
        Gera legenda para post usando Gemini
        
        Args:
            pauta_content: Conteúdo da pauta
            social_network: Rede social
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
        
        prompt = f"""Você é um copywriter especializado em redes sociais da FEMME.

Contexto da Empresa:
{knowledge_base_context}

Com base na seguinte pauta, crie uma legenda para {network_spec}:

{pauta_content}

A legenda deve:
- Ser autêntica e alinhada com o tom de voz da FEMME
- Gerar engajamento
- Incluir call-to-action quando apropriado
- Usar hashtags estratégicas (se aplicável)

Retorne APENAS a legenda, sem explicações adicionais."""
        
        return self.generate_text(prompt, max_tokens=800, temperature=0.7)
    
    def analyze_image(self, image_path, prompt):
        """
        Analisa imagem usando Gemini Pro Vision
        
        Args:
            image_path: Caminho da imagem
            prompt: Pergunta sobre a imagem
        
        Returns:
            dict: Resultado da análise
        """
        try:
            import PIL.Image
            
            started_at = datetime.now()
            
            img = PIL.Image.open(image_path)
            
            response = self.model_vision.generate_content([prompt, img])
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            result = {
                'success': True,
                'analysis': response.text,
                'model': settings.GEMINI_MODEL_IMAGE,
                'execution_time': execution_time,
                'error': None
            }
            
            logger.info(f"Imagem analisada com Gemini Vision em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao analisar imagem com Gemini: {e}")
            return {
                'success': False,
                'analysis': None,
                'model': settings.GEMINI_MODEL_IMAGE,
                'execution_time': 0,
                'error': str(e)
            }


# Instância global
gemini_manager = GeminiManager()


def generate_text_gemini(prompt, max_tokens=2000, temperature=0.7):
    """Atalho para geração de texto"""
    return gemini_manager.generate_text(prompt, max_tokens, temperature)


def optimize_image_prompt(prompt):
    """Atalho para otimizar prompt de imagem"""
    return gemini_manager.generate_image_description(prompt)
