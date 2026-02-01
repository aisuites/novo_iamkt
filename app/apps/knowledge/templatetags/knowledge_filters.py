"""
Template filters customizados para Knowledge Base
"""
from django import template
import json

register = template.Library()


@register.filter(name='to_json')
def to_json(value):
    """
    Converte valor Python (lista, dict) para string JSON
    Uso: {{ kb.palavras_recomendadas|to_json }}
    """
    if value is None:
        return '[]'
    
    if isinstance(value, str):
        # Já é string, retornar como está
        return value
    
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return '[]'


@register.filter(name='colors_to_json')
def colors_to_json(queryset):
    """
    Converte queryset de ColorPalette para JSON
    """
    if not queryset:
        return '[]'
    
    try:
        colors_list = []
        for color in queryset:
            colors_list.append({
                'id': color.id,
                'hex_code': color.hex_code,
                'name': color.name,
                'color_type': color.color_type,
                'order': color.order
            })
        return json.dumps(colors_list, ensure_ascii=False)
    except Exception:
        return '[]'


@register.filter(name='fonts_to_json')
def fonts_to_json(queryset):
    """
    Converte queryset de Typography para JSON compatível com fonts.js
    """
    if not queryset:
        return '[]'
    
    try:
        fonts_list = []
        
        for typo in queryset:
            # Determinar tipo e nome da fonte
            if typo.font_source == 'google':
                tipo = 'GOOGLE'
                nome = typo.google_font_name
                variante = typo.google_font_weight or '400'
                arquivo_url = ''
            else:  # upload
                tipo = 'UPLOAD'
                nome = typo.custom_font.name if typo.custom_font else ''
                variante = '400'
                arquivo_url = typo.custom_font.s3_url if typo.custom_font else ''
            
            fonts_list.append({
                'id': typo.id,
                'tipo': tipo,
                'nome': nome,
                'uso': typo.usage,  # Já está no formato correto (TITULO, TEXTO, etc)
                'variante': variante,
                'arquivo_url': arquivo_url
            })
        
        return json.dumps(fonts_list, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erro em fonts_to_json: {str(e)}", flush=True)
        return '[]'


@register.filter(name='translate_area')
def translate_area(area_code):
    """
    Traduz código de área técnico para nome amigável em português
    Uso: {{ gap.area|translate_area }}
    """
    translations = {
        'base': 'Base de Conhecimento',
        'digital_presence': 'Presença Digital',
        'visual_identity': 'Identidade Visual',
    }
    return translations.get(area_code, area_code)


@register.filter(name='translate_field')
def translate_field(field_code):
    """
    Traduz código de campo técnico para nome amigável em português
    Uso: {{ gap.field|translate_field }}
    """
    translations = {
        # Base de Conhecimento
        'identity_essence': 'Identidade e Essência',
        'audience': 'Público-Alvo',
        'strategy_channels': 'Canais Estratégicos',
        'key_messages': 'Mensagens-Chave',
        'positioning': 'Posicionamento',
        'tone_of_voice': 'Tom de Voz',
        
        # Presença Digital
        'website_url': 'Site Institucional',
        'social_networks': 'Redes Sociais',
        'competitors': 'Concorrentes',
        
        # Identidade Visual
        'palette_hex': 'Paleta de Cores',
        'typography': 'Tipografia',
        'logo_primary': 'Logo Principal',
        'visual_references': 'Referências Visuais',
    }
    return translations.get(field_code, field_code.replace('_', ' ').title())
