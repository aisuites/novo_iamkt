from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import User, Area
from apps.knowledge.models import KnowledgeBase


class Pauta(models.Model):
    """
    Pautas geradas por IA para criação de conteúdo
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pautas',
        verbose_name='Usuário'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='pautas',
        verbose_name='Área'
    )
    
    # Inputs do usuário
    theme = models.CharField(max_length=500, verbose_name='Tema')
    target_audience = models.CharField(max_length=200, verbose_name='Público-alvo')
    objective = models.CharField(
        max_length=100,
        choices=[
            ('engajamento', 'Engajamento'),
            ('conversao', 'Conversão'),
            ('educacao', 'Educação'),
            ('branding', 'Branding'),
            ('vendas', 'Vendas'),
        ],
        verbose_name='Objetivo'
    )
    additional_context = models.TextField(blank=True, verbose_name='Contexto Adicional')
    
    # Outputs gerados
    title = models.CharField(max_length=500, verbose_name='Título')
    description = models.TextField(verbose_name='Descrição')
    key_points = models.JSONField(
        default=list,
        verbose_name='Pontos-chave',
        help_text='Lista de pontos principais'
    )
    suggested_formats = models.JSONField(
        default=list,
        verbose_name='Formatos Sugeridos',
        help_text='["post", "carrossel", "video", etc]'
    )
    research_sources = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Fontes de Pesquisa',
        help_text='URLs e referências usadas'
    )
    trends_related = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Trends Relacionadas'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('processing', 'Processando'),
            ('completed', 'Concluída'),
            ('error', 'Erro'),
        ],
        default='processing',
        verbose_name='Status'
    )
    error_message = models.TextField(blank=True, verbose_name='Mensagem de Erro')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Concluído em')
    
    class Meta:
        verbose_name = 'Pauta'
        verbose_name_plural = 'Pautas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user}"


class Post(models.Model):
    """
    Posts de redes sociais gerados por IA (Instagram, Facebook, LinkedIn, etc)
    """
    # Multi-tenant
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='posts',
        null=True,
        blank=True,
        verbose_name='Organização',
        help_text='Organização à qual este post pertence'
    )
    
    # Auditoria (manter user e area além de organization)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name='Usuário'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name='Área'
    )
    pauta = models.ForeignKey(
        Pauta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        verbose_name='Pauta'
    )
    
    # Campos de texto estruturados
    requested_theme = models.TextField(
        blank=True,
        verbose_name='Tema Solicitado',
        help_text='Tema solicitado pelo usuário para geração do post'
    )
    title = models.CharField(
        max_length=220,
        blank=True,
        verbose_name='Título',
        help_text='Título do post (se aplicável)'
    )
    subtitle = models.CharField(
        max_length=220,
        blank=True,
        verbose_name='Subtítulo',
        help_text='Subtítulo do post (se aplicável)'
    )
    
    # Tipo de conteúdo
    content_type = models.CharField(
        max_length=20,
        choices=[
            ('post', 'Post'),
            ('carrossel', 'Carrossel'),
            ('story', 'Story'),
            ('reels', 'Reels'),
        ],
        verbose_name='Tipo'
    )
    
    # Rede social alvo
    social_network = models.CharField(
        max_length=20,
        choices=[
            ('instagram', 'Instagram'),
            ('facebook', 'Facebook'),
            ('linkedin', 'LinkedIn'),
            ('twitter', 'Twitter/X'),
            ('tiktok', 'TikTok'),
        ],
        verbose_name='Rede Social'
    )
    
    # Provider de IA usado
    ia_provider = models.CharField(
        max_length=20,
        choices=[
            ('openai', 'OpenAI'),
            ('gemini', 'Google Gemini'),
        ],
        verbose_name='Provider IA'
    )
    ia_model_text = models.CharField(max_length=50, verbose_name='Modelo IA Texto')
    ia_model_image = models.CharField(max_length=50, blank=True, verbose_name='Modelo IA Imagem')
    
    # Conteúdo gerado
    caption = models.TextField(verbose_name='Legenda')
    hashtags = models.JSONField(default=list, verbose_name='Hashtags')
    
    # Call-to-Action
    cta = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='CTA',
        help_text='Call-to-action do post'
    )
    cta_requested = models.BooleanField(
        default=True,
        verbose_name='CTA Solicitado',
        help_text='Usuário quer CTA no post'
    )
    
    # Formatos múltiplos e carrossel
    formats = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Formatos',
        help_text='Lista de formatos: ["feed", "story", "reels"]'
    )
    is_carousel = models.BooleanField(
        default=False,
        verbose_name='É Carrossel',
        help_text='Post é um carrossel (múltiplas imagens)'
    )
    image_count = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Quantidade de Imagens',
        help_text='Número de imagens no carrossel'
    )
    slides_metadata = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Metadados dos Slides',
        help_text='Dados estruturados de cada slide do carrossel'
    )
    
    # Sistema de revisões
    revisions_remaining = models.PositiveSmallIntegerField(
        default=2,
        verbose_name='Revisões Restantes',
        help_text='Número de revisões que o usuário ainda pode solicitar'
    )
    
    # Thread/Job tracking
    thread_id = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='Thread ID',
        help_text='ID do thread/job de processamento (N8N, GPT, etc)'
    )
    
    # Imagem gerada (S3)
    has_image = models.BooleanField(default=False, verbose_name='Tem Imagem')
    image_s3_key = models.CharField(max_length=500, blank=True, verbose_name='Chave S3 Imagem')
    image_s3_url = models.URLField(max_length=1000, blank=True, verbose_name='URL S3 Imagem')
    image_prompt = models.TextField(blank=True, verbose_name='Prompt da Imagem')
    image_width = models.IntegerField(null=True, blank=True, verbose_name='Largura')
    image_height = models.IntegerField(null=True, blank=True, verbose_name='Altura')
    
    # Status e aprovação
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Rascunho'),
            ('awaiting_approval', 'Aguardando Aprovação'),
            ('in_adjustment', 'Em Ajuste'),
            ('approved', 'Aprovado'),
            ('rejected', 'Rejeitado'),
            ('published', 'Publicado'),
            ('archived', 'Arquivado'),
        ],
        default='draft',
        verbose_name='Status'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-created_at']
        db_table = 'content_generatedcontent'  # Manter nome da tabela existente
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['social_network']),
        ]
    
    def __str__(self):
        return f"{self.get_content_type_display()} - {self.social_network} - {self.created_at}"
    
    def hashtag_list(self):
        """Retorna lista de hashtags formatadas"""
        if not self.hashtags:
            return []
        
        # Se já é lista (JSONField)
        if isinstance(self.hashtags, list):
            return [tag if tag.startswith("#") else f"#{tag}" for tag in self.hashtags if tag]
        
        # Se é string (fallback)
        tokens = [item.strip() for item in str(self.hashtags).replace("#", " #").split()]
        return [tag if tag.startswith("#") else f"#{tag}" for tag in tokens if tag]
    
    @property
    def primary_format(self):
        """Retorna o formato principal (primeiro da lista)"""
        if not self.formats:
            return self.content_type or ""
        return self.formats[0] if self.formats else ""
    
    def _normalized_formats(self):
        """Retorna formatos normalizados"""
        formats = []
        for value in self.formats or []:
            if not value:
                continue
            normalized = str(value).strip().lower()
            if normalized and normalized not in formats:
                formats.append(normalized)
        if not formats and self.content_type:
            formats = [self.content_type]
        return formats


class Asset(models.Model):
    """
    Biblioteca de assets (imagens, vídeos, etc)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assets',
        verbose_name='Usuário'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='assets',
        verbose_name='Área'
    )
    
    title = models.CharField(max_length=200, verbose_name='Título')
    description = models.TextField(blank=True, verbose_name='Descrição')
    
    # Tipo de asset
    asset_type = models.CharField(
        max_length=20,
        choices=[
            ('image', 'Imagem'),
            ('video', 'Vídeo'),
            ('document', 'Documento'),
        ],
        verbose_name='Tipo'
    )
    
    # S3
    s3_key = models.CharField(max_length=500, verbose_name='Chave S3')
    s3_url = models.URLField(max_length=1000, verbose_name='URL S3')
    file_size = models.BigIntegerField(verbose_name='Tamanho (bytes)')
    content_type = models.CharField(max_length=100, verbose_name='Content Type')
    
    # Metadados para imagens
    width = models.IntegerField(null=True, blank=True, verbose_name='Largura')
    height = models.IntegerField(null=True, blank=True, verbose_name='Altura')
    
    # Tags para busca
    tags = models.JSONField(default=list, blank=True, verbose_name='Tags')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['asset_type']),
        ]
    
    def __str__(self):
        return self.title


class TrendMonitor(models.Model):
    """
    Monitoramento de trends (Google Trends, etc)
    """
    keyword = models.CharField(max_length=200, verbose_name='Palavra-chave')
    source = models.CharField(
        max_length=50,
        choices=[
            ('google_trends', 'Google Trends'),
            ('reddit', 'Reddit'),
            ('twitter', 'Twitter/X'),
            ('youtube', 'YouTube'),
        ],
        verbose_name='Fonte'
    )
    
    # Dados da trend
    trend_score = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Score',
        help_text='0-100'
    )
    volume = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Volume',
        help_text='Volume de buscas/menções'
    )
    growth_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Taxa de Crescimento (%)'
    )
    
    # Análise IA
    relevance = models.CharField(
        max_length=20,
        choices=[
            ('high', 'Alta'),
            ('medium', 'Média'),
            ('low', 'Baixa'),
        ],
        verbose_name='Relevância'
    )
    ia_analysis = models.TextField(verbose_name='Análise IA')
    suggested_actions = models.JSONField(
        default=list,
        verbose_name='Ações Sugeridas'
    )
    
    # Metadados
    raw_data = models.JSONField(default=dict, verbose_name='Dados Brutos')
    related_topics = models.JSONField(default=list, blank=True, verbose_name='Tópicos Relacionados')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    alert_sent = models.BooleanField(default=False, verbose_name='Alerta Enviado')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Trend Monitor'
        verbose_name_plural = 'Trends Monitoradas'
        ordering = ['-trend_score', '-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['keyword']),
            models.Index(fields=['relevance']),
            models.Index(fields=['-trend_score']),
        ]
    
    def __str__(self):
        return f"{self.keyword} - {self.get_relevance_display()} ({self.trend_score})"


class WebInsight(models.Model):
    """
    Insights de pesquisa web (scraping + análise IA)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='web_insights',
        verbose_name='Usuário'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='web_insights',
        verbose_name='Área'
    )
    
    # Query de pesquisa
    query = models.CharField(max_length=500, verbose_name='Query')
    search_type = models.CharField(
        max_length=20,
        choices=[
            ('topic', 'Tópico Geral'),
            ('competitor', 'Concorrente'),
            ('trend', 'Trend'),
        ],
        verbose_name='Tipo de Pesquisa'
    )
    
    # URLs pesquisadas
    urls_scraped = models.JSONField(default=list, verbose_name='URLs Pesquisadas')
    
    # Resultados
    summary = models.TextField(verbose_name='Resumo')
    key_insights = models.JSONField(default=list, verbose_name='Insights Principais')
    recommendations = models.TextField(blank=True, verbose_name='Recomendações')
    
    # Dados brutos
    raw_content = models.TextField(blank=True, verbose_name='Conteúdo Bruto')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('processing', 'Processando'),
            ('completed', 'Concluído'),
            ('error', 'Erro'),
        ],
        default='processing',
        verbose_name='Status'
    )
    error_message = models.TextField(blank=True, verbose_name='Mensagem de Erro')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Concluído em')
    
    class Meta:
        verbose_name = 'Web Insight'
        verbose_name_plural = 'Web Insights'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.query} - {self.created_at}"


class IAModelUsage(models.Model):
    """
    Tracking detalhado de uso de modelos IA
    Para cálculo de custos e métricas
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ia_usages',
        verbose_name='Usuário'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='ia_usages',
        verbose_name='Área'
    )
    content = models.ForeignKey(
        GeneratedContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ia_usages',
        verbose_name='Conteúdo'
    )
    
    # Identificação do modelo
    provider = models.CharField(
        max_length=20,
        choices=[
            ('openai', 'OpenAI'),
            ('gemini', 'Google Gemini'),
            ('perplexity', 'Perplexity'),
        ],
        verbose_name='Provider'
    )
    model = models.CharField(max_length=50, verbose_name='Modelo')
    operation = models.CharField(
        max_length=50,
        choices=[
            ('pauta', 'Geração de Pauta'),
            ('post_text', 'Geração de Texto'),
            ('post_image', 'Geração de Imagem'),
            ('trend_analysis', 'Análise de Trend'),
            ('web_research', 'Pesquisa Web'),
        ],
        verbose_name='Operação'
    )
    
    # Métricas de uso
    tokens_input = models.IntegerField(default=0, verbose_name='Tokens Input')
    tokens_output = models.IntegerField(default=0, verbose_name='Tokens Output')
    tokens_total = models.IntegerField(default=0, verbose_name='Tokens Total')
    
    # Custo
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name='Custo (USD)'
    )
    
    # Performance
    execution_time_seconds = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        verbose_name='Tempo de Execução (s)'
    )
    
    # Timestamps
    started_at = models.DateTimeField(verbose_name='Iniciado em')
    completed_at = models.DateTimeField(verbose_name='Concluído em')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Sucesso'),
            ('error', 'Erro'),
            ('timeout', 'Timeout'),
        ],
        verbose_name='Status'
    )
    error_message = models.TextField(blank=True, verbose_name='Mensagem de Erro')
    
    class Meta:
        verbose_name = 'Uso de Modelo IA'
        verbose_name_plural = 'Usos de Modelos IA'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['area', '-started_at']),
            models.Index(fields=['provider', '-started_at']),
            models.Index(fields=['operation']),
        ]
    
    def __str__(self):
        return f"{self.provider}/{self.model} - {self.operation} - {self.cost_usd} USD"


class ContentMetrics(models.Model):
    """
    Métricas do ciclo de vida do conteúdo
    Para análise de performance e validação do MVP
    """
    content = models.OneToOneField(
        GeneratedContent,
        on_delete=models.CASCADE,
        related_name='metrics',
        verbose_name='Conteúdo'
    )
    
    # Tempo de Criação
    creation_started_at = models.DateTimeField(verbose_name='Criação Iniciada em')
    creation_completed_at = models.DateTimeField(verbose_name='Criação Concluída em')
    creation_duration_seconds = models.IntegerField(verbose_name='Duração Criação (s)')
    
    # Tempo de Aprovação
    submitted_for_approval_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enviado para Aprovação em'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Aprovado em'
    )
    approval_duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duração Aprovação (s)'
    )
    
    # Ajustes
    adjustment_count = models.IntegerField(default=0, verbose_name='Quantidade de Ajustes')
    total_adjustment_time_seconds = models.IntegerField(
        default=0,
        verbose_name='Tempo Total de Ajustes (s)'
    )
    
    # Custos Agregados
    total_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='Custo Total (USD)'
    )
    total_tokens = models.IntegerField(default=0, verbose_name='Tokens Total')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Métrica de Conteúdo'
        verbose_name_plural = 'Métricas de Conteúdo'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Métricas - {self.content}"
    
    def get_total_duration_seconds(self):
        """Retorna duração total (criação + aprovação + ajustes)"""
        total = self.creation_duration_seconds
        if self.approval_duration_seconds:
            total += self.approval_duration_seconds
        total += self.total_adjustment_time_seconds
        return total


class VideoAvatarStatus(models.Model):
    """Status possíveis para vídeos avatar"""
    code = models.CharField(max_length=40, unique=True, verbose_name='Código')
    label = models.CharField(max_length=120, verbose_name='Label')
    
    class Meta:
        ordering = ["id"]
        verbose_name = "Status de Vídeo Avatar"
        verbose_name_plural = "Status de Vídeos Avatar"
    
    def __str__(self):
        return self.label


class VideoAvatar(models.Model):
    """
    Vídeo Avatar gerado a partir de imagem + script.
    
    Workflow:
    1. Cliente solicita (upload avatar + script)
    2. Email enviado para equipe de produção
    3. Equipe faz upload do vídeo no admin
    4. Cliente é notificado automaticamente
    """
    from apps.core.storage import VideoAvatarStorage, VideoThumbnailStorage, AvatarImageStorage
    from django.utils import timezone
    
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name="videos_avatar",
        verbose_name='Organização'
    )
    
    # Entrada do cliente
    avatar_image = models.ImageField(
        upload_to='%Y/%m/%d/',
        storage=AvatarImageStorage(),
        help_text="Imagem do avatar/personagem (foto/ilustração)",
        verbose_name='Imagem do Avatar'
    )
    script_text = models.TextField(
        max_length=500,
        help_text="Texto para locução/legenda do vídeo (máx 500 caracteres)",
        verbose_name='Texto do Script'
    )
    avatar_action = models.CharField(
        max_length=200,
        blank=True,
        help_text="Ação desejada: 'acenar', 'sorrir', 'olhar para câmera', etc.",
        verbose_name='Ação do Avatar'
    )
    
    # Vídeo gerado (upload pela equipe)
    video_file = models.FileField(
        upload_to='%Y/%m/%d/',
        storage=VideoAvatarStorage(),
        blank=True,
        null=True,
        help_text="Vídeo final gerado (MP4)",
        verbose_name='Arquivo de Vídeo'
    )
    video_duration = models.FloatField(
        default=0,
        help_text="Duração do vídeo em segundos",
        verbose_name='Duração do Vídeo'
    )
    video_thumbnail = models.ImageField(
        upload_to='%Y/%m/%d/',
        storage=VideoThumbnailStorage(),
        blank=True,
        null=True,
        help_text="Thumbnail do vídeo (gerado automaticamente)",
        verbose_name='Thumbnail do Vídeo'
    )
    
    # Status e controle
    status = models.ForeignKey(
        VideoAvatarStatus,
        on_delete=models.PROTECT,
        related_name="videos",
        verbose_name='Status'
    )
    revisions_remaining = models.PositiveSmallIntegerField(
        default=1,
        help_text="Revisões restantes (padrão: 1)",
        verbose_name='Revisões Restantes'
    )
    is_revision_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revisions',
        help_text="Se for revisão, aponta para o vídeo original",
        verbose_name='Revisão de'
    )
    
    # Prazos e SLA
    expected_delivery_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Prazo estimado de entrega (48h úteis)",
        verbose_name='Entrega Esperada em'
    )
    delivered_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Data/hora em que vídeo foi entregue ao cliente",
        verbose_name='Entregue em'
    )
    
    # Metadados
    thread_id = models.CharField(
        max_length=160,
        blank=True,
        help_text="ID do job de processamento (se aplicável)",
        verbose_name='Thread ID'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vídeo Avatar'
        verbose_name_plural = 'Vídeos Avatar'
    
    def __str__(self):
        return f"Vídeo #{self.pk} - {self.organization.name}"
    
    def save(self, *args, **kwargs):
        # Calcular prazo de entrega na criação
        if not self.pk and not self.expected_delivery_at:
            from apps.core.utils import calculate_video_delivery_deadline
            from django.conf import settings
            from django.utils import timezone
            
            self.expected_delivery_at = calculate_video_delivery_deadline(
                self.created_at or timezone.now(),
                base_hours=getattr(settings, 'VIDEO_AVATAR_SLA_HOURS', 48),
                include_weekends=getattr(settings, 'VIDEO_AVATAR_INCLUDE_WEEKENDS', False),
                business_hours_only=getattr(settings, 'VIDEO_AVATAR_BUSINESS_HOURS_ONLY', True)
            )
        
        # Marcar como entregue quando vídeo é adicionado pela primeira vez
        if self.video_file and not self.delivered_at:
            from django.utils import timezone
            self.delivered_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Verifica se está atrasado"""
        if not self.expected_delivery_at or self.delivered_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expected_delivery_at
    
    @property
    def delivery_status_display(self):
        """Status de entrega amigável para display"""
        from django.utils import timezone
        
        if self.delivered_at:
            delta = self.delivered_at - self.created_at
            hours = delta.total_seconds() / 3600
            return f'✅ Entregue em {hours:.1f}h'
        
        if self.is_overdue:
            return '⚠️ ATRASADO'
        
        if self.expected_delivery_at:
            remaining = self.expected_delivery_at - timezone.now()
            hours = remaining.total_seconds() / 3600
            if hours > 0:
                return f'⏳ Faltam {hours:.1f}h'
            else:
                return '⚠️ VENCIDO'
        
        return '—'
