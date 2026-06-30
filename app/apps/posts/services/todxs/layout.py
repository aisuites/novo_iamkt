"""
Layout DETERMINISTICO da TODXS — calcula posicao e tamanho EXPLICITOS de cada
caixa de texto (sem depender de auto-fit/flow/contraste do motor generico).

Regra simples (a que voce descreveu):
  para cada caixa de texto:
    - carrega a fonte do peso de uso (Black/Medium/Regular/Light);
    - acha o MAIOR tamanho que faz o texto caber em <= max_linhas dentro da caixa;
    - fixa a posicao (y explicito; 'flow_after' calcula y abaixo da caixa anterior;
      'center_v' centraliza dentro da propria caixa);
    - emite um elemento _layout_elements JA RESOLVIDO (font_size, y, cor, lines).

Como tudo sai explicito, Pillow (publicacao) e o editor desenham igual — sem
gambiarra de background_color nem y falso.
"""
import io

from .wireframes import WF, zones_for, assets_needed


def _lighten(hex_color: str, amt: float = 0.72) -> str:
    """Clareia a cor em direcao ao branco (amt 0..1). Para 'tom claro de destaque'."""
    h = (hex_color or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return '#F4F1D9'
    r = int(r + (255 - r) * amt); g = int(g + (255 - g) * amt); b = int(b + (255 - b) * amt)
    return f'#{r:02X}{g:02X}{b:02X}'


def _contrast_on(hex_color: str) -> str:
    h = (hex_color or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return '#000000'
    return '#000000' if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else '#F4F1D9'


def _greedy_wrap(text, font, max_w, draw):
    out, cur = [], ''
    for w in str(text).split():
        trial = (cur + ' ' + w).strip()
        if not cur or draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or ['']


_LH = 1.16  # entrelinha (igual ao render_layout_document ~1.18, com folga)


def _fit(text, font_path, max_w, max_h, max_lines, start_px, draw, min_px=14, leading=_LH):
    """Maior tamanho que cabe o texto em <= max_lines dentro de (max_w,max_h)."""
    from PIL import ImageFont
    size = max(min_px, int(start_px))
    best = None
    while size >= min_px:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            return None, [str(text)], size, int(size * leading)
        lines = _greedy_wrap(text, font, max_w, draw)
        total_h = int(size * leading * len(lines))
        fits_w = all(draw.textlength(ln, font=font) <= max_w for ln in lines)
        if len(lines) <= max_lines and total_h <= max_h and fits_w:
            return font, lines, size, total_h
        best = (font, lines, size, total_h)
        size -= 2
    return best if best else (None, [str(text)], min_px, int(min_px * leading))


def compute_layout(archetype, content, color_hex, fmt, W, H, weights):
    """Retorna a lista de _layout_elements JA RESOLVIDA (explicita)."""
    from PIL import Image, ImageDraw
    w = WF()[archetype]
    draw = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    basis = min(W, H)
    els = []
    bottoms = {}  # id_da_caixa -> y do fim (em %), p/ flow_after

    # 1) Faixa de cor (B): grafismo retangulo do y% ate o fim.
    band = w.get('band', {}).get(fmt)
    if band:
        els.append({
            'role': 'grafismo', 'forma': 'retangulo', 'cor': color_hex, 'color': color_hex,
            'x_pct': 0, 'y_pct': band['y'], 'width_pct': 100,
            'height_pct': 100 - band['y'], 'raio_pct': 0, 'opacidade': 100,
        })

    # 2) Caixas de texto — fit explicito
    for z in zones_for(archetype, fmt):
        val = content.get(z['key'])
        if not val:
            continue
        items = ([v for v in val if v] if (z.get('is_blocks') and isinstance(val, list))
                 else [' '.join(val) if isinstance(val, list) else val])
        n = len(items) or 1
        # caixa de cada item (blocos dividem a altura igualmente)
        span = z['h'] / n
        for i, raw in enumerate(items):
            box_x = z['x']
            box_w = z['w']
            box_y = (z['y'] + i * span) if z.get('is_blocks') else z['y']
            box_h = span if z.get('is_blocks') else z['h']
            # flow_after: y comeca abaixo do fim da caixa anterior
            if z.get('flow_after') and z['flow_after'] in bottoms:
                box_y = bottoms[z['flow_after']] + z.get('gap_pct', 1.5)
                box_h = max(6.0, (z.get('y_max', 96) - box_y))
            text = str(raw).replace('\\n', ' ')
            text = ' '.join(text.split())
            if z.get('caps'):
                text = text.upper()
            font_path = weights.get(z['font'])
            leading = float(z.get('leading', _LH))
            max_w_px = box_w / 100.0 * W
            max_h_px = box_h / 100.0 * H
            start_px = z['fs'] / 100.0 * basis
            max_lines = z.get('max_linhas', 4)
            if z.get('fixed_fs'):
                # tamanho TRAVADO: usa o fs exato (nao encolhe) -> consistente
                # entre posts, independente do texto. So quebra em linhas.
                from PIL import ImageFont
                try:
                    font = ImageFont.truetype(font_path, max(8, int(start_px)))
                except Exception:
                    font = None
                lines = _greedy_wrap(text, font, max_w_px, draw)[:max_lines] if font else [text]
                size_px = int(start_px)
                total_h_px = int(size_px * leading * len(lines))
            else:
                font, lines, size_px, total_h_px = _fit(
                    text, font_path, max_w_px, max_h_px, max_lines, start_px, draw, leading=leading)
            total_h_pct = total_h_px / H * 100.0
            # valign: center_v centraliza dentro da caixa; senao topo
            draw_y = box_y + (box_h - total_h_pct) / 2.0 if z.get('center_v') else box_y
            zc = z['color']
            if zc == 'ACCENT_LIGHT':
                color = _lighten(color_hex, 0.72)
            elif zc == 'ACCENT':
                color = color_hex
            elif zc:
                color = zc
            else:
                color = _contrast_on(color_hex)
            els.append({
                'role': z['role'],
                'content': '\n'.join(lines),
                'x_pct': box_x, 'y_pct': round(draw_y, 2), 'width_pct': box_w,
                'height_pct': round(total_h_pct + 0.5, 2),
                'font_size_pct': round(size_px / basis * 100.0, 3),
                'weight': 'black' if z['role'] == 'titulo' else 'regular',
                'case': 'none', 'align': z['align'], 'color': color,
                '_font_path': font_path, '_leading': leading,
                'font_key': z['font'],  # editor carrega a fonte real por chave
            })
            bottoms[z['key']] = draw_y + total_h_pct

    # 3) Selo (circulo + X) e wordmark (logo) — marcadores explicitos
    need = assets_needed(archetype, fmt)
    seal = w.get('seal', {}).get(fmt)
    if need['selo'] and seal:
        sc = w.get('seal_color')
        if sc == 'ACCENT':
            sc = color_hex
        els.append({'role': 'seal', 'x_pct': seal['x'], 'y_pct': seal['y'],
                    'width_pct': seal['w'], 'style': w.get('seal_style', 'circle'),
                    'seal_color': sc})
    wm = w.get('wordmark', {}).get(fmt)
    if need['wordmark'] and wm:
        band = w.get('band', {}).get(fmt)
        over_faixa = bool(band) and wm['y'] >= band['y']  # wordmark na faixa -> contraste
        if w.get('wordmark_color'):
            logo_color = w.get('wordmark_color')
        elif over_faixa or w.get('fundo') == 'solid':
            logo_color = _contrast_on(color_hex)
        else:
            logo_color = '#F4F1D9'   # sobre a foto
        els.append({'role': 'logo', 'x_pct': wm['x'], 'y_pct': wm['y'],
                    'width_pct': wm['w'], 'logo_color': logo_color})

    return els
