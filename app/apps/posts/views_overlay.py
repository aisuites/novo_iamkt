"""
Views para overlay HTML: preview dos textos sobre a imagem Gemini
e exportação para PNG via Playwright.
"""
import asyncio
import base64
import json
import logging
import os
import urllib.request

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from apps.posts.models import Post

logger = logging.getLogger(__name__)


def _download_as_data_uri(url: str) -> str:
    """Baixa uma URL (ex: presigned S3) e retorna data URI base64. Retorna '' se falhar."""
    if not url:
        return ''
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            mime = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            if not mime.startswith('image/'):
                mime = 'image/jpeg'
        uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        logger.info('[overlay] download OK: %d bytes, %s', len(data), mime)
        return uri
    except Exception:
        logger.exception('[overlay] falha ao baixar URL: %s', url[:80])
        return ''


@login_required
@require_GET
def overlay_data(request, post_id):
    """Retorna JSON com elements, raw_image_url, logo_url e font_names para o frontend."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)

    elements = _get_elements(post)
    raw_image_url = _get_raw_image_url(post)
    logo_url = _get_logo_url(post)
    canvas_w, canvas_h = _get_canvas(post)
    font_names = _get_font_names(post)

    if not elements or not raw_image_url:
        return JsonResponse({'error': 'overlay_not_ready'}, status=404)

    return JsonResponse({
        'elements': elements,
        'raw_image_url': raw_image_url,
        'logo_url': logo_url,
        'canvas_w': canvas_w,
        'canvas_h': canvas_h,
        'font_names': font_names,
    })


@login_required
@require_POST
def export_png(request, post_id):
    """Renderiza o overlay HTML via Playwright e retorna PNG para download."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)

    # Elementos editados enviados pelo frontend
    try:
        body = json.loads(request.body or '{}')
        elements = body.get('elements') or []
    except Exception:
        elements = []

    if not elements:
        elements = _get_elements(post)

    canvas_w, canvas_h = _get_canvas(post)
    font_paths = _get_font_paths(post)

    if not elements:
        return JsonResponse({'error': 'overlay_not_ready'}, status=404)

    # Persiste posições editadas
    _save_elements(post.pk, elements)

    # Gera presigned URLs novas e baixa no servidor → data URIs para o Playwright
    raw_image_url = _get_raw_image_url(post)
    logo_url = _get_logo_url(post)

    raw_image_data = _download_as_data_uri(raw_image_url)
    logo_data = _download_as_data_uri(logo_url)

    if not raw_image_data:
        logger.error('[overlay] imagem não pôde ser baixada para export post=%s', post_id)
        return JsonResponse({'error': 'image_download_failed'}, status=500)

    from apps.posts.services.html_renderer import build_html
    html = build_html(
        elements=elements,
        raw_image_url=raw_image_data,
        logo_url=logo_data,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        font_paths=font_paths,
    )

    try:
        png_bytes = asyncio.run(_playwright_screenshot(html, canvas_w, canvas_h))
    except Exception:
        logger.exception('[overlay] Playwright falhou post=%s', post_id)
        return JsonResponse({'error': 'render_failed'}, status=500)

    response = HttpResponse(png_bytes, content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="post-{post_id}-arte.png"'
    return response


@login_required
@require_POST
def save_elements(request, post_id):
    """Persiste os elementos editados — chamado ao fechar o modal."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    try:
        body = json.loads(request.body or '{}')
        elements = body.get('elements')
        if not isinstance(elements, list) or not elements:
            return JsonResponse({'error': 'invalid_elements'}, status=400)
    except Exception:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    _save_elements(post.pk, elements)
    return JsonResponse({'ok': True})


async def _playwright_screenshot(html: str, width: int, height: int) -> bytes:
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/playwright-browsers')
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.new_page(viewport={'width': width, 'height': height})
        await page.set_content(html, wait_until='networkidle')
        await page.wait_for_timeout(500)
        png = await page.screenshot(
            clip={'x': 0, 'y': 0, 'width': width, 'height': height},
            full_page=False,
        )
        await browser.close()
        return png


# ── helpers ────────────────────────────────────────────────────────────────

def _save_elements(post_pk: int, elements: list) -> None:
    """Grava elementos no banco usando update() direto — evita conflitos de instância."""
    try:
        post = Post.objects.get(pk=post_pk)
        dp = dict(post.designer_payload or {})
        dp['_layout_elements'] = elements
        Post.objects.filter(pk=post_pk).update(designer_payload=dp)
        logger.info('[overlay] elements salvos post=%s (%d els)', post_pk, len(elements))
    except Exception:
        logger.exception('[overlay] falha ao salvar elements post=%s', post_pk)


def _get_elements(post: Post):
    dp = post.designer_payload or {}
    elements = dp.get('_layout_elements') or []
    if not elements:
        cp = post.copy_payload or {}
        elements = cp.get('_layout_elements') or []
    return elements


def _get_raw_image_url(post: Post) -> str:
    if not post.raw_image_s3_key:
        return post.raw_image_s3_url or ''
    try:
        from apps.core.services.s3_service import S3Service
        return S3Service.generate_presigned_download_url(post.raw_image_s3_key, expires_in=3600)
    except Exception:
        return post.raw_image_s3_url or ''


def _get_logo_url(post: Post) -> str:
    try:
        from apps.knowledge.models import KnowledgeBase
        from apps.core.services.s3_service import S3Service
        kb = KnowledgeBase.objects.filter(organization=post.organization).first()
        if not kb:
            return ''
        ctx = post.local_pipeline_context or {}
        selected_ids = ctx.get('selected_logo_ids') or []
        logo = (
            kb.logos.filter(id__in=selected_ids).first() if selected_ids
            else kb.logos.filter(is_primary=True).first() or kb.logos.first()
        )
        if not logo or not logo.s3_key:
            return ''
        return S3Service.generate_presigned_download_url(logo.s3_key, expires_in=3600)
    except Exception:
        return ''


def _get_canvas(post: Post):
    if post.post_format:
        return post.post_format.width or 1080, post.post_format.height or 1080
    return 1080, 1080


def _get_font_names(post: Post) -> dict:
    try:
        from apps.posts.tasks import _get_kb, _kb_typography
        kb = _get_kb(post)
        tipografia = _kb_typography(kb)
        titulo_font = next(
            (t['nome'] for t in tipografia if t.get('uso', '').lower() == 'titulo'),
            'serif'
        )
        return {'titulo': titulo_font, 'subtitulo': titulo_font, 'cta': titulo_font}
    except Exception:
        return {'titulo': 'serif', 'subtitulo': 'serif', 'cta': 'serif'}


def _get_font_paths(post: Post) -> dict:
    try:
        from apps.posts.tasks import _get_kb, _prepare_pillow_overlay, _formato_px
        kb = _get_kb(post)
        fonts_data = _prepare_pillow_overlay(post, kb, _formato_px(post))
        return {
            'titulo':    fonts_data.get('pillow_title_font_path') or '',
            'subtitulo': fonts_data.get('pillow_subtitle_font_path') or '',
            'cta':       fonts_data.get('pillow_title_font_path') or '',
        }
    except Exception:
        return {}
