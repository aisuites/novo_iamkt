"""
Fichas (specs) dos ARQUETIPOS da VB Gastronomia — fonte: Wireframes_VB_Gastronomia.pdf.

Coordenadas em PIXEL sobre o canvas (feed 1080x1350, story 1080x1920). Cores são
tokens da paleta da marca (resolvidos em PALETTE). O motor (render.py) lê estas
fichas; texto é desenhado no Pillow, ilustração via a skill de ilustração, foto
via Gemini. Validação 1 a 1 — arquetipos vão sendo ligados conforme aprovados.
"""

PALETTE = {
    'oliva': '#666651', 'laranja': '#F95B00', 'terracota': '#C68B71',
    'cinza': '#CCCCCC', 'vinho': '#71140D', 'creme': '#EAE0D3',
    'preto': '#000000', 'amarelo': '#FFF15F', 'branco': '#FFFFFF',
}

# Fontes (stand-in Barlow Condensed para Acumin Condensed)
FONT_KEYS = {'light', 'medium', 'semibold'}

SPECS = {
    # 01 — FEED · SOLID · "Hook sobre cor sólida"
    '01': {
        'name': 'Hook sobre cor sólida',
        'formato': 'feed', 'canvas': [1080, 1350],
        'bg': {'type': 'solid', 'color': 'oliva'},
        'safe': 90,
        'zones': [
            {'key': 'titulo', 'font': 'light', 'fs': 84, 'color': 'creme',
             'x': 90, 'y': 150, 'w': 770, 'h': 250, 'leading': 1.05,
             'max_linhas': 4, 'case': 'none'},
            {'key': 'apoio', 'font': 'semibold', 'fs': 62, 'color': 'creme',
             'x': 90, 'y': 470, 'w': 770, 'h': 150, 'leading': 1.05,
             'max_linhas': 2, 'case': 'none'},
        ],
        'ilustracao': {'x': 40, 'y': 760, 'w': 1000, 'h': 520, 'fit': 'height'},
        # 01 NAO usa logo (a referencia/peca nao tem assinatura).
    },

    # 02 — FEED · PHOTO · "Foto protagonista + assinatura"
    # A comida ocupa o quadro (foto Gemini OU upload); grafismos no canto + simbolo.
    '02': {
        'name': 'Foto protagonista + assinatura',
        'formato': 'feed', 'canvas': [1080, 1350],
        'bg': {'type': 'photo'},
        'safe': 90,
        'zones': [],  # sem texto na arte
        'foto': {'tema': 'comida'},  # gera foto via Gemini (ou upload no futuro)
        # Cluster: garfo + circulo + faca, PONTA para a DIREITA (rot 270), maiores,
        # empilhados, e fazendo BLEED na borda esquerda (box x<0 -> pedaco cortado).
        'grafismo_cluster': {
            'box': {'x': -65, 'y': 110, 'w': 300, 'h': 520},
            'recipe': {'canvas': [300, 520], 'bg': 'transparent', 'pecas': [
                {'tipo': 'asset', 'nome': 'garfo', 'cor': 'terracota',
                 'cx': 101, 'cy': 95, 'escala': 0.397, 'rot': 270},
                {'tipo': 'circulo', 'cor': 'terracota', 'cx': 94, 'cy': 260, 'r': 94},
                {'tipo': 'asset', 'nome': 'faca', 'cor': 'terracota',
                 'cx': 100, 'cy': 425, 'escala': 0.334, 'rot': 270},
            ]},
        },
        'logo': {'asset': 'simbolo', 'color': 'preto',
                 'x': 760, 'y': 820, 'w': 190, 'h': 150, 'fit': 'contain'},
    },

    # 03 — FEED · PHOTO+TEXT · "Informativo (texto + foto emoldurada)"
    # Fundo creme; título vinho; FOTO EMOLDURADA à esquerda; texto de apoio VERTICAL
    # (rotacionado 90°); grafismo garfo laranja (pontas pra cima) no canto inf-dir.
    '03': {
        'name': 'Informativo (texto + foto emoldurada)',
        'formato': 'feed', 'canvas': [1080, 1350],
        'bg': {'type': 'solid', 'color': 'creme'},
        'safe': 90,
        'foto': {'tema': 'cozinha'},
        # +15% de altura mantendo a BASE fixa (base = 1280; cresce pra cima).
        'foto_frame': {'x': 90, 'y': 406, 'w': 560, 'h': 874},
        'zones': [
            {'key': 'titulo', 'font': 'medium', 'fs': 76, 'color': 'vinho',
             'x': 90, 'y': 110, 'w': 620, 'h': 190, 'leading': 1.05,
             'max_linhas': 2, 'case': 'none'},
            # apoio vertical: MESMO tamanho do título (76px) mas peso mais LEVE
            # (light); até 2 linhas; posicionado ACIMA do garfo e centralizado
            # horizontalmente nele.
            {'key': 'apoio', 'font': 'light', 'fs': 76, 'color': 'oliva',
             'x': 700, 'y': 360, 'w': 200, 'h': 980, 'leading': 1.05,
             'max_linhas': 2, 'case': 'none', 'rot': 90, 'above_grafismo': True},
        ],
        # garfo laranja (pontas pra cima), ~25% mais acima, ainda com BLEED inferior.
        'grafismo_cluster': {
            'box': {'x': 780, 'y': 1060, 'w': 260, 'h': 340},
            'recipe': {'canvas': [260, 340], 'bg': 'transparent', 'pecas': [
                {'tipo': 'asset', 'nome': 'garfo', 'cor': 'laranja',
                 'cx': 130, 'cy': 175, 'escala': 0.62, 'rot': 0},
            ]},
        },
    },

    # 04 — STORY · SOLID · "Institucional sobre cor + padrão"
    # Fundo terracota; mensagem institucional + texto de apoio (à direita, creme);
    # logo VB grande (assinatura horizontal); faixa de grafismos (grid de carimbos)
    # ocupando 40% da altura no rodapé. SEM header/réguas/@handle.
    '04': {
        'name': 'Institucional sobre cor + padrão',
        'formato': 'story', 'canvas': [1080, 1920],
        'bg': {'type': 'solid', 'color': 'terracota'},
        'safe': 70,
        'zones': [
            # 3. Título institucional — à direita, creme, light 70, até 5 linhas
            {'key': 'titulo', 'font': 'light', 'fs': 70, 'color': 'creme',
             'x': 430, 'y': 290, 'w': 580, 'h': 380, 'leading': 1.12,
             'max_linhas': 5, 'case': 'none', 'align': 'right'},
            # 4. Texto de APOIO (era CTA) — à direita, VINHO (cor DIFERENTE do título
            #    creme), light 60, 2 linhas; ancorado logo ABAIXO do título real.
            {'key': 'apoio', 'font': 'light', 'fs': 60, 'color': 'vinho',
             'x': 430, 'y': 720, 'w': 580, 'h': 150, 'leading': 1.12,
             'max_linhas': 2, 'case': 'none', 'align': 'right',
             'follow_zone': 'titulo', 'follow_gap': 60},
        ],
        # 5. Logo VB Gastronomia (assinatura horizontal) — creme, ALINHADO À
        #    ESQUERDA (margem esq = 30% da largura do logo). DOBRO do tamanho.
        'logo': {'asset': 'horizontal', 'color': 'creme', 'left_margin_w': 0.30,
                 'x': 70, 'y': 870, 'w': 880, 'h': 220, 'fit': 'contain'},
        # 6. Faixa de grafismos (grid 5x5) — carimbos ~30% maiores com BLEED: topo
        #    fixo (y=1152), cresce p/ os lados (x centrado negativo) e p/ baixo,
        #    cortando nas laterais e no rodapé.
        'grafismo_grid': {
            # 5x5 com as 5 LINHAS presentes; as das bordas CORTAM pra fora (bleed,
            # como o garfo): topo fixo (y=1152), colunas laterais e última linha
            # vazam. Cada carimbo escala UNIFORME (preserva proporção, nunca achata).
            'grid': [5, 5], 'x': -162, 'y': 1152, 'w': 1404, 'h': 850, 'pad': 0.05,
            'cores': ['preto', 'vinho', 'oliva'], 'destaque': 'amarelo',
        },
    },
}


# ---- Data-driven: contextvar (banco sobre código, como em todxs/samsung) ----
import contextvars

_active = contextvars.ContextVar('vb_specs', default=None)


def set_specs(specs: dict):
    """Define as specs ativas para esta execução (usado pelo catálogo/DB)."""
    _active.set(dict(specs or {}))


def SP() -> dict:
    """Specs ativas (override do banco) ou o SPECS do código."""
    return _active.get() or SPECS


def archetypes_for_format(fmt):
    return [k for k, v in SP().items() if v.get('formato') == fmt]
