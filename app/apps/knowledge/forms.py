"""
IAMKT - Knowledge Base Forms
Forms para edição dos 7 blocos da Base de Conhecimento FEMME
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    KnowledgeBase, ColorPalette, SocialNetwork, 
    SocialNetworkTemplate, ReferenceImage, CustomFont, Logo
)
import json


class KnowledgeBaseBlock1Form(forms.ModelForm):
    """
    Bloco 1: Identidade Institucional
    Campos: nome_empresa, missao, visao, valores, historia
    """
    class Meta:
        model = KnowledgeBase
        fields = ['nome_empresa', 'missao', 'visao', 'valores', 'historia']
        widgets = {
            'nome_empresa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome oficial da empresa'
            }),
            'missao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Razão de existir da empresa'
            }),
            'visao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Onde a empresa quer chegar'
            }),
            'valores': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Valores fundamentais (um por linha)'
            }),
            'historia': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'História da empresa'
            }),
        }


class KnowledgeBaseBlock2Form(forms.ModelForm):
    """
    Bloco 2: Público e Segmentos
    Campos: publico_externo, publico_interno, segmentos_internos
    """
    segmentos_internos_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Um segmento por linha (ex: Gestores, Operacional, etc)'
        }),
        label='Segmentos Internos',
        help_text='Digite um segmento por linha'
    )
    
    class Meta:
        model = KnowledgeBase
        fields = ['publico_externo', 'publico_interno']
        widgets = {
            'publico_externo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Perfil dos clientes/pacientes'
            }),
            'publico_interno': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Perfil dos colaboradores'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Converter lista JSON para texto (um por linha)
            segmentos = self.instance.segmentos_internos or []
            self.initial['segmentos_internos_text'] = '\n'.join(segmentos)
    
    def clean_segmentos_internos_text(self):
        text = self.cleaned_data.get('segmentos_internos_text', '')
        if not text:
            return []
        # Converter texto para lista (remover linhas vazias)
        segmentos = [line.strip() for line in text.split('\n') if line.strip()]
        return segmentos
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.segmentos_internos = self.cleaned_data.get('segmentos_internos_text', [])
        if commit:
            instance.save()
        return instance


class KnowledgeBaseBlock3Form(forms.ModelForm):
    """
    Bloco 3: Posicionamento e Diferenciais
    Campos: posicionamento, diferenciais, proposta_valor
    """
    class Meta:
        model = KnowledgeBase
        fields = ['posicionamento', 'diferenciais', 'proposta_valor']
        widgets = {
            'posicionamento': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Como a marca quer ser percebida'
            }),
            'diferenciais': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'O que torna a marca única (um por linha)'
            }),
            'proposta_valor': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Proposta de valor para o cliente'
            }),
        }


class KnowledgeBaseBlock4Form(forms.ModelForm):
    """
    Bloco 4: Tom de Voz e Linguagem
    Campos: tom_voz_externo, tom_voz_interno
    
    Nota: palavras_recomendadas e palavras_evitar são salvos via AJAX (views_tags.py)
    """
    class Meta:
        model = KnowledgeBase
        fields = ['tom_voz_externo', 'tom_voz_interno']
        widgets = {
            'tom_voz_externo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Como falar com público externo'
            }),
            'tom_voz_interno': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Como comunicar com colaboradores'
            }),
        }


class KnowledgeBaseBlock5Form(forms.ModelForm):
    """
    Bloco 5: Identidade Visual
    Campos: paleta_cores, tipografia (LEGADOS - agora usamos ColorPalette e CustomFont models)
    
    Nota: ColorPalette, CustomFont, Logo são gerenciados via models separados
    Este form mantém os campos JSON legados como opcionais
    """
    paleta_cores = forms.JSONField(required=False, widget=forms.HiddenInput())
    tipografia = forms.JSONField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = KnowledgeBase
        fields = ['paleta_cores', 'tipografia']
    
    def clean_paleta_cores(self):
        data = self.cleaned_data.get('paleta_cores')
        if not data:
            return {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data
    
    def clean_tipografia(self):
        data = self.cleaned_data.get('tipografia')
        if not data:
            return {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data


class KnowledgeBaseBlock6Form(forms.ModelForm):
    """
    Bloco 6: Sites e Redes Sociais
    Campos: site_institucional, redes_sociais (LEGADO), templates_redes (LEGADO)
    
    Nota: SocialNetwork e SocialNetworkTemplate são gerenciados via models separados
    Este form mantém os campos JSON legados como opcionais
    """
    redes_sociais = forms.JSONField(required=False, widget=forms.HiddenInput())
    templates_redes = forms.JSONField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = KnowledgeBase
        fields = ['site_institucional', 'redes_sociais', 'templates_redes']
        widgets = {
            'site_institucional': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://exemplo.com.br'
            }),
        }
    
    def clean_redes_sociais(self):
        data = self.cleaned_data.get('redes_sociais')
        if not data:
            return {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data
    
    def clean_templates_redes(self):
        data = self.cleaned_data.get('templates_redes')
        if not data:
            return {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data


class KnowledgeBaseBlock7Form(forms.ModelForm):
    """
    Bloco 7: Dados e Insights
    
    Nota: fontes_confiaveis, canais_trends e palavras_chave_trends são salvos via AJAX (views_tags.py)
    Este form não tem campos - bloco 7 é gerenciado inteiramente via AJAX
    """
    class Meta:
        model = KnowledgeBase
        fields = []


# Forms para models relacionados

class ColorPaletteForm(forms.ModelForm):
    """Form para adicionar/editar cores da paleta"""
    class Meta:
        model = ColorPalette
        fields = ['name', 'hex_code', 'color_type', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'hex_code': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'placeholder': '#6B2C91'
            }),
            'color_type': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SocialNetworkForm(forms.ModelForm):
    """Form para adicionar/editar redes sociais"""
    class Meta:
        model = SocialNetwork
        fields = ['name', 'network_type', 'url', 'username', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'network_type': forms.Select(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ReferenceImageUploadForm(forms.ModelForm):
    """Form para upload de imagens de referência"""
    image_file = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label='Imagem',
        help_text='Formatos: JPG, PNG, GIF, WEBP. Máximo: 10MB'
    )
    
    class Meta:
        model = ReferenceImage
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }


class LogoUploadForm(forms.ModelForm):
    """Form para upload de logos"""
    logo_file = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.svg'
        }),
        label='Logo',
        help_text='Formatos: SVG, PNG. Preferir SVG.'
    )
    
    class Meta:
        model = Logo
        fields = ['name', 'logo_type', 'is_primary']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo_type': forms.Select(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CustomFontUploadForm(forms.ModelForm):
    """Form para upload de fontes customizadas"""
    font_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.ttf,.otf,.woff,.woff2'
        }),
        label='Arquivo de Fonte',
        help_text='Formatos: TTF, OTF, WOFF, WOFF2'
    )
    
    class Meta:
        model = CustomFont
        fields = ['name', 'font_type', 'file_format']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'font_type': forms.Select(attrs={'class': 'form-control'}),
            'file_format': forms.Select(attrs={'class': 'form-control'}),
        }
