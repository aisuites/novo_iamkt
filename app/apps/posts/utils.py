"""
Funções auxiliares para posts (webhook, email, audit)
"""
import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from apps.core.emails import get_notification_emails
from apps.utils.s3 import get_signed_url

logger = logging.getLogger(__name__)


def _get_organization_logos(organization):
    """
    Retorna lista de logos da organização
    
    Args:
        organization: Instância de Organization
    
    Returns:
        list: [{'url': str, 'name': str}, ...] ordenado por is_primary e data
    """
    try:
        kb = organization.knowledge_bases.first()
        if not kb:
            return []
        
        logos = kb.logos.all().order_by('-is_primary', '-created_at')
        return [
            {
                'url': get_signed_url(logo.s3_key, expiration=86400),  # 24 horas
                'name': logo.name,
            }
            for logo in logos
            if get_signed_url(logo.s3_key, expiration=86400)  # Só inclui se conseguir gerar URL
        ]
    except Exception as e:
        logger.warning(f'Erro ao buscar logos da organização {organization.id}: {e}')
        return []


def _get_kb_reference_images(organization):
    """
    Retorna imagens de referência da base de conhecimento
    
    Args:
        organization: Instância de Organization
    
    Returns:
        list: [{'url': str, 'name': str}, ...] ordenado por data (mais recente primeiro)
    """
    try:
        kb = organization.knowledge_bases.first()
        if not kb:
            return []
        
        images = kb.reference_images.all().order_by('-created_at')
        return [
            {
                'url': get_signed_url(img.s3_key, expiration=86400),  # 24 horas
                'name': img.title,
            }
            for img in images
            if get_signed_url(img.s3_key, expiration=86400)  # Só inclui se conseguir gerar URL
        ]
    except Exception as e:
        logger.warning(f'Erro ao buscar imagens de referência da KB {organization.id}: {e}')
        return []


def _get_post_reference_images(post):
    """
    Retorna imagens anexadas ao post
    
    Args:
        post: Instância de Post
    
    Returns:
        list: [{'url': str, 'name': str}, ...]
    """
    try:
        if not post.reference_images:
            return []
        
        # reference_images é um JSONField com lista de objetos
        # Formato esperado: [{'url': '...', 's3_key': '...', 'name': '...', ...}, ...]
        result = []
        for idx, img in enumerate(post.reference_images):
            s3_key = img.get('s3_key') or img.get('key')
            if s3_key:
                signed_url = get_signed_url(s3_key, expiration=86400)  # 24 horas
                if signed_url:
                    result.append({
                        'url': signed_url,
                        'name': img.get('name', f'Imagem {idx + 1}'),
                    })
        return result
    except Exception as e:
        logger.warning(f'Erro ao buscar imagens de referência do post {post.id}: {e}')
        return []


def _get_marketing_summary(organization):
    """
    Retorna resumo de marketing da base de conhecimento
    
    Args:
        organization: Instância de Organization
    
    Returns:
        str ou None: Resumo de marketing compilado pelo N8N
    """
    try:
        kb = organization.knowledge_bases.first()
        if not kb or not kb.n8n_compilation:
            return None
        
        return kb.n8n_compilation.get('marketing_input_summary', '')
    except Exception as e:
        logger.warning(f'Erro ao buscar resumo de marketing da organização {organization.id}: {e}')
        return None


def _calculate_image_deadline(requested_at):
    """
    Calcula prazo de entrega da imagem (6 horas úteis)
    Horário comercial: 09:00-17:00
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    if isinstance(requested_at, str):
        requested_at = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))
    
    if timezone.is_naive(requested_at):
        requested_at = timezone.make_aware(requested_at)
    
    current = requested_at
    hours_remaining = 6
    
    while hours_remaining > 0:
        # Pular fim de semana
        while current.weekday() >= 5:  # 5=sábado, 6=domingo
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            current += timedelta(days=1)
        
        # Se antes das 9h, começar às 9h
        if current.hour < 9:
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Se depois das 17h, ir para próximo dia útil às 9h
        if current.hour >= 17:
            current += timedelta(days=1)
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        
        # Calcular horas disponíveis hoje
        hours_until_end = 17 - current.hour - (current.minute / 60.0)
        
        if hours_remaining <= hours_until_end:
            # Termina hoje
            current += timedelta(hours=hours_remaining)
            hours_remaining = 0
        else:
            # Vai para próximo dia
            hours_remaining -= hours_until_end
            current += timedelta(days=1)
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return current


def _notify_image_request_email(post, request=None):
    """
    Envia email de notificação de solicitação INICIAL de imagem
    """
    if not post.organization:
        logger.warning(f'Post {post.id} sem organização - email não enviado')
        return
    
    # Buscar emails do grupo 'gestao' (configurado via NOTIFICATION_EMAILS_GESTAO no .env)
    recipient_emails = get_notification_emails('gestao')
    
    # Se não houver emails configurados, NÃO envia
    if not recipient_emails:
        logger.info(f'Nenhum email configurado em NOTIFICATION_EMAILS_GESTAO - email não enviado')
        return
    
    # Calcular prazo de entrega (6 horas úteis)
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Buscar última solicitação de imagem
    last_request = post.change_requests.filter(
        change_type='image'
    ).order_by('-created_at').first()
    
    requested_at = last_request.created_at if last_request else post.created_at
    deadline = _calculate_image_deadline(requested_at)
    deadline_formatted = deadline.strftime('%d/%m/%y às %H:%M')
    
    subject = f'🎨 Nova solicitação de imagem - Post #{post.id}'
    
    context = {
        'post': post,
        'organization': post.organization,
        'post_url': f"{settings.SITE_URL}/admin/posts/post/{post.id}/change/" if hasattr(settings, 'SITE_URL') else '',
        'requested_at': requested_at,
        'deadline': deadline_formatted,
        # Novos dados para seções adicionais
        'logos': _get_organization_logos(post.organization),
        'kb_references': _get_kb_reference_images(post.organization),
        'post_references': _get_post_reference_images(post),
        'marketing_summary': _get_marketing_summary(post.organization),
    }
    
    try:
        html_message = render_to_string('emails/post_image_request.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_emails,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f'Email de solicitação de imagem enviado para {recipient_emails}')
    except Exception as e:
        logger.error(f'Erro ao enviar email de solicitação de imagem: {e}')
        raise


def _notify_revision_request(post, message, payload=None, user=None, request=None):
    """
    Envia email de notificação de solicitação de ALTERAÇÃO de imagem
    """
    if not post.organization:
        logger.warning(f'Post {post.id} sem organização - email não enviado')
        return
    
    # Buscar emails do grupo 'gestao' (configurado via NOTIFICATION_EMAILS_GESTAO no .env)
    recipient_emails = get_notification_emails('gestao')
    
    # Se não houver emails configurados, NÃO envia
    if not recipient_emails:
        logger.info(f'Nenhum email configurado em NOTIFICATION_EMAILS_GESTAO - email não enviado')
        return
    
    # Calcular prazo de entrega (6 horas úteis)
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Buscar última solicitação de imagem
    last_request = post.change_requests.filter(
        change_type='image'
    ).order_by('-created_at').first()
    
    requested_at = last_request.created_at if last_request else post.created_at
    deadline = _calculate_image_deadline(requested_at)
    deadline_formatted = deadline.strftime('%d/%m/%y às %H:%M')
    
    subject = f'🔄 Solicitação de alteração de imagem - Post #{post.id}'
    
    context = {
        'post': post,
        'message': message,
        'organization': post.organization,
        'requester_name': user.get_full_name() if user else 'Usuário',
        'post_url': f"{settings.SITE_URL}/admin/posts/post/{post.id}/change/" if hasattr(settings, 'SITE_URL') else '',
        'requested_at': requested_at,
        'deadline': deadline_formatted,
    }
    
    try:
        html_message = render_to_string('emails/post_change_request.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_emails,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f'Email de solicitação de alteração enviado para {recipient_emails}')
    except Exception as e:
        logger.error(f'Erro ao enviar email de alteração: {e}')
        raise


def _post_audit(post, action, user, meta=None):
    """
    Registra log de auditoria para ações em posts
    """
    # TODO: Implementar sistema de auditoria se necessário
    logger.info(f'[AUDIT] Post {post.id} - Action: {action} - User: {user} - Meta: {meta}')


def _resolve_user_name(payload_data, user, organization):
    """
    Resolve o nome do usuário a partir do payload ou do objeto user
    """
    if payload_data and payload_data.get('requester_name'):
        return payload_data.get('requester_name')
    
    if user and hasattr(user, 'get_full_name'):
        full_name = user.get_full_name()
        if full_name:
            return full_name
    
    if user and hasattr(user, 'email'):
        return user.email
    
    return 'Usuário'
