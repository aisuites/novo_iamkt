"""
Widgets customizados para Django Admin
Renderizam JSONFields de forma visual e amigável
"""
from django import forms
from django.utils.safestring import mark_safe
import json


class TagsWidget(forms.Textarea):
    """
    Widget para exibir JSONField de lista como tags visuais no Django Admin
    """
    
    def __init__(self, attrs=None):
        default_attrs = {'rows': 3, 'cols': 40}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        # Renderizar textarea normal (para edição)
        textarea_html = super().render(name, value, attrs, renderer)
        
        # Parsear valor JSON
        try:
            if isinstance(value, str):
                tags = json.loads(value) if value else []
            elif isinstance(value, list):
                tags = value
            else:
                tags = []
        except (json.JSONDecodeError, TypeError):
            tags = []
        
        # Renderizar visualização de tags
        tags_html = '<div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px;">'
        
        if tags:
            for tag in tags:
                tags_html += f'''
                <span style="
                    display: inline-block;
                    padding: 4px 10px;
                    background: linear-gradient(135deg, #7a3d8a, #9b59b6);
                    color: white;
                    border-radius: 999px;
                    font-size: 11px;
                    font-weight: 500;
                ">{tag}</span>
                '''
        else:
            tags_html += '<em style="color: #999;">Nenhuma tag cadastrada</em>'
        
        tags_html += '</div>'
        tags_html += '<p style="margin-top: 8px; font-size: 11px; color: #666;">💡 Edite o JSON acima para modificar as tags. Formato: ["tag1", "tag2", "tag3"]</p>'
        
        return mark_safe(textarea_html + tags_html)


class ReadOnlyTagsWidget(forms.Widget):
    """
    Widget somente leitura para exibir tags (para campos readonly)
    """
    
    def render(self, name, value, attrs=None, renderer=None):
        # Parsear valor JSON
        try:
            if isinstance(value, str):
                tags = json.loads(value) if value else []
            elif isinstance(value, list):
                tags = value
            else:
                tags = []
        except (json.JSONDecodeError, TypeError):
            tags = []
        
        # Renderizar visualização de tags
        html = '<div style="display: flex; flex-wrap: wrap; gap: 6px;">'
        
        if tags:
            for tag in tags:
                html += f'''
                <span style="
                    display: inline-block;
                    padding: 4px 10px;
                    background: linear-gradient(135deg, #7a3d8a, #9b59b6);
                    color: white;
                    border-radius: 999px;
                    font-size: 11px;
                    font-weight: 500;
                ">{tag}</span>
                '''
        else:
            html += '<em style="color: #999;">Nenhuma tag cadastrada</em>'
        
        html += '</div>'
        
        return mark_safe(html)
