"""
Assets visuais da TODXS para o single-shot.

Seleciona o grafismo "X" (BrandgraficModule), o logo primario (Logo) e renderiza
um specimen da Ana Banana Black (para enviesar o desenho tipografico no Gemini).
Tambem resolve a "ultima cor usada" para a rotacao de cor da skill.
"""
import io
import logging

logger = logging.getLogger(__name__)


def last_todxs_color_hex(organization):
    """HEX da cor de destaque do ultimo post TODXS (para evitar repetir)."""
    from apps.posts.models import Post
    qs = Post.objects.filter(
        organization=organization, pipeline_used='todxs'
    ).order_by('-id')[:10]
    for p in qs:
        ctx = (p.local_pipeline_context or {}).get('todxs') or {}
        hexv = ctx.get('color_hex')
        if hexv:
            return hexv
    return None


def pick_grafismo_x(kb, *, rotate_seed: int = 0):
    """
    Escolhe um grafismo "X" ativo+aprovado da KB. Rotaciona por rotate_seed
    (ex.: contagem de posts) para variar a peca. Retorna dict ou None.
    """
    from apps.knowledge.models import BrandgraficModule
    from apps.core.services.s3_service import S3Service
    qs = list(
        BrandgraficModule.objects.filter(
            knowledge_base=kb, is_active=True, approved_by_user=True
        ).order_by('name')
    )
    if not qs:
        return None
    gm = qs[rotate_seed % len(qs)]
    url = gm.s3_url
    try:
        url = S3Service.generate_presigned_download_url(gm.s3_key, expires_in=3600)
    except Exception:
        pass
    return {'name': gm.name, 's3_key': gm.s3_key, 'url': url}


def render_ana_banana_specimen(kb, text: str):
    """
    Renderiza um PNG com a manchete na Ana Banana Black (fonte real do S3), para
    anexar ao Gemini como guia tipografico. Best-effort: None se falhar.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        from apps.posts.services.font_resolver import _load_custom_font
        # Resolve direto pelo CustomFont (Ana Banana), independente de Typography:
        # prefere o peso Black; cai para qualquer titulo; por fim qualquer fonte.
        cf = (
            kb.custom_fonts.filter(name__icontains='Black').first()
            or kb.custom_fonts.filter(font_type='titulo').first()
            or kb.custom_fonts.first()
        )
        path = _load_custom_font(cf) if cf else None
        if not path:
            return None
        sample = (text or 'TODXS').strip()[:28].upper() or 'TODXS'
        font = ImageFont.truetype(path, 120)
        img = Image.new('RGB', (1400, 320), (244, 241, 217))  # off-white da marca
        draw = ImageDraw.Draw(img)
        draw.text((40, 90), sample, font=font, fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        return buf.getvalue()
    except Exception:
        logger.warning('[todxs.assets] falha ao renderizar specimen Ana Banana', exc_info=True)
        return None
