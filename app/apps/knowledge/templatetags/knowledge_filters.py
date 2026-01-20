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
    Converte queryset de CustomFont para JSON compatível com fonts.js
    """
    if not queryset:
        return '[]'
    
    try:
        fonts_list = []
        # Mapear font_type do model para uso do frontend
        font_type_to_uso = {
            'titulo': 'TITULO',
            'corpo': 'TEXTO',
            'destaque': 'BOTAO'
        }
        
        for font in queryset:
            fonts_list.append({
                'id': font.id,
                'tipo': 'GOOGLE',  # Por enquanto todas são Google Fonts
                'nome': font.name,
                'uso': font_type_to_uso.get(font.font_type, 'TITULO'),
                'variante': '400',  # Default
                'arquivo_url': font.s3_url
            })
        return json.dumps(fonts_list, ensure_ascii=False)
    except Exception:
        return '[]'
