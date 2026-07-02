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

    # VB: editor de texto generico (mesmo front), com fonte por elemento.
    # raw = cena sem texto (bg + ilustracao); elements = zonas de texto editaveis.
    if post.pipeline_used == 'vb':
        from apps.posts.services.vb.specs import SPECS
        vbx = (post.local_pipeline_context or {}).get('vb') or {}
        sp = SPECS.get((vbx.get('archetype') or '').strip())
        cw, ch = (sp['canvas'] if sp else _get_canvas(post))
        vb_font_urls = {k: f'/posts/{post.id}/todxs-font/{k}/'
                        for k in ('light', 'semibold', 'medium')}
        return JsonResponse({
            'elements': _get_elements(post),
            'raw_image_url': _get_raw_image_url(post), 'logo_url': '',
            'canvas_w': cw, 'canvas_h': ch, 'font_names': {}, 'font_urls': {},
            'todxs_font_urls': vb_font_urls, 'pipeline': 'vb', 'status': post.status,
            'raw_image_s3_key': post.raw_image_s3_key or '', 'background_history_size': 0,
        })

    # Samsung Healthcare: editor generico (mesmo front), fonte por font_key
    # (Samsung SS Head/Body servidas via /posts/<id>/samsung-font/<key>/).
    if post.pipeline_used == 'samsung':
        from apps.posts.services.samsung.wireframes import FONT_FILES
        s_font_urls = {k: f'/posts/{post.id}/samsung-font/{k}/' for k in FONT_FILES}
        return JsonResponse({
            'elements': _get_elements(post),
            'raw_image_url': _get_raw_image_url(post), 'logo_url': '',
            'canvas_w': 1080, 'canvas_h': 1350, 'font_names': {}, 'font_urls': {},
            'todxs_font_urls': s_font_urls, 'pipeline': 'samsung', 'status': post.status,
            'raw_image_s3_key': post.raw_image_s3_key or '', 'background_history_size': 0,
        })

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

    # TODXS: fontes por CHAVE de uso (display/regular/caps_small) p/ o editor
    # desenhar com a mesma fonte do render Pillow (por elemento, nao por papel).
    todxs_font_urls = {}
    if post.pipeline_used == 'todxs':
        for k in ('display', 'medium', 'regular', 'caps_small'):
            todxs_font_urls[k] = f'/posts/{post.id}/todxs-font/{k}/'

    history = ((post.local_pipeline_context or {}).get('background_history') or [])

    return JsonResponse({
        'elements': elements,
        'raw_image_url': raw_image_url,
        'logo_url': logo_url,
        'canvas_w': canvas_w,
        'canvas_h': canvas_h,
        'font_names': font_names,
        'font_urls': font_urls,
        'todxs_font_urls': todxs_font_urls,
        'pipeline': post.pipeline_used or '',
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
    """Área de validação do pipeline simples v2 (ADMIN-ONLY).

    Retorna o fundo SEM texto, a imagem final e os prompts/JSON usados, para
    comparação visual. Disponível em prod apenas para administradores.
    """
    # Equipe INTERNA apenas (superuser/staff). profile=='admin' e o admin da
    # empresa-CLIENTE — nao deve ver o debug.
    is_admin = bool(request.user.is_superuser or request.user.is_staff)
    if not is_admin:
        return JsonResponse({'error': 'forbidden'}, status=403)
    post = get_object_or_404(Post, id=post_id, organization=request.organization)

    def _presign(key, fallback=''):
        if not key:
            return fallback
        try:
            from apps.core.services.s3_service import S3Service
            return S3Service.generate_presigned_download_url(key, expires_in=3600)
        except Exception:
            return fallback

    # Pipeline TODXS: estrutura propria (fundo + pillow publicado + gemini-texto
    # de comparacao). Reusa o mesmo painel admin, mapeando os campos.
    if post.pipeline_used == 'todxs':
        tx = (post.local_pipeline_context or {}).get('todxs') or {}
        di = tx.get('debug_images') or {}
        trace = tx.get('trace') or []

        def _step(name):
            return next((t for t in trace if t.get('etapa') == name), {}) or {}

        bg_t, gx_t, pil_t = _step('2_background'), _step('2b_gemini_text_debug'), _step('3_pillow_render')
        return JsonResponse({
            'pipeline': 'todxs', 'status': post.status,
            'bg_url': di.get('fundo') or _presign(post.raw_image_s3_key),
            'final_url': di.get('pillow') or _presign(post.image_s3_key),
            'gemini_url': di.get('gemini_texto') or '',
            'bg_prompt': bg_t.get('prompt') or '(fundo solido desenhado pelo Pillow — sem prompt)',
            'final_prompt': gx_t.get('prompt') or post.image_prompt or '',
            'rules': {
                'archetype': tx.get('archetype'), 'color_hex': tx.get('color_hex'),
                'background_mode': bg_t.get('mode'), 'fonts': pil_t.get('fonts'),
                'elements': (post.designer_payload or {}).get('_layout_elements'),
            },
            'model_bg': bg_t.get('model', 'pillow'),
            'model_final': 'todxs-pillow',
            'created_at': tx.get('updated_at', ''),
            'texts': {'title': post.title or '', 'subtitle': post.subtitle or '', 'cta': ''},
        })

    # Pipeline VB: fundo (cena sem texto) + arte final, ambos Pillow.
    if post.pipeline_used == 'vb':
        vb = (post.local_pipeline_context or {}).get('vb') or {}
        di = vb.get('debug_images') or {}
        return JsonResponse({
            'pipeline': 'vb', 'status': post.status,
            'bg_url': di.get('fundo') or _presign(post.raw_image_s3_key),
            'final_url': di.get('final') or _presign(post.image_s3_key),
            'gemini_url': '',
            'bg_prompt': '(VB: fundo + ilustracao desenhados pelo Pillow — sem prompt de imagem)',
            'final_prompt': post.image_prompt or '',
            'rules': {'archetype': vb.get('archetype'),
                      'objeto_ilustracao': vb.get('objeto_ilustracao')},
            'model_bg': 'vb-pillow', 'model_final': 'vb-pillow',
            'created_at': vb.get('updated_at', ''),
        })

    if post.pipeline_used != 'simple':
        return JsonResponse({'error': 'not_simple_pipeline'}, status=404)

    dbg = (post.local_pipeline_context or {}).get('simple_image') or {}

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

    # Stickers (role='image'): injeta data URI inline (mesma normalizacao).
    elements = _prepare_stickers_for_export(elements)

    # Render via PILLOW (render_layout_document) — MESMO motor da publicacao, para
    # que o "Baixar PNG" seja IDENTICO ao que aparece publicado. Antes usava
    # Playwright (regras de tamanho/centralizacao diferentes -> divergia).
    import base64 as _b64
    try:
        _, _, _payload = (raw_image_data or '').partition(',')
        bg_bytes = _b64.b64decode(_payload)
    except Exception:
        logger.error('[overlay] base do fundo invalida para export post=%s', post_id)
        return JsonResponse({'error': 'image_download_failed'}, status=500)

    try:
        if post.pipeline_used == 'todxs':
            # TODXS: usa o desenhador DEDICADO (mesmo do publicado) -> respeita
            # leading/quebras por elemento. render_layout_document ignoraria isso.
            from apps.posts.services.todxs.pillow_render import draw_todxs
            png_bytes = draw_todxs(bg_bytes, elements, canvas_w, canvas_h, logo_url=logo_url)
        elif post.pipeline_used == 'vb':
            from apps.posts.services.vb.render import draw_vb_compose
            from apps.posts.services.vb.specs import SPECS
            from PIL import Image
            import io as _io2
            vbx = (post.local_pipeline_context or {}).get('vb') or {}
            sp = SPECS.get((vbx.get('archetype') or '').strip())
            cw, ch = (sp['canvas'] if sp else (canvas_w, canvas_h))
            base = Image.open(_io2.BytesIO(bg_bytes)).convert('RGBA')
            if base.size != (cw, ch):
                base = base.resize((cw, ch), Image.LANCZOS)
            draw_vb_compose(base, elements, cw, ch)
            _o = _io2.BytesIO(); base.convert('RGB').save(_o, 'PNG'); png_bytes = _o.getvalue()
        else:
            from apps.posts.services.gemini_image_generator import render_layout_document
            png_bytes = render_layout_document(
                bg_bytes, elements, paleta=None, fonts=font_paths, logo_url=logo_url,
            )
    except Exception:
        logger.exception('[overlay] render (export) falhou post=%s', post_id)
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


_TODXS_FONT_KEYS = {'display', 'medium', 'regular', 'caps_small'}


@login_required
@require_GET
def todxs_font_file(request, post_id, key):
    """Serve a fonte real da TODXS por CHAVE de uso (display/medium/regular/
    caps_small) — para o editor desenhar com a MESMA fonte do render Pillow."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    # VB: serve a fonte Barlow Condensed (stand-in da Acumin) por chave. Aditivo.
    if post.pipeline_used == 'vb':
        import os
        from apps.posts.services.vb.render import _font_path, _FONT_FILES
        if key not in _FONT_FILES:
            return JsonResponse({'error': 'key_invalida'}, status=400)
        fp = _font_path(key)
        if not os.path.isfile(fp):
            return JsonResponse({'error': 'font_missing'}, status=404)
        mime, _m = mimetypes.guess_type(fp)
        resp = FileResponse(open(fp, 'rb'), content_type=mime or 'font/ttf')
        resp['Cache-Control'] = 'private, max-age=3600'
        resp['Access-Control-Allow-Origin'] = '*'
        return resp
    if key not in _TODXS_FONT_KEYS:
        return JsonResponse({'error': 'key_invalida'}, status=400)
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.services.todxs.pillow_render import resolve_todxs_weights
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    fp = (resolve_todxs_weights(kb) or {}).get(key) if kb else None
    if not fp:
        return JsonResponse({'error': 'font_missing'}, status=404)
    try:
        resolved = Path(fp).resolve()
        if _FONTS_CACHE_DIR not in resolved.parents or not resolved.is_file():
            return JsonResponse({'error': 'path_forbidden'}, status=403)
    except Exception:
        return JsonResponse({'error': 'invalid_path'}, status=400)
    mime, _ = mimetypes.guess_type(resolved.name)
    resp = FileResponse(open(resolved, 'rb'),
                        content_type=mime or ('font/otf' if resolved.suffix.lower() == '.otf' else 'font/ttf'))
    resp['Cache-Control'] = 'private, max-age=3600'
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


@login_required
@require_GET
def samsung_font_file(request, post_id, key):
    """Serve a fonte Samsung SS (Head/Body) por font_key, bundled em
    services/samsung/fonts/ — para o editor desenhar igual ao render Pillow."""
    post = get_object_or_404(Post, id=post_id, organization=request.organization)
    from apps.posts.services import samsung as _samsung_pkg
    from apps.posts.services.samsung.wireframes import FONT_FILES
    fname = FONT_FILES.get(key)
    if not fname:
        return JsonResponse({'error': 'key_invalida'}, status=400)
    fp = os.path.join(os.path.dirname(_samsung_pkg.__file__), 'fonts', fname)
    if not os.path.isfile(fp):
        return JsonResponse({'error': 'font_missing'}, status=404)
    mime, _m = mimetypes.guess_type(fp)
    resp = FileResponse(open(fp, 'rb'), content_type=mime or 'font/otf')
    resp['Cache-Control'] = 'private, max-age=3600'
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


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

    # TODXS: re-renderiza e ATUALIZA a imagem publicada, para o preview da pagina
    # refletir as edicoes (senao o usuario so ve a mudanca abrindo o editor).
    image_url = None
    if post.pipeline_used == 'todxs':
        try:
            image_url = _todxs_rerender_published(post, elements)
        except Exception:
            logger.exception('[overlay] re-render todxs (save) falhou post=%s', post.id)
    elif post.pipeline_used == 'vb':
        try:
            image_url = _vb_rerender_published(post, elements)
        except Exception:
            logger.exception('[overlay] re-render vb (save) falhou post=%s', post.id)
    return JsonResponse({'ok': True, 'image_url': image_url})


def _vb_rerender_published(post, elements):
    """Redesenha a arte VB (raw cena + texto editado) e atualiza a imagem publicada."""
    import base64 as _b64
    from apps.posts.models import PostImage
    from apps.posts.services.vb.render import draw_vb_compose
    from apps.posts.services.vb.specs import SPECS
    from apps.posts.tasks import _upload_image_to_s3
    from apps.core.services.s3_service import S3Service
    from PIL import Image
    import io as _io

    raw_data = _download_as_data_uri(_get_raw_image_url(post))
    if not raw_data:
        return None
    _, _, payload = raw_data.partition(',')
    base = Image.open(_io.BytesIO(_b64.b64decode(payload))).convert('RGBA')
    vbx = (post.local_pipeline_context or {}).get('vb') or {}
    sp = SPECS.get((vbx.get('archetype') or '').strip())
    cw, ch = (sp['canvas'] if sp else _get_canvas(post))
    if base.size != (cw, ch):
        base = base.resize((cw, ch), Image.LANCZOS)
    draw_vb_compose(base, elements, cw, ch)  # imagem (stickers) + texto
    out = _io.BytesIO(); base.convert('RGB').save(out, 'PNG')

    old_key = post.image_s3_key
    key, url = _upload_image_to_s3(org_id=post.organization_id, post_id=post.id,
                                   png_bytes=out.getvalue(), mime_type='image/png')
    if old_key:
        PostImage.objects.filter(post=post, s3_key=old_key).update(s3_key=key, s3_url=url)
    post.image_s3_key, post.image_s3_url = key, url
    gi = post.generated_images if isinstance(post.generated_images, list) else []
    gi.append({'s3_key': key, 'url': url})
    post.generated_images = gi
    post.save(update_fields=['image_s3_key', 'image_s3_url', 'generated_images'])
    try:
        return S3Service.generate_presigned_download_url(key, expires_in=86400)
    except Exception:
        return url


def _todxs_rerender_published(post, elements):
    """Redesenha a arte do post todxs (draw_todxs) a partir do fundo + elementos
    editados e atualiza post.image_s3_key/url + a PostImage ativa. Retorna a URL."""
    import base64 as _b64
    from apps.posts.models import PostImage
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.services.todxs.pillow_render import draw_todxs
    from apps.posts.services.todxs.assets import todxs_wordmark_url
    from apps.posts.tasks import _upload_image_to_s3
    from apps.core.services.s3_service import S3Service

    raw_data = _download_as_data_uri(_get_raw_image_url(post))
    if not raw_data:
        return None
    _, _, payload = raw_data.partition(',')
    bg_bytes = _b64.b64decode(payload)
    cw, ch = _get_canvas(post)
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    logo_url = todxs_wordmark_url(kb) if kb else _get_logo_url(post)
    els = _prepare_stickers_for_export(elements)
    png = draw_todxs(bg_bytes, els, cw, ch, logo_url=logo_url)

    old_key = post.image_s3_key
    key, url = _upload_image_to_s3(org_id=post.organization_id, post_id=post.id,
                                   png_bytes=png, mime_type='image/png')
    if old_key:
        PostImage.objects.filter(post=post, s3_key=old_key).update(s3_key=key, s3_url=url)
    post.image_s3_key, post.image_s3_url = key, url
    gi = post.generated_images if isinstance(post.generated_images, list) else []
    gi.append({'s3_key': key, 'url': url})
    post.generated_images = gi
    post.save(update_fields=['image_s3_key', 'image_s3_url', 'generated_images'])
    try:
        return S3Service.generate_presigned_download_url(key, expires_in=86400)
    except Exception:
        return url


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
    # TODXS: sem post_format -> deriva do formato salvo no contexto (feed 4:5 /
    # story 9:16). Sem isso o canvas viraria 1080x1080 e desalinharia o editor.
    px = ((post.local_pipeline_context or {}).get('todxs') or {}).get('formato_px')
    if px:
        try:
            w, h = (int(x) for x in str(px).lower().split('x'))
            return w, h
        except Exception:
            pass
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
