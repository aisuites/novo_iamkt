"""Primitivas de imagem compartilhadas (origem: todxs/vb/samsung renders)."""
from PIL import Image


def hex_to_rgb(h, fallback=(0, 0, 0)):
    """'#RGB'/'#RRGGBB' -> (r,g,b). Robusta: 3-char expande, invalido -> fallback.
    (Comportamento do todxs._hex_to_rgb — superset dos _rgb/_hex2rgb de vb/samsung,
    que so recebiam hex de 6 chars validos.)"""
    h = (h or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def cover(img, w, h, rounding=int):
    """Redimensiona (cover) e corta no centro para (w,h).

    `rounding`: diferenca HISTORICA entre pipelines — todxs/vb usam int()
    (trunca), samsung usa round(). Em escalas fracionarias isso muda 1px do
    tamanho intermediario. Unificar = Fase 2 (com re-gravacao de goldens).
    """
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = max(1, rounding(iw * scale)), max(1, rounding(ih * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def contain(img, w, h):
    """Redimensiona preservando proporcao para caber em (w,h). (samsung)"""
    iw, ih = img.size
    scale = min(w / iw, h / ih)
    return img.resize((max(1, round(iw * scale)), max(1, round(ih * scale))), Image.LANCZOS)


def recolor_opaque(img, rgb):
    """Recolore todos os pixels opacos para `rgb`, preservando o canal alpha.
    (Comportamento exato do todxs._recolor_opaque == vb._recolor.)"""
    img = img.convert('RGBA')
    alpha = img.split()[3]
    solid = Image.new('RGBA', img.size, tuple(rgb) + (255,))
    solid.putalpha(alpha)
    return solid
