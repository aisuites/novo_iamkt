"""
Adaptador entre o designer_payload (px-based, asset_path lógico) e o que o
renderer iamkt entende (layout_document em %_pct + URLs S3 reais).

Também rasteriza o wireframe_plan em PNG (para preview do user e mecanismo B
— envio ao Gemini como referência visual).
"""

import logging
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# Conversão de px → %_pct (designer_payload → layout_document)
# ============================================================

def _px_to_pct(px: float, ref: float) -> float:
    """Converte pixel para % de uma dimensão de referência."""
    if not ref:
        return 0.0
    return round((float(px) / float(ref)) * 100, 3)


def wireframe_plan_to_layout_document(
    designer_payload: Dict[str, Any],
    canvas_w: int,
    canvas_h: int,
    asset_resolver=None,
) -> Dict[str, Any]:
    """Converte designer_payload.wireframe_plan no formato layout_document
    usado por render_layout_document. Faz a conversão px→%_pct e resolve
    asset_path (logo, imagens uploadeadas) via asset_resolver(asset_path).
    """
    wireframe = (designer_payload or {}).get('wireframe_plan') or {}
    elements_raw = wireframe.get('elements') or []
    basis = min(canvas_w, canvas_h)

    out_elements: List[Dict[str, Any]] = []
    for el in elements_raw:
        try:
            converted = _convert_element(el, canvas_w, canvas_h, basis, asset_resolver)
            if converted:
                out_elements.append(converted)
        except Exception:
            logger.exception('[adapter] falha ao converter elemento: %s', el.get('id'))

    return {
        'elements': out_elements,
        '_render_order': wireframe.get('render_order') or [],
        '_designer_payload_meta': designer_payload.get('designer_meta', {}),
    }


def _convert_element(el: Dict[str, Any], W: int, H: int, basis: int,
                     asset_resolver) -> Optional[Dict[str, Any]]:
    el_type = (el.get('type') or '').lower()
    mech = (el.get('mechanism') or '').lower()
    pos = el.get('position') or {}
    size = el.get('size') or {}
    content = el.get('content') or {}

    x_pct = _px_to_pct(pos.get('x_px', 0), W)
    y_pct = _px_to_pct(pos.get('y_px', 0), H)
    w_pct = _px_to_pct(size.get('width_px', 0) or 0, W) if size.get('width_px') else None
    h_pct = _px_to_pct(size.get('height_px', 0) or 0, H) if size.get('height_px') else None

    base = {
        '_id': el.get('id'),
        '_layer': el.get('layer', 0),
        'x_pct': x_pct,
        'y_pct': y_pct,
    }
    if w_pct is not None:
        base['width_pct'] = w_pct
    if h_pct is not None:
        base['height_pct'] = h_pct

    # Anchor center -> ajusta x/y para top-left
    if pos.get('anchor') == 'center' and w_pct and h_pct:
        base['x_pct'] = x_pct - (w_pct / 2)
        base['y_pct'] = y_pct - (h_pct / 2)

    if el_type == 'text':
        base.update({
            'role': _infer_text_role(el.get('id')),
            'content': content.get('text', ''),
            'font_size_pct': _px_to_pct(content.get('font_size_px', 32), basis),
            'weight': content.get('font_weight', 'regular'),
            'color': content.get('color_hex'),
            'align': content.get('align', 'left'),
            'padding_pct': 0,
            'case': 'none',
        })
        return base
    if el_type == 'shape':
        forma_map = {
            'rounded_rect': 'faixa', 'rect': 'faixa', 'rectangle': 'faixa',
            'ellipse': 'selo', 'circle': 'selo',
            'line': 'linha',
        }
        forma = forma_map.get(content.get('shape_type', ''), 'faixa')
        base.update({
            'role': 'grafismo',
            'forma': forma,
            'cor': content.get('color_hex', '#000000'),
        })
        if content.get('border_radius_px'):
            base['raio_pct'] = _px_to_pct(content['border_radius_px'], W)
        return base
    if el_type == 'overlay':
        base.update({
            'role': 'grafismo',
            'forma': 'faixa',
            'cor': content.get('color_hex', '#000000'),
            'opacidade': int(100 * (content.get('opacity_0_to_1') or 0.5)),
            'raio_pct': 0,
        })
        return base
    if el_type == 'logo':
        base['role'] = 'logo'
        # Resolve asset
        if asset_resolver:
            url = asset_resolver(content.get('asset_path') or 'logo:auto')
            if url:
                base['_logo_url'] = url
        return base
    if el_type == 'image':
        # Gemini-generated image: NÃO entra no layout_document (Gemini gera a cena toda)
        # Asset-fornecida: ainda não suportamos paste direto pelo renderer atual.
        return None
    if el_type == 'background':
        # Background sólido: pulamos (Gemini gera o fundo) ou poderíamos preencher
        return None
    return None


def _infer_text_role(element_id: str) -> str:
    eid = (element_id or '').lower()
    if 'cta' in eid or 'button' in eid:
        return 'cta'
    if 'subtitle' in eid or 'subtitulo' in eid:
        return 'subtitulo'
    if 'headline' in eid or 'titulo' in eid or 'title' in eid:
        return 'titulo'
    if 'body' in eid or 'descric' in eid:
        return 'body'
    return 'titulo'  # fallback


# ============================================================
# Asset resolver (asset_path → URL S3)
# ============================================================

class AssetResolver:
    """Resolve `asset_path` lógico do designer em URL S3 presigned."""

    def __init__(self, post, ctx: dict, references: list):
        self.post = post
        self.ctx = ctx or {}
        self.references = references or []
        from apps.knowledge.models import KnowledgeBase
        self.kb = KnowledgeBase.objects.filter(organization=post.organization).first()

    def __call__(self, asset_path: str) -> Optional[str]:
        if not asset_path:
            return None
        ap = asset_path.lower().strip()
        # logo:auto, logo:bottom-right, etc → primeiro logo selecionado
        if ap.startswith('logo'):
            return self._resolve_logo()
        # image:upload_N → upload N do post
        if ap.startswith('image:upload_'):
            try:
                idx = int(ap.replace('image:upload_', '')) - 1
                if 0 <= idx < len(self.references):
                    return self.references[idx].get('url')
            except Exception:
                pass
        return None

    def _resolve_logo(self) -> Optional[str]:
        if not self.kb:
            return None
        from apps.core.services.s3_service import S3Service
        selected = set(self.ctx.get('selected_logo_ids') or [])
        for logo in self.kb.logos.all().order_by('-is_primary', 'logo_type'):
            if selected and logo.id not in selected:
                continue
            if logo.s3_key:
                try:
                    return S3Service.generate_presigned_download_url(
                        logo.s3_key, expires_in=86400
                    )
                except Exception:
                    pass
        return None


# ============================================================
# Wireframe PNG (mecanismo B — pra Gemini ver e pro user aprovar)
# ============================================================

# Cores semi-transparentes para tipos de elemento
_WIREFRAME_COLORS = {
    'text': (0, 150, 60, 90),
    'shape': (220, 80, 30, 80),
    'image': (90, 90, 90, 80),
    'overlay': (0, 0, 0, 60),
    'logo': (50, 120, 200, 100),
    'background': (200, 200, 200, 40),
    'icon': (140, 80, 180, 90),
}


def render_wireframe_png(designer_payload: Dict[str, Any],
                        canvas_w: int, canvas_h: int) -> bytes:
    """Renderiza um PNG do wireframe_plan: boxes coloridas por tipo com labels.
    Serve para: (1) preview pro user antes da aprovação, (2) mecanismo B —
    enviar ao Gemini como referência visual de layout.
    """
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (canvas_w, canvas_h), (245, 245, 248))
    draw = ImageDraw.Draw(img, 'RGBA')

    # Grade leve
    for i in range(11):
        c = (220, 220, 225)
        draw.line([(int(canvas_w * i / 10), 0), (int(canvas_w * i / 10), canvas_h)],
                  fill=c, width=1)
        draw.line([(0, int(canvas_h * i / 10)), (canvas_w, int(canvas_h * i / 10))],
                  fill=c, width=1)
    try:
        f_lbl = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            max(14, int(canvas_w / 60))
        )
        f_sm = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            max(11, int(canvas_w / 80))
        )
    except Exception:
        f_lbl = ImageFont.load_default()
        f_sm = f_lbl

    wireframe = designer_payload.get('wireframe_plan') or {}
    elements = wireframe.get('elements') or []
    for el in elements:
        try:
            _draw_wireframe_box(draw, el, canvas_w, canvas_h, f_lbl, f_sm)
        except Exception:
            logger.warning('[wireframe_png] falha em elemento %s', el.get('id'))

    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _draw_wireframe_box(draw, el: Dict[str, Any], W: int, H: int,
                        f_lbl, f_sm) -> None:
    pos = el.get('position') or {}
    size = el.get('size') or {}
    x = int(pos.get('x_px', 0) or 0)
    y = int(pos.get('y_px', 0) or 0)
    w = int(size.get('width_px', 0) or 60)
    h = int(size.get('height_px', 0) or 30)
    if pos.get('anchor') == 'center':
        x -= w // 2
        y -= h // 2
    el_type = (el.get('type') or '').lower()
    rgba = _WIREFRAME_COLORS.get(el_type, (100, 100, 100, 60))
    draw.rectangle([x, y, x + w, y + h], outline=rgba[:3] + (255,),
                   width=3, fill=rgba)
    label = (el.get('id') or el_type).upper()
    draw.text((x + 8, y + 6), label, fill=rgba[:3], font=f_lbl)
    sub = f'{el_type} / layer={el.get("layer", "?")} / mech={el.get("mechanism", "?")}'
    draw.text((x + 8, y + 6 + max(20, f_lbl.size + 4)), sub,
              fill=rgba[:3], font=f_sm)
