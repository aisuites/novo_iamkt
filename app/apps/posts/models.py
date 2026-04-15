from django.db import models
from apps.core.models import User, Area
from apps.core.managers import OrganizationScopedManager


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
    
    # Auditoria
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
        verbose_name='Área',
        null=True,
        blank=True
    )
    pauta = models.ForeignKey(
        'pautas.Pauta',
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
            ('whatsapp', 'WhatsApp'),
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
    
    # Imagens de referência (enviadas pelo usuário)
    reference_images = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Imagens de Referência',
        help_text='URLs S3 das imagens de referência enviadas pelo usuário'
    )
    
    # Formato da imagem (derivado automaticamente se None)
    post_format = models.ForeignKey(
        'PostFormat',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        verbose_name='Formato da Imagem',
        help_text='Formato específico (derivado automaticamente da rede social + tipo de formato se não especificado)'
    )
    
    # Imagem gerada (S3)
    has_image = models.BooleanField(default=False, verbose_name='Tem Imagem')
    image_file = models.ImageField(
        upload_to='temp/posts/',
        blank=True,
        null=True,
        verbose_name='Upload de Imagem',
        help_text='Faça upload da imagem aqui. Será automaticamente enviada para S3.'
    )
    generated_images = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Imagens Geradas',
        help_text='Array de objetos com s3_key, s3_url, width, height de cada imagem gerada'
    )
    image_s3_key = models.CharField(max_length=500, blank=True, verbose_name='Chave S3 Imagem (Principal)')
    image_s3_url = models.URLField(max_length=1000, blank=True, verbose_name='URL S3 Imagem (Principal)')
    image_prompt = models.TextField(blank=True, verbose_name='Prompt da Imagem')
    image_width = models.IntegerField(null=True, blank=True, verbose_name='Largura')
    image_height = models.IntegerField(null=True, blank=True, verbose_name='Altura')
    
    # Status e aprovação
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente de Aprovação'),
            ('generating', 'Agente Gerando Conteúdo'),
            ('image_generating', 'Agente Gerando Imagem'),
            ('image_ready', 'Imagem Disponível'),
            ('approved', 'Aprovado'),
            ('agent', 'Agente Alterando — Aguarde'),
            ('rejected', 'Rejeitado'),
        ],
        default='pending',
        verbose_name='Status'
    )

    # BRANDGUIDE PIPELINE (Fase 1)
    # Objetivo do post - influencia o template visual selecionado
    objetivo = models.CharField(
        max_length=30,
        default='institucional',
        choices=[
            ('evento', 'Divulgar evento'),
            ('venda', 'Venda / Promoção'),
            ('educacional', 'Conteúdo educacional'),
            ('institucional', 'Institucional / Branding'),
            ('bastidores', 'Bastidores / Cultura'),
            ('depoimento', 'Depoimento / Case'),
            ('datas_comemorativas', 'Datas comemorativas'),
            ('engajamento', 'Engajamento (enquete, quiz)'),
        ],
        verbose_name='Objetivo do post'
    )
    # Método de geração de imagem (para clientes com Brand Visual Spec)
    generation_method = models.CharField(
        max_length=30,
        default='free_style',
        choices=[
            ('free_style', 'Estilo livre (Gemini completo)'),
            ('controlled_render', 'Renderização controlada'),
            ('both', 'Comparar os dois'),
        ],
        verbose_name='Método de geração'
    )
    # Plano de layout decidido pelo Layout Planner (Fase 6)
    layout_plan = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Plano de Layout',
        help_text='JSON com áreas, restrições e template escolhido pela IA'
    )
    # Briefing da imagem (quando gerada pelo Copywriter ciente do layout)
    image_brief = models.TextField(
        blank=True,
        verbose_name='Briefing da imagem'
    )
    # Imagem de comparação quando generation_method='both' (Fase 8 - A/B testing)
    comparison_image_s3_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='URL S3 da imagem de comparação'
    )
    comparison_image_s3_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Chave S3 da imagem de comparação'
    )
    # Imagem raw gerada pelo Gemini antes da composição (Modo A - Fase 7)
    raw_image_s3_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='URL S3 da imagem raw'
    )
    raw_image_s3_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Chave S3 da imagem raw'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['social_network']),
        ]
    
    def __str__(self):
        return f"{self.get_content_type_display()} - {self.social_network} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        """
        Garantir integridade: organization do post DEVE ser igual à organization do user.
        """
        if self.user and self.user.organization:
            self.organization = self.user.organization
        super().save(*args, **kwargs)
    
    def hashtag_list(self):
        """Retorna lista de hashtags formatadas"""
        if not self.hashtags:
            return []
        
        if isinstance(self.hashtags, list):
            return [tag if tag.startswith("#") else f"#{tag}" for tag in self.hashtags if tag]
        
        tokens = [item.strip() for item in str(self.hashtags).replace("#", " #").split()]
        return [tag if tag.startswith("#") else f"#{tag}" for tag in tokens if tag]
    
    @property
    def primary_format(self):
        """Retorna o formato principal (primeiro da lista)"""
        if not self.formats:
            return self.content_type or ""
        return self.formats[0] if self.formats else ""


class PostImage(models.Model):
    """
    Imagens geradas para um Post (suporta múltiplas imagens por post)
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Post'
    )
    image_file = models.ImageField(
        upload_to='temp/posts/',
        blank=True,
        null=True,
        verbose_name='Upload de Imagem',
        help_text='Faça upload da imagem. Será automaticamente enviada para S3.'
    )
    s3_key = models.CharField(max_length=500, blank=True, verbose_name='Chave S3')
    s3_url = models.URLField(max_length=1000, blank=True, verbose_name='URL S3')
    width = models.IntegerField(null=True, blank=True, verbose_name='Largura')
    height = models.IntegerField(null=True, blank=True, verbose_name='Altura')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Imagem do Post'
        verbose_name_plural = 'Imagens do Post'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"Imagem {self.order} - Post #{self.post.id}"


class PostReferenceImage(models.Model):
    """
    Imagens de referência anexadas ao solicitar geração de um Post.
    Diferentes de PostImage (imagens geradas pelo N8N) e ReferenceImage (base de conhecimento).
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='reference_image_files',
        verbose_name='Post'
    )
    s3_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Chave S3'
    )
    s3_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='URL S3'
    )
    original_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nome Original'
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ordem'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )

    # INTENT (Fase 1 - pipeline de brandguide)
    # Contexto sobre como a imagem deve ser utilizada pela IA
    usage_description = models.TextField(
        blank=True,
        verbose_name='O que aproveitar desta imagem'
    )
    aspects_to_use = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Aspectos a aproveitar',
        help_text='paleta_cor, mood, composicao, tipografia_aplicada, uso_fotografia, estilo_ilustracao, grafismos, tratamento_cor'
    )
    importance = models.CharField(
        max_length=10,
        default='medium',
        choices=[
            ('high', 'Alta'),
            ('medium', 'Média'),
            ('low', 'Baixa'),
        ],
        verbose_name='Importância'
    )
    usage_type = models.CharField(
        max_length=10,
        default='inspire',
        choices=[
            ('inspire', 'Inspirar'),
            ('mimic', 'Seguir fielmente'),
            ('avoid', 'EVITAR'),
        ],
        verbose_name='Tipo de uso'
    )

    class Meta:
        verbose_name = 'Imagem de Referência do Post'
        verbose_name_plural = 'Imagens de Referência do Post'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Ref {self.order} - Post #{self.post.id} - {self.original_name}"


class PostChangeRequest(models.Model):
    """
    Solicitações de alteração de posts (texto ou imagem)
    """
    class ChangeType(models.TextChoices):
        TEXT = 'text', 'Texto'
        IMAGE = 'image', 'Imagem'
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='change_requests',
        verbose_name='Post'
    )
    message = models.TextField(
        verbose_name='Mensagem',
        help_text='Mensagem de solicitação de alteração'
    )
    requester_name = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='Nome do Solicitante'
    )
    requester_email = models.EmailField(
        max_length=254,
        blank=True,
        verbose_name='Email do Solicitante'
    )
    change_type = models.CharField(
        max_length=10,
        choices=ChangeType.choices,
        default=ChangeType.TEXT,
        verbose_name='Tipo de Alteração'
    )
    is_initial = models.BooleanField(
        default=False,
        verbose_name='É Solicitação Inicial',
        help_text='True se é a primeira solicitação (sem mensagem customizada)'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Solicitação de Alteração'
        verbose_name_plural = 'Solicitações de Alteração'
        ordering = ['-created_at']
    
    def __str__(self):
        tipo = self.get_change_type_display()
        inicial = " (inicial)" if self.is_initial else ""
        return f"{tipo}{inicial} - Post #{self.post.id}"


class PostFormat(models.Model):
    """
    Formatos padrão de imagem por rede social
    Tabela global (não vinculada a organização)
    """
    NETWORK_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('twitter', 'Twitter/X'),
        ('tiktok', 'TikTok'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    social_network = models.CharField(
        max_length=20,
        choices=NETWORK_CHOICES,
        verbose_name='Rede Social'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Nome do Formato',
        help_text='Ex: Feed Retrato, Stories, Reels'
    )
    width = models.IntegerField(
        verbose_name='Largura (px)',
        help_text='Ex: 1080'
    )
    height = models.IntegerField(
        verbose_name='Altura (px)',
        help_text='Ex: 1350'
    )
    aspect_ratio = models.CharField(
        max_length=10,
        verbose_name='Aspect Ratio',
        help_text='Ex: 4:5, 9:16, 1:1'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Ordem',
        help_text='Ordem de prioridade (menor = maior prioridade)'
    )
    
    class Meta:
        verbose_name = 'Formato de Post'
        verbose_name_plural = 'Formatos de Post'
        unique_together = [['social_network', 'name']]
        ordering = ['social_network', 'order', 'name']
    
    @property
    def dimensions(self):
        """Retorna dimensões no formato WxH"""
        return f"{self.width}x{self.height}"

    def __str__(self):
        return f"{self.get_social_network_display()} - {self.name} ({self.dimensions})"


# =====================================================================
# A/B TESTING (Fase 1 - base de métricas para Fase 8)
# =====================================================================

class PostGenerationMetric(models.Model):
    """
    Métricas de geração de posts para comparação A/B entre métodos
    (free_style vs controlled_render).
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='generation_metrics',
        verbose_name='Post'
    )
    method_used = models.CharField(
        max_length=30,
        choices=[
            ('free_style', 'Estilo livre'),
            ('controlled_render', 'Renderização controlada'),
        ],
        verbose_name='Método utilizado'
    )
    approved = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Aprovado'
    )
    revisions_requested = models.PositiveIntegerField(
        default=0,
        verbose_name='Revisões solicitadas'
    )
    time_to_approval_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tempo até aprovação (segundos)'
    )
    user_rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Avaliação do usuário (1-5)'
    )
    tokens_used = models.PositiveIntegerField(
        default=0,
        verbose_name='Tokens consumidos'
    )
    cost_usd = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
        verbose_name='Custo (USD)'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Métrica de Geração de Post'
        verbose_name_plural = 'Métricas de Geração de Posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['method_used', '-created_at']),
            models.Index(fields=['post', 'method_used']),
        ]

    def __str__(self):
        return f"Post #{self.post_id} - {self.method_used}"
