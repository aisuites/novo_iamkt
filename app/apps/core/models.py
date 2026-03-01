from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify
from decimal import Decimal
from datetime import timedelta
from calendar import monthrange


class TimeStampedModel(models.Model):
    """Classe base abstrata com timestamps automáticos"""
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class User(AbstractUser):
    """
    Modelo customizado de usuário com suporte a múltiplas áreas
    """
    PROFILE_CHOICES = [
        ('admin', 'Administrador'),
        ('ti', 'TI'),
        ('gestor', 'Gestor'),
        ('operacional', 'Operacional'),
    ]
    
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        verbose_name='Organização',
        help_text='Organização à qual o usuário pertence'
    )
    profile = models.CharField(
        max_length=20,
        choices=PROFILE_CHOICES,
        default='operacional',
        verbose_name='Perfil'
    )
    areas = models.ManyToManyField(
        'Area',
        related_name='users',
        blank=True,
        verbose_name='Áreas'
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['first_name', 'last_name']
    
    def __str__(self):
        return self.get_full_name() or self.username
    
    def has_area_permission(self, area):
        """Verifica se o usuário tem permissão para uma área específica"""
        if self.profile in ['admin', 'ti']:
            return True
        return self.areas.filter(id=area.id).exists()
    
    def get_active_areas(self):
        """Retorna áreas ativas do usuário"""
        return self.areas.filter(is_active=True)


class Area(models.Model):
    """
    Áreas/Departamentos globais (Marketing, Vendas, RH, etc)
    Compartilhadas por todas as organizations
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Nome')
    description = models.TextField(blank=True, verbose_name='Descrição')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Área Pai'
    )
    is_active = models.BooleanField(default=True, verbose_name='Ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_hierarchy(self):
        """Retorna hierarquia completa da área"""
        hierarchy = [self.name]
        parent = self.parent
        while parent:
            hierarchy.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(hierarchy)


class AuditLog(models.Model):
    """
    Log de auditoria para ações críticas
    """
    ACTION_CHOICES = [
        ('user_create', 'Criação de Usuário'),
        ('user_update', 'Atualização de Usuário'),
        ('user_delete', 'Exclusão de Usuário'),
        ('area_create', 'Criação de Área'),
        ('area_update', 'Atualização de Área'),
        ('area_delete', 'Exclusão de Área'),
        ('knowledge_update', 'Atualização Base Conhecimento'),
        ('content_create', 'Criação de Conteúdo'),
        ('content_approve', 'Aprovação de Conteúdo'),
        ('content_reject', 'Rejeição de Conteúdo'),
        ('limit_update', 'Atualização de Limite'),
        ('config_update', 'Atualização de Configuração'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        verbose_name='Usuário'
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name='Ação'
    )
    model_name = models.CharField(max_length=100, verbose_name='Modelo')
    object_id = models.IntegerField(verbose_name='ID do Objeto')
    object_repr = models.CharField(max_length=200, verbose_name='Representação')
    changes = models.JSONField(default=dict, verbose_name='Alterações')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.created_at}"


class SystemConfig(models.Model):
    """
    Configurações globais do sistema
    """
    key = models.CharField(max_length=100, unique=True, verbose_name='Chave')
    value = models.TextField(verbose_name='Valor')
    description = models.TextField(blank=True, verbose_name='Descrição')
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Configuração do Sistema'
        verbose_name_plural = 'Configurações do Sistema'
        ordering = ['key']
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_value(cls, key, default=None):
        """Retorna valor de uma configuração"""
        try:
            config = cls.objects.get(key=key, is_active=True)
            return config.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value, description=''):
        """Define valor de uma configuração"""
        config, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
        return config


class PlanTemplate(TimeStampedModel):
    """
    Template de plano com quotas configuráveis.
    Permite que gestores alterem limites sem mexer no código.
    """
    # Choices importados de Organization (definido abaixo)
    PLAN_TYPE_CHOICES = [
        ('pending', 'Aguardando Aprovação'),
        ('free', 'Gratuito'),
        ('basic', 'Básico'),
        ('premium', 'Premium'),
        ('custom', 'Personalizado'),
    ]
    
    # Identificação
    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPE_CHOICES,
        unique=True,
        verbose_name='Tipo de Plano'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Nome do Plano',
        help_text='Ex: Plano Gratuito, Plano Básico'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descrição'
    )
    
    # Quotas de Conteúdo
    quota_pautas_dia = models.PositiveIntegerField(
        default=3,
        verbose_name='Pautas por Dia',
        help_text='Limite de pautas que podem ser criadas por dia'
    )
    quota_posts_dia = models.PositiveIntegerField(
        default=3,
        verbose_name='Posts por Dia',
        help_text='Limite de posts que podem ser criados por dia'
    )
    quota_posts_mes = models.PositiveIntegerField(
        default=15,
        verbose_name='Posts por Mês',
        help_text='Limite de posts que podem ser criados por mês'
    )
    
    # Quotas de Vídeos Avatar
    quota_videos_dia = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Vídeos Avatar por Dia',
        help_text='Limite de vídeos avatar por dia (0 = desabilitado)'
    )
    quota_videos_mes = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Vídeos Avatar por Mês',
        help_text='Limite de vídeos avatar por mês (0 = desabilitado)'
    )
    videos_avatar_enabled = models.BooleanField(
        default=False,
        verbose_name='Vídeos Avatar Habilitados',
        help_text='Se marcado, permite criação de vídeos avatar'
    )
    
    # Configurações
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Plano disponível para uso'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Padrão',
        help_text='Plano aplicado por padrão em novas aprovações'
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ordem de Exibição',
        help_text='Ordem de exibição no admin (menor = primeiro)'
    )
    
    class Meta:
        verbose_name = 'Template de Plano'
        verbose_name_plural = 'Templates de Planos'
        ordering = ['display_order', 'plan_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"
    
    def apply_to_organization(self, organization):
        """
        Aplica este template a uma organização.
        Retorna a organização (não salva automaticamente).
        """
        organization.plan_type = self.plan_type
        organization.quota_pautas_dia = self.quota_pautas_dia
        organization.quota_posts_dia = self.quota_posts_dia
        organization.quota_posts_mes = self.quota_posts_mes
        organization.quota_videos_dia = self.quota_videos_dia
        organization.quota_videos_mes = self.quota_videos_mes
        organization.videos_avatar_enabled = self.videos_avatar_enabled
        return organization
    
    def get_quota_summary(self):
        """Retorna resumo das quotas em formato legível"""
        return f"Pautas: {self.quota_pautas_dia}/dia | Posts: {self.quota_posts_dia}/dia, {self.quota_posts_mes}/mês"
    
    @property
    def has_pautas_module(self):
        """Verifica se empresa tem módulo de pautas contratado"""
        return self.pautas_enabled
    
    @property
    def has_posts_module(self):
        """Verifica se empresa tem módulo de posts contratado"""
        return self.posts_enabled
    
    @property
    def has_trends_module(self):
        """Verifica se empresa tem módulo de trends contratado"""
        return self.trends_enabled
    
    @property
    def has_videos_avatar_module(self):
        """Verifica se empresa tem módulo de vídeos avatar contratado"""
        return self.videos_avatar_enabled
    
    @property
    def has_email_marketing_module(self):
        """Verifica se empresa tem módulo de email marketing contratado"""
        return self.email_marketing_enabled
    
    def get_enabled_modules(self):
        """Retorna lista de módulos habilitados"""
        modules = []
        if self.pautas_enabled:
            modules.append('pautas')
        if self.posts_enabled:
            modules.append('posts')
        if self.trends_enabled:
            modules.append('trends')
        if self.videos_avatar_enabled:
            modules.append('videos_avatar')
        if self.email_marketing_enabled:
            modules.append('email_marketing')
        return modules


class Organization(TimeStampedModel):
    """
    Organização/Empresa no sistema multi-tenant.
    Cada organização tem seus próprios usuários, áreas, base de conhecimento e conteúdos.
    """
    class PlanType(models.TextChoices):
        PENDING = 'pending', 'Aguardando Aprovação'
        FREE = 'free', 'Gratuito'
        BASIC = 'basic', 'Básico'
        PREMIUM = 'premium', 'Premium'
        CUSTOM = 'custom', 'Personalizado'
    
    name = models.CharField(max_length=160, verbose_name='Nome')
    slug = models.SlugField(max_length=160, unique=True, verbose_name='Slug')
    tagline = models.CharField(max_length=255, blank=True, verbose_name='Tagline')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='organizations',
        verbose_name='Proprietário'
    )
    
    # Plano e Status
    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
        default=PlanType.FREE,
        help_text="Plano atual da organização",
        verbose_name='Tipo de Plano'
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Organização aprovada e ativa. False = aguardando aprovação ou suspensa",
        verbose_name='Ativa'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Aprovada em')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='organizations_approved',
        verbose_name='Aprovada por'
    )
    
    # Motivo de Inativação/Suspensão
    class SuspensionReason(models.TextChoices):
        ACTIVE = '', '(Nenhum - Organização Ativa)'
        PENDING = 'pending', 'Aguardando Aprovação'
        PAYMENT = 'payment', 'Pagamento Atrasado'
        TERMS = 'terms', 'Violação de Termos'
        CANCELED = 'canceled', 'Cancelada pelo Cliente'
        OTHER = 'other', 'Outro Motivo'
    
    suspension_reason = models.CharField(
        max_length=20,
        choices=SuspensionReason.choices,
        default=SuspensionReason.PENDING,
        blank=True,
        help_text="Motivo da suspensão/inativação (vazio = ativa)",
        verbose_name='Motivo de Suspensão'
    )
    
    # Quotas (editáveis pelo admin)
    quota_pautas_dia = models.PositiveIntegerField(
        default=3,
        help_text="Limite de pautas por dia (0 = bloqueado)",
        verbose_name='Quota Pautas/Dia'
    )
    quota_posts_dia = models.PositiveIntegerField(
        default=3,
        help_text="Limite de posts por dia (0 = bloqueado)",
        verbose_name='Quota Posts/Dia'
    )
    quota_posts_mes = models.PositiveIntegerField(
        default=15,
        help_text="Limite de posts por mês (0 = ilimitado)",
        verbose_name='Quota Posts/Mês'
    )
    
    # Quotas para Vídeos Avatar
    quota_videos_dia = models.PositiveSmallIntegerField(
        default=2,
        help_text="Máximo de vídeos avatar por dia",
        verbose_name='Quota Vídeos/Dia'
    )
    quota_videos_mes = models.PositiveSmallIntegerField(
        default=5,
        help_text="Máximo de vídeos avatar por mês (ciclo de billing)",
        verbose_name='Quota Vídeos/Mês'
    )
    videos_avatar_enabled = models.BooleanField(
        default=False,
        help_text="Empresa autorizada a criar vídeos avatar",
        verbose_name='Vídeos Avatar Habilitados'
    )
    
    # Módulos/Ferramentas Contratadas
    pautas_enabled = models.BooleanField(
        default=True,  # Habilitado por padrão
        help_text="Empresa autorizada a usar módulo de pautas",
        verbose_name='Pautas Habilitadas'
    )
    
    posts_enabled = models.BooleanField(
        default=True,  # Habilitado por padrão
        help_text="Empresa autorizada a usar módulo de posts",
        verbose_name='Posts Habilitados'
    )
    
    trends_enabled = models.BooleanField(
        default=False,  # Desabilitado por padrão
        help_text="Empresa autorizada a usar módulo de trends",
        verbose_name='Trends Habilitados'
    )
    
    videos_avatar_enabled = models.BooleanField(
        default=False,  # Desabilitado por padrão
        help_text="Empresa autorizada a criar vídeos avatar",
        verbose_name='Vídeos Avatar Habilitados'
    )
    
    email_marketing_enabled = models.BooleanField(
        default=False,  # Desabilitado por padrão
        help_text="Empresa autorizada a usar módulo de email marketing",
        verbose_name='Email Marketing Habilitado'
    )
    
    # Ciclo de Faturamento (Billing Cycle)
    billing_cycle_day = models.PositiveSmallIntegerField(
        default=1,
        help_text="Dia do mês que reseta a quota mensal (1-31). Ex: 15 = todo dia 15",
        verbose_name='Dia do Ciclo de Faturamento'
    )
    
    # Notas Internas
    internal_notes = models.TextField(
        blank=True,
        help_text="Notas internas da equipe (não visível para cliente)",
        verbose_name='Notas Internas'
    )
    
    # Sistema de Alertas (migrado de UsageLimit)
    alert_80_enabled = models.BooleanField(
        default=True,
        help_text="Enviar alerta quando atingir 80% da quota",
        verbose_name='Alertas 80% Habilitados'
    )
    alert_100_enabled = models.BooleanField(
        default=True,
        help_text="Enviar alerta quando atingir 100% da quota",
        verbose_name='Alertas 100% Habilitados'
    )
    alert_email = models.EmailField(
        blank=True,
        help_text="Email para receber alertas (deixe vazio para usar email do owner)",
        verbose_name='Email de Alertas'
    )
    
    class Meta:
        verbose_name = 'Organização'
        verbose_name_plural = 'Organizações'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def _generate_unique_slug(self):
        """Gera slug único baseado no nome"""
        base = slugify(self.name) or "organizacao"
        slug_candidate = base
        index = 1
        queryset = type(self).objects.exclude(pk=self.pk)
        while queryset.filter(slug=slug_candidate).exists():
            slug_candidate = f"{base}-{index}"
            index += 1
        return slug_candidate
    
    def save(self, *args, **kwargs):
        # Gerar slug único se necessário
        if not self.slug or type(self).objects.exclude(pk=self.pk).filter(slug=self.slug).exists():
            self.slug = self._generate_unique_slug()
        
        # Setar billing_cycle_day e suspension_reason quando aprovar
        if self.approved_at and self.pk:
            try:
                old_instance = Organization.objects.get(pk=self.pk)
                if not old_instance.approved_at and self.approved_at:
                    approval_day = self.approved_at.day
                    self.billing_cycle_day = min(approval_day, 28)
                    if self.is_active:
                        self.suspension_reason = ''
            except Organization.DoesNotExist:
                pass
        
        # Lógica bidirecional: is_active <-> suspension_reason
        old_is_active = None
        old_suspension_reason = None
        if self.pk:
            try:
                old_instance = Organization.objects.get(pk=self.pk)
                old_is_active = old_instance.is_active
                old_suspension_reason = old_instance.suspension_reason
            except Organization.DoesNotExist:
                pass
        
        # Se admin mudou para is_active=True → limpar motivo
        if self.is_active and (old_is_active is None or old_is_active != self.is_active):
            self.suspension_reason = ''
        
        # Se admin escolheu um motivo → forçar inativa
        elif self.suspension_reason and self.suspension_reason != '' and \
             (old_suspension_reason is None or old_suspension_reason != self.suspension_reason):
            self.is_active = False
        
        # Se está ativa → garantir sem motivo
        elif self.is_active:
            self.suspension_reason = ''
        
        # Se está inativa mas sem motivo → definir padrão
        elif not self.is_active and (not self.suspension_reason or self.suspension_reason == ''):
            if not self.approved_at:
                self.suspension_reason = 'pending'
            else:
                self.suspension_reason = 'other'
        
        super().save(*args, **kwargs)
    
    def get_quota_usage_today(self):
        """Retorna uso de quotas de hoje (com cache por 1 minuto)"""
        from django.core.cache import cache
        
        cache_key = f'quota_usage_{self.id}_{timezone.now().date()}'
        usage = cache.get(cache_key)
        
        if usage is None:
            try:
                usage_obj = QuotaUsageDaily.objects.get(
                    organization=self,
                    date=timezone.now().date()
                )
                usage = {
                    'pautas_used': usage_obj.pautas_used,
                    'posts_used': usage_obj.posts_used,
                }
            except QuotaUsageDaily.DoesNotExist:
                usage = {'pautas_used': 0, 'posts_used': 0}
            
            cache.set(cache_key, usage, 60)  # Cache por 1 minuto
        
        return usage
    
    def get_billing_cycle_start(self):
        """
        Retorna a data de início do ciclo mensal atual baseado em billing_cycle_day.
        
        Exemplo: Se billing_cycle_day = 15
        - Hoje é 20/out: ciclo começou em 15/out
        - Hoje é 10/out: ciclo começou em 15/set
        """
        from datetime import timedelta
        
        now = timezone.now()
        current_day = now.day
        cycle_day = min(self.billing_cycle_day, 28)  # Máximo dia 28 para evitar problemas com fevereiro
        
        # Se hoje >= dia do ciclo, ciclo começou neste mês
        if current_day >= cycle_day:
            cycle_start = now.replace(day=cycle_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_prev_month = first_of_month - timedelta(days=1)
            
            try:
                cycle_start = last_day_prev_month.replace(day=cycle_day, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                cycle_start = last_day_prev_month.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return cycle_start
    
    def get_billing_cycle_end(self):
        """Retorna a data de fim (próximo reset) do ciclo mensal atual"""
        now = timezone.now()
        cycle_day = min(self.billing_cycle_day, 28)
        
        if now.day < cycle_day:
            try:
                next_reset = now.replace(day=cycle_day, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                last_day = monthrange(now.year, now.month)[1]
                next_reset = now.replace(day=last_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            try:
                next_reset = next_month.replace(day=cycle_day)
            except ValueError:
                last_day = monthrange(next_month.year, next_month.month)[1]
                next_reset = next_month.replace(day=last_day)
        
        return next_reset
    
    def get_posts_this_month(self):
        """Conta posts criados no ciclo mensal atual"""
        from django.db.models import Sum
        
        cycle_start = self.get_billing_cycle_start()
        
        total = QuotaUsageDaily.objects.filter(
            organization=self,
            date__gte=cycle_start.date()
        ).aggregate(total=Sum('posts_created'))['total'] or 0
        
        adjustments = QuotaAdjustment.objects.filter(
            organization=self,
            resource_type='post_monthly',
            created_at__gte=cycle_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return max(0, total + adjustments)
    
    @property
    def has_pautas_module(self):
        """Verifica se empresa tem módulo de pautas contratado"""
        return self.pautas_enabled
    
    @property
    def has_posts_module(self):
        """Verifica se empresa tem módulo de posts contratado"""
        return self.posts_enabled
    
    @property
    def has_trends_module(self):
        """Verifica se empresa tem módulo de trends contratado"""
        return self.trends_enabled
    
    @property
    def has_videos_avatar_module(self):
        """Verifica se empresa tem módulo de vídeos avatar contratado"""
        return self.videos_avatar_enabled
    
    @property
    def has_email_marketing_module(self):
        """Verifica se empresa tem módulo de email marketing contratado"""
        return self.email_marketing_enabled
    
    def get_enabled_modules(self):
        """Retorna lista de módulos habilitados"""
        modules = []
        if self.pautas_enabled:
            modules.append('pautas')
        if self.posts_enabled:
            modules.append('posts')
        if self.trends_enabled:
            modules.append('trends')
        if self.videos_avatar_enabled:
            modules.append('videos_avatar')
        if self.email_marketing_enabled:
            modules.append('email_marketing')
        return modules
    
    def can_create_pauta(self):
        """Verifica se pode criar pauta. Retorna: (bool, str|None, str|None)"""
        if not self.is_active:
            if self.approved_at:
                return False, 'suspended', f'Essa empresa está suspensa no momento. Para mais detalhes entre em contato com o nosso suporte {settings.NOTIFICATION_EMAIL_SUPORTE}'
            else:
                return False, 'pending', 'Organização aguardando aprovação'
        
        if self.quota_pautas_dia == 0:
            return False, 'no_quota', 'Sem quota de pautas disponível'
        
        usage = self.get_quota_usage_today()
        if usage['pautas_used'] >= self.quota_pautas_dia:
            return False, 'daily_limit', f'Limite diário de pautas atingido ({self.quota_pautas_dia}/{self.quota_pautas_dia})'
        
        return True, None, None
    
    def can_create_post(self):
        """Verifica se pode criar post (valida dia E mês). Retorna: (bool, str|None, str|None)"""
        if not self.is_active:
            if self.approved_at:
                return False, 'suspended', f'Essa empresa está suspensa no momento. Para mais detalhes entre em contato com o nosso suporte {settings.NOTIFICATION_EMAIL_SUPORTE}'
            else:
                return False, 'pending', 'Organização aguardando aprovação'
        
        if self.quota_posts_dia == 0:
            return False, 'no_quota', 'Sem quota de posts disponível'
        
        usage = self.get_quota_usage_today()
        if usage['posts_used'] >= self.quota_posts_dia:
            return False, 'daily_limit', f'Limite diário de posts atingido ({self.quota_posts_dia}/{self.quota_posts_dia})'
        
        if self.quota_posts_mes > 0:
            posts_month = self.get_posts_this_month()
            if posts_month >= self.quota_posts_mes:
                return False, 'monthly_limit', f'Limite mensal de posts atingido ({self.quota_posts_mes}/{self.quota_posts_mes})'
        
        return True, None, None
    
    def can_create_video_avatar(self):
        """Valida se pode criar vídeo avatar. Retorna: (bool, str|None, str|None)"""
        if not self.videos_avatar_enabled:
            return False, 'not_authorized', 'Sua empresa não está autorizada a criar vídeos avatar. Entre em contato conosco.'
        
        if not self.is_active:
            if not self.approved_at:
                return False, 'pending', 'Organização aguardando aprovação'
        
        usage_today = self.get_video_quota_usage_today()
        if usage_today['videos_used'] >= self.quota_videos_dia:
            return False, 'daily_limit', f'Limite diário atingido ({self.quota_videos_dia} vídeos/dia).'
        
        videos_month = self.get_videos_this_month()
        if videos_month >= self.quota_videos_mes:
            return False, 'monthly_limit', f'Limite mensal atingido ({self.quota_videos_mes} vídeos/mês).'
        
        return True, None, None
    
    def get_video_quota_usage_today(self):
        """Retorna uso de quota de vídeos hoje"""
        today = timezone.now().date()
        usage = QuotaUsageDaily.objects.filter(
            organization=self,
            date=today
        ).first()
        
        if not usage:
            return {'videos_used': 0}
        
        return {'videos_used': usage.videos_created or 0}
    
    def get_videos_this_month(self):
        """Conta vídeos criados neste ciclo de billing"""
        from apps.content.models import VideoAvatar
        start_date = self.get_billing_cycle_start()
        return VideoAvatar.objects.filter(
            organization=self,
            created_at__gte=start_date
        ).count()


class QuotaUsageDaily(TimeStampedModel):
    """Cache de uso diário de quotas (evita COUNT toda vez)"""
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='quota_usage_daily',
        verbose_name='Organização'
    )
    date = models.DateField(db_index=True, verbose_name='Data')
    
    # Contadores (atualizados em tempo real)
    pautas_requested = models.PositiveIntegerField(
        default=0,
        help_text="Pautas solicitadas hoje",
        verbose_name='Pautas Solicitadas'
    )
    posts_created = models.PositiveIntegerField(
        default=0,
        help_text="Posts criados hoje",
        verbose_name='Posts Criados'
    )
    videos_created = models.PositiveIntegerField(
        default=0,
        help_text="Vídeos avatar criados hoje",
        verbose_name='Vídeos Criados'
    )
    
    # Ajustes manuais aplicados neste dia
    pautas_adjustments = models.IntegerField(
        default=0,
        help_text="Ajustes de pautas (+/-)",
        verbose_name='Ajustes de Pautas'
    )
    posts_adjustments = models.IntegerField(
        default=0,
        help_text="Ajustes de posts (+/-)",
        verbose_name='Ajustes de Posts'
    )
    videos_adjustments = models.IntegerField(
        default=0,
        help_text="Ajustes de vídeos (+/-)",
        verbose_name='Ajustes de Vídeos'
    )
    
    # Tracking de custos (migrado de UsageLimit)
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0.0000'))],
        verbose_name='Custo USD',
        help_text='Custo total em USD das operações deste dia'
    )
    
    class Meta:
        unique_together = [('organization', 'date')]
        ordering = ['-date']
        verbose_name = 'Uso Diário de Quota'
        verbose_name_plural = 'Uso Diário de Quotas'
        indexes = [
            models.Index(fields=['organization', '-date']),
        ]
    
    @property
    def pautas_used(self):
        """Total usado (requests + ajustes)"""
        return max(0, self.pautas_requested + self.pautas_adjustments)
    
    @property
    def posts_used(self):
        """Total usado (created + ajustes)"""
        return max(0, self.posts_created + self.posts_adjustments)
    
    def __str__(self):
        return f"{self.organization.name} · {self.date} · Pautas:{self.pautas_used} Posts:{self.posts_used}"


class QuotaAdjustment(TimeStampedModel):
    """Log de ajustes manuais de quota (devoluções, bônus, correções)"""
    
    class AdjustmentType(models.TextChoices):
        REFUND = 'refund', 'Devolução (Erro/Falha)'
        BONUS = 'bonus', 'Bônus (Promocional)'
        CORRECTION = 'correction', 'Correção Manual'
        PLAN_CHANGE = 'plan_change', 'Mudança de Plano'
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='quota_adjustments',
        verbose_name='Organização'
    )
    
    # Tipo de recurso ajustado
    resource_type = models.CharField(
        max_length=20,
        choices=[
            ('pauta_daily', 'Pauta (Diária)'),
            ('post_daily', 'Post (Diária)'),
            ('post_monthly', 'Post (Mensal)'),
        ],
        help_text="Tipo de quota ajustada",
        verbose_name='Tipo de Recurso'
    )
    
    # Ajuste
    adjustment_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
        help_text="Motivo do ajuste",
        verbose_name='Tipo de Ajuste'
    )
    amount = models.IntegerField(
        help_text="Quantidade ajustada (positivo=adicionar, negativo=remover)",
        verbose_name='Quantidade'
    )
    
    # Referência (se for devolução por falha)
    pauta_audit_log = models.ForeignKey(
        'PautaAuditLog',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quota_adjustments',
        help_text="Referência ao audit log da pauta (se aplicável)",
        verbose_name='Log de Auditoria da Pauta'
    )
    post = models.ForeignKey(
        'posts.Post',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quota_adjustments',
        help_text="Referência ao post (se aplicável)",
        verbose_name='Post'
    )
    
    # Auditoria
    reason = models.TextField(
        help_text="Motivo detalhado do ajuste",
        verbose_name='Motivo'
    )
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='quota_adjustments_made',
        help_text="Usuário que fez o ajuste",
        verbose_name='Ajustado por'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ajuste de Quota'
        verbose_name_plural = 'Ajustes de Quotas'
    
    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.organization.name} · {self.get_resource_type_display()} · {sign}{self.amount}"


class QuotaAlert(TimeStampedModel):
    """
    Registro de alertas de quota enviados (migrado de UsageLimit.alert_80_sent/alert_100_sent).
    Evita envio duplicado de alertas no mesmo dia.
    """
    
    class AlertType(models.TextChoices):
        ALERT_80 = '80', '80% da Quota'
        ALERT_100 = '100', '100% da Quota (Limite Atingido)'
    
    class ResourceType(models.TextChoices):
        PAUTA_DAILY = 'pauta_daily', 'Pauta (Diária)'
        POST_DAILY = 'post_daily', 'Post (Diária)'
        POST_MONTHLY = 'post_monthly', 'Post (Mensal)'
        VIDEO_DAILY = 'video_daily', 'Vídeo (Diária)'
        VIDEO_MONTHLY = 'video_monthly', 'Vídeo (Mensal)'
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='quota_alerts',
        verbose_name='Organização'
    )
    alert_type = models.CharField(
        max_length=3,
        choices=AlertType.choices,
        verbose_name='Tipo de Alerta'
    )
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        verbose_name='Tipo de Recurso'
    )
    date = models.DateField(
        db_index=True,
        help_text="Data em que o alerta foi disparado",
        verbose_name='Data'
    )
    sent_to = models.EmailField(
        help_text="Email para onde o alerta foi enviado",
        verbose_name='Enviado Para'
    )
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Alerta de Quota'
        verbose_name_plural = 'Alertas de Quotas'
        unique_together = [['organization', 'alert_type', 'resource_type', 'date']]
        indexes = [
            models.Index(fields=['organization', '-date']),
            models.Index(fields=['alert_type', '-date']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} · {self.get_alert_type_display()} · {self.get_resource_type_display()} · {self.date}"


class PautaAuditLog(TimeStampedModel):
    """Log de auditoria para ações em Pautas"""
    class Action(models.TextChoices):
        REQUESTED = 'requested', 'Solicitado'
        WEBHOOK_SENT = 'webhook_sent', 'Webhook Enviado'
        WEBHOOK_FAILED = 'webhook_failed', 'Webhook Falhou'
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        DELETED = 'deleted', 'Deleted'

    pauta = models.ForeignKey(
        'content.Pauta',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
        verbose_name='Pauta'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='pauta_audit_logs',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
    action = models.CharField(max_length=40, choices=Action.choices, verbose_name='Ação')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Usuário'
    )
    meta = models.JSONField(default=dict, blank=True, verbose_name='Metadados')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de Auditoria de Pauta'
        verbose_name_plural = 'Logs de Auditoria de Pautas'
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]

    def __str__(self):
        user_email = self.user.email if self.user else 'Sistema'
        if self.pauta:
            return f"{self.get_action_display()} · Pauta {self.pauta_id} · {user_email}"
        elif self.organization:
            return f"{self.get_action_display()} · {self.organization.name} · {user_email}"
        return f"{self.get_action_display()} · {user_email}"
