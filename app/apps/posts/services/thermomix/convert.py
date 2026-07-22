"""
Conversor do dialeto AUTORADO da thermomix (authored.py) -> spec v3 (artkit).

Roda no SEED (seed_archetypes): o banco (PostArchetype.spec) recebe a spec v3
pronta; o admin edita a v3 e o render le do banco (catalog.py). O autorado fica
no codigo como fonte primaria re-importavel (--resync-spec).

Mapeamento por categoria:
  LOGOTIPO      -> zona role 'brand_lockup' (asset da KB, slot em `asset`)
  ASSINATURA    -> zona role 'logo_fixo'    (asset da KB, slot em `asset`)
  TITULO        -> zona de texto (fit shrink, sem truncate)
  LISTA         -> effect 'panel' (faixa translucida, camada raw) + zonas de
                   icone (image) + UMA zona de texto POR LINHA (estilo unico por
                   linha; trechos mistos viajam em `spans` p/ o engine desenhar
                   quando houver suporte — ate la vale o estilo do 1o trecho)
  SELO          -> zona layer 'elements' shape circle|pill no contrato do CTA
                   unificado (background_color+radius+texto centralizado);
                   emissao no engine e o proximo passo — `optional` ate la
  ASSET_RETRATO -> zona de imagem (upload usage_type=pessoa), cover, optional
  fundo foto    -> background photo_upload + effect scrim vertical no topo

Tudo em px (units='px'); spec3.normalize() fraciona no load.
"""

LINE_GAP = 1.35          # avanco vertical entre linhas de LISTA (x font_size)
LIST_PAD_TOP_PX = 10     # respiro entre o topo da faixa e a 1a linha


def _px_box(bbox_norm, W, H):
    x, y, w, h = bbox_norm
    return [int(round(x * W)), int(round(y * H)),
            int(round(w * W)), int(round(h * H))]


def _spans(segmentos):
    return [{'t': s['t'], 'color': s.get('cor', 'texto_escuro'),
             'weight': int(s.get('weight', 400))} for s in (segmentos or [])]


def _plain(segmentos):
    return ''.join(s['t'] for s in (segmentos or []))


def _line_zone(linha, x, y, w, fs, fontes):
    """Zona de texto de UMA linha de LISTA. Estilo base = 1o segmento."""
    segs = linha.get('segmentos') or []
    first = segs[0] if segs else {}
    fam = linha.get('familia', 'corpo')
    bold = f'{fam}_bold' if f'{fam}_bold' in (fontes or {}) else fam
    return {
        'key': linha['key'],
        'role': 'subtitulo',
        'box': [x, y, w, int(round(fs * LINE_GAP))],
        'font': fam,
        'font_bold': bold,
        'fs': fs,
        'min_fs': int(round(fs * 0.7)),
        'max_lines': 1,
        'fit': 'shrink',
        'leading': 1.2,
        'align': 'left',
        'color': first.get('cor', 'texto_escuro'),
        'weight': 'bold' if int(first.get('weight', 400)) >= 700 else 'regular',
        'spans': _spans(segs),          # trechos p/ desenho rico (engine, passo 2)
    }


def authored_to_v3(a: dict) -> dict:
    meta = a['meta']
    W, H = meta['dimensoes']['w'], meta['dimensoes']['h']
    cores = (a.get('tokens') or {}).get('cores') or {}
    fontes = (a.get('tokens') or {}).get('tipografia') or {}

    zones, effects = [], []

    fundo = a.get('fundo') or {}
    background = {'type': 'photo_upload', 'color': '#5E5E5E'}
    if fundo.get('scrim_topo'):
        st = fundo['scrim_topo']
        effects.append({'name': 'scrim', 'layer': 'bg', 'axis': 'y',
                        'color': '#000000', 'alpha': int(st.get('alpha', 140)),
                        'to': float(st.get('ate_norm', 0.35))})

    for b in a['blocos']:
        cat = b['categoria']
        box = _px_box(b['bbox_norm'], W, H)

        if cat == 'LOGOTIPO':
            zones.append({'key': b['key'], 'role': 'brand_lockup',
                          'asset': b.get('asset_ref', 'brand_lockup'),
                          'box': box, 'note': b.get('label')})

        elif cat == 'ASSINATURA':
            zones.append({'key': b['key'], 'role': 'logo_fixo',
                          'asset': b.get('asset_ref', 'distribuidor'),
                          'box': box, 'valign': 'center', 'note': b.get('label')})

        elif cat == 'TITULO':
            t = b.get('texto') or {}
            zones.append({
                'key': b['key'], 'role': 'titulo', 'box': box,
                'font': t.get('familia', 'display'),
                'fs': int(t.get('font_size_px', 94)),
                'min_fs': int(t.get('min_font_px', 60)),
                'max_lines': int(t.get('max_linhas', 2)),
                'leading': float(t.get('line_height', 1.05)),
                'align': t.get('align', 'left'), 'fit': 'shrink',
                'color': t.get('cor', 'branco'), 'weight': 'bold',
                'note': b.get('label'),
            })

        elif cat == 'LISTA':
            forma = b.get('forma') or {}
            if forma.get('tipo') == 'faixa':
                effects.append({
                    'name': 'panel', 'layer': 'raw',
                    'x': box[0], 'y': box[1], 'w': box[2], 'h': box[3],
                    'color': forma.get('cor', 'branco'),
                    'alpha': int(round(float(forma.get('opacidade', 0.75)) * 255)),
                })
            for ic in (b.get('icones') or []):
                zones.append({'key': ic['ref'], 'role': 'image',
                              'asset': ic['ref'], 'fit': 'contain',
                              'recolor': ic.get('cor', 'verde'),
                              'box': _px_box(ic['bbox_norm'], W, H),
                              'optional': True})
            indent = float(b.get('indent_norm', 0.0))
            tx = int(round((b['bbox_norm'][0] + indent) * W))
            tw = int(round((b['bbox_norm'][2] - indent - 0.01) * W))
            ty = box[1] + LIST_PAD_TOP_PX
            for linha in (b.get('linhas') or []):
                fs = int(linha.get('font_size_px', 42))
                zones.append(_line_zone(linha, tx, ty, tw, fs, fontes))
                ty += int(round(fs * LINE_GAP))

        elif cat == 'ASSET_RETRATO':
            zones.append({'key': b['key'], 'role': 'image', 'asset': b['key'],
                          'box': box, 'fit': 'cover', 'optional': True,
                          'note': b.get('label')})

        elif cat == 'SELO':
            forma = b.get('forma') or {}
            fixo = b.get('conteudo_fixo') or {}
            zones.append({
                'key': b['key'], 'layer': 'elements', 'role': 'cta',
                'box': box, 'optional': True, 'note': b.get('label'),
                'shape': 'circle' if forma.get('tipo') == 'circulo' else 'pill',
                'bg': forma.get('cor', 'verde'),
                'align': fixo.get('align', 'center'),
                'valign': fixo.get('valign', 'center'),
                'lines': [{'key': ln['key'],
                           'fs': int(ln.get('font_size_px', 36)),
                           'font': ln.get('familia', 'corpo'),
                           'spans': _spans(ln.get('segmentos'))}
                          for ln in (fixo.get('linhas') or [])],
            })

    return {
        'spec_version': 3,
        'name': meta.get('nome') or meta.get('id'),
        'canvas': [W, H],
        'units': 'px',
        'formats': [meta.get('formato', 'feed')],
        'background': background,
        'zones': zones,
        'effects': effects,
        'tokens': dict(cores),
        'fonts': dict(fontes),
        'authored_id': meta.get('id'),
    }


def default_content(a: dict) -> dict:
    """{zone_key: texto plano} do conteudo-exemplo autorado (preview/portao)."""
    out = {}
    for b in a['blocos']:
        if b['categoria'] == 'TITULO' and b.get('exemplo'):
            out[b['key']] = b['exemplo']
        for linha in (b.get('linhas') or []):
            out[linha['key']] = _plain(linha.get('segmentos'))
        fixo = b.get('conteudo_fixo') or {}
        for linha in (fixo.get('linhas') or []):
            out[linha['key']] = _plain(linha.get('segmentos'))
    return out
