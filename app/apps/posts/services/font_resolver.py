"""
Font Resolver — carrega TTFs para uso no Pillow overlay.

Estrategia em camadas:
1. CustomFont da KB (TTF/OTF privado salvo no S3 — apps.knowledge.CustomFont)
2. Google Fonts via CSS API (Typography com font_source='google')
3. Cache local em /app/fonts_cache/
4. Fallback DejaVu do sistema

A API CSS do Google retorna formato baseado no User-Agent:
- Browsers modernos -> WOFF2 (Pillow nao decodifica)
- Browsers antigos -> TTF
Usamos UA Android 2.3.5 para forcar TTF.
"""

import logging
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FONTS_CACHE_DIR = Path('/app/fonts_cache')
try:
    FONTS_CACHE_DIR.mkdir(exist_ok=True, parents=True)
except PermissionError:
    # Fallback se /app nao for writable (ex: container)
    FONTS_CACHE_DIR = Path('/tmp/fonts_cache')
    FONTS_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Mapeia normalizacao de pesos
WEIGHT_TO_NUMERIC = {
    'thin': '100', 'extralight': '200', 'light': '300',
    'regular': '400', 'normal': '400', 'book': '400',
    'medium': '500', 'semibold': '600', 'semi-bold': '600',
    'bold': '700', 'extrabold': '800', 'black': '900',
}


def resolve_font_for_kb(
    kb,
    usage_filter: str = 'titulo',
    weight: str = 'bold',
) -> Optional[str]:
    """
    Resolve UMA fonte da KB baseada em usage_filter (titulo/corpo/destaque etc).

    Retorna caminho local do arquivo TTF, ou None se nada disponivel.

    Estrategia:
      1. Procura Typography com usage matching no nome (heuristico) e prefere
         a primeira do tipo.
      2. Se font_source='upload' e tem custom_font: baixa o TTF/OTF do S3
      3. Se font_source='google': baixa via Google CSS API
      4. Retorna None se nao achar (caller usa DejaVu como fallback)
    """
    if not kb:
        return None

    typographies = list(kb.typography_settings.all().order_by('order'))
    if not typographies:
        return None

    # Matching por substring SEM ACENTO ('titulo' casa 'Títulos'); entre os
    # que casam, escolhe a VARIANTE pelo peso pedido (Bold/Light/Regular).
    uf = _strip_accents((usage_filter or '').lower())
    matched_list = [t for t in typographies if uf and uf in _strip_accents((t.usage or '').lower())]
    if matched_list:
        matched = _pick_by_weight(matched_list, weight)
    else:
        matched = typographies[0]

    return resolve_typography(matched, weight=weight)


def _strip_accents(s: str) -> str:
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s or '')
        if not unicodedata.combining(c)
    )


def _pick_by_weight(matched, weight: str):
    """Entre Typographies que casaram o usage, escolhe a que melhor bate com o
    peso pedido olhando o nome da fonte (ex: '_Vorwerk-Bold' vs '-Light')."""
    if len(matched) == 1:
        return matched[0]
    w = (weight or '').lower()
    want_bold = w in ('bold', 'semibold', '600', '700', '800', '900', 'black', 'heavy')

    def _name(t):
        if getattr(t, 'custom_font', None):
            return (t.custom_font.name or '').lower()
        return (t.google_font_name or '').lower()

    def _score(t):
        n = _name(t)
        is_bold = any(k in n for k in ('bold', 'black', 'heavy'))
        is_italic = 'italic' in n
        is_light = any(k in n for k in ('light', 'thin'))
        s = 0
        if want_bold:
            s += 10 if is_bold else 0
        else:
            if 'regular' in n:
                s += 10
            elif is_light:
                s += 7
            elif 'medium' in n:
                s += 5
            if is_bold:
                s -= 6
        if is_italic:
            s -= 3  # evita italico salvo se for a unica opcao
        return s

    return max(matched, key=_score)


def resolve_typography(typography, weight: str = 'bold') -> Optional[str]:
    """Resolve uma instancia de Typography para caminho TTF local."""
    if not typography:
        return None

    if typography.font_source == 'upload' and typography.custom_font:
        return _load_custom_font(typography.custom_font)

    if typography.font_source == 'google' and typography.google_font_name:
        actual_weight = typography.google_font_weight or weight
        return _load_google_font(typography.google_font_name, actual_weight)

    return None


def system_dejavu_path(weight: str = 'regular') -> str:
    """Retorna caminho do DejaVu do sistema conforme peso (fallback final)."""
    if (weight or '').lower() in ('bold', 'extrabold', 'black', '700', '800', '900'):
        return '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    return '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


# ---- Loaders -----------------------------------------------------------------


def _load_custom_font(custom_font) -> Optional[str]:
    """Baixa TTF/OTF privado do S3 e cacheia localmente."""
    from apps.core.services.s3_service import S3Service

    ext = (custom_font.file_format or 'ttf').lower()
    cache_name = f'kb{custom_font.knowledge_base_id}_cf{custom_font.id}.{ext}'
    cache_path = FONTS_CACHE_DIR / cache_name
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return str(cache_path)
    try:
        url = S3Service.generate_presigned_download_url(custom_font.s3_key, expires_in=3600)
    except Exception as exc:
        logger.warning('Falha presigned custom_font %s: %s', custom_font.s3_key, exc)
        url = custom_font.s3_url
    if not _download(url, cache_path):
        return None
    return str(cache_path)


def _load_google_font(family: str, weight: str) -> Optional[str]:
    """Baixa TTF do Google Fonts via CSS API com UA Android 2.3.5."""
    family_clean = (family or '').strip()
    if not family_clean:
        return None

    weight_norm = _normalize_weight(weight)
    weight_num = WEIGHT_TO_NUMERIC.get(weight_norm, '400')
    safe = family_clean.lower().replace(' ', '_')
    cache_path = FONTS_CACHE_DIR / f'gf_{safe}_{weight_num}.ttf'
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return str(cache_path)

    family_url = family_clean.replace(' ', '+')
    css_url = (
        f'https://fonts.googleapis.com/css2?family={family_url}'
        f':wght@{weight_num}&display=swap'
    )
    try:
        req = urllib.request.Request(
            css_url,
            headers={
                # UA Android 2.3.5: forca Google Fonts a servir TTF (nao WOFF2)
                'User-Agent': 'Mozilla/5.0 (Linux; U; Android 2.3.5)',
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            css = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        logger.warning('Falha CSS Google Fonts %s: %s', css_url, exc)
        return None

    m = re.search(r'url\((https://fonts\.gstatic\.com/[^)]+?\.ttf)\)', css)
    if not m:
        logger.warning('TTF URL nao achada no CSS de %s (peso %s)', family_clean, weight)
        return None
    if not _download(m.group(1), cache_path):
        return None
    return str(cache_path)


def _normalize_weight(weight: str) -> str:
    w = (weight or 'regular').lower().strip()
    if w in WEIGHT_TO_NUMERIC:
        return w
    # ja vem como numerico?
    reverse = {v: k for k, v in WEIGHT_TO_NUMERIC.items()}
    return reverse.get(w, 'regular')


def _download(url: str, target: Path) -> bool:
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
        logger.warning('Falha download font %s: %s', url, exc)
        return False
