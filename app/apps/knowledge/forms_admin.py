"""
Formulários customizados para Django Admin
Aplicam widgets visuais para JSONFields
"""
from django import forms
from .models import KnowledgeBase
from .widgets import TagsWidget


class KnowledgeBaseAdminForm(forms.ModelForm):
    """
    Formulário customizado para KnowledgeBase no Django Admin
    Aplica widgets visuais para campos JSON
    """
    
    class Meta:
        model = KnowledgeBase
        fields = '__all__'
        widgets = {
            'palavras_recomendadas': TagsWidget(attrs={'placeholder': '["palavra1", "palavra2", "palavra3"]'}),
            'palavras_evitar': TagsWidget(attrs={'placeholder': '["palavra1", "palavra2", "palavra3"]'}),
            'fontes_confiaveis': TagsWidget(attrs={'placeholder': '["https://fonte1.com", "https://fonte2.com"]'}),
            'canais_trends': TagsWidget(attrs={'placeholder': '["canal1", "canal2"]'}),
            'palavras_chave_trends': TagsWidget(attrs={'placeholder': '["palavra1", "palavra2"]'}),
        }
