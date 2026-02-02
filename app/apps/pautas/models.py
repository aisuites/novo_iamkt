import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import Organization

User = get_user_model()


class Pauta(models.Model):
    """Modelo para gerenciar pautas geradas por IA"""
    
    # Choices para redes sociais
    REDE_SOCIAL_CHOICES = [
        ('FACEBOOK', 'Facebook'),
        ('INSTAGRAM', 'Instagram'),
        ('LINKEDIN', 'LinkedIn'),
        ('TWITTER', 'Twitter'),
    ]
    
    # Status simplificado
    STATUS_CHOICES = [
        ('requested', 'Solicitado'),
        ('generated', 'Gerado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='pautas_ia'
    )
    knowledge_base = models.ForeignKey(
        'knowledge.KnowledgeBase',
        on_delete=models.CASCADE,
        related_name='pautas'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pautas_criadas'
    )
    
    # Dados principais
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Conteúdo")
    rede_social = models.CharField(
        max_length=20,
        choices=REDE_SOCIAL_CHOICES,
        default='FACEBOOK',
        verbose_name="Rede Social"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='requested',
        verbose_name="Status"
    )
    
    # Dados N8N
    n8n_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID N8N"
    )
    n8n_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Dados N8N"
    )
    generation_request = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Payload Enviado"
    )
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pautas_solicitadas',
        verbose_name="Solicitado por"
    )
    requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Solicitado em"
    )
    
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pautas_editadas',
        verbose_name="Editado por"
    )
    last_edited_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Editado em"
    )
    
    # Histórico completo
    audit_history = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Histórico de Auditoria"
    )
    
    class Meta:
        verbose_name = "Pauta"
        verbose_name_plural = "Pautas"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['status', 'rede_social']),
            models.Index(fields=['knowledge_base']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.rede_social}"
    
    def add_audit_entry(self, action, user, details=None):
        """Adiciona entrada no histórico de auditoria"""
        entry = {
            'action': action,
            'user_id': user.id if user else None,
            'user_email': user.email if user else None,
            'timestamp': self.updated_at.isoformat(),
            'details': details or {}
        }
        self.audit_history.append(entry)
        self.save(update_fields=['audit_history'])
    
    def save(self, *args, **kwargs):
        # Se é uma nova pauta, define requested_by e requested_at
        if not self.id and not self.requested_by:
            self.requested_by = self.user
            self.requested_at = self.created_at
            
            # Adiciona entrada de criação no audit_history
            self.audit_history = [{
                'action': 'created',
                'user_id': self.user.id,
                'user_email': self.user.email,
                'timestamp': self.created_at.isoformat(),
                'details': {
                    'title': self.title,
                    'rede_social': self.rede_social,
                    'n8n_id': self.n8n_id
                }
            }]
        
        super().save(*args, **kwargs)
