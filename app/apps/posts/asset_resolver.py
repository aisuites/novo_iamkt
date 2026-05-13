"""
Asset Resolver — carrega assets reais (Logo, BrandgraficModule, imagens)
do S3/KB para uso no Compose Engine.

Estrategia em camadas:
1. Cache local em /app/assets_cache/ (compartilhado entre renders)
2. Download via S3 url publica (presigned ou direta)
3. Retorna PIL.Image RGBA pronto para colagem

Tipos resolvidos:
- Logo: busca em kb.logos por logo_type/variant (preferencial/horizontal/icone/monocromatico)
- BrandgraficModule: busca em kb.grafic_modules por nome ou numero do modulo
- Image: download direto de URL S3 fornecida no content
"""

import hashlib
import logging
import os
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

logger = logging.getLogger(__name__)

ASSETS_CACHE_DIR = Path('/app/assets_cache')
ASSETS_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Mapeia logo_variant do template_spec para logo_type do Logo model
LOGO_VARIANT_MAP = {
    'preferencial':   'principal',
    'principal':      'principal',
    'horizontal':     'horizontal',
    'vertical':       'vertical',
    'icone':          'icone',
    'monocromatico':  'monocromatico',
    'preto':          'monocromatico',
    'branco':         'monocromatico',
}


class AssetResolver:
    """Carrega logo, grafismos e imagens reais do S3."""

    def __init__(self, kb=None):
        self.kb = kb
        self._mem_cache: Dict[str, Image.Image] = {}

    # ---- API publica --------------------------------------------------

    def resolve_logo(self, variant: Optional[str] = None) -> Optional[Image.Image]:
        """
        Resolve o logo da KB respeitando a variante solicitada.
        Cai para o logo principal (is_primary=True) se variante nao existir.
        """
        if not self.kb:
            return None
        try:
            from apps.knowledge.models import Logo
        except Exception:
            return None

        wanted_type = LOGO_VARIANT_MAP.get((variant or '').lower(), 'principal')
        qs = Logo.objects.filter(knowledge_base=self.kb)

        logo = qs.filter(logo_type=wanted_type).first()
        if not logo:
            logo = qs.filter(is_primary=True).first() or qs.first()
        if not logo:
            return None

        cache_key = f'logo_{self.kb.id}_{logo.id}'
        return self._load_s3(
            logo.s3_key, logo.s3_url, cache_key, ext=logo.file_format or 'png'
        )

    def resolve_graphic_module(
        self,
        module_number: Optional[Any] = None,
        orientation: Optional[str] = None,
    ) -> Optional[Image.Image]:
        """
        Resolve um BrandgraficModule por numero ou orientacao.
        Estrategia:
        - Se module_number == 1/2/3 -> procura por 'modelo_01', 'modelo_02', 'modelo_03'
        - Senao usa orientation para filtrar e pega o primeiro ativo
        """
        if not self.kb:
            return None
        try:
            from apps.knowledge.models import BrandgraficModule
        except Exception:
            return None

        qs = BrandgraficModule.objects.filter(
            knowledge_base=self.kb,
            is_active=True,
            approved_by_user=True,
        )

        module = None
        if module_number and str(module_number).strip() not in ('', 'nao_aplicavel'):
            try:
                num_int = int(module_number)
                # Procura padrao "modelo_01", "modelo_02", etc
                module = qs.filter(name__iendswith=f'_{num_int:02d}').first()
                if not module:
                    module = qs.filter(name__icontains=f'{num_int:02d}').first()
            except (ValueError, TypeError):
                module = qs.filter(name__icontains=str(module_number)).first()

        if not module and orientation:
            module = qs.filter(orientation__in=[orientation, 'both']).first()
        if not module:
            module = qs.first()

        if not module:
            return None

        cache_key = f'graphic_{self.kb.id}_{module.id}'
        return self._load_s3(
            module.s3_key, module.s3_url, cache_key,
            ext=module.file_format or 'png',
        )

    def resolve_image_from_content(
        self, content_value: Any
    ) -> Optional[Image.Image]:
        """
        Resolve uma imagem do content. Aceita:
        - dict {s3_url: '...'} ou {url: '...'}
        - string URL direta
        """
        url = None
        if isinstance(content_value, dict):
            url = content_value.get('s3_url') or content_value.get('url')
        elif isinstance(content_value, str) and content_value.startswith(('http://', 'https://')):
            url = content_value

        if not url:
            return None

        # Cache key derivado da URL
        cache_key = 'img_' + hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]
        # Tenta inferir extensao
        ext = 'png'
        for candidate in ('.png', '.jpg', '.jpeg', '.webp'):
            if candidate in url.lower():
                ext = candidate.lstrip('.')
                break
        return self._load_from_url(url, cache_key, ext=ext)

    # ---- Helpers de paste ---------------------------------------------

    @staticmethod
    def paste_fit(
        canvas: Image.Image, asset: Image.Image,
        x: int, y: int, w: int, h: int,
        mode: str = 'contain',
    ) -> None:
        """
        Cola o asset no canvas dentro da bbox (x,y,w,h).

        mode='contain': mantem aspect ratio, centraliza, deixa espaco vazio
        mode='cover':   mantem aspect ratio, cobre tudo, pode cortar bordas
        mode='stretch': estica para preencher bbox exata
        """
        if w <= 0 or h <= 0:
            return

        asset_w, asset_h = asset.size
        if asset_w == 0 or asset_h == 0:
            return

        if mode == 'stretch':
            resized = asset.resize((w, h), Image.LANCZOS)
            paste_x, paste_y = x, y
        else:
            scale_w = w / asset_w
            scale_h = h / asset_h
            scale = min(scale_w, scale_h) if mode == 'contain' else max(scale_w, scale_h)
            new_w = max(1, int(asset_w * scale))
            new_h = max(1, int(asset_h * scale))
            resized = asset.resize((new_w, new_h), Image.LANCZOS)
            if mode == 'cover':
                # Crop centralizado para encaixar exato em (w,h)
                left = max(0, (new_w - w) // 2)
                top = max(0, (new_h - h) // 2)
                resized = resized.crop((left, top, left + w, top + h))
                paste_x, paste_y = x, y
            else:
                # contain: centraliza
                paste_x = x + (w - new_w) // 2
                paste_y = y + (h - new_h) // 2

        if resized.mode == 'RGBA':
            canvas.paste(resized, (paste_x, paste_y), resized)
        else:
            canvas.paste(resized, (paste_x, paste_y))

    # ---- Loader interno -----------------------------------------------

    def _load_s3(
        self, s3_key: Optional[str], fallback_url: Optional[str],
        cache_key: str, ext: str = 'png',
    ) -> Optional[Image.Image]:
        """
        Carrega asset do S3 gerando presigned URL via S3Service.
        Cai para fallback_url se nao tiver s3_key (assets legados).
        """
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        cache_file = ASSETS_CACHE_DIR / f'{cache_key}.{ext.lower()}'
        if not (cache_file.exists() and cache_file.stat().st_size > 0):
            url = None
            if s3_key:
                try:
                    from apps.core.services.s3_service import S3Service
                    url = S3Service.generate_presigned_download_url(s3_key)
                except Exception as exc:
                    logger.warning('Falha ao gerar presigned para %s: %s', s3_key, exc)
            if not url:
                url = fallback_url
            if not url or not self._download(url, cache_file):
                return None

        return self._open_image(cache_file, cache_key)

    def _load_from_url(
        self, url: str, cache_key: str, ext: str = 'png'
    ) -> Optional[Image.Image]:
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        cache_file = ASSETS_CACHE_DIR / f'{cache_key}.{ext.lower()}'
        if not (cache_file.exists() and cache_file.stat().st_size > 0):
            if not self._download(url, cache_file):
                return None
        return self._open_image(cache_file, cache_key)

    def _open_image(
        self, cache_file: Path, cache_key: str
    ) -> Optional[Image.Image]:
        try:
            img = Image.open(cache_file)
            img.load()
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
        except Exception as exc:
            logger.warning('Falha ao abrir asset %s: %s', cache_file, exc)
            return None

        self._mem_cache[cache_key] = img
        return img

    @staticmethod
    def _download(url: str, target: Path) -> bool:
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 IAMKT AssetResolver'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if not data:
                return False
            target.parent.mkdir(exist_ok=True, parents=True)
            with open(target, 'wb') as f:
                f.write(data)
            logger.info('Asset baixado: %s (%d bytes)', target.name, len(data))
            return True
        except Exception as exc:
            logger.warning('Falha ao baixar asset %s: %s', url, exc)
            return False
