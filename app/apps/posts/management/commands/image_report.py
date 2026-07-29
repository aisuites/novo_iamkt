"""
Relatorio de geracao de IMAGENS (fonte: core.AIUsageEvent, step=image_generation).

Responde: quantas imagens foram geradas/cobradas, quantas vieram do pedido
original vs alteracoes do usuario, quais modelos e o valor por modelo/org.

  python manage.py image_report                          # ultimos 30 dias
  python manage.py image_report --days 7
  python manage.py image_report --start 2026-07-10 --end 2026-07-10
  python manage.py image_report --org konimagem
  python manage.py image_report --csv
"""
from django.core.management.base import BaseCommand

# Classificacao dos purposes granulares (C0.2) em categorias de negocio.
CATEGORIA_POR_PURPOSE = {
    # pedido original — etapas que produzem o post pedido
    'gemini_main': 'original',
    'gemini_background': 'original',
    'gemini_bg_cleanup': 'original',
    'gemini_text_apply': 'original',
    'bg_text_guard': 'original',
    'samsung_background': 'original',
    'vb_photo': 'original',
    'todxs_background': 'original',
    # alteracoes — pedidos de mudanca do usuario sobre um post pronto
    'gemini_regenerate_background': 'alteracao',
    'regen_bg_edit_prompt': 'alteracao',
    'image_edit_prompt': 'alteracao',
    'gemini_edit_image': 'alteracao',
    'gemini_edit_raw_sync': 'alteracao',
}


class Command(BaseCommand):
    help = ('Relatorio de imagens: original x alteracoes, por modelo, '
            'por etapa e por org (USD/BRL).')

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='janela em dias (default 30; ignorado com --start)')
        parser.add_argument('--start', default=None, help='data inicial YYYY-MM-DD')
        parser.add_argument('--end', default=None,
                            help='data final YYYY-MM-DD (inclusiva; default = start ou hoje)')
        parser.add_argument('--org', default=None, help='filtra por slug de org')
        parser.add_argument('--csv', action='store_true', help='saida CSV')

    def handle(self, *args, **o):
        import datetime
        from datetime import timedelta

        from django.db.models import Count, Sum
        from django.utils import timezone

        from apps.core.models import AIUsageEvent

        tz = timezone.get_current_timezone()
        if o['start']:
            start = datetime.datetime.strptime(o['start'], '%Y-%m-%d').replace(tzinfo=tz)
            end_date = o['end'] or o['start']
            end = (datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=tz)
                   + timedelta(days=1))
        else:
            end = timezone.now()
            start = end - timedelta(days=o['days'])

        qs = AIUsageEvent.objects.filter(
            step='image_generation', created_at__gte=start, created_at__lt=end)
        if o['org']:
            qs = qs.filter(organization__slug=o['org'])

        agg = ['n', 'imgs', 'usd', 'brl']

        def _annot(values_qs):
            return values_qs.annotate(
                n=Count('id'), imgs=Sum('images_generated'),
                usd=Sum('cost_usd'), brl=Sum('cost_brl'))

        por_purpose = list(_annot(qs.values('purpose', 'model')).order_by('-usd'))
        por_modelo = list(_annot(qs.values('model')).order_by('-usd'))
        por_org = list(_annot(qs.values('organization__slug', 'organization__name'))
                       .order_by('-usd'))

        # categorias (original x alteracao x outros) somadas em python — a
        # classificacao e um mapa de negocio, nao um campo do banco
        cats = {}
        for r in por_purpose:
            cat = CATEGORIA_POR_PURPOSE.get(r['purpose'] or '', 'outros')
            c = cats.setdefault(cat, {k: 0 for k in agg})
            for k in agg:
                c[k] += r[k] or 0

        total = {k: sum((c[k] or 0) for c in cats.values()) for k in agg}
        periodo = f"{start:%d/%m/%Y} a {(end - timedelta(days=1)):%d/%m/%Y}"

        if o['csv']:
            w = self.stdout.write
            w(f'# periodo,{periodo}' + (f",org,{o['org']}" if o['org'] else ''))
            w('secao,chave,modelo,chamadas,imagens_cobradas,usd,brl')
            for cat, c in sorted(cats.items()):
                w(f"categoria,{cat},,{c['n']},{c['imgs']},{c['usd']:.4f},{c['brl']:.4f}")
            for r in por_modelo:
                w(f"modelo,{r['model'] or '?'},,{r['n']},{r['imgs'] or 0},"
                  f"{r['usd'] or 0:.4f},{r['brl'] or 0:.4f}")
            for r in por_purpose:
                cat = CATEGORIA_POR_PURPOSE.get(r['purpose'] or '', 'outros')
                w(f"etapa,{r['purpose'] or '?'} ({cat}),{r['model'] or '?'},"
                  f"{r['n']},{r['imgs'] or 0},{r['usd'] or 0:.4f},{r['brl'] or 0:.4f}")
            for r in por_org:
                w(f"org,{r['organization__slug'] or '?'},,{r['n']},{r['imgs'] or 0},"
                  f"{r['usd'] or 0:.4f},{r['brl'] or 0:.4f}")
            w(f"total,,,{total['n']},{total['imgs']},{total['usd']:.4f},{total['brl']:.4f}")
            return

        w = self.stdout.write
        head = self.style.MIGRATE_HEADING
        w(head(f"Relatorio de imagens — {periodo}"
               + (f" — org: {o['org']}" if o['org'] else '')))
        if not por_purpose:
            w('(sem eventos de imagem no periodo — fonte comeca em 2026-07-08)')
            return

        w('')
        w(head('Por categoria (pedido original x alteracoes do usuario)'))
        fmt = '{:<12} {:>8} {:>10} {:>11} {:>11}'
        w(fmt.format('categoria', 'chamadas', 'imagens', 'US$', 'R$'))
        for cat in ('original', 'alteracao', 'outros'):
            c = cats.get(cat)
            if c:
                w(fmt.format(cat, c['n'], c['imgs'], f"{c['usd']:.4f}", f"{c['brl']:.4f}"))
        w(fmt.format('TOTAL', total['n'], total['imgs'],
                     f"{total['usd']:.4f}", f"{total['brl']:.4f}"))

        w('')
        w(head('Por modelo'))
        fmt = '{:<34} {:>8} {:>10} {:>11} {:>11} {:>12}'
        w(fmt.format('modelo', 'chamadas', 'imagens', 'US$', 'R$', 'US$/chamada'))
        for r in por_modelo:
            n = r['n'] or 0
            w(fmt.format((r['model'] or '?')[:34], n, r['imgs'] or 0,
                         f"{r['usd'] or 0:.4f}", f"{r['brl'] or 0:.4f}",
                         f"{(r['usd'] or 0) / n:.4f}" if n else '-'))

        w('')
        w(head('Por etapa (purpose)'))
        fmt = '{:<30} {:<10} {:<28} {:>8} {:>9} {:>11}'
        w(fmt.format('etapa', 'categoria', 'modelo', 'chamadas', 'imagens', 'US$'))
        for r in por_purpose:
            cat = CATEGORIA_POR_PURPOSE.get(r['purpose'] or '', 'outros')
            w(fmt.format((r['purpose'] or '?')[:30], cat, (r['model'] or '?')[:28],
                         r['n'], r['imgs'] or 0, f"{r['usd'] or 0:.4f}"))

        w('')
        w(head('Por organizacao'))
        fmt = '{:<28} {:>8} {:>10} {:>11} {:>11}'
        w(fmt.format('org', 'chamadas', 'imagens', 'US$', 'R$'))
        for r in por_org:
            w(fmt.format((r['organization__name'] or r['organization__slug'] or '?')[:28],
                         r['n'], r['imgs'] or 0,
                         f"{r['usd'] or 0:.4f}", f"{r['brl'] or 0:.4f}"))
