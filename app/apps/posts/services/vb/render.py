"""
Motor de render DETERMINISTICO da VB Gastronomia (Pillow puro).

Lê a ficha do arquetipo (specs.SPECS) e compõe a arte: fundo (sólido/foto/
emoldurada) + texto (Barlow Condensed, stand-in da Acumin) + ILUSTRAÇÃO (skill de
ilustração, relacionada ao tema) + grafismos + logo. 100% isolado da TODXS.

render_vb(archetype, content, color_hex, fmt, kb, photo_png) -> {raw_png, final_png}
"""
import io
import os
import importlib.util

from PIL import Image, ImageDraw, ImageFont

from .specs import PALETTE

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS = os.path.join(_HERE, 'fonts')
_FONT_FILES = {
    'light': 'BarlowCondensed-Light.ttf',
    'medium': 'BarlowCondensed-Medium.ttf',
    'semibold': 'BarlowCondensed-SemiBold.ttf',
}
_LOGO_NAMES = {
    'horizontal': 'VB Logo Horizontal (Preto)',
    'vertical': 'VB Logo Vertical (Preto)',
    'simbolo': 'VB Simbolo (Preto)',
}

# compositor de ilustração da skill (vb/illustration/scripts/illustrate.py)
_ILLU_PATH = os.path.join(_HERE, 'illustration', 'scripts', 'illustrate.py')


def _load_illustrate():
    spec = importlib.util.spec_from_file_location('vb_illustrate', _ILLU_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- helpers

def _rgb(token_or_hex):
    from apps.posts.services.artkit.image import hex_to_rgb
    return hex_to_rgb(PALETTE.get(token_or_hex, token_or_hex))


def _font(font_key, fs):
    return ImageFont.truetype(os.path.join(_FONTS, _FONT_FILES[font_key]), int(fs))


def _lum(rgb):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(rgb1, rgb2):
    l1, l2 = _lum(rgb1), _lum(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _ensure_contrast(color_token_or_hex, bg_hex):
    """Garante contraste do TEXTO sobre o fundo escolhido. Se a cor do texto
    colide com o fundo (ex.: usuario escolheu oliva e o apoio tambem e oliva),
    troca por uma cor da paleta que contrasta (creme em fundo escuro, vinho em
    fundo claro). Retorna SEMPRE um hex."""
    tc, bgc = _rgb(color_token_or_hex), _rgb(bg_hex)
    if _contrast(tc, bgc) >= 2.2:
        return PALETTE.get(color_token_or_hex, color_token_or_hex)
    return PALETTE['creme'] if _lum(bgc) < 0.4 else PALETTE['vinho']


def _wrap(draw, text, font, max_w):
    from apps.posts.services.artkit.text import wrap_greedy
    return wrap_greedy(text, font, max_w, draw)


def _draw_zone(img, draw, text, z):
    if not text:
        return
    if z.get('case') == 'upper':
        text = str(text).upper()
    font = _font(z['font'], z['fs'])
    color = _rgb(z['color']) + (255,)
    leading = float(z.get('leading', 1.1))
    lines = _wrap(draw, text, font, z['w'])[:z.get('max_linhas', 6)]
    align = z.get('align', 'left')
    cy = z['y']
    for ln in lines:
        x = z['x']
        if align in ('right', 'center'):
            tw = draw.textlength(ln, font=font)
            x = z['x'] + (z['w'] - tw) * (1.0 if align == 'right' else 0.5)
        draw.text((x, cy), ln, font=font, fill=color)
        cy += int(z['fs'] * leading)


def _s3_bytes(kb, s3_key):
    import urllib.request
    from apps.core.services.s3_service import S3Service
    url = S3Service.generate_presigned_download_url(s3_key, expires_in=300)
    return urllib.request.urlopen(url, timeout=60).read()


def _logo_img(kb, asset, color):
    name = _LOGO_NAMES.get(asset, _LOGO_NAMES['horizontal'])
    lg = kb.logos.filter(name=name).first() or kb.logos.filter(is_primary=True).first()
    im = Image.open(io.BytesIO(_s3_bytes(kb, lg.s3_key))).convert('RGBA')
    if color:
        r, g, b = _rgb(color)
        solid = Image.new('RGBA', im.size, (r, g, b, 255))
        solid.putalpha(im.split()[3])
        im = solid
    return im


def _composite_bleed(base, layer, x, y):
    """Compoe `layer` (RGBA) sobre `base` (RGBA) em (x,y) aceitando offset NEGATIVO
    e transbordo (bleed): recorta a interseção e faz alpha_composite só nela.
    Para elementos 100% dentro da arte, é idêntico a alpha_composite."""
    x, y = int(x), int(y)
    bw, bh = base.size
    lw, lh = layer.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(bw, x + lw), min(bh, y + lh)
    if x1 <= x0 or y1 <= y0:
        return
    crop = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    region = Image.alpha_composite(base.crop((x0, y0, x1, y1)), crop)
    base.paste(region, (x0, y0))


def _paste_fit(img, a, x, y, w, h=None, fit='width'):
    if h is None:
        s = w / a.width
    elif fit == 'height':
        s = h / a.height
    elif fit == 'width':
        s = w / a.width
    else:  # contain
        s = min(w / a.width, h / a.height)
    nw, nh = max(1, int(a.width * s)), max(1, int(a.height * s))
    a = a.resize((nw, nh), Image.LANCZOS)
    # centraliza dentro da caixa (quando h dado)
    ox = x + (int((w - nw) / 2) if (w and nw < w) else 0)
    oy = y + (int(((h or nh) - nh) / 2) if (h and nh < h) else 0)
    _composite_bleed(img, a, ox, oy)


def _cover(im, W, H):
    from apps.posts.services.artkit.image import cover
    return cover(im, W, H)  # int() historico (todxs/vb)


_GRAF_DIR = os.path.join(_HERE, 'illustration', 'assets', 'grafismos', 'oficiais')


def _load_stamps():
    """Carrega os carimbos oficiais (PNG mono c/ alpha) recoloríveis."""
    out = []
    try:
        for f in sorted(os.listdir(_GRAF_DIR)):
            if f.lower().endswith('.png'):
                out.append(Image.open(os.path.join(_GRAF_DIR, f)).convert('RGBA'))
    except Exception:
        pass
    return out


def _recolor(stamp, cor):
    r, g, b = _rgb(cor)
    solid = Image.new('RGBA', stamp.size, (r, g, b, 255))
    solid.putalpha(stamp.split()[3])
    return solid


def _grafismo_grid(grid_spec, W_box, H_box, seed=0):
    """Padrão de rodapé = grid de carimbos (5x5). Algoritmo: 3 cores base + 1 de
    destaque (apenas 1 célula, no miolo 3x3). Carimbos direto sobre a cor da peça
    (sem fundo). Determinístico por `seed` (reproduzível no save)."""
    import random as _rnd
    rng = _rnd.Random(seed)
    cols, rows = grid_spec.get('grid', [5, 5])
    cores = grid_spec.get('cores') or [c for c in PALETTE if c not in ('terracota', 'creme')]
    pad = float(grid_spec.get('pad', 0.16))
    stamps = _load_stamps()
    canvas = Image.new('RGBA', (int(W_box), int(H_box)), (0, 0, 0, 0))
    if not stamps:
        return canvas
    cw, ch = W_box / cols, H_box / rows
    base = rng.sample(cores, min(3, len(cores)))
    dest_spec = grid_spec.get('destaque')
    if dest_spec:
        destaque = dest_spec
    else:
        resto = [c for c in cores if c not in base]
        destaque = rng.choice(resto) if resto else base[0]
    dcol = rng.randint(1, cols - 2) if cols > 2 else 0
    drow = rng.randint(1, rows - 2) if rows > 2 else 0
    for lin in range(rows):
        for col in range(cols):
            st = rng.choice(stamps)
            cor = destaque if (col == dcol and lin == drow) else rng.choice(base)
            piece = _recolor(st, cor)
            # carimbos alongados tendem a deitar (horizontais), como na referência
            asp = st.height / max(1, st.width)
            if asp > 1.15 and rng.random() < 0.75:
                piece = piece.rotate(90, expand=True, resample=Image.BICUBIC)
            elif rng.random() < 0.15:
                piece = piece.rotate(rng.choice([90, -90]), expand=True, resample=Image.BICUBIC)
            maxw, maxh = cw * (1 - pad * 2), ch * (1 - pad * 2)
            s = min(maxw / piece.width, maxh / piece.height)
            nw, nh = max(1, int(piece.width * s)), max(1, int(piece.height * s))
            piece = piece.resize((nw, nh), Image.LANCZOS)
            ox = int(col * cw + (cw - nw) / 2)
            oy = int(lin * ch + (ch - nh) / 2)
            canvas.alpha_composite(piece, (ox, oy))
    return canvas


def _fix_recipe_contrast(recipe, bg_value):
    """Guardrail: peça da ilustração na COR DO FUNDO fica invisível — remapeia
    para a primeira cor de contraste da paleta. Determinístico (independe do brain)."""
    try:
        bgc = _rgb(bg_value)
    except Exception:
        return recipe
    prefer = ['terracota', 'laranja', 'vinho', 'creme', 'amarelo', 'preto']
    repl = next((c for c in prefer if _rgb(c) != bgc), 'creme')
    changed = 0
    for p in (recipe or {}).get('pecas') or []:
        try:
            if _rgb(p.get('cor')) == bgc:
                p['cor'] = repl
                changed += 1
        except Exception:
            continue
    if changed:
        logger.warning('[vb] ilustracao: %s peca(s) na cor do fundo remapeada(s) p/ %s',
                       changed, repl)
    return recipe


def _illustration(recipe, W, H):
    """Renderiza a ilustração (skill) a partir da receita -> Image RGBA WxH-canvas."""
    illu = _load_illustrate()
    rec = dict(recipe or {})
    rec['bg'] = 'transparent'
    import tempfile
    tmp = tempfile.mktemp(suffix='.png')
    illu.render(rec, tmp)
    im = Image.open(tmp).convert('RGBA')
    try:
        os.remove(tmp)
    except Exception:
        pass
    return im


# ------------------------------------------------ elementos editáveis (texto)

def _font_path(font_key):
    return os.path.join(_FONTS, _FONT_FILES.get(font_key, _FONT_FILES['light']))


# Mapa zona->role reconhecido pelo editor (titulo/subtitulo/cta). O editor so
# renderiza/edita esses roles; a fonte/posicao continua por elemento (font_key).
_EDITOR_ROLE = {'titulo': 'titulo', 'apoio': 'subtitulo', 'cta': 'cta',
                'kicker': 'subtitulo', 'manifesto': 'subtitulo', 'handle': 'subtitulo'}


def build_text_elements(spec, content, W, H):
    """Constrói os _layout_elements de TEXTO (mesma convenção do editor: posição
    em %, font_size_pct relativo a min(W,H), fonte por elemento)."""
    draw0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    basis = min(W, H)
    els = []
    for z in spec.get('zones', []):
        if z.get('rot'):
            continue  # zonas rotacionadas viram elemento de imagem (render_vb)
        text = content.get(z['key'])
        if not text:
            continue
        if z.get('case') == 'upper':
            text = str(text).upper()
        font = _font(z['font'], z['fs'])
        lines = _wrap(draw0, text, font, z['w'])[:z.get('max_linhas', 6)]
        els.append({
            'role': _EDITOR_ROLE.get(z['key'], 'subtitulo'), 'zone': z['key'],
            'content': '\n'.join(lines),
            'x_pct': round(z['x'] / W * 100, 3), 'y_pct': round(z['y'] / H * 100, 3),
            'width_pct': round(z['w'] / W * 100, 3), 'height_pct': round(z['h'] / H * 100, 3),
            'font_size_pct': round(z['fs'] / basis * 100, 4),
            'color': PALETTE.get(z['color'], z['color']),
            'font_key': z['font'], '_leading': float(z.get('leading', 1.1)),
            '_font_path': _font_path(z['font']),
            'align': z.get('align', 'left'),
        })
    return els


def draw_vb_text(img, elements, W, H):
    """Desenha os elementos de texto sobre a imagem (mesma convenção do editor)."""
    draw = ImageDraw.Draw(img)
    basis = min(W, H)
    for el in elements:
        if (el.get('role') or '') in ('grafismo', 'seal', 'logo', 'image'):
            continue
        if el.get('visible') is False:
            continue
        size = max(8, int(float(el.get('font_size_pct', 5)) / 100.0 * basis))
        try:
            font = ImageFont.truetype(el.get('_font_path') or _font_path(el.get('font_key')), size)
        except Exception:
            font = ImageFont.load_default()
        # Texto VERTICAL (rotacionado): rasteriza as linhas (exatas do editor) e cola
        rot = int(el.get('_rot') or 0)
        if rot:
            x = float(el.get('x_pct', 0)) / 100.0 * W
            y = float(el.get('y_pct', 0)) / 100.0 * H
            leading = float(el.get('_leading', 1.1))
            lines = str(el.get('content', '')).split('\n')
            line_h = max(1, int(size * leading))
            d0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
            maxw = max((int(d0.textlength(ln, font=font)) for ln in lines), default=1)
            layer = Image.new('RGBA', (max(1, maxw), line_h * len(lines)), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            col = _rgb(el.get('color') or '#000000') + (255,)
            cy = 0
            for ln in lines:
                ld.text((0, cy), ln, font=font, fill=col); cy += line_h
            layer = layer.rotate(rot, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(layer, (int(x), int(y)))
            continue
        x = float(el.get('x_pct', 0)) / 100.0 * W
        y = float(el.get('y_pct', 0)) / 100.0 * H
        bw = float(el.get('width_pct', 60)) / 100.0 * W
        align = (el.get('align') or 'left').lower()
        color = _rgb(el.get('color') or '#000000') + (255,)
        line_h = size * float(el.get('_leading', 1.16))
        for line in str(el.get('content', '')).split('\n'):
            lw = draw.textlength(line, font=font)
            lx = x + (bw - lw) / 2 if align == 'center' else (x + bw - lw if align == 'right' else x)
            draw.text((lx, y), line, font=font, fill=color)
            y += line_h
    return img


# ---------------------------------------------------------------- render

def _img_el(subrole, pil_img, x, y, w, h, W, H, fit='contain'):
    """Elemento de IMAGEM editavel (role='image' do editor), PNG embutido em data URI."""
    import base64
    buf = io.BytesIO(); pil_img.convert('RGBA').save(buf, 'PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return {
        'role': 'image', 'subrole': subrole,
        'url': 'data:image/png;base64,' + b64,
        'x_pct': round(x / W * 100, 3), 'y_pct': round(y / H * 100, 3),
        'width_pct': round(w / W * 100, 3), 'height_pct': round(h / H * 100, 3),
        '_fit': fit,
    }


def _emit_within_bounds(elements, subrole, img, gx, gy, gw, gh, W, H):
    """Emite uma imagem possivelmente SANGRANTE (bleed) como elemento DENTRO DOS
    LIMITES do canvas: recorta o excedente na própria imagem e posiciona na área
    visível. Garante que o editor (overlay em %) bata com o publicado (Pillow)."""
    gx, gy = int(gx), int(gy)
    vx0, vy0 = max(0, gx), max(0, gy)
    vx1, vy1 = min(W, gx + int(gw)), min(H, gy + int(gh))
    if vx1 <= vx0 or vy1 <= vy0:
        return
    crop = img.crop((vx0 - gx, vy0 - gy, vx1 - gx, vy1 - gy))
    elements.append(_img_el(subrole, crop, vx0, vy0, vx1 - vx0, vy1 - vy0, W, H, 'contain'))


def draw_vb_compose(base, elements, W, H):
    """Compoe a arte: pinta os elementos de IMAGEM (na ordem) e desenha o TEXTO."""
    import base64
    for el in elements:
        if (el.get('role') or '').lower() != 'image':
            continue
        url = el.get('url') or ''
        if not url.startswith('data:'):
            continue
        try:
            payload = url.split(',', 1)[1]
            im = Image.open(io.BytesIO(base64.b64decode(payload))).convert('RGBA')
            x = float(el.get('x_pct', 0)) / 100.0 * W
            y = float(el.get('y_pct', 0)) / 100.0 * H
            w = float(el.get('width_pct', 10)) / 100.0 * W
            h = float(el.get('height_pct', 10)) / 100.0 * H
            _paste_fit(base, im, x, y, w, h, fit=el.get('_fit', 'contain'))
        except Exception:
            pass
    draw_vb_text(base, elements, W, H)
    return base


def _rotated_text_img(text, font_key, fs, color, box_w, box_h, rot, leading=1.1, max_linhas=2):
    """Renderiza o texto (quebrado no eixo LONGO) e rotaciona -> PIL RGBA."""
    long_dim = box_h if rot in (90, 270) else box_w
    font = _font(font_key, fs)
    draw0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    lines = _wrap(draw0, str(text), font, long_dim)[:max_linhas]
    line_h = max(1, int(fs * leading))
    # largura JUSTA = maior linha real (sem sobra) -> texto rotacionado fica
    # do tamanho exato do conteudo (posicionamento preciso).
    maxw = max((int(draw0.textlength(ln, font=font)) for ln in lines), default=1)
    layer = Image.new('RGBA', (max(1, maxw), line_h * len(lines)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = 0
    for ln in lines:
        d.text((0, cy), ln, font=font, fill=_rgb(color) + (255,))
        cy += line_h
    return layer.rotate(rot, expand=True, resample=Image.BICUBIC)


def render_vb(archetype, content, color_hex=None, fmt='feed', kb=None, photo_png=None):
    from .specs import SP
    spec = SP()[archetype]
    W, H = spec['canvas']

    # 1) Fundo — o RAW é SÓ o fundo; todo o resto vira elemento editável.
    bg = spec['bg']
    if bg['type'] == 'solid':
        base = Image.new('RGBA', (W, H), _rgb(color_hex or bg['color']) + (255,))
    elif bg['type'] in ('photo',) and photo_png:
        base = _cover(Image.open(io.BytesIO(photo_png)).convert('RGBA'), W, H)
    else:
        base = Image.new('RGBA', (W, H), _rgb(bg.get('color', 'creme')) + (255,))
    raw = base.copy()

    elements = []

    # 1b) Foto EMOLDURADA (retângulo de foto sobre o fundo) — elemento editável
    ff = spec.get('foto_frame')
    if ff and photo_png:
        try:
            photo = _cover(Image.open(io.BytesIO(photo_png)).convert('RGBA'), ff['w'], ff['h'])
            elements.append(_img_el('foto', photo, ff['x'], ff['y'], ff['w'], ff['h'], W, H, 'contain'))
        except Exception:
            pass

    # 2) Ilustração (zona reservada) — relacionada ao tema
    izone = spec.get('ilustracao')
    if izone and content.get('ilustracao'):
        try:
            _bg_val = color_hex or (bg.get('color') if bg.get('type') == 'solid' else None)
            recipe = (_fix_recipe_contrast(content['ilustracao'], _bg_val)
                      if _bg_val else content['ilustracao'])
            im = _illustration(recipe, izone['w'], izone['h'])
            elements.append(_img_el('ilustracao', im, izone['x'], izone['y'],
                                    izone['w'], izone['h'], W, H, izone.get('fit', 'contain')))
        except Exception:
            pass

    # 3) Cluster de grafismos (pode sangrar -> recorta p/ dentro dos limites)
    gc = spec.get('grafismo_cluster')
    if gc and gc.get('recipe'):
        try:
            box = gc['box']
            im = _illustration(gc['recipe'], box['w'], box['h'])
            _emit_within_bounds(elements, 'grafismo', im, box['x'], box['y'],
                                box['w'], box['h'], W, H)
        except Exception:
            pass

    # 3b) Faixa de grafismos (grid de carimbos) — rodapé.
    #     O grid pode "sangrar" (x negativo / largura > canvas). Em vez de guardar
    #     o elemento sangrando (o que descompassa no editor), recortamos o bleed
    #     JÁ NA IMAGEM e emitimos um elemento DENTRO DOS LIMITES -> editor == publicado.
    gg = spec.get('grafismo_grid')
    if gg:
        try:
            import zlib
            seed = zlib.crc32((str(content.get('titulo') or '') + str(archetype)).encode('utf-8'))
            full = _grafismo_grid(gg, gg['w'], gg['h'], seed=seed)
            _emit_within_bounds(elements, 'grafismo_grid', full, gg['x'], gg['y'],
                                gg['w'], gg['h'], W, H)
        except Exception:
            pass

    # 4) Logo / símbolo
    lg = spec.get('logo')
    if lg:
        try:
            im = _logo_img(kb, lg['asset'], lg.get('color'))
            bw = lg['w']
            bh = lg.get('h') or int(lg['w'] * im.height / im.width)
            if lg.get('left_margin_w') is not None:
                # ALINHADO À ESQUERDA: margem esq = left_margin_w * largura do logo;
                # emite no tamanho exato (sem centralizar no box) e centra na vertical.
                s = min(bw / im.width, bh / im.height)
                nw, nh = max(1, int(im.width * s)), max(1, int(im.height * s))
                ex = int(lg['left_margin_w'] * nw)
                ey = lg['y'] + int((bh - nh) / 2)
                elements.append(_img_el('logo', im, ex, ey, nw, nh, W, H, 'contain'))
            else:
                elements.append(_img_el('logo', im, lg['x'], lg['y'], bw, bh, W, H,
                                        lg.get('fit', 'contain')))
        except Exception:
            pass

    # cor sólida efetiva do fundo (p/ guarda de contraste do texto)
    solid_bg_hex = None
    if bg['type'] == 'solid':
        _b = color_hex or bg['color']
        solid_bg_hex = PALETTE.get(_b, _b)

    # 5) Texto (editável)
    txt_els = build_text_elements(spec, content, W, H)
    if solid_bg_hex:
        for el in txt_els:
            if el.get('color'):
                el['color'] = _ensure_contrast(el['color'], solid_bg_hex)
    # zonas que SEGUEM outra: reposiciona logo abaixo do TEXTO REAL da zona-ref
    # (ex.: apoio sobe e acompanha o nº de linhas do título).
    _basis = min(W, H)
    _by_zone = {e.get('zone'): e for e in txt_els}
    for z in spec.get('zones', []):
        fz = z.get('follow_zone')
        me, ref = _by_zone.get(z.get('key')), _by_zone.get(fz) if fz else None
        if not (fz and me and ref):
            continue
        ref_lines = str(ref.get('content') or '').count('\n') + 1
        ref_lh = (float(ref.get('font_size_pct', 5)) / 100 * _basis) * float(ref.get('_leading', 1.1))
        ref_bottom = (float(ref.get('y_pct', 0)) / 100 * H) + ref_lines * ref_lh
        me['y_pct'] = round((ref_bottom + z.get('follow_gap', 50)) / H * 100, 3)
    elements += txt_els

    # 5b) Texto VERTICAL (rotacionado) -> elemento de TEXTO EDITAVEL (rotation).
    #     Rasteriza apenas p/ MEDIR o bbox; no editor continua texto (editavel) e
    #     e re-desenhado rotacionado por draw_vb_text no save/export.
    for z in spec.get('zones', []):
        if not z.get('rot') or not content.get(z['key']):
            continue
        try:
            txt = content[z['key']]
            if z.get('case') == 'upper':
                txt = str(txt).upper()
            rot_color = _ensure_contrast(z['color'], solid_bg_hex) if solid_bg_hex else z['color']
            font = _font(z['font'], z['fs'])
            draw0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
            long_dim = z['h'] if z['rot'] in (90, 270) else z['w']
            lines = _wrap(draw0, str(txt), font, long_dim)[:z.get('max_linhas', 2)]
            leading = float(z.get('leading', 1.1))
            line_h = max(1, int(z['fs'] * leading))
            maxw = max((int(draw0.textlength(ln, font=font)) for ln in lines), default=1)
            # bbox NA TELA (rot 90/270 trocam eixos): largura=pilha de linhas; altura=comprimento do texto
            bw, bh = line_h * len(lines), maxw
            gc = spec.get('grafismo_cluster')
            if z.get('above_grafismo') and gc:
                gb = gc['box']; gcx = gb['x'] + gb['w'] / 2.0
                ex = int(gcx - bw / 2.0); ey = int(gb['y'] - 25 - bh)
            elif z.get('center_to_grafismo') and gc:
                gb = gc['box']; ex = z['x']; ey = int((gb['y'] + gb['h'] / 2.0) - bh / 2.0)
            else:
                ex, ey = z['x'], z['y']
            elements.append({
                'role': _EDITOR_ROLE.get(z['key'], 'subtitulo'), 'zone': z['key'],
                'content': '\n'.join(lines),
                'x_pct': round(ex / W * 100, 3), 'y_pct': round(ey / H * 100, 3),
                'width_pct': round(bw / W * 100, 3), 'height_pct': round(bh / H * 100, 3),
                'font_size_pct': round(z['fs'] / min(W, H) * 100, 4),
                'color': PALETTE.get(rot_color, rot_color),
                'font_key': z['font'], '_leading': leading,
                '_font_path': _font_path(z['font']), 'align': z.get('align', 'left'),
                'rotation': -90 if z['rot'] == 90 else (90 if z['rot'] == 270 else 0),
                '_rot': z['rot'], '_max_linhas': z.get('max_linhas', 2),
            })
        except Exception:
            pass

    final = raw.copy()
    draw_vb_compose(final, elements, W, H)

    raw_png = io.BytesIO(); raw.convert('RGB').save(raw_png, 'PNG')
    final_png = io.BytesIO(); final.convert('RGB').save(final_png, 'PNG')
    return {'raw_png': raw_png.getvalue(), 'final_png': final_png.getvalue(),
            'elements': elements, 'archetype': archetype, 'canvas': [W, H]}
