"""
Celery tasks da pipeline interna de geracao de post.

Substitui os workflows N8N (gerar-post-appiamkt e gerarimagem-appiamkt)
quando o usuario clica em "Enviar Fluxo interno" no modal.

Tasks:
    - generate_post_text_task(post_id): gera texto via Claude Sonnet 4.5
    - generate_post_image_task(post_id): gera imagem via Gemini 3 Pro (Etapa 3)
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
    Prefere `n8n_compilation`; se vazio, monta string com 6 campos.
    """
    from apps.knowledge.models import KnowledgeBase

    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return f'(Organizacao {organization.name} sem base de conhecimento)'

    # n8n_compilation pode nao existir como campo dependendo da migracao
    compilation = getattr(kb, 'n8n_compilation', None) or ''
    if compilation and len(compilation.strip()) > 50:
        return compilation.strip()

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
