"""
Spec v3 — validador + normalizador do dialeto UNICO de arquetipos.
(Fase 2.1 — schema validado ponto a ponto com o dono em 2026-07-08.)

Decisoes de schema (docs/arquitetura-pipeline-escalavel.md + memoria do plano):
  P1  `units: "px"|"pct"` declarada no topo + `canvas` [W,H]. O loader normaliza
      TUDO para fracao (0-1) do canvas; o engine so ve normalizado. Sem mistura
      de unidades na mesma spec.
  P2  Zonas com chaves unificadas; CHAVE DESCONHECIDA NUNCA E ERRO — viaja na
      spec normalizada (plugins/futuro leem).
  P3  `background` declarativo + `effects` = lista ordenada de plugins nomeados
      (catalogo em artkit/effects; `custom:<id>` = hook livre por arquetipo).
      Efeito desconhecido = ERRO CLARO na validacao.
  P4  Texto: `fit: "shrink"|"fixed"` (+ fit_step/min_fs/overflow) e `max_lines`.
      `overflow: "truncate"` NAO EXISTE (descartar texto = bug): use
      "best_effort" ou "rewrite".
  P5  O engine emite elements canonicos (ver artkit/engine.py).

Estrutura autorada (exemplo minimo):
  {
    "spec_version": 3, "name": "...", "canvas": [1080, 1350], "units": "px",
    "formats": ["feed"],
    "background": {"type": "solid|gradient|photo_gemini|photo_ref|photo_upload", ...},
    "zones": [{"key": "titulo", "role": "titulo", "box": [x,y,w,h],
               "font": "head_bold", "fs": 84, "max_lines": 2, "leading": 1.04,
               "color": "accent_blue", "align": "left", "fit": "shrink", ...}],
    "effects": [{"name": "guide_line", "layer": "raw", ...params...}],
    "tokens": {"accent_blue": "#3874B0", ...},        # paleta local (opcional)
    "fonts": {"head_bold": "SamsungSSHead-Bold.otf"}  # papel->arquivo (opcional)
  }

Normalizacao (o que o engine recebe):
  zone.box  -> (fx, fy, fw, fh) fracoes de W/H
  zone.fs   -> fracao de min(W, H)  (mesma base do editor)
  zone.radius, border.width -> fracao de min(W, H)
  Params de EFFECTS ficam crus; o engine entrega ctx.ux/uy/ub para o efeito
  converter na unidade autorada (cada efeito documenta seus params).
"""

BACKGROUND_TYPES = {'solid', 'gradient', 'photo_gemini', 'photo_ref', 'photo_upload'}
FIT_TEXT = {'shrink', 'fixed'}
FIT_IMAGE = {'cover', 'contain'}
OVERFLOW = {'best_effort', 'rewrite'}  # 'truncate' abolido (Ponto 4)

# Chaves oficiais de zona (P2). Extras sao preservadas, nunca rejeitadas.
ZONE_OFFICIAL = {
    'key', 'role', 'box', 'font', 'fs', 'weight', 'color', 'align', 'valign',
    'leading', 'max_lines', 'case', 'tracking', 'fit', 'fit_step', 'min_fs',
    'overflow', 'radius', 'round_corners', 'border', 'asset', 'optional',
    'anchor', 'halign', 'category', 'note',
}


class SpecError(ValueError):
    """Spec v3 invalida — mensagem lista TODOS os problemas de uma vez."""


def validate(spec: dict) -> list:
    """Retorna lista de erros (vazia = valida). Nao altera a spec."""
    errs = []
    if not isinstance(spec, dict):
        return ['spec deve ser um objeto JSON']
    if spec.get('spec_version') != 3:
        errs.append("spec_version deve ser 3")
    canvas = spec.get('canvas')
    if (not isinstance(canvas, (list, tuple)) or len(canvas) != 2
            or not all(isinstance(v, (int, float)) and v > 0 for v in canvas)):
        errs.append('canvas deve ser [W, H] positivos')
    units = spec.get('units', 'pct')
    if units not in ('px', 'pct'):
        errs.append("units deve ser 'px' ou 'pct'")

    bg = spec.get('background') or {}
    if bg and bg.get('type') not in BACKGROUND_TYPES:
        errs.append(f"background.type invalido: {bg.get('type')!r} "
                    f"(opcoes: {sorted(BACKGROUND_TYPES)})")

    zones = spec.get('zones')
    if not isinstance(zones, list):
        errs.append('zones deve ser uma lista')
        zones = []
    seen = set()
    for i, z in enumerate(zones):
        tag = f"zones[{i}]"
        if not isinstance(z, dict) or not z.get('key'):
            errs.append(f'{tag}: zona sem key')
            continue
        tag = f"zona {z['key']!r}"
        if z['key'] in seen:
            errs.append(f'{tag}: key duplicada')
        seen.add(z['key'])
        box = z.get('box')
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or not all(isinstance(v, (int, float)) for v in box)):
            errs.append(f'{tag}: box deve ser [x, y, w, h] numericos')
        fit = z.get('fit')
        if fit is not None and fit not in (FIT_TEXT | FIT_IMAGE):
            errs.append(f"{tag}: fit invalido {fit!r} "
                        f"(texto: {sorted(FIT_TEXT)}; imagem: {sorted(FIT_IMAGE)})")
        ov = z.get('overflow')
        if ov is not None and ov not in OVERFLOW:
            extra = ' — truncate foi ABOLIDO (Ponto 4): texto nunca e descartado' \
                if ov == 'truncate' else ''
            errs.append(f'{tag}: overflow invalido {ov!r}{extra}')

    effects = spec.get('effects') or []
    if not isinstance(effects, list):
        errs.append('effects deve ser uma lista')
        effects = []
    from apps.posts.services.artkit.effects import known_effect
    for i, e in enumerate(effects):
        if not isinstance(e, dict) or not e.get('name'):
            errs.append(f'effects[{i}]: efeito sem name')
            continue
        if not known_effect(e['name']):
            errs.append(f"effects[{i}]: efeito desconhecido {e['name']!r} — "
                        f"registre em artkit/effects (ou use 'custom:<id>')")
    return errs


def normalize(spec: dict) -> dict:
    """Valida e devolve a spec NORMALIZADA (fracoes). Raises SpecError."""
    errs = validate(spec)
    if errs:
        raise SpecError('; '.join(errs))

    W, H = spec['canvas']
    basis = float(min(W, H))
    units = spec.get('units', 'pct')

    def fx(v):  # eixo X -> fracao de W
        return float(v) / W if units == 'px' else float(v) / 100.0
    def fy(v):  # eixo Y -> fracao de H
        return float(v) / H if units == 'px' else float(v) / 100.0
    def fb(v):  # tamanhos "isotropicos" (fonte, radius, stroke) -> fracao da base
        return float(v) / basis if units == 'px' else float(v) / 100.0

    out = dict(spec)  # chaves desconhecidas do topo viajam (P2)
    out['canvas'] = (int(W), int(H))
    out['_normalized'] = True

    zones = []
    for z in spec['zones']:
        nz = dict(z)  # extras preservadas
        x, y, w, h = z['box']
        nz['box'] = (fx(x), fy(y), fx(w), fy(h))
        if 'fs' in z:
            nz['fs'] = fb(z['fs'])
        if 'min_fs' in z:
            nz['min_fs'] = fb(z['min_fs'])
        if 'radius' in z:
            nz['radius'] = fb(z['radius'])
        if isinstance(z.get('border'), dict) and 'width' in z['border']:
            nz['border'] = dict(z['border'], width=fb(z['border']['width']))
        zones.append(nz)
    out['zones'] = zones
    return out


def unit_helpers(spec_norm: dict, authored_units: str = None):
    """ctx.ux/uy/ub para EFFECTS converterem params (na unidade AUTORADA) -> px.
    Cada efeito documenta quais params sao geometricos."""
    W, H = spec_norm['canvas']
    basis = min(W, H)
    units = authored_units or spec_norm.get('units', 'pct')
    if units == 'px':
        return {'ux': lambda v: int(round(float(v))),
                'uy': lambda v: int(round(float(v))),
                'ub': lambda v: int(round(float(v)))}
    return {'ux': lambda v: int(round(float(v) / 100.0 * W)),
            'uy': lambda v: int(round(float(v) / 100.0 * H)),
            'ub': lambda v: int(round(float(v) / 100.0 * basis))}
