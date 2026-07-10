"""
Catalogo de EFFECTS do engine v3 (Ponto 3 — escada de 3 degraus).

Degrau 2: efeitos nomeados aqui, parametrizados pela spec, reusaveis por TODAS
as orgs. Degrau 3: `custom:<id>` — codigo livre por arquetipo, registrado em
effects/custom.py (a valvula de escape explicita).

Governanca (validada com o dono):
  1. Nasce custom p/ 1 arquetipo; 2+ usos -> parametriza e sobe pro catalogo.
  2. Efeito desconhecido = ERRO CLARO na validacao da spec (nunca silencio).
  3. Efeito novo entra acompanhado de golden.

Assinatura de um efeito:
  def meu_efeito(img, draw, params: dict, ctx: dict) -> Image|None
    img/draw  canvas atual (PIL) — retorne uma NOVA Image para substituir
              (efeitos de composicao, ex. scrim) ou None se desenhou in-place.
    params    dict cru da spec (efeito converte geometria com ctx['ux'/'uy'/'ub'])
    ctx       {'ux','uy','ub' (unidade autorada -> px), 'color' (token->hex),
               'assets', 'canvas' (W,H), 'fonts'...}
Params opcionais universais (o ENGINE interpreta, nao o efeito):
  layer: 'raw'|'final'  (default 'raw' — antes do snapshot editavel)
  only_if: '<asset>'    (so roda se ctx['assets'][asset] existir; ex. scrim
                         apenas quando ha foto de fundo)
"""
_REGISTRY = {}


def register(name):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


def known_effect(name: str) -> bool:
    if name.startswith('custom:'):
        from . import custom  # noqa: F401 — registra os customs
        return name in _REGISTRY
    _load_builtin()
    return name in _REGISTRY


def get_effect(name: str):
    if not known_effect(name):
        raise KeyError(
            f"efeito {name!r} nao registrado no catalogo (artkit/effects). "
            f"Disponiveis: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


_loaded = False


def _load_builtin():
    global _loaded
    if not _loaded:
        from . import basic  # noqa: F401
        _loaded = True
