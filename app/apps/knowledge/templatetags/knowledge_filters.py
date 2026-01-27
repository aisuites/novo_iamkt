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
