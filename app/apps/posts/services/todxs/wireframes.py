"""
Sistema de wireframes da TODXS (fonte: TODXS_wireframes — especificacao de layout).

Encoda os 6 ARQUETIPOS (A-F) x 2 FORMATOS (feed 4:5, story 9:16) com zonas
nomeadas, posicoes/tamanhos relativos, fontes, cor e regras globais. E a FONTE
UNICA DE VERDADE que dirige:
  1) a geracao do FUNDO (receita por arquetipo);
  2) a aplicacao do TEXTO via Gemini (wireframe explicito: zonas + tamanhos).

Manutencao em prod = editar este dado, sem mexer em logica. 100% isolado.

Tamanhos sao % da LARGURA do canvas (px do doc / largura de referencia:
640 no feed, 360 no story). Posicoes sao descritivas (o modelo nao honra px,
mas segue zonas/altura/alinhamento com fidelidade).
"""

# Vocabulario fixo de zonas (do doc): Background, Asset/Foto, Faixa de cor,
# Formas organicas, Marca (simbolo), Logotipo (wordmark), Kicker/Tema, Titulo,
# Texto de apoio, Assinatura.

FORMATOS = {
    'feed': {'label': 'Feed 4:5', 'ratio': '4:5', 'px': '1080x1350', 'ref_w': 640},
    'story': {'label': 'Story 9:16', 'ratio': '9:16', 'px': '1080x1920', 'ref_w': 360},
}

# Regras globais (valem para TODAS as pecas).
GLOBAL_RULES = [
    'MARGIN: safety margin ~5% on every side; text, kicker and logo never touch the edge.',
    'ALIGNMENT: everything left-aligned. Only exception: a centered watermark wordmark.',
    'HIERARCHY: Kicker -> Title -> Support -> Signature. One zone dominates (almost always the title).',
    'CASE: TITLES IN ALL CAPS; support text in normal case.',
    'BRAND MARK: use the four-petal "X" SEAL when there is a photo or full-color top; '
    'use the "TODXS" WORDMARK on headlines and covers.',
    'COLOR: if the photo is duotone, the duotone uses the SAME color as the band/accent '
    '(monochrome, cohesive piece). No gradients. No pure-white background.',
]

# Papeis tipograficos -> descricao de estilo (as fontes reais nao existem no modelo).
FONTS = {
    'display_black': 'very heavy grotesque display sans-serif (Ana Banana Black style): '
                     'CAPS, tight tracking, deep ink-traps, flared bell-mouth terminals, '
                     'rounded smiling counters; bold 1970s queer-press poster feel',
    'sans_medium': 'medium/condensed grotesque sans-serif, CAPS, high legibility',
    'sans_regular': 'clean grotesque sans-serif, regular weight, normal case',
    'sans_caps_small': 'small condensed grotesque sans-serif, CAPS, wide tracking',
}

# Cada arquetipo: formatos validos, receita de fundo, e zonas de texto.
# size = % da largura do canvas de referencia. content_key = chave em `content`.
WIREFRAMES = {
    'A': {
        'name': 'Capa tipografica - fundo solido',
        'formatos': ['feed'],
        'tem_foto': False,
        'background': 'solid flat {COR} color field (no photo). The color is the protagonist.',
        'marca': 'small black circular seal with a four-petal "X" in {COR} at top-left.',
        'zonas': [
            {'key': 'kicker', 'label': 'kicker/tema', 'pos': 'top-left, inside ~5% margin',
             'font': 'sans_caps_small', 'size': 2.0, 'caps': True, 'align': 'left'},
            {'key': 'titulo', 'label': 'title (display, up to 2 lines)',
             'pos': 'lower third, NOT starting at the top (breathing space above), left-aligned',
             'font': 'display_black', 'size': 13.8, 'caps': True, 'align': 'left', 'leading': 0.92},
            {'key': 'apoio', 'label': 'support text', 'pos': 'right column (~50% width), bottom, left-aligned',
             'font': 'sans_regular', 'size': 3.4, 'caps': False, 'align': 'left', 'leading': 1.35},
        ],
        'color_note': 'title in black on the solid color field.',
    },
    'B': {
        'name': 'Foto + faixa de cor inferior',
        'formatos': ['feed', 'story'],
        'tem_foto': True,
        'split': {'feed': {'foto_pct': 70, 'faixa_pct': 30},
                  'story': {'foto_pct': 52, 'faixa_pct': 48}},
        'background': 'TOP {FOTO_PCT}% = photo of {PESSOA}; BOTTOM {FAIXA_PCT}% = solid {COR} band. '
                      'Straight horizontal cut, no overlap. Optional duotone on the photo using {COR}.',
        'marca': 'four-petal "X" SEAL at top-right over the photo; wordmark may appear in the signature line.',
        'zonas': [
            {'key': 'kicker', 'label': 'kicker/tema', 'pos': 'top-left over the photo',
             'font': 'sans_caps_small', 'size': 1.9, 'caps': True, 'align': 'left'},
            {'key': 'titulo', 'label': 'title (up to 3 lines)',
             'pos': 'entirely INSIDE the bottom color band, left-aligned, equal top/bottom padding (>=4%)',
             'font': 'sans_medium', 'size': 7.0, 'caps': True, 'align': 'left', 'leading': 1.05},
            {'key': 'apoio', 'label': 'support text (story only)',
             'pos': 'inside the band, below the title (~16px gap), left-aligned',
             'font': 'sans_regular', 'size': 4.2, 'caps': False, 'align': 'left', 'leading': 1.4},
            {'key': 'assinatura', 'label': 'signature line (story only)',
             'pos': 'bottom of the band: tema at left + "TODXS" wordmark at right',
             'font': 'sans_caps_small', 'size': 3.3, 'caps': True, 'align': 'left'},
        ],
        'color_note': 'dark title over the warm/colored band; if duotone, photo shares the band color.',
    },
    'C': {
        'name': 'Manchete em cima - foto no miolo/base',
        'formatos': ['feed'],
        'tem_foto': True,
        'background': 'solid {COR} color field holding everything; a color american-shot PHOTO of '
                      '{PESSOA} is framed in the middle/lower area with equal side margins (~5%), '
                      '"framed" by the color field.',
        'marca': 'kicker at top-left and "TODXS" wordmark at top-right on the same baseline.',
        'zonas': [
            {'key': 'kicker', 'label': 'kicker (e.g. NOTICIA)', 'pos': 'top-left header',
             'font': 'sans_caps_small', 'size': 2.0, 'caps': True, 'align': 'left'},
            {'key': 'titulo', 'label': 'news headline (large)',
             'pos': 'right below the header, left-aligned, nearly full width',
             'font': 'display_black', 'size': 7.5, 'caps': True, 'align': 'left', 'leading': 1.0},
            {'key': 'apoio', 'label': 'support text', 'pos': 'below the photo, left-aligned, within bottom margin',
             'font': 'sans_regular', 'size': 2.7, 'caps': False, 'align': 'left', 'leading': 1.4},
        ],
        'color_note': 'black text on the solid color field.',
    },
    'D': {
        'name': 'Retrato full-bleed + logotipo gigante (peca de marca, SEM texto)',
        'formatos': ['feed'],
        'tem_foto': True,
        'background': 'black-and-white cut-out PORTRAIT of {PESSOA} over organic {COR} shapes on a gray field; '
                      'GIANT "TODXS" wordmark bleeding off the sides at the top, with the head/hair of the '
                      'portrait overlapping the letters (intentional). The "X" of the wordmark may be cropped.',
        'marca': 'the giant wordmark IS the graphic element.',
        'zonas': [],  # sem texto de leitura
        'color_note': 'brand/identity cover, no reading text. Eyes of the portrait in the upper-central third.',
    },
    'E': {
        'name': 'Story tipografico - lista de blocos',
        'formatos': ['story'],
        'tem_foto': False,
        'background': 'solid flat {COR} color field with a rounded inner frame (radius ~6%).',
        'marca': 'four-petal "X" SEAL at top-left, inside the rounded frame.',
        'zonas': [
            {'key': 'blocos', 'label': '2-3 text blocks of EQUAL weight, stacked, generous gap (~9%) between them',
             'pos': 'left-aligned column, generous vertical gaps (the gap creates the "list" reading)',
             'font': 'sans_medium', 'size': 8.3, 'caps': True, 'align': 'left', 'leading': 1.05},
            {'key': 'assinatura', 'label': 'tema/signature', 'pos': 'fixed at bottom-left within the safety margin',
             'font': 'sans_caps_small', 'size': 3.3, 'caps': True, 'align': 'left'},
        ],
        'color_note': 'black text on the solid color field; all blocks share the same style (no numbering).',
    },
    'F': {
        'name': 'Story duotone + marca d agua (peca de transicao, SEM texto)',
        'formatos': ['story'],
        'tem_foto': True,
        'background': 'full-bleed black-and-white PHOTO of {PESSOA} with a flat {COR} multiply DUOTONE, '
                      'inside a rounded frame (radius ~6%). Organic {COR} X-petal shapes bite 2-4 corners.',
        'marca': 'four-petal "X" SEAL at top-left; centered "TODXS" WORDMARK as a tonal watermark '
                 '(same color as the photo, low opacity ~35-50%) — the ONLY centered case.',
        'zonas': [],  # sem texto de leitura
        'color_note': 'transition/breather piece, no reading text.',
    },
}


def archetypes_for_format(fmt: str) -> list:
    """Letras de arquetipos validos para o formato ('feed' ou 'story')."""
    return [k for k, v in WIREFRAMES.items() if fmt in v['formatos']]


def describe_for_brain(fmt: str) -> str:
    """Resumo dos arquetipos validos no formato, para o skill brain escolher."""
    lines = []
    for k in archetypes_for_format(fmt):
        w = WIREFRAMES[k]
        zonas = ', '.join(z['key'] for z in w['zonas']) or '(sem texto de leitura)'
        lines.append(f"  {k} — {w['name']} | foto={'sim' if w['tem_foto'] else 'nao'} | zonas: {zonas}")
    return '\n'.join(lines)


def _zone_instruction(z: dict, content: dict, color_hex: str) -> str:
    """Monta a linha de uma zona com a string travada citada (PT, com acentos)."""
    val = content.get(z['key'])
    if not val:
        return ''
    font = FONTS.get(z['font'], z['font'])
    extra = []
    if z.get('leading'):
        extra.append(f"leading {z['leading']}")
    extra_s = (', ' + ', '.join(extra)) if extra else ''
    if z['key'] == 'blocos' and isinstance(val, list):
        blocos = '; '.join(f'"{b}"' for b in val)
        return (f"- {z['label']} [{z['pos']}]: render each block exactly, stacked: {blocos} "
                f"— {font}, ~{z['size']}% of width{extra_s}.")
    return (f"- {z['label']} [{z['pos']}]: \"{val}\" — {font}, "
            f"~{z['size']}% of width, {'CAPS' if z.get('caps') else 'normal case'}, "
            f"align {z['align']}{extra_s}.")


def build_singleshot_prompt(archetype: str, content: dict, color_hex: str,
                            color_name: str, fmt: str, pessoa_hint: str = '') -> str:
    """
    Monta o prompt single-shot DETERMINISTICO a partir do wireframe do arquetipo.
    content: {kicker, titulo, apoio, assinatura, blocos, footer, pessoa}.
    """
    w = WIREFRAMES[archetype]
    f = FORMATOS[fmt]
    split = w.get('split', {}).get(fmt, {})
    pessoa = content.get('pessoa') or pessoa_hint or 'a diverse LGBTQIA+ person, american/medium shot, expressive'

    bg = w['background'].replace('{COR}', color_hex).replace('{PESSOA}', pessoa)
    if split:
        bg = bg.replace('{FOTO_PCT}', str(split.get('foto_pct', ''))).replace(
            '{FAIXA_PCT}', str(split.get('faixa_pct', '')))
    marca = w['marca'].replace('{COR}', color_hex)

    parts = [
        f"{f['ratio']} ({f['px']}) editorial social media {fmt} for TODXS, a Brazilian "
        f"LGBTQIA+ NGO. Bold editorial poster style inspired by 1970s queer print press "
        f"(Lampiao da Esquina). Archetype {archetype}: {w['name']}.",
        f"BACKGROUND: {bg}",
        f"BRAND MARK / GRAPHIC: {marca}",
        f"ACCENT COLOR: {color_name} {color_hex}. {w['color_note']}",
    ]

    zone_lines = [_zone_instruction(z, content, color_hex) for z in w['zonas']]
    zone_lines = [z for z in zone_lines if z]
    if zone_lines:
        parts.append('TEXT ZONES (render exactly, do not paraphrase, do not alter spelling):\n'
                     + '\n'.join(zone_lines))
    else:
        parts.append('NO reading text on this piece (brand/cover piece).')

    parts.append(
        'All visible text is in Brazilian Portuguese, spelled exactly as written, preserving '
        'every diacritic (á é í ó ú â ê ô ã õ à ç) and all punctuation.')
    parts.append(f'Palette: ONLY {color_hex} + black #000000 + off-white #F4F1D9.')
    parts.append('GLOBAL RULES:\n' + '\n'.join(f'- {r}' for r in GLOBAL_RULES))
    parts.append('AVOID: gradients, pure white background, extra logos, watermark text other than '
                 'the wordmark, lorem ipsum, garbled or misspelled text, any color outside the palette.')
    return '\n\n'.join(parts)
