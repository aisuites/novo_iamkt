"""
Renderiza um VisualTemplate com dados mockados para validacao visual.
Util para iterar no Compose Engine sem precisar passar pelo fluxo completo.

Uso:
    python manage.py render_template --template-id 50 --output /tmp/test.png
    python manage.py render_template --org-slug colletivo --name speaker_card_horizontal_landscape
    python manage.py render_template --org-slug colletivo --first 3  # renderiza os 3 primeiros
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Organization
from apps.knowledge.models import KnowledgeBase, VisualTemplate
from apps.posts.compose_engine import ComposeEngine


class Command(BaseCommand):
    help = 'Renderiza VisualTemplate(s) com dados mockados para validacao visual'

    def add_arguments(self, parser):
        parser.add_argument('--template-id', type=int)
        parser.add_argument('--name', help='Nome do template (alternativa ao id)')
        parser.add_argument('--org-slug', default='colletivo')
        parser.add_argument('--output', default='/tmp/render_test.png',
                            help='Caminho para salvar PNG (single mode)')
        parser.add_argument('--first', type=int, default=0,
                            help='Renderiza os N primeiros templates da KB (multi mode)')
        parser.add_argument('--output-dir', default='/tmp/renders',
                            help='Diretorio para multi mode')

    def handle(self, *args, **opts):
        slug = opts['org_slug']
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f'Org slug={slug!r} nao encontrada')

        kb = KnowledgeBase.objects.filter(organization=org).first()
        if not kb:
            raise CommandError(f'Org {org.name} nao tem KnowledgeBase')

        spec = kb.brand_visual_spec or {}
        if not spec.get('versao'):
            self.stdout.write(self.style.WARNING(
                'KB.brand_visual_spec nao parece estar em v2 (sem campo "versao"). '
                'Rode populate_colletivo_v2 antes.'
            ))

        # Single mode
        if opts.get('template_id') or opts.get('name'):
            template = self._get_template(kb, opts)
            self._render_one(template, spec, opts['output'])
            return

        # Multi mode
        n = opts.get('first') or 0
        if n <= 0:
            n = 3
        import os
        os.makedirs(opts['output_dir'], exist_ok=True)
        templates = VisualTemplate.objects.filter(knowledge_base=kb).order_by('id')[:n]
        for t in templates:
            safe_name = t.name.replace('/', '_').replace(' ', '_')
            out_path = os.path.join(opts['output_dir'], f'{t.id}_{safe_name}.png')
            self._render_one(t, spec, out_path)

    def _get_template(self, kb, opts) -> VisualTemplate:
        if opts.get('template_id'):
            try:
                return VisualTemplate.objects.get(id=opts['template_id'])
            except VisualTemplate.DoesNotExist:
                raise CommandError(f'Template id={opts["template_id"]} nao existe')
        if opts.get('name'):
            try:
                return VisualTemplate.objects.get(knowledge_base=kb, name=opts['name'])
            except VisualTemplate.DoesNotExist:
                raise CommandError(f'Template name={opts["name"]!r} nao encontrado na KB')
        raise CommandError('Forneca --template-id ou --name')

    def _render_one(self, template: VisualTemplate, brand_spec: dict, output: str):
        tpl_spec = template.template_spec or {}
        # Mock: usa exemplo_conteudo de cada region como content
        content = {}
        for region in tpl_spec.get('regions', []):
            rid = region.get('id')
            if rid:
                content[rid] = region.get('exemplo_conteudo') or ''

        engine = ComposeEngine(
            template_spec=tpl_spec,
            content=content,
            brand_visual_spec=brand_spec,
            kb=template.knowledge_base,
        )
        try:
            n_bytes = engine.render_to_file(output)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f'  [FAIL] {template.name}: {exc}'
            ))
            return
        regions = len(tpl_spec.get('regions') or [])
        size = engine._resolve_dimensions()
        self.stdout.write(self.style.SUCCESS(
            f'  [OK] {template.name} ({template.aspect_ratio}, {size[0]}x{size[1]}, '
            f'{regions} regions) -> {output} ({n_bytes} bytes)'
        ))
