"""
Signals para auto-incremento de QuotaUsageDaily

Incrementa contadores diários quando Pauta/Post/VideoAvatar são criados.
Segue padrão estabelecido na aplicação anterior.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import logging

from apps.content.models import Pauta, Post, VideoAvatar
from apps.core.models import QuotaUsageDaily

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Pauta)
def increment_pauta_quota(sender, instance, created, **kwargs):
    """
    Incrementa quota de pautas ao criar nova Pauta.
    
    Referência: core/views.py linhas 1725-1753 (aplicação anterior)
    """
    if not created:
        return
    
    if not instance.organization:
        logger.warning(f'[PAUTA] Pauta #{instance.id} criada sem organization - quota não incrementada')
        return
    
    try:
        # Get or create do registro do dia
        usage, created_usage = QuotaUsageDaily.objects.get_or_create(
            organization=instance.organization,
            date=timezone.now().date(),
            defaults={
                'pautas_requested': 0,
                'posts_created': 0,
                'videos_created': 0,
                'cost_usd': Decimal('0.0000')
            }
        )
        
        # Incrementar contador
        usage.pautas_requested += 1
        usage.save(update_fields=['pautas_requested', 'updated_at'])
        
        logger.info(
            f'[PAUTA] Quota atualizada: {usage.pautas_used}/{instance.organization.quota_pautas_dia} '
            f'(Pauta #{instance.id}, Org: {instance.organization.name})'
        )
        
        # Limpar cache de quota
        cache_key = f'quota_usage_{instance.organization.id}_{timezone.now().date()}'
        cache.delete(cache_key)
        
    except Exception as e:
        logger.error(f'[PAUTA] Erro ao incrementar quota para Pauta #{instance.id}: {e}')


@receiver(post_save, sender=Post)
def increment_post_quota(sender, instance, created, **kwargs):
    """
    Incrementa quota de posts ao criar novo Post.
    
    Referência: core/views.py linhas 1036-1077 (aplicação anterior)
    """
    if not created:
        return
    
    if not instance.organization:
        logger.warning(f'[POST] Post #{instance.id} criado sem organization - quota não incrementada')
        return
    
    try:
        # Get or create do registro do dia
        usage, created_usage = QuotaUsageDaily.objects.get_or_create(
            organization=instance.organization,
            date=timezone.now().date(),
            defaults={
                'pautas_requested': 0,
                'posts_created': 0,
                'videos_created': 0,
                'cost_usd': Decimal('0.0000')
            }
        )
        
        # Incrementar contador
        usage.posts_created += 1
        usage.save(update_fields=['posts_created', 'updated_at'])
        
        posts_month = instance.organization.get_posts_this_month()
        logger.info(
            f'[POST] Quota atualizada: {usage.posts_used}/{instance.organization.quota_posts_dia} '
            f'(mês: {posts_month}/{instance.organization.quota_posts_mes}) '
            f'(Post #{instance.id}, Org: {instance.organization.name})'
        )
        
        # Limpar cache de quota
        cache_key = f'quota_usage_{instance.organization.id}_{timezone.now().date()}'
        cache.delete(cache_key)
        
    except Exception as e:
        logger.error(f'[POST] Erro ao incrementar quota para Post #{instance.id}: {e}')


@receiver(post_save, sender=VideoAvatar)
def increment_video_quota(sender, instance, created, **kwargs):
    """
    Incrementa quota de vídeos ao criar novo VideoAvatar.
    
    Referência: core/views.py linhas 1234-1252 (aplicação anterior)
    """
    if not created:
        return
    
    if not instance.organization:
        logger.warning(f'[VIDEO] VideoAvatar #{instance.id} criado sem organization - quota não incrementada')
        return
    
    try:
        # Get or create do registro do dia
        usage, created_usage = QuotaUsageDaily.objects.get_or_create(
            organization=instance.organization,
            date=timezone.now().date(),
            defaults={
                'pautas_requested': 0,
                'posts_created': 0,
                'videos_created': 0,
                'cost_usd': Decimal('0.0000')
            }
        )
        
        # Incrementar contador
        usage.videos_created += 1
        usage.save(update_fields=['videos_created', 'updated_at'])
        
        logger.info(
            f'[VIDEO] Quota atualizada: vídeos={usage.videos_created} '
            f'(VideoAvatar #{instance.id}, Org: {instance.organization.name})'
        )
        
        # Limpar cache de quota (se implementado para vídeos)
        cache_key = f'quota_usage_{instance.organization.id}_{timezone.now().date()}'
        cache.delete(cache_key)
        
    except Exception as e:
        logger.error(f'[VIDEO] Erro ao incrementar quota para VideoAvatar #{instance.id}: {e}')
