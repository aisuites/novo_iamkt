"""
Popula a Colletivo (org=23, slug=colletivo) com o brand_visual_spec v2
estrutural e os 26 VisualTemplate extraidos do brandguide via Claude.

Idempotente: pode rodar varias vezes. O brand_visual_spec v1 (do N8N)
e preservado em brand_visual_spec_v1_backup antes de sobrescrever.

Uso:
    python manage.py populate_colletivo_v2
    python manage.py populate_colletivo_v2 --dry-run
    python manage.py populate_colletivo_v2 --org-slug colletivo

Arquivo de origem: apps/knowledge/data/colletivo_spec_v2_seed.json
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Organization
from apps.knowledge.models import (
    BrandguidePage, BrandguideUpload, KnowledgeBase, VisualTemplate,
)


SEED_PATH = Path(__file__).resolve().parent.parent.parent / 'data' / 'colletivo_spec_v2_seed.json'


class Command(BaseCommand):
    help = 'Popula a KB da Colletivo com brand_visual_spec v2 + 26 VisualTemplate.'

    def add_arguments(self, parser):
        parser.add_argument('--org-slug', default='colletivo', help='Slug da org (default: colletivo)')
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que faria sem gravar')

    def handle(self, *args, **opts):
        slug = opts['org_slug']
        dry = opts['dry_run']

        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f'Organization slug={slug!r} nao existe.')

        kb = KnowledgeBase.objects.filter(organization=org).first()
        if not kb:
            raise CommandError(f'Organization {org.name} nao tem KnowledgeBase.')

        if not SEED_PATH.exists():
            raise CommandError(f'Seed file nao encontrado em {SEED_PATH}')

        with open(SEED_PATH, encoding='utf-8') as f:
            seed = json.load(f)
        spec_v2 = seed.get('brand_visual_spec_v2') or {}
        templates_seed = seed.get('templates') or []

        if not spec_v2 or not templates_seed:
            raise CommandError('Seed file vazio ou malformado.')

        # Brandguide upload mais recente da org (para vincular VisualTemplate.source_page)
        bg = (
            BrandguideUpload.objects
            .filter(knowledge_base=kb, processing_status='completed')
            .order_by('-completed_at', '-id')
            .first()
        )

        self.stdout.write(f'Organization: {org.name} (id={org.id}, slug={slug})')
        self.stdout.write(f'KnowledgeBase: id={kb.id}')
        self.stdout.write(f'BrandguideUpload: id={bg.id if bg else None}')
        self.stdout.write(f'Spec v2 keys: {list(spec_v2.keys())}')
        self.stdout.write(f'Templates a popular: {len(templates_seed)}')

        if dry:
            self.stdout.write(self.style.WARNING('\nDRY RUN - nada sera gravado.'))
            return

        with transaction.atomic():
            # 1. Backup do spec v1 atual (se ainda nao foi feito)
            if kb.brand_visual_spec and not kb.brand_visual_spec_v1_backup:
                kb.brand_visual_spec_v1_backup = kb.brand_visual_spec
                self.stdout.write(self.style.SUCCESS('  ✓ Backup do v1 salvo em brand_visual_spec_v1_backup'))
            elif kb.brand_visual_spec_v1_backup:
                self.stdout.write(self.style.WARNING('  ↻ Backup do v1 ja existe, nao sobrescrito'))

            # 2. Substitui pelo spec v2
            kb.brand_visual_spec = spec_v2
            kb.brand_visual_spec_source = 'brandguide_pdf'
            kb.brand_visual_spec_confidence = 'high'
            kb.brand_visual_spec_validated = False
            kb.save(update_fields=[
                'brand_visual_spec', 'brand_visual_spec_v1_backup',
                'brand_visual_spec_source', 'brand_visual_spec_confidence',
                'brand_visual_spec_validated',
            ])
            self.stdout.write(self.style.SUCCESS('  ✓ brand_visual_spec atualizado para v2'))

            # 3. Popula VisualTemplate (upsert por nome dentro da KB)
            created = 0
            updated = 0
            for t in templates_seed:
                name = t.get('nome_inferido') or 'template_sem_nome'
                aspect = t.get('format_aspect') or ''

                # Map format_aspect -> template_type
                if aspect in ('1:1',):
                    template_type = 'quadrado'
                elif aspect in ('9:16',):
                    template_type = 'story'
                elif aspect in ('4:5', '16:9'):
                    template_type = 'feed'
                else:
                    template_type = 'outro'

                # Pega source_page e tenta linkar com BrandguidePage para thumbnail
                source_pages = t.get('source_pages') or []
                thumb_page = t.get('thumbnail_page') or (source_pages[0] if source_pages else None)
                s3_key = ''
                s3_url = ''
                if thumb_page and bg:
                    page = BrandguidePage.objects.filter(
                        brandguide=bg, page_number=thumb_page
                    ).first()
                    if page:
                        s3_key = page.s3_key or ''
                        s3_url = page.s3_url or ''

                obj, created_flag = VisualTemplate.objects.update_or_create(
                    knowledge_base=kb,
                    name=name,
                    defaults={
                        'template_type': template_type,
                        'aspect_ratio': aspect,
                        'template_spec': t,
                        'source': 'pdf_extracted',
                        'source_page': thumb_page,
                        's3_key': s3_key,
                        's3_url': s3_url,
                        'description': ', '.join(t.get('regras_aplicadas', [])[:3])[:500],
                        'approved_by_user': False,
                        'is_active': True,
                    },
                )
                if created_flag:
                    created += 1
                    self.stdout.write(f'  + {name} ({aspect}) [novo]')
                else:
                    updated += 1
                    self.stdout.write(f'  ↻ {name} ({aspect}) [atualizado]')

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'OK: {created} criados + {updated} atualizados. Total: {created + updated} templates.'
            ))
            self.stdout.write(f'KB.brand_visual_spec agora tem versao={spec_v2.get("versao")}')
