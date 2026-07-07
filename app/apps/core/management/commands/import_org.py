"""
Importa um bundle de organizacao gerado pelo `export_org` (migracao dev -> prod).

  python manage.py import_org --file /tmp/org-todxs.tar.gz --dry-run   # ensaio
  python manage.py import_org --file /tmp/org-todxs.tar.gz             # de verdade

Propriedades de seguranca:
  - IDEMPOTENTE: pode rodar N vezes; casa por natural key (slug da org, name/
    title/key dos filhos) e ATUALIZA em vez de duplicar.
  - --dry-run: executa TUDO dentro de uma transacao e faz rollback no final
    (nao toca S3). Mostra o plano real (criar/atualizar) sem efeito.
  - S3 re-key: as chaves `org-<id-antigo>/...` viram `org-<id-novo>/...`;
    upload so acontece se a chave nao existir no bucket (head_object).
  - NAO cria usuarios, NAO mexe em plano/billing/quotas, NAO dispara emails.
  - A flag archetype_selector_enabled NAO e ligada automaticamente (rollout
    por org e decisao manual no admin — disciplina de deploy).
"""
import json
import re
import tarfile

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Organization

IMPORT_ORDER = ['ColorPalette', 'CustomFont', 'Logo', 'ReferenceImage',
                'BrandgraficModule', 'Typography']

# Campos que o import NUNCA sobrescreve no destino
SKIP_ON_IMPORT = {'s3_key', 's3_url'}  # tratados pelo fluxo de arquivo


class DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = 'Importa bundle de org (par do export_org). Idempotente; use --dry-run primeiro.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='caminho do .tar.gz')
        parser.add_argument('--dry-run', action='store_true',
                            help='executa em transacao e faz rollback (nao toca S3)')
        parser.add_argument('--skip-s3', action='store_true',
                            help='nao envia arquivos ao S3 (so banco)')

    def handle(self, *args, **o):
        self.dry = o['dry_run']
        self.skip_s3 = o['skip_s3'] or self.dry
        self.tar = tarfile.open(o['file'], 'r:gz')
        self.manifest = json.load(self.tar.extractfile('manifest.json'))
        self.stats = {'created': 0, 'updated': 0, 'uploaded': 0, 's3_reused': 0}

        try:
            with transaction.atomic():
                self._run()
                if self.dry:
                    raise DryRunRollback()
        except DryRunRollback:
            self.stdout.write(self.style.WARNING(
                '[dry-run] rollback executado — NADA foi persistido.'))
        s = self.stats
        self.stdout.write(self.style.SUCCESS(
            f"OK: {s['created']} criados, {s['updated']} atualizados, "
            f"{s['uploaded']} arquivos enviados, {s['s3_reused']} ja no S3."))

    # ------------------------------------------------------------------ core
    def _run(self):
        from apps.knowledge import models as km
        from apps.knowledge.models import KnowledgeBase
        from apps.posts.models import PostArchetype

        m = self.manifest
        org, created = Organization.objects.get_or_create(
            slug=m['org']['slug'], defaults={'name': m['org']['name']})
        self._count(created)
        self.stdout.write(f"Organization {m['org']['slug']}: "
                          f"{'CRIADA' if created else 'existente'} (id={org.id})")
        self.org = org
        self.old_org_id = m.get('source_org_id')

        kb, created = KnowledgeBase.objects.get_or_create(organization=org)
        self._apply_fields(kb, m['kb'])
        kb.save()
        self._count(created)
        self.stdout.write(f'KnowledgeBase: {"CRIADA" if created else "atualizada"} (id={kb.id})')
        self.kb = kb

        self._registry = {}  # model_name -> {nk_tuple: obj}
        for model_name in IMPORT_ORDER:
            rows = m['children'].get(model_name) or []
            M = getattr(km, model_name)
            self._registry[model_name] = {}
            for row in rows:
                # defaults completos no INSERT (campos NOT NULL como file_size
                # e s3_key precisam entrar ja na criacao, nao num save() depois).
                defaults = self._field_defaults(M, row['fields'], exclude=set(row['nk']))
                obj, was_created = M.objects.get_or_create(
                    knowledge_base=kb, defaults=defaults, **row['nk'])
                if not was_created:
                    self._apply_fields(obj, row['fields'])
                self._apply_fks(obj, row.get('fk') or {})
                if row.get('s3_key'):
                    self._handle_file(obj, row)
                obj.save()
                self._count(was_created)
                self._registry[model_name][self._nk_key(row['nk'])] = obj
            self.stdout.write(f'  {model_name}: {len(rows)} processados')

        # Arquetipos (FK organization + thumbnail -> ReferenceImage por title)
        refs_by_title = {getattr(r, 'title', None): r
                         for r in self._registry.get('ReferenceImage', {}).values()}
        for a in m.get('archetypes') or []:
            obj, was_created = PostArchetype.objects.get_or_create(
                organization=org, key=a['key'],
                defaults={'name': a['name'], 'format': a['format'],
                          'spec': a['spec'], 'order': a['order'],
                          'is_active': a['is_active']})
            if not was_created:
                obj.name = obj.name or a['name']
                obj.format, obj.order, obj.is_active = a['format'], a['order'], a['is_active']
                obj.spec = a['spec']  # spec do bundle e a fonte de verdade validada
            obj.description = a.get('description') or obj.description
            if a.get('thumbnail_title') and refs_by_title.get(a['thumbnail_title']):
                obj.thumbnail = refs_by_title[a['thumbnail_title']]
            obj.save()
            self._count(was_created)
        self.stdout.write(f"  PostArchetype: {len(m.get('archetypes') or [])} processados")
        self.stdout.write(self.style.WARNING(
            'Lembrete: archetype_selector_enabled NAO foi ligado — ative no admin '
            'quando a org for entrar no rollout.'))

    # --------------------------------------------------------------- helpers
    def _count(self, created):
        self.stats['created' if created else 'updated'] += 1

    @staticmethod
    def _nk_key(nk: dict):
        return tuple(sorted(nk.items()))

    def _field_defaults(self, M, fields: dict, exclude=frozenset()):
        """Converte os campos do manifest em defaults prontos para o INSERT.
        Campos de arquivo entram como '' (o _handle_file re-chaveia depois)."""
        out = {}
        for f in M._meta.concrete_fields:
            if f.is_relation or f.name in exclude:
                continue
            if f.get_internal_type() in ('DateTimeField', 'DateField'):
                continue
            if f.name in SKIP_ON_IMPORT:
                out[f.name] = ''  # s3_key/s3_url: placeholder p/ NOT NULL
                continue
            if f.name in fields:
                try:
                    out[f.name] = f.to_python(fields[f.name])
                except Exception:
                    pass
        return out

    def _apply_fields(self, obj, fields: dict):
        for f in obj._meta.concrete_fields:
            if f.name not in fields or f.name in SKIP_ON_IMPORT or f.is_relation:
                continue
            if f.get_internal_type() in ('DateTimeField', 'DateField'):
                continue  # timestamps do ambiente de destino
            try:
                setattr(obj, f.name, f.to_python(fields[f.name]))
            except Exception:
                pass  # campo incompativel entre versoes: mantem o valor local

    def _apply_fks(self, obj, fk: dict):
        for field, ref in fk.items():
            if not ref:
                continue
            (nk_field, nk_value), = ref.items()
            target = self._registry.get('CustomFont', {}).get(
                self._nk_key({nk_field: nk_value}))
            if target is not None:
                setattr(obj, field, target)

    def _handle_file(self, obj, row):
        """Re-chaveia org-<old>/ -> org-<new>/ e sobe o arquivo se nao existir."""
        from django.conf import settings
        from apps.core.services.s3_service import S3Service

        old_key = row['s3_key']
        new_key = re.sub(r'^org-\d+/', f'org-{self.org.id}/', old_key)
        if new_key == old_key and self.old_org_id != self.org.id:
            new_key = f'org-{self.org.id}/{old_key}'

        obj.s3_key = new_key
        try:
            obj.s3_url = S3Service.get_public_url(new_key)
        except Exception:
            pass

        if self.skip_s3:
            return
        client = S3Service._get_s3_client()
        bucket = settings.AWS_BUCKET_NAME
        try:
            client.head_object(Bucket=bucket, Key=new_key)
            self.stats['s3_reused'] += 1
            return  # ja existe — idempotente
        except Exception:
            pass
        if not row.get('file'):
            self.stderr.write(self.style.WARNING(
                f'  ! sem bytes no bundle para {new_key} (exportado sem arquivo?)'))
            return
        data = self.tar.extractfile(row['file']).read()
        client.put_object(Bucket=bucket, Key=new_key, Body=data)
        self.stats['uploaded'] += 1
