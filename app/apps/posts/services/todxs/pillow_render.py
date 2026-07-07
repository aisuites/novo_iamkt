"""
Render Pillow da TODXS — aplica texto/logo/selo/faixa sobre o fundo usando
render_layout_document (o MESMO motor do editor avancado), com a fonte real
(Ana Banana via CustomFont). Garante a fonte correta e abre na edicao avancada.

Fluxo: wireframe_elements (zonas -> _layout_elements) -> compoe o SELO (circulo
preto + X off-white) -> resolve fontes -> render_layout_document -> PNG final.

100% isolado: reusa apenas helpers low-level (render_layout_document,
_load_custom_font) sem alterar nada do fluxo existente.
"""
import base64
import io
import logging

logger = logging.getLogger(__name__)

_OFFWHITE = (244, 241, 217)


def _hex_to_rgb(h):
    from apps.posts.services.artkit.image import hex_to_rgb
    return hex_to_rgb(h)


def _parse_px(formato_px, default=(1080, 1350)):
    try:
        w, h = (int(x) for x in str(formato_px).lower().split('x'))
        return w, h
    except Exception:
        return default


def resolve_todxs_fonts(kb) -> dict:
    """{role: caminho_ttf}. titulo=Ana Banana Black; subtitulo=peso mais leve."""
    from apps.posts.services.font_resolver import _load_custom_font
    fonts = {}
    cfs = list(kb.custom_fonts.all())
    by_name = {c.name.lower(): c for c in cfs}

    def find(*needles):
        for n in needles:
            for name, cf in by_name.items():
                if n in name:
                    return cf
        return None

    black = find('black') or find('bold') or (cfs[0] if cfs else None)
    light = find('medium') or find('regular') or find('semibold') or black
    if black:
        p = _load_custom_font(black)
        if p:
            fonts['titulo'] = p
    if light:
        p = _load_custom_font(light)
        if p:
            fonts['subtitulo'] = p
    return fonts


def resolve_todxs_weights(kb) -> dict:
    """Mapa peso-de-uso -> caminho da fonte (hierarquia tipografica do doc).
    display=Black, medium=Medium, regular=Regular, caps_small=Light (stand-in da
    Vinila Condensed Light ate subirmos a Vinila)."""
    from apps.posts.services.font_resolver import _load_custom_font
    by = {c.name.lower(): c for c in kb.custom_fonts.all()}

    def path(*needles):
        for n in needles:
            for name, cf in by.items():
                if n in name:
                    p = _load_custom_font(cf)
                    if p:
                        return p
        return None

    return {
        'display': path('black', 'bold'),
        'medium': path('medium', 'semibold', 'bold'),
        'regular': path('ana banana regular', 'regular', 'medium'),
        # kicker/tema = Vinila -> stand-in CallingCode (cadastrada na KB)
        'caps_small': path('calling', 'vinila') or path('light', 'extralight'),
    }


def _download_bytes(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception:
        logger.warning('[todxs.pillow] download falhou: %s', (url or '')[:80], exc_info=True)
        return None


def _recolor_opaque(img, rgb):
    """Recolore todos os pixels opacos para `rgb`, preservando o canal alpha."""
    from PIL import Image
    img = img.convert('RGBA')
    alpha = img.split()[3]
    solid = Image.new('RGBA', img.size, rgb + (255,))
    solid.putalpha(alpha)
    return solid


def compose_seal_datauri(x_png_bytes, diameter=420, x_color=_OFFWHITE):
    """Compoe o SELO da marca: circulo PRETO + X (na cor x_color) centrado.
    Retorna data URI (image/png) para usar como sticker editavel."""
    from PIL import Image, ImageDraw
    D = diameter
    seal = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(seal)
    draw.ellipse([0, 0, D - 1, D - 1], fill=(0, 0, 0, 255))
    if x_png_bytes:
        try:
            x = Image.open(io.BytesIO(x_png_bytes)).convert('RGBA')
            x = _recolor_opaque(x, x_color)
            bbox = x.split()[3].getbbox()
            if bbox:
                x = x.crop(bbox)
            target = int(D * 0.56)
            iw, ih = x.size
            scale = min(target / iw, target / ih)
            x = x.resize((max(1, int(iw * scale)), max(1, int(ih * scale))), Image.LANCZOS)
            seal.alpha_composite(x, ((D - x.size[0]) // 2, (D - x.size[1]) // 2))
        except Exception:
            logger.warning('[todxs.pillow] falha ao compor X no selo', exc_info=True)
    buf = io.BytesIO()
    seal.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _cover(img, W, H):
    """Redimensiona (cover) e corta no centro para WxH."""
    from apps.posts.services.artkit.image import cover
    return cover(img.convert('RGB'), W, H)  # todxs: converte RGB antes (historico)


def build_background(archetype, fmt, color_hex, formato_px, photo_png=None):
    """Constroi o fundo (raw): 'solid' = campo de cor; 'photo'/'image' = foto/cena
    do Gemini (cover). Retorna PNG bytes."""
    from PIL import Image, ImageChops
    from .wireframes import background_mode, foto_region, WF
    W, H = _parse_px(formato_px)
    mode = background_mode(archetype)
    img = Image.new('RGB', (W, H), _hex_to_rgb(color_hex))
    if mode in ('photo', 'solid_photo', 'image') and photo_png:
        # Cola a foto na regiao visivel (faixa: topo; frame: miolo) cover-crop.
        fx, fy, fw, fh = foto_region(archetype, fmt, W, H)
        photo = _cover(Image.open(io.BytesIO(photo_png)), fw, fh)
        aw = WF().get(archetype, {})
        if aw.get('grayscale'):                 # foto P&B (arquetipo C)
            photo = photo.convert('L').convert('RGB')
        if aw.get('multiply'):                  # duotone (B_DUO): multiply da cor
            overlay = Image.new('RGB', photo.size, _hex_to_rgb(color_hex))
            photo = ImageChops.multiply(photo.convert('RGB'), overlay)
        img.paste(photo, (fx, fy))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def compose_simbolo_datauri(x_png_bytes, color=_OFFWHITE):
    """SIMBOLO 'bare' (sem circulo): o X recolorido p/ contraste, cortado no bbox."""
    from PIL import Image
    try:
        x = Image.open(io.BytesIO(x_png_bytes)).convert('RGBA')
        x = _recolor_opaque(x, color)
        bbox = x.split()[3].getbbox()
        if bbox:
            x = x.crop(bbox)
    except Exception:
        return None
    buf = io.BytesIO()
    x.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _expand_seals(elements, x_png_bytes):
    """Substitui elementos role='seal' por sticker (data URI): 'circle' = circulo+X,
    'bare' = X recolorido (off-white) sem circulo."""
    out = []
    for el in elements:
        if (el.get('role') or '') == 'seal':
            if not x_png_bytes:
                continue
            if el.get('style') == 'bare':
                uri = compose_simbolo_datauri(x_png_bytes,
                                              color=_hex_to_rgb(el.get('seal_color') or '#F4F1D9'))
            else:
                uri = compose_seal_datauri(x_png_bytes,
                                           x_color=_hex_to_rgb(el.get('seal_color') or '#F4F1D9'))
            if not uri:
                continue
            out.append({
                'role': 'image', 'url': uri,
                'x_pct': el['x_pct'], 'y_pct': el['y_pct'],
                'width_pct': el['width_pct'], 'height_pct': el['width_pct'],
                '_todxs_seal': True,
            })
        else:
            out.append(el)
    return out


# ----------------------------------------------------------------------------
# Desenhador DEDICADO (Pillow puro) — NAO usa o motor do fluxo simples.
# Desenha exatamente o que o layout determinou (posicao/tamanho ja resolvidos).
# ----------------------------------------------------------------------------

def _draw_text_el(draw, el, W, H):
    from PIL import ImageFont
    basis = min(W, H)
    size = max(8, int(float(el.get('font_size_pct', 5)) / 100.0 * basis))
    path = el.get('_font_path')
    try:
        font = ImageFont.truetype(path, size)
    except Exception:
        font = ImageFont.load_default()
    x = float(el.get('x_pct', 0)) / 100.0 * W
    y = float(el.get('y_pct', 0)) / 100.0 * H
    bw = float(el.get('width_pct', 60)) / 100.0 * W
    align = (el.get('align') or 'left').lower()
    color = _hex_to_rgb(el.get('color') or '#000000')
    line_h = size * float(el.get('_leading', 1.16))
    for line in str(el.get('content', '')).split('\n'):
        lw = draw.textlength(line, font=font)
        lx = x + (bw - lw) / 2 if align == 'center' else (x + bw - lw if align == 'right' else x)
        draw.text((lx, y), line, font=font, fill=color)
        y += line_h


def _paste_contain(base, sticker_rgba, el, W, H):
    from PIL import Image
    x = int(float(el.get('x_pct', 0)) / 100.0 * W)
    y = int(float(el.get('y_pct', 0)) / 100.0 * H)
    bw = max(8, int(float(el.get('width_pct', 10)) / 100.0 * W))
    bh = max(8, int(float(el.get('height_pct', el.get('width_pct', 10))) / 100.0 * H))
    iw, ih = sticker_rgba.size
    s = min(bw / iw, bh / ih)
    nw, nh = max(1, int(iw * s)), max(1, int(ih * s))
    sticker_rgba = sticker_rgba.resize((nw, nh), Image.LANCZOS)
    base.alpha_composite(sticker_rgba, (x, y))  # ancora no topo-esquerda do box


def draw_todxs(bg_png, elements, W, H, logo_url=None):
    """Desenha a arte final: faixa -> selo/logo -> texto. Pillow puro.

    O fundo e SEMPRE normalizado para o canvas WxH (cover) — as zonas usam
    coordenadas em % de WxH, entao um fundo de tamanho/aspecto diferente (ex.:
    output do Gemini no regenerate-background) desalinharia tudo. No-op quando o
    fundo ja e WxH (caso da geracao original)."""
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(bg_png))
    if img.size != (W, H):
        img = _cover(img, W, H)
    img = img.convert('RGBA')
    draw = ImageDraw.Draw(img)

    # 1) faixa (grafismo retangulo)
    for el in elements:
        if (el.get('role') or '') == 'grafismo':
            x = int(float(el.get('x_pct', 0)) / 100 * W)
            y = int(float(el.get('y_pct', 0)) / 100 * H)
            w = int(float(el.get('width_pct', 0)) / 100 * W)
            h = int(float(el.get('height_pct', 0)) / 100 * H)
            draw.rectangle([x, y, x + w, y + h],
                           fill=_hex_to_rgb(el.get('cor') or el.get('color') or '#000000'))

    # 2) selo (image data URI) e logo (wordmark PNG)
    for el in elements:
        role = (el.get('role') or '')
        if role == 'image' and (el.get('url') or '').startswith('data:'):
            try:
                _, _, payload = el['url'].partition(',')
                st = Image.open(io.BytesIO(base64.b64decode(payload))).convert('RGBA')
                _paste_contain(img, st, el, W, H)
            except Exception:
                logger.warning('[todxs.draw] selo falhou', exc_info=True)
        elif role == 'logo' and logo_url:
            try:
                lb = _download_bytes(logo_url)
                if lb:
                    logo = Image.open(io.BytesIO(lb)).convert('RGBA')
                    logo = _recolor_opaque(logo, _hex_to_rgb(el.get('logo_color') or '#F4F1D9'))
                    _paste_contain(img, logo, el, W, H)
            except Exception:
                logger.warning('[todxs.draw] logo falhou', exc_info=True)

    # 3) texto (por cima)
    for el in elements:
        if (el.get('role') or '') in ('titulo', 'subtitulo', 'cta') and el.get('content'):
            _draw_text_el(draw, el, W, H)

    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'PNG')
    return buf.getvalue()


def _round_corners(png_bytes, radius, bg=(244, 241, 217)):
    """Arredonda os 4 cantos da arte (moldura), preenchendo o fora com bg."""
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    W, H = img.size
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=radius, fill=255)
    out = Image.new('RGB', (W, H), bg)
    out.paste(img, (0, 0), mask)
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()


def render_todxs(*, archetype, content, color_hex, fmt, formato_px, kb,
                 paleta=None, photo_png=None, x_png_bytes=None, logo_url=None):
    """
    Renderiza a arte final da TODXS via desenhador DEDICADO (Pillow puro).
    Layout 100% explicito (compute_layout) -> sem motor do fluxo simples.
    Retorna dict: {raw_png, final_png, elements, fonts_resolved}.
    """
    from .layout import compute_layout
    from .wireframes import WF

    W, H = _parse_px(formato_px)
    raw_png = build_background(archetype, fmt, color_hex, formato_px, photo_png=photo_png)
    weights = resolve_todxs_weights(kb)
    elements = compute_layout(archetype, content, color_hex, fmt, W, H, weights)
    elements = _expand_seals(elements, x_png_bytes)  # seal -> image (data URI)
    final_png = draw_todxs(raw_png, elements, W, H, logo_url=logo_url)
    # moldura arredondada (ex.: B story)
    rf = (WF().get(archetype, {}).get('rounded_frame', {}) or {}).get(fmt)
    if rf:
        final_png = _round_corners(final_png, int(rf / 100.0 * W))
    return {
        'raw_png': raw_png,
        'final_png': final_png,
        'elements': elements,
        'fonts_resolved': [k for k, v in weights.items() if v],
    }
