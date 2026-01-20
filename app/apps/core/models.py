from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


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
    Áreas organizacionais (Marketing, RH, Diretoria, etc)
    Base para permissões e limites de uso
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


class UsageLimit(models.Model):
    """
    Limites de uso mensal por área
    Controla quantidade de gerações e custos
    """
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='usage_limits',
        verbose_name='Área'
    )
    month = models.DateField(verbose_name='Mês (primeiro dia)')
    
    # Limites configurados
    max_generations = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Máximo de Gerações'
    )
    max_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Custo Máximo (USD)'
    )
    
    # Uso atual
    current_generations = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Gerações Atuais'
    )
    current_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0.0000'))],
        verbose_name='Custo Atual (USD)'
    )
    
    # Alertas
    alert_80_sent = models.BooleanField(default=False, verbose_name='Alerta 80% Enviado')
    alert_100_sent = models.BooleanField(default=False, verbose_name='Alerta 100% Enviado')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Limite de Uso'
        verbose_name_plural = 'Limites de Uso'
        unique_together = [['area', 'month']]
        ordering = ['-month', 'area']
    
    def __str__(self):
        return f"{self.area.name} - {self.month.strftime('%m/%Y')}"
    
    def get_generation_percentage(self):
        """Retorna percentual de uso de gerações"""
        if self.max_generations == 0:
            return 0
        return (self.current_generations / self.max_generations) * 100
    
    def get_cost_percentage(self):
        """Retorna percentual de uso de custo"""
        if self.max_cost_usd == 0:
            return 0
        return float((self.current_cost_usd / self.max_cost_usd) * 100)
    
    def is_blocked(self):
        """Verifica se a área está bloqueada por limite"""
        return (
            self.current_generations >= self.max_generations or
            self.current_cost_usd >= self.max_cost_usd
        )
    
    def should_send_alert_80(self):
        """Verifica se deve enviar alerta de 80%"""
        if self.alert_80_sent:
            return False
        return (
            self.get_generation_percentage() >= 80 or
            self.get_cost_percentage() >= 80
        )
    
    def should_send_alert_100(self):
        """Verifica se deve enviar alerta de 100%"""
        if self.alert_100_sent:
            return False
        return self.is_blocked()


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
