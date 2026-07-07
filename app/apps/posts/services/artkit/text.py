"""Primitivas de texto compartilhadas (origem: todxs/layout e vb/render)."""


def wrap_greedy(text, font, max_w, draw):
    """Quebra gulosa por palavra; retorna [''] para texto vazio.
    (Comportamento exato de todxs._greedy_wrap == vb._wrap. O _wrap do samsung
    difere no caso vazio ([]) e permanece local ate a Fase 2.)"""
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


def contrast_on(hex_color, dark='#000000', light='#F4F1D9', threshold=150):
    """Preto ou off-white conforme a luminancia do fundo. (todxs, 2 copias unificadas)"""
    h = (hex_color or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return dark
    return dark if (0.299 * r + 0.587 * g + 0.114 * b) > threshold else light
