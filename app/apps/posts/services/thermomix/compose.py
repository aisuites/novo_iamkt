"""
Compose do editor avancado da thermomix: redesenha os ELEMENTOS editados sobre
o fundo raw (mesmo desenhador do publicado — engine.draw_layout_elements —
=> editor == publicado por construcao, incluindo spans e grafismo pill/circulo).
"""


def draw_thermomix_compose(base, elements, W, H, kb, archetype=None):
    """Desenha os elementos sobre `base` (RGBA). Re-resolve os paths de fonte
    por font_key (o front so conhece as keys)."""
    from apps.posts.services.artkit.engine import draw_layout_elements
    from .wireframes import WF
    from .assets import font_paths

    spec = WF().get(archetype) or next(iter(WF().values()))
    paths = font_paths(kb, spec.get('fonts') or {})

    els = []
    for el in elements:
        el = dict(el)
        fk = el.get('font_key')
        if fk:
            el['_font_path'] = paths.get(fk) or el.get('_font_path')
            bk = el.get('font_key_bold') or f'{fk}_bold'
            el['_font_path_bold'] = (paths.get(bk) or el.get('_font_path_bold')
                                     or el['_font_path'])
        els.append(el)
    draw_layout_elements(base, els, {'assets': {}}, W, H)
    return base
