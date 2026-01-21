from django.db import models
from apps.core.models import User, Area
from apps.content.models import Post


class Project(models.Model):
    """
    Projetos/Campanhas para organizar conteúdos
    """
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,
        blank=True,
        verbose_name='Organização'
    )
    name = models.CharField(max_length=200, verbose_name='Nome')
    description = models.TextField(blank=True, verbose_name='Descrição')
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='projects',
        verbose_name='Área'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        verbose_name='Responsável'
    )
    
    # Datas
    start_date = models.DateField(null=True, blank=True, verbose_name='Data de Início')
    end_date = models.DateField(null=True, blank=True, verbose_name='Data de Término')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('planning', 'Planejamento'),
            ('active', 'Ativo'),
            ('paused', 'Pausado'),
            ('completed', 'Concluído'),
            ('cancelled', 'Cancelado'),
        ],
        default='planning',
        verbose_name='Status'
    )
    
    # Metadados
    tags = models.JSONField(default=list, blank=True, verbose_name='Tags')
    budget_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Orçamento (USD)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['area', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_content_count(self):
        """Retorna quantidade de conteúdos no projeto"""
        return self.contents.count()
    
    def get_approved_count(self):
        """Retorna quantidade de conteúdos aprovados"""
        return self.contents.filter(status='approved').count()


class Approval(models.Model):
    """
    Workflow de aprovação de conteúdo
    """
    content = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='Conteúdo'
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approvals',
        verbose_name='Projeto'
    )
    
    # Tipo de aprovação
    approval_type = models.CharField(
        max_length=20,
        choices=[
            ('self', 'Auto-aprovação'),
            ('manager', 'Aprovação Gestor'),
        ],
        verbose_name='Tipo de Aprovação'
    )
    
    # Solicitante e aprovador
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='approval_requests',
        verbose_name='Solicitado por'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approvals_given',
        verbose_name='Aprovador'
    )
    
    # Decisão
    decision = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente'),
            ('approved', 'Aprovado'),
            ('adjustments', 'Solicitar Ajustes'),
            ('rejected', 'Rejeitado'),
        ],
        default='pending',
        verbose_name='Decisão'
    )
    decision_notes = models.TextField(blank=True, verbose_name='Observações da Decisão')
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='Solicitado em')
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name='Decidido em')
    
    # Notificações
    notification_sent = models.BooleanField(default=False, verbose_name='Notificação Enviada')
    reminder_sent = models.BooleanField(default=False, verbose_name='Lembrete Enviado')
    
    class Meta:
        verbose_name = 'Aprovação'
        verbose_name_plural = 'Aprovações'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['-requested_at']),
            models.Index(fields=['approver', 'decision']),
            models.Index(fields=['decision']),
        ]
    
    def __str__(self):
        return f"Aprovação #{self.id} - {self.content} - {self.get_decision_display()}"
    
    def is_overdue(self):
        """Verifica se aprovação está atrasada (>48h)"""
        if self.decision != 'pending':
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > (self.requested_at + timedelta(hours=48))
    
    def get_duration_hours(self):
        """Retorna duração da aprovação em horas"""
        if not self.decided_at:
            return None
        delta = self.decided_at - self.requested_at
        return delta.total_seconds() / 3600


class ApprovalComment(models.Model):
    """
    Comentários no processo de aprovação
    Thread de discussão
    """
    approval = models.ForeignKey(
        Approval,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Aprovação'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='approval_comments',
        verbose_name='Usuário'
    )
    comment = models.TextField(verbose_name='Comentário')
    
    # Anexos (opcional)
    has_attachment = models.BooleanField(default=False, verbose_name='Tem Anexo')
    attachment_s3_key = models.CharField(max_length=500, blank=True, verbose_name='Chave S3 Anexo')
    attachment_s3_url = models.URLField(max_length=1000, blank=True, verbose_name='URL S3 Anexo')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Comentário de Aprovação'
        verbose_name_plural = 'Comentários de Aprovação'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['approval', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comentário de {self.user} em {self.created_at}"


# Relacionamento Many-to-Many entre Project e Post
class ProjectContent(models.Model):
    """
    Relacionamento entre projetos e posts
    Permite que um conteúdo esteja em múltiplos projetos
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='project_contents',
        verbose_name='Projeto'
    )
    content = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='content_projects',
        verbose_name='Conteúdo'
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Adicionado por'
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Adicionado em')
    
    class Meta:
        verbose_name = 'Conteúdo do Projeto'
        verbose_name_plural = 'Conteúdos dos Projetos'
        unique_together = [['project', 'content']]
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.project} - {self.content}"
