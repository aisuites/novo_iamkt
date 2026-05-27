"""
Backfill: gera o dossie visual (BrandgraficModule.visual_analysis) dos
grafismos/elementos ja existentes que ainda nao foram analisados.

Uso:
    python manage.py analyze_brand_assets            # enfileira (Celery)
    python manage.py analyze_brand_assets --sync     # analisa inline
    python manage.py analyze_brand_assets --org 12   # so uma organizacao
    python manage.py analyze_brand_assets --force    # reanalisa tudo
"""

from django.core.management.base import BaseCommand

from apps.knowledge.models import BrandgraficModule
from apps.knowledge.tasks import (
    analyze_brandgrafic_module_task,
    run_brandgrafic_module_analysis,
)


class Command(BaseCommand):
    help = 'Analisa grafismos (BrandgraficModule) sem dossie visual (backfill).'

    def add_arguments(self, parser):
        parser.add_argument('--sync', action='store_true',
                            help='Analisa inline em vez de enfileirar no Celery')
        parser.add_argument('--org', type=int, default=None,
                            help='Restringe a uma organization_id')
        parser.add_argument('--force', action='store_true',
                            help='Reanalisa mesmo os ja completed')

    def handle(self, *args, **options):
        qs = BrandgraficModule.objects.all()
        if options['org']:
            qs = qs.filter(knowledge_base__organization_id=options['org'])
        if not options['force']:
            qs = qs.filter(analysis_status__in=['pending', 'error'])

        ids = list(qs.values_list('id', flat=True))
        total = len(ids)
        if not total:
            self.stdout.write(self.style.SUCCESS('Nada a analisar.'))
            return

        self.stdout.write(f'{total} grafismo(s) a analisar (sync={options["sync"]}, force={options["force"]}).')

        if not options['sync']:
            for aid in ids:
                analyze_brandgrafic_module_task.delay(aid)
            self.stdout.write(self.style.SUCCESS(f'{total} tarefa(s) enfileirada(s) no Celery.'))
            return

        ok = 0
        for aid in ids:
            asset = BrandgraficModule.objects.filter(id=aid).first()
            if not asset:
                continue
            if options['force']:
                asset.analysis_status = 'pending'
            try:
                if run_brandgrafic_module_analysis(asset):
                    ok += 1
                    self.stdout.write(f'  ✓ grafismo {aid}')
                else:
                    self.stdout.write(self.style.WARNING(f'  ✗ grafismo {aid} (falha)'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  ✗ grafismo {aid}: {exc}'))

        self.stdout.write(self.style.SUCCESS(f'Concluido: {ok}/{total} analisados.'))
