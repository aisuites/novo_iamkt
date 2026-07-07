"""
Exporta uma organizacao completa (KB + assets + arquetipos) para um bundle
.tar.gz portavel — o par do `import_org` (migracao dev -> prod).

  python manage.py export_org --org todxs --out /tmp/org-todxs.tar.gz

O bundle contem:
  manifest.json  — Organization (campos de negocio), KnowledgeBase (todos os
                   campos de conteudo), filhos (ColorPalette, CustomFont,
                   Typography, Logo, ReferenceImage c/ dossie visual,
                   BrandgraficModule) e PostArchetype (specs).
  files/         — os BYTES de cada asset S3 (logos, fontes, referencias,
                   grafismos), baixados via presigned URL.

NAO exporta: usuarios, posts, billing/planos/quotas (prod gerencia).
"""
import io
import json
import os
import tarfile
from datetime import datetime, date
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand

from apps.core.models import Organization

# (Model, filtro, natural_key, tem_arquivo_s3, fks_especiais)
CHILDREN = [
    ('ColorPalette', ('name', 'hex_code'), False, {}),
    ('CustomFont', ('name',), True, {}),
    ('Logo', ('name',), True, {}),
    ('ReferenceImage', ('title',), True, {}),
    ('BrandgraficModule', ('name',), True, {}),
    ('Typography', ('usage', 'order'), False, {'custom_font': ('CustomFont', 'name')}),
]

# Campos NUNCA exportados (gerenciados pelo ambiente de destino)
SKIP_FIELDS = {
    'id', 'knowledge_base', 'organization', 'uploaded_by', 'created_at',
    'updated_at', 'last_updated_by', 'onboarding_completed_by',
    'suggestions_reviewed_by', 'created_from_brandguide', 'brandguide',
    'updated_by', 'thumbnail', 'custom_font',
}


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def _row_fields(obj):
    out = {}
    for f in obj._meta.concrete_fields:
        if f.name in SKIP_FIELDS or f.is_relation:
            continue
        out[f.name] = _jsonable(getattr(obj, f.name))
    return out


class Command(BaseCommand):
    help = 'Exporta org (KB + assets + arquetipos) para bundle .tar.gz portavel.'

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help='slug da organizacao')
        parser.add_argument('--out', default=None, help='caminho do .tar.gz de saida')

    def handle(self, *args, **o):
        from apps.knowledge import models as km
        from apps.knowledge.models import KnowledgeBase
        from apps.posts.models import PostArchetype
        from apps.core.services.s3_service import S3Service

        slug = o['org']
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'org slug={slug!r} nao encontrada'))
            return
        kb = KnowledgeBase.objects.filter(organization=org).first()
        if not kb:
            self.stderr.write(self.style.ERROR(f'org {slug} nao tem KnowledgeBase'))
            return

        out_path = o['out'] or f'/tmp/org-{slug}.tar.gz'
        manifest = {
            'version': 1,
            'exported_at': datetime.now().isoformat(),
            'source_org_id': org.id,
            'org': {
                'slug': org.slug,
                'name': org.name,
                'archetype_selector_enabled': bool(
                    getattr(org, 'archetype_selector_enabled', False)),
            },
            'kb': _row_fields(kb),
            'children': {},
            'archetypes': [],
        }

        files = []  # (arcname, bytes)

        def _grab_file(obj, model_name):
            """Baixa o asset S3 do objeto -> retorna arcname (ou None)."""
            key = getattr(obj, 's3_key', '') or ''
            if not key:
                return None
            try:
                url = S3Service.generate_presigned_download_url(key, expires_in=600)
                data = requests.get(url, timeout=60).content
            except Exception:
                self.stderr.write(self.style.WARNING(
                    f'  ! download falhou: {model_name} id={obj.id} key={key} (segue sem o arquivo)'))
                return None
            arc = f'files/{model_name}/{obj.id}__{os.path.basename(key)}'
            files.append((arc, data))
            return arc

        for model_name, nk, has_file, fk_map in CHILDREN:
            M = getattr(km, model_name)
            rows = []
            for obj in M.objects.filter(knowledge_base=kb):
                row = {
                    'nk': {k: _jsonable(getattr(obj, k)) for k in nk},
                    'fields': _row_fields(obj),
                    's3_key': getattr(obj, 's3_key', '') or None,
                    'file': _grab_file(obj, model_name) if has_file else None,
                    'fk': {},
                }
                for fk_field, (fk_model, fk_nk) in fk_map.items():
                    ref = getattr(obj, fk_field, None)
                    row['fk'][fk_field] = (
                        {fk_nk: getattr(ref, fk_nk)} if ref else None)
                rows.append(row)
            manifest['children'][model_name] = rows
            self.stdout.write(f'  {model_name}: {len(rows)}')

        for a in PostArchetype.objects.filter(organization=org):
            manifest['archetypes'].append({
                'key': a.key, 'name': a.name, 'description': a.description,
                'format': a.format, 'spec': a.spec, 'order': a.order,
                'is_active': a.is_active,
                'thumbnail_title': a.thumbnail.title if a.thumbnail else None,
            })
        self.stdout.write(f'  PostArchetype: {len(manifest["archetypes"])}')

        with tarfile.open(out_path, 'w:gz') as tar:
            mdata = json.dumps(manifest, ensure_ascii=False, indent=1).encode()
            info = tarfile.TarInfo('manifest.json')
            info.size = len(mdata)
            tar.addfile(info, io.BytesIO(mdata))
            for arc, data in files:
                info = tarfile.TarInfo(arc)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

        size_mb = os.path.getsize(out_path) / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f'OK: {out_path} ({size_mb:.1f} MB, {len(files)} arquivos)'))
