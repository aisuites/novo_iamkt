"""
Catalogo data-driven dos arquetipos thermomix (espelha samsung/catalog.py).

  load_org_wireframes(org) -> {key: spec v3} (banco SOBRE o codigo)
  apply_org_wireframes(org) -> seta no contextvar que o renderizador le (WF()).
"""
import logging

logger = logging.getLogger(__name__)


def load_org_wireframes(org) -> dict:
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
        logger.warning('[thermomix.catalog] falha ao carregar specs do banco',
                       exc_info=True)
    return merged


def apply_org_wireframes(org):
    from .wireframes import set_wireframes
    set_wireframes(load_org_wireframes(org))
