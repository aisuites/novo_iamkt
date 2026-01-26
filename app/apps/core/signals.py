"""
Sistema de Signals para Organization
Detecta mudanças e envia emails automaticamente
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Organization
from .emails import (
    send_organization_approved_email,
    send_organization_suspended_email,
    send_organization_reactivated_email
)
import logging

logger = logging.getLogger(__name__)

# Cache para armazenar estado anterior (pre_save)
_org_state_cache = {}


@receiver(pre_save, sender=Organization)
def capture_organization_state(sender, instance, **kwargs):
    """
    Captura estado anterior da organização antes de salvar.
    Necessário para detectar mudanças em post_save.
    """
    if instance.pk:
        try:
            old_org = Organization.objects.get(pk=instance.pk)
            _org_state_cache[instance.pk] = {
                'is_active': old_org.is_active,
                'approved_at': old_org.approved_at,
                'suspension_reason': old_org.suspension_reason,
            }
        except Organization.DoesNotExist:
            pass


@receiver(post_save, sender=Organization)
def handle_organization_changes(sender, instance, created, **kwargs):
    """
    Detecta mudanças na organização e envia emails apropriados.
    
    EVENTOS:
    1. Aprovada: approved_at None → valor
    2. Suspensa: is_active True → False
    3. Reativada: is_active False → True (já aprovada)
    4. Mudança de motivo de suspensão: suspension_reason alterado (já inativa)
    """
    
    # Ignorar se acabou de ser criada (já envia email no cadastro)
    if created:
        return
    
    # Recuperar estado anterior
    old_state = _org_state_cache.get(instance.pk)
    if not old_state:
        return
    
    # EVENTO 1: Organização APROVADA
    # Detecta quando approved_at muda de None para algum valor
    if not old_state['approved_at'] and instance.approved_at:
        logger.info(f'[SIGNAL] Organização {instance.name} aprovada. Enviando email...')
        send_organization_approved_email(instance)
    
    # EVENTO 2: Organização SUSPENSA (primeira vez)
    # Detecta quando is_active muda de True para False
    elif old_state['is_active'] and not instance.is_active:
        logger.info(f'[SIGNAL] Organização {instance.name} suspensa ({instance.suspension_reason}). Enviando email...')
        send_organization_suspended_email(instance)
    
    # EVENTO 3: Organização REATIVADA
    # Detecta quando is_active muda de False para True (já aprovada)
    elif not old_state['is_active'] and instance.is_active and instance.approved_at:
        logger.info(f'[SIGNAL] Organização {instance.name} reativada. Enviando email...')
        send_organization_reactivated_email(instance)
    
    # EVENTO 4: Mudança de motivo de suspensão (já estava inativa)
    # Detecta quando suspension_reason muda (ex: payment → canceled)
    elif (not instance.is_active and 
          old_state['suspension_reason'] != instance.suspension_reason and
          instance.suspension_reason in ['payment', 'terms', 'canceled']):
        logger.info(f'[SIGNAL] Organização {instance.name} mudou motivo de suspensão: {old_state["suspension_reason"]} → {instance.suspension_reason}. Enviando email...')
        send_organization_suspended_email(instance)
    
    # Limpar cache
    if instance.pk in _org_state_cache:
        del _org_state_cache[instance.pk]
