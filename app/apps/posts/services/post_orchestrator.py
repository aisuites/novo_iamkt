"""
Post Orchestrator — agente Claude Sonnet 4.5 multimodal que recebe o
briefing + imagens anexadas + KB e decide:

1. O ROLE de cada imagem na cena final (produto_principal, premio_destaque,
   pessoa_protagonista etc — semantica, nao apenas usage_type)
2. A ESTRATEGIA de composicao (narrativa, flat-lay, destaque dramatico etc)
3. O PROMPT FINAL otimizado para o Gemini (substitui o image_prompt cru)
4. O TEXT_RENDER_MODE adequado (inline | pillow | sanitized)
5. WARNINGS quando o briefing tem ambiguidade

Substitui o _build_combination_rules hardcoded. Mais caro (+$0.02/post),
porem MUITO mais inteligente em casos como "sorteio com premio", "speaker
+ palco", "produto + pessoa demonstrando" etc.

Custo: ~$0.02-0.03 por chamada (Sonnet 4.5 com 2-4 imagens + ~800 tokens out).
"""

import base64
import json
import logging
import os
import re
import urllib.request
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-5'
MAX_TOKENS = 2500

SYSTEM_PROMPT = """Voce e um diretor de arte e estrategista de conteudo digital
senior. Sua missao: receber um briefing de post + imagens de referencia + KB
da marca e produzir uma instrucao FINAL otimizada para um gerador de imagem
(Gemini 3 Pro Image).

A diferenca entre voce e os geradores de imagem: VOCE ENTENDE A INTENCAO.

EXEMPLOS DE INTENCOES E COMO INTERPRETAR:
- "Sorteio do produto X e voce ganha o produto Y"
   -> X = produto principal/funcional, Y = premio em destaque (luz dramatica,
      pedestal, troféu visual)
- "Conheça nosso novo produto X"
   -> X = produto unico em destaque, sem distracoes
- "Speaker Z no evento Y"
   -> Z (pessoa) = protagonista, foto do rosto preservada
- "Combo: produto X + produto Y juntos"
   -> Ambos com peso igual (flat-lay, vitrine)
- "Use o produto X no cenario do palestrante Y"
   -> Pessoa interagindo com produto em destaque

REGRAS DE SAIDA:
1. Para cada IMAGEM anexada, atribua um ROLE semantico (nao apenas o
   usage_type tecnico — interprete a INTENCAO).
2. Escolha uma COMPOSITION STRATEGY que faca a narrativa do briefing fluir.
3. Produza o IMAGE_PROMPT_FINAL para o Gemini com REGRAS CRITICAS:

   a) NUNCA descreva produtos/pessoas em palavras. SEMPRE use referencia
      por imagem: "o produto da IMAGEM N", "a pessoa da IMAGEM N", "a bolsa
      da IMAGEM N". Descrever em palavras (ex: "uma bolsa de couro
      monogramada marrom") ativa priors do training data do Gemini e ele
      ignora a imagem anexada.

      ❌ ERRADO: "uma elegante bolsa de couro com padrao monogramado marrom
                  e fecho dourado"
      ✅ CERTO: "a bolsa da IMAGEM 3, exatamente como aparece"

      ❌ ERRADO: "um processador de alimentos moderno com tela touchscreen"
      ✅ CERTO: "o produto da IMAGEM 4, exatamente como aparece, sem
                 modificar formato, cor ou display"

   b) NUNCA mencione nomes de marca, modelo de produto, ou caracteristicas
      especificas do produto em palavras. Apenas "o produto da IMAGEM N".

   c) NAO use pedestais flutuantes ou elementos no ar sem ancoragem fisica.
      Sempre coloque produtos sobre superficies REAIS (bancada, mesa,
      prateleira, chao). Pedestais flutuantes geram artefatos visuais
      ("produto voando").

   d) Descreva LIVREMENTE em palavras: ambiente, iluminacao, mood,
      composicao geral, elementos secundarios (ingredientes, plantas,
      texturas, paredes). Tudo que NAO seja produto/pessoa principal.

   e) Mantenha o prompt em 3-6 linhas. Direto, sem floreios.
4. Decida TEXT_RENDER_MODE:
   - 'inline' (Gemini desenha texto): se o titulo nao contem marcas/nomes
     proprios que ativam priors. Tem o melhor visual integrado.
   - 'pillow' (texto desenhado depois): se o titulo contem nomes proprios
     CRITICOS (marca/produto/modelo) que precisam ser literais OU se ja
     ha produtos sensiveis a name-anchor.
   - 'sanitized': raramente — quase nunca melhor que pillow.
5. LAYOUT PLAN — defina zonas reservadas no canvas para que o gerador de
   imagem NAO posicione elementos visuais (rostos, produtos, detalhes) sobre
   areas que vao receber texto/logo em pos-processamento.

   Por padrao, o canvas tem 4 zonas:
   - title_zone: onde o titulo aparece (topo esquerdo ou superior)
   - subtitle_zone: opcional, abaixo do titulo
   - logo_zone: pequena area para logo da marca (canto)
   - cta_zone: opcional, area do call-to-action (rodape)
   - main_subject_zone: centro/foco principal (onde produtos+pessoas devem
     ser concentrados)

   Para cada zona, defina:
   - position: "top-left"|"top-center"|"top-right"|"center-left"|"center"|
     "center-right"|"bottom-left"|"bottom-center"|"bottom-right"
   - width_pct e height_pct: tamanho relativo ao canvas (0-100)
   - background_requirement: "uniforme/claro/desfocado/sem rostos/sem texto"
     — instrucao para o Gemini deixar essa area visualmente "limpa"

   Considere o aspect ratio do canvas (sera informado no briefing):
   - 1:1 (feed quadrado): title topo, cta rodape, sujeito centro
   - 9:16 (stories/reels): titulo topo, cta base, sujeito centro
   - 4:5 (feed retrato): title topo, cta base, sujeito centro-baixo
   - 16:9 (banner/linkedin): title left, sujeito right (lado a lado)

6. WARNINGS: se o briefing tem ambiguidades importantes (ex: "faltam regras
   do sorteio", "nao esta claro qual produto e o premio"), liste em
   warnings. Nao bloqueia geracao mas registra.

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "image_roles": [
    {
      "image_n": 1,
      "tipo_original": "logo",
      "role": "marca",
      "treatment": "string descrevendo onde/como aplicar"
    },
    ...
  ],
  "composition_strategy": "string narrativa explicando a composicao geral",
  "image_prompt_final": "string final em PT-BR para o Gemini (3-6 linhas)",
  "text_render_mode": "inline" | "pillow" | "sanitized",
  "text_render_rationale": "string curta justificando a escolha",
  "layout_plan": {
    "title_zone": {
      "position": "top-left",
      "width_pct": 60,
      "height_pct": 22,
      "background_requirement": "uniforme/claro/sem rostos/sem texto"
    },
    "subtitle_zone": {
      "position": "top-left",
      "width_pct": 60,
      "height_pct": 8,
      "background_requirement": "uniforme/continuacao do titulo"
    },
    "logo_zone": {
      "position": "top-right",
      "width_pct": 12,
      "height_pct": 8,
      "background_requirement": "fundo limpo, sem elementos"
    },
    "cta_zone": {
      "position": "bottom-center",
      "width_pct": 50,
      "height_pct": 10,
      "background_requirement": "superficie uniforme — bancada, fundo simples, sem rostos"
    },
    "main_subject_zone": {
      "position": "center",
      "description": "produtos e pessoas concentrados aqui"
    }
  },
  "spatial_instructions_for_gemini": "string com instrucoes explicitas para o gerador de imagem respeitar as zonas reservadas. Sera injetada como bloco separado no prompt final.",
  "warnings": ["string de cada warning"]
}

REGRAS CRITICAS para layout_plan:
- title_zone NUNCA deve incluir rosto humano, produto principal, ou texto visivel
- main_subject_zone deve estar AFASTADO das zonas de title/cta para nao competir
- Aspect ratio define onde o sujeito vai: 9:16/4:5/1:1 -> sujeito CENTRO-BAIXO,
  16:9 -> sujeito CENTRO-DIREITA (texto fica na esquerda)

EXEMPLOS DE spatial_instructions_for_gemini:
- "DEIXE LIVRE a area do topo (0-25% da altura): nenhum rosto, nenhum produto,
   nenhum texto. Pode haver parede uniforme, ceu, fundo desfocado, mesa lisa.
   Esta area sera coberta por titulo em pos-processamento."
- "Posicione o sujeito principal e os produtos no terço CENTRAL e INFERIOR
   da composicao, deixando o terço superior visualmente limpo."

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def orchestrate_post(
    *,
    post,
    references: List[Dict[str, Any]],
    kb_summary: str,
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    references_usage_description: str = '',
    formato_px: str = '',
    aspect_ratio: str = '',
    kb_dossiers: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Roda o orquestrador Claude Sonnet 4.5 multimodal.

    Args:
        post: Post Django (le title, subtitle, requested_theme, cta)
        references: lista de dicts {url, tipo, usage_description} — refs
            que vao pro Gemini (logos + grafismos + uploads)
        kb_summary: resumo textual da KB
        paleta: lista de cores
        tipografia: lista de fontes
        references_usage_description: texto livre do user sobre uso das refs

    Retorna dict com:
        {
          'orchestration': dict do JSON parseado (image_roles, strategy, etc),
          'usage': dict de tokens/custo,
          'model': str,
        }
    Ou None em caso de falha (caller usa fallback).
    """
    kb_dossiers = kb_dossiers or []

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[orchestrator] ANTHROPIC_API_KEY ausente')
        return None

    if not references and not kb_dossiers:
        logger.info('[orchestrator] sem refs nem dossies — skip orchestration')
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Monta content multimodal: lista de imagens + meta de cada + texto final
    content_blocks: List[Dict[str, Any]] = []
    image_meta_lines = []

    for i, ref in enumerate(references, 1):
        url = ref.get('url')
        tipo = str(ref.get('tipo', 'desconhecido')).lower()
        usage_desc = (ref.get('usage_description') or '').strip()

        meta = f'IMAGEM {i}: tipo_original={tipo}'
        if usage_desc:
            meta += f' | uso indicado pelo user: "{usage_desc}"'
        image_meta_lines.append(meta)

        if not url:
            continue
        try:
            b64, mime = _download_to_base64(url)
            if not b64:
                continue
            content_blocks.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': mime, 'data': b64},
            })
        except Exception as exc:
            logger.warning('[orchestrator] falha download imagem %d: %s', i, exc)

    # Texto final com briefing e metadados
    user_text = _build_user_text(
        post=post,
        kb_summary=kb_summary,
        paleta=paleta,
        tipografia=tipografia,
        references_usage_description=references_usage_description,
        image_meta_lines=image_meta_lines,
        formato_px=formato_px,
        aspect_ratio=aspect_ratio,
        kb_dossiers=kb_dossiers,
    )
    content_blocks.append({'type': 'text', 'text': user_text})

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {'role': 'user', 'content': content_blocks},
                {'role': 'assistant', 'content': '{'},  # prefill JSON
            ],
        )
    except Exception:
        logger.exception('[orchestrator] erro Claude')
        return None

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    orchestration = _parse_json(raw)
    if not orchestration:
        logger.error('[orchestrator] parse JSON falhou. Raw: %s', raw[:400])
        return None

    # Sanity check basico do output
    if 'image_prompt_final' not in orchestration:
        logger.warning('[orchestrator] output sem image_prompt_final — invalido')
        return None

    usage = _extract_usage(resp)
    logger.info(
        '[orchestrator] post=%s tokens=%d cost=$%s strategy=%s mode=%s',
        post.id, usage.get('total_tokens', 0), usage.get('cost_usd', 0),
        (orchestration.get('composition_strategy') or '')[:80],
        orchestration.get('text_render_mode', '?'),
    )

    return {
        'orchestration': orchestration,
        'usage': usage,
        'model': MODEL,
    }


def _build_user_text(
    *,
    post,
    kb_summary: str,
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    references_usage_description: str,
    image_meta_lines: List[str],
    formato_px: str = '',
    aspect_ratio: str = '',
    kb_dossiers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    lines = [
        '== Briefing do post ==',
        f'Titulo: {post.title or "(sem titulo)"}',
        f'Subtitulo: {post.subtitle or "(sem subtitulo)"}',
        f'CTA: {post.cta or "(sem CTA)"}',
        f'Tema/contexto original: {post.requested_theme or "(sem tema)"}',
        f'Rede social: {post.social_network or "instagram"}',
        f'Formato da arte: {formato_px or "?"} (aspect_ratio: {aspect_ratio or "?"})',
        '',
        '== Marca (KB compilation) ==',
        kb_summary[:1500] if kb_summary else '(sem resumo da marca)',
        '',
        '== Imagens anexadas (na ordem mostrada ACIMA deste texto) ==',
        '\n'.join(image_meta_lines) if image_meta_lines else '(nenhuma)',
    ]
    if references_usage_description:
        lines.extend([
            '',
            '== Observacao geral do user sobre uso das referencias ==',
            references_usage_description,
        ])
    if kb_dossiers:
        lines.extend([
            '',
            '== Dossies de imagens de referencia da marca (KB) ==',
            '(Analise visual ja extraida dessas imagens. NAO sao imagens a',
            'reproduzir — sao referencias de ESTILO. Use APENAS os aspectos que',
            'o user pediu em "o que aproveitar". Incorpore os aspectos relevantes',
            '(iluminacao, paleta, composicao, mood, grid, etc) no image_prompt_final.',
            'NUNCA copie produtos/pessoas especificos desses dossies.)',
        ])
        for i, d in enumerate(kb_dossiers, 1):
            dossier = d.get('dossier') or {}
            intent = (d.get('usage_description') or '').strip() or '(uso geral / inspiracao)'
            lines.append('')
            lines.append(f'-- Referencia KB {i} --')
            lines.append(f'O que aproveitar (intencao do user): "{intent}"')
            lines.append('Dossie: ' + json.dumps(dossier, ensure_ascii=False)[:1800])

    lines.extend([
        '',
        '== Tarefa ==',
        'Analise as imagens + os dossies + o briefing acima e produza o JSON',
        'conforme instrucoes do system prompt. Foque em INTENCAO, nao apenas em',
        'usage_type tecnico. Para os dossies da KB, extraia SO o que o user',
        'pediu em "o que aproveitar" e funda no image_prompt_final.',
    ])
    return '\n'.join(lines)


def _download_to_base64(url: str):
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ct = resp.headers.get('Content-Type', 'image/png').split(';')[0].strip()
    except Exception:
        return None, 'image/png'
    if ct not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        ct = 'image/png'
    return base64.b64encode(data).decode('ascii'), ct


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    s = re.sub(r'^```(?:json)?\s*', '', text.strip())
    s = re.sub(r'\s*```$', '', s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _extract_usage(resp) -> Dict[str, Any]:
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
        + Decimal('3.75') * Decimal(cache_write) / Decimal(1_000_000)
        + Decimal('0.30') * Decimal(cache_read) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'total_tokens': in_tokens + out_tokens,
        'cost_usd': float(cost),
    }
