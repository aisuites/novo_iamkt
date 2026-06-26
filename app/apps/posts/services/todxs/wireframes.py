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
        # Peca 01: SEM simbolo e SEM logo. So kicker + titulo + apoio.
        'usa': {'selo': False, 'wordmark': False, 'specimen': True},
        'bg_prompt': '',               # solid: sem Gemini
        'marca_desc': 'no symbol and no logo — the solid color and the big title ARE the piece.',
        'zonas': {
            'feed': [
                # Coordenadas EXATAS medidas da referencia (arquetipo_A.json).
                # Cor do texto = PRETO obrigatorio. kicker = Vinila (CallingCode).
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'top-left (margem)',
                 'x': 6.18, 'y': 3.54, 'w': 30.74, 'h': 4.0, 'fs': 2.3, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': '#000000', 'max_linhas': 1,
                 'leading': 1.0},
                {'key': 'titulo', 'role': 'titulo', 'pos': 'ancora y=0.40 (nunca no topo)',
                 'x': 6.66, 'y': 40.42, 'w': 86.69, 'h': 22.71, 'fs': 13.9, 'font': 'display',
                 'caps': True, 'align': 'left', 'color': '#000000', 'max_linhas': 2,
                 'leading': 0.92},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'coluna direita, base inferior',
                 'x': 47.39, 'y': 71.06, 'w': 44.85, 'h': 22.1, 'fs': 2.78, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': '#000000', 'max_linhas': 6,
                 'leading': 1.35},
            ],
        },
        'avoid': ['no photo', 'no color band', 'no symbol/seal', 'no logo/wordmark',
                  'title and support text in BLACK on the color field'],
    },
    'B': {
        'name': 'Foto + faixa de cor inferior',
        'formatos': ['feed', 'story'],
        'fundo': 'photo',              # Gemini gera a foto; Pillow desenha a faixa
        # feed (peca 02): wordmark top-left, SEM selo, SEM kicker.
        # story (peca 04): selo top-left + wordmark na assinatura (rodape direito).
        'usa': {'selo': {'feed': False, 'story': True},
                'wordmark': {'feed': True, 'story': True}, 'specimen': False},
        'bg_prompt': ('full-bleed editorial COLOR photo of {PESSOA}, sharp focus throughout; '
                      'frame the subject in the TOP ~65% of the image (the bottom third will be '
                      'covered by a solid color band, so keep the subject high); documentary, '
                      'vibrant, natural light, evenly composed; NO blurred bands or strips, '
                      'NO text, NO logo, NO color band, NO graphic overlays.'),
        'marca_desc': ('feed: the "TODXS" wordmark at top-left over the photo. '
                       f'story: {SELO_DESC} at top-left + the wordmark in the bottom signature.'),
        # split do JSON: foto 67.77% / faixa 32.23%
        'band': {'feed': {'y': 67.77}, 'story': {'y': 50.25}},
        'wordmark_color': '#000000',   # B: wordmark SEMPRE preto (decisao do dono)
        'seal_color': 'ACCENT',        # selo (story): circulo preto + X na cor da faixa
        'zonas': {
            'feed': [
                # coords do arquetipo_B.json; titulo PRETO, Ana Banana Medium,
                # centralizado vertical na faixa, leading 1.05.
                # box = faixa inteira (67.77->100) + center_v -> respiro igual em cima/baixo.
                {'key': 'titulo', 'role': 'titulo', 'pos': 'centered in the bottom color band',
                 'x': 7.61, 'y': 67.77, 'w': 70.52, 'h': 32.23, 'fs': 7.2, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': '#000000', 'center_v': True,
                 'leading': 1.05, 'max_linhas': 3},
            ],
            # coords do arquetipo_B_story.json: faixa empilha titulo->apoio->assinatura.
            'story': [
                {'key': 'titulo', 'role': 'titulo', 'pos': 'faixa, hero (3 linhas)',
                 'x': 9.43, 'y': 57.26, 'w': 81.14, 'h': 17.92, 'fs': 8.9, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': '#000000', 'leading': 1.05,
                 'max_linhas': 3},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'faixa, below title',
                 'x': 9.25, 'y': 79.48, 'w': 80.43, 'h': 8.5, 'fs': 3.15, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': '#000000', 'leading': 1.4,
                 'max_linhas': 3},
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'assinatura base-left (tema)',
                 'x': 9.61, 'y': 90.69, 'w': 34.52, 'h': 2.7, 'fs': 2.6, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': '#000000', 'max_linhas': 1},
            ],
        },
        'seal': {'story': {'x': 4.98, 'y': 3.8, 'w': 11.92}},
        'wordmark': {'feed': {'x': 6.34, 'y': 3.42, 'w': 19.18},
                     'story': {'x': 69.75, 'y': 90.69, 'w': 20.46}},
        'rounded_frame': {'story': 3.9},   # moldura arredondada (raio % da largura)
        'avoid': ['straight horizontal cut between photo and band',
                  'feed: wordmark top-left + title in the band ONLY (no kicker, no seal)'],
    },
    'B_DUO': {
        'name': 'Foto duotone (multiply) + faixa - variante mono',
        'formatos': ['feed'],
        'auto': False,          # so via force (selecao automatica fica p/ depois)
        'fundo': 'photo',       # foto gerada no Gemini JA como duotone
        'gemini_duotone': True, # bg_prompt pede DUOTONE na cor da faixa (sem multiply Pillow)
        'usa': {'selo': True, 'wordmark': False, 'specimen': False},
        'seal_style': 'bare',   # simbolo = X puro (sem circulo)
        'seal_color': '#000000',  # asset PRETO
        'bg_prompt': ('editorial portrait of {PESSOA}, sharp focus throughout; '
                      'frame the subject in the TOP ~68% of the image (the bottom will be '
                      'covered by a solid color band, so keep the subject high); '
                      'evenly composed; NO blurred bands or strips, NO text, NO logo, '
                      'NO color band, NO graphic overlays.'),
        'marca_desc': ('TEMA (kicker) top-left + four-petal X (black) top-right over the photo; '
                       'the photo is a monochromatic DUOTONE in the band color.'),
        # split do arquetipo_B_duotone.json: foto 70.26% / faixa 29.74%
        'band': {'feed': {'y': 70.26}},
        'zonas': {
            'feed': [
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'tema top-left over photo',
                 'x': 6.18, 'y': 3.55, 'w': 29.95, 'h': 4.0, 'fs': 1.95, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': 'ACCENT', 'max_linhas': 1,
                 'leading': 1.0},
                # titulo PRETO, ~largura total, GRANDE, centralizado vertical na faixa.
                {'key': 'titulo', 'role': 'titulo', 'pos': 'in band, almost full width',
                 'x': 6.5, 'y': 70.26, 'w': 92.55, 'h': 29.74, 'fs': 7.4, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': '#000000', 'center_v': True,
                 'leading': 1.06, 'max_linhas': 3},
            ],
        },
        'seal': {'feed': {'x': 86.69, 'y': 3.43, 'w': 6.97}},
        'avoid': ['no wordmark', 'photo in duotone/multiply of the band color',
                  'tema top-left + X seal top-right'],
    },
    'C': {
        'name': 'Manchete em cima + foto P&B emoldurada no miolo',
        'formatos': ['feed'],
        'fundo': 'solid_photo',        # campo de cor solido + foto emoldurada (Gemini)
        'grayscale': True,             # foto em P&B (grayscale)
        'usa': {'selo': False, 'wordmark': True, 'specimen': False},
        'wordmark_color': '#000000',   # wordmark PRETO no topo-direita sobre a cor
        'bg_prompt': ('editorial portrait of {PESSOA}, sharp focus; '
                      'NO text, NO logo, NO border, NO frame.'),
        'marca_desc': ('KICKER (e.g. NOTICIA) top-left + "TODXS" wordmark top-right on the same '
                       'baseline; a BLACK-AND-WHITE framed photo in the middle, on a solid color field.'),
        # foto emoldurada no miolo (arquetipo_C.json): margens laterais ~6.3%.
        'photo_frame': {'feed': {'x': 6.34, 'y': 38.75, 'w': 86.85, 'h': 41.2}},
        'zonas': {
            'feed': [
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'header top-left (ex.: NOTICIA)',
                 'x': 6.34, 'y': 3.06, 'w': 40, 'h': 4, 'fs': 2.2, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': '#000000', 'max_linhas': 1},
                # manchete grande (medium), ate 5 linhas, abaixo do cabecalho.
                {'key': 'titulo', 'role': 'titulo', 'pos': 'headline below header (HERO, big)',
                 'x': 6.34, 'y': 8.19, 'w': 90.0, 'h': 30.0, 'fs': 13.0, 'font': 'medium',
                 'caps': True, 'align': 'left', 'color': '#000000', 'leading': 1.02,
                 'max_linhas': 5},
                {'key': 'apoio', 'role': 'subtitulo', 'pos': 'below the photo',
                 'x': 6.02, 'y': 83.86, 'w': 87.48, 'h': 10.88, 'fs': 2.6, 'font': 'regular',
                 'caps': False, 'align': 'left', 'color': '#000000', 'leading': 1.4,
                 'max_linhas': 3},
            ],
        },
        'wordmark': {'feed': {'x': 84.94, 'y': 3.55, 'w': 8.24}},
        'avoid': ['no band', 'black text on the solid color field', 'photo is BLACK AND WHITE'],
    },
    'C_DISPLAY': {
        'name': 'Manchete display + foto colorida na base (variante)',
        'formatos': ['feed'],
        'auto': False,                 # so via force
        'fundo': 'solid_photo',        # campo de cor + foto COLORIDA emoldurada (sem grayscale)
        'usa': {'selo': False, 'wordmark': True, 'specimen': True},
        'wordmark_color': '#000000',
        'bg_prompt': ('editorial portrait of {PESSOA}, sharp focus, vibrant; '
                      'NO text, NO logo, NO border, NO frame.'),
        'marca_desc': ('KICKER top-left + "TODXS" wordmark top-right; a BIG display headline is '
                       'the hero; a COLOR framed photo anchored at the base. No support text.'),
        # foto colorida ancorada na BASE (arquetipo_C_display.json).
        'photo_frame': {'feed': {'x': 6.8, 'y': 54.27, 'w': 87.34, 'h': 41.1}},
        'zonas': {
            'feed': [
                # kicker com a MESMA altura de maiuscula do logotipo (fs medido = 5.28)
                {'key': 'kicker', 'role': 'subtitulo', 'pos': 'header top-left',
                 'x': 7.12, 'y': 3.0, 'w': 70, 'h': 7, 'fs': 5.28, 'font': 'caps_small',
                 'caps': True, 'align': 'left', 'color': '#000000', 'max_linhas': 1},
                # titulo DISPLAY/BLACK GIGANTE (heroi ~39%), leading apertado 0.95.
                {'key': 'titulo', 'role': 'titulo', 'pos': 'display HERO (~39%)',
                 'x': 6.8, 'y': 11.5, 'w': 86.71, 'h': 39.27, 'fs': 15.0, 'font': 'display',
                 'caps': True, 'align': 'left', 'color': '#000000', 'leading': 0.95,
                 'max_linhas': 4},
            ],
        },
        # wordmark DOBRO da largura (mantendo a margem direita ~6.5%)
        'wordmark': {'feed': {'x': 77.69, 'y': 3.0, 'w': 15.82}},
        'avoid': ['no support text (the title carries the piece)',
                  'COLOR framed photo anchored at the base', 'black display headline on the color field'],
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
                 'caps': True, 'align': 'left', 'color': None, 'is_blocks': True,
                 'center_v': True},
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


# Direção fotográfica da TODXS (extraída dos dossiês das referências da KB):
# retratos editoriais marcantes, makeup artístico colorido, luz dramática/colorida,
# olhar firme, fundos com textura/caráter, cor saturada, energia Lampião.
BRAND_PHOTO_STYLE = (
    'TODXS editorial photography — BOLD and high-impact. '
    'Real LGBTQIA+ person whose QUEER identity reads clearly and connects to the topic '
    '(gay man, lesbian woman, bi, trans, travesti or non-binary — choose to fit the theme); '
    'VARIED ethnicity reflecting Brazilian diversity (Black, brown, white, Indigenous, Asian), '
    'varied bodies and ages; CONFIDENT DIRECT GAZE into the camera. '
    'Expressive artistic styling: vivid colorful eyeshadow/makeup, characterful '
    'wardrobe with saturated colors. DRAMATIC lighting — directional or a saturated '
    'colored gel light, strong shadows, cinematic mood. Characterful background '
    '(worn textured wall, intimate interior with a window, OR clean studio backdrop). '
    'Rich saturated color, shallow depth of field, tack-sharp on the eyes. '
    'Bold contemporary queer aesthetic energy. '
    'Authentic, dignified, powerful — NOT a generic stock photo.'
)


def foto_region(archetype: str, fmt: str, W: int, H: int):
    """(x,y,w,h) px da AREA VISIVEL da foto (acima da faixa, ou frame, ou full)."""
    w = WIREFRAMES[archetype]
    band = w.get('band', {}).get(fmt)
    if band:
        return (0, 0, W, int(round(band['y'] / 100.0 * H)))
    frame = w.get('photo_frame', {}).get(fmt)
    if frame:
        return (int(frame['x'] / 100.0 * W), int(frame['y'] / 100.0 * H),
                int(frame['w'] / 100.0 * W), int(frame['h'] / 100.0 * H))
    return (0, 0, W, H)  # full-bleed


def build_background_prompt(archetype: str, content: dict, color_hex: str, fmt: str,
                            brand_summary: str = '') -> str:
    """Prompt para o Gemini gerar o FUNDO (foto/cena), sem texto. '' = sem Gemini."""
    w = WIREFRAMES[archetype]
    tmpl = w.get('bg_prompt') or ''
    if not tmpl:
        return ''
    brand_ctx = ''
    if brand_summary:
        brand_ctx = (f"BRAND CONTEXT (who this is for): {str(brand_summary).strip()[:700]}\n\n")
    pessoa = content.get('pessoa') or 'a diverse LGBTQIA+ person'
    f = FORMATOS[fmt]
    pw, ph = (int(x) for x in f['px'].split('x'))
    _, _, fw, fh = foto_region(archetype, fmt, pw, ph)
    if fw > fh * 1.07:
        shape = f'SLIGHTLY LANDSCAPE (wider than tall, about {fw}x{fh}px)'
    elif fh > fw * 1.07:
        shape = f'PORTRAIT (taller than wide, about {fw}x{fh}px)'
    else:
        shape = f'NEAR-SQUARE (about {fw}x{fh}px)'
    body = tmpl.replace('{PESSOA}', pessoa).replace('{COR}', color_hex)
    titulo = ' '.join(str(content.get('titulo') or '').replace('\\n', ' ').split())
    apoio = ' '.join(str(content.get('apoio') or '').replace('\\n', ' ').split())
    if titulo:
        ctx = f'headline "{titulo}"' + (f' — support text: "{apoio[:200]}"' if apoio else '')
        msg = (f"MESSAGE TO CONVEY: the photo must VISUALLY express this post ({ctx}). "
               f"The subject and scene should CONNECT to the topic AND clearly read as part "
               f"of the LGBTQIA+ community relevant to it (a visibly queer person — e.g. a "
               f"gay/lesbian/trans person, or pride/affection cues) — NOT a generic portrait, "
               f"NOT a purely racial/ethnic read disconnected from the queer theme.\n\n")
    else:
        msg = ''
    duo = ''
    if w.get('gemini_duotone'):
        duo = (f"\n\nFINAL TREATMENT — DUOTONE: render the ENTIRE photo as a MONOCHROMATIC "
               f"DUOTONE in the color {color_hex}. Every tone is a shade of {color_hex} "
               f"(deep shadows ~black/dark {color_hex}, highlights ~light {color_hex}/white). "
               f"NO other hues anywhere — a single-color {color_hex} duotone print look. "
               f"Keep the bold styling and strong contrast, but unified in this one color.")
    return (
        f"Editorial photo, {shape}. {body}\n\n{brand_ctx}{msg}"
        f"FRAMING: TIGHT close-up / chest-up crop — the PERSON DOMINATES the frame, "
        f"filling ~75-85% of it; face and shoulders LARGE and prominent; eyes/head in the "
        f"upper-center; minimal empty background. Compose for THIS exact crop (nothing "
        f"important near the very bottom edge).\n\n"
        f"PHOTOGRAPHIC DIRECTION: {BRAND_PHOTO_STYLE}{duo}\n\n"
        f"CRITICAL: this is a PHOTOGRAPH ONLY. ABSOLUTELY NO text of any kind anywhere "
        f"in the image — no headlines, mastheads, captions, words, letters, numbers, "
        f"watermark, logo, UI or color band. Just a clean, bold photo of the person.")


def _zone_budget(z) -> str:
    """Descreve o orcamento de texto de uma zona (p/ o brain dimensionar o copy)."""
    n = z.get('max_linhas')
    if z.get('is_blocks'):
        return f"{z['key']} (2-3 blocos curtos, ~{n or 2} linhas cada)"
    if z['key'] == 'titulo':
        if z['font'] == 'display':
            return f"titulo (DISPLAY: CURTO e impactante, <= {n or 2} linhas / poucas palavras)"
        # titulo nao-display com varias linhas = MANCHETE jornalistica completa
        if (n or 0) >= 4:
            return (f"titulo (MANCHETE jornalistica COMPLETA: escreva a FRASE INTEIRA da "
                    f"noticia, ~12 a 16 palavras, para encher ~{n} linhas)")
        return f"titulo (CAIXA ALTA, curto, <= {n or 3} linhas)"
    cab = 'caixa alta' if z.get('caps') else 'caixa normal'
    return f"{z['key']} ({cab}, ate {n or 3} linhas)"


def describe_for_brain(fmt: str) -> str:
    """Resumo dos arquetipos validos no formato + orcamento de texto por zona."""
    lines = []
    for k in archetypes_for_format(fmt):
        w = WIREFRAMES[k]
        if w.get('auto') is False:      # variantes (ex.: B_DUO) so via force
            continue
        zs = [_zone_budget(z) for z in zones_for(k, fmt)]
        zonas = ' | '.join(zs) or '(sem texto de leitura)'
        lines.append(f"  {k} — {w['name']} | fundo={w['fundo']}\n      zonas: {zonas}")
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
    # Sem quebras explicitas: tanto o Pillow quanto o editor quebram por LARGURA.
    # Um '\n' no conteudo seria ignorado pelo Pillow mas forcado pelo editor
    # (pre-line) -> divergencia. Colapsa qualquer quebra/espaco em espaco unico.
    el = {
        'role': z['role'], 'content': ' '.join(str(content_text).replace('\\n', ' ').split()),
        'x_pct': z['x'], 'y_pct': z['y'] if y is None else y, 'width_pct': z['w'],
        'height_pct': z['h'] if h is None else h, 'font_size_pct': z['fs'],
        'weight': 'black' if z['role'] == 'titulo' else 'regular',
        'case': 'upper' if z.get('caps') else 'none',
        'align': z['align'], 'color': z['color'],
        '_font': z.get('font'),  # peso de uso -> pillow_render resolve _font_path
    }
    if z['color'] is None:
        el['color'] = _contrast_on(color_hex)
        # Centralizacao vertical na caixa SO quando a zona pede (center_v). Caso
        # contrario o texto alinha no topo e FLUI (titulo seguido do apoio).
        if z.get('center_v'):
            el['background_color'] = color_hex  # dispara has_bg (sem pill p/ titulo)
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
