"""
Degrau 3 da escada: hooks CUSTOM por arquetipo — codigo Python livre, chamado
pela spec via {"name": "custom:<id>"}.

Regra de promocao: nasceu aqui p/ 1 arquetipo; quando uma 2a org quiser algo
parecido, parametriza e sobe pro catalogo (effects/basic.py ou tematico).

Exemplo:
    @register('custom:vb_peixe_especial')
    def vb_peixe_especial(img, draw, params, ctx):
        ...liberdade total sobre o canvas...
"""
from . import register  # noqa: F401 — decorator para os customs
