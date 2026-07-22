"""Efeitos do catalogo — portados FIELMENTE dos pipelines de origem.

scrim, guide_line: origem services/samsung/render.py (pixel-parity provada no
lado a lado v2 vs v3 do samsung B). Novos efeitos: docstring com os params e
qual eixo cada um usa (ux/uy/ub).
"""
from PIL import Image

from . import register


@register('scrim')
def scrim(img, draw, params, ctx):
    """Escurece um lado p/ legibilidade de texto sobre foto (origem: samsung B).
    params: color (token|hex), alpha (0-255, default 205), to (FRACAO do eixo
    onde o gradiente zera, default 0.6 — unitless por definicao do efeito),
    axis ('x' default = esquerda->direita; 'y' = topo->base, origem thermomix)."""
    W, H = img.size
    from apps.posts.services.artkit.image import hex_to_rgb
    color = hex_to_rgb(ctx['color'](params.get('color', '#0A1420')))
    a0 = int(params.get('alpha', 205))
    axis = params.get('axis', 'x')
    span = H if axis == 'y' else W
    split = max(1, int(float(params.get('to', 0.6)) * span))
    if axis == 'y':
        mask = Image.new('L', (1, H))
        mpx = mask.load()
        for y in range(H):
            t = min(1.0, y / split)
            mpx[0, y] = int(a0 * (1 - t))
    else:
        mask = Image.new('L', (W, 1))
        mpx = mask.load()
        for x in range(W):
            t = min(1.0, x / split)
            mpx[x, 0] = int(a0 * (1 - t))
    mask = mask.resize((W, H))
    ov = Image.new('RGB', (W, H), color)
    return Image.composite(ov, img, mask)


@register('panel')
def panel(img, draw, params, ctx):
    """Faixa/painel translucido atras de blocos de texto (origem: thermomix A).
    params geometricos (unidade da spec): x (ux), y (uy), w (ux), h (uy),
    radius (ub, default 0). color = token|hex; alpha 0-255 (default 191 = 75%).
    layer tipico: 'raw' (cozido no fundo editavel, antes do snapshot)."""
    from apps.posts.services.artkit.image import hex_to_rgb
    col = hex_to_rgb(ctx['color'](params.get('color', '#FFFFFF')))
    alpha = int(params.get('alpha', 191))
    x, y = ctx['ux'](params['x']), ctx['uy'](params['y'])
    w, h = ctx['ux'](params['w']), ctx['uy'](params['h'])
    r = ctx['ub'](params.get('radius', 0))
    base = img.convert('RGBA') if img.mode != 'RGBA' else img
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    from PIL import ImageDraw as _ImageDraw
    od = _ImageDraw.Draw(ov)
    od.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=r,
                         fill=col + (alpha,))
    out = Image.alpha_composite(base, ov)
    return out if img.mode == 'RGBA' else out.convert('RGB')


@register('guide_line')
def guide_line(img, draw, params, ctx):
    """Linha-guia fina decorativa em ╰ (origem: samsung B): desce reta do topo,
    curva p/ a direita (radius) e segue ate x_end.
    params geometricos (unidade da spec): x (ux), y0/y1 (uy), curve (ub),
    x_end (ux), width (ub). color = token|hex."""
    col = ctx['color'](params.get('color', '#3874B0'))
    w = ctx['ub'](params.get('width', 2))
    x, y0, y1 = ctx['ux'](params['x']), ctx['uy'](params['y0']), ctx['uy'](params['y1'])
    r = ctx['ub'](params.get('curve', 0))
    x_end = ctx['ux'](params.get('x_end', params['x']))
    if r > 0:
        draw.line([(x, y0), (x, y1 - r)], fill=col, width=w)
        draw.arc([x, y1 - 2 * r, x + 2 * r, y1], 90, 180, fill=col, width=w)
        draw.line([(x + r, y1), (x_end, y1)], fill=col, width=w)
    else:
        draw.line([(x, y0), (x, y1)], fill=col, width=w)
        draw.line([(x, y1), (x_end, y1)], fill=col, width=w)
    return None


@register('rounded_border')
def rounded_border(img, draw, params, ctx):
    """Moldura de cantos arredondados na arte inteira (origem: todxs B story).
    params: radius (% da LARGURA — quantizacao int() historica do todxs),
    bg_color (token|hex do preenchimento fora dos cantos, default off-white).
    layer tipico: 'final'."""
    from PIL import ImageDraw as _ImageDraw
    from apps.posts.services.artkit.image import hex_to_rgb
    W, H = ctx['canvas']
    radius = int(float(params.get('radius', 0)) / 100.0 * W)  # int() historico
    bg = hex_to_rgb(ctx['color'](params.get('bg_color', '#F4F1D9')))
    src = img.convert('RGB')
    mask = Image.new('L', (W, H), 0)
    _ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=radius, fill=255)
    out = Image.new('RGB', (W, H), bg)
    out.paste(src, (0, 0), mask)
    return out
