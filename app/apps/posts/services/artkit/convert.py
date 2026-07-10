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


def todxs_to_v3(key: str, fmt: str, color_hex: str, src: dict = None) -> dict:
    """Converte um wireframe todxs v2 (pct) para v3, com a COR DO POST resolvida.

    Conversao ON-THE-FLY por render (como samsung_to_v3): a cor escolhida pelo
    usuario entra BAKED (ACCENT / ACCENT_LIGHT / contraste automatico viram hex
    literais) e os numeros validados entram intactos. As zonas pos-raw levam
    `layer: 'elements'` (dialeto do editor: faixa/selo/logo/texto viram
    _layout_elements quantizados em % — editor == publicado). `pct_box` carrega
    os floats AUTORADOS intactos (P2) p/ eliminar ruido de ida-e-volta na
    quantizacao int() historica."""
    from apps.posts.services.todxs.wireframes import WF
    from apps.posts.services.todxs.layout import _lighten
    from apps.posts.services.artkit.text import contrast_on

    src = src or WF()[key]
    if src.get('spec_version') == 3:   # ja e v3 (futuro: banco nativo v3)
        return src
    W, H = (1080, 1920) if fmt == 'story' else (1080, 1350)
    basis = min(W, H)

    spec = {
        'spec_version': 3,
        'name': src.get('name') or key,
        'canvas': [W, H],
        'units': 'pct',
        'formats': [fmt],
        'background': {'type': 'solid', 'color': color_hex},
        'zones': [],
        'effects': [],
    }

    def _color(zc):
        if zc == 'ACCENT':
            return color_hex
        if zc == 'ACCENT_LIGHT':
            return _lighten(color_hex, 0.72)
        return zc or contrast_on(color_hex)

    def _uso(val):
        return bool(val.get(fmt, False)) if isinstance(val, dict) else bool(val)

    fundo = src.get('fundo', 'solid')
    band = (src.get('band') or {}).get(fmt)
    frame = (src.get('photo_frame') or {}).get(fmt)

    # foto no RAW — regiao visivel com a quantizacao HISTORICA do foto_region
    # (band: h=round; frame: int/trunca). Emitimos pct exatos-em-px p/ o engine
    # recuperar os MESMOS ints.
    if fundo in ('photo', 'solid_photo', 'image'):
        if band:
            box = [0.0, 0.0, 100.0, int(round(band['y'] / 100.0 * H)) / H * 100.0]
        elif frame:
            fx, fy = int(frame['x'] / 100.0 * W), int(frame['y'] / 100.0 * H)
            fw, fh = int(frame['w'] / 100.0 * W), int(frame['h'] / 100.0 * H)
            box = [fx / W * 100.0, fy / H * 100.0, fw / W * 100.0, fh / H * 100.0]
        else:
            box = [0.0, 0.0, 100.0, 100.0]
        zone = {'key': 'photo', 'role': 'image', 'box': box, 'fit': 'cover',
                'fetch': 'rgb', 'cover_rounding': 'int'}
        if src.get('grayscale'):
            zone['grayscale'] = True
        if src.get('multiply'):
            zone['multiply'] = color_hex
        spec['zones'].append(zone)

    # faixa de cor -> elemento grafismo (retangulo editavel, pos-raw)
    if band:
        bb = [0, band['y'], 100, 100 - band['y']]
        spec['zones'].append({'key': 'band', 'role': 'grafismo',
                              'layer': 'elements', 'box': list(bb), 'pct_box': bb,
                              'color': color_hex})

    # zonas de texto (dialeto todxs -> chaves canonicas; semantica de fit em
    # BLOCO: maior corpo cuja pilha de linhas cabe na caixa, passo 2, min 14px)
    for z in (src.get('zonas') or {}).get(fmt) or []:
        bb = [z['x'], z['y'], z['w'], z['h']]
        nz = {
            'key': z['key'], 'role': z.get('role') or 'subtitulo',
            'layer': 'elements', 'box': list(bb), 'pct_box': bb,
            'fs': z['fs'], 'font': z['font'], 'align': z.get('align', 'left'),
            'color': _color(z.get('color')),
            'max_lines': z.get('max_linhas', 4),
            'leading': float(z.get('leading', 1.16)),
            'text_normalize': 'collapse',
        }
        if z.get('caps'):
            nz['case'] = 'upper'
        if z.get('center_v'):
            nz['valign'] = 'center'
        if z.get('is_blocks'):
            nz['blocks'] = True
        if z.get('flow_after'):
            nz['flow_after'] = z['flow_after']
            nz['flow_gap'] = z.get('gap_pct', 1.5)
            nz['y_max'] = z.get('y_max', 96)
        if z.get('fixed_fs'):
            nz['fit'] = 'fixed'
        else:
            nz['fit'] = 'shrink'
            nz['fit_step'] = 2
            nz['fit_measure'] = 'block'
            nz['min_fs'] = 14.0 / basis * 100.0
        spec['zones'].append(nz)

    # selo e wordmark — assets compostos pelo ADAPTER (KB); box h=w (semantica
    # historica: height_pct do elemento = width_pct)
    usa = src.get('usa') or {}
    seal = (src.get('seal') or {}).get(fmt)
    if _uso(usa.get('selo')) and seal:
        bb = [seal['x'], seal['y'], seal['w'], seal['w']]
        spec['zones'].append({'key': 'seal', 'role': 'image', 'layer': 'elements',
                              'asset': 'seal', 'box': list(bb), 'pct_box': bb,
                              'fit': 'contain'})
    wm = (src.get('wordmark') or {}).get(fmt)
    if _uso(usa.get('wordmark')) and wm:
        over_faixa = bool(band) and wm['y'] >= band['y']
        if src.get('wordmark_color'):
            logo_color = src['wordmark_color']
        elif over_faixa or fundo == 'solid':
            logo_color = contrast_on(color_hex)
        else:
            logo_color = '#F4F1D9'   # sobre a foto
        bb = [wm['x'], wm['y'], wm['w'], wm['w']]
        spec['zones'].append({'key': 'wordmark', 'role': 'image',
                              'layer': 'elements', 'asset': 'wordmark',
                              'recolor': logo_color, 'box': list(bb),
                              'pct_box': bb, 'fit': 'contain'})

    # moldura arredondada (ex.: B story) — efeito no final
    rf = (src.get('rounded_frame') or {}).get(fmt)
    if rf:
        spec['effects'].append({'name': 'rounded_border', 'layer': 'final',
                                'radius': rf, 'bg_color': '#F4F1D9'})
    return spec
