"""
Renderizador Pillow determinístico dos arquétipos Samsung Healthcare.

Fase atual: Arquétipo A (foto-topo + agradecimento, fundo preto sólido).
Consome a spec de wireframes.WIREFRAMES/WF() e produz o PNG final + o raw
(fundo) + os _layout_elements (consumidos pela edição avançada), no mesmo
contrato de retorno/schema de elementos do todxs/vb (roles: titulo/subtitulo/
image; font_key servido por /posts/<id>/samsung-font/<key>/).
"""
import base64
import io
import os
import logging
import urllib.request

from PIL import Image, ImageDraw, ImageFont

from .wireframes import WF, TOKENS, FONT_FILES

logger = logging.getLogger(__name__)

_FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
_font_cache = {}

# roles que o canvas da edição avançada entende
_EDITOR_ROLE = {'title': 'titulo'}  # demais textos -> 'subtitulo'
_BOLD_KEYS = {'head_bold', 'body_bold'}


def _font(font_key: str, size: int) -> ImageFont.FreeTypeFont:
    size = max(6, int(size))
    ck = (font_key, size)
    if ck in _font_cache:
        return _font_cache[ck]
    path = os.path.join(_FONTS_DIR, FONT_FILES.get(font_key, FONT_FILES['head_regular']))
    f = ImageFont.truetype(path, size)
    _font_cache[ck] = f
    return f


def _color(token: str) -> str:
    if not token:
        return '#000000'
    return TOKENS.get(token, token)


def _apply_case(text: str, case: str) -> str:
    if case == 'upper':
        return text.upper()
    return text


def _hex2rgb(h):
    from apps.posts.services.artkit.image import hex_to_rgb
    return hex_to_rgb(_color(h))


def _gradient_bg(W, H, bg):
    """Gradiente radial navy: claro perto de (cx,cy), escurece p/ os cantos.
    Renderiza em baixa resolução e escala (rápido + suave)."""
    import math
    light = _hex2rgb(bg.get('light', '#33445C'))
    dark = _hex2rgb(bg.get('dark', '#0A1420'))
    cx, cy = bg.get('cx', 0.6), bg.get('cy', 0.32)
    lw, lh = 96, 120
    g = Image.new('RGB', (lw, lh))
    px = g.load()
    ccx, ccy = cx * lw, cy * lh
    maxd = max(math.hypot(ccx, ccy), math.hypot(ccx - lw, ccy),
               math.hypot(ccx, ccy - lh), math.hypot(ccx - lw, ccy - lh))
    for yy in range(lh):
        for xx in range(lw):
            t = min(1.0, math.hypot(xx - ccx, yy - ccy) / maxd)
            px[xx, yy] = tuple(int(light[i] + (dark[i] - light[i]) * t) for i in range(3))
    return g.resize((W, H), Image.BICUBIC)


def _apply_scrim(base, sc):
    """Escurece a esquerda (navy) p/ legibilidade quando a foto é fundo inteiro.
    Gradiente de alpha: forte na esquerda -> 0 em sc['to']*W."""
    W, H = base.size
    color = _hex2rgb(sc.get('color', '#0A1420'))
    a0 = int(sc.get('alpha', 205))
    split = max(1, int(sc.get('to', 0.6) * W))
    mask = Image.new('L', (W, 1))
    mpx = mask.load()
    for x in range(W):
        t = min(1.0, x / split)
        mpx[x, 0] = int(a0 * (1 - t))
    mask = mask.resize((W, H))
    ov = Image.new('RGB', (W, H), color)
    return Image.composite(ov, base, mask)


def _draw_guide_line(draw, gl):
    """Linha-guia fina (accent) decorativa em forma de ╰: vem reta do topo,
    desce, curva p/ a DIREITA (radius r, estilo arquétipo A) e segue reto p/ a
    direita até x_end (sem radius no fim)."""
    col = _color(gl.get('color', 'accent_blue'))
    w = gl.get('width', 2)
    x, y0, y1 = gl['x'], gl['y0'], gl['y1']
    r = gl.get('curve', 0)
    x_end = gl.get('x_end', x)
    if r > 0:
        draw.line([(x, y0), (x, y1 - r)], fill=col, width=w)          # vertical
        draw.arc([x, y1 - 2 * r, x + 2 * r, y1], 90, 180, fill=col, width=w)  # curva ╰
        draw.line([(x + r, y1), (x_end, y1)], fill=col, width=w)      # horizontal
    else:
        draw.line([(x, y0), (x, y1)], fill=col, width=w)
        draw.line([(x, y1), (x_end, y1)], fill=col, width=w)


def _fetch(src) -> Image.Image:
    if isinstance(src, (bytes, bytearray)):
        data = bytes(src)
    else:
        req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    return Image.open(io.BytesIO(data)).convert('RGBA')


def _cover(img, w, h):
    from apps.posts.services.artkit.image import cover
    return cover(img, w, h, rounding=round)  # samsung: round() historico


def _contain(img, w, h):
    from apps.posts.services.artkit.image import contain
    return contain(img, w, h)


def _round_corners(img, radius, corners):
    if not radius or not corners:
        return img
    w, h = img.size
    mask = Image.new('L', (w, h), 255)
    md = ImageDraw.Draw(mask)
    r = radius
    spots = {'top-left': (0, 0), 'top-right': (w - r, 0),
             'bottom-left': (0, h - r), 'bottom-right': (w - r, h - r)}
    arcs = {'top-left': (180, 270), 'top-right': (270, 360),
            'bottom-left': (90, 180), 'bottom-right': (0, 90)}
    bboxes = {'top-left': [0, 0, 2 * r, 2 * r], 'top-right': [w - 2 * r, 0, w, 2 * r],
              'bottom-left': [0, h - 2 * r, 2 * r, h], 'bottom-right': [w - 2 * r, h - 2 * r, w, h]}
    for c in corners:
        if c not in spots:
            continue
        x, y = spots[c]
        md.rectangle([x, y, x + r, y + r], fill=0)
        md.pieslice(bboxes[c], arcs[c][0], arcs[c][1], fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


def _wrap(text, font, max_w, draw):
    words = (text or '').split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        if draw.textlength(cur + ' ' + w, font=font) <= max_w:
            cur += ' ' + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _fit(text, font_key, box_w, box_h, max_lines, start_px, leading, draw, min_px=12):
    size = int(start_px)
    while size >= min_px:
        font = _font(font_key, size)
        lines = _wrap(text, font, box_w, draw)
        if len(lines) <= max_lines and len(lines) * size * leading <= box_h + 1:
            return font, size, lines
        size -= 1
    font = _font(font_key, min_px)
    return font, min_px, _wrap(text, font, box_w, draw)[:max_lines]


def _draw_line(draw, xy, line, font, fill, tracking=0.0):
    if not tracking:
        draw.text(xy, line, font=font, fill=fill)
        return
    x, y = xy
    extra = tracking * font.size
    for ch in line:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + extra


def _datauri(img):
    buf = io.BytesIO()
    img.convert('RGBA').save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def render_samsung(*, archetype, content, kb=None, assets=None):
    """Retorna {raw_png, final_png, elements, fonts_resolved}."""
    assets = assets or {}
    spec = WF().get(archetype)
    if not spec:
        raise ValueError(f'arquétipo desconhecido: {archetype}')

    W, H = 1080, 1350
    BASIS = min(W, H)
    bg = spec.get('background') or {'type': 'solid', 'color': 'black'}
    if assets.get('background_image'):
        # Imagem opaca de produto (ou Gemini) ocupa o fundo INTEIRO da arte.
        try:
            base = _cover(_fetch(assets['background_image']).convert('RGB'), W, H)
        except Exception:
            base = Image.new('RGB', (W, H), _color(bg.get('color', 'black')))
        if spec.get('scrim'):
            base = _apply_scrim(base, spec['scrim'])
    elif bg.get('type') == 'gradient':
        base = _gradient_bg(W, H, bg)
    else:
        base = Image.new('RGB', (W, H), _color(bg.get('color', 'black')))
    draw = ImageDraw.Draw(base)

    # ---- zonas de imagem (baked no raw = fundo) ----
    for z in spec.get('zones', []):
        if z.get('category') != 'image':
            continue
        src = assets.get(z['key']) or assets.get('photo')
        x, y, w, h = z['box']
        if src:
            try:
                if z.get('fit') == 'contain':
                    img = _contain(_fetch(src), w, h)
                    ha, va = z.get('halign', 'center'), z.get('anchor', 'top')
                    ox = (x + (w - img.width) // 2 if ha == 'center'
                          else x + w - img.width if ha == 'right' else x)
                    oy = (y + (h - img.height) if va == 'bottom'
                          else y + (h - img.height) // 2 if va == 'center' else y)
                    base.paste(img, (ox, oy), img if img.mode == 'RGBA' else None)
                else:
                    img = _round_corners(_cover(_fetch(src), w, h), z.get('radius', 0), z.get('round_corners'))
                    base.paste(img, (x, y), img if img.mode == 'RGBA' else None)
            except Exception:
                logger.exception('[samsung] falha imagem zona=%s', z['key'])
        bd = z.get('border')
        if bd:
            rc = z.get('round_corners') or []
            corners = ('top-left' in rc, 'top-right' in rc, 'bottom-right' in rc, 'bottom-left' in rc)
            draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=z.get('radius', 0),
                                   corners=corners, outline=_color(bd.get('color', '#444')),
                                   width=bd.get('width', 2))

    gl = spec.get('guide_line')
    if gl:
        _draw_guide_line(draw, gl)

    raw = base.copy()

    elements = []
    fonts_resolved = {}

    # ---- zonas de texto ----
    for z in spec.get('zones', []):
        cat = z.get('category')
        if cat in ('image',):
            continue
        if cat == 'partner_logo':
            src = assets.get('partner_logo')
            if not src:
                continue
            x, y, w, h = z['box']
            try:
                lg = _contain(_fetch(src), w, h)
                px = x + (w - lg.width) if z.get('align') == 'right' else x
                py = y + (h - lg.height) // 2
                base.paste(lg, (px, py), lg)
                elements.append({'role': 'image', 'zone': 'partner_logo', 'url': _datauri(lg),
                                 'x_pct': round(px / W * 100, 3), 'y_pct': round(py / H * 100, 3),
                                 'width_pct': round(lg.width / W * 100, 3),
                                 'height_pct': round(lg.height / H * 100, 3)})
            except Exception:
                logger.exception('[samsung] partner_logo falhou')
            continue

        text = (content or {}).get(z['key'])
        if not text:
            continue
        text = _apply_case(str(text).strip(), z.get('case', 'none'))
        x, y, w, h = z['box']
        leading = z.get('leading', 1.1)
        font, size, lines = _fit(text, z['font'], w, h, z.get('max_linhas', 1),
                                 z.get('fs', 40), leading, draw)
        fonts_resolved[z['font']] = FONT_FILES[z['font']]
        fill = _color(z.get('color', 'white'))
        ly = y
        for ln in lines:
            _draw_line(draw, (x, ly), ln, font, fill, z.get('tracking', 0.0))
            ly += size * leading
        elements.append({
            'role': _EDITOR_ROLE.get(z['key'], 'subtitulo'), 'zone': z['key'],
            'content': '\n'.join(lines),
            'x_pct': round(x / W * 100, 3), 'y_pct': round(y / H * 100, 3),
            'width_pct': round(w / W * 100, 3), 'height_pct': round(h / H * 100, 3),
            'font_size_pct': round(size / BASIS * 100, 4), 'font_key': z['font'],
            'weight': 'bold' if z['font'] in _BOLD_KEYS else 'regular',
            'color': fill, 'align': z.get('align', 'left'), 'case': 'none',
            '_leading': leading, '_font_file': FONT_FILES[z['font']],
            'tracking': z.get('tracking', 0.0),
        })

    # ---- brand_lockup FIXO (elemento imagem editável) ----
    bl = spec.get('brand_lockup')
    if bl and assets.get('brand_lockup'):
        x, y, w, h = bl['box']
        try:
            lg = _contain(_fetch(assets['brand_lockup']), w, h)
            px = x + (w - lg.width) if bl.get('align') == 'right' else x
            py = y + (h - lg.height) // 2 if bl.get('valign') == 'center' else y
            base.paste(lg, (px, py), lg)
            elements.append({'role': 'image', 'zone': 'brand_lockup', 'url': _datauri(lg),
                             'x_pct': round(px / W * 100, 3), 'y_pct': round(py / H * 100, 3),
                             'width_pct': round(lg.width / W * 100, 3),
                             'height_pct': round(lg.height / H * 100, 3)})
        except Exception:
            logger.exception('[samsung] brand_lockup falhou')

    def _png(im):
        b = io.BytesIO()
        im.save(b, format='PNG')
        return b.getvalue()

    return {'raw_png': _png(raw), 'final_png': _png(base),
            'elements': elements, 'fonts_resolved': fonts_resolved}


def draw_samsung_compose(base, elements, W, H):
    """Compõe a arte a partir dos ELEMENTOS do editor (mesma convenção do canvas):
    pinta elementos de imagem (data URI) e desenha o texto. Usado pelo save/export
    do editor avançado (espelha draw_vb_compose)."""
    if base.mode != 'RGBA':
        base = base.convert('RGBA')
    draw = ImageDraw.Draw(base)
    basis = min(W, H)
    for el in elements:
        if el.get('visible') is False:
            continue
        role = (el.get('role') or '').lower()
        if role == 'image':
            url = el.get('url') or ''
            if not url.startswith('data:'):
                continue
            try:
                img = Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1]))).convert('RGBA')
                x = float(el.get('x_pct', 0)) / 100.0 * W
                y = float(el.get('y_pct', 0)) / 100.0 * H
                w = float(el.get('width_pct', 10)) / 100.0 * W
                h = float(el.get('height_pct', 10)) / 100.0 * H
                img = _contain(img, max(1, int(w)), max(1, int(h)))
                base.paste(img, (int(x + (w - img.width) / 2), int(y + (h - img.height) / 2)), img)
            except Exception:
                logger.exception('[samsung] compose: elemento de imagem falhou')
            continue
        text = str(el.get('content') or '')
        if not text.strip():
            continue
        size = max(8, int(float(el.get('font_size_pct', 4)) / 100.0 * basis))
        font = _font(el.get('font_key') or 'head_regular', size)
        x = float(el.get('x_pct', 0)) / 100.0 * W
        y = float(el.get('y_pct', 0)) / 100.0 * H
        bw = float(el.get('width_pct', 60)) / 100.0 * W
        align = (el.get('align') or 'left').lower()
        fill = el.get('color') or '#FFFFFF'
        leading = float(el.get('_leading', 1.1))
        tracking = float(el.get('tracking') or 0.0)
        for line in text.split('\n'):
            lw = draw.textlength(line, font=font)
            if tracking:
                lw += tracking * size * max(0, len(line) - 1)
            lx = x + (bw - lw) / 2 if align == 'center' else (x + bw - lw if align == 'right' else x)
            _draw_line(draw, (lx, y), line, font, fill, tracking)
            y += size * leading
    return base
