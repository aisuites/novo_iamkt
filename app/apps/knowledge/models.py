from django.db import models
from django.core.validators import URLValidator
from django.utils.text import slugify
from apps.core.models import User


class InternalSegment(models.Model):
    """
    Segmento/Área Interna da Organização
    Permite hierarquia (parent/child) e auditoria completa
    """
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        related_name='internal_segments',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Nome',
        help_text='Ex: Marketing, Operacional, Médicos'
    )
    code = models.SlugField(
        max_length=100,
        verbose_name='Código',
        help_text='Gerado automaticamente a partir do nome'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descrição',
        help_text='Descrição detalhada do segmento'
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name='Segmento Pai',
        help_text='Para criar hierarquia (ex: Marketing > Digital)'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Ordem',
        help_text='Ordem de exibição'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Desmarque para desativar sem excluir'
    )
    
    # Auditoria
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='segments_updated',
        verbose_name='Atualizado por'
    )
    
    class Meta:
        verbose_name = 'Segmento Interno'
        verbose_name_plural = 'Segmentos Internos'
        ordering = ['order', 'name']
        unique_together = [['knowledge_base', 'code']]
        indexes = [
            models.Index(fields=['knowledge_base', 'is_active']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-gerar código se não fornecido
        if not self.code:
            base_slug = slugify(self.name)
            self.code = base_slug
            
            # Garantir unicidade dentro da KB
            counter = 1
            while InternalSegment.objects.filter(
                knowledge_base=self.knowledge_base,
                code=self.code
            ).exclude(pk=self.pk).exists():
                self.code = f"{base_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Retorna o caminho completo na hierarquia"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_children_count(self):
        """Retorna quantidade de filhos ativos"""
        return self.children.filter(is_active=True).count()


class KnowledgeBase(models.Model):
    """
    Base de Conhecimento - Multi-tenant
    Contém 7 blocos temáticos que definem o DNA da marca
    Cada organização tem sua própria base de conhecimento
    """
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='knowledge_bases',
        null=True,
        blank=True,
        verbose_name='Organização',
        help_text='Organização à qual esta base de conhecimento pertence'
    )
    
    # BLOCO 1: IDENTIDADE INSTITUCIONAL
    nome_empresa = models.CharField(max_length=200, verbose_name='Nome da Empresa')
    missao = models.TextField(verbose_name='Missão')
    visao = models.TextField(blank=True, verbose_name='Visão')
    valores = models.TextField(verbose_name='Valores')
    historia = models.TextField(blank=True, verbose_name='História')
    
    # BLOCO 2: PÚBLICO E SEGMENTOS
    publico_externo = models.TextField(verbose_name='Público Externo')
    publico_interno = models.TextField(blank=True, verbose_name='Público Interno')
    segmentos_internos = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Segmentos Internos',
        help_text='Lista de segmentos: ["Gestores", "Operacional", etc]'
    )
    
    # BLOCO 3: POSICIONAMENTO E DIFERENCIAIS
    posicionamento = models.TextField(verbose_name='Posicionamento de Marca')
    diferenciais = models.TextField(verbose_name='Diferenciais Competitivos')
    proposta_valor = models.TextField(blank=True, verbose_name='Proposta de Valor')
    
    # BLOCO 4: TOM DE VOZ E LINGUAGEM
    tom_voz_externo = models.TextField(verbose_name='Tom de Voz Externo')
    tom_voz_interno = models.TextField(blank=True, verbose_name='Tom de Voz Interno')
    palavras_recomendadas = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Palavras Recomendadas',
        help_text='Lista de palavras-chave da marca'
    )
    palavras_evitar = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Palavras a Evitar',
        help_text='Lista de palavras que não devem ser usadas'
    )
    
    # BLOCO 5: IDENTIDADE VISUAL
    paleta_cores = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Paleta de Cores (LEGADO)',
        help_text='⚠️ DEPRECADO: Use ColorPalette model. Este campo será removido em versão futura.'
    )
    tipografia = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Tipografia (LEGADO)',
        help_text='⚠️ DEPRECADO: Use CustomFont model. Este campo será removido em versão futura.'
    )
    
    # BLOCO 6: SITES E REDES SOCIAIS
    site_institucional = models.URLField(blank=True, verbose_name='Site Institucional')
    redes_sociais = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Redes Sociais (LEGADO)',
        help_text='⚠️ DEPRECADO: Use SocialNetwork model. Este campo será removido em versão futura.'
    )
    templates_redes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Templates por Rede Social',
        help_text='Configurações específicas por rede social'
    )
    
    # BLOCO 7: DADOS E INSIGHTS
    fontes_confiaveis = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Fontes Confiáveis',
        help_text='Lista de URLs de pesquisas confiáveis'
    )
    canais_trends = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Canais de Trends',
        help_text='Canais customizados para monitoramento'
    )
    palavras_chave_trends = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Palavras-chave para Trends',
        help_text='Termos para monitoramento automático'
    )
    
    # STATUS E COMPLETUDE
    completude_percentual = models.IntegerField(
        default=0,
        verbose_name='Completude (%)',
        help_text='Calculado automaticamente'
    )
    is_complete = models.BooleanField(
        default=False,
        verbose_name='Base Completa',
        help_text='Indica se atende requisitos mínimos'
    )
    
    # TIMESTAMPS
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    last_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='knowledge_updates',
        verbose_name='Última atualização por'
    )
    
    class Meta:
        verbose_name = 'Base de Conhecimento'
        verbose_name_plural = 'Bases de Conhecimento'
    
    def __str__(self):
        return f"Base {self.organization.name} - {self.nome_empresa}"
    
    def save(self, *args, **kwargs):
        """Calcula completude antes de salvar"""
        self.completude_percentual = self.calculate_completude()
        self.is_complete = self.completude_percentual >= 70
        super().save(*args, **kwargs)
    
    def calculate_completude(self):
        """
        Calcula percentual de completude baseado em campos obrigatórios
        Cada bloco tem peso igual (14.28% cada = 100/7)
        Usa models relacionados (ColorPalette, CustomFont, SocialNetwork) ao invés de JSONFields legados
        """
        score = 0
        total_blocks = 7
        
        # BLOCO 1: Identidade (3 campos essenciais)
        bloco1_fields = [self.nome_empresa, self.missao, self.valores]
        if all(bloco1_fields):
            score += 1
        
        # BLOCO 2: Público (1 campo essencial)
        if self.publico_externo:
            score += 1
        
        # BLOCO 3: Posicionamento (2 campos essenciais)
        bloco3_fields = [self.posicionamento, self.diferenciais]
        if all(bloco3_fields):
            score += 1
        
        # BLOCO 4: Tom de Voz (3 campos essenciais)
        bloco4_fields = [
            self.tom_voz_externo,
            len(self.palavras_recomendadas or []) > 0,
            len(self.palavras_evitar or []) > 0
        ]
        if all(bloco4_fields):
            score += 1
        
        # BLOCO 5: Identidade Visual (usa models relacionados)
        # Mínimo: 2 cores OU paleta_cores legado preenchido
        has_colors = self.colors.exists() or (self.paleta_cores and len(self.paleta_cores) > 0)
        if has_colors:
            score += 1
        
        # BLOCO 6: Sites e Redes (usa SocialNetwork model)
        # Mínimo: site institucional OU pelo menos 1 rede social
        has_social = self.site_institucional or self.social_networks.exists()
        if has_social:
            score += 1
        
        # BLOCO 7: Dados (1 campo essencial)
        if len(self.fontes_confiaveis or []) > 0:
            score += 1
        
        return int((score / total_blocks) * 100)


class ReferenceImage(models.Model):
    """
    Imagens de referência para identidade visual
    Com hash perceptual para evitar repetições
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='reference_images',
        verbose_name='Base de Conhecimento'
    )
    title = models.CharField(max_length=200, verbose_name='Título')
    description = models.TextField(blank=True, verbose_name='Descrição')
    s3_key = models.CharField(max_length=500, verbose_name='Chave S3')
    s3_url = models.URLField(max_length=1000, verbose_name='URL S3')
    perceptual_hash = models.CharField(
        max_length=64,
        verbose_name='Hash Perceptual',
        help_text='Para evitar imagens similares'
    )
    file_size = models.BigIntegerField(verbose_name='Tamanho (bytes)')
    width = models.IntegerField(verbose_name='Largura')
    height = models.IntegerField(verbose_name='Altura')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Enviado por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Imagem de Referência'
        verbose_name_plural = 'Imagens de Referência'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class CustomFont(models.Model):
    """
    Fontes customizadas enviadas para S3
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='custom_fonts',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(max_length=200, verbose_name='Nome da Fonte')
    font_type = models.CharField(
        max_length=20,
        choices=[
            ('titulo', 'Título'),
            ('corpo', 'Corpo'),
            ('destaque', 'Destaque'),
        ],
        verbose_name='Tipo'
    )
    s3_key = models.CharField(max_length=500, verbose_name='Chave S3')
    s3_url = models.URLField(max_length=1000, verbose_name='URL S3')
    file_format = models.CharField(
        max_length=10,
        choices=[
            ('ttf', 'TrueType'),
            ('otf', 'OpenType'),
            ('woff', 'WOFF'),
            ('woff2', 'WOFF2'),
        ],
        verbose_name='Formato'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Enviado por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Fonte Customizada'
        verbose_name_plural = 'Fontes Customizadas'
        ordering = ['font_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_font_type_display()})"


class Logo(models.Model):
    """
    Logos da empresa (principal, variações)
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='logos',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(max_length=200, verbose_name='Nome')
    logo_type = models.CharField(
        max_length=20,
        choices=[
            ('principal', 'Principal'),
            ('horizontal', 'Horizontal'),
            ('vertical', 'Vertical'),
            ('icone', 'Ícone'),
            ('monocromatico', 'Monocromático'),
        ],
        verbose_name='Tipo'
    )
    s3_key = models.CharField(max_length=500, verbose_name='Chave S3')
    s3_url = models.URLField(max_length=1000, verbose_name='URL S3')
    file_format = models.CharField(max_length=10, verbose_name='Formato')
    is_primary = models.BooleanField(default=False, verbose_name='Logo Principal')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Enviado por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Logo'
        verbose_name_plural = 'Logos'
        ordering = ['-is_primary', 'logo_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_logo_type_display()})"


class Competitor(models.Model):
    """
    Concorrentes para análise comparativa
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='competitors',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(max_length=200, verbose_name='Nome')
    website = models.URLField(blank=True, verbose_name='Website')
    description = models.TextField(blank=True, verbose_name='Descrição')
    social_media = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Redes Sociais'
    )
    strengths = models.TextField(blank=True, verbose_name='Pontos Fortes')
    weaknesses = models.TextField(blank=True, verbose_name='Pontos Fracos')
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Concorrente'
        verbose_name_plural = 'Concorrentes'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class ColorPalette(models.Model):
    """
    Paleta de cores da marca
    Gerenciável via interface com color picker
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='colors',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(max_length=100, verbose_name='Nome da Cor')
    hex_code = models.CharField(
        max_length=7,
        verbose_name='Código HEX',
        help_text='Formato: #RRGGBB'
    )
    color_type = models.CharField(
        max_length=20,
        choices=[
            ('primary', 'Primária'),
            ('secondary', 'Secundária'),
            ('accent', 'Acento'),
        ],
        verbose_name='Tipo'
    )
    order = models.IntegerField(default=0, verbose_name='Ordem')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Cor da Paleta'
        verbose_name_plural = 'Cores da Paleta'
        ordering = ['order', 'name']
        unique_together = [['knowledge_base', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.hex_code})"


class SocialNetwork(models.Model):
    """
    Redes sociais da marca
    Gerenciável via Admin sem necessidade de código
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='social_networks',
        verbose_name='Base de Conhecimento'
    )
    name = models.CharField(max_length=100, verbose_name='Nome')
    network_type = models.CharField(
        max_length=20,
        choices=[
            ('instagram', 'Instagram'),
            ('facebook', 'Facebook'),
            ('linkedin', 'LinkedIn'),
            ('youtube', 'YouTube'),
            ('tiktok', 'TikTok'),
            ('twitter', 'Twitter/X'),
            ('other', 'Outro'),
        ],
        verbose_name='Tipo de Rede'
    )
    url = models.URLField(verbose_name='URL')
    username = models.CharField(max_length=100, blank=True, verbose_name='Username')
    is_active = models.BooleanField(default=True, verbose_name='Ativa')
    order = models.IntegerField(default=0, verbose_name='Ordem')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Rede Social'
        verbose_name_plural = 'Redes Sociais'
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_network_type_display()})"


class SocialNetworkTemplate(models.Model):
    """
    Templates de conteúdo por rede social
    Define dimensões e limites específicos
    """
    social_network = models.ForeignKey(
        SocialNetwork,
        on_delete=models.CASCADE,
        related_name='templates',
        verbose_name='Rede Social'
    )
    name = models.CharField(max_length=100, verbose_name='Nome do Template')
    width = models.IntegerField(verbose_name='Largura (px)')
    height = models.IntegerField(verbose_name='Altura (px)')
    aspect_ratio = models.CharField(
        max_length=10,
        verbose_name='Aspect Ratio',
        help_text='Ex: 1:1, 9:16, 16:9'
    )
    character_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Limite de Caracteres'
    )
    hashtag_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Limite de Hashtags'
    )
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Template de Rede Social'
        verbose_name_plural = 'Templates de Redes Sociais'
        ordering = ['social_network', 'name']
    
    def __str__(self):
        return f"{self.social_network.name} - {self.name} ({self.aspect_ratio})"


class KnowledgeChangeLog(models.Model):
    """
    Histórico de alterações na Base de Conhecimento
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='change_logs',
        verbose_name='Base de Conhecimento'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Usuário'
    )
    block_name = models.CharField(
        max_length=50,
        verbose_name='Bloco',
        help_text='Nome do bloco alterado'
    )
    field_name = models.CharField(max_length=100, verbose_name='Campo')
    old_value = models.TextField(blank=True, verbose_name='Valor Anterior')
    new_value = models.TextField(verbose_name='Novo Valor')
    change_summary = models.CharField(max_length=500, verbose_name='Resumo da Alteração')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Log de Alteração'
        verbose_name_plural = 'Logs de Alterações'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['knowledge_base', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.block_name} - {self.field_name} - {self.created_at}"
