"""
Aplica os dados extraidos pelo brandguide nos campos da KB e em
ColorPalette/Typography.

Util para:
- Backfill de brandguides que foram processados antes desta feature existir
- Reprocessamento manual em caso de divergencia

Uso:
    python manage.py apply_brandguide_to_kb --brandguide-id 1
    python manage.py apply_brandguide_to_kb --all
    python manage.py apply_brandguide_to_kb --brandguide-id 1 --sync   # roda inline
"""

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import BrandguideUpload
from apps.knowledge.tasks import (
    _apply_brandguide_inner,
    apply_brandguide_to_kb_task,
)


class Command(BaseCommand):
    help = (
        'Aplica resultados de brandguide ja processados na KB '
        '(backfill / reprocessamento)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--brandguide-id',
            type=int,
            help='ID do BrandguideUpload a aplicar',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Aplica em todos os brandguides com brand_visual_spec preenchido',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Roda inline em vez de despachar para Celery (debug)',
        )

    def handle(self, *args, **options):
        bg_id = options.get('brandguide_id')
        run_all = options.get('all')
        sync = options.get('sync')

        if not bg_id and not run_all:
            raise CommandError('Informe --brandguide-id <id> ou --all')

        if bg_id:
            try:
                bg = BrandguideUpload.objects.select_related('knowledge_base').get(id=bg_id)
            except BrandguideUpload.DoesNotExist:
                raise CommandError(f'BrandguideUpload id={bg_id} nao existe')
            targets = [bg]
        else:
            targets = list(
                BrandguideUpload.objects.select_related('knowledge_base').filter(
                    knowledge_base__brand_visual_spec__isnull=False,
                )
            )
            self.stdout.write(f'Encontrados {len(targets)} brandguides com spec.')

        for bg in targets:
            kb = bg.knowledge_base
            self.stdout.write(
                f'-> brandguide_id={bg.id} kb_id={kb.id} org={kb.organization_id} '
                f'status={bg.processing_status}'
            )
            if sync:
                # Chama o nucleo direto para nao depender do contexto Celery
                result = _apply_brandguide_inner(bg)
                # Marca completed manualmente (a task assincrona faria isso)
                from django.utils import timezone
                bg.processing_status = 'completed'
                bg.completed_at = timezone.now()
                bg.save(update_fields=['processing_status', 'completed_at'])
                self.stdout.write(self.style.SUCCESS(f'   inline: {result}'))
            else:
                async_result = apply_brandguide_to_kb_task.delay(bg.id)
                self.stdout.write(
                    self.style.SUCCESS(f'   despachado task_id={async_result.id}')
                )
