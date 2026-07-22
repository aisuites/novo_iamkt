"""
Registry dos pipelines de arte por organizacao (Fase 1.4 do artkit).

Substitui os `if org.slug == '...'` espalhados (views_gerar_simples,
seed_archetypes). ONBOARDAR UMA NOVA ORG com pipeline de arquetipos =
adicionar UMA entrada aqui (+ o pacote services/<org>/ e sua task, ate a
Fase 2 unificar o corpo do pipeline).

Campos por entrada (paths lazy — import so quando usados):
  pipeline_used  valor gravado em Post.pipeline_used
  view           handler que cria o Post e dispara a task (assume o request)
  wireframes     dict {key: spec} do codigo (fonte p/ seed_archetypes)
  context_key    chave da org em Post.local_pipeline_context

NOTA (ate a Fase 2): a task de cada org ainda precisa ser re-importada no fim
de apps/posts/tasks.py para o autodiscovery do Celery registra-la.
"""
from importlib import import_module

ART_PIPELINES = {
    'todxs': {
        'pipeline_used': 'todxs',
        'context_key': 'todxs',
        'view': 'apps.posts.views_gerar_todxs.gerar_post_todxs',
        'wireframes': 'apps.posts.services.todxs.wireframes.WIREFRAMES',
    },
    'vb-gastronomia': {
        'pipeline_used': 'vb',
        'context_key': 'vb',
        'view': 'apps.posts.views_gerar_vb.gerar_post_vb',
        'wireframes': 'apps.posts.services.vb.specs.SPECS',
    },
    'samsung-healthcare': {
        'pipeline_used': 'samsung',
        'context_key': 'samsung',
        'view': 'apps.posts.views_gerar_samsung.gerar_post_samsung',
        'wireframes': 'apps.posts.services.samsung.wireframes.WIREFRAMES',
    },
    # thermomix nasce DIRETO no engine v3 (sem renderizador legado).
    'thermomix': {
        'pipeline_used': 'thermomix',
        'context_key': 'thermomix',
        'view': 'apps.posts.views_gerar_thermomix.gerar_post_thermomix',
        'wireframes': 'apps.posts.services.thermomix.wireframes.WIREFRAMES',
    },
}


def _resolve(path):
    module, attr = path.rsplit('.', 1)
    return getattr(import_module(module), attr)


def get_pipeline(slug):
    """Entrada do registry para o slug, ou None (org sem pipeline de arte)."""
    return ART_PIPELINES.get(slug or '')


def view_for(slug):
    """Handler de geracao da org, ou None (entrada sem view = ainda sem task
    dedicada; a geracao cai no fluxo padrao)."""
    entry = get_pipeline(slug)
    return _resolve(entry['view']) if entry and entry.get('view') else None


def wireframes_for(slug):
    """Dict {key: spec} do codigo da org, ou None (fonte do seed_archetypes)."""
    entry = get_pipeline(slug)
    return _resolve(entry['wireframes']) if entry and entry.get('wireframes') else None
