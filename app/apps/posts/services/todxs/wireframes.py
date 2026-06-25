"""
Sistema de wireframes da TODXS (fonte: TODXS_wireframes — especificacao de layout).

Encoda os 6 ARQUETIPOS (A-F) x 2 FORMATOS (feed 4:5, story 9:16) com zonas
nomeadas, COORDENADAS NUMERICAS (x/y/w/h/fs em %), fontes, cor e regras globais.
E a FONTE UNICA DE VERDADE que dirige:
  1) o FUNDO (campo de cor solido desenhado no Pillow, ou foto/cena via Gemini);
  2) a aplicacao de TEXTO/LOGO/SELO via Pillow (render_layout_document), com a
     fonte real (Ana Banana) e coordenadas exatas;
  3) (debug) um prompt single-shot para o Gemini renderizar com texto, so para
     comparacao na area de debug.

Coordenadas: x/y = canto superior-esquerdo da caixa, w/h = largura/altura, todos
em % do canvas. fs = font_size_pct (% do menor lado, como o render_layout_document
espera). Cada zona declara seu `role` no schema de _layout_elements:
  titulo | subtitulo | bloco(->titulo) | assinatura(->subtitulo) | logo | image | grafismo

Manutencao em prod = editar este dado. 100% isolado (nenhum codigo existente muda).
"""

FORMATOS = {
    'feed': {'label': 'Feed 4:5', 'ratio': '4:5', 'px': '1080x1350'},
    'story': {'label': 'Story 9:16', 'ratio': '9:16', 'px': '1080x1920'},
}

# Regras globais (do doc) — entram no prompt do Gemini-debug.
GLOBAL_RULES = [
    'MARGIN: safety margin ~5%; text/kicker/logo never touch the edge.',
    'ALIGNMENT: everything left-aligned. Only exception: a centered watermark wordmark.',
    'HIERARCHY: Kicker -> Title -> Support -> Signature. One zone dominates (the title).',
    'CASE: TITLES IN ALL CAPS; support text in normal case.',
    'COLOR: duotone uses the SAME color as the band/accent. No gradients. No pure white bg.',
]

# Negativos globais (reforco para o Gemini-debug; o Pillow ja so desenha as zonas).
GLOBAL_AVOID = [
    'gradients', 'pure white background', 'any color outside the palette',
    'lorem ipsum', 'garbled or misspelled text',
    'any thin outline, stroke, frame or border around the canvas or any zone '
    '(a solid color BAND is allowed; a hairline border is NOT)',
    'any logo, wordmark or seal anywhere other than the positions specified',
    'any text/label/paragraph not listed in the text zones',
]

# Papeis tipograficos -> descricao de estilo (para o Gemini-debug).
FONTS_DESC = {
    'display': 'very heavy grotesque display sans (Ana Banana Black): CAPS, tight tracking, '
               'deep ink-traps, rounded counters, 1970s queer-press poster feel',
    'medium': 'medium grotesque sans, CAPS, high legibility',
    'regular': 'clean grotesque sans, regular weight, normal case',
    'caps_small': 'small grotesque sans, CAPS, wide tracking',
}

# Definicao do SELO da marca (corrige "X sem circulo preto").
SELO_DESC = ('the TODXS seal: a SOLID BLACK CIRCLE with the four-petal butterfly "X" '
             'reversed out in off-white #F4F1D9 centered inside it')


def _band_color(_hex):
    return _hex


# Cada arquetipo: formato unico (exceto B), modo de fundo, marca/assets usados e
# zonas com coordenadas numericas. Para B (dual), zonas e coords sao por formato.
WIREFRAMES = {
    'A': {
        'name': 'Capa tipografica - fundo solido',
        'formatos': ['feed'],
        'fundo': 'solid',              # Pillow desenha campo de cor
        'usa': {'selo': True, 'wordmark': False, 'specimen': True},
        'bg_prompt': '',               # solid: sem Gemini
        'marca_desc': f'a small {SELO_DESC} at top-right.',
        'zonas': {
            'feed': [
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'top-left',
                 'x': 6, 'y': 6, 'w': 60, 'h': 6, 'fs': 2.4, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': None},
                {'key': 'titulo', 'role': 'titulo', 'pos': 'lower third, breathing space above',
                 'x': 6, 'y': 55, 'w': 90, 'h': 28, 'fs': 12, 'font': 'display',
                 'caps': True, 'align': 'left', 'color': None},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'right column, bottom',
                 'x': 52, 'y': 84, 'w': 42, 'h': 12, 'fs': 3.0, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': None},
            ],
        },
        'seal': {'feed': {'x': 82, 'y': 4, 'w': 12}},
        'avoid': ['no photo', 'no color band', 'title in BLACK on the color field'],
    },
    'B': {
        'name': 'Foto + faixa de cor inferior',
        'formatos': ['feed', 'story'],
        'fundo': 'photo',              # Gemini gera a foto; Pillow desenha a faixa
        'usa': {'selo': True, 'wordmark': {'feed': False, 'story': True}, 'specimen': False},
        'bg_prompt': ('full-bleed editorial COLOR photo of {PESSOA}, sharp focus throughout, '
                      'subject in the upper-center of the frame; documentary, vibrant, natural '
                      'light, evenly composed; NO blurred bands or strips, NO text, NO logo, '
                      'NO color band, NO graphic overlays.'),
        'marca_desc': f'{SELO_DESC} over the photo.',
        'band': {'feed': {'y': 70}, 'story': {'y': 52}},   # faixa do y% ate 100%
        'zonas': {
            'feed': [
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'top-left over photo',
                 'x': 6, 'y': 5, 'w': 60, 'h': 6, 'fs': 2.4, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': '#F4F1D9'},
                {'key': 'titulo', 'role': 'titulo', 'pos': 'inside the bottom color band',
                 'x': 6, 'y': 71, 'w': 88, 'h': 26, 'fs': 9.0, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': None},
            ],
            'story': [
                {'key': 'titulo', 'role': 'titulo', 'pos': 'inside the band (top)',
                 'x': 7, 'y': 55, 'w': 86, 'h': 16, 'fs': 8.0, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': None},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'inside the band, below title',
                 'x': 7, 'y': 72, 'w': 86, 'h': 14, 'fs': 3.2, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': None},
                {'key': 'assinatura', 'role': 'subtitulo', 'pos': 'band bottom-left (tema)',
                 'x': 7, 'y': 93, 'w': 50, 'h': 4, 'fs': 2.4, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': None},
            ],
        },
        'seal': {'feed': {'x': 82, 'y': 4, 'w': 13}, 'story': {'x': 7, 'y': 3, 'w': 15}},
        'wordmark': {'story': {'x': 70, 'y': 92, 'w': 23}},  # assinatura direita
        'avoid': ['straight horizontal cut between photo and band',
                  'feed: ONLY kicker + title (NO support text, NO bottom wordmark)'],
    },
    'C': {
        'name': 'Manchete em cima - foto emoldurada',
        'formatos': ['feed'],
        'fundo': 'solid_photo',        # Pillow: campo de cor + foto colada (emoldurada)
        'usa': {'selo': False, 'wordmark': True, 'specimen': True},
        'bg_prompt': ('full-bleed editorial COLOR photo of {PESSOA}, american shot, vibrant; '
                      'NO text, NO logo, NO border.'),
        'marca_desc': 'the "TODXS" wordmark at top-right.',
        'photo_frame': {'feed': {'x': 6, 'y': 40, 'w': 88, 'h': 40}},
        'zonas': {
            'feed': [
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'top-left header',
                 'x': 6, 'y': 5, 'w': 50, 'h': 5, 'fs': 2.4, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': None},
                {'key': 'titulo', 'role': 'titulo', 'pos': 'below header, large',
                 'x': 6, 'y': 12, 'w': 88, 'h': 24, 'fs': 9.0, 'font': 'display',
                 'caps': True, 'align': 'left', 'color': None},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'below the photo',
                 'x': 6, 'y': 84, 'w': 88, 'h': 10, 'fs': 2.8, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': None},
            ],
        },
        'wordmark': {'feed': {'x': 66, 'y': 4, 'w': 28}},
        'avoid': ['no band', 'black text on the color field'],
    },
    'D': {
        'name': 'Retrato full-bleed + wordmark gigante (peca de marca, SEM texto)',
        'formatos': ['feed'],
        'fundo': 'image',              # Gemini entrega a peca inteira
        'usa': {'selo': False, 'wordmark': False, 'specimen': False},
        'bg_prompt': ('brand cover: black-and-white CUT-OUT portrait of {PESSOA} over organic '
                      '{COR} shapes on a gray field; GIANT "TODXS" wordmark bleeding off the '
                      'sides at the top, the head/hair overlapping the letters. NO reading text.'),
        'marca_desc': 'the giant wordmark IS the graphic.',
        'zonas': {'feed': []},
        'avoid': ['no reading text', 'no kicker', 'no band'],
    },
    'E': {
        'name': 'Story tipografico - lista de blocos',
        'formatos': ['story'],
        'fundo': 'solid',
        'usa': {'selo': True, 'wordmark': True, 'specimen': False},
        'bg_prompt': '',
        'marca_desc': f'{SELO_DESC} at top-left.',
        'zonas': {
            'story': [
                {'key': 'blocos', 'role': 'titulo', 'pos': 'stacked equal-weight blocks',
                 'x': 7, 'y': 18, 'w': 86, 'h': 64, 'fs': 9.5, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': None, 'is_blocks': True},
            ],
        },
        'seal': {'story': {'x': 7, 'y': 4, 'w': 15}},
        'wordmark': {'story': {'x': 7, 'y': 91, 'w': 22}},  # logotipo (nao texto) no rodape
        'avoid': ['no photo', 'no frame/border', 'black text on the color field',
                  'all blocks same style, no numbering'],
    },
    'F': {
        'name': 'Story duotone + marca d agua (peca de transicao, SEM texto)',
        'formatos': ['story'],
        'fundo': 'image',
        'usa': {'selo': True, 'wordmark': True, 'specimen': False},
        'bg_prompt': ('full-bleed black-and-white photo of {PESSOA} with a flat {COR} duotone; '
                      'organic {COR} X-petal shapes bite 2-3 corners. NO reading text.'),
        'marca_desc': f'{SELO_DESC} at top-left, plus a centered "TODXS" wordmark watermark '
                      '(tonal, low opacity).',
        'zonas': {'story': []},
        'seal': {'story': {'x': 7, 'y': 4, 'w': 14}},
        'avoid': ['no reading text', 'no thin border'],
    },
}


# ----------------------------------------------------------------------------
# Helpers de leitura
# ----------------------------------------------------------------------------

def archetypes_for_format(fmt: str) -> list:
    return [k for k, v in WIREFRAMES.items() if fmt in v['formatos']]


def _uso(val, fmt):
    """Resolve um campo de `usa` que pode ser bool ou {fmt: bool}."""
    if isinstance(val, dict):
        return bool(val.get(fmt, False))
    return bool(val)


def assets_needed(archetype: str, fmt: str) -> dict:
    """Quais assets de marca o arquetipo/formato realmente usa (gating)."""
    usa = WIREFRAMES[archetype]['usa']
    return {
        'selo': _uso(usa.get('selo'), fmt),
        'wordmark': _uso(usa.get('wordmark'), fmt),
        'specimen': _uso(usa.get('specimen'), fmt),
    }


def background_mode(archetype: str) -> str:
    """'solid' (Pillow desenha), 'photo' (Gemini foto + Pillow faixa),
    'solid_photo' (Pillow cor + foto colada), 'image' (Gemini peca inteira)."""
    return WIREFRAMES[archetype].get('fundo', 'solid')


def zones_for(archetype: str, fmt: str) -> list:
    return WIREFRAMES[archetype].get('zonas', {}).get(fmt, [])


def build_background_prompt(archetype: str, content: dict, color_hex: str, fmt: str) -> str:
    """Prompt para o Gemini gerar o FUNDO (foto/cena), sem texto. '' = sem Gemini."""
    w = WIREFRAMES[archetype]
    tmpl = w.get('bg_prompt') or ''
    if not tmpl:
        return ''
    pessoa = content.get('pessoa') or 'a diverse LGBTQIA+ person, expressive, natural'
    f = FORMATOS[fmt]
    body = tmpl.replace('{PESSOA}', pessoa).replace('{COR}', color_hex)
    return (f"{f['ratio']} ({f['px']}) {body} Editorial documentary photography for TODXS, "
            f"a Brazilian LGBTQIA+ NGO. No watermark, no caption, no UI.")


def describe_for_brain(fmt: str) -> str:
    """Resumo dos arquetipos validos no formato, para o skill brain escolher."""
    lines = []
    for k in archetypes_for_format(fmt):
        w = WIREFRAMES[k]
        keys = [z['key'] for z in zones_for(k, fmt)]
        zonas = ', '.join(keys) or '(sem texto de leitura)'
        lines.append(f"  {k} — {w['name']} | fundo={w['fundo']} | zonas: {zonas}")
    return '\n'.join(lines)


# ----------------------------------------------------------------------------
# Prompt single-shot (Gemini-DEBUG: arte com texto embutido, so p/ comparacao)
# ----------------------------------------------------------------------------

def _zone_instruction(z: dict, content: dict) -> str:
    val = content.get(z['key'])
    if not val:
        return ''
    font = FONTS_DESC.get(z['font'], z['font'])
    if z.get('is_blocks') and isinstance(val, list):
        blocos = '; '.join(f'"{b}"' for b in val if b)
        return (f"- stacked blocks [{z['pos']}], equal weight, generous gaps: {blocos} "
                f"— {font}, left-aligned, CAPS.")
    if isinstance(val, list):
        val = ' '.join(str(v) for v in val if v)
    return (f"- {z['key']} [{z['pos']}]: \"{val}\" — {font}, "
            f"{'CAPS' if z.get('caps') else 'normal case'}, align {z['align']}.")


def build_singleshot_prompt(archetype: str, content: dict, color_hex: str,
                            color_name: str, fmt: str) -> str:
    w = WIREFRAMES[archetype]
    f = FORMATOS[fmt]
    pessoa = content.get('pessoa') or 'a diverse LGBTQIA+ person, expressive'
    band = w.get('band', {}).get(fmt)

    parts = [
        f"{f['ratio']} ({f['px']}) editorial social media {fmt} for TODXS, a Brazilian "
        f"LGBTQIA+ NGO. 1970s queer print-press poster style. Archetype {archetype}: {w['name']}.",
    ]
    if w['fundo'] == 'solid':
        parts.append(f"BACKGROUND: flat solid {color_hex} color field. No photo.")
    elif w['fundo'] in ('photo', 'solid_photo'):
        parts.append(f"BACKGROUND: editorial color photo of {pessoa}.")
    else:
        parts.append(f"BACKGROUND: {w.get('bg_prompt','').replace('{PESSOA}', pessoa).replace('{COR}', color_hex)}")
    if band:
        parts.append(f"COLOR BAND: solid {color_hex} band from {band['y']}% height to the bottom; "
                     f"straight horizontal cut.")
    parts.append(f"BRAND MARK: {w['marca_desc'].replace('{COR}', color_hex)}")
    parts.append(f"ACCENT COLOR: {color_name} {color_hex}.")

    zlines = [_zone_instruction(z, content) for z in zones_for(archetype, fmt)]
    zlines = [z for z in zlines if z]
    if zlines:
        parts.append('TEXT ZONES (render exactly, preserve every PT-BR diacritic):\n' + '\n'.join(zlines))
    else:
        parts.append('NO reading text on this piece.')

    parts.append(f'Palette: ONLY {color_hex} + black #000000 + off-white #F4F1D9.')
    parts.append('GLOBAL RULES:\n' + '\n'.join(f'- {r}' for r in GLOBAL_RULES))
    avoid = (w.get('avoid') or []) + GLOBAL_AVOID
    parts.append('AVOID: ' + '; '.join(avoid) + '.')
    return '\n\n'.join(parts)


# ----------------------------------------------------------------------------
# Elementos para o Pillow (render_layout_document) — schema _layout_elements
# ----------------------------------------------------------------------------

def _contrast_on(hex_color: str) -> str:
    """Preto ou off-white conforme a luminancia do fundo (campo/faixa)."""
    h = (hex_color or '#000000').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return '#000000'
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return '#000000' if lum > 150 else '#F4F1D9'


def _text_el(z, content_text, color_hex, *, y=None, h=None):
    """Monta um elemento de texto. Cor None -> contraste sobre o campo/faixa, e
    nesse caso ativa a CENTRALIZACAO VERTICAL na caixa (background_color dispara
    o has_bg do render_layout_document; para role != 'cta' nao desenha pill)."""
    el = {
        'role': z['role'], 'content': str(content_text).replace('\\n', '\n'),
        'x_pct': z['x'], 'y_pct': z['y'] if y is None else y, 'width_pct': z['w'],
        'height_pct': z['h'] if h is None else h, 'font_size_pct': z['fs'],
        'weight': 'black' if z['role'] == 'titulo' else 'regular',
        'case': 'upper' if z.get('caps') else 'none',
        'align': z['align'], 'color': z['color'],
    }
    if z['color'] is None:
        el['color'] = _contrast_on(color_hex)
        el['background_color'] = color_hex  # so p/ centralizar vertical (sem pill)
    return el


def wireframe_elements(archetype: str, content: dict, color_hex: str, fmt: str) -> list:
    """
    Converte as zonas do wireframe em _layout_elements (o MESMO schema que o
    editor avancado consome). Inclui: faixa de cor (grafismo), selo (role='seal'
    -> pillow_render compoe circulo+X), texto (centralizado vertical) e wordmark.
    """
    w = WIREFRAMES[archetype]
    els = []

    # 1) Faixa de cor (B): grafismo retangulo do y% ate o fim, corte reto.
    #    cor -> chave que o canvas JS le (e o Pillow tambem); color -> fallback.
    band = w.get('band', {}).get(fmt)
    if band:
        els.append({
            'role': 'grafismo', 'forma': 'retangulo', 'cor': color_hex, 'color': color_hex,
            'x_pct': 0, 'y_pct': band['y'], 'width_pct': 100,
            'height_pct': 100 - band['y'], 'raio_pct': 0, 'opacidade': 100,
        })

    # 2) Zonas de texto
    for z in zones_for(archetype, fmt):
        val = content.get(z['key'])
        if not val:
            continue
        if z.get('is_blocks') and isinstance(val, list):
            blocos = [b for b in val if b]
            n = len(blocos) or 1
            top, span = z['y'], z['h']
            step = span / n
            for i, b in enumerate(blocos):
                els.append(_text_el(z, b, color_hex, y=top + i * step, h=max(4, step)))
            continue
        if isinstance(val, list):
            val = ' '.join(str(v) for v in val if v)
        els.append(_text_el(z, val, color_hex))

    # 3) Selo (circulo preto + X) — pillow_render expande 'seal'
    need = assets_needed(archetype, fmt)
    seal = w.get('seal', {}).get(fmt)
    if need['selo'] and seal:
        els.append({'role': 'seal', 'x_pct': seal['x'], 'y_pct': seal['y'],
                    'width_pct': seal['w']})

    # 4) Wordmark (logo real)
    wm = w.get('wordmark', {}).get(fmt)
    if need['wordmark'] and wm:
        els.append({'role': 'logo', 'x_pct': wm['x'], 'y_pct': wm['y'], 'width_pct': wm['w']})

    return els
