# 📦 IAMKT - ESTRUTURA DE APPS DJANGO

**Documento:** 03 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

O IAMKT é organizado em **4 Django Apps**, cada uma com responsabilidades específicas e bem definidas, seguindo o princípio de separação de responsabilidades (Separation of Concerns).

```
iamkt/app/apps/
├── __init__.py          ⚠️ OBRIGATÓRIO
├── core/                # Base, autenticação, dashboard
├── knowledge/           # Base de Conhecimento FEMME
├── content/             # Ferramentas de geração + histórico
└── campaigns/           # Projetos, campanhas, calendário (Fase 2)
```

---

## 📊 VISÃO COMPARATIVA

| App | Responsabilidade | Models Principais | Complexidade |
|-----|------------------|-------------------|--------------|
| **core** | Base do Sistema | 5 models | Média |
| **knowledge** | Base FEMME | 6 models | Média |
| **content** | Geração IA | 6 models | Alta |
| **campaigns** | Projetos | 5 models | Média |

---

## 🔷 APP: core

### Propósito
Funcionalidades base do sistema: autenticação, permissões, dashboard, configurações globais, gestão de áreas.

### Models Principais

#### 1. **User** (extensão do Django User)
```python
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Extensão do modelo User padrão do Django
    """
    # Campos adicionais
    email = models.EmailField(unique=True)  # Email obrigatório e único
    areas = models.ManyToManyField('Area', related_name='usuarios')
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)
    # PERFIL_CHOICES: 'admin', 'ti', 'gestor', 'operacional'
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    ativo = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    REQUIRED_FIELDS = ['email']  # Email obrigatório no createsuperuser
```

#### 2. **Area** (áreas organizacionais)
```python
class Area(models.Model):
    """
    Áreas organizacionais da FEMME (Marketing, RH, TI, etc)
    """
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    ativa = models.BooleanField(default=True)
    
    # Permissões: quais ferramentas esta área pode acessar
    ferramentas_permitidas = models.JSONField(default=list)
    # Exemplo: ['pautas', 'posts', 'trends', 'pesquisa_web']
    
    # Limites de uso
    limite_mensal = models.IntegerField(default=1000)
    # Pode ser em tokens ou número de gerações
    tipo_limite = models.CharField(max_length=20, default='geracoes')
    # 'geracoes' ou 'tokens'
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas'
```

#### 3. **UsageLimit** (controle de limites)
```python
class UsageLimit(models.Model):
    """
    Controle mensal de uso por área
    """
    area = models.ForeignKey('Area', on_delete=models.CASCADE)
    mes_referencia = models.DateField()  # Primeiro dia do mês
    
    consumido = models.IntegerField(default=0)
    # tokens ou gerações consumidas
    
    bloqueado = models.BooleanField(default=False)
    alerta_enviado = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['area', 'mes_referencia']
```

#### 4. **AuditLog** (trilha de auditoria)
```python
class AuditLog(models.Model):
    """
    Registro de ações críticas no sistema
    """
    usuario = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    acao = models.CharField(max_length=100)
    # 'create', 'update', 'delete', 'approve', 'reject', etc
    
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField()
    
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['usuario', '-created_at']),
            models.Index(fields=['model_name', 'object_id']),
        ]
```

#### 5. **SystemConfig** (configurações globais)
```python
class SystemConfig(models.Model):
    """
    Configurações globais do sistema (singleton)
    """
    # Rate limiting
    rate_limit_enabled = models.BooleanField(default=True)
    requests_per_minute = models.IntegerField(default=60)
    
    # Alertas
    alertas_email_enabled = models.BooleanField(default=True)
    email_alertas = models.EmailField(default='marketing@femme.com.br')
    
    # Cache
    cache_ia_enabled = models.BooleanField(default=True)
    cache_ttl_days = models.IntegerField(default=7)
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
```

### URLs Principais
- `/` - Dashboard
- `/login/` - Login
- `/logout/` - Logout
- `/admin/` - Django Admin (apenas Admin/TI)

---

## 🔷 APP: knowledge

### Propósito
Gerenciamento da Base de Conhecimento FEMME (7 blocos de informações da marca).

### Models Principais

#### 1. **KnowledgeBase** (base única - singleton)
```python
class KnowledgeBase(models.Model):
    """
    Base de Conhecimento FEMME (instância única)
    Contém todos os 7 blocos de informações
    """
    # BLOCO 1: Identidade Institucional
    nome_empresa = models.CharField(max_length=200)
    descricao_resumida = models.TextField()
    missao = models.TextField()
    visao = models.TextField()
    valores_principios = models.JSONField(default=list)
    
    # BLOCO 2: Público e Segmentos
    publico_alvo_externo = models.TextField()
    publico_interno = models.TextField()
    segmentos_internos = models.JSONField(default=list)
    
    # BLOCO 3: Posicionamento e Diferenciais
    posicionamento_marca = models.TextField()
    principais_diferenciais = models.JSONField(default=list)
    # Concorrentes são gerenciados no model Competitor (relacionado)
    
    # BLOCO 4: Tom de Voz
    tom_voz_externo = models.TextField()
    palavras_recomendadas = models.JSONField(default=list)
    tom_voz_interno = models.TextField()
    palavras_evitar = models.JSONField(default=list)
    
    # BLOCO 5: Identidade Visual (referências básicas)
    logotipo_s3_url = models.URLField(blank=True)  # URL no S3
    logotipo_upload = models.ImageField(upload_to='knowledge/logos/', null=True, blank=True)
    # Quando faz upload, salva localmente e depois move para S3
    
    # BLOCO 6: Sites e Redes Sociais (flexível)
    site_institucional = models.URLField(blank=True)
    # Redes sociais gerenciadas no model SocialNetwork (relacionado)
    
    # BLOCO 7: Dados e Insights
    fontes_pesquisa_urls = models.JSONField(default=list)
    # URLs de fontes confiáveis para pesquisa de pautas/trends
    
    canais_monitoramento_trends = models.JSONField(default=list)
    # Canais customizados para monitoramento (além dos pré-configurados)
    
    regras_interpretacao = models.TextField(blank=True)
    
    # Integração AWS Athena (Fase 2)
    athena_habilitado = models.BooleanField(default=False)
    athena_endpoint = models.CharField(max_length=500, blank=True)
    athena_database = models.CharField(max_length=200, blank=True)
    athena_credenciais = models.JSONField(null=True, blank=True)
    # {'access_key': '...', 'secret_key': '...', 'region': 'us-east-1'}
    
    queries_predefinidas = models.JSONField(default=list)
    # [{'nome': 'Exames por período', 'sql': 'SELECT ...', 'descricao': '...'}]
    
    # Status
    status = models.CharField(max_length=20, default='incompleto')
    # 'incompleto', 'completo'
    completude_percentual = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    
    def save(self, *args, **kwargs):
        # Garante que existe apenas uma instância
        if not self.pk and KnowledgeBase.objects.exists():
            raise ValidationError('Já existe uma Base de Conhecimento')
        return super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Base de Conhecimento'
        verbose_name_plural = 'Base de Conhecimento'
```

#### 2. **ColorPalette** (cores da marca)
```python
class ColorPalette(models.Model):
    """
    Paleta de cores da marca FEMME
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='cores')
    
    nome = models.CharField(max_length=50)  # 'Primária', 'Secundária', etc
    hex_code = models.CharField(max_length=7)  # '#6B2C91'
    tipo = models.CharField(max_length=20, choices=[
        ('primaria', 'Primária'),
        ('secundaria', 'Secundária'),
        ('acento', 'Acento')
    ])
    ordem = models.IntegerField(default=0)
```

#### 3. **SocialNetwork** (redes sociais - gerenciável)
```python
class SocialNetwork(models.Model):
    """
    Redes sociais da FEMME (gerenciável via admin)
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='redes_sociais')
    
    nome = models.CharField(max_length=50)
    # 'Instagram', 'Facebook', 'LinkedIn', 'YouTube', 'TikTok', 'Twitter/X'
    
    tipo = models.CharField(max_length=20, choices=[
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('twitter', 'Twitter/X'),
        ('outro', 'Outro')
    ])
    
    url = models.URLField(blank=True)
    username = models.CharField(max_length=100, blank=True)  # @username
    
    ativa = models.BooleanField(default=True)
    # Permite ativar/desativar redes sem deletar
    
    ordem = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Rede Social'
        verbose_name_plural = 'Redes Sociais'
        ordering = ['ordem', 'nome']
```

#### 4. **SocialNetworkTemplate** (templates por rede social - gerenciável)
```python
class SocialNetworkTemplate(models.Model):
    """
    Templates de posts por rede social (gerenciável via admin)
    """
    rede_social = models.ForeignKey('SocialNetwork', on_delete=models.CASCADE, related_name='templates')
    
    nome = models.CharField(max_length=100)
    # 'Feed 1:1', 'Feed 4:5', 'Stories', 'Carrossel', etc
    
    descricao = models.TextField(blank=True)
    
    # Dimensões da imagem
    largura_px = models.IntegerField()
    altura_px = models.IntegerField()
    
    aspect_ratio = models.CharField(max_length=10)  # '1:1', '4:5', '9:16'
    
    # Limites de texto
    limite_caracteres_legenda = models.IntegerField(null=True, blank=True)
    limite_hashtags = models.IntegerField(null=True, blank=True)
    
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Template de Rede Social'
        verbose_name_plural = 'Templates de Redes Sociais'
        ordering = ['rede_social', 'ordem']
```

#### 5. **CustomFont** (fontes customizadas)
```python
class CustomFont(models.Model):
    """
    Fontes customizadas: Google Fonts ou upload (.otf/.ttf)
    Máximo 5 fontes no total
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='fontes_custom')
    
    nome = models.CharField(max_length=100)
    
    # Tipo de fonte
    tipo_fonte = models.CharField(max_length=20, choices=[
        ('google', 'Google Fonts'),
        ('upload', 'Upload (OTF/TTF)')
    ])
    
    # Para Google Fonts
    google_font_name = models.CharField(max_length=100, blank=True)
    # Ex: 'Montserrat', 'Open Sans'
    google_font_url = models.URLField(blank=True)
    # URL da API Google Fonts
    
    # Para uploads
    arquivo_s3_url = models.URLField(blank=True)  # S3 URL
    arquivo_upload = models.FileField(upload_to='knowledge/fonts/', null=True, blank=True)
    tipo_arquivo = models.CharField(max_length=10, blank=True)  # 'otf' ou 'ttf'
    tamanho_bytes = models.IntegerField(null=True, blank=True)
    
    principal = models.BooleanField(default=False)
    # Apenas 1 pode ser principal
    
    ordem = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Fonte Customizada'
        verbose_name_plural = 'Fontes Customizadas'
        ordering = ['ordem']
```

#### 6. **ReferenceImage** (imagens de referência visual)
```python
class ReferenceImage(models.Model):
    """
    Imagens de referência para estilo visual
    Sistema analisa com IA para evitar criações repetitivas
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='imagens_referencia')
    
    descricao = models.CharField(max_length=200)
    
    # Armazenamento dual: upload local + S3
    arquivo_upload = models.ImageField(upload_to='knowledge/references/', null=True, blank=True)
    arquivo_s3_url = models.URLField(blank=True)
    thumbnail_s3_url = models.URLField(blank=True)
    
    # Categorização
    categoria = models.CharField(max_length=50, blank=True)
    # 'campanha', 'institucional', 'produto', 'evento', 'geral'
    
    relacionado_campanha = models.ForeignKey(
        'campaigns.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='imagens_referencia'
    )
    
    tags = models.JSONField(default=list)
    # ['cardiologia', 'preventivo', 'azul', 'minimalista']
    
    # IA analisa e extrai características (para evitar repetição)
    analise_ia = models.JSONField(null=True, blank=True)
    # {
    #   'estilo': 'minimalista',
    #   'cores_predominantes': ['#6B2C91', '#FFFFFF'],
    #   'elementos_visuais': ['pessoa', 'equipamento médico'],
    #   'composicao': 'centralizada',
    #   'mood': 'profissional e acolhedor',
    #   'hash_perceptual': '...'  # Para detectar similaridade
    # }
    
    hash_perceptual = models.CharField(max_length=64, blank=True)
    # Hash da imagem para detectar duplicatas ou similares
    
    # Uso
    vezes_usada_como_referencia = models.IntegerField(default=0)
    ultima_vez_usada = models.DateTimeField(null=True, blank=True)
    
    ordem = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Imagem de Referência'
        verbose_name_plural = 'Imagens de Referência'
        ordering = ['ordem', '-created_at']
    
    def incrementar_uso(self):
        """Incrementa contador de uso"""
        self.vezes_usada_como_referencia += 1
        self.ultima_vez_usada = timezone.now()
        self.save(update_fields=['vezes_usada_como_referencia', 'ultima_vez_usada'])
```

#### 5. **Competitor** (concorrentes)
```python
class Competitor(models.Model):
    """
    Sites concorrentes para análise
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='concorrentes')
    
    nome = models.CharField(max_length=200)
    url = models.URLField()
    descricao = models.TextField(blank=True)
    
    # Scraping
    ultimo_scraping = models.DateTimeField(null=True, blank=True)
    scraping_ativo = models.BooleanField(default=True)
    
    # Análise IA
    analise_posicionamento = models.TextField(blank=True)
    analise_diferenciais = models.TextField(blank=True)
    analise_tom_voz = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### 6. **ChangeLog** (histórico de alterações)
```python
class ChangeLog(models.Model):
    """
    Histórico de alterações na Base FEMME
    """
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.CASCADE, related_name='change_logs')
    
    bloco = models.CharField(max_length=50)
    # 'institucional', 'publico', 'posicionamento', 'tom_voz', 'visual', 'sites', 'dados'
    
    campo_alterado = models.CharField(max_length=100)
    valor_anterior = models.TextField(blank=True)
    valor_novo = models.TextField()
    
    usuario = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
```

### URLs Principais
- `/knowledge/` - Dashboard da Base FEMME
- `/knowledge/edit/` - Edição sanfona (7 blocos)
- `/knowledge/competitors/` - Gerenciar concorrentes
- `/knowledge/history/` - Histórico de alterações

---

## 🔷 APP: content

### Propósito
Ferramentas de geração de conteúdo com IA, templates, histórico, favoritos.

### Models Principais

#### 1. **ContentTemplate** (templates)
```python
class ContentTemplate(models.Model):
    """
    Templates pré-definidos para cada ferramenta
    """
    nome = models.CharField(max_length=200)
    ferramenta = models.CharField(max_length=50)
    # 'pautas', 'posts', 'blog', 'roteiro', 'ppt', etc
    
    tipo_rede_social = models.CharField(max_length=50, blank=True)
    # Para posts: 'instagram_feed', 'instagram_stories', 'linkedin', 'facebook'
    
    descricao = models.TextField()
    prompt_base = models.TextField()
    # Template de prompt com placeholders: {tema}, {publico}, {objetivo}
    
    dimensoes_imagem = models.JSONField(null=True, blank=True)
    # {'width': 1080, 'height': 1080}
    
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
```

#### 2. **GeneratedContent** (conteúdos gerados)
```python
class GeneratedContent(models.Model):
    """
    Histórico de conteúdos gerados
    """
    usuario = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='conteudos')
    area = models.ForeignKey('core.Area', on_delete=models.SET_NULL, null=True)
    
    ferramenta = models.CharField(max_length=50)
    # 'pautas', 'posts', 'blog', etc
    
    template = models.ForeignKey('ContentTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Inputs do usuário
    inputs_usuario = models.JSONField()
    # {'tema': 'exames cardiológicos', 'publico': 'adultos 40+', ...}
    
    # Modelo IA usado
    modelo_ia = models.CharField(max_length=50)
    # 'openai-gpt4', 'gemini-pro', 'grok'
    
    # Conteúdo gerado
    conteudo_texto = models.TextField(blank=True)
    conteudo_imagem_url = models.URLField(blank=True)  # S3 URL
    metadados = models.JSONField(null=True, blank=True)
    # {'tokens_used': 1200, 'cost_usd': 0.05, 'generation_time': 15.3}
    
    # Status
    status = models.CharField(max_length=20, default='rascunho')
    # 'rascunho', 'aguardando_aprovacao', 'aprovado', 'em_ajuste', 'arquivado'
    
    favorito = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['usuario', '-created_at']),
            models.Index(fields=['ferramenta', 'status']),
        ]
```

#### 3. **Asset** (biblioteca de assets)
```python
class Asset(models.Model):
    """
    Biblioteca de imagens, vídeos, documentos
    """
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    
    tipo = models.CharField(max_length=20)
    # 'imagem', 'video', 'documento'
    
    arquivo_s3_url = models.URLField()
    thumbnail_s3_url = models.URLField(blank=True)
    
    tamanho_bytes = models.IntegerField()
    mime_type = models.CharField(max_length=100)
    
    # Organização
    categoria = models.CharField(max_length=50, blank=True)
    tags = models.JSONField(default=list)
    
    # Uso
    usado_em_conteudos = models.ManyToManyField('GeneratedContent', related_name='assets', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
```

#### 4. **TrendMonitor** (monitoramento de trends)
```python
class TrendMonitor(models.Model):
    """
    Dados de monitoramento de tendências
    """
    data_coleta = models.DateTimeField(auto_now_add=True)
    fonte = models.CharField(max_length=50)
    # 'google_trends', 'think_with_google', 'reddit', 'twitter'
    
    titulo = models.CharField(max_length=300)
    descricao = models.TextField()
    url_fonte = models.URLField(blank=True)
    
    # Análise IA
    relevancia_score = models.IntegerField()  # 0-100
    analise_ia = models.TextField()
    sugestao_aproveitamento = models.TextField(blank=True)
    
    # Status
    visualizado = models.BooleanField(default=False)
    alerta_enviado = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-relevancia_score', '-created_at']
        indexes = [
            models.Index(fields=['-relevancia_score', '-created_at']),
        ]
```

#### 5. **WebInsight** (pesquisas web)
```python
class WebInsight(models.Model):
    """
    Pesquisas e insights da web
    """
    usuario = models.ForeignKey('core.User', on_delete=models.CASCADE)
    area = models.ForeignKey('core.Area', on_delete=models.SET_NULL, null=True)
    
    query = models.TextField()  # Pergunta/tema da pesquisa
    urls_pesquisadas = models.JSONField(default=list)
    
    # Resultado
    resumo = models.TextField()
    insights = models.JSONField()
    fontes_citadas = models.JSONField(default=list)
    
    exportado_pdf = models.BooleanField(default=False)
    pdf_s3_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
```

#### 6. **IAModelUsage** (métricas de uso de IA)
```python
class IAModelUsage(models.Model):
    """
    Métricas de uso de modelos de IA
    """
    usuario = models.ForeignKey('core.User', on_delete=models.CASCADE)
    area = models.ForeignKey('core.Area', on_delete=models.SET_NULL, null=True)
    
    modelo = models.CharField(max_length=50)
    # 'openai-gpt4', 'openai-dalle3', 'gemini-pro', 'grok'
    
    ferramenta = models.CharField(max_length=50)
    # 'pautas', 'posts', etc
    
    tokens_prompt = models.IntegerField()
    tokens_resposta = models.IntegerField()
    tokens_total = models.IntegerField()
    
    custo_estimado_usd = models.DecimalField(max_digits=10, decimal_places=4)
    tempo_geracao_segundos = models.FloatField()
    
    sucesso = models.BooleanField(default=True)
    erro_mensagem = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['modelo', '-created_at']),
        ]
```

### URLs Principais
- `/content/` - Dashboard de ferramentas
- `/content/pautas/` - Geração de pautas
- `/content/posts/` - Geração de posts
- `/content/trends/` - Monitoramento de trends
- `/content/research/` - Pesquisa web
- `/content/history/` - Histórico de gerações
- `/content/favorites/` - Favoritos

---

## 🔷 APP: campaigns

### Propósito
Gestão de projetos, campanhas, workflow de aprovação, calendário editorial (Fase 2).

### Models Principais (Estrutura Básica para Fase 1)

#### 1. **Project** (projetos/campanhas)
```python
class Project(models.Model):
    """
    Projetos ou campanhas de marketing
    TODO conteúdo gerado deve estar relacionado a um projeto
    """
    nome = models.CharField(max_length=200)
    descricao = models.TextField()
    
    # Tipologia do projeto
    tipo = models.CharField(max_length=30, choices=[
        ('campanha', 'Campanha'),
        ('trend', 'Aproveitamento de Trend'),
        ('impulsao', 'Impulsão'),
        ('institucional', 'Institucional'),
        ('avulso', 'Avulso/Individual'),
        ('outro', 'Outro')
    ], default='avulso')
    
    # Se tipo='trend', vincular ao trend que originou
    trend_origem = models.ForeignKey(
        'content.TrendMonitor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projetos'
    )
    
    area_responsavel = models.ForeignKey('core.Area', on_delete=models.CASCADE)
    
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, default='ativo')
    # 'rascunho', 'ativo', 'concluido', 'cancelado'
    
    conteudos = models.ManyToManyField('content.GeneratedContent', related_name='projetos', blank=True)
    
    # Métricas
    total_conteudos = models.IntegerField(default=0)
    conteudos_aprovados = models.IntegerField(default=0)
    conteudos_publicados = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Projeto/Campanha'
        verbose_name_plural = 'Projetos/Campanhas'
        ordering = ['-created_at']
```

#### 2. **Approval** (aprovações)
```python
class Approval(models.Model):
    """
    Solicitações de aprovação de conteúdo
    """
    conteudo = models.ForeignKey('content.GeneratedContent', on_delete=models.CASCADE, related_name='aprovacoes')
    
    solicitante = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='solicitacoes')
    aprovador = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, related_name='aprovacoes_gestor')
    
    status = models.CharField(max_length=20, default='pendente')
    # 'pendente', 'aprovado', 'em_ajuste', 'reprovado'
    
    mensagem_solicitacao = models.TextField(blank=True)
    mensagem_resposta = models.TextField(blank=True)
    
    # Notificações
    email_enviado = models.BooleanField(default=False)
    data_email = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
```

#### 3. **ApprovalComment** (comentários em aprovações)
```python
class ApprovalComment(models.Model):
    """
    Comentários em aprovações (thread de discussão)
    """
    aprovacao = models.ForeignKey('Approval', on_delete=models.CASCADE, related_name='comentarios')
    
    usuario = models.ForeignKey('core.User', on_delete=models.CASCADE)
    comentario = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
```

#### 4. **Report** (relatórios - Fase 2)
```python
class Report(models.Model):
    """
    Relatórios de métricas (Fase 2)
    """
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=50)
    # 'uso_ferramentas', 'custos_ia', 'performance_usuarios', etc
    
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    
    area = models.ForeignKey('core.Area', on_delete=models.SET_NULL, null=True, blank=True)
    # null = relatório global
    
    dados_json = models.JSONField()
    pdf_s3_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
```

#### 5. **ScheduledPost** (posts agendados - Fase 2)
```python
class ScheduledPost(models.Model):
    """
    Posts agendados para publicação automática (Fase 2)
    """
    conteudo = models.ForeignKey('content.GeneratedContent', on_delete=models.CASCADE)
    
    rede_social = models.CharField(max_length=50)
    # 'instagram', 'linkedin', 'facebook'
    
    data_agendada = models.DateTimeField()
    publicado = models.BooleanField(default=False)
    data_publicacao = models.DateTimeField(null=True, blank=True)
    
    erro = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
```

### URLs Principais (Fase 1 - Básico)
- `/campaigns/approvals/` - Lista de aprovações pendentes
- `/campaigns/approvals/<id>/` - Detalhes de aprovação

---

## 🔗 RELACIONAMENTOS ENTRE APPS

```
User (core)
   ├─> ManyToMany: Area (core)
   ├─> OneToMany: GeneratedContent (content)
   ├─> OneToMany: Approval (campaigns)
   └─> OneToMany: AuditLog (core)

Area (core)
   ├─> ManyToMany: User (core)
   ├─> OneToMany: GeneratedContent (content)
   └─> OneToMany: Project (campaigns)

KnowledgeBase (knowledge)
   ├─> OneToMany: ColorPalette (knowledge)
   ├─> OneToMany: CustomFont (knowledge)
   ├─> OneToMany: ReferenceImage (knowledge)
   ├─> OneToMany: Competitor (knowledge)
   └─> OneToMany: ChangeLog (knowledge)

GeneratedContent (content)
   ├─> ForeignKey: User (core)
   ├─> ForeignKey: Area (core)
   ├─> ForeignKey: ContentTemplate (content)
   ├─> ManyToMany: Asset (content)
   ├─> OneToMany: Approval (campaigns)
   └─> ManyToMany: Project (campaigns)
```

---

**Próximo documento:** [04_IAMKT_Funcionalidades_Fase1.md](04_IAMKT_Funcionalidades_Fase1.md)
