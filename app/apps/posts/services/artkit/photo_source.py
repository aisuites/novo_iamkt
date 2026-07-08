"""
Fonte da FOTO escolhida pelo usuario para pipelines de arquetipo (C1.6).

Prioridade (dono, 2026-07-08): UPLOAD feito no modal de gerar post (a imagem
e ADAPTADA pelo render: cover-crop na regiao de foto do arquetipo + tratamento
P&B/duotone/scrim do template) > REF da KB selecionada no modal > None
(o caller cai no Gemini). A escolha acontece NO MODAL, nao no portao.
"""
import logging

logger = logging.getLogger(__name__)


def _presigned(s3_key, s3_url=None):
    if s3_key:
        try:
            from apps.core.services.s3_service import S3Service
            return S3Service.generate_presigned_download_url(s3_key, expires_in=3600)
        except Exception:
            pass
    return s3_url or None


def _download(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception:
        logger.warning('[photo_source] download falhou: %s', (url or '')[:80],
                       exc_info=True)
        return None


def resolve_user_photo(post, kb):
    """(png_bytes, origin) da foto escolhida pelo usuario, ou (None, None).

    1. Upload do modal (PostReferenceImage, na ordem enviada)
    2. Ref da KB selecionada no modal (selected_reference_ids)
    """
    # 1) upload novo
    try:
        up = post.reference_image_files.order_by('order').first()
    except Exception:
        up = None
    if up:
        url = _presigned(up.s3_key, up.s3_url)
        if url:
            data = _download(url)
            if data:
                return data, 'user_upload'

    # 2) ref da KB selecionada
    ctx = post.local_pipeline_context or {}
    ids = ctx.get('selected_reference_ids') or []
    if kb and ids:
        try:
            from apps.knowledge.models import ReferenceImage
            ref = ReferenceImage.objects.filter(
                knowledge_base=kb, id__in=ids).first()
        except Exception:
            ref = None
        if ref:
            url = _presigned(ref.s3_key, getattr(ref, 's3_url', None))
            if url:
                data = _download(url)
                if data:
                    return data, f'kb_reference_{ref.id}'

    return None, None
