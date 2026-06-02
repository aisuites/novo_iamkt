"""
Backfill: gera o dossie visual (ReferenceImage.visual_analysis) das imagens
de referencia ja existentes que ainda nao foram analisadas.

Uso:
    python manage.py analyze_reference_images            # enfileira (Celery)
    python manage.py analyze_reference_images --sync     # analisa inline
    python manage.py analyze_reference_images --org 12   # so uma organizacao
    python manage.py analyze_reference_images --force    # reanalisa tudo
"""

from django.core.management.base import BaseCommand

from apps.knowledge.models import ReferenceImage
from apps.knowledge.tasks import (
    analyze_reference_image_task,
    run_reference_image_analysis,
)


class Command(BaseCommand):
    help = 'Analisa imagens de referencia sem dossie visual (backfill).'

    def add_arguments(self, parser):
        parser.add_argument('--sync', action='store_true',
                            help='Analisa inline em vez de enfileirar no Celery')
        parser.add_argument('--org', type=int, default=None,
                            help='Restringe a uma organization_id')
        parser.add_argument('--force', action='store_true',
                            help='Reanalisa mesmo as ja completed')

    def handle(self, *args, **options):
        qs = ReferenceImage.objects.all()
        if options['org']:
            qs = qs.filter(knowledge_base__organization_id=options['org'])
        if not options['force']:
            qs = qs.filter(analysis_status__in=['pending', 'error'])

        ids = list(qs.values_list('id', flat=True))
        total = len(ids)
        if not total:
            self.stdout.write(self.style.SUCCESS('Nada a analisar.'))
            return

        self.stdout.write(f'{total} imagem(ns) a analisar (sync={options["sync"]}, force={options["force"]}).')

        if not options['sync']:
            for rid in ids:
                analyze_reference_image_task.delay(rid)
            self.stdout.write(self.style.SUCCESS(f'{total} tarefa(s) enfileirada(s) no Celery.'))
            return

        ok = 0
        for rid in ids:
            ref = ReferenceImage.objects.filter(id=rid).first()
            if not ref:
                continue
            if options['force']:
                ref.analysis_status = 'pending'
            try:
                if run_reference_image_analysis(ref):
                    ok += 1
                    self.stdout.write(f'  ✓ ref {rid}')
                else:
                    self.stdout.write(self.style.WARNING(f'  ✗ ref {rid} (falha)'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  ✗ ref {rid}: {exc}'))

        self.stdout.write(self.style.SUCCESS(f'Concluido: {ok}/{total} analisadas.'))
