"""
Preview DETERMINISTICO de um arquetipo a partir da spec do BANCO (PostArchetype),
com conteudo de exemplo — SEM brain (Claude) e SEM Gemini. Sustenta o loop de
refinamento de arquetipos (docs/arquitetura-pipeline-escalavel.md §2.1):
edita a spec (admin/shell) -> roda o preview -> valida o PNG -> repete.

  python manage.py render_archetype_preview --org todxs --archetype A
  python manage.py render_archetype_preview --org vb-gastronomia --archetype 01
  python manage.py render_archetype_preview --org samsung-healthcare --archetype B \
      --content '{"title": "Titulo custom"}' --out /tmp/preview.png

Onde ha foto no layout, usa um placeholder cinza. --content (JSON) sobrepoe o
conteudo de exemplo. A logica de render vive em services/preview.py (compartilhada
com o golden_archetypes).
"""
import json

from django.core.management.base import BaseCommand

from apps.core.models import Organization


class Command(BaseCommand):
    help = 'Renderiza preview deterministico de um arquetipo (spec do banco + conteudo de exemplo).'

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help='slug da organizacao')
        parser.add_argument('--archetype', required=True, help='key do arquetipo (ex.: A, 01)')
        parser.add_argument('--format', default=None, help='feed|story (default: o do arquetipo)')
        parser.add_argument('--color', default=None, help='hex da cor de fundo (orgs com paleta)')
        parser.add_argument('--content', default=None, help='JSON que sobrepoe o conteudo de exemplo')
        parser.add_argument('--out', default=None, help='caminho do PNG (default /tmp/preview_<org>_<arch>.png)')

    def handle(self, *args, **o):
        from apps.knowledge.models import KnowledgeBase
        from apps.posts.services.preview import render_preview

        slug = o['org']
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'org slug={slug!r} nao encontrada'))
            return
        kb = KnowledgeBase.objects.filter(organization=org).first()
        override = json.loads(o['content']) if o['content'] else {}
        out_path = o['out'] or f'/tmp/preview_{slug}_{o["archetype"]}.png'

        try:
            png = render_preview(org, kb, o['archetype'], fmt=o['format'],
                                 color=o['color'], content_override=override)
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        with open(out_path, 'wb') as f:
            f.write(png)
        self.stdout.write(self.style.SUCCESS(f'OK: {out_path}'))
