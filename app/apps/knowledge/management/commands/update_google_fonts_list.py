"""
Atualiza app/apps/knowledge/data/google_fonts.json buscando
https://fonts.google.com/metadata/fonts (endpoint publico, sem API key).

Uso:
    python manage.py update_google_fonts_list
    python manage.py update_google_fonts_list --dry-run

A lista e versionada no git. Rodar manualmente ou via cron quando quiser
atualizar (tipicamente algumas vezes por ano).
"""

import datetime as dt
import json
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge import google_fonts as gf

METADATA_URL = 'https://fonts.google.com/metadata/fonts'
DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / 'data'
    / 'google_fonts.json'
)


class Command(BaseCommand):
    help = 'Atualiza a lista de Google Fonts em google_fonts.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que mudaria sem gravar',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        self.stdout.write(f'Buscando {METADATA_URL} ...')

        try:
            r = requests.get(METADATA_URL, timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f'Falha ao buscar metadata: {exc}')

        data = r.json()
        raw_families = data.get('familyMetadataList') or []
        families = sorted(
            f['family'] for f in raw_families if f.get('family')
        )
        if not families:
            raise CommandError('Resposta nao continha familyMetadataList util')

        # Comparacao com a lista atual
        try:
            with open(DATA_PATH, encoding='utf-8') as f:
                current = json.load(f).get('families') or []
        except (FileNotFoundError, json.JSONDecodeError):
            current = []

        added = sorted(set(families) - set(current))
        removed = sorted(set(current) - set(families))

        self.stdout.write(f'  Lista atual: {len(current)} familias')
        self.stdout.write(f'  Nova lista:  {len(families)} familias')
        if added:
            self.stdout.write(self.style.SUCCESS(f'  + {len(added)} novas'))
            for name in added[:10]:
                self.stdout.write(f'      + {name}')
            if len(added) > 10:
                self.stdout.write(f'      ... e mais {len(added) - 10}')
        if removed:
            self.stdout.write(self.style.WARNING(f'  - {len(removed)} removidas'))
            for name in removed[:10]:
                self.stdout.write(f'      - {name}')

        if dry_run:
            self.stdout.write('Dry-run: nada gravado.')
            return

        out = {
            'updated_at': dt.date.today().isoformat(),
            'source': METADATA_URL,
            'count': len(families),
            'families': families,
        }
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        gf.reload_cache()
        self.stdout.write(
            self.style.SUCCESS(f'Lista atualizada: {len(families)} familias gravadas em {DATA_PATH}')
        )
