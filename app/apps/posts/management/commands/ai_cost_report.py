"""
Relatorio agregado de custos de IA — baseline do redesenho dos fluxos
(docs/redesenho-fluxos-geracao.md, Fase C0.5).

Agrega Post.total_cost_usd por organizacao x pipeline_used x mes: total, n de
posts, custo MEDIO por post (USD e BRL via USD_TO_BRL_RATE). E a metrica que
compara as familias (simple vs arquetipos) e justifica desligar a familia 3.

  python manage.py ai_cost_report                 # ultimos 3 meses
  python manage.py ai_cost_report --months 12
  python manage.py ai_cost_report --org todxs
  python manage.py ai_cost_report --csv           # saida CSV (p/ planilha)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Custo de IA agregado: org x pipeline x mes (media por post, USD/BRL).'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=3,
                            help='janela em meses (default 3)')
        parser.add_argument('--org', default=None, help='filtra por slug de org')
        parser.add_argument('--csv', action='store_true', help='saida CSV')

    def handle(self, *args, **o):
        from datetime import timedelta

        from django.conf import settings
        from django.db.models import Avg, Count, Sum
        from django.db.models.functions import TruncMonth
        from django.utils import timezone

        from apps.posts.models import Post

        rate = float(getattr(settings, 'USD_TO_BRL_RATE', 5.80))
        since = timezone.now() - timedelta(days=30 * o['months'])

        qs = Post.objects.filter(created_at__gte=since)
        if o['org']:
            qs = qs.filter(organization__slug=o['org'])

        rows = (
            qs.annotate(mes=TruncMonth('created_at'))
            .values('mes', 'organization__slug', 'pipeline_used')
            .annotate(
                posts=Count('id'),
                total_usd=Sum('total_cost_usd'),
                medio_usd=Avg('total_cost_usd'),
                texto_usd=Sum('total_text_cost_usd'),
                imagem_usd=Sum('total_image_cost_usd'),
            )
            .order_by('mes', 'organization__slug', 'pipeline_used')
        )

        if o['csv']:
            self.stdout.write('mes,org,pipeline,posts,total_usd,medio_usd,'
                              'medio_brl,texto_usd,imagem_usd')
            for r in rows:
                medio = float(r['medio_usd'] or 0)
                self.stdout.write(
                    f"{r['mes']:%Y-%m},{r['organization__slug']},"
                    f"{r['pipeline_used'] or '-'},{r['posts']},"
                    f"{float(r['total_usd'] or 0):.4f},{medio:.4f},"
                    f"{medio * rate:.4f},{float(r['texto_usd'] or 0):.4f},"
                    f"{float(r['imagem_usd'] or 0):.4f}")
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Custo de IA por org x pipeline x mes — ultimos {o['months']} "
            f"meses (USD->BRL {rate})"))
        header = (f"{'mes':<8} {'org':<22} {'pipeline':<10} {'posts':>5} "
                  f"{'total US$':>10} {'medio US$':>10} {'medio R$':>9} "
                  f"{'texto US$':>10} {'imagem US$':>10}")
        self.stdout.write(header)
        self.stdout.write('-' * len(header))
        for r in rows:
            medio = float(r['medio_usd'] or 0)
            self.stdout.write(
                f"{r['mes']:%Y-%m}   {(r['organization__slug'] or '?'):<22} "
                f"{(r['pipeline_used'] or '-'):<10} {r['posts']:>5} "
                f"{float(r['total_usd'] or 0):>10.4f} {medio:>10.4f} "
                f"{medio * rate:>9.4f} {float(r['texto_usd'] or 0):>10.4f} "
                f"{float(r['imagem_usd'] or 0):>10.4f}")
        if not rows:
            self.stdout.write('(sem posts na janela)')
