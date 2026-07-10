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


def shrink_for_ai(data, mime='', max_bytes=4_500_000, max_dim=2200):
    """Compacta uma imagem para ENVIO A IAs (Claude/Gemini) sem tocar o
    original no S3.

    Regra (dono, 2026-07-08): o upload aceita ate 15MB; a compactacao acontece
    SO na hora de mandar para a IA (o render Pillow usa o original integro).
    - <= max_bytes: retorna intacto (bytes, mime).
    - com alpha: re-encode PNG (preserva transparencia — logos/produtos),
      reduzindo dimensao se preciso.
    - sem alpha: JPEG com qualidade decrescente ate caber.
    max_bytes default 4.5MB (limite de 5MB/imagem do Claude; seguro p/ Gemini).
    """
    if not data or len(data) <= max_bytes:
        return data, mime
    import io
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return data, mime
    if max(img.size) > max_dim:
        s = max_dim / max(img.size)
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))),
                         Image.LANCZOS)
    has_alpha = (img.mode in ('RGBA', 'LA')
                 or (img.mode == 'P' and 'transparency' in img.info))
    if has_alpha:
        img = img.convert('RGBA')
        buf = io.BytesIO()
        img.save(buf, 'PNG', optimize=True)
        out = buf.getvalue()
        while len(out) > max_bytes and max(img.size) > 800:
            img = img.resize((max(1, int(img.width * 0.8)),
                              max(1, int(img.height * 0.8))), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, 'PNG', optimize=True)
            out = buf.getvalue()
        return out, 'image/png'
    img = img.convert('RGB')
    out = data
    for q in (85, 75, 65, 55, 45):
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=q, optimize=True)
        out = buf.getvalue()
        if len(out) <= max_bytes:
            break
    return out, 'image/jpeg'


def duotone_bytes(png_bytes, hex_color):
    """Duotone monocromatico: P&B -> multiply na cor. Usado quando a foto e
    do USUARIO e o arquetipo pedia duotone via prompt do Gemini (gemini_duotone
    — ex.: todxs B_DUO): o tratamento que o Gemini faria vira Pillow."""
    import io
    from PIL import ImageChops
    img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    gray = img.convert('L').convert('RGB')
    overlay = Image.new('RGB', gray.size, hex_to_rgb(hex_color))
    out = ImageChops.multiply(gray, overlay)
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()


def recolor_opaque(img, rgb):
    """Recolore todos os pixels opacos para `rgb`, preservando o canal alpha.
    (Comportamento exato do todxs._recolor_opaque == vb._recolor.)"""
    img = img.convert('RGBA')
    alpha = img.split()[3]
    solid = Image.new('RGBA', img.size, tuple(rgb) + (255,))
    solid.putalpha(alpha)
    return solid
