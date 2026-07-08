"""
Conversores v2 -> spec v3 (Fase 2.2). Um por dialeto de origem; rodados uma vez
na migracao (a spec v3 vira a fonte no PostArchetype). Fidelidade: os numeros
VALIDADOS entram intactos (samsung/vb em px; todxs em pct).
"""


def samsung_to_v3(key: str, src: dict = None) -> dict:
    """Converte uma spec samsung v2 para v3 (units=px).

    `src` opcional: a spec v2 ATIVA (ex.: WF()[key], banco-sobre-código) para
    conversão ON-THE-FLY no runtime — o banco continua v2/editável e o engine
    recebe v3; rollback = desligar a flag. Default: WIREFRAMES do código."""
    from apps.posts.services.samsung.wireframes import WIREFRAMES, TOKENS, FONT_FILES
    src = src or WIREFRAMES[key]
    if src.get('spec_version') == 3:   # já é v3 (futuro: banco nativo v3)
        return src

    spec = {
        'spec_version': 3,
        'name': src.get('name') or key,
        'canvas': [1080, 1350],
        'units': 'px',
        'formats': list(src.get('formatos') or ['feed']),
        'tokens': dict(TOKENS),
        'fonts': dict(FONT_FILES),
        'background': dict(src.get('background') or {'type': 'solid', 'color': 'black'}),
        'zones': [],
        'effects': [],
    }
    if src.get('use'):
        spec['use'] = src['use']

    # scrim: so quando a foto ocupa o fundo inteiro (comportamento historico).
    if src.get('scrim'):
        spec['effects'].append({'name': 'scrim', 'layer': 'bg',
                                'only_if': 'background_image', **src['scrim']})
    if src.get('guide_line'):
        spec['effects'].append({'name': 'guide_line', 'layer': 'raw',
                                **src['guide_line']})

    def _zone(z):
        nz = dict(z)
        # renomeios canonicos (P2)
        if 'max_linhas' in nz:
            nz['max_lines'] = nz.pop('max_linhas')
        cat = nz.get('category')
        if cat == 'image':
            nz['role'] = 'image'
            nz.setdefault('fit', 'cover')
        else:
            nz['role'] = 'titulo' if cat == 'title' else nz.get('role') or 'subtitulo'
            # fit booleano do samsung -> modo canonico (P4); True = shrink passo 1
            if nz.get('fit') is True:
                nz['fit'] = 'shrink'
                nz['fit_step'] = 1
                nz['min_fs'] = 12
                nz['overflow'] = 'best_effort'  # truncate abolido (P4)
            elif nz.get('fit') in (False, None):
                nz['fit'] = 'fixed'
        return nz

    for z in src.get('zones') or []:
        spec['zones'].append(_zone(z))
    if src.get('brand_lockup'):
        bl = dict(src['brand_lockup'])
        bl['role'] = 'brand_lockup'
        spec['zones'].append(bl)
    return spec
