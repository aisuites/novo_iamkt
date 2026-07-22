"""
Semeia/atualiza o catalogo PostArchetype a partir do WIREFRAMES (codigo) para
uma organizacao (default: todxs).

Idempotente. Por padrao NAO sobrescreve a `spec` de arquetipos ja existentes
(preserva correcoes feitas no admin); use --resync-spec para reimportar do codigo.

  python manage.py seed_archetypes                 # cria os que faltam (org todxs)
  python manage.py seed_archetypes --resync-spec   # reimporta a spec do codigo
  python manage.py seed_archetypes --org outra
"""
from django.core.management.base import BaseCommand

from apps.core.models import Organization
from apps.posts.models import PostArchetype

# Nomes amigaveis por org (fallback ao spec['name']); admin pode renomear depois.
FRIENDLY_BY_ORG = {
    'todxs': {
        'A': 'Capa tipografica',
        'B': 'Foto + faixa',
        'B_DUO': 'Foto duotone + faixa',
        'C': 'Noticia (P&B)',
        'C_DISPLAY': 'Display (manchete gigante)',
        'D': 'Retrato + wordmark',
        'E': 'Story — lista de blocos',
        'F': 'Story duotone',
    },
}


def _wireframes_for(slug: str) -> dict:
    """Fonte de specs por org — resolvida pelo REGISTRY do artkit."""
    from apps.posts.services.artkit.registry import wireframes_for
    return wireframes_for(slug)


def _fmt(spec) -> str:
    # todxs/samsung: spec['formatos'] = lista; vb: spec['formato'] = string;
    # specs v3 (thermomix): spec['formats'] = lista.
    formatos = (spec.get('formatos') or spec.get('formats')
                or ([spec['formato']] if spec.get('formato') else None))
    s = set(formatos or ['feed'])
    if {'feed', 'story'} <= s:
        return 'both'
    return 'story' if 'story' in s else 'feed'


class Command(BaseCommand):
    help = 'Semeia/atualiza PostArchetype a partir do WIREFRAMES (codigo).'

    def add_arguments(self, parser):
        parser.add_argument('--org', default='todxs', help='slug da organizacao')
        parser.add_argument('--resync-spec', action='store_true',
                            help='sobrescreve a spec de arquetipos existentes (perde edicoes do admin)')

    def handle(self, *args, **opts):
        slug = opts['org']
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'org slug={slug!r} nao encontrada'))
            return

        wireframes = _wireframes_for(slug)
        if wireframes is None:
            self.stderr.write(self.style.ERROR(
                f'org {slug!r} nao tem pipeline de arquetipos no registry '
                f'(services/artkit/registry.py)'))
            return
        friendly = FRIENDLY_BY_ORG.get(slug, {})
        for order, (key, spec) in enumerate(wireframes.items(), start=1):
            fmt = _fmt(spec)
            name = friendly.get(key) or spec.get('name') or key
            obj, created = PostArchetype.objects.get_or_create(
                organization=org, key=key,
                defaults={'name': name, 'format': fmt, 'spec': spec,
                          'order': order, 'is_active': True},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  + {key:10s} ({fmt})'))
            else:
                obj.format = fmt
                obj.order = order
                if not obj.name:
                    obj.name = name
                if opts['resync_spec']:
                    obj.spec = spec
                obj.save()
                tag = ' [spec resync]' if opts['resync_spec'] else ''
                self.stdout.write(f'  ~ {key:10s} ({fmt}){tag}')

        total = PostArchetype.objects.filter(organization=org).count()
        self.stdout.write(self.style.SUCCESS(f'OK: {total} arquetipos para org={slug}'))
