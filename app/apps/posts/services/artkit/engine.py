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
    import urllib.request
    if isinstance(src, (bytes, bytearray)):
        data = bytes(src)
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

    # ---- 3. zonas de imagem ----
    for z in spec['zones']:
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
                    radius = int(round((z.get('radius') or 0) * basis))
                    img = _rounded(_cover(_fetch(src), w, h, rounding=round),
                                   radius, z.get('round_corners'))
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

    # ---- 6. zonas de texto + logos ----
    for z in spec['zones']:
        role = z.get('role') or z.get('category')
        if role in ('image', 'imagem', 'produto'):
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

    return {'raw_png': _png(raw), 'final_png': _png(base),
            'elements': elements, 'fonts_resolved': fonts_resolved}
