"""
Utilitarios para validacao de Google Fonts.

Fonte de verdade: app/apps/knowledge/data/google_fonts.json (versionado no repo).
Gerado por `python manage.py update_google_fonts_list` (consome
https://fonts.google.com/metadata/fonts, sem API key).
"""

import json
import logging
import threading
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent / 'data' / 'google_fonts.json'

_lock = threading.Lock()
_cache_loaded = False
_families_canonical: list = []         # ordem alfabetica, capitalizacao oficial
_families_lookup: dict = {}            # lower -> canonical
_meta: dict = {}


def _load_cache() -> None:
    """Carrega o JSON em memoria. Idempotente, thread-safe."""
    global _cache_loaded, _families_canonical, _families_lookup, _meta
    if _cache_loaded:
        return
    with _lock:
        if _cache_loaded:
            return
        try:
            with open(_DATA_PATH, encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning(
                'google_fonts.json nao encontrado em %s. Lista vazia.', _DATA_PATH
            )
            data = {'families': []}
        except (json.JSONDecodeError, OSError) as exc:
            logger.exception('Falha ao ler google_fonts.json: %s', exc)
            data = {'families': []}

        families = list(data.get('families') or [])
        _families_canonical = families
        _families_lookup = {fam.lower(): fam for fam in families}
        _meta = {
            'count': data.get('count', len(families)),
            'updated_at': data.get('updated_at'),
            'source': data.get('source'),
        }
        _cache_loaded = True


def reload_cache() -> None:
    """Forca recarga do JSON (usado pelo management command apos atualizar)."""
    global _cache_loaded
    with _lock:
        _cache_loaded = False
    _load_cache()


def get_google_fonts_list() -> list:
    """Retorna a lista de families (capitalizacao oficial, ordem alfabetica)."""
    _load_cache()
    return list(_families_canonical)


def get_meta() -> dict:
    """Retorna metadados da lista (count, updated_at, source)."""
    _load_cache()
    return dict(_meta)


def is_valid_google_font(name: Optional[str]) -> bool:
    """Verifica se um nome corresponde a uma Google Font (case-insensitive)."""
    if not name or not isinstance(name, str):
        return False
    _load_cache()
    return name.strip().lower() in _families_lookup


def normalize_google_font_name(name: Optional[str]) -> Optional[str]:
    """
    Retorna o nome canonical (capitalizacao oficial) se a fonte for valida.
    Retorna None se nao for uma Google Font conhecida.

    Ex: 'lora' -> 'Lora', 'OPEN SANS' -> 'Open Sans', 'Supreme' -> None
    """
    if not name or not isinstance(name, str):
        return None
    _load_cache()
    return _families_lookup.get(name.strip().lower())


def find_first_valid(names: Iterable[Optional[str]]) -> Optional[str]:
    """Retorna o primeiro nome canonical valido da sequencia, ou None."""
    for n in names:
        canonical = normalize_google_font_name(n)
        if canonical:
            return canonical
    return None
