"""
Layout wireframes — regras de design padrao usadas como fallback quando a
KB nao tem references analisaveis para o brand_layout_analyzer extrair.

Output: dict no mesmo schema de KnowledgeBase.brand_layout_spec, para que
o smart pillow overlay use sem precisar saber a origem.
"""

from typing import Dict


# Regras por aspect ratio — derivadas de heuristicas de design de social media:
# regra dos tercos, hierarquia visual, gravidade leitura ocidental (TR -> BL).
WIREFRAME_BY_ASPECT: Dict[str, Dict] = {
    '1:1': {
        'title_position': 'top-left',
        'title_size_pct': 8,
        'title_weight': 'bold',
        'title_color_hint': 'auto_contrast',
        'subtitle_offset': 'below_title',
        'subtitle_size_pct': 3.5,
        'subtitle_weight': 'regular',
        'logo_position': 'top-right',
        'logo_size_pct': 12,
        'cta_style': 'pill',
        'cta_position': 'bottom-center',
        'alignment': 'left',
        'padding_pct': 5,
        'background_treatment': 'none',
    },
    '4:5': {
        'title_position': 'top-left',
        'title_size_pct': 7.5,
        'title_weight': 'bold',
        'title_color_hint': 'auto_contrast',
        'subtitle_offset': 'below_title',
        'subtitle_size_pct': 3,
        'subtitle_weight': 'regular',
        'logo_position': 'top-right',
        'logo_size_pct': 11,
        'cta_style': 'pill',
        'cta_position': 'bottom-left',
        'alignment': 'left',
        'padding_pct': 5,
        'background_treatment': 'none',
    },
    '9:16': {  # Stories / Reels — vertical
        'title_position': 'top-center',
        'title_size_pct': 6.5,
        'title_weight': 'bold',
        'title_color_hint': 'auto_contrast',
        'subtitle_offset': 'below_title',
        'subtitle_size_pct': 2.8,
        'subtitle_weight': 'regular',
        'logo_position': 'top-center',
        'logo_size_pct': 10,
        'cta_style': 'pill',
        'cta_position': 'bottom-center',
        'alignment': 'center',
        'padding_pct': 6,
        'background_treatment': 'none',
    },
    '16:9': {  # LinkedIn cover / banner
        'title_position': 'center-left',
        'title_size_pct': 12,   # mais alto pq canvas e horizontal
        'title_weight': 'bold',
        'title_color_hint': 'auto_contrast',
        'subtitle_offset': 'below_title',
        'subtitle_size_pct': 5,
        'subtitle_weight': 'regular',
        'logo_position': 'top-right',
        'logo_size_pct': 12,
        'cta_style': 'pill',
        'cta_position': 'bottom-left',
        'alignment': 'left',
        'padding_pct': 5,
        'background_treatment': 'none',
    },
    '1200x630': {  # Facebook/LinkedIn feed retrato e wide
        'title_position': 'center-left',
        'title_size_pct': 13,
        'title_weight': 'bold',
        'title_color_hint': 'auto_contrast',
        'subtitle_offset': 'below_title',
        'subtitle_size_pct': 5,
        'subtitle_weight': 'regular',
        'logo_position': 'top-right',
        'logo_size_pct': 12,
        'cta_style': 'pill',
        'cta_position': 'bottom-left',
        'alignment': 'left',
        'padding_pct': 5,
        'background_treatment': 'none',
    },
}


def wireframe_for_aspect(aspect_ratio: str, formato_px: str = '') -> Dict:
    """
    Retorna o spec wireframe adequado ao aspect ratio. Se nao reconhecer,
    calcula heuristicamente baseado em w/h.
    """
    if aspect_ratio in WIREFRAME_BY_ASPECT:
        return dict(WIREFRAME_BY_ASPECT[aspect_ratio])

    # Tenta formato_px (ex: '1200x630')
    if formato_px in WIREFRAME_BY_ASPECT:
        return dict(WIREFRAME_BY_ASPECT[formato_px])

    # Heuristico por w/h se vier algo como '1200x630'
    try:
        w_str, h_str = formato_px.lower().split('x')
        w, h = int(w_str), int(h_str)
        ratio = w / h if h else 1.0
    except Exception:
        ratio = 1.0

    if ratio > 1.5:
        return dict(WIREFRAME_BY_ASPECT['16:9'])
    elif ratio < 0.7:
        return dict(WIREFRAME_BY_ASPECT['9:16'])
    elif ratio < 0.9:
        return dict(WIREFRAME_BY_ASPECT['4:5'])
    return dict(WIREFRAME_BY_ASPECT['1:1'])
