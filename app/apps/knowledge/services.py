"""
Knowledge Base - Service Layer
Centraliza lógica de negócio para manter views limpas
"""
import re
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.contrib import messages

from .models import KnowledgeBase, ColorPalette, CustomFont, SocialNetwork


class ValidationError(Exception):
    """Erro de validação customizado"""
    pass


class ColorService:
    """Serviço para gerenciar paleta de cores"""
    
    @staticmethod
    def generate_color_name(hex_code: str) -> str:
        """
        Gera nome descritivo baseado no código HEX
        Ex: #FF0000 -> Vermelho, #00FF00 -> Verde, #0000FF -> Azul
        """
        # Converter HEX para RGB
        hex_code = hex_code.lstrip('#')
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        
        # Calcular luminosidade
        luminosity = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        # Determinar cor base
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        
        # Tons de cinza
        if max_val - min_val < 30:
            if luminosity > 0.9:
                return "Branco"
            elif luminosity > 0.7:
                return "Cinza Claro"
            elif luminosity > 0.4:
                return "Cinza Médio"
            elif luminosity > 0.2:
                return "Cinza Escuro"
            else:
                return "Preto"
        
        # Cores cromáticas
        color_name = ""
        if r > g and r > b:
            if g > b + 50:
                color_name = "Laranja"
            elif b > g + 30:
                color_name = "Rosa"
            else:
                color_name = "Vermelho"
        elif g > r and g > b:
            if r > b + 50:
                color_name = "Amarelo"
            elif b > r + 30:
                color_name = "Ciano"
            else:
                color_name = "Verde"
        elif b > r and b > g:
            if r > g + 30:
                color_name = "Roxo"
            elif g > r + 30:
                color_name = "Azul Turquesa"
            else:
                color_name = "Azul"
        else:
            color_name = "Cor"
        
        # Adicionar modificador de luminosidade
        if luminosity > 0.7:
            return f"{color_name} Claro"
        elif luminosity < 0.3:
            return f"{color_name} Escuro"
        else:
            return color_name
    
    @staticmethod
    def validate_hex_color(hex_code: str) -> Tuple[bool, Optional[str]]:
        """
        Valida código HEX de cor
        
        Args:
            hex_code: Código HEX a validar (ex: #FF5733)
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not hex_code:
            return False, "Código HEX não pode ser vazio"
        
        # Remover espaços
        hex_code = hex_code.strip()
        
        # Verificar se começa com #
        if not hex_code.startswith('#'):
            return False, "Código HEX deve começar com #"
        
        # Verificar formato #RRGGBB
        pattern = r'^#[0-9A-Fa-f]{6}$'
        if not re.match(pattern, hex_code):
            return False, "Código HEX deve estar no formato #RRGGBB (ex: #FF5733)"
        
        return True, None
    
    @staticmethod
    def normalize_hex_color(hex_code: str) -> str:
        """Normaliza código HEX para uppercase"""
        return hex_code.strip().upper()
    
    @staticmethod
    @transaction.atomic
    def process_colors(request, kb: KnowledgeBase) -> Tuple[int, List[str]]:
        """
        Processa e salva cores da paleta
        
        Args:
            request: HttpRequest com POST data
            kb: Instância KnowledgeBase
            
        Returns:
            Tuple (colors_created, errors)
        """
        errors = []
        colors_created = 0
        
        # DEBUG: Verificar quais chaves estão no POST
        post_keys = [k for k in request.POST.keys() if 'cor' in k.lower()]
        print(f"🎨 DEBUG ColorService - POST keys com 'cor': {post_keys}", flush=True)
        
        # Limpar cores existentes
        deleted_count = kb.colors.all().delete()
        print(f"🗑️  Removidas {deleted_count[0] if deleted_count else 0} cores existentes", flush=True)
        
        # Processar novas cores - formato: cores[0][hex], cores[0][nome]
        cores_dict = {}
        for key in request.POST.keys():
            if key.startswith('cores['):
                # Extrair índice e campo: cores[0][hex] -> index=0, field=hex
                parts = key.replace('cores[', '').replace(']', '').split('[')
                if len(parts) == 2:
                    index, field = parts
                    if index not in cores_dict:
                        cores_dict[index] = {}
                    cores_dict[index][field] = request.POST.get(key)
        
        print(f"📊 DEBUG ColorService - cores_dict: {cores_dict}", flush=True)
        
        # Criar cores
        for index, cor_data in sorted(cores_dict.items()):
            hex_code = cor_data.get('hex', '').strip()
            nome = cor_data.get('nome', '').strip()
            
            # Validar dados básicos
            if not hex_code:
                continue
            
            # Gerar nome automático se não fornecido
            if not nome:
                nome = ColorService.generate_color_name(hex_code)
                print(f"🎨 Nome automático gerado: {nome} para {hex_code}", flush=True)
            
            # Normalizar HEX
            hex_code = ColorService.normalize_hex_color(hex_code)
            
            # Validar formato HEX
            is_valid, error_msg = ColorService.validate_hex_color(hex_code)
            if not is_valid:
                errors.append(f'Cor "{nome}": {error_msg}')
                continue
            
            try:
                ColorPalette.objects.create(
                    knowledge_base=kb,
                    name=nome,
                    hex_code=hex_code,
                    color_type='primary',
                    order=int(index)
                )
                colors_created += 1
                print(f"✅ Cor criada: {nome} ({hex_code})", flush=True)
            except Exception as e:
                error_msg = f'Erro ao salvar cor "{nome}": {str(e)}'
                errors.append(error_msg)
                print(f"❌ {error_msg}", flush=True)
        
        print(f"🎨 Total de cores criadas: {colors_created}", flush=True)
        return colors_created, errors


class FontService:
    """Serviço para gerenciar tipografia"""
    
    FONT_TYPE_MAP = {
        'TITULO': 'titulo',
        'SUBTITULO': 'corpo',
        'TEXTO': 'corpo',
        'BOTAO': 'destaque',
        'LEGENDA': 'corpo'
    }
    
    @staticmethod
    def validate_google_font_name(font_name: str) -> Tuple[bool, Optional[str]]:
        """
        Valida nome de fonte do Google Fonts
        
        Args:
            font_name: Nome da fonte
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not font_name or not font_name.strip():
            return False, "Nome da fonte não pode ser vazio"
        
        # Verificar caracteres válidos
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', font_name):
            return False, "Nome da fonte contém caracteres inválidos"
        
        return True, None
    
    @staticmethod
    @transaction.atomic
    def process_fonts(request, kb: KnowledgeBase) -> Tuple[int, List[str]]:
        """
        Processa e salva fontes
        
        Args:
            request: HttpRequest com POST data
            kb: Instância KnowledgeBase
            
        Returns:
            Tuple (fonts_created, errors)
        """
        errors = []
        fonts_created = 0
        
        # DEBUG: Verificar quais chaves estão no POST
        post_keys = [k for k in request.POST.keys() if 'font' in k.lower()]
        print(f"🔤 DEBUG FontService - POST keys com 'font': {post_keys}", flush=True)
        
        # Limpar fontes existentes
        deleted_count = kb.custom_fonts.all().delete()
        print(f"🗑️  Removidas {deleted_count[0] if deleted_count else 0} fontes existentes", flush=True)
        
        # Processar novas fontes - formato: fontes[0][tipo], fontes[0][nome_fonte], etc
        fontes_dict = {}
        for key in request.POST.keys():
            if key.startswith('fontes['):
                # Extrair índice e campo: fontes[0][tipo] -> index=0, field=tipo
                parts = key.replace('fontes[', '').replace(']', '').split('[')
                if len(parts) == 2:
                    index, field = parts
                    if index not in fontes_dict:
                        fontes_dict[index] = {}
                    fontes_dict[index][field] = request.POST.get(key)
        
        print(f"📊 DEBUG FontService - fontes_dict: {fontes_dict}", flush=True)
        
        # Criar fontes (apenas Google Fonts por enquanto)
        for index, fonte_data in sorted(fontes_dict.items()):
            tipo = fonte_data.get('tipo', 'GOOGLE')
            nome_fonte = fonte_data.get('nome_fonte', '').strip()
            uso = fonte_data.get('uso', '').strip()
            
            print(f"🔍 Processando fonte {index}: tipo={tipo}, nome={nome_fonte}, uso={uso}", flush=True)
            
            if tipo == 'GOOGLE' and nome_fonte and uso:
                # Validar nome da fonte
                is_valid, error_msg = FontService.validate_google_font_name(nome_fonte)
                if not is_valid:
                    errors.append(f'Fonte "{nome_fonte}": {error_msg}')
                    continue
                
                # Mapear uso para font_type do model
                font_type = FontService.FONT_TYPE_MAP.get(uso.upper(), 'corpo')
                
                try:
                    # Criar fonte com URL do Google Fonts
                    CustomFont.objects.create(
                        knowledge_base=kb,
                        name=nome_fonte,
                        font_type=font_type,
                        s3_key=f'google-fonts/{nome_fonte.replace(" ", "-").lower()}',
                        s3_url=f'https://fonts.googleapis.com/css2?family={nome_fonte.replace(" ", "+")}',
                        file_format='woff2'
                    )
                    fonts_created += 1
                    print(f"✅ Fonte criada: {nome_fonte} (uso: {uso}, tipo: {font_type})", flush=True)
                except Exception as e:
                    error_msg = f'Erro ao salvar fonte "{nome_fonte}": {str(e)}'
                    errors.append(error_msg)
                    print(f"❌ {error_msg}", flush=True)
            else:
                print(f"⚠️  Fonte {index} ignorada: tipo={tipo}, nome={nome_fonte}, uso={uso}", flush=True)
        
        print(f"🔤 Total de fontes criadas: {fonts_created}", flush=True)
        return fonts_created, errors


class SocialNetworkService:
    """Serviço para gerenciar redes sociais"""
    
    NETWORK_TYPES = ['instagram', 'facebook', 'linkedin', 'youtube', 'tiktok', 'twitter']
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Valida URL de rede social
        
        Args:
            url: URL a validar
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not url or not url.strip():
            return True, None  # URL vazia é válida (opcional)
        
        url = url.strip()
        
        # Verificar se começa com http:// ou https://
        if not url.startswith(('http://', 'https://')):
            return False, "URL deve começar com http:// ou https://"
        
        # Validação básica de URL
        url_pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
        if not re.match(url_pattern, url):
            return False, "URL inválida"
        
        return True, None
    
    @staticmethod
    def validate_social_network_url(url: str, network_type: str) -> Tuple[bool, Optional[str]]:
        """
        Valida URL específica de rede social
        
        Args:
            url: URL a validar
            network_type: Tipo de rede (instagram, facebook, etc)
            
        Returns:
            Tuple (is_valid, error_message)
        """
        # Validação básica de URL
        is_valid, error_msg = SocialNetworkService.validate_url(url)
        if not is_valid:
            return False, error_msg
        
        if not url:
            return True, None
        
        # Validações específicas por rede
        domain_map = {
            'instagram': 'instagram.com',
            'facebook': 'facebook.com',
            'linkedin': 'linkedin.com',
            'youtube': 'youtube.com',
            'tiktok': 'tiktok.com',
            'twitter': ('twitter.com', 'x.com')
        }
        
        expected_domain = domain_map.get(network_type)
        if expected_domain:
            if isinstance(expected_domain, tuple):
                if not any(domain in url.lower() for domain in expected_domain):
                    return False, f"URL deve ser do {network_type}"
            else:
                if expected_domain not in url.lower():
                    return False, f"URL deve ser do {expected_domain}"
        
        return True, None
    
    @staticmethod
    @transaction.atomic
    def process_social_networks(request, kb: KnowledgeBase) -> Tuple[int, List[str]]:
        """
        Processa e salva redes sociais
        
        Args:
            request: HttpRequest com POST data
            kb: Instância KnowledgeBase
            
        Returns:
            Tuple (networks_updated, errors)
        """
        errors = []
        networks_updated = 0
        
        # Processar campos individuais de redes sociais
        social_data = {
            'instagram': request.POST.get('social_instagram', ''),
            'facebook': request.POST.get('social_facebook', ''),
            'linkedin': request.POST.get('social_linkedin', ''),
            'youtube': request.POST.get('social_youtube', ''),
        }
        
        # Atualizar ou criar redes sociais
        for network_type, url in social_data.items():
            url = url.strip() if url else ''
            
            if url:
                # Validar URL
                is_valid, error_msg = SocialNetworkService.validate_social_network_url(url, network_type)
                if not is_valid:
                    errors.append(f'{network_type.capitalize()}: {error_msg}')
                    continue
                
                try:
                    SocialNetwork.objects.update_or_create(
                        knowledge_base=kb,
                        network_type=network_type,
                        defaults={
                            'name': network_type.capitalize(),
                            'url': url,
                            'is_active': True
                        }
                    )
                    networks_updated += 1
                except Exception as e:
                    errors.append(f'Erro ao salvar {network_type}: {str(e)}')
            else:
                # Remover se URL estiver vazia
                try:
                    SocialNetwork.objects.filter(
                        knowledge_base=kb,
                        network_type=network_type
                    ).delete()
                except Exception as e:
                    errors.append(f'Erro ao remover {network_type}: {str(e)}')
        
        return networks_updated, errors


class KnowledgeBaseService:
    """Serviço principal para operações da Base de Conhecimento"""
    
    @staticmethod
    def save_all_blocks(request, kb: KnowledgeBase, forms: Dict) -> Tuple[bool, List[str]]:
        """
        Salva todos os blocos da base de conhecimento
        
        Args:
            request: HttpRequest
            kb: Instância KnowledgeBase
            forms: Dicionário com forms de cada bloco
            
        Returns:
            Tuple (success, errors)
        """
        print("🚀 INÍCIO save_all_blocks", flush=True)
        all_errors = []
        
        # Validar todos os forms
        all_valid = all(form.is_valid() for form in forms.values())
        print(f"📋 Forms válidos: {all_valid}", flush=True)
        
        if not all_valid:
            for block_name, form in forms.items():
                if not form.is_valid():
                    for field, errors in form.errors.items():
                        for error in errors:
                            all_errors.append(f'{block_name} - {field}: {error}')
            return False, all_errors
        
        try:
            with transaction.atomic():
                # Salvar cada form
                for block_name, form in forms.items():
                    kb = form.save(commit=False)
                    kb.last_updated_by = request.user
                    kb.save()
                
                # Processar cores da paleta (Bloco 5)
                colors_created, color_errors = ColorService.process_colors(request, kb)
                if color_errors:
                    all_errors.extend(color_errors)
                
                # Processar fontes
                fonts_created, font_errors = FontService.process_fonts(request, kb)
                all_errors.extend(font_errors)
                
                # Processar redes sociais
                networks_updated, network_errors = SocialNetworkService.process_social_networks(request, kb)
                all_errors.extend(network_errors)
            
            # Transação foi commitada com sucesso aqui
            print(f"✅ save_all_blocks SUCESSO - Erros: {all_errors}", flush=True)
            return True, all_errors
            
        except Exception as e:
            error_msg = f'Erro ao salvar: {str(e)}'
            all_errors.append(error_msg)
            print(f"❌ save_all_blocks ERRO: {error_msg}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            return False, all_errors
