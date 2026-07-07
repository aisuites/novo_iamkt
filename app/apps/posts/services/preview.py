"""
Render DETERMINISTICO de arquetipos com conteudo de exemplo — sem Claude/Gemini.

Usado por:
  - management command `render_archetype_preview` (loop de refinamento de spec)
  - management command `golden_archetypes` (golden files do refactor artkit/v3)

A spec vem do BANCO (PostArchetype, via catalogos por org); fotos viram
placeholder cinza (o objetivo e validar geometria/tipografia, nao imagem).
"""
import io

# Texto de exemplo por chave de zona (fallback: "[<key> de exemplo]").
SAMPLE_TEXT = {
    'kicker': 'Kicker de exemplo',
    'titulo': 'Título de exemplo do arquétipo',
    'title': 'Título de exemplo do arquétipo',
    'apoio': ('Texto de apoio de exemplo para validar espaçamentos, quebras de '
              'linha e a hierarquia tipográfica do arquétipo.'),
    'body': ('Texto de corpo de exemplo para validar espaçamentos, quebras de '
             'linha e a hierarquia tipográfica.'),
    'meta': 'meta · exemplo',
    'assinatura': 'Assinatura de exemplo',
    'signature_name': 'Nome de Exemplo',
    'cta': 'Saiba mais',
}

# Cor FIXA para goldens/previews do todxs quando nenhuma for pedida:
# deterministico independente da ordem da paleta na KB.
TODXS_DEFAULT_COLOR = '#F25C05'


def sample_content(keys):
    return {k: SAMPLE_TEXT.get(k, f'[{k} de exemplo]') for k in keys}


def placeholder_photo_png(w=1080, h=1350):
    """Foto neutra (cinza) para arquétipos com fundo/moldura de foto."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (128, 128, 128)).save(buf, 'PNG')
    return buf.getvalue()


def list_cases(org):
    """[(archetype_key, fmt)] disponiveis para a org (specs do banco+codigo)."""
    slug = org.slug
    if slug == 'vb-gastronomia':
        from apps.posts.services.vb.catalog import apply_org_specs
        from apps.posts.services.vb.specs import SP
        apply_org_specs(org)
        return [(k, (s.get('formato') or 'feed')) for k, s in sorted(SP().items())]
    if slug == 'samsung-healthcare':
        from apps.posts.services.samsung.catalog import apply_org_wireframes
        from apps.posts.services.samsung.wireframes import WF
        apply_org_wireframes(org)
        return [(k, f) for k, s in sorted(WF().items())
                for f in (s.get('formatos') or ['feed'])]
    from apps.posts.services.todxs.catalog import apply_org_wireframes
    from apps.posts.services.todxs.wireframes import WF
    apply_org_wireframes(org)
    return [(k, f) for k, s in sorted(WF().items())
            for f in sorted((s.get('zonas') or {}).keys())]


def render_preview(org, kb, archetype, fmt=None, color=None, content_override=None):
    """PNG (bytes) do arquetipo com conteudo de exemplo. Raises ValueError."""
    slug = org.slug
    override = content_override or {}
    if slug == 'vb-gastronomia':
        return _vb(org, kb, archetype, fmt, color, override)
    if slug == 'samsung-healthcare':
        return _samsung(org, kb, archetype, fmt, color, override)
    return _todxs(org, kb, archetype, fmt, color, override)


# ---- adaptadores por dialeto (unificam na spec v3 / Fase 2) -----------------

def _todxs(org, kb, archetype, fmt, color, override):
    from apps.posts.services.todxs.catalog import apply_org_wireframes
    from apps.posts.services.todxs.wireframes import WF
    from apps.posts.services.todxs import pillow_render

    apply_org_wireframes(org)
    spec = WF().get(archetype)
    if not spec:
        raise ValueError(f'arquetipo {archetype!r} nao existe (tem: {sorted(WF().keys())})')
    fmt = fmt or (spec.get('formatos') or ['feed'])[0]
    zonas = (spec.get('zonas') or {}).get(fmt)
    if zonas is None:
        raise ValueError(f'arquetipo {archetype!r} nao tem formato {fmt!r} '
                         f'(tem: {sorted((spec.get("zonas") or {}).keys())})')
    formato_px = '1080x1920' if fmt == 'story' else '1080x1350'
    content = sample_content([z['key'] for z in zonas])
    content.update(override)

    color_hex = color or TODXS_DEFAULT_COLOR

    photo_png = None
    if spec.get('fundo') == 'photo':
        w, h = (1080, 1920) if fmt == 'story' else (1080, 1350)
        photo_png = placeholder_photo_png(w, h)

    x_png, logo_url = None, None
    try:
        from apps.posts.services.todxs.assets import todxs_simbolo_url, todxs_wordmark_url
        logo_url = todxs_wordmark_url(kb) if kb else None
        simbolo_url = todxs_simbolo_url(kb) if kb else None
        if simbolo_url:
            import requests
            x_png = requests.get(simbolo_url, timeout=20).content
    except Exception:
        pass  # preview segue sem selo/wordmark

    pr = pillow_render.render_todxs(
        archetype=archetype, content=content, color_hex=color_hex, fmt=fmt,
        formato_px=formato_px, kb=kb, photo_png=photo_png,
        x_png_bytes=x_png, logo_url=logo_url)
    return pr['final_png']


def _vb(org, kb, archetype, fmt, color, override):
    from apps.posts.services.vb.catalog import apply_org_specs
    from apps.posts.services.vb.specs import SP
    from apps.posts.services.vb.render import render_vb

    apply_org_specs(org)
    spec = SP().get(archetype)
    if not spec:
        raise ValueError(f'arquetipo {archetype!r} nao existe (tem: {sorted(SP().keys())})')
    fmt = fmt or spec.get('formato', 'feed')
    content = sample_content([z['key'] for z in spec.get('zones', [])])
    content.update(override)

    photo_png = None
    if (spec.get('bg', {}).get('type') == 'photo') or spec.get('foto_frame'):
        w, h = spec.get('canvas', [1080, 1350])
        photo_png = placeholder_photo_png(w, h)

    pr = render_vb(archetype, content, color_hex=color, fmt=fmt, kb=kb,
                   photo_png=photo_png)
    return pr['final_png']


def _samsung(org, kb, archetype, fmt, color, override):
    from apps.posts.services.samsung.catalog import apply_org_wireframes
    from apps.posts.services.samsung.wireframes import WF
    from apps.posts.services.samsung.render import render_samsung

    apply_org_wireframes(org)
    spec = WF().get(archetype)
    if not spec:
        raise ValueError(f'arquetipo {archetype!r} nao existe (tem: {sorted(WF().keys())})')
    keys = [z['key'] for z in spec.get('zones', [])
            if z.get('category') not in ('image', 'partner_logo')]
    content = sample_content(keys)
    content.update(override)

    pr = render_samsung(archetype=archetype, content=content, kb=kb, assets={})
    return pr['final_png']
