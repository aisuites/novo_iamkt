"""
Compose Engine — renderizador deterministico de templates visuais para posts.

Recebe um VisualTemplate.template_spec + content data + brand_visual_spec
e produz uma imagem PNG via Pillow, sem depender de IA para layout.

A IA gera somente o conteudo visual de algumas regions (slot type=image
com content_source=ai_generated_scene), tudo o resto e composto por codigo
respeitando regras do brandguide.

Fase 5 (esta implementacao):
- Renderiza texto, imagens placeholder, logo placeholder, grafismo placeholder
- Resolve tokens de cor (color_token) consultando brand_visual_spec.cores
- Fontes do sistema (DejaVu); fontes reais (Supreme, IBM Plex Sans) vem na F6

Fases seguintes:
- F6 Font Resolver: download e cache de TTFs reais
- F7 Asset Resolver: carrega Logo / BrandgraficModule reais do S3 e aplica
- F8 AI scene: integra com Gemini para gerar imagem real nas regions ai_*
"""

import logging
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

# Tamanhos padrao por aspect ratio (canvas de saida)
ASPECT_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    '1:1': (1080, 1080),
    '4:5': (1080, 1350),
    '9:16': (1080, 1920),
    '16:9': (1920, 1080),
}

# Fontes do sistema disponiveis no container Ubuntu (DejaVu)
SYSTEM_FONTS = {
    'regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'oblique': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
}

# Tipos de region textuais (recebem texto desenhado)
TEXT_TYPES = {'title', 'subtitle', 'body_text', 'secondary_text', 'tag'}


# ============================================================
# COMPOSE ENGINE
# ============================================================

class ComposeEngine:
    """Renderiza um template_spec em PNG via Pillow."""

    def __init__(
        self,
        template_spec: Dict[str, Any],
        content: Dict[str, Any],
        brand_visual_spec: Optional[Dict[str, Any]] = None,
        size_override: Optional[Tuple[int, int]] = None,
        kb=None,
    ):
        from .asset_resolver import AssetResolver
        from .font_resolver import FontResolver

        self.spec = template_spec or {}
        self.content = content or {}
        self.brand = brand_visual_spec or {}
        self.size_override = size_override
        self.kb = kb
        self.canvas: Optional[Image.Image] = None
        self.canvas_w: int = 0
        self.canvas_h: int = 0
        self.font_resolver = FontResolver(brand_visual_spec=self.brand, kb=kb)
        self.asset_resolver = AssetResolver(kb=kb)

    # ---- Public API -----------------------------------------------------

    def render(self) -> bytes:
        """Executa o render e retorna PNG bytes."""
        self.canvas_w, self.canvas_h = self._resolve_dimensions()
        bg_color = self._resolve_color(
            self.spec.get('background_color'), default='#FFFFFF'
        )
        self.canvas = Image.new('RGB', (self.canvas_w, self.canvas_h), bg_color)

        regions = self.spec.get('regions') or []
        # Ordenacao: logo e graphic primeiro (fundo), texto depois (frente)
        z_order = {'graphic': 0, 'image': 1, 'logo': 2}
        regions_sorted = sorted(
            regions, key=lambda r: z_order.get(r.get('tipo', ''), 3)
        )
        for region in regions_sorted:
            try:
                self._render_region(region)
            except Exception:
                logger.exception(
                    'Falha ao renderizar region %s', region.get('id', '?')
                )

        buf = BytesIO()
        self.canvas.save(buf, format='PNG', optimize=True)
        return buf.getvalue()

    def render_to_file(self, path: str) -> int:
        """Atalho: renderiza e salva em arquivo. Retorna bytes escritos."""
        data = self.render()
        with open(path, 'wb') as f:
            f.write(data)
        return len(data)

    # ---- Dimensions ----------------------------------------------------

    def _resolve_dimensions(self) -> Tuple[int, int]:
        if self.size_override:
            return self.size_override
        aspect = (self.spec.get('format_aspect') or '').strip()
        if aspect in ASPECT_DIMENSIONS:
            return ASPECT_DIMENSIONS[aspect]
        # Fallback: tenta interpretar W:H
        m = re.match(r'(\d+):(\d+)', aspect)
        if m:
            ratio_w, ratio_h = int(m.group(1)), int(m.group(2))
            base = 1080
            if ratio_w >= ratio_h:
                return (base, int(base * ratio_h / ratio_w))
            return (int(base * ratio_w / ratio_h), base)
        return (1080, 1080)

    # ---- Region dispatcher ---------------------------------------------

    def _bbox_to_px(self, bbox_pct: Dict[str, Any]) -> Tuple[int, int, int, int]:
        x = int(self.canvas_w * float(bbox_pct.get('x', 0)) / 100)
        y = int(self.canvas_h * float(bbox_pct.get('y', 0)) / 100)
        w = int(self.canvas_w * float(bbox_pct.get('w', 0)) / 100)
        h = int(self.canvas_h * float(bbox_pct.get('h', 0)) / 100)
        return x, y, w, h

    def _natural_bbox(
        self, placement: Dict[str, Any], asset_w: int, asset_h: int
    ) -> Tuple[int, int, int, int]:
        """
        Calcula bbox de um asset respeitando aspect ratio nativo.

        placement schema:
        - anchor: 'top-left' | 'top-center' | 'top-right' |
                  'center-left' | 'center' | 'center-right' |
                  'bottom-left' | 'bottom-center' | 'bottom-right'
        - scale_pct: numero (0-100), tamanho relativo a scale_dim do canvas
        - scale_dim: 'width' (default) | 'height' — referencia do canvas
        - offset_pct: {x: %, y: %} — afastamento da borda do anchor (default 0)
        """
        anchor = (placement.get('anchor') or 'top-left').lower()
        scale_dim = (placement.get('scale_dim') or 'width').lower()
        scale_pct = float(placement.get('scale_pct') or 100)
        offset = placement.get('offset_pct') or {}
        off_x_pct = float(offset.get('x', 0))
        off_y_pct = float(offset.get('y', 0))

        # Calcula largura final do asset (preservando aspect ratio nativo)
        if scale_dim == 'height':
            new_h = int(self.canvas_h * scale_pct / 100)
            new_w = int(asset_w * (new_h / asset_h)) if asset_h else new_h
        else:
            new_w = int(self.canvas_w * scale_pct / 100)
            new_h = int(asset_h * (new_w / asset_w)) if asset_w else new_w

        # Calcula x baseado no anchor horizontal
        if anchor.endswith('left'):
            x = int(self.canvas_w * off_x_pct / 100)
        elif anchor.endswith('right'):
            x = self.canvas_w - new_w - int(self.canvas_w * off_x_pct / 100)
        else:
            x = (self.canvas_w - new_w) // 2 + int(self.canvas_w * off_x_pct / 100)

        # Calcula y baseado no anchor vertical
        if anchor.startswith('top'):
            y = int(self.canvas_h * off_y_pct / 100)
        elif anchor.startswith('bottom'):
            y = self.canvas_h - new_h - int(self.canvas_h * off_y_pct / 100)
        else:
            y = (self.canvas_h - new_h) // 2 + int(self.canvas_h * off_y_pct / 100)

        return x, y, new_w, new_h

    def _render_region(self, region: Dict[str, Any]) -> None:
        tipo = (region.get('tipo') or '').lower()

        # Natural placement: para logo/graphic com 'placement' dict
        # o engine pre-calcula bbox a partir do tamanho real do asset
        placement = region.get('placement')
        if placement and tipo in ('logo', 'graphic'):
            self._render_asset_natural(region, tipo, placement)
            return

        bbox = region.get('bbox_pct') or {}
        if not bbox:
            return
        x, y, w, h = self._bbox_to_px(bbox)
        if w <= 0 or h <= 0:
            return

        if tipo in TEXT_TYPES:
            self._render_text(region, x, y, w, h)
        elif tipo == 'image':
            self._render_image_placeholder(region, x, y, w, h)
        elif tipo == 'logo':
            self._render_logo_placeholder(region, x, y, w, h)
        elif tipo == 'graphic':
            self._render_graphic_placeholder(region, x, y, w, h)
        else:
            logger.info('Tipo de region nao suportado: %r', tipo)

    def _render_asset_natural(
        self, region: Dict[str, Any], tipo: str, placement: Dict[str, Any]
    ) -> None:
        """
        Renderiza logo ou graphic respeitando dimensoes nativas do asset.
        Usa placement.anchor + placement.scale_pct para posicionar.
        Fallback: se asset nao carrega, desenha placeholder com bbox calculada.
        """
        # Tenta carregar asset
        if tipo == 'logo':
            asset = self.asset_resolver.resolve_logo(
                variant=region.get('logo_variant') or 'preferencial'
            )
        else:
            asset = self.asset_resolver.resolve_graphic_module(
                module_number=region.get('graphic_module_number'),
                orientation=region.get('orientation'),
            )

        if asset:
            x, y, w, h = self._natural_bbox(placement, asset.size[0], asset.size[1])
            # fit_mode default 'stretch' aqui pq ja calculamos w,h conforme aspect
            self.asset_resolver.paste_fit(
                self.canvas, asset, x, y, w, h, mode='stretch'
            )
            return

        # Fallback: usa scale_pct para gerar uma bbox quadrada e desenha placeholder
        fallback_pct = float(placement.get('scale_pct') or 20)
        fake_size = (1, 1)  # 1:1 para fallback nao ter ratio absurdo
        x, y, w, h = self._natural_bbox(placement, *fake_size)
        # Garante minimo razoavel
        w = max(w, int(self.canvas_w * fallback_pct / 200))
        h = max(h, w)
        if tipo == 'logo':
            self._render_logo_placeholder(region, x, y, w, h)
        else:
            self._render_graphic_placeholder(region, x, y, w, h)

    # ---- Text renderer -------------------------------------------------

    def _render_text(
        self, region: Dict[str, Any], x: int, y: int, w: int, h: int
    ) -> None:
        text = self._resolve_text_content(region)
        if not text:
            return

        case = (region.get('case') or '').lower()
        if 'upper' in case or 'alta' in case:
            text = text.upper()

        color = self._resolve_color(
            region.get('color_token'), default='#000000'
        )

        # Calcula font_size MELHOR: itera ate o texto caber tanto em
        # largura (com wrap) quanto em altura (numero de linhas).
        font, lines, line_h = self._fit_text_in_bbox(region, text, w, h)
        if not lines:
            return

        draw = ImageDraw.Draw(self.canvas)
        align = (region.get('alignment') or 'left').lower()

        # Posiciona verticalmente centralizado dentro do bbox
        total_h = line_h * len(lines)
        cy = y + max(0, (h - total_h) // 2)

        for i, line in enumerate(lines):
            line_y = cy + i * line_h
            if 'center' in align or 'centro' in align:
                lx = x + w // 2
                anchor = 'ma'
            elif 'right' in align or 'direita' in align:
                lx = x + w
                anchor = 'ra'
            else:
                lx = x
                anchor = 'la'
            draw.text((lx, line_y), line, fill=color, font=font, anchor=anchor)

        # Tag: desenha borda em volta
        if region.get('tipo') == 'tag':
            draw.rectangle([x, y, x + w, y + h], outline=color, width=2)

    def _fit_text_in_bbox(
        self, region: Dict[str, Any], text: str, w: int, h: int,
    ):
        """
        Encontra o maior font_size onde o texto cabe completamente no bbox.
        Itera de cima pra baixo (binary-search style com step decremental).
        Retorna (font, lines, line_height).
        """
        # Tamanho inicial baseado em size_token e altura
        size_token = (region.get('size_token') or '').upper().replace(' ', '')
        # Cap base por altura (mais conservador agora)
        if size_token in ('X/2', '1/2X', '0.5X'):
            initial = int(h * 0.55)
        elif size_token in ('2X/3', '2/3X', '0.66X'):
            initial = int(h * 0.50)
        elif size_token == 'X':
            initial = int(h * 0.80)
        else:
            initial = int(h * 0.55)
        # Limites
        max_size = max(12, min(initial, int(min(w, h) * 0.95)))
        min_size = 10

        best = None  # (font, lines, line_h)
        size = max_size
        while size >= min_size:
            try:
                font = self._load_text_font(region, size)
            except Exception:
                font = ImageFont.load_default()
            lines = self._wrap_text(text, font, w)
            # Altura da linha: usa ascent+descent para precisao
            ascent, descent = font.getmetrics() if hasattr(font, 'getmetrics') else (size, size // 4)
            line_h = ascent + descent + 2
            total_h = line_h * len(lines)
            # Verifica se caiu em altura E se nenhuma linha excede largura
            longest = max((font.getbbox(line)[2] for line in lines), default=0)
            if total_h <= h and longest <= w:
                best = (font, lines, line_h)
                break
            size = int(size * 0.85)  # decremento agressivo

        if best is None:
            # Fallback: tamanho minimo com clip
            font = self._load_text_font(region, min_size)
            lines = self._wrap_text(text, font, w)
            ascent, descent = font.getmetrics() if hasattr(font, 'getmetrics') else (min_size, min_size // 4)
            line_h = ascent + descent + 2
            # Trunca linhas que nao cabem
            max_lines = max(1, h // line_h)
            lines = lines[:max_lines]
            best = (font, lines, line_h)
        return best

    def _load_text_font(self, region: Dict[str, Any], size: int):
        """
        Carrega fonte real via FontResolver:
        1. Resolve font_token (ex: 'primaria.supreme') consultando brand spec
        2. Baixa/cacheia TTF se necessario (fontsource)
        3. Fallback DejaVu se tudo falhar

        Peso e inferido do tipo de region OU do peso_aparente quando especificado.
        """
        tipo = region.get('tipo', '')
        # Decide peso: title/subtitle/tag = bold, resto = regular.
        # Se a region especificar peso explicito, usa esse.
        peso = region.get('peso') or region.get('peso_aparente') or ''
        if peso and peso.lower() not in ('null', 'nao_aplicavel', ''):
            weight = peso
        elif tipo in ('title', 'subtitle', 'tag'):
            weight = 'bold'
        else:
            weight = 'regular'

        # Tenta resolver via FontResolver
        font_token = region.get('font_token')
        system_fb = SYSTEM_FONTS['bold'] if weight.lower() in ('bold', 'extrabold', 'black') else SYSTEM_FONTS['regular']
        try:
            ttf_path = self.font_resolver.resolve_with_fallback(
                font_token=font_token,
                weight=weight,
                system_fallback=system_fb,
            )
            return ImageFont.truetype(ttf_path, size)
        except Exception:
            try:
                return ImageFont.truetype(system_fb, size)
            except Exception:
                return ImageFont.load_default()

    def _text_height(self, font, sample: str) -> int:
        bbox = font.getbbox(sample)
        return bbox[3] - bbox[1]

    def _wrap_text(self, text: str, font, max_w: int, draw=None) -> List[str]:
        """Quebra texto em multiplas linhas se nao couber na largura."""
        words = text.split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f'{current} {word}'
            tw = font.getbbox(candidate)[2]
            if tw <= max_w:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    # ---- Image / Logo / Graphic placeholders ---------------------------

    def _render_image_placeholder(
        self, region: Dict[str, Any], x: int, y: int, w: int, h: int
    ) -> None:
        # Tenta carregar imagem real do content
        slot_id = region.get('id')
        content_value = self.content.get(slot_id) if slot_id else None
        asset = self.asset_resolver.resolve_image_from_content(content_value)
        if asset:
            mode = region.get('fit_mode') or 'cover'
            self.asset_resolver.paste_fit(self.canvas, asset, x, y, w, h, mode=mode)
            return

        # Fallback: wireframe placeholder
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle(
            [x, y, x + w, y + h], fill='#D8D8D8', outline='#A0A0A0', width=2
        )
        draw.line([(x, y), (x + w, y + h)], fill='#A0A0A0', width=2)
        draw.line([(x + w, y), (x, y + h)], fill='#A0A0A0', width=2)
        label = (slot_id or 'IMAGE').upper()
        try:
            font = ImageFont.truetype(SYSTEM_FONTS['regular'], 28)
        except Exception:
            font = ImageFont.load_default()
        draw.text(
            (x + w // 2, y + h // 2), label,
            fill='#606060', font=font, anchor='mm'
        )

    def _render_logo_placeholder(
        self, region: Dict[str, Any], x: int, y: int, w: int, h: int
    ) -> None:
        """Renderiza logo real da KB; fallback: caixa preta com label."""
        variant = region.get('logo_variant') or 'preferencial'
        asset = self.asset_resolver.resolve_logo(variant=variant)
        if asset:
            self.asset_resolver.paste_fit(self.canvas, asset, x, y, w, h, mode='contain')
            return

        draw = ImageDraw.Draw(self.canvas)
        bg = self._resolve_color(
            region.get('color_token'), default='#000000'
        )
        canvas_bg = self.canvas.getpixel((min(x + 2, self.canvas_w - 1), min(y + 2, self.canvas_h - 1)))
        if isinstance(canvas_bg, tuple) and self._is_dark(bg) == self._is_dark_rgb(canvas_bg):
            bg = '#FFFFFF' if self._is_dark_rgb(canvas_bg) else '#000000'

        draw.rectangle([x, y, x + w, y + h], fill=bg)
        label_color = '#FFFFFF' if self._is_dark(bg) else '#000000'
        font_size = max(12, min(int(h * 0.5), 40))
        try:
            font = ImageFont.truetype(SYSTEM_FONTS['bold'], font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text(
            (x + w // 2, y + h // 2),
            f'LOGO\n{variant}',
            fill=label_color, font=font, anchor='mm', align='center'
        )

    def _render_graphic_placeholder(
        self, region: Dict[str, Any], x: int, y: int, w: int, h: int
    ) -> None:
        """
        Renderiza region tipo 'graphic'. Tres casos:
        1. Sem graphic_module_number ou 'nao_aplicavel' -> retangulo solido
           com color_token (background highlight, barra colorida etc)
        2. graphic_module_number valido -> carrega BrandgraficModule real PNG
        3. Falhou tudo -> fallback formas geometricas
        """
        module_num = region.get('graphic_module_number')
        is_color_block = (
            not module_num or
            str(module_num).strip().lower() in (
                '', 'nao_aplicavel', 'na', 'none', 'indeterminado'
            )
        )

        if is_color_block:
            # Apenas um retangulo de destaque na cor do brand
            draw = ImageDraw.Draw(self.canvas)
            color = self._resolve_color(
                region.get('color_token'), default='#FFCDD8'
            )
            draw.rectangle([x, y, x + w, y + h], fill=color)
            return

        orientation = region.get('orientation') or self._infer_orientation(w, h)
        asset = self.asset_resolver.resolve_graphic_module(
            module_number=module_num, orientation=orientation
        )
        if asset:
            mode = region.get('fit_mode') or 'contain'
            self.asset_resolver.paste_fit(self.canvas, asset, x, y, w, h, mode=mode)
            return

        # Fallback: formas geometricas representativas
        draw = ImageDraw.Draw(self.canvas)
        color = self._resolve_color(
            region.get('color_token'), default='#000000'
        )
        cx, cy = x + w // 2, y + h // 2
        r = max(8, min(w, h) // 6)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        bar_w = max(4, r // 2)
        draw.rectangle(
            [x + w // 4 - bar_w // 2, y + h // 4, x + w // 4 + bar_w // 2, y + 3 * h // 4],
            fill=color,
        )
        draw.rectangle(
            [x + 3 * w // 4 - bar_w // 2, y + h // 4, x + 3 * w // 4 + bar_w // 2, y + 3 * h // 4],
            fill=color,
        )
        if module_num and str(module_num).strip() not in ('', 'nao_aplicavel'):
            try:
                font = ImageFont.truetype(SYSTEM_FONTS['regular'], 18)
            except Exception:
                font = ImageFont.load_default()
            draw.text(
                (x + 8, y + h - 22), f'mod {module_num}',
                fill=color, font=font, anchor='lt'
            )

    @staticmethod
    def _infer_orientation(w: int, h: int) -> str:
        if h > w * 1.2:
            return 'vertical'
        if w > h * 1.2:
            return 'horizontal'
        return 'both'

    # ---- Resolvers ----------------------------------------------------

    def _resolve_text_content(self, region: Dict[str, Any]) -> str:
        """
        Resolve o texto do slot. Prioridade:
        1. content[region.id]
        2. content[region.tipo]
        3. region.exemplo_conteudo
        4. ''
        """
        slot_id = region.get('id')
        if slot_id and slot_id in self.content:
            value = self.content[slot_id]
            if value:
                return str(value)
        tipo = region.get('tipo')
        if tipo and tipo in self.content:
            value = self.content[tipo]
            if value:
                return str(value)
        exemplo = region.get('exemplo_conteudo') or ''
        return str(exemplo)

    def _resolve_color(self, value: Any, default: str = '#000000') -> str:
        """
        Resolve um valor de cor para hex.

        Aceita:
        - Hex direto: '#FF0047' -> '#FF0047'
        - Token: 'institucional.preto' -> consulta brand spec
        - Multiplas alternativas: '#000000 (em fundo branco) | #FFFFFF (em fundo preto)'
          -> pega a primeira hex valida
        - None -> default
        """
        if not value:
            return default
        if not isinstance(value, str):
            return default

        # Encontra primeira ocorrencia de #RRGGBB
        hex_match = re.search(r'#([0-9A-Fa-f]{6})', value)
        if hex_match:
            return '#' + hex_match.group(1).upper()

        # Token tipo "institucional.preto" ou "iniciativas.azul"
        if '.' in value:
            return self._resolve_color_token(value, default)

        return default

    def _resolve_color_token(self, token: str, default: str) -> str:
        """Consulta brand_visual_spec.cores.<group>[*].nome == <name>."""
        # Trata multiplas alternativas separadas por |
        first = token.split('|')[0].strip()
        parts = first.split('.')
        if len(parts) < 2:
            return default
        group, name = parts[0].strip().lower(), parts[1].strip().lower()
        # Mapeamento de grupos do spec
        cores = (self.brand or {}).get('cores', {})
        candidates = cores.get(group, []) or []
        if not candidates:
            # Fallback: tenta procurar em todos os grupos
            for grp_values in cores.values():
                if isinstance(grp_values, list):
                    candidates.extend(grp_values)
        # Tenta match por nome
        for c in candidates:
            if not isinstance(c, dict):
                continue
            cname = (c.get('nome') or '').lower()
            if cname == name or name in cname or cname in name:
                hex_value = c.get('hex')
                if hex_value:
                    return hex_value
        return default

    # ---- Helpers ------------------------------------------------------

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
        h = hex_str.lstrip('#')
        if len(h) != 6:
            return (0, 0, 0)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @classmethod
    def _is_dark(cls, hex_color: str) -> bool:
        r, g, b = cls._hex_to_rgb(hex_color)
        # Luminancia perceptual
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        return luma < 128

    @classmethod
    def _is_dark_rgb(cls, rgb: Tuple[int, int, int]) -> bool:
        r, g, b = rgb[:3]
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        return luma < 128
