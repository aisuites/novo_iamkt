"""
Golden files dos arquetipos — a rede de seguranca do refactor artkit/engine-v3
(docs/arquitetura-pipeline-escalavel.md, Fase 1.0).

Renderiza TODOS os arquetipos das orgs de pipeline (todxs, vb-gastronomia,
samsung-healthcare) com conteudo de exemplo FIXO e deterministico (sem
Claude/Gemini; foto = placeholder) e compara pixel a pixel com a referencia.

  python manage.py golden_archetypes --record   # grava referencias + manifest
  python manage.py golden_archetypes --check    # re-renderiza e compara (CI do refactor)
  python manage.py golden_archetypes --check --only todxs

Arquivos:
  PNGs de referencia:  /app/golden/<slug>__<arch>__<fmt>.png   (gitignored)
  Manifest (sha256):   /app/apps/posts/golden_manifest.json    (COMMITADO)
  Em divergencia:      /app/golden/<caso>.actual.png + .diff.png p/ inspecao

Regra do refactor: QUALQUER passo do artkit so avanca com --check retornando
0 divergencias. Ajuste legitimo de arquetipo => re-rodar --record e commitar
o manifest junto da mudanca.
"""
import hashlib
import io
import json
import os

from django.core.management.base import BaseCommand

from apps.core.models import Organization

ORG_SLUGS = ['todxs', 'vb-gastronomia', 'samsung-healthcare']
GOLDEN_DIR = os.environ.get('GOLDEN_DIR', '/app/golden')
MANIFEST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'golden_manifest.json')


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Command(BaseCommand):
    help = 'Grava/verifica golden files dos arquetipos (rede de seguranca do refactor).'

    def add_arguments(self, parser):
        parser.add_argument('--record', action='store_true', help='grava referencias + manifest')
        parser.add_argument('--check', action='store_true', help='compara render atual vs manifest')
        parser.add_argument('--only', default=None, help='filtra por slug de org')
        parser.add_argument('--engine', default='legacy', choices=['legacy', 'v3'],
                            help="v3 = renderiza pelo ENGINE V3 e compara com o "
                                 "manifest LEGADO (prova de paridade pixel)")

    def handle(self, *args, **o):
        from apps.knowledge.models import KnowledgeBase
        from apps.posts.services.preview import render_preview, list_cases

        if not (o['record'] or o['check']):
            self.stderr.write(self.style.ERROR('use --record ou --check'))
            return
        if o['record'] and o['engine'] != 'legacy':
            self.stderr.write(self.style.ERROR(
                'goldens sao SEMPRE do render legado (referencia); '
                '--engine v3 so com --check'))
            return
        os.makedirs(GOLDEN_DIR, exist_ok=True)

        slugs = [s for s in ORG_SLUGS if not o['only'] or s == o['only']]
        manifest = {}
        if o['check']:
            try:
                with open(MANIFEST) as f:
                    manifest = json.load(f)
            except FileNotFoundError:
                self.stderr.write(self.style.ERROR(f'manifest ausente: {MANIFEST} — rode --record antes'))
                return

        new_manifest = dict(manifest)
        diffs, total = [], 0
        for slug in slugs:
            org = Organization.objects.get(slug=slug)
            kb = KnowledgeBase.objects.filter(organization=org).first()
            for arch, fmt in list_cases(org):
                case = f'{slug}__{arch}__{fmt}'
                total += 1
                try:
                    png = render_preview(org, kb, arch, fmt=fmt, engine=o['engine'])
                except Exception as e:
                    diffs.append((case, f'RENDER FALHOU: {e}'))
                    self.stdout.write(self.style.ERROR(f'  ✗ {case}: render falhou: {e}'))
                    continue
                digest = _sha(png)
                ref_path = os.path.join(GOLDEN_DIR, f'{case}.png')

                if o['record']:
                    with open(ref_path, 'wb') as f:
                        f.write(png)
                    new_manifest[case] = digest
                    self.stdout.write(f'  ✓ {case} ({len(png)//1024}KB)')
                    continue

                # --check
                expected = manifest.get(case)
                if expected is None:
                    diffs.append((case, 'CASO NOVO (sem referencia) — rode --record'))
                    self.stdout.write(self.style.WARNING(f'  ? {case}: sem referencia'))
                elif digest != expected:
                    diffs.append((case, 'PIXEL DIFF'))
                    with open(os.path.join(GOLDEN_DIR, f'{case}.actual.png'), 'wb') as f:
                        f.write(png)
                    self._write_diff(ref_path, png, case)
                    self.stdout.write(self.style.ERROR(f'  ✗ {case}: DIVERGIU (ver {case}.actual/.diff.png)'))
                else:
                    self.stdout.write(f'  = {case}')

        if o['record']:
            with open(MANIFEST, 'w') as f:
                json.dump(new_manifest, f, indent=1, sort_keys=True)
            self.stdout.write(self.style.SUCCESS(
                f'OK: {total} referencias gravadas; manifest: {MANIFEST}'))
            return

        if diffs:
            self.stdout.write(self.style.ERROR(
                f'FALHOU: {len(diffs)}/{total} casos divergentes.'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f'OK: {total}/{total} casos identicos ao golden.'))

    def _write_diff(self, ref_path, actual_png, case):
        """Imagem de diff (pixels divergentes em magenta) para inspecao rapida."""
        try:
            from PIL import Image, ImageChops
            ref = Image.open(ref_path).convert('RGB')
            act = Image.open(io.BytesIO(actual_png)).convert('RGB')
            if ref.size != act.size:
                return
            delta = ImageChops.difference(ref, act).convert('L').point(lambda p: 255 if p else 0)
            out = act.copy()
            out.paste((255, 0, 255), mask=delta)
            out.save(os.path.join(GOLDEN_DIR, f'{case}.diff.png'))
        except Exception:
            pass
