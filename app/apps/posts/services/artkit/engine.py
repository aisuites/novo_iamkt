"""
Engine v3 — renderizador UNICO de arquetipos a partir da spec normalizada
(artkit/spec3.py). Fase 2.3 (nucleo; cresce conforme os conversores chegam).

Pipeline de desenho (ordem fixa):
  1. background (solid | gradient | photo_* via assets)
  2. effects layer='bg'      (ex.: scrim — antes das zonas de imagem)
  3. zonas de IMAGEM         (assets; borda/cantos desenhados mesmo sem asset)
  4. effects layer='raw'     (ex.: guide_line — cozido no fundo editavel)
  5. --- snapshot RAW (o fundo que o editor recebe) ---
  6. zonas de TEXTO (fit fixed|shrink; overflow best_effort/rewrite — NUNCA
     descarta texto: Ponto 4) + partner_logo + brand_lockup
  7. effects layer='final'
Retorna {'raw_png','final_png','elements','fonts_resolved'} — elements no
formato CANONICO do editor (Ponto 5).

ctx exigido:
  font    callable(font_key, size_px) -> PIL.ImageFont
  assets  dict (background_image, product_hero, brand_lockup, ...)
  tokens  dict token->hex adicional (spec['tokens'] tem precedencia)
"""
import io
import logging

from PIL import Image, ImageDraw

from .image import cover as _cover, contain as _contain
from .text import wrap_greedy
from .spec3 import unit_helpers

logger = logging.getLogger(__name__)

_EDITOR_ROLE = {'title': 'titulo', 'titulo': 'titulo'}


def _apply_case(text, case):
    if case == 'upper':
        return text.upper()
    return text


def _draw_line(draw, xy, line, font, fill, tracking=0.0):
    if not tracking:
        draw.text(xy, line, font=font, fill=fill)
        return
    x, y = xy
    extra = tracking * font.size
    for ch in line:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + extra


def _fit_shrink(text, font_loader, font_key, box_w, box_h, max_lines,
                start_px, leading, draw, step=1, min_px=12):
    """Maior fonte que faz o texto caber (semantica samsung: tolerancia +1px).
    NUNCA descarta texto: se nem min_px couber, devolve completo (best_effort)."""
    size = int(start_px)
    while size >= min_px:
        font = font_loader(font_key, size)
        lines = wrap_greedy(text, font, box_w, draw)
        if len(lines) <= max_lines and len(lines) * size * leading <= box_h + 1:
            return font, size, lines, True
        size -= step
    font = font_loader(font_key, min_px)
    return font, min_px, wrap_greedy(text, font, box_w, draw), False


def _fit_block(text, font_path, max_w, max_h, max_lines, start_px, draw,
               min_px=14, leading=1.16, step=2):
    """Maior corpo cujo BLOCO (linhas empilhadas com leading) cabe na caixa
    (semantica todxs, fit_measure='block': mede altura TOTAL int() e checa a
    largura real de cada linha). Fallback = ultimo tamanho tentado (>= min_px):
    NUNCA descarta texto."""
    from PIL import ImageFont
    size = max(min_px, int(start_px))
    best = None
    while size >= min_px:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            return None, [str(text)], size, int(size * leading)
        lines = wrap_greedy(text, font, max_w, draw)
        total_h = int(size * leading * len(lines))
        fits_w = all(draw.textlength(ln, font=font) <= max_w for ln in lines)
        if len(lines) <= max_lines and total_h <= max_h and fits_w:
            return font, lines, size, total_h
        best = (font, lines, size, total_h)
        size -= step
    return best if best else (None, [str(text)], min_px, int(min_px * leading))


def _rounded(img, radius, corners):
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
              'bottom-left': [0, h - 2 * r, 2 * r, h],
              'bottom-right': [w - 2 * r, h - 2 * r, w, h]}
    for c in corners:
        if c not in spots:
            continue
        x, y = spots[c]
        md.rectangle([x, y, x + r, y + r], fill=0)
        md.pieslice(bboxes[c], arcs[c][0], arcs[c][1], fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


def _gradient_bg(W, H, bg, color):
    """Gradiente radial (origem samsung): claro em (cx,cy) -> escuro nos cantos."""
    import math
    from .image import hex_to_rgb
    light = hex_to_rgb(color(bg.get('light', '#33445C')))
    dark = hex_to_rgb(color(bg.get('dark', '#0A1420')))
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


def _fetch(src):
    import base64
    import urllib.request
    if isinstance(src, (bytes, bytearray)):
        data = bytes(src)
    elif isinstance(src, str) and src.startswith('data:'):
        data = base64.b64decode(src.partition(',')[2])
    else:
        req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    return Image.open(io.BytesIO(data)).convert('RGBA')


def _datauri(img):
    import base64
    buf = io.BytesIO()
    img.convert('RGBA').save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


# ---------------------------------------------------------------------------
# Camada de ELEMENTS (zonas layer='elements') — dialeto todxs/vb: o pos-raw
# vira _layout_elements EXPLICITOS (quantizados em %) e o desenho le OS
# ELEMENTOS, nao as zonas -> editor == publicado por construcao.
# Semanticas historicas preservadas: int() nas conversoes %->px, rects
# inclusivos, alpha_composite ancorado no topo-esquerda, acumulacao float do y
# de linha, corpo re-quantizado a partir do font_size_pct round(3).
# ---------------------------------------------------------------------------

def _zone_pct(z):
    """[x,y,w,h] em % — floats AUTORADOS (pct_box) ou box normalizado *100."""
    if z.get('pct_box'):
        return list(z['pct_box'])
    fx, fy, fw, fh = z['box']
    return [fx * 100.0, fy * 100.0, fw * 100.0, fh * 100.0]


def layout_element_zones(zones, content, ctx, W, H):
    """Resolve as zonas layer='elements' em elementos explicitos (sem desenhar)."""
    from PIL import Image as _Img, ImageDraw as _IDraw, ImageFont
    draw0 = _IDraw.Draw(_Img.new('RGB', (8, 8)))
    basis = min(W, H)
    font_paths = ctx.get('font_paths') or {}
    assets = ctx.get('assets') or {}
    color = ctx['color']
    els, bottoms = [], {}

    for z in zones:
        pct = _zone_pct(z)
        role = z.get('role')

        if role == 'grafismo':
            hexcol = color(z.get('color'))
            els.append({'role': 'grafismo', 'forma': 'retangulo',
                        'cor': hexcol, 'color': hexcol,
                        'x_pct': pct[0], 'y_pct': pct[1], 'width_pct': pct[2],
                        'height_pct': pct[3], 'raio_pct': 0, 'opacidade': 100})
            continue

        if role == 'image':
            if z.get('recolor'):
                els.append({'role': 'logo', 'zone': z['key'],
                            'x_pct': pct[0], 'y_pct': pct[1], 'width_pct': pct[2],
                            'logo_color': color(z['recolor'])})
            else:
                uri = assets.get(z.get('asset') or z['key'])
                if uri:
                    els.append({'role': 'image', 'zone': z['key'], 'url': uri,
                                'x_pct': pct[0], 'y_pct': pct[1],
                                'width_pct': pct[2], 'height_pct': pct[3]})
            continue

        # ---- texto ----
        val = (content or {}).get(z['key'])
        if not val:
            continue
        blocks = z.get('blocks')
        items = ([v for v in val if v] if (blocks and isinstance(val, list))
                 else [' '.join(val) if isinstance(val, list) else val])
        n = len(items) or 1
        bx, by, bw, bh = pct
        span = bh / n
        leading = float(z.get('leading', 1.16))
        fpath = font_paths.get(z.get('font'))
        max_lines = z.get('max_lines', 4)
        for i, raw_text in enumerate(items):
            box_y = (by + i * span) if blocks else by
            box_h = span if blocks else bh
            if z.get('flow_after') and z['flow_after'] in bottoms:
                box_y = bottoms[z['flow_after']] + z.get('flow_gap', 1.5)
                box_h = max(6.0, (z.get('y_max', 96) - box_y))
            text = str(raw_text).replace('\\n', ' ')
            if z.get('text_normalize') == 'collapse':
                text = ' '.join(text.split())
            if z.get('case') == 'upper':
                text = text.upper()
            max_w_px = bw / 100.0 * W
            max_h_px = box_h / 100.0 * H
            start_px = (z.get('fs') or 0.037) * basis   # fs ja normalizado
            if z.get('fit') == 'fixed':
                try:
                    font = ImageFont.truetype(fpath, max(8, int(start_px)))
                except Exception:
                    font = None
                lines = (wrap_greedy(text, font, max_w_px, draw0)[:max_lines]
                         if font else [text])
                size_px = int(start_px)
                total_h_px = int(size_px * leading * len(lines))
            else:
                min_px = int(round((z.get('min_fs') or (14.0 / basis)) * basis))
                font, lines, size_px, total_h_px = _fit_block(
                    text, fpath, max_w_px, max_h_px, max_lines, start_px, draw0,
                    min_px=min_px, leading=leading, step=int(z.get('fit_step', 2)))
            total_h_pct = total_h_px / H * 100.0
            draw_y = (box_y + (box_h - total_h_pct) / 2.0
                      if z.get('valign') == 'center' else box_y)
            els.append({
                'role': z.get('role') or 'subtitulo', 'zone': z['key'],
                'content': '\n'.join(lines),
                'x_pct': bx, 'y_pct': round(draw_y, 2), 'width_pct': bw,
                'height_pct': round(total_h_pct + 0.5, 2),
                'font_size_pct': round(size_px / basis * 100.0, 3),
                'weight': 'black' if z.get('role') == 'titulo' else 'regular',
                'case': 'none', 'align': z.get('align', 'left'),
                'color': color(z.get('color')),
                '_font_path': fpath, '_leading': leading, 'font_key': z.get('font'),
            })
            bottoms[z['key']] = draw_y + total_h_pct
    return els


def _paste_contain_el(base, sticker, el, W, H):
    """Cola contain no box do elemento, ancorado no topo-esquerda (todxs).
    height ausente => height_pct = width_pct (semantica historica do selo)."""
    x = int(float(el.get('x_pct', 0)) / 100.0 * W)
    y = int(float(el.get('y_pct', 0)) / 100.0 * H)
    bw = max(8, int(float(el.get('width_pct', 10)) / 100.0 * W))
    bh = max(8, int(float(el.get('height_pct', el.get('width_pct', 10))) / 100.0 * H))
    iw, ih = sticker.size
    s = min(bw / iw, bh / ih)
    sticker = sticker.resize((max(1, int(iw * s)), max(1, int(ih * s))), Image.LANCZOS)
    base.alpha_composite(sticker, (x, y))


def _draw_element_text(draw, el, W, H):
    from PIL import ImageFont
    from .image import hex_to_rgb
    basis = min(W, H)
    size = max(8, int(float(el.get('font_size_pct', 5)) / 100.0 * basis))
    try:
        font = ImageFont.truetype(el.get('_font_path'), size)
    except Exception:
        font = ImageFont.load_default()
    x = float(el.get('x_pct', 0)) / 100.0 * W
    y = float(el.get('y_pct', 0)) / 100.0 * H
    bw = float(el.get('width_pct', 60)) / 100.0 * W
    align = (el.get('align') or 'left').lower()
    fill = hex_to_rgb(el.get('color') or '#000000')
    line_h = size * float(el.get('_leading', 1.16))
    for line in str(el.get('content', '')).split('\n'):
        lw = draw.textlength(line, font=font)
        lx = x + (bw - lw) / 2 if align == 'center' else (x + bw - lw if align == 'right' else x)
        draw.text((lx, y), line, font=font, fill=fill)
        y += line_h


def draw_layout_elements(base, elements, ctx, W, H):
    """Desenha os elementos resolvidos: grafismos -> imagens/logos -> texto
    (mesma ordem de camadas do desenhador todxs). `base` deve ser RGBA."""
    import base64
    from .image import hex_to_rgb, recolor_opaque
    draw = ImageDraw.Draw(base)
    assets = ctx.get('assets') or {}

    for el in elements:
        if (el.get('role') or '') == 'grafismo':
            x = int(float(el.get('x_pct', 0)) / 100 * W)
            y = int(float(el.get('y_pct', 0)) / 100 * H)
            w = int(float(el.get('width_pct', 0)) / 100 * W)
            h = int(float(el.get('height_pct', 0)) / 100 * H)
            draw.rectangle([x, y, x + w, y + h],
                           fill=hex_to_rgb(el.get('cor') or el.get('color') or '#000000'))

    for el in elements:
        role = (el.get('role') or '')
        if role == 'image' and (el.get('url') or '').startswith('data:'):
            try:
                _, _, payload = el['url'].partition(',')
                st = Image.open(io.BytesIO(base64.b64decode(payload))).convert('RGBA')
                _paste_contain_el(base, st, el, W, H)
            except Exception:
                logger.exception('[engine.v3] elemento imagem falhou (%s)', el.get('zone'))
        elif role == 'logo':
            src = assets.get(el.get('zone') or 'wordmark') or assets.get('wordmark')
            if not src:
                continue
            try:
                lg = _fetch(src).convert('RGBA')
                lg = recolor_opaque(lg, hex_to_rgb(el.get('logo_color') or '#F4F1D9'))
                _paste_contain_el(base, lg, el, W, H)
            except Exception:
                logger.exception('[engine.v3] elemento logo falhou (%s)', el.get('zone'))

    for el in elements:
        if (el.get('role') or '') in ('titulo', 'subtitulo', 'cta') and el.get('content'):
            _draw_element_text(draw, el, W, H)


def render_v3(spec, *, content, ctx):
    """Renderiza a spec v3 NORMALIZADA com o content (dict zona->texto)."""
    assert spec.get('_normalized'), 'passe a spec por spec3.normalize() antes'
    W, H = spec['canvas']
    basis = min(W, H)
    assets = ctx.get('assets') or {}
    tokens = {**(ctx.get('tokens') or {}), **(spec.get('tokens') or {})}

    def color(token):
        if not token:
            return '#000000'
        return tokens.get(token, token)

    ectx = {**unit_helpers(spec), 'color': color, 'assets': assets,
            'canvas': (W, H)}
    effects = spec.get('effects') or []

    def run_effects(layer, base, draw):
        from .effects import get_effect
        for e in effects:
            if (e.get('layer') or 'raw') != layer:
                continue
            need = e.get('only_if')
            if need and not assets.get(need):
                continue
            new = get_effect(e['name'])(base, draw, e, ectx)
            if new is not None:
                base = new
                draw = ImageDraw.Draw(base)
        return base, draw

    def px_box(box):
        fx, fy, fw, fh = box
        return (int(round(fx * W)), int(round(fy * H)),
                int(round(fw * W)), int(round(fh * H)))

    # ---- 1. background ----
    bg = spec.get('background') or {'type': 'solid', 'color': 'black'}
    if assets.get('background_image'):
        try:
            base = _cover(_fetch(assets['background_image']).convert('RGB'), W, H,
                          rounding=round)
        except Exception:
            base = Image.new('RGB', (W, H), color(bg.get('color', 'black')))
    elif bg.get('type') == 'gradient':
        base = _gradient_bg(W, H, bg, color)
    else:
        base = Image.new('RGB', (W, H), color(bg.get('color', 'black')))
    draw = ImageDraw.Draw(base)

    # ---- 2. effects bg (ex.: scrim sobre a foto) ----
    base, draw = run_effects('bg', base, draw)

    # ---- 3. zonas de imagem (layer 'raw'; as de layer 'elements' vem depois) ----
    for z in spec['zones']:
        if z.get('layer') == 'elements':
            continue
        if (z.get('role') or z.get('category')) not in ('image', 'imagem', 'produto'):
            continue
        x, y, w, h = px_box(z['box'])
        src = assets.get(z['key']) or assets.get('photo')
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
                    src_img = _fetch(src)
                    if z.get('fetch') == 'rgb':   # historico todxs/vb
                        src_img = src_img.convert('RGB')
                    rounding = int if z.get('cover_rounding') == 'int' else round
                    img = _cover(src_img, w, h, rounding=rounding)
                    if z.get('grayscale'):
                        img = img.convert('L').convert('RGB')
                    if z.get('multiply'):
                        from PIL import ImageChops
                        from .image import hex_to_rgb
                        overlay = Image.new('RGB', img.size,
                                            hex_to_rgb(color(z['multiply'])))
                        img = ImageChops.multiply(img.convert('RGB'), overlay)
                    radius = int(round((z.get('radius') or 0) * basis))
                    img = _rounded(img, radius, z.get('round_corners'))
                    base.paste(img, (x, y), img if img.mode == 'RGBA' else None)
            except Exception:
                logger.exception('[engine.v3] falha imagem zona=%s', z['key'])
        bd = z.get('border')
        if bd:
            rc = z.get('round_corners') or []
            corners = ('top-left' in rc, 'top-right' in rc,
                       'bottom-right' in rc, 'bottom-left' in rc)
            radius = int(round((z.get('radius') or 0) * basis))
            width = int(round((bd.get('width') or 2 / basis) * basis)) \
                if isinstance(bd.get('width'), float) else int(bd.get('width', 2))
            draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=radius,
                                   corners=corners, outline=color(bd.get('color', '#444')),
                                   width=width)

    # ---- 4. effects raw (ex.: guide_line) ----
    base, draw = run_effects('raw', base, draw)
    raw = base.copy()

    elements, fonts_resolved = [], {}
    font_loader = ctx['font']
    font_files = spec.get('fonts') or {}

    # ---- 5b. camada de ELEMENTS (todxs/vb): layout explicito + desenho ----
    layout_zones = [z for z in spec['zones'] if z.get('layer') == 'elements']
    if layout_zones:
        base = base.convert('RGBA')
        lctx = {'color': color, 'assets': assets,
                'font_paths': ctx.get('font_paths') or {}}
        lay_els = layout_element_zones(layout_zones, content, lctx, W, H)
        draw_layout_elements(base, lay_els, lctx, W, H)
        draw = ImageDraw.Draw(base)
        elements.extend(lay_els)
        for z in layout_zones:
            if z.get('font') in font_files:
                fonts_resolved[z['font']] = font_files[z['font']]

    # ---- 6. zonas de texto + logos (inline; layer 'elements' ja resolvida) ----
    for z in spec['zones']:
        if z.get('layer') == 'elements':
            continue
        role = z.get('role') or z.get('category')
        if role in ('image', 'imagem', 'produto', 'grafismo'):
            continue
        if role == 'partner_logo' or z.get('category') == 'partner_logo':
            src = assets.get('partner_logo')
            if not src:
                continue
            x, y, w, h = px_box(z['box'])
            try:
                lg = _contain(_fetch(src), w, h)
                px_ = x + (w - lg.width) if z.get('align') == 'right' else x
                py = y + (h - lg.height) // 2
                base.paste(lg, (px_, py), lg)
                elements.append({'role': 'image', 'zone': 'partner_logo',
                                 'url': _datauri(lg),
                                 'x_pct': round(px_ / W * 100, 3),
                                 'y_pct': round(py / H * 100, 3),
                                 'width_pct': round(lg.width / W * 100, 3),
                                 'height_pct': round(lg.height / H * 100, 3)})
            except Exception:
                logger.exception('[engine.v3] partner_logo falhou')
            continue
        if role in ('logo_fixo', 'brand_lockup') or z.get('category') == 'brand_lockup':
            src = assets.get('brand_lockup') or assets.get(z.get('asset') or '')
            if not src:
                continue
            x, y, w, h = px_box(z['box'])
            try:
                lg = _contain(_fetch(src), w, h)
                px_ = x + (w - lg.width) if z.get('align') == 'right' else x
                py = y + (h - lg.height) // 2 if z.get('valign') == 'center' else y
                base.paste(lg, (px_, py), lg)
                elements.append({'role': 'image', 'zone': z['key'], 'url': _datauri(lg),
                                 'x_pct': round(px_ / W * 100, 3),
                                 'y_pct': round(py / H * 100, 3),
                                 'width_pct': round(lg.width / W * 100, 3),
                                 'height_pct': round(lg.height / H * 100, 3)})
            except Exception:
                logger.exception('[engine.v3] brand_lockup falhou')
            continue

        text = (content or {}).get(z['key'])
        if not text:
            continue
        text = _apply_case(str(text).strip(), z.get('case', 'none'))
        x, y, w, h = px_box(z['box'])
        leading = z.get('leading', 1.1)
        start_px = max(1, int(round((z.get('fs') or 0.037) * basis)))
        fit_mode = z.get('fit', 'shrink')
        if fit_mode == 'fixed':
            font = font_loader(z['font'], start_px)
            lines = wrap_greedy(text, font, w, draw)[: z.get('max_lines', 99)]
            size, fitted = start_px, True
        else:
            min_px = max(6, int(round((z.get('min_fs') or (12 / basis)) * basis)))
            font, size, lines, fitted = _fit_shrink(
                text, font_loader, z['font'], w, h, z.get('max_lines', 1),
                start_px, leading, draw, step=int(z.get('fit_step', 1)),
                min_px=min_px)
        if not fitted:
            logger.warning('[engine.v3] zona %s: texto nao coube nem no minimo '
                           '(best_effort; considere overflow=rewrite)', z['key'])
        if z.get('font') in font_files:
            fonts_resolved[z['font']] = font_files[z['font']]
        fill = color(z.get('color', 'white'))
        ly = y
        for ln in lines:
            _draw_line(draw, (x, ly), ln, font, fill, z.get('tracking', 0.0))
            ly += size * leading
        elements.append({
            'role': _EDITOR_ROLE.get(z['key'], 'subtitulo'), 'zone': z['key'],
            'content': '\n'.join(lines),
            'x_pct': round(x / W * 100, 3), 'y_pct': round(y / H * 100, 3),
            'width_pct': round(w / W * 100, 3), 'height_pct': round(h / H * 100, 3),
            'font_size_pct': round(size / basis * 100, 4), 'font_key': z['font'],
            'weight': z.get('weight') or ('bold' if 'bold' in (z.get('font') or '') else 'regular'),
            'color': fill, 'align': z.get('align', 'left'), 'case': 'none',
            '_leading': leading, '_font_file': font_files.get(z.get('font')),
            'tracking': z.get('tracking', 0.0),
        })

    # ---- 7. effects final ----
    base, draw = run_effects('final', base, draw)

    def _png(im):
        b = io.BytesIO()
        im.save(b, format='PNG')
        return b.getvalue()

    # final SEMPRE RGB (semantica historica dos 3 pipelines; no-op se ja RGB)
    final = base if base.mode == 'RGB' else base.convert('RGB')
    return {'raw_png': _png(raw), 'final_png': _png(final),
            'elements': elements, 'fonts_resolved': fonts_resolved}
