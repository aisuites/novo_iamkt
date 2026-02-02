from django import forms
from .models import Pauta


class PautaCreateForm(forms.Form):
    """Formulário para criação de pautas via modal"""
    
    tema = forms.CharField(
        label="Tema",
        max_length=100,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: mamografia, marketing digital, etc',
            'required': True
        })
    )
    
    rede_social = forms.ChoiceField(
        label="Rede Social",
        choices=[
            ('', 'Selecione...'),
            ('FACEBOOK', 'Facebook'),
            ('INSTAGRAM', 'Instagram'),
            ('LINKEDIN', 'LinkedIn'),
            ('TWITTER', 'Twitter'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        })
    )
    
    def clean_tema(self):
        tema = self.cleaned_data.get('tema')
        if len(tema.strip()) < 3:
            raise forms.ValidationError("O tema deve ter pelo menos 3 caracteres.")
        return tema.strip()


class PautaEditForm(forms.ModelForm):
    """Formulário para edição de pauta (inline no card)"""
    
    class Meta:
        model = Pauta
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Título da pauta'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 4,
                'placeholder': 'Conteúdo da pauta'
            })
        }
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title.strip()) < 3:
            raise forms.ValidationError("O título deve ter pelo menos 3 caracteres.")
        return title.strip()
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.strip()) < 10:
            raise forms.ValidationError("O conteúdo deve ter pelo menos 10 caracteres.")
        return content.strip()
