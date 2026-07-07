"""
Catalogo data-driven dos arquetipos da VB Gastronomia (espelha todxs/catalog.py).

A spec de cada arquetipo pode vir do banco (PostArchetype) por organizacao. Assim,
correcoes via admin refletem na arte sem deploy.

  load_org_specs(org) -> {key: spec}  (banco SOBRE o codigo; fallback total
                                       = SPECS do codigo)
  apply_org_specs(org) -> seta esse dict no contextvar que o renderizador le (SP()).
"""
import logging

logger = logging.getLogger(__name__)


def load_org_specs(org) -> dict:
    """{key: spec} da org: comeca do SPECS do codigo e sobrepoe as specs
    cadastradas (ativas) no banco. Se o banco estiver vazio, devolve o codigo."""
    from .specs import SPECS
    merged = dict(SPECS)
    if org is None:
        return merged
    try:
        from apps.posts.models import PostArchetype
        for a in PostArchetype.objects.filter(organization=org, is_active=True):
            if isinstance(a.spec, dict) and a.spec:
                merged[a.key] = a.spec
    except Exception:
        logger.warning('[vb.catalog] falha ao carregar specs do banco', exc_info=True)
    return merged


def apply_org_specs(org):
    """Seta o conjunto de specs da org no contextvar do renderizador (SP())."""
    from .specs import set_specs
    set_specs(load_org_specs(org))
