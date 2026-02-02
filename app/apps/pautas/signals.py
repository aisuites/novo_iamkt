from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Pauta


@receiver(pre_save, sender=Pauta)
def pauta_pre_save(sender, instance, **kwargs):
    """Signal para registrar edição antes de salvar"""
    if instance.id:  # Se não é uma nova instância
        try:
            old_instance = Pauta.objects.get(id=instance.id)
            
            # Verifica se houve alteração nos campos principais
            if (old_instance.title != instance.title or 
                old_instance.content != instance.content):
                
                # Atualiza campos de edição
                instance.last_edited_at = timezone.now()
                
                # Adiciona entrada de edição no audit_history
                if hasattr(instance, '_edited_by_user'):
                    entry = {
                        'action': 'edited',
                        'user_id': instance._edited_by_user.id,
                        'user_email': instance._edited_by_user.email,
                        'timestamp': instance.last_edited_at.isoformat(),
                        'details': {
                            'fields_changed': []
                        }
                    }
                    
                    if old_instance.title != instance.title:
                        entry['details']['fields_changed'].append('title')
                    if old_instance.content != instance.content:
                        entry['details']['fields_changed'].append('content')
                    
                    instance.audit_history.append(entry)
                    
        except Pauta.DoesNotExist:
            pass  # Nova instância, não faz nada
