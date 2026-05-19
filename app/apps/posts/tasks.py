"""
Celery tasks da pipeline interna de geracao de post.

Substitui os workflows N8N (gerar-post-appiamkt e gerarimagem-appiamkt)
quando o usuario clica em "Enviar Fluxo interno" no modal.

Tasks:
    - generate_post_text_task(post_id): gera texto via Claude Sonnet 4.5
    - generate_post_image_task(post_id, message): gera imagem via Gemini 3 Pro
"""

import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_post_text_task(self, post_id: int):
    """
    Gera o texto do post (title, subtitle, image_prompt, caption, hashtags,
    visual_brief, cta_text) via Claude Sonnet 4.5. Atualiza o Post no banco.

    Substitui o N8N workflow 'gerar-post-appiamkt'. Disparada quando o user
    clica em 'Enviar Fluxo interno' no modal.

    Fluxo:
        1. Carrega Post + KB
        2. Monta resumo da KB (preferindo n8n_compilation)
        3. Chama Claude via service
        4. Salva campos do Post (caption, hashtags, title, subtitle,
           image_prompt, visual_brief, cta)
        5. Loga em AIUsageLog
        6. Status final: 'awaiting_image' (user pode disparar imagem depois)
    """
    from apps.posts.models import Post
    from apps.posts.services.claude_post_generator import generate_post_text

    logger.info('[posts.local] generate_post_text_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    # Marca em progresso
    post.status = 'generating'
    post.save(update_fields=['status'])

    # Resumo da KB (igual ao fallback do N8N)
    kb_summary = _build_kb_summary(post.organization)

    # Formato (PostFormat ou dict legado)
    formato = _format_to_dict(post.post_format) if post.post_format else {
        'name': post.formats[0] if post.formats else 'feed',
        'aspect_ratio': '1:1',
    }

    # Logos da KB (passados como URLs para o prompt)
    logo_urls = list(_logos_from_org(post.organization))

    # Reference images do Post (PostReferenceImage)
    reference_images = list(_reference_images_from_post(post))

    try:
        result = generate_post_text(
            knowledge_base_summary=kb_summary,
            rede_social=post.social_network,
            formato=formato,
            tema=post.requested_theme,
            cta_requested=post.cta_requested,
            is_carousel=post.is_carousel,
            image_count=post.image_count,
            reference_images=reference_images,
            logo_urls=logo_urls,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Claude post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    structured = result['structured']
    usage = result['usage']

    # Normaliza hashtags: garante prefixo '#' em cada item (Claude as vezes esquece)
    raw_hashtags = structured.get('hashtags') or []
    normalized_hashtags = [
        h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
        for h in raw_hashtags if h
    ]
    structured['hashtags'] = normalized_hashtags

    # Aplica resultado no Post
    if post.is_carousel and isinstance(structured.get('slides'), list):
        # Carrossel: salva slides em campo dedicado (se existir) ou em caption
        slides = structured['slides']
        post.caption = structured.get('caption') or ''
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text') or ''
        # Slides ficam disponiveis para o gerador de imagem via primeiro slide
        if slides:
            first = slides[0]
            post.title = first.get('title', '')
            post.subtitle = first.get('subtitle', '')
            post.image_prompt = first.get('image_prompt', '')
            post.visual_brief = first.get('visual_brief', '')
        # Guarda todos os slides no JSON do post para a etapa de imagem
        post.slides_data = slides
    else:
        post.title = structured.get('title', '')
        post.subtitle = structured.get('subtitle', '')
        post.image_prompt = structured.get('image_prompt', '')
        post.visual_brief = structured.get('visual_brief', '')
        post.caption = structured.get('caption', '')
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text', '')

    post.ia_provider = 'anthropic'
    post.ia_model_text = result['model']
    # Status final 'pending' segue mesma semantica do callback N8N:
    # texto pronto, aguardando user clicar em "Gerar Imagem" depois.
    post.status = 'pending'
    post.save()

    # Loga custo
    _log_usage(post, result['model'], usage, purpose='generate_post_text')

    logger.info(
        '[posts.local] generate_post_text_task OK post_id=%s tokens_in=%s tokens_out=%s cost=$%s',
        post_id, usage.get('input_tokens'), usage.get('output_tokens'),
        usage.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        'model': result['model'],
        'usage': usage,
    }


# ---- Helpers ----------------------------------------------------------------


def _build_kb_summary(organization) -> str:
    """
    Constroi resumo textual da KB usado como contexto no prompt.
    Prefere `n8n_compilation.marketing_input_summary`; se vazio, monta string
    com 6 campos da KB.
    """
    from apps.knowledge.models import KnowledgeBase

    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return f'(Organizacao {organization.name} sem base de conhecimento)'

    # n8n_compilation pode ser dict (atual) ou string (legado)
    compilation = getattr(kb, 'n8n_compilation', None)
    summary_text = ''
    if isinstance(compilation, dict):
        summary_text = (compilation.get('marketing_input_summary') or '').strip()
    elif isinstance(compilation, str):
        summary_text = compilation.strip()
    if summary_text and len(summary_text) > 50:
        return summary_text

    # Fallback manual
    parts = [
        f'Empresa: {kb.nome_empresa or organization.name}',
    ]
    if kb.missao:
        parts.append(f'Missao: {kb.missao}')
    if kb.posicionamento:
        parts.append(f'Posicionamento: {kb.posicionamento}')
    if kb.tom_voz_externo:
        parts.append(f'Tom de voz: {kb.tom_voz_externo}')
    if kb.publico_externo:
        parts.append(f'Publico-alvo: {kb.publico_externo}')
    if kb.proposta_valor:
        parts.append(f'Proposta de valor: {kb.proposta_valor}')
    return '\n'.join(parts)


def _format_to_dict(post_format) -> dict:
    return {
        'name': post_format.name,
        'width': post_format.width,
        'height': post_format.height,
        'aspect_ratio': post_format.aspect_ratio,
    }


def _logos_from_org(organization):
    """Retorna URLs dos logos cadastrados na KB da org."""
    from apps.knowledge.models import KnowledgeBase, Logo
    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return []
    return [l.s3_url for l in Logo.objects.filter(knowledge_base=kb) if l.s3_url]


def _reference_images_from_post(post):
    """Retorna lista de dicts com URL e descricao de uso de cada PostReferenceImage."""
    from apps.posts.models import PostReferenceImage
    refs = PostReferenceImage.objects.filter(post=post).order_by('order', 'id')
    out = []
    for ref in refs:
        out.append({
            'url': ref.s3_url,
            's3_key': ref.s3_key,
            'name': ref.original_name,
            'usage_description': getattr(ref, 'usage_description', '') or '',
            'aspects_to_use': getattr(ref, 'aspects_to_use', '') or '',
            'usage_type': getattr(ref, 'usage_type', '') or '',
        })
    return out


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_post_image_task(self, post_id: int, message: str = ''):
    """
    Gera a imagem do post via Gemini 3 Pro Image e salva no S3.

    Substitui o N8N workflow 'gerarimagem-appiamkt'. Disparada quando o user
    clica em 'Gerar Imagem' no detalhe do post (para posts com pipeline=local).

    Fluxo:
        1. Carrega Post + KB
        2. Coleta paleta, tipografia, referencias (logos, ref_kb, ref_post)
        3. Gera presigned URLs (24h) para todas as referencias
        4. Chama Gemini via service (multimodal: prompt + inline_data das refs)
        5. Faz upload do PNG no S3
        6. Atualiza Post (post_images, image_s3_url, status='image_ready')
        7. Loga em AIUsageLog
    """
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.models import Post
    from apps.posts.services.gemini_image_generator import generate_post_image

    logger.info('[posts.local] generate_post_image_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format', 'user'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'image_generating'
    post.save(update_fields=['status'])

    # KB + dados de design
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    paleta = _kb_colors(kb)
    tipografia = _kb_typography(kb)
    references = _collect_references(kb=kb, post=post)
    publico_alvo = (kb.publico_externo if kb else '') or ''
    marketing_input_summary = _kb_summary_marketing(kb)
    formato_px = _formato_px(post)

    try:
        result = generate_post_image(
            post=post,
            references=references,
            paleta=paleta,
            tipografia=tipografia,
            publico_alvo=publico_alvo,
            marketing_input_summary=marketing_input_summary,
            formato_px=formato_px,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Gemini post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    # Upload PNG no S3
    s3_key, s3_url = _upload_image_to_s3(
        org_id=post.organization.id,
        post_id=post.id,
        png_bytes=result['png_bytes'],
        mime_type=result.get('mime_type', 'image/png'),
    )

    # Cria PostImage (model FK que o frontend le via post.images.all())
    # Equivalente ao que o callback N8N faz em views_webhook.py
    from apps.posts.models import PostImage
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    next_order = (max_order if max_order is not None else -1) + 1
    PostImage.objects.create(
        post=post,
        s3_key=s3_key,
        s3_url=s3_url,
        order=next_order,
    )

    # Atualiza Post (campos principais + lista json)
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = result['model']
    img_entry = {
        's3_key': s3_key,
        'url': s3_url,
        'width': post.image_width or None,
        'height': post.image_height or None,
    }
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append(img_entry)
    post.generated_images = existing
    post.status = 'image_ready'
    post.save()

    # Loga custo
    _log_usage_gemini(post, result['model'], result.get('cost_usd', 0))

    logger.info(
        '[posts.local] generate_post_image_task OK post_id=%s s3_key=%s cost=$%s',
        post_id, s3_key, result.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        's3_key': s3_key,
        's3_url': s3_url,
        'cost_usd': result.get('cost_usd'),
    }


def _kb_colors(kb) -> list:
    if not kb:
        return []
    try:
        return [
            {
                'nome': c.name,
                'hex': c.hex_code,
                'tipo': c.color_type or 'primary',
            }
            for c in kb.colors.all().order_by('order')
        ]
    except Exception:
        return []


def _kb_typography(kb) -> list:
    if not kb:
        return []
    try:
        out = []
        for f in kb.typography_settings.all().order_by('order'):
            nome = (
                f.google_font_name if f.font_source == 'google'
                else (f.custom_font.name if f.custom_font else '')
            )
            out.append({
                'uso': f.usage,
                'origem': f.font_source or 'google',
                'nome': nome,
                'peso': f.google_font_weight if f.font_source == 'google' else 'regular',
            })
        return out
    except Exception:
        return []


def _kb_summary_marketing(kb) -> str:
    """Recupera marketing_input_summary do n8n_compilation, fallback string vazia."""
    if not kb:
        return ''
    compilation = getattr(kb, 'n8n_compilation', None)
    if isinstance(compilation, dict):
        return compilation.get('marketing_input_summary') or ''
    return ''


def _formato_px(post) -> str:
    if post.post_format and post.post_format.width and post.post_format.height:
        return f'{post.post_format.width}x{post.post_format.height}'
    if post.image_width and post.image_height:
        return f'{post.image_width}x{post.image_height}'
    return '1080x1080'


def _collect_references(kb, post) -> list:
    """
    Coleta logos, reference images da KB e PostReferenceImage como lista de
    dicts {tipo, url} com presigned URLs validas por 24h.
    """
    from apps.core.services.s3_service import S3Service
    out = []

    if kb:
        # Logos
        try:
            for logo in kb.logos.all().order_by('-is_primary', 'logo_type'):
                if logo.s3_key:
                    try:
                        url = S3Service.generate_presigned_download_url(
                            logo.s3_key, expires_in=86400
                        )
                        out.append({'tipo': 'logotipo', 'url': url})
                    except Exception:
                        pass
        except Exception:
            pass

        # KB references
        try:
            for img in kb.reference_images.all():
                if img.s3_key:
                    try:
                        url = S3Service.generate_presigned_download_url(
                            img.s3_key, expires_in=86400
                        )
                        out.append({'tipo': 'referencia_kb', 'url': url})
                    except Exception:
                        pass
        except Exception:
            pass

    # Post-specific references
    try:
        for ref in post.reference_image_files.all():
            if ref.s3_key:
                try:
                    url = S3Service.generate_presigned_download_url(
                        ref.s3_key, expires_in=86400
                    )
                    out.append({'tipo': 'referencia_post', 'url': url})
                except Exception:
                    pass
    except Exception:
        pass

    return out


def _upload_image_to_s3(*, org_id: int, post_id: int, png_bytes: bytes, mime_type: str):
    """Faz upload do PNG gerado no S3 e retorna (s3_key, s3_url presigned)."""
    from apps.core.services.s3_service import S3Service
    from django.utils import timezone as dj_tz

    ext = 'png' if mime_type == 'image/png' else 'jpg'
    ts = int(dj_tz.now().timestamp() * 1000)
    s3_key = f'org-{org_id}/imagensgeradas/{ts}-post{post_id}-generated.{ext}'

    client = S3Service._get_s3_client()
    bucket = S3Service._get_bucket_name() if hasattr(S3Service, '_get_bucket_name') else None
    if not bucket:
        from django.conf import settings as dj_settings
        bucket = dj_settings.AWS_BUCKET_NAME

    client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=png_bytes,
        ContentType=mime_type,
    )

    s3_url = S3Service.generate_presigned_download_url(s3_key, expires_in=86400)
    return s3_key, s3_url


def _log_usage_gemini(post, model: str, cost_usd: float):
    """Loga custo Gemini em AIUsageLog (defensivo)."""
    try:
        from apps.core.models import AIUsageLog
    except ImportError:
        return
    try:
        AIUsageLog.objects.create(
            organization=post.organization,
            post=post,
            user=post.user,
            provider=AIUsageLog.Provider.GEMINI,
            model=model,
            purpose=AIUsageLog.Purpose.GENERATE_POST_IMAGE,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=Decimal(str(cost_usd or 0)),
            raw_usage={'note': 'Gemini image generation — cost flat-rate estimate'},
        )
    except Exception:
        logger.exception('Falha ao salvar AIUsageLog (Gemini)')


def _log_usage(post, model: str, usage: dict, purpose: str):
    """Salva AIUsageLog para a chamada. No-op se o model nao existir nesta branch."""
    try:
        from apps.core.models import AIUsageLog
    except ImportError:
        logger.debug('AIUsageLog nao disponivel nesta branch — pulando log de custo')
        return
    try:
        AIUsageLog.objects.create(
            organization=post.organization,
            post=post,
            user=post.user,
            provider=AIUsageLog.Provider.ANTHROPIC,
            model=model,
            purpose=AIUsageLog.Purpose.GENERATE_POST_TEXT,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            cached_input_tokens=usage.get('cache_read_input_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            cost_usd=Decimal(str(usage.get('cost_usd', 0))),
            raw_usage=usage,
        )
    except Exception:
        logger.exception('Falha ao salvar AIUsageLog')
