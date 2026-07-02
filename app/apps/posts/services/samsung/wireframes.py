"""
Fichas declarativas dos arquétipos Samsung Healthcare (Relentless Innovation /
Samsung Medison). Formato único: feed 4:5 (1080x1350).

A geometria (bbox/px) vem dos wireframes anotados do dono (Relentless_wireframes
+ arquetipo_A.json). Aqui ela é ENRIQUECIDA com a camada tipográfica que o JSON
não traz: fonte (família Samsung SS), tamanho-alvo, nº máx. de linhas, leading,
caixa, cor (token) e alinhamento.

Contrato de zonas (vocabulário fixo do pipeline): image, product_hero,
product_pair, product_label, kicker, accent, title, body, signature,
event_name, event_meta, partner_logo, brand_lockup, frame, guide_line.

Data-driven: `WF()` lê as specs ativas do contextvar (o catálogo do banco pode
sobrepor o código, como em todxs). `seed_archetypes --org samsung-healthcare`
importa este WIREFRAMES para PostArchetype.
"""
import contextvars

# ---- Tokens globais (valem para os 4 arquétipos) -------------------------
CANVAS = (1080, 1350)          # feed 4:5

TOKENS = {
    'accent_blue': '#3874B0',  # azul accent das peças sociais (≠ Samsung Blue #1428A0)
    'white': '#FFFFFF',
    'gray_label': '#9AA6B2',
    'black': '#000000',
    'navy': '#0A1A2F',         # base do gradiente navy (B/C/D)
}

# Papéis tipográficos -> arquivo local (bundled em services/samsung/fonts/)
FONT_FILES = {
    'head_bold':    'SamsungSSHead-Bold.otf',
    'head_medium':  'SamsungSSHead-Medium.otf',
    'head_regular': 'SamsungSSHead-Regular.otf',
    'head_light':   'SamsungSSHead-Light.otf',
    'body_bold':    'SamsungSSBody-Bold.otf',
}

# Margem de texto padrão à esquerda (12.2% de 1080 ≈ 132px). Tudo ancora aqui.
TEXT_LEFT = 132


# ---- Arquétipos ----------------------------------------------------------
# Cada zona: key, category, role, box=[x,y,w,h] px, font (chave em FONT_FILES),
# fs (px alvo/máx), max_linhas, leading, color (token|hex), case
# (none|upper|title), align, fit (bool: encolhe p/ caber), valign (top|center).
WIREFRAMES = {
    'A': {
        'name': 'Foto-topo + agradecimento',
        'use': 'Cursos, institucional com pessoas, agradecimento a equipe/parceiros.',
        'formatos': ['feed'],
        'background': {'type': 'solid', 'color': 'black'},
        'zones': [
            {
                'key': 'photo_top', 'category': 'image', 'role': 'imagem',
                # Ancorada à DIREITA e sangra para CIMA e para a DIREITA (box
                # passa dos limites topo/direita p/ esses cantos ficarem retos e
                # fora do canvas). Margem só à esquerda (~100px). ÚNICO canto
                # arredondado = INFERIOR-ESQUERDO (radius grande) + BORDA AZUL.
                # Superior-esquerdo, superior-direito e inferior-direito = retos.
                'box': [100, -6, 1000, 652],
                'round_corners': ['bottom-left'],
                'radius': 130, 'fit': 'cover',
                'border': {'color': 'accent_blue', 'width': 3},
                'note': 'Ancorada à direita, sangra topo/direita, só inferior-esquerdo arredondado, borda azul.',
            },
            {
                'key': 'kicker', 'category': 'kicker', 'role': 'rotulo',
                'box': [TEXT_LEFT, 672, 470, 32],
                'font': 'head_medium', 'fs': 26, 'max_linhas': 1, 'leading': 1.0,
                'color': 'white', 'case': 'upper', 'align': 'left', 'fit': True,
                'tracking': 0.06,
            },
            {
                'key': 'title', 'category': 'title', 'role': 'titulo',
                'box': [TEXT_LEFT, 712, 620, 180],
                'font': 'head_bold', 'fs': 84, 'max_linhas': 2, 'leading': 1.04,
                'color': 'accent_blue', 'case': 'title', 'align': 'left', 'fit': True,
                'valign': 'top',
            },
            {
                'key': 'body', 'category': 'body', 'role': 'apoio',
                'box': [TEXT_LEFT, 905, 620, 180],
                'font': 'head_regular', 'fs': 42, 'max_linhas': 3, 'leading': 1.2,
                'color': 'white', 'case': 'none', 'align': 'left', 'fit': True,
                'valign': 'top',
            },
            {
                'key': 'signature_label', 'category': 'signature', 'role': 'assinatura',
                'box': [TEXT_LEFT, 1204, 470, 28],
                'font': 'head_regular', 'fs': 20, 'max_linhas': 1, 'leading': 1.0,
                'color': 'gray_label', 'case': 'none', 'align': 'left', 'fit': True,
            },
            {
                'key': 'signature_name', 'category': 'signature', 'role': 'assinatura',
                'box': [TEXT_LEFT, 1234, 470, 44],
                'font': 'head_bold', 'fs': 32, 'max_linhas': 1, 'leading': 1.0,
                'color': 'accent_blue', 'case': 'none', 'align': 'left', 'fit': True,
            },
            {
                'key': 'partner_logo', 'category': 'partner_logo', 'role': 'logo_parceiro',
                'box': [923, 675, 108, 94], 'fit': 'contain', 'align': 'right',
                'optional': True,
                'note': 'Logo de parceiro (ex.: Grupo Fleury). Topo-direito do bloco de texto.',
            },
        ],
        # FIXO em todas as peças, canto inferior-direito, escala fixa.
        'brand_lockup': {
            'key': 'brand_lockup', 'category': 'brand_lockup', 'role': 'logo_fixo',
            'box': [648, 1222, 373, 77], 'asset': 'relentless_white',
            'fit': 'contain', 'align': 'right', 'valign': 'center',
        },
    },

    'B': {
        'name': 'Produto-herói',
        'use': 'Destacar UMA tecnologia/feature. Produto grande sangrando.',
        'formatos': ['feed'],
        'background': {'type': 'gradient', 'light': '#33445C', 'dark': '#0A1420',
                       'cx': 0.62, 'cy': 0.30},
        # Aplicado só quando a foto é fundo-inteiro (imagem opaca/Gemini):
        # escurece a esquerda p/ o texto ficar legível.
        'scrim': {'color': '#0A1420', 'alpha': 210, 'to': 0.60},
        # Linha-guia azul fina em ╰: reta do topo, desce, curva p/ a direita
        # (radius ~ do arquétipo A) e segue reto até a direita. O texto fica à
        # DIREITA da vertical (x=90) — margem de texto = 135, sem sobreposição.
        'guide_line': {'x': 90, 'y0': 0, 'y1': 1165, 'curve': 48, 'x_end': 1080,
                       'color': 'accent_blue', 'width': 2},
        'zones': [
            {
                'key': 'product_hero', 'category': 'image', 'role': 'produto',
                # Render do produto (imagem de referência escolhida pelo usuário),
                # grande, centro-base, sangrando para baixo. Camada de fundo,
                # abaixo do texto. Por ora sem recorte (fundo cinza aparece).
                'box': [130, 455, 820, 950], 'fit': 'contain',
                'anchor': 'bottom', 'halign': 'center',
                'note': 'Produto grande, centro-base, sangra p/ baixo.',
            },
            {
                'key': 'title', 'category': 'title', 'role': 'titulo',
                'box': [135, 158, 810, 100],
                'font': 'head_bold', 'fs': 80, 'max_linhas': 2, 'leading': 1.0,
                'color': 'accent_blue', 'case': 'none', 'align': 'left', 'fit': True,
                'valign': 'top',
            },
            {
                'key': 'body', 'category': 'body', 'role': 'apoio',
                'box': [135, 262, 800, 372],
                'font': 'head_bold', 'fs': 56, 'max_linhas': 4, 'leading': 1.12,
                'color': 'white', 'case': 'none', 'align': 'left', 'fit': True,
                'valign': 'top',
            },
        ],
        'brand_lockup': {
            'key': 'brand_lockup', 'category': 'brand_lockup', 'role': 'logo_fixo',
            'box': [648, 1222, 373, 77], 'asset': 'relentless_white',
            'fit': 'contain', 'align': 'right', 'valign': 'center',
        },
    },
}


# ---- Data-driven: contextvar (banco sobre código, como em todxs) ----------
_active = contextvars.ContextVar('samsung_wireframes', default=None)


def set_wireframes(specs: dict):
    """Define as specs ativas para esta execução (usado pelo catálogo/DB)."""
    _active.set(dict(specs or {}))


def WF() -> dict:
    """Specs ativas (override do banco) ou o WIREFRAMES do código."""
    return _active.get() or WIREFRAMES


def archetypes_for_format(fmt: str) -> list:
    return [k for k, s in WF().items() if fmt in (s.get('formatos') or ['feed'])]


def background_mode(archetype: str) -> str:
    """'solid' (Pillow desenha o fundo) ou 'photo'/'gradient' (precisa de imagem)."""
    spec = WF().get(archetype) or {}
    return (spec.get('background') or {}).get('type', 'solid')
