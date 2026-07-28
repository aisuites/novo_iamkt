from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import User, Area
from apps.core.managers import OrganizationScopedManager
from apps.knowledge.models import KnowledgeBase


class Pauta(models.Model):
    """
    Pautas geradas por IA para criação de conteúdo
    """
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='pautas',
        null=True,
        blank=True,
        verbose_name='Organização',
        help_text='Organização à qual esta pauta pertence'
    )
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
        blank=True,
        verbose_name='Pontos-chave',
        help_text='Lista de pontos principais'
    )
    suggested_formats = models.JSONField(
        default=list,
        blank=True,
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
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
    
    def save(self, *args, **kwargs):
        """
        Garantir integridade: organization da pauta DEVE ser igual à organization do user.
        Previne inconsistências de dados entre tenants.
        """
        if self.user and self.user.organization:
            # Forçar organization da pauta = organization do user
            self.organization = self.user.organization
        super().save(*args, **kwargs)


# NOTA: Model Post foi movido para apps.posts (app dedicada)
# Para usar Post, importe de: from apps.posts.models import Post


class Asset(models.Model):
    """
    Biblioteca de assets (imagens, vídeos, etc)
    """
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='assets',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
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
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='trend_monitors',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
    class Meta:
        verbose_name = 'Trend Monitor'
        verbose_name_plural = 'Trend Monitors'
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
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='web_insights',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
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
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='ia_usages',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
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
        'posts.Post',
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
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
        'posts.Post',
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


class HeygenAvatar(models.Model):
    """
    APRESENTADOR HeyGen liberado para uma organização (a PESSOA, não o visual).

    Espelha a hierarquia da HeyGen: avatar group (pessoa) → looks (variações
    de roupa/cenário, em HeygenLook). A voz pertence à pessoa e vale para
    todos os looks. Cadastrado APENAS pela equipe interna; os looks são
    puxados da API via sync (heygen_sync / botão no admin).
    """
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='heygen_avatars',
        verbose_name='Organização',
    )
    name = models.CharField(
        max_length=120,
        help_text='Nome de exibição para o cliente (ex.: "Mauricio")',
        verbose_name='Nome',
    )
    group_id = models.CharField(
        max_length=64,
        blank=True,
        help_text='ID do avatar GROUP na HeyGen — permite sincronizar os looks '
                  'automaticamente (GET /v3/avatars/looks?group_id=...)',
        verbose_name='Group ID (HeyGen)',
    )
    voice_id = models.CharField(
        max_length=64,
        help_text='Voz pt-BR da HeyGen usada com este apresentador — GET /v3/voices',
        verbose_name='Voice ID (HeyGen)',
    )
    engine = models.CharField(
        max_length=16,
        default='avatar_iv',
        choices=[('avatar_iv', 'Avatar IV'), ('avatar_v', 'Avatar V')],
        help_text='Confirmar em supported_api_engines dos looks antes de usar avatar_v',
        verbose_name='Engine',
    )
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    objects = OrganizationScopedManager()

    class Meta:
        ordering = ['name']
        verbose_name = 'Apresentador HeyGen'
        verbose_name_plural = 'Apresentadores HeyGen'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'group_id'],
                name='uniq_heygen_avatar_org_group',
                condition=~models.Q(group_id=''),
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.organization.name})'


class HeygenLook(models.Model):
    """
    Look (visual) de um apresentador: roupa + cenário + enquadramento.
    É o que vai como avatar_id no POST /v3/videos. Criado na plataforma
    HeyGen e puxado pelo sync; a equipe controla o que o cliente vê
    via is_active (looks novos entram INATIVOS — curadoria).
    """
    from apps.core.storage import AvatarImageStorage

    avatar = models.ForeignKey(
        HeygenAvatar,
        on_delete=models.CASCADE,
        related_name='looks',
        verbose_name='Apresentador',
    )
    look_id = models.CharField(
        max_length=64,
        help_text='ID do LOOK na HeyGen (vai no payload do vídeo)',
        verbose_name='Look ID (HeyGen)',
    )
    name = models.CharField(
        max_length=160,
        help_text='Nome de exibição (ex.: "Escritório", "Casual")',
        verbose_name='Nome',
    )
    avatar_type = models.CharField(
        max_length=24,
        blank=True,
        help_text='photo_avatar | digital_twin (informativo, vem do sync)',
        verbose_name='Tipo',
    )
    preview_image = models.ImageField(
        upload_to='heygen/%Y/%m/',
        storage=AvatarImageStorage(),
        blank=True,
        null=True,
        help_text='Foto exibida no card do formulário (o sync baixa da HeyGen)',
        verbose_name='Imagem de Preview',
    )
    is_active = models.BooleanField(
        default=False,
        help_text='Só looks ativos aparecem para o cliente (curadoria da equipe)',
        verbose_name='Ativo',
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Pré-selecionado no formulário',
        verbose_name='Padrão',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        ordering = ['-is_default', 'name']
        verbose_name = 'Look HeyGen'
        verbose_name_plural = 'Looks HeyGen'
        constraints = [
            models.UniqueConstraint(
                fields=['avatar', 'look_id'],
                name='uniq_heygen_look_avatar_look',
            ),
        ]

    def __str__(self):
        return f'{self.avatar.name} — {self.name}'


class HeygenWebhookEvent(models.Model):
    """Dedup de entregas do webhook HeyGen (Heygen-Event-Id é único por entrega)."""
    event_id = models.CharField(max_length=128, unique=True, verbose_name='Event ID')
    received_at = models.DateTimeField(auto_now_add=True, verbose_name='Recebido em')

    class Meta:
        verbose_name = 'Evento de Webhook HeyGen'
        verbose_name_plural = 'Eventos de Webhook HeyGen'

    def __str__(self):
        return self.event_id


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
    avatar = models.ForeignKey(
        HeygenAvatar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos',
        help_text='Apresentador do catálogo da org',
        verbose_name='Apresentador HeyGen',
    )
    look = models.ForeignKey(
        HeygenLook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos',
        help_text='Look (visual) escolhido — é o avatar_id enviado à HeyGen',
        verbose_name='Look HeyGen',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos_avatar',
        help_text='Usuário que solicitou o vídeo (recebe os emails)',
        verbose_name='Solicitado por',
    )
    avatar_image = models.ImageField(
        upload_to='%Y/%m/%d/',
        storage=AvatarImageStorage(),
        blank=True,
        null=True,
        help_text="Legado (fluxo manual): imagem enviada pelo cliente",
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
        help_text="Direção de atuação enviada como motion_prompt (Avatar IV): "
                  "'fale gesticulando', 'tom animado', 'sorria no final'...",
        verbose_name='Gestos / Atuação'
    )
    voice_speed = models.FloatField(
        default=1.0,
        help_text='Velocidade da fala (0.5–2.0); vai em voice_settings.speed',
        verbose_name='Velocidade da Fala',
    )
    aspect_ratio = models.CharField(
        max_length=8,
        default='auto',
        choices=[('auto', 'Automático (segue o look)'), ('9:16', 'Vertical 9:16'),
                 ('16:9', 'Horizontal 16:9'), ('1:1', 'Quadrado 1:1')],
        help_text='Formato do vídeo enviado à HeyGen',
        verbose_name='Formato',
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

    # Integração HeyGen (fecha na criação + webhook; ver skill heygen-django)
    heygen_video_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text='video_id retornado pelo POST /v3/videos',
        verbose_name='Video ID (HeyGen)',
    )
    idempotency_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        help_text='Idempotency-Key enviada à HeyGen (uuid5 determinístico) — '
                  'retry do Celery nunca gera vídeo cobrado em dobro',
        verbose_name='Idempotency Key',
    )
    estimated_duration = models.FloatField(
        default=0,
        help_text='Duração estimada pelo roteiro (s) antes do render; a real '
                  'fica em video_duration',
        verbose_name='Duração Estimada',
    )
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        help_text='Custo real (duração × tarifa/s), fechado no webhook',
        verbose_name='Custo (USD)',
    )
    error_code = models.CharField(
        max_length=64,
        blank=True,
        help_text='Código de erro da HeyGen quando status=failed',
        verbose_name='Código de Erro',
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Mensagem de Erro',
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vídeo Avatar'
        verbose_name_plural = 'Vídeos Avatar'
    
    def __str__(self):
        return f"Vídeo #{self.pk} - {self.organization.name}"
    
    def save(self, *args, **kwargs):
        # Prazo de entrega: geração via HeyGen leva minutos; 1h é o SLA
        # "algo deu errado" (o util de 48h úteis do fluxo manual nunca existiu)
        if not self.pk and not self.expected_delivery_at:
            from datetime import timedelta

            from django.conf import settings
            from django.utils import timezone

            sla_minutes = getattr(settings, 'VIDEO_AVATAR_SLA_MINUTES', 60)
            self.expected_delivery_at = timezone.now() + timedelta(minutes=sla_minutes)
        
        # Marcar como entregue quando vídeo é adicionado pela primeira vez
        if self.video_file and not self.delivered_at:
            from django.utils import timezone
            self.delivered_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def download_url(self):
        """URL assinada que força download (attachment) em vez de abrir o MP4."""
        if not self.video_file:
            return None
        try:
            return self.video_file.storage.url(
                self.video_file.name,
                parameters={'ResponseContentDisposition':
                            f'attachment; filename="video-avatar-{self.pk}.mp4"'})
        except Exception:
            return self.video_file.url

    @property
    def css_aspect(self):
        """aspect-ratio CSS do player conforme o formato pedido."""
        return {'16:9': '16/9', '1:1': '1/1'}.get(self.aspect_ratio, '9/16')

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
