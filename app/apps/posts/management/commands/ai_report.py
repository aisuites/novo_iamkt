"""
Relatorio GERAL de chamadas de IA (fonte: core.AIUsageEvent) para reconciliacao
com os paineis dos provedores (Google AI Studio Spend, Anthropic, OpenAI).

Por dia x modelo: chamadas, imagens faturaveis, tokens e custo logado; para os
modelos Gemini inclui o CUSTO ESPERADO pela tarifa oficial (ai.google.dev/pricing)
— e a divergencia. E a coluna para detectar cobranca "fantasma" no painel.

  python manage.py ai_report                         # ultimos 14 dias
  python manage.py ai_report --days 30
  python manage.py ai_report --start 2026-07-01 --end 2026-07-14
  python manage.py ai_report --model gemini          # filtra por substring
  python manage.py ai_report --csv
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

# Tarifa OFICIAL por modelo (USD). Imagem = preco flat da imagem FINAL
# (rascunho de thinking NAO e cobrado — confirmado com medicao real 15/07/2026).
# input_per_m = USD por 1M tokens de entrada.
TARIFA_OFICIAL = {
    'gemini-3-pro-image-preview': {'img': Decimal('0.134'), 'input_per_m': Decimal('2.00')},
    'gemini-3.1-flash-image':     {'img': Decimal('0.067'), 'input_per_m': Decimal('0.50')},
    'gemini-2.5-flash-image':     {'img': Decimal('0.039'), 'input_per_m': Decimal('0.30')},
}

USD_BRL = Decimal('5.8')  # mesma taxa usada no logging interno


class Command(BaseCommand):
    help = 'Relatorio geral de chamadas IA por dia x modelo, com custo esperado oficial (Gemini).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14)
        parser.add_argument('--start', type=str, default=None, help='YYYY-MM-DD')
        parser.add_argument('--end', type=str, default=None, help='YYYY-MM-DD')
        parser.add_argument('--model', type=str, default=None, help='substring do modelo')
        parser.add_argument('--csv', action='store_true')

    def handle(self, *args, **opts):
        from apps.core.models import AIUsageEvent

        qs = AIUsageEvent.objects.all()
        if opts['start']:
            qs = qs.filter(created_at__date__gte=opts['start'])
        else:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=opts['days']))
        if opts['end']:
            qs = qs.filter(created_at__date__lte=opts['end'])
        if opts['model']:
            qs = qs.filter(model__icontains=opts['model'])

        rows = (qs.annotate(d=TruncDate('created_at'))
                  .values('d', 'model')
                  .annotate(n=Count('id'),
                            imgs=Sum('images_generated'),
                            tin=Sum('input_tokens'),
                            tout=Sum('output_tokens'),
                            usd=Sum('cost_usd'),
                            brl=Sum('cost_brl'))
                  .order_by('d', 'model'))

        if opts['csv']:
            self.stdout.write('dia,modelo,chamadas,imgs_logadas,imgs_faturaveis,'
                              'tokens_in,tokens_out,usd_logado,brl_logado,'
                              'usd_esperado_oficial,divergencia_usd')
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"{'dia':<11}{'modelo':<30}{'cham':>5}{'imgs':>5}{'fat':>4}"
                f"{'tok_in':>9}{'tok_out':>9}{'USD log':>9}{'USD ofic':>9}{'diff':>8}"))

        tot = {'n': 0, 'usd': Decimal('0'), 'esp': Decimal('0')}
        tot_gemini = {'n': 0, 'fat': 0, 'usd': Decimal('0'), 'esp': Decimal('0')}

        for r in rows:
            model = r['model'] or '?'
            usd = r['usd'] or Decimal('0')
            tarifa = TARIFA_OFICIAL.get(model)
            if tarifa:
                # faturavel = 1 imagem final por chamada (rascunho nao e cobrado)
                faturaveis = r['n']
                esperado = (faturaveis * tarifa['img']
                            + Decimal(r['tin'] or 0) * tarifa['input_per_m'] / Decimal(1_000_000))
                tot_gemini['n'] += r['n']
                tot_gemini['fat'] += faturaveis
                tot_gemini['usd'] += usd
                tot_gemini['esp'] += esperado
            else:
                faturaveis = ''
                esperado = None

            tot['n'] += r['n']
            tot['usd'] += usd
            if esperado is not None:
                tot['esp'] += esperado

            diff = (usd - esperado) if esperado is not None else None
            if opts['csv']:
                self.stdout.write(
                    f"{r['d']},{model},{r['n']},{r['imgs'] or 0},{faturaveis},"
                    f"{r['tin'] or 0},{r['tout'] or 0},{usd:.4f},{r['brl'] or 0:.2f},"
                    f"{esperado:.4f}" if esperado is not None else
                    f"{r['d']},{model},{r['n']},{r['imgs'] or 0},,"
                    f"{r['tin'] or 0},{r['tout'] or 0},{usd:.4f},{r['brl'] or 0:.2f},,")
            else:
                self.stdout.write(
                    f"{str(r['d']):<11}{model[:29]:<30}{r['n']:>5}{r['imgs'] or 0:>5}"
                    f"{str(faturaveis):>4}{r['tin'] or 0:>9}{r['tout'] or 0:>9}"
                    f"{usd:>9.4f}"
                    + (f"{esperado:>9.4f}{diff:>+8.4f}" if esperado is not None else f"{'—':>9}{'—':>8}"))

        if not opts['csv']:
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING('== RESUMO =='))
            self.stdout.write(
                f"Total geral: {tot['n']} chamadas | USD logado {tot['usd']:.2f} "
                f"(~R$ {tot['usd'] * USD_BRL:.2f})")
            if tot_gemini['n']:
                brl_esp = tot_gemini['esp'] * USD_BRL
                self.stdout.write(
                    f"GEMINI (credito): {tot_gemini['n']} chamadas | "
                    f"{tot_gemini['fat']} imagens faturaveis | "
                    f"esperado oficial US$ {tot_gemini['esp']:.2f} (~R$ {brl_esp:.2f}) | "
                    f"logado US$ {tot_gemini['usd']:.2f}")
                self.stdout.write(self.style.WARNING(
                    'Compare "esperado oficial" com o Spend do projeto no AI Studio. '
                    'Painel > esperado = cobranca indevida; log > esperado = nosso log '
                    'superconta (rascunho/tarifa antiga).'))
