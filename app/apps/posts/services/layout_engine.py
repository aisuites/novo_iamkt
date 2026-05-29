"""
Layout Engine — converte card estratégico + copy em elementos prontos para
render_layout_document (Pillow). Nenhuma IA envolvida.

Filosofia tipográfica:
  A hierarquia define o tamanho da fonte — não o espaço disponível.
  Usamos uma escala baseada em "rem" do canvas (canvas_h / BASE_DIVISOR).
  O fitting só entra se o texto for genuinamente longo demais para o formato.

  base = canvas_h / 35   (35 "linhas" de referência vertical)
  H1   = 3.0 × base      → título de impacto
  H2   = 1.4 × base      → subtítulo
  CTA  = 1.2 × base      → call to action
  body = 1.0 × base      → corpo (não aparece na arte, só na legenda)

Regras de layout:
  - titulo:    ancora no TOPO da zona de texto (H1)
  - subtitulo: segue o título com gap (H2)
  - cta:       ancora na BASE da zona de texto (pill)
  - logo:      posição do modal_choice

Regra do CTA pill (padrão quando KB não define estilo de botão):
  - Forma: retângulo com cantos totalmente arredondados (pill = radius=height/2)
  - Padding: 10px horizontal, 7px vertical
  - Cor de fundo: cor primária da marca
  - Cor do texto: #FFFFFF
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Divisor base da escala tipográfica (canvas_h / BASE_DIVISOR = 1rem do canvas)
BASE_DIVISOR = 35

# Multiplicadores tipográficos
SCALE = {
    'h1':   3.0,   # título — impacto máximo
    'h2':   1.4,   # subtítulo
    'cta':  1.2,   # call to action
    'body': 1.0,   # corpo (referência)
}

# Padding padrão do pill CTA (px absolutos)
CTA_PILL_PAD_H = 10  # horizontal
CTA_PILL_PAD_V = 7   # vertical

# Fonte fallback
_DEJAVU_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU_REG  = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def build_elements(
    strategic_payload: Dict[str, Any],
    copy_payload: Dict[str, Any],
    canvas_w: int,
    canvas_h: int,
    paleta: List[Dict[str, Any]],
    fonts: Dict[str, str],               # {'titulo': path, 'subtitulo': path, 'cta': path}
    modal_choices: Dict[str, Any] = None,
    kb_cta_style: Optional[Dict] = None, # futuro: estilo de botão da KB
    bg_color: Optional[str] = None,      # cor dominante do fundo (paleta_observada) — para contraste do subtítulo
) -> List[Dict[str, Any]]:
    """
    Retorna lista de elementos prontos para render_layout_document.
    Coordenadas em %_pct relativas ao canvas.
    """
    fmt     = strategic_payload.get('format') or {}
    safe_z  = fmt.get('safe_zone_inset_px') or {}
    vd      = strategic_payload.get('visual_direction') or {}
    modal   = modal_choices or {}

    safe_t = int(safe_z.get('top',    60))
    safe_b = int(safe_z.get('bottom', 60))
    safe_l = int(safe_z.get('left',   60))
    safe_r = int(safe_z.get('right',  60))

    # Zona de texto: extrai largura, lado e posição X da composição do strategist
    zone_pct, zone_side, zone_x_pct = _extract_text_zone(vd.get('composition') or '')
    zone_w_px = int(canvas_w * zone_pct / 100)
    # X: usa coordenada explícita do strategist se disponível; senão usa safe margin
    if zone_x_pct > 0:
        zone_x_px = int(canvas_w * zone_x_pct / 100)
    else:
        zone_x_px = safe_l if zone_side == 'left' else (canvas_w - zone_w_px - safe_r)
    logger.info(
        '[layout_engine] zona texto: %d%% (%s) x=%dpx w=%dpx',
        zone_pct, zone_side, zone_x_px, zone_w_px,
    )
    zone_top  = safe_t
    zone_bot  = canvas_h - safe_b

    # Copy
    variant    = _pick_variant(copy_payload)
    copy       = variant.get('copy') or {}
    headline   = (copy.get('headline') or '').strip()
    # subtitulo: campo dedicado para arte visual (max 12 palavras, gerado pelo copywriter)
    # body/legenda NÃO vai na imagem — fica apenas na postagem da rede social
    body       = (copy.get('subtitulo') or '').strip()
    cta_text   = (copy.get('cta') or '').strip()

    # Cores
    cor_titulo   = _primary_color(paleta, exclude_white=True) or '#23282A'
    cor_cta_bg   = _primary_color(paleta, exclude_white=True) or '#00AC46'
    # Subtítulo: contraste automático contra o fundo da imagem
    # Se bg_color informado → luminância decide; senão usa cor da marca (seguro na maioria dos fundos)
    cor_subtitulo = _contrast_color(bg_color, fallback=cor_titulo)

    # Fontes
    f_titulo   = fonts.get('titulo')   or _DEJAVU_BOLD
    f_sub      = fonts.get('subtitulo') or _DEJAVU_REG
    f_cta      = fonts.get('cta')      or fonts.get('titulo') or _DEJAVU_BOLD

    elements = []

    # ── Escala tipográfica (rem do canvas) ─────────────────────────────────
    base_px = canvas_h / BASE_DIVISOR
    h1_px   = int(base_px * SCALE['h1'])
    h2_px   = int(base_px * SCALE['h2'])
    cta_px  = int(base_px * SCALE['cta'])
    logger.info(
        '[layout_engine] escala: base=%.1fpx h1=%dpx h2=%dpx cta=%dpx',
        base_px, h1_px, h2_px, cta_px,
    )

    # ── 1. HEADLINE (ancora topo, H1) ──────────────────────────────────────
    # Tamanho definido pela escala (H1). Só reduz se o texto não couber em
    # 2 linhas dentro da largura da zona — e loga aviso se isso acontecer.
    hl_font_size, hl_lines, hl_h_px = _fit_font(
        headline, f_titulo, zone_w_px, max_lines=3,
        size_start=h1_px,
        size_min=int(h1_px * 0.6),
    )
    if hl_font_size < h1_px:
        logger.warning(
            '[layout_engine] headline reduziu H1 %dpx→%dpx '
            '(texto longo demais para %dpx em 2 linhas)',
            h1_px, hl_font_size, zone_w_px,
        )

    elements.append({
        'role':          'titulo',
        'content':       headline,
        'x_pct':         _pct(zone_x_px, canvas_w),
        'y_pct':         _pct(zone_top, canvas_h),
        'width_pct':     _pct(zone_w_px, canvas_w),
        'height_pct':    _pct(hl_h_px + int(base_px * 0.5), canvas_h),
        'font_size_pct': _pct(hl_font_size, canvas_h),
        'color':         cor_titulo,
        'weight':        'bold',
        'align':         'left',
        'padding_pct':   0,
    })
    hl_bottom = zone_top + hl_h_px + int(base_px * 0.5)

    # ── 2. CTA PILL (ancora base, CTA scale) ───────────────────────────────
    cta_font_size, _, cta_line_h = _fit_font(
        cta_text, f_cta, zone_w_px - CTA_PILL_PAD_H * 2, max_lines=1,
        size_start=cta_px,
        size_min=int(cta_px * 0.6),
    )
    pill_h   = cta_line_h + CTA_PILL_PAD_V * 2
    pill_w   = _measure_text_width(cta_text, f_cta, cta_font_size) + CTA_PILL_PAD_H * 2
    pill_w   = min(pill_w, zone_w_px)
    radius   = pill_h // 2  # pill = totalmente arredondado

    pill_x   = zone_x_px
    pill_y   = zone_bot - pill_h - int(canvas_h * 0.02)

    # Shape do pill (grafismo rounded)
    elements.append({
        'role':       'grafismo',
        'forma':      'faixa',
        'x_pct':      _pct(pill_x, canvas_w),
        'y_pct':      _pct(pill_y, canvas_h),
        'width_pct':  _pct(pill_w, canvas_w),
        'height_pct': _pct(pill_h, canvas_h),
        'cor':        cor_cta_bg,
        'raio_pct':   _pct(radius, canvas_w),
        'opacidade':  100,
    })
    # Texto do CTA centralizado dentro do pill
    elements.append({
        'role':          'cta',
        'content':       cta_text,
        'x_pct':         _pct(pill_x + CTA_PILL_PAD_H, canvas_w),
        'y_pct':         _pct(pill_y + CTA_PILL_PAD_V, canvas_h),
        'width_pct':     _pct(pill_w - CTA_PILL_PAD_H * 2, canvas_w),
        'height_pct':    _pct(cta_line_h, canvas_h),
        'font_size_pct': _pct(cta_font_size, min(canvas_w, canvas_h)),
        'color':         '#FFFFFF',
        'weight':        'bold',
        'align':         'center',
        'padding_pct':   0,
    })
    cta_top = pill_y

    # ── 3. SUBTÍTULO (flow entre headline e CTA) ───────────────────────────
    if body:
        gap      = int(canvas_h * 0.025)
        sub_top  = hl_bottom + gap
        sub_bot  = cta_top - gap
        sub_h_av = max(40, sub_bot - sub_top)

        sub_font_size, _, sub_h = _fit_font(
            body, f_sub, zone_w_px, max_lines=3,
            size_start=h2_px,
            size_min=int(h2_px * 0.7),
            max_height=sub_h_av,
        )
        elements.append({
            'role':          'subtitulo',
            'content':       body,
            'x_pct':         _pct(zone_x_px, canvas_w),
            'y_pct':         _pct(sub_top, canvas_h),
            'width_pct':     _pct(zone_w_px, canvas_w),
            'height_pct':    _pct(sub_h, canvas_h),  # altura real do texto, não o espaço disponível
            'font_size_pct': _pct(sub_font_size, canvas_h),
            'color':         cor_subtitulo,
            'weight':        'regular',
            'align':         'left',
            'padding_pct':   0,
        })

    # ── 4. LOGO ────────────────────────────────────────────────────────────
    # Usa os mesmos insets do safe_zone para garantir respiro consistente.
    logo_pos = (modal.get('logo_position') or 'bottom-right').lower()
    lw_px    = int(canvas_w * 0.15)
    lh_px    = int(canvas_h * 0.12)

    if 'right' in logo_pos:
        lx = canvas_w - lw_px - safe_r
    else:
        lx = safe_l
    if 'bottom' in logo_pos:
        ly = canvas_h - lh_px - safe_b
    elif 'top' in logo_pos:
        ly = safe_t
    else:
        ly = canvas_h - lh_px - safe_b

    elements.append({
        'role':       'logo',
        'x_pct':      _pct(lx, canvas_w),
        'y_pct':      _pct(ly, canvas_h),
        'width_pct':  _pct(lw_px, canvas_w),
        'height_pct': _pct(lh_px, canvas_h),
    })

    logger.info(
        '[layout_engine] canvas=%dx%d zone=%d%% (%s) '
        'hl_size=%dpx sub_size=%dpx cta_size=%dpx pill=%dx%dpx r=%dpx',
        canvas_w, canvas_h, zone_pct, zone_side,
        hl_font_size,
        sub_font_size if body else 0,
        cta_font_size, pill_w, pill_h, radius,
    )
    return elements


# ── helpers ────────────────────────────────────────────────────────────────

def _extract_text_zone(composition: str) -> Tuple[int, str, int]:
    """Extrai (width_pct, side, x_pct) da zona de texto do card.

    Suporta dois formatos emitidos pelo strategist:
      A) Estruturado: "bloco de texto ... (x=5% y=30% w=40% h=40%)"
      B) Livre:       "esquerda (35%)"  ou  "left 35%"

    Retorna (width_pct, side, x_pct).
    """
    lower = composition.lower()

    # Formato A — coordenadas inline emitidas pelo strategist
    # ex: "bloco de texto com headline ... (x=5% y=30% w=40% h=40%)"
    for keyword in ('bloco de texto', 'headline e subtítulo', 'headline e subtitulo', 'texto com headline'):
        m = re.search(
            keyword + r'[^(]*\(x=(\d+)%[^w]*w=(\d+)%',
            lower,
        )
        if m:
            x_pct = int(m.group(1))
            w_pct = int(m.group(2))
            side = 'left' if x_pct < 50 else 'right'
            return w_pct, side, x_pct

    # Formato B — "esquerda (35%)" / "left 35%"
    # usa palavra-limite \b para não capturar dígitos dentro de hex (#C2A989)
    m = re.search(r'\b(?:esquerda|left)\b[^(]*\((\d+)\s*%', lower)
    if m:
        return int(m.group(1)), 'left', 0
    m = re.search(r'\b(?:esquerda|left)\b\s+(\d+)\s*%', lower)
    if m:
        return int(m.group(1)), 'left', 0
    m = re.search(r'\b(?:direita|right)\b[^(]*\((\d+)\s*%', lower)
    if m:
        return int(m.group(1)), 'right', 0
    m = re.search(r'\b(?:direita|right)\b\s+(\d+)\s*%', lower)
    if m:
        return int(m.group(1)), 'right', 0

    # fallback: esquerda 38%
    return 38, 'left', 0


def _fit_font(
    text: str, font_path: str, max_width: int, max_lines: int,
    size_start: int, size_min: int, max_height: int = 99999,
) -> Tuple[int, List[str], int]:
    """Encontra o maior font_size que faz o texto caber em max_lines × max_width.
    Retorna (font_size, lines, total_height_px).
    """
    from PIL import ImageFont, ImageDraw, Image

    def try_size(sz):
        try:
            font = ImageFont.truetype(font_path, sz)
        except Exception:
            font = ImageFont.load_default()
        lines = _wrap_text(text, font, max_width)
        lh = int(sz * 1.2)
        return font, lines, lh * len(lines)

    size = max(size_min, min(size_start, 200))
    while size >= size_min:
        font, lines, total_h = try_size(size)
        if len(lines) <= max_lines and total_h <= max_height:
            return size, lines, total_h
        size -= 1
    font, lines, total_h = try_size(size_min)
    return size_min, lines[:max_lines], int(size_min * 1.2) * min(len(lines), max_lines)


def _wrap_text(text: str, font, max_width: int) -> List[str]:
    """Quebra texto em linhas respeitando max_width."""
    from PIL import ImageDraw, Image
    img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(img)
    words = text.split()
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def _measure_text_width(text: str, font_path: str, size: int) -> int:
    from PIL import ImageFont, ImageDraw, Image
    try:
        font = ImageFont.truetype(font_path, size)
    except Exception:
        font = ImageFont.load_default()
    img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(img)
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _is_light(hex_color: str) -> bool:
    """True se a cor for clara (luminância relativa > 0.5)."""
    h = (hex_color or '').lstrip('#')
    if len(h) != 6:
        return True
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.5
    except ValueError:
        return True


def _contrast_color(bg_hex: Optional[str], fallback: str = '#23282A') -> str:
    """Retorna cor de texto com contraste adequado para o fundo informado.
    Se bg_hex não fornecido, usa fallback (cor da marca).
    """
    if not bg_hex:
        return fallback
    return '#23282A' if _is_light(bg_hex) else '#FFFFFF'


def _primary_color(paleta: List[Dict], exclude_white: bool = True) -> Optional[str]:
    for c in (paleta or []):
        hex_val = (c.get('hex') or '').upper()
        if not hex_val:
            continue
        if exclude_white and hex_val in ('#FFFFFF', '#FFF', '#FEFEFE'):
            continue
        return hex_val
    return None


def _pct(px: int, total: int) -> float:
    return round(px / total * 100, 3)


def _pick_variant(copy_payload: Dict) -> Dict:
    variants = copy_payload.get('variants') or []
    if not variants:
        return {}
    rec_id = copy_payload.get('recommended_variant') or 'v1'
    return next((v for v in variants if v.get('id') == rec_id), variants[0])
