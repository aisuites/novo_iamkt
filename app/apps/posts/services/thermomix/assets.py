"""
Assets da thermomix: resolucao das fontes Vorwerk (CustomFont da KB) para os
papeis da spec ('display', 'corpo', 'corpo_bold').

A spec v3 declara em `fonts` o NOME do CustomFont (ex.: 'Vorwerk-Bold'); aqui
baixamos o arquivo (cache local do font_resolver) e devolvemos paths + um
loader callable(font_key, size_px) no formato que o engine v3 espera.
Fallback: DejaVu (preview nunca quebra por fonte ausente).
"""
import logging

logger = logging.getLogger(__name__)

_DEJAVU_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def font_paths(kb, fonts_map: dict) -> dict:
    """{font_key: path local} para o mapa `fonts` da spec ({key: nome CustomFont})."""
    out = {}
    for key, cf_name in (fonts_map or {}).items():
        path = None
        if kb is not None:
            try:
                from apps.posts.services.font_resolver import _load_custom_font
                cf = kb.custom_fonts.filter(name__iexact=cf_name).first() \
                    or kb.custom_fonts.filter(name__icontains=cf_name).first()
                path = _load_custom_font(cf) if cf else None
            except Exception:
                logger.warning('[thermomix.assets] falha ao resolver fonte %r',
                               cf_name, exc_info=True)
        if not path:
            path = _DEJAVU_BOLD if 'bold' in key or 'display' in key else _DEJAVU
        out[key] = path
    return out


def font_loader(paths: dict):
    """callable(font_key, size_px) -> PIL.ImageFont (contrato do engine v3)."""
    from PIL import ImageFont

    def _font(key, size):
        path = paths.get(key) or _DEJAVU
        try:
            return ImageFont.truetype(path, int(size))
        except Exception:
            return ImageFont.truetype(_DEJAVU, int(size))
    return _font
