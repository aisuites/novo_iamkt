"""
Catalogo data-driven dos arquetipos Samsung Healthcare (espelha todxs/catalog.py).

A spec de cada arquetipo (zonas, coords, fontes, tratamento) pode vir do banco
(PostArchetype) por organizacao. Assim, correcoes via admin refletem na arte sem
deploy, e (futuramente) um agente preenche a spec a partir de wireframe+imagem.

  load_org_wireframes(org) -> {key: spec}  (banco SOBRE o codigo; fallback total
                                            = WIREFRAMES do codigo)
  apply_org_wireframes(org) -> seta esse dict no contextvar que o renderizador le.
"""
import logging

logger = logging.getLogger(__name__)


def load_org_wireframes(org) -> dict:
    """{key: spec} da org: comeca do WIREFRAMES do codigo e sobrepoe as specs
    cadastradas (ativas) no banco. Se o banco estiver vazio, devolve o codigo."""
    from .wireframes import WIREFRAMES
    merged = dict(WIREFRAMES)
    if org is None:
        return merged
    try:
        from apps.posts.models import PostArchetype
        for a in PostArchetype.objects.filter(organization=org, is_active=True):
            if isinstance(a.spec, dict) and a.spec:
                merged[a.key] = a.spec
    except Exception:
        logger.warning('[samsung.catalog] falha ao carregar specs do banco', exc_info=True)
    return merged


def apply_org_wireframes(org):
    """Seta o conjunto de specs da org no contextvar do renderizador (WF())."""
    from .wireframes import set_wireframes
    set_wireframes(load_org_wireframes(org))
