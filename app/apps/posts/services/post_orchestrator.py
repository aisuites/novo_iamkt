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
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 8000

# Carrega o conhecimento do orquestrador-designer: base compartilhada
# (shared_skill/) + designer_skill (SKILL + 3 references). Bloco cacheado
# por 1h via cache_control no system message.
_SERVICES_DIR = Path(__file__).parent
_SHARED_DIR = _SERVICES_DIR / 'shared_skill'
_DESIGNER_DIR = _SERVICES_DIR / 'designer_skill'


def _load_skill_for_orchestrator() -> str:
    parts = []
    files = [
        # Base compartilhada (designer + critico aplicam os mesmos principios)
        _SHARED_DIR / 'formats-and-safe-zones.md',
        _SHARED_DIR / 'typography-scale.md',
        _SHARED_DIR / 'contrast-rules.md',
        _SHARED_DIR / 'design-principles.md',
        # Especifica do designer (criacao do wireframe, image_prompt, etc.)
        _DESIGNER_DIR / 'SKILL.md',
        _DESIGNER_DIR / 'references' / 'wireframe-examples.md',
        _DESIGNER_DIR / 'references' / 'prompt-library.md',
        _DESIGNER_DIR / 'references' / 'render-order-guide.md',
    ]
    for fp in files:
        try:
            parts.append(f'\n\n=== ARQUIVO: {fp.name} ===\n\n')
            parts.append(fp.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[orchestrator] skill file faltando: %s', fp)
    return ''.join(parts)


DESIGNER_SKILL = _load_skill_for_orchestrator()

# Aspecto escolhido no modal -> diretriz explicita do que extrair da referencia.
# Substitui o texto livre "o que aproveitar" (removido do modal).
ASPECT_DIRECTIVES = {
    'layout_composicao': (
        'Layout/composicao: posicoes do grid, hierarquia visual, onde texto '
        'cai. Sao inspiracao para o seu layout — voce adapta ao nosso conteudo '
        '(que pode ter texto mais longo, formato diferente, mais blocos). NAO '
        'copie o sujeito/comida/cenario.'
    ),
    'iluminacao': (
        'Iluminacao: tipo, direcao, temperatura e qualidade da luz da referencia.'
    ),
    'estilo_ambiente': (
        'Ambiente/cenario: superficies, materiais, mood e paleta de cena. NAO '
        'copie o sujeito especifico.'
    ),
    'estilo_pessoas': (
        'Estilo das pessoas: enquadramento, pose, faixa etaria, vestuario, mood. '
        'Preserve rosto se foto especifica anexada; senao inspire-se sem copiar.'
    ),
    'grafismos': (
        'Grafismos: faixas, selos, divisores da referencia. Cores e formas. '
        'Selos circulares e linhas retas o Pillow desenha (injetados '
        'deterministicamente). Faixas com curva organica vao para o Gemini — '
        'voce descreve fielmente no image_prompt_final.'
    ),
}

# Aspecto -> chaves do dossie que importam (envia so a fatia relevante,
# evita truncamento e ruido). 'descricao_geral' entra sempre como contexto.
ASPECT_DOSSIER_KEYS = {
    # layout = ESTRUTURA (sem grafismos: faixas/selos sao o aspecto 'grafismos')
    'layout_composicao': ['grid', 'composicao', 'texto_x_imagem',
                          'recreation_prompt', 'logo_na_referencia'],
    'iluminacao': ['iluminacao'],
    'estilo_ambiente': ['ambiente', 'mood', 'estilo_visual', 'paleta_observada'],
    'estilo_pessoas': ['pessoas', 'is_humanizada'],
    'grafismos': ['assets_grafismos', 'paleta_observada'],
}


def _slice_dossier(dossier: Dict[str, Any], aspects) -> Dict[str, Any]:
    """Retorna so a fatia do dossie relevante aos aspectos escolhidos (uniao das
    chaves de cada aspecto). Sempre inclui 'descricao_geral' como contexto curto.
    Sem aspecto conhecido -> dossie inteiro."""
    if not isinstance(dossier, dict):
        return {}
    if isinstance(aspects, str):
        aspects = [aspects]
    aspects = [a for a in (aspects or []) if a]
    wanted = []
    for a in aspects:
        for k in ASPECT_DOSSIER_KEYS.get(a, []):
            if k not in wanted:
                wanted.append(k)
    if not wanted:
        return dossier
    out = {}
    if dossier.get('descricao_geral'):
        out['descricao_geral'] = dossier['descricao_geral']
    for k in wanted:
        if k in dossier:
            out[k] = dossier[k]
    return out

SYSTEM_PROMPT = """Voce e diretor de arte senior desta marca. Sua missao:
produzir UMA instrucao final (image_prompt + layout_document) que um gerador
de imagem (Gemini 3 Pro Image) seguido de Pillow vao virar a arte do post.

Como diretor senior, voce PENSA, JULGA e DECIDE. Voce nao segue checklist —
voce CRIA com julgamento informado.

# CONTEXTO QUE VOCE RECEBE

- KB da marca: paleta, tipografia, voz/identidade visual.
- Referencias visuais selecionadas pelo user. Cada uma tem ASPECTO(s)
  escolhidos (layout_composicao, iluminacao, estilo_pessoas, estilo_ambiente,
  grafismos, produto). Para cada uma voce recebe:
  - A IMAGEM em si (o Gemini tambem vai recebe-la, na sequencia do
    pipeline — voce tem que saber disso)
  - O DOSSIE objetivo (analise visual ja extraida, fatiada pelo aspecto)
- Briefing do post (titulo, subtitulo, CTA, tema).
- Formato (1:1, 9:16, 16:9, 4:5...).

# OBJETIVO

Arte final que seja:
- Coerente com a identidade visual da marca.
- Fiel a intencao do user e ao(s) aspecto(s) escolhido(s) em cada ref.
- Legivel (titulo importante, subtitulo subordinado, contraste suficiente).
- Tecnicamente realizavel pela cadeia Gemini + Pillow.

# COMO O TRABALHO ACONTECE TECNICAMENTE (consequencias para o seu plano)

O Gemini recebe: as imagens das refs (multimodal) + um texto seu
(`image_prompt_final`). Ele gera UMA CENA.
O Pillow recebe: a cena do Gemini + um `layout_document` seu (lista de
"divs" — texto, logo, grafismos primitivos como circulo/linha). Ele desenha
por cima.

Implicacoes que voce precisa internalizar:
- **Gemini equilibra TEXTO + VISUAL.** Se voce descreve uma cozinha escura
  mas anexa uma referencia de cozinha clara, o VISUAL ganha. Seu
  `image_prompt_final` precisa ser CONSISTENTE com as referencias que
  voce esta anexando — descreva uma cena que combina com a luz, ambiente,
  pessoas e estilo das refs. Se nao quer que algum aspecto da ref
  influencie, simplesmente NAO inclua aquele aspecto.
- **Pillow desenha bem**: texto, logo (asset), selo circular com texto,
  linhas retas. SO ISSO.
- **Pillow NAO desenha**: faixas, blocos/zonas de cor, swoosh, ondas,
  formas com curva organica, foto. TUDO ISSO e parte da CENA -> vai no
  image_prompt_final (Gemini), NUNCA no layout_document.
- **Grafismo de marca ATRAS do texto** (bloco/faixa/swoosh de cor que serve
  de fundo para o titulo/subtitulo): e CENA, NAO overlay. NUNCA use
  retangulo/bloco Pillow como fundo de texto e NUNCA reserve "zona limpa"
  esperando um overlay desenhar o bloco depois — esse overlay NAO existe.
  IMPORTANTE: NAO descreva em palavras a forma, a cor nem a posicao do
  grafismo no image_prompt_final. Quando houver uma IMAGEM N com role GRAPHIC
  REFERENCE anexada, escreva no image_prompt_final APENAS uma frase de
  reforco, sem detalhar o grafismo: "Todos os elementos graficos devem ser
  extraidos da IMAGEM N de referencia com ALTA FIDELIDADE; nao invente nenhum
  outro grafismo." Os grafismos vem da imagem anexada, nunca da sua descricao.
- **Pillow honra suas decisoes**: se voce escolhe a cor de um texto, ele
  usa aquela cor. Se voce deixa cor em branco/null, ele auto-contrasta.
- **Pillow tem rede de protecao silenciosa**: se voce dimensionar um texto
  que nao cabe, ele encolhe. Mas voce e o designer — pense na caixa antes.

# COMO VOCE TRABALHA

1. **Estude** o briefing + as referencias + os dossies. Entenda o que o
   user quer comunicar e o que cada referencia aporta segundo o aspecto.
   Observe SOBREPOSICOES (o que cobre o que).
2. **Sintetize** em um plano visual: composicao, hierarquia, onde cada
   elemento vai, cores, ritmo, respiracao. Para texto, pense na caixa
   (x_pct, y_pct, width_pct, height_pct) considerando o conteudo real
   (caracteres do nosso post — se maior que o da ref, a caixa precisa
   crescer).
3. **Decida o render_plan** por elemento (texto/logo/primitiva simples
   -> Pillow; cena + grafismos complexos + produto -> Gemini).
4. **Releia seu plano como designer.** Funciona? Os textos cabem nas
   caixas declaradas com IMPACTO adequado? A hierarquia esta legivel?
   A cena que voce esta pedindo ao Gemini eh CONSISTENTE com as
   referencias visuais que voce esta anexando? As cores fazem sentido
   com o fundo descrito? Se nao, ITERE.
5. **Emita o JSON final.**

# PRINCIPIOS

- **Cena cheia, organica.** O Gemini compoe uma fotografia completa que
  ocupa todo o quadro. NAO reserve "zona limpa" para texto. NAO descreva
  paredes "lisas" ou "neutras escuras para acomodar texto". Descreva
  TEXTURA REAL (reboco com grao, cimento queimado, marmore com veios,
  madeira escovada) — sujeito num lado, area mais calma do outro como
  parte ORGANICA da cena.
- **Identidade do produto > criatividade da cena.** Use SEMPRE "o produto
  da IMAGEM N" — nunca descreva o produto em palavras (ativa priors).
  Mesmo principio para pessoas (preserve rosto se ref especifica).
- **Cadeia de prioridade.** Quando ha conflito: escolha direta do user
  (logo_position, posicao etc.) > aspect/dossie da ref > sua intuicao.
- **Sem pedestais flutuantes, sem glow/halo coloridos artificiais.**
- **Hierarquia visual clara**: titulo > subtitulo > cta. Voce escolhe os
  tamanhos.
- **Coerencia texto-visual**: o que voce diz no `image_prompt_final` tem
  que combinar com o que o Gemini vai ver nas refs.

# REGRAS DA INSTRUCAO PARA O GEMINI (`image_prompt_final`)

- 3-6 linhas. Direto.
- Cada produto/pessoa principal: "o produto da IMAGEM N" / "a pessoa
  da IMAGEM N". Nunca em palavras.
- Pode mostrar produto em angulo/posicao diferente da foto, mas com a
  MESMA identidade.
- Descreva livremente: ambiente, iluminacao, mood, composicao, elementos
  secundarios.
- Luz realista (natural de janela, estudio suave). Sem efeitos artificiais.

# FORMATO DE SAIDA (JSON puro, sem markdown — backend precisa parsear)

{
  "study": "<sua leitura do briefing + refs + dossies, em prosa de designer>",
  "wireframe": "<plano visual: posicoes em %, hierarquia, ritmo, em prosa>",
  "wireframe_critique": "<sua releitura como designer: o que funciona, o que ajustou, por que o desenho final esta bom — prosa, nao formula>",
  "render_plan": [
    {"elemento": "<nome>", "render": "pillow" | "gemini", "razao": "<curta>"}
  ],
  "rules": "<decisoes finais por bloco em prosa direta: cor, tamanho, contraste, posicao>",
  "image_roles": [
    {"image_n": <int>, "tipo_original": "<tipo>", "role": "<papel semantico>", "treatment": "<como aplicar>"}
  ],
  "composition_strategy": "<resumo curto da composicao>",
  "image_prompt_final": "<texto em PT-BR para o Gemini, 3-6 linhas, consistente com as refs anexadas>",
  "spatial_instructions_for_gemini": "<sintese curta da composicao>",
  "text_render_mode": "pillow",
  "layout_document": {
    "elements": [
      {"role": "titulo", "content": "<texto>", "x_pct": <num>, "y_pct": <num>, "width_pct": <num>, "height_pct": <num>, "font_size_pct": <num>, "weight": "bold|regular", "case": "none|upper", "color": "#RRGGBB" | null, "align": "left|center|right", "padding_pct": <num>},
      {"role": "subtitulo", ... (mesmos campos)},
      {"role": "cta", ... (mesmos campos)},
      {"role": "logo", "x_pct": <num>, "y_pct": <num>, "width_pct": <num>},
      // opcional quando ha grafismos primitivos:
      {"role": "grafismo", "forma": "selo|linha", "cor": "#RRGGBB", "x_pct": <num>, "y_pct": <num>, "width_pct": <num>, "height_pct": <num>}
    ]
  },
  "warnings": ["<warning, se houver>"]
}

# OBSERVACOES FINAIS

- Cor null/em branco = Pillow auto-escolhe contraste. Cor hex = Pillow usa
  exatamente. Voce escolhe quando delegar e quando decidir.
- O Pillow tem auto-fit por altura como rede silenciosa. Mas projete a caixa
  com folga, pra nao precisar.
- Grafismos complexos (faixas com curva organica) entram na descricao do
  `image_prompt_final` (Gemini desenha na cena). Selos circulares e linhas
  retas entram como `role: "grafismo"` no layout_document (Pillow desenha).

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown.
"""


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

    # System como LIST: [skill cacheada 1h, system_prompt cacheado 1h].
    # Os 2 blocos sao estaticos por hora — sao escritos em cache na 1a chamada
    # e lidos com -90% nas seguintes. O conteudo dinamico (refs, dossie,
    # briefing) vai no messages.user, fora do cache.
    system_blocks = [
        {
            'type': 'text',
            'text': DESIGNER_SKILL,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
        {
            'type': 'text',
            'text': SYSTEM_PROMPT,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
    ]
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=[
                {'role': 'user', 'content': content_blocks},
            ],
        )
    except Exception:
        logger.exception('[orchestrator] erro Claude')
        return None

    # Sonnet 4.6 nao aceita prefill de assistant; _parse_json extrai o JSON
    # mesmo com cercas markdown / texto ao redor.
    raw = ''.join(
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

    usage = _extract_usage(resp, cache_ttl='1h')
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
        '== Cores da marca (paleta KB) — use para glow/acentos da cena ==',
        ', '.join(
            f"{(c.get('hex') or '').strip()} ({c.get('tipo') or 'cor'})"
            for c in (paleta or []) if c.get('hex')
        ) or '(sem paleta)',
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
            'reproduzir — sao referencias de ESTILO. Cada uma tem um ASPECTO que o',
            'user escolheu aproveitar (na linha "Instrucao"). Extraia SOMENTE aquele',
            'aspecto e funda no image_prompt_final / layout_document. O dossie abaixo',
            'ja vem FILTRADO para o aspecto escolhido. NUNCA copie produtos/pessoas',
            'especificos desses dossies.)',
        ])
        for i, d in enumerate(kb_dossiers, 1):
            dossier = d.get('dossier') or {}
            aspects = d.get('aspects')
            if aspects is None:  # compat: formato antigo com 'aspect' string
                _a = (d.get('aspect') or '').strip()
                aspects = [_a] if _a else []
            aspects = [a for a in aspects if a]
            free_text = (d.get('usage_description') or '').strip()
            directives = [ASPECT_DIRECTIVES[a] for a in aspects if a in ASPECT_DIRECTIVES]
            if directives:
                intent = '\n  '.join(directives)
            elif free_text:
                intent = free_text
            else:
                intent = '(uso geral / inspiracao — extraia o que melhor servir ao briefing)'
            sliced = _slice_dossier(dossier, aspects)
            header = f'-- Referencia KB {i}'
            header += f' [aspectos: {", ".join(aspects)}] --' if aspects else ' --'
            lines.append('')
            lines.append(header)
            lines.append(f'Instrucao: {intent}')
            lines.append(
                'Dossie (filtrado para os aspectos): '
                + json.dumps(sliced, ensure_ascii=False)[:5000]
            )

    lines.extend([
        '',
        '== Tarefa ==',
        'Analise as imagens + os dossies + o briefing acima e produza o JSON',
        'conforme instrucoes do system prompt. Foque em INTENCAO, nao apenas em',
        'usage_type tecnico. Para cada dossie da KB, extraia SOMENTE o aspecto da',
        'linha "Instrucao" e funda no image_prompt_final / layout_document.',
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


def _extract_usage(resp, cache_ttl: str = '5m') -> Dict[str, Any]:
    """Extrai tokens/custos incluindo CACHE. cache_ttl='1h' usa write +100%,
    '5m' usa write +25%. Cache read sempre -90%."""
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cache_write_rate = Decimal('6.0') if cache_ttl == '1h' else Decimal('3.75')
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
        + cache_write_rate * Decimal(cache_write) / Decimal(1_000_000)
        + Decimal('0.30') * Decimal(cache_read) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'cache_creation_input_tokens': cache_write,
        'cache_read_input_tokens': cache_read,
        'total_tokens': in_tokens + out_tokens + cache_write + cache_read,
        'cost_usd': float(cost),
    }


# =====================================================================
# ADAPTADOR DE LAYOUT POR FORMATO (text-only) — usado quando a ref de
# layout nasceu num aspect ratio diferente do post (ex: 1:1 -> 9:16).
# =====================================================================

_LAYOUT_ADAPT_SYSTEM = """Voce e um diretor de arte. Recebe um LAYOUT_SPEC de
texto pensado para um aspect ratio de ORIGEM e deve ADAPTA-LO para um aspect
ratio de DESTINO diferente, mantendo a INTENCAO mas reposicionando as ZONAS.

REGRAS:
- Mantenha title_align / subtitle_align / cta_align EXATAMENTE como vieram.
- Reposicione apenas as zonas em %: title_zone_pct, subtitle_zone_pct e as
  posicoes de logo/cta. Campos: x_pct, y_pct (canto superior esquerdo),
  width_pct. Tudo 0-100.
- Pense na proporcao: indo de 1:1 (quadrado) para 9:16 (vertical alto), um
  bloco de texto no terco esquerdo pode subir para o TOPO. De 1:1 para 16:9
  (horizontal), o texto tende a ficar de um LADO (esquerda) e o sujeito do outro.
- PESO DE OCUPACAO: mantenha o texto com peso visual SEMELHANTE ao da origem.
  O texto NAO deve dominar a arte — o sujeito (produto/pessoa) continua sendo o
  foco. NAO alargue a zona de texto alem do necessario (evite width_pct alto so
  para preencher espaco). Prefira manter o texto compacto num canto/faixa.
- NAO crie campos novos nem remova existentes. Devolva os MESMOS campos do
  input, apenas com as zonas/posicoes ajustadas ao destino.

Devolva APENAS o JSON do layout_spec adaptado, sem markdown."""


def adapt_layout_spec(
    layout_spec: Dict[str, Any],
    source_ar: float,
    target_ar: float,
    target_px: str = '',
) -> Optional[Dict[str, Any]]:
    """
    Reposiciona as zonas de um layout_spec da proporcao de origem para a de
    destino via Claude (text-only, barato). Mantem alinhamentos. Retorna o
    spec adaptado (merge sobre o original) ou None em falha.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key or not layout_spec:
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    user = (
        f'LAYOUT_SPEC (origem aspect_ratio={source_ar}):\n'
        f'{json.dumps(layout_spec, ensure_ascii=False)}\n\n'
        f'Adapte para o DESTINO: aspect_ratio={target_ar}'
        + (f', dimensoes={target_px}' if target_px else '')
        + '.\nDevolva o JSON adaptado.'
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=_LAYOUT_ADAPT_SYSTEM,
            messages=[
                {'role': 'user', 'content': user},
            ],
        )
    except Exception:
        logger.exception('[layout_adapt] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    adapted = _parse_json(raw)
    if not adapted:
        logger.warning('[layout_adapt] parse JSON falhou')
        return None
    merged = dict(layout_spec)
    merged.update(adapted)

    # Clamp de seguranca: o texto nao deve dominar a arte. Limita a largura das
    # zonas de texto (mesmo que o LLM tenha alargado demais).
    for key, cap in (('title_zone_pct', 60), ('subtitle_zone_pct', 72)):
        zone = merged.get(key)
        if isinstance(zone, dict) and zone.get('width_pct'):
            try:
                if float(zone['width_pct']) > cap:
                    zone['width_pct'] = cap
            except (TypeError, ValueError):
                pass

    merged['source'] = 'dossier_layout_aspect+format_adapted'
    return merged
