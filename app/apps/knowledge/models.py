from django.db import models
from django.core.validators import URLValidator
from django.utils.text import slugify
from apps.core.models import User
from apps.core.managers import OrganizationScopedManager

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
    descricao_produto = models.TextField(blank=True, verbose_name='Descrição do Produto/Serviço')
    
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
    # Cores gerenciadas via ColorPalette model
    # Tipografia gerenciada via Typography model
    
    # BLOCO 6: SITES, REDES SOCIAIS E CONCORRÊNCIA
    site_institucional = models.URLField(blank=True, verbose_name='Site Institucional')
    # Redes sociais gerenciadas via SocialNetwork model
    concorrentes = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Concorrentes',
        help_text='Lista de concorrentes: [{"nome": "Empresa X", "url": "https://..."}, ...]'
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
    
    # ONBOARDING
    onboarding_completed = models.BooleanField(
        default=False,
        verbose_name='Onboarding Concluído',
        help_text='True quando usuário clica em "Salvar Base IAMKT" pela primeira vez e envia dados para N8N'
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Conclusão do Onboarding',
        help_text='Timestamp de quando o onboarding foi concluído'
    )
    onboarding_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_completions',
        verbose_name='Onboarding Concluído Por',
        help_text='Usuário que completou o onboarding pela primeira vez'
    )
    
    # APROVAÇÃO DE SUGESTÕES
    suggestions_reviewed = models.BooleanField(
        default=False,
        verbose_name='Sugestões Revisadas',
        help_text='True quando usuário clica em "Aplicar Sugestões Selecionadas" pela primeira vez'
    )
    suggestions_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Revisão das Sugestões',
        help_text='Timestamp de quando as sugestões foram revisadas'
    )
    suggestions_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggestions_reviews',
        verbose_name='Sugestões Revisadas Por',
        help_text='Usuário que revisou as sugestões pela primeira vez'
    )
    
    # ========================================
    # ANÁLISE N8N
    # ========================================
    
    # Análises N8N
    n8n_analysis = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Análise N8N',
        help_text='Payload completo retornado pelo N8N (primeira análise)'
    )
    n8n_compilation = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Compilação N8N',
        help_text='Compilação final retornada pelo N8N (plano de marketing, avaliações)'
    )
    accepted_suggestions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Sugestões Aceitas',
        help_text='Campos onde usuário aceitou sugestão do agente'
    )
    accepted_suggestion_fields = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Campos com Sugestões Aceitas',
        help_text='Lista de nomes de campos que tiveram sugestões aceitas (para reavaliação)'
    )
    
    # Status e metadados
    analysis_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente'),
            ('processing', 'Processando'),
            ('completed', 'Análise Concluída'),
            ('compiling', 'Compilando'),
            ('compiled', 'Compilado'),
            ('error', 'Erro')
        ],
        default='pending',
        verbose_name='Status da Análise'
    )
    compilation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente'),
            ('processing', 'Processando'),
            ('completed', 'Completa'),
            ('error', 'Erro'),
        ],
        default='pending',
        verbose_name='Status da Compilação'
    )
    analysis_revision_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID da Revisão N8N',
        help_text='revision_id retornado pelo N8N'
    )
    analysis_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Análise Solicitada em'
    )
    analysis_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Análise Concluída em'
    )
    compilation_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Compilação Solicitada em'
    )
    compilation_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Compilação Concluída em'
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
    
    # Manager com filtro automático por organization
    objects = OrganizationScopedManager()
    
    class Meta:
        verbose_name = 'Base de Conhecimento'
        verbose_name_plural = 'Bases de Conhecimento'
    
    def __str__(self):
        return f"Base {self.organization.name} - {self.nome_empresa}"
    
    def save(self, *args, **kwargs):
        """Salvar e calcular completude"""
        # Se já tem pk, calcular completude antes de salvar
        if self.pk:
            self.completude_percentual = self.calculate_completude()
            self.is_complete = self.completude_percentual >= 70
        
        # Salvar
        super().save(*args, **kwargs)
        
        # Se é novo (acabou de ganhar pk), calcular completude e atualizar
        if not self.completude_percentual and self.pk:
            self.completude_percentual = self.calculate_completude()
            self.is_complete = self.completude_percentual >= 70
            KnowledgeBase.objects.filter(pk=self.pk).update(
                completude_percentual=self.completude_percentual,
                is_complete=self.is_complete
            )
    
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
        # Mínimo: 2 cores na paleta
        if self.colors.exists():
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
    
    # ========================================
    # HELPER METHODS - ANÁLISE N8N
    # ========================================
    
    def get_field_analysis(self, field_name):
        """
        Retorna análise de um campo específico do N8N
        
        Args:
            field_name (str): Nome do campo (ex: 'missao', 'visao')
        
        Returns:
            dict: {
                'informado_pelo_usuario': valor,
                'avaliacao': texto,
                'status': 'fraco'|'medio'|'bom',
                'sugestao_do_agente_iamkt': texto ou lista
            }
        """
        if not self.n8n_analysis or 'payload' not in self.n8n_analysis:
            return {}
        
        return self.n8n_analysis['payload'].get(field_name, {})
    
    def set_n8n_response(self, n8n_data):
        """
        Processa e armazena resposta do N8N (primeira análise)
        
        Args:
            n8n_data (dict): Resposta completa do N8N
        """
        from django.utils import timezone
        
        # Extrair payload[0] e armazenar como objeto
        payload = n8n_data.get('payload', [{}])[0] if isinstance(n8n_data.get('payload'), list) else n8n_data.get('payload', {})
        
        self.n8n_analysis = {
            'baseId': n8n_data.get('baseId'),
            'revision_id': n8n_data.get('revision_id'),
            'received_at': timezone.now().isoformat(),
            'reference_images_analysis': n8n_data.get('reference_images_analysis', []),
            'payload': payload
        }
        
        self.analysis_revision_id = n8n_data.get('revision_id', '')
        self.analysis_status = 'completed'
        self.analysis_completed_at = timezone.now()
        
        self.save(update_fields=[
            'n8n_analysis',
            'analysis_revision_id',
            'analysis_status',
            'analysis_completed_at'
        ])
    
    def set_n8n_compilation(self, n8n_data):
        """
        Processa e armazena compilação do N8N (segundo retorno)
        
        Args:
            n8n_data (dict): Resposta de compilação do N8N
        """
        from django.utils import timezone
        
        self.n8n_compilation = {
            'received_at': timezone.now().isoformat(),
            'four_week_marketing_plan': n8n_data.get('four_week_marketing_plan', []),
            'assessment_summary': n8n_data.get('assessment_summary', {}),
            'improvements_summary': n8n_data.get('improvements_summary', {}),
            'marketing_input_summary': n8n_data.get('marketing_input_summary', '')
        }
        
        self.analysis_status = 'compiled'
        self.compilation_completed_at = timezone.now()
        
        self.save(update_fields=[
            'n8n_compilation',
            'analysis_status',
            'compilation_completed_at'
        ])
    
    def get_overall_status_summary(self):
        """
        Retorna resumo das classificações da análise N8N
        
        Returns:
            dict: {
                'fraco': 10,
                'medio': 3,
                'bom': 2,
                'total': 15,
                'percentual_bom': 13.3
            }
        """
        if not self.n8n_analysis or 'payload' not in self.n8n_analysis:
            return {'fraco': 0, 'medio': 0, 'bom': 0, 'total': 0, 'percentual_bom': 0}
        
        counts = {'fraco': 0, 'medio': 0, 'bom': 0}
        
        for field_data in self.n8n_analysis['payload'].values():
            if isinstance(field_data, dict) and 'status' in field_data:
                status = field_data['status'].lower()
                if status in counts:
                    counts[status] += 1
        
        total = sum(counts.values())
        percentual_bom = (counts['bom'] / total * 100) if total > 0 else 0
        
        return {
            **counts,
            'total': total,
            'percentual_bom': round(percentual_bom, 1)
        }
    
    def get_fields_by_status(self, status):
        """
        Retorna lista de campos com determinado status
        
        Args:
            status (str): 'fraco', 'medio' ou 'bom'
        
        Returns:
            list: ['missao', 'visao', ...]
        """
        if not self.n8n_analysis or 'payload' not in self.n8n_analysis:
            return []
        
        fields = []
        for field_name, field_data in self.n8n_analysis['payload'].items():
            if isinstance(field_data, dict) and field_data.get('status', '').lower() == status.lower():
                fields.append(field_name)
        
        return fields
    
    def has_analysis(self):
        """Verifica se já tem análise do N8N"""
        return bool(self.n8n_analysis and self.n8n_analysis.get('payload'))
    
    def has_compilation(self):
        """Verifica se já tem compilação do N8N"""
        return bool(self.n8n_compilation and self.n8n_compilation.get('four_week_marketing_plan'))
    
    def can_request_analysis(self):
        """Verifica se pode solicitar análise"""
        return self.analysis_status in ['pending', 'error', 'completed', 'compiled']
    
    def is_analysis_processing(self):
        """Verifica se análise está sendo processada"""
        return self.analysis_status == 'processing'
    
    def is_compilation_processing(self):
        """Verifica se compilação está sendo processada"""
        return self.analysis_status == 'compiling'
    
    def apply_accepted_suggestions(self, accepted_suggestions):
        """
        Atualiza campos da KB com sugestões aceitas pelo usuário
        
        Args:
            accepted_suggestions (dict): {campo: True/False}
        
        Returns:
            int: Número de sugestões aplicadas
        """
        if not self.n8n_analysis or 'payload' not in self.n8n_analysis:
            return 0
        
        # Armazena decisões
        self.accepted_suggestions = accepted_suggestions
        
        applied_count = 0
        
        # Para cada campo aceito, atualizar com sugestão
        for field_name, accepted in accepted_suggestions.items():
            if not accepted:
                continue
            
            # Buscar sugestão no n8n_analysis
            field_analysis = self.n8n_analysis['payload'].get(field_name, {})
            suggestion = field_analysis.get('sugestao_do_agente_iamkt')
            
            if not suggestion:
                continue
            
            # Atualizar campo correspondente na KB
            if hasattr(self, field_name):
                # Se sugestão é lista, converter para string ou manter como lista dependendo do campo
                if isinstance(suggestion, list):
                    # Campos que esperam lista (JSONField)
                    if field_name in ['palavras_recomendadas', 'palavras_evitar', 'fontes_confiaveis', 
                                     'canais_trends', 'palavras_chave_trends', 'concorrentes']:
                        setattr(self, field_name, suggestion)
                    else:
                        # Campos de texto, juntar lista em string
                        setattr(self, field_name, '\n'.join(suggestion) if suggestion else '')
                else:
                    setattr(self, field_name, suggestion)
                
                applied_count += 1
        
        self.save()
        return applied_count
    
    def has_accepted_suggestions(self):
        """Verifica se usuário aceitou alguma sugestão"""
        if not self.accepted_suggestions:
            return False
        
        return any(self.accepted_suggestions.values())


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
            ('ttf', 'TrueType (TTF)'),
            ('otf', 'OpenType (OTF)'),
            ('woff', 'WOFF'),
            ('woff2', 'WOFF2'),
        ],
        verbose_name='Formato',
        help_text='Formato do arquivo de fonte'
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


class Typography(models.Model):
    """
    Configuração de tipografia da marca
    Suporta Google Fonts e Fontes Customizadas (TTF/OTF)
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='typography_settings',
        verbose_name='Base de Conhecimento'
    )
    
    # Uso da fonte
    usage = models.CharField(
        max_length=50,
        verbose_name='Uso da Fonte',
        help_text='Ex: Texto corrido, Títulos, Botões, etc'
    )
    
    # Tipo de fonte
    font_source = models.CharField(
        max_length=20,
        choices=[
            ('google', 'Google Fonts'),
            ('upload', 'Upload TTF/OTF'),
        ],
        verbose_name='Origem da Fonte'
    )
    
    # GOOGLE FONTS (quando font_source='google')
    google_font_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nome da Fonte (Google)',
        help_text='Ex: Montserrat, Open Sans, Roboto'
    )
    google_font_weight = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Peso da Fonte',
        help_text='Ex: Regular, Bold, Light, 400, 700'
    )
    google_font_url = models.URLField(
        blank=True,
        verbose_name='URL Google Fonts',
        help_text='Gerado automaticamente'
    )
    
    # UPLOAD TTF/OTF (quando font_source='upload')
    custom_font = models.ForeignKey(
        CustomFont,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='typography_usages',
        verbose_name='Fonte Customizada'
    )
    
    # Metadados
    order = models.IntegerField(default=0, verbose_name='Ordem')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Atualizado por'
    )
    
    class Meta:
        verbose_name = 'Configuração de Tipografia'
        verbose_name_plural = 'Configurações de Tipografia'
        ordering = ['order', 'usage']
        unique_together = [['knowledge_base', 'usage']]
    
    def __str__(self):
        if self.font_source == 'google':
            return f"{self.usage}: {self.google_font_name} {self.google_font_weight}"
        else:
            return f"{self.usage}: {self.custom_font.name if self.custom_font else 'N/A'}"
    
    def get_font_css(self):
        """Retorna CSS para usar a fonte"""
        if self.font_source == 'google':
            return f"font-family: '{self.google_font_name}', sans-serif;"
        elif self.custom_font:
            return f"font-family: '{self.custom_font.name}', sans-serif;"
        return ""


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
