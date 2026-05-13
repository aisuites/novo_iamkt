"""
Re-analisa VisualTemplates com Claude Sonnet 4.5 passando JUNTO:
- PNG do template original (s3_url)
- PNG do logo da KB
- PNG de cada BrandgraficModule
- brand_visual_spec (cores/tipografia)

Resultado: template_spec_v3 com regions calibradas com bboxes/placements
corretos e identificacao precisa do que e color block vs grafismo PNG vs
logo vs texto.

Uso:
    # Dry-run (so imprime, nao salva)
    python manage.py reanalyze_template_v3 --ids 28,30,32

    # Salva no template (faz backup do v2 atual em template_spec_v2_backup)
    python manage.py reanalyze_template_v3 --ids 28,30,32 --save

    # Re-analisa os primeiros N templates da Colletivo
    python manage.py reanalyze_template_v3 --org-slug colletivo --first 3
"""

import base64
import json
import os
import re
import urllib.request
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Organization
from apps.core.services.s3_service import S3Service
from apps.knowledge.models import (
    BrandgraficModule,
    KnowledgeBase,
    Logo,
    VisualTemplate,
)

MODEL = 'claude-sonnet-4-5'
MAX_TOKENS = 8000

# Pricing Sonnet 4.5 (USD per 1M tokens) — para AIUsageLog
COST_INPUT_PER_M = Decimal('3.0')
COST_OUTPUT_PER_M = Decimal('15.0')


SYSTEM_PROMPT = """Voce e um designer especialista em sistemas de design.
Sua tarefa: analisar um template visual existente + os assets reais da marca
(logo, grafismos PNG, cores, tipografia) e produzir um spec JSON estruturado
que descreva cada region/elemento do template com PRECISAO.

PRINCIPIOS:
1. Mapeie cada elemento visual visivel no template para uma region
2. Distinga rigorosamente os tipos:
   - 'title' / 'subtitle' / 'body_text' / 'secondary_text' / 'tag' — texto
   - 'image' — placeholder para foto/imagem (sera preenchida via IA)
   - 'logo' — logotipo da marca
   - 'graphic' — pode ser:
     a) grafismo PNG real (letterform, modulo decorativo) -> use graphic_module_number
     b) bloco de cor solida atras de texto (highlight bar) -> deixe
        graphic_module_number como "nao_aplicavel" e defina color_token
3. Para LOGO e GRAPHIC PNG (nao color-block), USE PLACEMENT EM VEZ DE BBOX:
   - placement = {anchor, scale_pct, scale_dim, offset_pct}
   - anchor: top-left | top-center | top-right | center-left | center |
     center-right | bottom-left | bottom-center | bottom-right
   - scale_pct: tamanho relativo ao canvas (0-100)
   - scale_dim: 'width' (default) ou 'height'
   - offset_pct: {x, y} afastamento da borda (default 0)
   - Isso preserva o aspect ratio nativo do asset
4. Para TEXTOS e COLOR-BLOCKS, use bbox_pct = {x, y, w, h} em percentual
5. Tokens de cor: use 'institucional.preto', 'iniciativas.azul' etc.
   conforme brand_visual_spec.cores fornecido. Nunca invente token.
6. NUNCA crie regions com bbox sobreposto a outras a menos que seja
   intencional (ex: texto sobre fundo de cor).

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "regions": [
    {
      "id": "title_main",
      "tipo": "title",
      "bbox_pct": {"x": 5, "y": 20, "w": 50, "h": 25},
      "color_token": "institucional.preto",
      "font_token": "primaria.regular",
      "font_weight": "bold",
      "alignment": "left",
      "exemplo_conteudo": "SXSW 2026"
    },
    {
      "id": "logo_brand",
      "tipo": "logo",
      "logo_variant": "preferencial",
      "placement": {
        "anchor": "bottom-left",
        "scale_pct": 18,
        "scale_dim": "width",
        "offset_pct": {"x": 5, "y": 5}
      }
    },
    {
      "id": "highlight_bar",
      "tipo": "graphic",
      "graphic_module_number": "nao_aplicavel",
      "color_token": "iniciativas.rosa_claro",
      "bbox_pct": {"x": 0, "y": 18, "w": 60, "h": 22}
    }
  ]
}

Retorne APENAS o JSON, sem nenhum texto antes ou depois, sem markdown."""


class Command(BaseCommand):
    help = 'Re-analisa templates com Claude Sonnet 4.5 + assets reais'

    def add_arguments(self, parser):
        parser.add_argument('--ids', help='IDs separados por virgula (ex: 28,30,32)')
        parser.add_argument('--org-slug', default='colletivo')
        parser.add_argument('--first', type=int, default=0,
                            help='Primeiros N templates da KB (alternativo a --ids)')
        parser.add_argument('--save', action='store_true',
                            help='Salva no template (default: dry-run)')
        parser.add_argument('--dump-prompt', action='store_true',
                            help='Mostra o prompt completo enviado a Claude (debug)')

    # ---- Entry --------------------------------------------------------

    def handle(self, *args, **opts):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise CommandError('ANTHROPIC_API_KEY ausente no ambiente')

        try:
            import anthropic
        except ImportError:
            raise CommandError('Pacote anthropic nao instalado')

        self.client = anthropic.Anthropic(api_key=api_key)

        templates = self._select_templates(opts)
        if not templates:
            raise CommandError('Nenhum template selecionado')

        kb = templates[0].knowledge_base
        brand_spec = kb.brand_visual_spec or {}
        assets = self._collect_assets(kb)

        self.stdout.write(self.style.SUCCESS(
            f'KB: {kb} | Logos: {len(assets["logos"])} | '
            f'Grafismos: {len(assets["grafismos"])}'
        ))

        for t in templates:
            self.stdout.write(self.style.HTTP_INFO(
                f'\n=== Template {t.id}: {t.name} [{t.aspect_ratio}] ==='
            ))
            self._reanalyze_one(t, brand_spec, assets, opts)

    # ---- Selection ----------------------------------------------------

    def _select_templates(self, opts):
        if opts.get('ids'):
            ids = [int(x.strip()) for x in opts['ids'].split(',') if x.strip()]
            return list(VisualTemplate.objects.filter(id__in=ids).order_by('id'))

        try:
            org = Organization.objects.get(slug=opts['org_slug'])
        except Organization.DoesNotExist:
            raise CommandError(f'Org {opts["org_slug"]!r} nao encontrada')
        kb = KnowledgeBase.objects.filter(organization=org).first()
        if not kb:
            raise CommandError(f'KB nao encontrada para {org}')

        qs = VisualTemplate.objects.filter(knowledge_base=kb).order_by('id')
        n = opts.get('first') or 3
        return list(qs[:n])

    # ---- Asset collection --------------------------------------------

    def _collect_assets(self, kb):
        logos = list(Logo.objects.filter(knowledge_base=kb))
        grafismos = list(
            BrandgraficModule.objects.filter(
                knowledge_base=kb, is_active=True
            ).order_by('name')
        )
        return {'logos': logos, 'grafismos': grafismos}

    # ---- Image download + base64 --------------------------------------

    def _download_b64(self, s3_key: str, fallback_url: str) -> tuple:
        """Retorna (base64_str, media_type) ou (None, None) se falhar."""
        try:
            url = S3Service.generate_presigned_download_url(s3_key)
        except Exception:
            url = fallback_url
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                content_type = resp.headers.get('Content-Type', 'image/png')
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f'  [WARN] falha ao baixar {s3_key}: {exc}'
            ))
            return None, None
        media_type = content_type.split(';')[0].strip()
        if media_type not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
            media_type = 'image/png'
        return base64.b64encode(data).decode('ascii'), media_type

    # ---- Per-template analysis ---------------------------------------

    def _reanalyze_one(self, template, brand_spec, assets, opts):
        # 1. Baixa todas as imagens necessarias
        tpl_b64, tpl_type = self._download_b64(template.s3_key, template.s3_url)
        if not tpl_b64:
            self.stdout.write(self.style.ERROR('  Falha baixando PNG do template'))
            return

        logo_imgs = []
        for lg in assets['logos']:
            b64, mt = self._download_b64(lg.s3_key, lg.s3_url)
            if b64:
                logo_imgs.append({
                    'name': lg.name, 'type': lg.logo_type, 'b64': b64, 'mt': mt
                })

        graf_imgs = []
        for gr in assets['grafismos']:
            b64, mt = self._download_b64(gr.s3_key, gr.s3_url)
            if b64:
                graf_imgs.append({
                    'name': gr.name, 'b64': b64, 'mt': mt
                })

        # 2. Monta mensagem multimodal
        content = self._build_user_content(
            template, brand_spec, tpl_b64, tpl_type, logo_imgs, graf_imgs
        )

        if opts.get('dump_prompt'):
            preview = [
                c if c.get('type') == 'text' else {'type': 'image', '...': '...'}
                for c in content
            ]
            self.stdout.write(json.dumps(preview, indent=2, ensure_ascii=False)[:3000])

        # 3. Chama Claude
        self.stdout.write('  Chamando Claude Sonnet 4.5...')
        try:
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': content}],
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Erro Claude: {exc}'))
            return

        # 4. Loga custo
        self._log_cost(template, resp)

        # 5. Parse JSON
        text = ''.join(
            blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
        )
        spec_new = self._parse_json(text)
        if not spec_new:
            self.stdout.write(self.style.ERROR(
                f'  Falha parsing JSON. Raw: {text[:500]}...'
            ))
            return

        regions = spec_new.get('regions') or []
        self.stdout.write(self.style.SUCCESS(
            f'  Spec v3 gerado: {len(regions)} regions'
        ))
        for r in regions:
            tipo = r.get('tipo')
            placement = r.get('placement')
            bbox = r.get('bbox_pct')
            pos = (
                f'placement={placement}' if placement else f'bbox={bbox}'
            )
            self.stdout.write(f'    - {r.get("id")} [{tipo}] {pos}')

        if opts.get('save'):
            self._save_spec(template, spec_new)
            self.stdout.write(self.style.SUCCESS('  SALVO em template_spec'))
        else:
            self.stdout.write(self.style.WARNING(
                '  (dry-run — use --save para persistir)'
            ))

    def _build_user_content(
        self, template, brand_spec, tpl_b64, tpl_type, logos, grafismos
    ):
        cores = (brand_spec or {}).get('cores') or {}
        tipografia = (brand_spec or {}).get('tipografia') or {}
        meta_brand = json.dumps(
            {'cores': cores, 'tipografia': tipografia},
            ensure_ascii=False, indent=2,
        )[:8000]

        content = [
            {
                'type': 'text',
                'text': (
                    f'Template: {template.name} | aspect_ratio: {template.aspect_ratio}\n'
                    f'Descricao: {template.description or "(sem descricao)"}\n\n'
                    f'== Brand spec (cores + tipografia disponiveis) ==\n{meta_brand}\n\n'
                    f'== Assets da marca disponiveis ==\n'
                    f'Logos: {[(l["name"], l["type"]) for l in logos]}\n'
                    f'Grafismos: {[g["name"] for g in grafismos]}\n\n'
                    f'IMAGEM 1 = template visual a analisar.\n'
                    f'IMAGENS seguintes = logos e grafismos disponiveis.\n\n'
                    f'Produza JSON com regions calibradas como descrito no system prompt.'
                ),
            },
            {
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': tpl_type or 'image/png',
                    'data': tpl_b64,
                },
            },
        ]
        for lg in logos:
            content.append({'type': 'text', 'text': f'Logo: {lg["name"]} (type={lg["type"]})'})
            content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': lg['mt'], 'data': lg['b64']},
            })
        for gr in grafismos:
            content.append({'type': 'text', 'text': f'Grafismo: {gr["name"]}'})
            content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': gr['mt'], 'data': gr['b64']},
            })
        return content

    # ---- Helpers ------------------------------------------------------

    def _parse_json(self, text: str):
        if not text:
            return None
        # Remove cercas markdown se vier
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Tenta extrair primeiro objeto {} grande
            m = re.search(r'\{[\s\S]+\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    return None
            return None

    def _save_spec(self, template, spec_new):
        with transaction.atomic():
            backup = template.template_spec or {}
            # Preserva format_aspect do v2 ou aspect_ratio do model
            # (Claude as vezes esquece de incluir esse campo)
            if not spec_new.get('format_aspect'):
                spec_new['format_aspect'] = (
                    backup.get('format_aspect') or template.aspect_ratio or '1:1'
                )
            # Preserva background_color se v2 tinha
            if not spec_new.get('background_color') and backup.get('background_color'):
                spec_new['background_color'] = backup['background_color']
            # Backup v2 dentro do proprio JSON pra rollback
            spec_new['_v2_backup'] = backup
            template.template_spec = spec_new
            template.save(update_fields=['template_spec'])

    def _log_cost(self, template, resp):
        try:
            from apps.core.models import AIUsageLog
        except Exception:
            return
        usage = getattr(resp, 'usage', None)
        if not usage:
            return
        in_tokens = getattr(usage, 'input_tokens', 0) or 0
        out_tokens = getattr(usage, 'output_tokens', 0) or 0
        cost = (
            COST_INPUT_PER_M * Decimal(in_tokens) / Decimal(1_000_000) +
            COST_OUTPUT_PER_M * Decimal(out_tokens) / Decimal(1_000_000)
        )
        self.stdout.write(
            f'  Tokens: in={in_tokens} out={out_tokens} | '
            f'Custo: ${cost:.4f}'
        )
        try:
            AIUsageLog.objects.create(
                organization=template.knowledge_base.organization,
                knowledge_base=template.knowledge_base,
                provider=AIUsageLog.Provider.ANTHROPIC,
                model=MODEL,
                purpose=AIUsageLog.Purpose.OTHER,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                cost_usd=cost,
                raw_usage={
                    'template_id': template.id,
                    'template_name': template.name,
                    'context': 'reanalyze_template_v3',
                },
            )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  Falha logando custo: {exc}'))
