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


def _presigned(logo):
    try:
        from apps.core.services.s3_service import S3Service
        return S3Service.generate_presigned_download_url(logo.s3_key, expires_in=3600)
    except Exception:
        return logo.s3_url or None


# slot da spec -> termo no NOME do asset da KB (estavel entre dev/prod)
_ICON_SLOTS = {
    'icone_calendario': 'calendar',
    'icone_pessoas': 'user',
    'icone_whatsapp': 'whatsapp',
}


def resolve_asset_urls(kb) -> dict:
    """{slot: url} dos assets da KB para os slots da spec (dono, 2026-07-22):
      brand_lockup (topo)       = Logo versao 'white' vertical (sobre foto)
      distribuidor (assinatura) = Logo versao 'horizontal'
      icone_calendario/pessoas/whatsapp = BrandgraficModule com
        'calendar'/'user'/'whatsapp' no nome
    Regra por NOME (estavel entre dev/prod); ausente = slot vazio (o engine
    pula a zona)."""
    out = {}
    if kb is None:
        return out
    try:
        from apps.knowledge.models import Logo
        logos = [l for l in Logo.objects.filter(knowledge_base=kb).order_by('id')
                 if not (l.name or '').startswith('._')]

        def _norm(s):
            return (s or '').lower().replace('_', ' ')

        def _pick(term, evitar='negative'):
            cands = [l for l in logos if term in _norm(l.name)]
            # prod tem variantes 'negative': prefere a SEM negative
            return next((l for l in cands if evitar not in _norm(l.name)),
                        cands[0] if cands else None)
        # topo: lockup 'thermomix workshop' dedicado (Logo WS, dono 2026-07-22)
        # quando existir na KB; fallback = versao white vertical
        topo = _pick('logo ws') or _pick('white')
        horiz = _pick('horizontal')
        if topo:
            out['brand_lockup'] = _presigned(topo)
        if horiz:
            out['distribuidor'] = _presigned(horiz)
    except Exception:
        logger.warning('[thermomix.assets] falha ao resolver lockups', exc_info=True)
    try:
        from apps.knowledge.models import BrandgraficModule
        mods = list(BrandgraficModule.objects.filter(knowledge_base=kb))
        for slot, term in _ICON_SLOTS.items():
            m = next((g for g in mods if term in (g.name or '').lower()), None)
            if m:
                out[slot] = _presigned(m)
    except Exception:
        logger.warning('[thermomix.assets] falha ao resolver icones', exc_info=True)
    return {k: v for k, v in out.items() if v}


def font_paths(kb, fonts_map: dict) -> dict:
    """{font_key: path local} para o mapa `fonts` da spec ({key: nome CustomFont})."""
    out = {}
    for key, cf_name in (fonts_map or {}).items():
        path = None
        if kb is not None:
            try:
                from apps.posts.services.font_resolver import _load_custom_font
                # exclui lixo AppleDouble do macOS ('._Vorwerk-*'): nao e fonte
                fontes = kb.custom_fonts.exclude(name__startswith='._')
                cf = fontes.filter(name__iexact=cf_name).first() \
                    or fontes.filter(name__icontains=cf_name).first()
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
