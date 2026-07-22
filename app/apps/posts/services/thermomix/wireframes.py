"""
Specs v3 dos arquetipos thermomix (espelha samsung/wireframes.py, mas ja NASCE
no dialeto v3 — nao ha renderizador legado).

WIREFRAMES (codigo) = authored.py convertido por convert.authored_to_v3.
Em runtime o render le WF() (contextvar): catalog.apply_org_wireframes(org)
carrega o banco (PostArchetype) SOBRE este codigo — edicao no admin reflete
na arte sem deploy.
"""
from contextvars import ContextVar

from .authored import AUTHORED
from .convert import authored_to_v3, default_content

WIREFRAMES = {key: authored_to_v3(a) for key, a in AUTHORED.items()}

# Conteudo-exemplo por arquetipo (preview / conteudo_fixo inicial do portao)
DEFAULT_CONTENT = {key: default_content(a) for key, a in AUTHORED.items()}

_wireframes: ContextVar = ContextVar('thermomix_wireframes', default=None)


def WF() -> dict:
    """Specs v3 ativas neste contexto (banco-sobre-codigo, ou o codigo puro)."""
    return _wireframes.get() or WIREFRAMES


def set_wireframes(specs: dict):
    _wireframes.set(specs)
