"""
Font Resolver — carrega TTFs reais para uso no Compose Engine.

Estrategia em camadas:
1. CustomFont da KB (upload privado do usuario, ex: Supreme oficial)
2. Cache local (TTF ja baixado anteriormente)
3. Download de CDN publico (fontsource + Google Fonts API)
4. Fallback DejaVu do sistema

Fontes conhecidas (mapeadas para URLs publicas de TTF direto):
- IBM Plex Sans (Google Fonts) — fallback oficial da Colletivo
- Satoshi (Fontshare) — substituto livre da Supreme (ambas Indian Type Foundry)
- Inter (Google Fonts)
- Lora, Epilogue, Roboto, Open Sans (Google Fonts)

Para Supreme: como e fonte privada (paga), o resolver usa Satoshi como fallback
visualmente proximo (mesmo designer, mesmas caracteristicas geometricas).
Quando o cliente subir o Supreme.ttf oficial via CustomFont, sera usado em
preferencia ao fallback.
"""

import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Diretorio de cache compartilhado entre orgs. Fontes baixadas uma vez
# servem para todos. Em prod migrar para S3 com presigned URLs.
FONTS_CACHE_DIR = Path('/app/fonts_cache')
FONTS_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Familias suportadas via Google Fonts CSS API (com Mozilla UA retorna .ttf).
# Key: nome lowercase (para lookup) -> Value: nome com capitalizacao correta
# para a URL do CSS API (case-sensitive).
GOOGLE_FONTS_DISPLAY_NAMES = {
    'ibm plex sans':    'IBM Plex Sans',
    'inter':            'Inter',
    'lora':             'Lora',
    'epilogue':         'Epilogue',
    'roboto':           'Roboto',
    'open sans':        'Open Sans',
    'montserrat':       'Montserrat',
    'poppins':          'Poppins',
    'raleway':          'Raleway',
    'nunito':           'Nunito',
    'work sans':        'Work Sans',
    'rubik':            'Rubik',
    'pt sans':          'PT Sans',
    'merriweather':     'Merriweather',
    'oswald':           'Oswald',
    'playfair display': 'Playfair Display',
    'mulish':           'Mulish',
    'karla':            'Karla',
    'dm sans':          'DM Sans',
    'lato':             'Lato',
}
GOOGLE_FONTS_FAMILIES = set(GOOGLE_FONTS_DISPLAY_NAMES.keys())

WEIGHT_TO_NUMERIC = {
    'thin': '100', 'extralight': '200', 'light': '300',
    'regular': '400', 'medium': '500', 'semibold': '600',
    'bold': '700', 'extrabold': '800', 'black': '900',
}

# Substitutos quando a fonte real e privada/paga e nao disponivel.
# Apontam para fontes em GOOGLE_FONTS_FAMILIES (disponiveis via CSS API).
# Quando o cliente subir o TTF oficial via CustomFont, esse override e usado.
PRIVATE_FONT_FALLBACK: Dict[str, str] = {
    # Supreme -> IBM Plex Sans (fallback oficial conforme brand book For Tomorrow:
    # "Na impossibilidade de usar a fonte Supreme, devemos usar IBM Plex Sans")
    'supreme': 'ibm plex sans',
    'general sans': 'inter',
    'cabinet grotesk': 'inter',
    'satoshi': 'inter',  # Satoshi tambem e privada (Fontshare)
}


class FontResolver:
    """
    Resolve um font_token (ex: 'primaria.supreme') ou nome direto (ex: 'IBM Plex Sans')
    para um caminho local de arquivo TTF, baixando da CDN publica se necessario.
    """

    def __init__(self, brand_visual_spec: Optional[dict] = None, kb=None):
        self.brand = brand_visual_spec or {}
        self.kb = kb
        self._mem_cache: Dict[str, str] = {}

    # ---- API publica --------------------------------------------------

    def resolve(self, font_token: Optional[str], weight: str = 'regular') -> Optional[str]:
        """
        Resolve token ou nome de familia em caminho TTF local.
        Retorna None se nao conseguir.
        """
        if not font_token:
            return None

        family = self._resolve_family_name(font_token)
        if not family:
            return None

        weight_norm = self._normalize_weight(weight)
        return self._load_family(family, weight_norm)

    def resolve_with_fallback(
        self,
        font_token: Optional[str],
        weight: str = 'regular',
        system_fallback: Optional[str] = None,
    ) -> str:
        """
        Igual a resolve(), mas garante retorno de um path valido.
        Usa system_fallback (DejaVu) se tudo falhar.
        """
        path = self.resolve(font_token, weight)
        if path and os.path.exists(path):
            return path
        if system_fallback and os.path.exists(system_fallback):
            return system_fallback
        # Ultimo recurso: DejaVu Bold ou Regular
        default = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if 'regular' in weight.lower() or 'light' in weight.lower():
            default = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        return default

    # ---- Resolucao de family ------------------------------------------

    def _resolve_family_name(self, token: str) -> Optional[str]:
        """
        'primaria.supreme'   -> consulta brand.tipografia.primaria.familia
        'secundaria.ibm_plex' -> consulta brand.tipografia.fallback_ou_secundaria.familia
        'IBM Plex Sans'      -> retorna direto
        """
        if '.' not in token:
            return token.strip()

        group, _ = token.split('.', 1)
        group = group.lower()

        tipo = (self.brand or {}).get('tipografia', {}) or {}
        if group in ('primaria', 'primary'):
            primaria = tipo.get('primaria') or {}
            return primaria.get('familia')
        if group in ('secundaria', 'secondary', 'fallback', 'apoio'):
            fb = (
                tipo.get('fallback_ou_secundaria')
                or tipo.get('secundaria')
                or tipo.get('fallback')
                or {}
            )
            return fb.get('familia')
        # Fallback: usa parte depois do ponto como nome
        return token.split('.', 1)[1].strip()

    # ---- Carregamento -------------------------------------------------

    def _load_family(self, family: str, weight: str) -> Optional[str]:
        family_clean = family.strip()
        family_lower = family_clean.lower()
        cache_key = f'{family_lower.replace(" ", "_")}_{weight}'

        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        # 1. CustomFont da KB (upload privado tem precedencia)
        if self.kb:
            custom_path = self._try_custom_font(family_clean)
            if custom_path:
                self._mem_cache[cache_key] = custom_path
                return custom_path

        # 2. Arquivo no cache local
        cache_file = FONTS_CACHE_DIR / f'{cache_key}.ttf'
        if cache_file.exists() and cache_file.stat().st_size > 0:
            path = str(cache_file)
            self._mem_cache[cache_key] = path
            return path

        # 3. Google Fonts via CSS API
        if family_lower in GOOGLE_FONTS_FAMILIES:
            path = self._download_google_font(family_clean, weight, cache_file)
            if path:
                self._mem_cache[cache_key] = path
                return path

        # 4. Fallback de fonte privada conhecida (ex: Supreme -> Inter)
        if family_lower in PRIVATE_FONT_FALLBACK:
            substitute = PRIVATE_FONT_FALLBACK[family_lower]
            logger.info(
                'Fonte privada %s nao disponivel, usando fallback %s',
                family_clean, substitute,
            )
            sub_path = self._load_family(substitute, weight)
            if sub_path:
                self._mem_cache[cache_key] = sub_path
                return sub_path

        return None

    def _download_google_font(
        self, family: str, weight: str, cache_file: Path
    ) -> Optional[str]:
        """
        Baixa um TTF do Google Fonts.
        1. Constroi URL CSS API: https://fonts.googleapis.com/css2?family=Name:wght@xxx
        2. GET com User-Agent Mozilla (sem isso vem WOFF2 que Pillow nao le)
        3. Parse o CSS pra extrair src url() format('truetype')
        4. Baixa o TTF
        """
        import re as _re
        weight_num = WEIGHT_TO_NUMERIC.get(weight, '400')
        # Usa display name com capitalizacao correta (Google Fonts e case-sensitive)
        display_name = GOOGLE_FONTS_DISPLAY_NAMES.get(family.lower(), family)
        family_url = display_name.replace(' ', '+')
        css_url = (
            f'https://fonts.googleapis.com/css2?family={family_url}'
            f':wght@{weight_num}&display=swap'
        )
        try:
            req = urllib.request.Request(
                css_url,
                headers={
                    # User-Agent crucial: o Google Fonts CSS API serve formato
                    # baseado em capabilities do browser detectado pelo UA.
                    # Browsers MODERNOS recebem WOFF2 (Pillow nao decodifica).
                    # Browsers ANTIGOS recebem TTF (que e o que queremos).
                    # Android 2.3.5 e antigo o suficiente para garantir TTF.
                    'User-Agent': 'Mozilla/5.0 (Linux; U; Android 2.3.5)',
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                css = resp.read().decode('utf-8', errors='ignore')
        except Exception as exc:
            logger.warning('Falha ao buscar CSS Google Fonts %s: %s', css_url, exc)
            return None

        # Extrai a URL TTF do CSS
        # src: url(https://fonts.gstatic.com/.../file.ttf) format('truetype');
        m = _re.search(r"url\((https://fonts\.gstatic\.com/[^)]+?\.ttf)\)", css)
        if not m:
            logger.warning('Nao encontrou URL TTF no CSS de %s (peso %s)', family, weight)
            return None
        ttf_url = m.group(1)
        if self._download_url(ttf_url, cache_file):
            return str(cache_file)
        return None

    def _try_custom_font(self, family: str) -> Optional[str]:
        """Procura CustomFont na KB com nome igual ao family."""
        try:
            from apps.knowledge.models import CustomFont
        except Exception:
            return None
        cf = (
            CustomFont.objects
            .filter(knowledge_base=self.kb, name__iexact=family)
            .first()
        )
        if not cf or not cf.s3_url:
            return None
        # Baixa para cache local com nome estavel
        target = FONTS_CACHE_DIR / f'kb{self.kb.id}_{cf.id}_{family.lower().replace(" ", "_")}.ttf'
        if target.exists() and target.stat().st_size > 0:
            return str(target)
        if self._download_url(cf.s3_url, target):
            return str(target)
        return None

    @staticmethod
    def _download_url(url: str, target: Path) -> bool:
        """Baixa um arquivo de URL para target. Retorna True em sucesso."""
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 IAMKT FontResolver'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if not data:
                return False
            target.parent.mkdir(exist_ok=True, parents=True)
            with open(target, 'wb') as f:
                f.write(data)
            logger.info('Font baixada: %s (%d bytes)', target.name, len(data))
            return True
        except Exception as exc:
            logger.warning('Falha ao baixar font %s: %s', url, exc)
            return False

    # ---- Helpers ------------------------------------------------------

    @staticmethod
    def _normalize_weight(weight: str) -> str:
        """Normaliza 'Bold', 'BOLD', '700' -> 'bold'."""
        w = (weight or 'regular').lower().strip()
        # Mapeia codigos numericos
        weight_map = {
            '100': 'thin', '200': 'extralight', '300': 'light',
            '400': 'regular', '500': 'medium', '600': 'semibold',
            '700': 'bold', '800': 'extrabold', '900': 'black',
            'normal': 'regular', 'book': 'regular',
        }
        return weight_map.get(w, w)
