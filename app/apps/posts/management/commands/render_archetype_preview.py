"""
Preview DETERMINISTICO de um arquetipo a partir da spec do BANCO (PostArchetype),
com conteudo de exemplo — SEM brain (Claude) e SEM Gemini. Sustenta o loop de
refinamento de arquetipos (docs/arquitetura-pipeline-escalavel.md §2.1):
edita a spec (admin/shell) -> roda o preview -> valida o PNG -> repete.

  python manage.py render_archetype_preview --org todxs --archetype A
  python manage.py render_archetype_preview --org vb-gastronomia --archetype 01
  python manage.py render_archetype_preview --org samsung-healthcare --archetype B \
      --content '{"title": "Titulo custom"}' --out /tmp/preview.png

Onde ha foto no layout, usa um placeholder cinza (o objetivo e validar geometria/
tipografia, nao a imagem). --content (JSON) sobrepoe o conteudo de exemplo.
"""
import io
import json

from django.core.management.base import BaseCommand

from apps.core.models import Organization

# Texto de exemplo por chave de zona (fallback: "[<key> de exemplo]").
_SAMPLE_TEXT = {
    'kicker': 'Kicker de exemplo',
    'titulo': 'Título de exemplo do arquétipo',
    'title': 'Título de exemplo do arquétipo',
    'apoio': ('Texto de apoio de exemplo para validar espaçamentos, quebras de '
              'linha e a hierarquia tipográfica do arquétipo.'),
    'body': ('Texto de corpo de exemplo para validar espaçamentos, quebras de '
             'linha e a hierarquia tipográfica.'),
    'meta': 'meta · exemplo',
    'assinatura': 'Assinatura de exemplo',
    'signature_name': 'Nome de Exemplo',
    'cta': 'Saiba mais',
}


def _sample_content(keys):
    return {k: _SAMPLE_TEXT.get(k, f'[{k} de exemplo]') for k in keys}


def _placeholder_photo_png(w=1080, h=1350):
    """Foto neutra (cinza) para arquétipos com fundo/moldura de foto."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (128, 128, 128)).save(buf, 'PNG')
    return buf.getvalue()


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
        slug, arch = o['org'], o['archetype']
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'org slug={slug!r} nao encontrada'))
            return
        from apps.knowledge.models import KnowledgeBase
        kb = KnowledgeBase.objects.filter(organization=org).first()

        override = json.loads(o['content']) if o['content'] else {}
        out_path = o['out'] or f'/tmp/preview_{slug}_{arch}.png'

        if slug == 'vb-gastronomia':
            png = self._vb(org, kb, arch, o, override)
        elif slug == 'samsung-healthcare':
            png = self._samsung(org, kb, arch, o, override)
        else:
            png = self._todxs(org, kb, arch, o, override)
        if not png:
            return

        with open(out_path, 'wb') as f:
            f.write(png)
        self.stdout.write(self.style.SUCCESS(f'OK: {out_path}'))

    # ---- adaptadores por dialeto (unificam na spec v3 / Fase 2) -------------

    def _todxs(self, org, kb, arch, o, override):
        from apps.posts.services.todxs.catalog import apply_org_wireframes
        from apps.posts.services.todxs.wireframes import WF
        from apps.posts.services.todxs import pillow_render

        apply_org_wireframes(org)
        spec = WF().get(arch)
        if not spec:
            self.stderr.write(self.style.ERROR(
                f'arquetipo {arch!r} nao existe (disponiveis: {sorted(WF().keys())})'))
            return None
        fmt = o['format'] or (spec.get('formatos') or ['feed'])[0]
        zonas = (spec.get('zonas') or {}).get(fmt)
        if zonas is None:
            self.stderr.write(self.style.ERROR(
                f'arquetipo {arch!r} nao tem formato {fmt!r} (tem: {sorted((spec.get("zonas") or {}).keys())})'))
            return None
        formato_px = '1080x1920' if fmt == 'story' else '1080x1350'
        content = _sample_content([z['key'] for z in zonas])
        content.update(override)

        color_hex = o['color']
        if not color_hex:
            try:
                from apps.posts.tasks import _kb_colors
                cores = _kb_colors(org) or []
                color_hex = (cores[0].get('hex') if isinstance(cores[0], dict) else cores[0]) if cores else '#F4F1D9'
            except Exception:
                color_hex = '#F4F1D9'

        photo_png = None
        if spec.get('fundo') == 'photo':
            w, h = (1080, 1920) if fmt == 'story' else (1080, 1350)
            photo_png = _placeholder_photo_png(w, h)

        x_png, logo_url = None, None
        try:
            from apps.posts.services.todxs.assets import todxs_simbolo_url, todxs_wordmark_url
            logo_url = todxs_wordmark_url(kb) if kb else None
            simbolo_url = todxs_simbolo_url(kb) if kb else None
            if simbolo_url:
                import requests
                x_png = requests.get(simbolo_url, timeout=20).content
        except Exception:
            pass  # preview segue sem selo/wordmark

        pr = pillow_render.render_todxs(
            archetype=arch, content=content, color_hex=color_hex, fmt=fmt,
            formato_px=formato_px, kb=kb, photo_png=photo_png,
            x_png_bytes=x_png, logo_url=logo_url)
        return pr['final_png']

    def _vb(self, org, kb, arch, o, override):
        from apps.posts.services.vb.catalog import apply_org_specs
        from apps.posts.services.vb.specs import SP
        from apps.posts.services.vb.render import render_vb

        apply_org_specs(org)
        spec = SP().get(arch)
        if not spec:
            self.stderr.write(self.style.ERROR(
                f'arquetipo {arch!r} nao existe (disponiveis: {sorted(SP().keys())})'))
            return None
        fmt = spec.get('formato', 'feed')
        content = _sample_content([z['key'] for z in spec.get('zones', [])])
        content.update(override)

        photo_png = None
        if (spec.get('bg', {}).get('type') == 'photo') or spec.get('foto_frame'):
            w, h = spec.get('canvas', [1080, 1350])
            photo_png = _placeholder_photo_png(w, h)

        pr = render_vb(arch, content, color_hex=o['color'], fmt=fmt, kb=kb,
                       photo_png=photo_png)
        return pr['final_png']

    def _samsung(self, org, kb, arch, o, override):
        from apps.posts.services.samsung.catalog import apply_org_wireframes
        from apps.posts.services.samsung.wireframes import WF
        from apps.posts.services.samsung.render import render_samsung

        apply_org_wireframes(org)
        spec = WF().get(arch)
        if not spec:
            self.stderr.write(self.style.ERROR(
                f'arquetipo {arch!r} nao existe (disponiveis: {sorted(WF().keys())})'))
            return None
        keys = [z['key'] for z in spec.get('zones', [])
                if z.get('category') not in ('image', 'partner_logo')]
        content = _sample_content(keys)
        content.update(override)

        pr = render_samsung(archetype=arch, content=content, kb=kb, assets={})
        return pr['final_png']
