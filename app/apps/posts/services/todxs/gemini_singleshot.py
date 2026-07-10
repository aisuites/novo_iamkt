"""Shim de compatibilidade: o caller Gemini virou infra compartilhada.

Movido para apps.posts.services.artkit.gemini (Fase 1.3 do artkit) — era
importado por vb/samsung apesar do namespace todxs. Imports novos devem usar
o caminho do artkit; este shim mantem os antigos funcionando.
"""
from apps.posts.services.artkit.gemini import *  # noqa: F401,F403
from apps.posts.services.artkit.gemini import generate_singleshot  # noqa: F401
