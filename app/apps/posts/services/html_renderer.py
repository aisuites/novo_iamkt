"""
HTML Renderer — converte os elementos do layout_engine em HTML/CSS
pronto para renderização via Playwright (screenshot → PNG).

Cada elemento usa coordenadas em %_pct (relativas ao canvas),
mapeadas diretamente para position:absolute + top/left/width em CSS.
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CANVAS_W = 1080
_CANVAS_H = 1080


def build_html(
    elements: List[Dict[str, Any]],
    raw_image_url: str,
    logo_url: Optional[str],
    canvas_w: int = _CANVAS_W,
    canvas_h: int = _CANVAS_H,
    font_paths: Optional[Dict[str, str]] = None,
) -> str:
    """
    Retorna HTML completo com:
    - imagem Gemini como fundo (raw, sem Pillow)
    - elementos de texto e logo posicionados via CSS absoluto
    - fontes TTF embutidas via base64 @font-face
    """
    font_paths = font_paths or {}
    font_css = _build_font_css(font_paths)
    elements_html = _build_elements_html(elements, logo_url, canvas_w, canvas_h, font_paths)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{font_css}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    width: {canvas_w}px;
    height: {canvas_h}px;
    overflow: hidden;
    background: #fff;
}}

.canvas {{
    position: relative;
    width: {canvas_w}px;
    height: {canvas_h}px;
    overflow: hidden;
}}

.canvas-bg {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: cover;
}}

.el {{
    position: absolute;
    line-height: 1.2;
}}

.el-titulo {{
    font-weight: bold;
}}

.el-subtitulo {{
    font-weight: normal;
}}

.el-cta {{
    font-weight: bold;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.el-pill {{
    border-radius: 999px;
}}

.el-logo {{
    object-fit: contain;
    object-position: left center;
}}
</style>
</head>
<body>
<div class="canvas">
    <img class="canvas-bg" src="{raw_image_url}">
    {elements_html}
</div>
</body>
</html>"""


def _build_font_css(font_paths: Dict[str, str]) -> str:
    """Embute fontes TTF como base64 @font-face — uma declaracao por role.
    Mesmo quando varios roles compartilham o mesmo arquivo, cada role
    recebe sua propria @font-face. Cacheia o base64 por path para evitar
    re-encoding redundante."""
    css_lines = []
    cache = {}  # path -> (b64, fmt)
    for role, path in font_paths.items():
        if not path:
            continue
        if path not in cache:
            try:
                data = Path(path).read_bytes()
                b64 = base64.b64encode(data).decode()
                fmt = 'opentype' if path.endswith('.otf') else 'truetype'
                cache[path] = (b64, fmt)
            except Exception:
                logger.warning('[html_renderer] falha ao ler fonte %s', path)
                continue
        b64, fmt = cache[path]
        css_lines.append(
            f"@font-face {{font-family:'CustomFont_{role}';"
            f"src:url('data:font/{fmt};base64,{b64}') format('{fmt}');}}"
        )
    return '\n'.join(css_lines)


def _font_family(role: str, font_paths: Dict[str, str]) -> str:
    if font_paths.get(role):
        return f"'CustomFont_{role}', serif"
    return 'serif'


def _build_elements_html(
    elements: List[Dict[str, Any]],
    logo_url: Optional[str],
    canvas_w: int,
    canvas_h: int,
    font_paths: Optional[Dict[str, str]] = None,
) -> str:
    font_paths = font_paths or {}
    parts = []

    for el in elements:
        # Visibilidade — quando False, elemento e ocultado tanto no modal
        # quanto no PNG exportado (consistente com o olhinho do painel).
        if el.get('visible', True) is False:
            continue
        role = (el.get('role') or '').lower()
        x = el.get('x_pct', 0)
        y = el.get('y_pct', 0)
        w = el.get('width_pct', 10)
        h = el.get('height_pct', 5)

        if role == 'grafismo':
            forma = (el.get('forma') or '').lower()
            if forma in ('faixa', 'pill', 'retangulo'):
                cor = el.get('cor') or '#000000'
                raio_pct = float(el.get('raio_pct') or 0)
                raio_px = int(raio_pct / 100 * canvas_w)
                parts.append(
                    f'<div class="el el-pill" style="'
                    f'left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;'
                    f'background:{cor};border-radius:{raio_px}px;'
                    f'"></div>'
                )

        elif role == 'logo':
            if logo_url:
                parts.append(
                    f'<img class="el el-logo" src="{logo_url}" '
                    f'style="left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;">'
                )

        elif role == 'image':
            # Sticker — `url` deve ser data URI (Playwright nao busca URLs externas).
            # views_overlay._prepare_stickers_for_export injeta data URI antes do build.
            img_url = (el.get('url') or '').strip()
            if img_url:
                parts.append(
                    f'<img class="el el-image" src="{img_url}" '
                    f'style="left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;'
                    f'object-fit:contain;">'
                )

        elif role in ('titulo', 'subtitulo', 'cta'):
            content = (el.get('content') or '').strip()
            if not content and not el.get('visible_force', False):
                # CTA unificado pode nao ter content quando user esvaziou — pula
                if role != 'cta' or not el.get('background_color'):
                    continue
            color = el.get('color') or '#000000'
            weight = 'bold' if (el.get('weight') or '').lower() == 'bold' else 'normal'
            align = el.get('align') or 'left'
            font_size_pct = float(el.get('font_size_pct') or 5)
            font_size_px = font_size_pct / 100 * canvas_h

            # Usa a fonte embutida (CustomFont_<role>) se disponível
            font_role = role if role in font_paths else 'titulo'
            if font_paths.get(font_role):
                font_family = f"'CustomFont_{font_role}', serif"
            else:
                font_family = 'serif'

            css_class = f'el el-{role}'
            extra_styles = []
            inner_pad = ''

            # CTA unificado: pode ter background_color + radius_pct + padding
            bg = (el.get('background_color') or '').strip() if role == 'cta' else ''
            if bg:
                extra_styles.append(f'background:{bg}')
                radius_pct = float(el.get('radius_pct') or 0)
                if radius_pct > 0:
                    radius_px = int(radius_pct / 100 * canvas_w)
                    extra_styles.append(f'border-radius:{radius_px}px')
                ph_pct = float(el.get('padding_h_pct') or 0)
                pv_pct = float(el.get('padding_v_pct') or 0)
                if ph_pct or pv_pct:
                    ph_px = int(ph_pct / 100 * canvas_w)
                    pv_px = int(pv_pct / 100 * canvas_h)
                    inner_pad = f'padding:{pv_px}px {ph_px}px;'

            # Altura quando especificada (CTA precisa pra alinhar texto vertical)
            h_pct = el.get('height_pct')
            if h_pct:
                extra_styles.append(f'height:{float(h_pct):.3f}%')

            # CTA centraliza vertical+horizontal o texto dentro do box
            if role == 'cta':
                extra_styles.append('display:flex')
                extra_styles.append('align-items:center')
                extra_styles.append('justify-content:center')

            # Suporta quebra de linha (\n no content)
            extra_styles.append('white-space:pre-line')

            extras = ';'.join(extra_styles)
            if extras:
                extras += ';'

            parts.append(
                f'<div class="{css_class}" style="'
                f'left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;'
                f'color:{color};font-size:{font_size_px:.1f}px;'
                f'font-weight:{weight};text-align:{align};'
                f'font-family:{font_family};{extras}{inner_pad}'
                f'">{_escape(content)}</div>'
            )

    return '\n    '.join(parts)


def _escape(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
