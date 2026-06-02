"""
Views para overlay HTML: preview dos textos sobre a imagem Gemini
e exportação para PNG via Playwright.
"""
import asyncio
import base64
import json
import logging
import mimetypes
import os
import urllib.request
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
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
    font_paths = _get_font_paths(post) or {}

    if not elements or not raw_image_url:
        return JsonResponse({'error': 'overlay_not_ready'}, status=404)

    # Para cada role, indica se ha TTF/OTF servivel via endpoint /fonts/<role>/.
    # JS injeta @font-face apontando ao endpoint quando tem arquivo (sempre que
    # _get_font_paths achou path); fallback so se nao houver arquivo nenhum.
    font_urls = {}
    for role in _VALID_FONT_ROLES:
        if font_paths.get(role):
            font_urls[role] = f'/posts/{post.id}/fonts/{role}/'

    history = ((post.local_pipeline_context or {}).get('background_history') or [])

    return JsonResponse({
        'elements': elements,
        'raw_image_url': raw_image_url,
        'logo_url': logo_url,
        'canvas_w': canvas_w,
        'canvas_h': canvas_h,
        'font_names': font_names,
        'font_urls': font_urls,
        # Status + chave da imagem raw — usados pelo polling do "Solicitar nova
        # imagem de fundo" para saber quando a nova arte ficou pronta.
        'status': post.status,
        'raw_image_s3_key': post.raw_image_s3_key or '',
        # Tamanho do histórico de imagens de fundo — frontend usa pra
        # mostrar/esconder botão "Voltar imagem anterior".
        'background_history_size': len(history),
    })


@login_required
@require_GET
def simple_debug(request, post_id):
    """Área de validação (TEMPORÁRIA) do pipeline simples v2.

    Retorna o fundo SEM texto, a imagem final e os prompts/JSON usados, para
    comparação visual durante os testes. Restrito a pipeline_used='simple'.
    """
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    if post.pipeline_used != 'simple':
        return JsonResponse({'error': 'not_simple_pipeline'}, status=404)

    dbg = (post.local_pipeline_context or {}).get('simple_image') or {}

    def _presign(key, fallback=''):
        if not key:
            return fallback
        try:
            from apps.core.services.s3_service import S3Service
            return S3Service.generate_presigned_download_url(key, expires_in=3600)
        except Exception:
            return fallback

    return JsonResponse({
        'pipeline': 'simple',
        'status': post.status,
        'bg_url': _presign(post.raw_image_s3_key, post.raw_image_s3_url or ''),
        'final_url': _presign(post.image_s3_key, post.image_s3_url or ''),
        'bg_prompt': dbg.get('bg_prompt', ''),
        'final_prompt': dbg.get('final_prompt', ''),
        'rules': dbg.get('rules', {}),
        'model_bg': dbg.get('model_bg', ''),
        'model_final': dbg.get('model_final', ''),
        'created_at': dbg.get('created_at', ''),
        'texts': {'title': post.title or '', 'subtitle': post.subtitle or '', 'cta': post.cta or ''},
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

    # Stickers (role='image'): baixa cada um e injeta data URI no elemento.
    # Playwright headless nao busca URLs externas, entao precisa data URI inline.
    elements = _prepare_stickers_for_export(elements)

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


_VALID_FONT_ROLES = {'titulo', 'subtitulo', 'cta'}
_FONTS_CACHE_DIR = Path('/app/fonts_cache')

# Sticker upload — limites e MIME aceitos
_STICKER_MAX_BYTES = 8 * 1024 * 1024  # 8 MB hard cap
_STICKER_ACCEPTED_MIME = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
}


@login_required
@require_GET
def font_file(request, post_id, role):
    """Serve o arquivo TTF/OTF da fonte usada por um role do post.
    Permite que o modal Arte Final injete @font-face apontando para a fonte
    real da KB (ou Google Fonts cacheado) — independente do Google Fonts CSS.
    """
    if role not in _VALID_FONT_ROLES:
        return JsonResponse({'error': 'role_invalido'}, status=400)
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    paths = _get_font_paths(post)
    fp = (paths or {}).get(role) or ''
    if not fp:
        return JsonResponse({'error': 'font_missing'}, status=404)
    try:
        # Sandbox: so serve dentro de /app/fonts_cache
        resolved = Path(fp).resolve()
        if _FONTS_CACHE_DIR not in resolved.parents and resolved != _FONTS_CACHE_DIR:
            return JsonResponse({'error': 'path_forbidden'}, status=403)
        if not resolved.is_file():
            return JsonResponse({'error': 'file_missing'}, status=404)
    except Exception:
        return JsonResponse({'error': 'invalid_path'}, status=400)

    mime, _ = mimetypes.guess_type(resolved.name)
    if not mime:
        mime = 'font/otf' if resolved.suffix.lower() == '.otf' else 'font/ttf'
    resp = FileResponse(open(resolved, 'rb'), content_type=mime)
    resp['Cache-Control'] = 'private, max-age=3600'
    resp['Access-Control-Allow-Origin'] = '*'  # CORS-safe para @font-face
    return resp


@login_required
@require_POST
def regenerate_background(request, post_id):
    """Dispara task que regera SOMENTE a imagem de fundo a partir da imagem
    atual + mensagem do usuario. Nao toca em _layout_elements, copy, etc.

    Body JSON: {"message": "texto do usuario"}
    """
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    try:
        body = json.loads(request.body or '{}')
    except Exception:
        body = {}
    message = (body.get('message') or '').strip()
    if not message:
        return JsonResponse({'error': 'message_required'}, status=400)
    if not post.raw_image_s3_key:
        return JsonResponse({'error': 'no_raw_image'}, status=400)

    from apps.posts.tasks import regenerate_background_task
    regenerate_background_task.delay(post.id, message)
    return JsonResponse({
        'success': True,
        'status': 'queued',
        'current_raw_s3_key': post.raw_image_s3_key,
    })


@login_required
@require_POST
def restore_background(request, post_id):
    """Volta para a imagem de fundo anterior (pop do background_history).
    Empurra a atual de volta para o final do history (permite ping-pong)."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    ctx = dict(post.local_pipeline_context or {})
    history = list(ctx.get('background_history') or [])
    if not history:
        return JsonResponse({'error': 'history_empty'}, status=400)

    # Pop ultimo entry
    last = history.pop()
    prev_key = last.get('s3_key') or ''
    prev_url = last.get('s3_url') or ''
    if not prev_key:
        return JsonResponse({'error': 'history_invalid'}, status=500)

    # Salva o ATUAL no inicio do history (pode voltar a frente depois)
    current_key = post.raw_image_s3_key
    current_url = post.raw_image_s3_url or ''
    if current_key:
        # Insere no comeco para nao misturar com fluxo natural — pop sempre
        # retorna a mais recente. Aqui colocamos a "ultima trocada" no topo
        # invertido. Simpler: substitui post.raw e nao re-empurra. Decision:
        # empurra so para permitir refazer (UX redo).
        history.append({
            's3_key': current_key,
            's3_url': current_url,
            'replaced_at': last.get('replaced_at'),
            'user_request': '__restored__',
        })

    ctx['background_history'] = history
    post.local_pipeline_context = ctx
    post.raw_image_s3_key = prev_key
    post.raw_image_s3_url = prev_url
    post.save(update_fields=['raw_image_s3_key', 'raw_image_s3_url', 'local_pipeline_context'])

    # Regenera presigned para uso imediato no modal
    try:
        from apps.core.services.s3_service import S3Service
        fresh_url = S3Service.generate_presigned_download_url(prev_key, expires_in=3600)
    except Exception:
        fresh_url = prev_url

    return JsonResponse({
        'success': True,
        'raw_image_s3_key': prev_key,
        'raw_image_url': fresh_url,
        'history_remaining': len(history),
    })


@login_required
@require_POST
def upload_sticker(request, post_id):
    """Recebe upload de imagem (multipart) e armazena no S3 como sticker do post.
    Retorna {s3_key, url} para o frontend criar um elemento role='image' no canvas.
    """
    from apps.core.services.s3_service import S3Service

    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'arquivo_ausente'}, status=400)
    if f.size > _STICKER_MAX_BYTES:
        return JsonResponse({'error': 'arquivo_muito_grande', 'max_mb': 8}, status=413)
    ct = (f.content_type or '').lower().strip()
    if ct not in _STICKER_ACCEPTED_MIME:
        return JsonResponse({'error': 'tipo_nao_suportado', 'aceitos': sorted(_STICKER_ACCEPTED_MIME)}, status=415)

    import time
    safe_name = ''.join(c if c.isalnum() or c in ('.', '-', '_') else '_' for c in f.name)[:120]
    ts = int(time.time() * 1000)
    s3_key = f'org-{post.organization.id}/posts/stickers/{ts}-post{post.id}-{safe_name}'

    try:
        import boto3
        from django.conf import settings as dj_settings
        client = boto3.client(
            's3',
            region_name=getattr(dj_settings, 'AWS_S3_REGION_NAME', None) or 'us-east-1',
        )
        bucket = getattr(dj_settings, 'AWS_BUCKET_NAME', None) or os.environ.get('AWS_BUCKET_NAME', '')
        client.put_object(
            Bucket=bucket, Key=s3_key, Body=f.read(), ContentType=ct,
            ServerSideEncryption='AES256',
        )
    except Exception:
        logger.exception('[stickers] falha upload S3 post=%s', post_id)
        return JsonResponse({'error': 'upload_falhou'}, status=500)

    try:
        url = S3Service.generate_presigned_download_url(s3_key, expires_in=3600)
    except Exception:
        url = ''

    return JsonResponse({'s3_key': s3_key, 'url': url})


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

def _prepare_stickers_for_export(elements: list) -> list:
    """Para cada elemento role='image' (sticker), regenera presigned URL pelo
    s3_key (se houver) e baixa o arquivo como data URI no campo `url` — assim
    o html_renderer consegue inline na <img src> e o Playwright renderiza.
    Mantem todos os outros elementos intactos."""
    from apps.core.services.s3_service import S3Service
    out = []
    for el in elements or []:
        if (el.get('role') or '').lower() != 'image':
            out.append(el)
            continue
        new_el = dict(el)
        url = el.get('url') or ''
        s3_key = el.get('s3_key') or ''
        # Sempre regenera URL pelo s3_key (presigned pode ter expirado)
        if s3_key:
            try:
                url = S3Service.generate_presigned_download_url(s3_key, expires_in=600)
            except Exception:
                pass
        if url:
            data_uri = _download_as_data_uri(url)
            if data_uri:
                new_el['url'] = data_uri
        out.append(new_el)
    return out


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


def _norm_uso(s: str) -> str:
    """Normaliza rotulo de uso da tipografia (lower + sem acento + sem plural simples)."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return s.rstrip('s')  # 'titulos' -> 'titulo', 'subtitulos' -> 'subtitulo'


def _get_font_names(post: Post) -> dict:
    """Resolve a fonte da KB para exibicao no modal (browser).
    Tenta varios rotulos comuns ('titulo', 'headline', 'principal', 'primary')
    com normalizacao de acento/plural. Fallback: primeira fonte da KB, depois serif.
    """
    try:
        from apps.posts.tasks import _get_kb, _kb_typography
        kb = _get_kb(post)
        tipografia = _kb_typography(kb) or []
        if not tipografia:
            return {'titulo': 'serif', 'subtitulo': 'serif', 'cta': 'serif'}

        def _pick(usage_keys):
            for t in tipografia:
                u = _norm_uso(t.get('uso') or '')
                if any(k in u for k in usage_keys) and t.get('nome'):
                    return t['nome']
            return None

        titulo_font = (
            _pick(['titulo', 'headline', 'principal', 'primary', 'destaque'])
            or (tipografia[0].get('nome') if tipografia else None)
            or 'serif'
        )
        sub_font = (
            _pick(['subtitulo', 'secundaria', 'secondary', 'body', 'corpo', 'texto'])
            or titulo_font
        )
        return {'titulo': titulo_font, 'subtitulo': sub_font, 'cta': titulo_font}
    except Exception:
        logger.exception('[overlay] falha resolver font_names')
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
