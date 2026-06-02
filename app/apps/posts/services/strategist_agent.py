"""
Strategist agent — primeiro nó do pipeline novo.

Lê briefing + KB + modal_choices e produz strategic_payload com decisões
estruturadas que viram briefs para copywriter (copy_direction) e designer
(visual_direction).

Carrega a skill estruturada (strategist_skill/) como system prompt cacheado 1h.
A 1ª chamada da janela paga write (+100%); próximas leem cache (-90%).
"""

import json
import logging
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 4000

_SKILL_DIR = Path(__file__).parent / 'strategist_skill'


def _load_skill() -> str:
    parts = []
    files = [
        _SKILL_DIR / 'SKILL.md',
        _SKILL_DIR / 'references' / 'intention-visual-map.md',
        _SKILL_DIR / 'references' / 'briefing-examples.md',
    ]
    for fp in files:
        try:
            parts.append(f'\n\n=== ARQUIVO: {fp.name} ===\n\n')
            parts.append(fp.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[strategist] skill file faltando: %s', fp)
    return ''.join(parts)


STRATEGIST_SKILL = _load_skill()


SYSTEM_INTRO = """Você é o estrategista criativo do iamkt. Você é o PRIMEIRO
agente do pipeline. Sua única função é ler o briefing + KB + escolhas do modal
e produzir o strategic_payload — JSON estruturado que vira brief para os
agentes downstream (copywriter recebe copy_direction; designer recebe
visual_direction).

Aplique o passo a passo da skill carregada abaixo. Respeite a cadeia de
prioridade (user_explicit > reference_visual > brand_kb > inferred).

Retorne APENAS o JSON do schema do Passo 5, sem texto antes/depois, sem
markdown."""


def generate_strategy(
    *,
    post,
    kb_summary: str,
    references: List[Dict[str, Any]] = None,
    modal_choices: Dict[str, Any] = None,
    paleta: List[Dict[str, Any]] = None,
    tipografia: List[Dict[str, Any]] = None,
    kb_dossiers: List[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Roda o strategist agent. Retorna dict com:
        {'payload': <strategic_payload>, 'usage': <tokens/custo>, 'model': MODEL}
    Ou None em caso de falha.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[strategist] ANTHROPIC_API_KEY ausente')
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning('[strategist] anthropic SDK indisponivel')
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user_text = _build_user_text(
        post=post,
        kb_summary=kb_summary,
        references=references or [],
        modal_choices=modal_choices or {},
        paleta=paleta or [],
        tipografia=tipografia or [],
        kb_dossiers=kb_dossiers or [],
    )

    system_blocks = [
        {
            'type': 'text',
            'text': SYSTEM_INTRO,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
        {
            'type': 'text',
            'text': STRATEGIST_SKILL,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
    ]

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=[{'role': 'user', 'content': user_text}],
        )
    except Exception:
        logger.exception('[strategist] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    payload = _parse_json(raw)
    if not payload:
        logger.error('[strategist] parse JSON falhou. Raw: %s', raw[:400])
        return None

    usage = _extract_usage(resp, cache_ttl='1h')
    intent = (payload.get('intention') or {}).get('primary', '?')
    confidence = (payload.get('briefing_meta') or {}).get('confidence', '?')
    img_style = (payload.get('visual_direction') or {}).get('image_style', '?')
    fw = (payload.get('copy_direction') or {}).get('framework', '?')
    flags = payload.get('flags') or []
    blockers = sum(1 for f in flags if (f.get('type') == 'blocker'))
    logger.info(
        '[strategist] post=%s tokens=%d cost=$%s intent=%s '
        'image_style=%s framework=%s confidence=%s blockers=%d',
        post.id, usage.get('total_tokens', 0), usage.get('cost_usd', 0),
        intent, img_style, fw, confidence, blockers,
    )
    return {
        'payload': payload,
        'usage': usage,
        'model': MODEL,
    }


def _build_user_text(*, post, kb_summary: str,
                     references: List[Dict[str, Any]],
                     modal_choices: Dict[str, Any],
                     paleta: List[Dict[str, Any]],
                     tipografia: List[Dict[str, Any]],
                     kb_dossiers: List[Dict[str, Any]]) -> str:
    formato = post.post_format
    fmt_str = (
        f"{formato.aspect_ratio} ({formato.width or '?'}x{formato.height or '?'}px)"
        if formato else '?'
    )
    parts = [
        '== Briefing do cliente ==',
        f'Rede social: {post.social_network or "instagram"}',
        f'Formato escolhido: {fmt_str}',
        f'Tema/contexto original: {post.requested_theme or "(sem tema)"}',
        f'CTA solicitado: {"sim" if getattr(post, "cta_requested", True) else "nao"}',
    ]

    if modal_choices:
        parts.extend([
            '',
            '== Escolhas explicitas do usuario no modal ==',
            '(prioridade MAXIMA — entram em priority_chain.user_explicit)',
        ])
        for k, v in modal_choices.items():
            if v in (None, '', [], {}):
                continue
            parts.append(f'  - {k}: {v}')

    # KB: resumo + paleta real + tipografia real
    parts.extend([
        '',
        '== Contexto da marca (KB) ==',
        '(prioridade brand_kb na cadeia)',
        kb_summary[:2000] if kb_summary else '(sem resumo da marca)',
    ])

    if paleta:
        parts.append('')
        parts.append('Paleta de cores da marca (USE EXATAMENTE ESSES HEXAS):')
        for c in paleta:
            parts.append(f'  - {c.get("hex")} ({c.get("tipo", "cor")}) — {c.get("nome", "")}')

    if tipografia:
        parts.append('')
        parts.append('Tipografia da marca (USE EXATAMENTE ESSAS FONTES — nao invente outras):')
        for t in tipografia:
            parts.append(f'  - {t.get("nome")} — uso: {t.get("uso")} — peso: {t.get("peso")}')

    # Referencias visuais — com metadados de produto e dossiê analítico
    produtos = [r for r in references if r.get('tipo') == 'produto']
    refs_visuais = [r for r in references if r.get('tipo') != 'produto']

    if produtos:
        parts.extend(['', '== Produto(s) do cliente (uploads) =='])
        for i, p in enumerate(produtos, 1):
            desc = (p.get('usage_description') or '').strip()
            parts.append(f'  Produto {i}: {desc or "(sem descricao)"}')

    dossiers_produto = [d for d in kb_dossiers if d.get('aspects') == ['produto']]
    dossiers_ref = [d for d in kb_dossiers if d.get('aspects') != ['produto']]

    if dossiers_produto:
        parts.extend([
            '',
            '== Produto(s) da KB — analise visual ja extraida ==',
            '(use para descrever o produto no card — nao invente modelo ou specs)',
        ])
        for d in dossiers_produto:
            dossier = d.get('dossier') or {}
            desc = d.get('usage_description') or ''
            if desc:
                parts.append(f'  Instrucao do usuario sobre este produto: "{desc}"')
            grid = dossier.get('grid') or {}
            zonas = grid.get('zonas') or []
            if zonas:
                parts.append('  O que a analise visual identificou no produto:')
                for z in zonas:
                    parts.append(f'    - {z.get("nome")}: {z.get("conteudo")}')
            if dossier.get('mood'):
                parts.append(f'  mood/atmosfera da imagem do produto: {dossier["mood"]}')
    elif produtos:
        parts.extend(['', '== Produto(s) do cliente (uploads sem analise) =='])
        for i, p in enumerate(produtos, 1):
            desc = (p.get('usage_description') or '').strip()
            parts.append(f'  Produto {i}: {desc or "(sem descricao)"}')

    if dossiers_ref:
        parts.extend([
            '',
            '== Analise visual das referencias da KB (ja extraida — USE para decidir image_style e composition) ==',
            '(prioridade reference_visual na cadeia — cada campo abaixo e informacao real da imagem)',
        ])
        for i, d in enumerate(dossiers_ref, 1):
            aspects = d.get('aspects') or []
            dossier = d.get('dossier') or {}
            parts.append(f'  Referencia KB {i} [aspectos analisados: {", ".join(aspects)}]:')
            grid = dossier.get('grid') or {}
            if grid.get('alinhamento_geral'):
                parts.append(f'    layout/alinhamento: {grid["alinhamento_geral"]}')
            zonas = grid.get('zonas') or []
            if zonas:
                parts.append('    zonas detectadas na imagem:')
                for z in zonas:
                    parts.append(
                        f'      - {z.get("nome")}: x={z.get("x_pct")}% y={z.get("y_pct")}% '
                        f'w={z.get("largura_pct")}% h={z.get("altura_pct")}% '
                        f'— "{z.get("conteudo")}"'
                    )
            if dossier.get('mood'):
                parts.append(f'    mood: {dossier["mood"]}')
            ilum = dossier.get('iluminacao') or {}
            if ilum:
                parts.append(f'    iluminacao: {ilum.get("tipo")} — {ilum.get("direcao")} — qualidade: {ilum.get("qualidade")}')
            pessoas = dossier.get('pessoas') or []
            if pessoas:
                parts.append(f'    pessoas: {len(pessoas)} figura(s) detectada(s)')
                for ps in pessoas[:2]:
                    parts.append(
                        f'      - {ps.get("pose")} | expressao: {ps.get("expressao")} | tom_pele: {ps.get("tom_pele")}'
                    )
    elif refs_visuais:
        parts.extend(['', '== Referencias visuais (sem dossie analitico) =='])
        for i, ref in enumerate(refs_visuais, 1):
            parts.append(f'  Ref {i}: tipo={ref.get("tipo")} — {ref.get("usage_description") or ""}')

    parts.extend([
        '',
        '== Tarefa ==',
        'Aplique o passo a passo da skill no system prompt e produza o JSON',
        'do schema do Passo 5 — strategic_payload completo.',
        '',
        'REGRAS CRITICAS:',
        '1. visual_direction.image_style: UMA decisao final, sem "ou". Use o',
        '   dossie das referencias para decidir — nao invente alternativas.',
        '2. typography_style: use os nomes de fonte exatos da KB (acima).',
        '   Nunca escreva "sans-serif" generico se a KB tem fonte propria.',
        '3. color_mood: use os hexas exatos da paleta da KB (acima).',
        '4. copy_direction.framework: UNO — copywriter e designer seguem o mesmo.',
        '5. priority_chain: cada decisao vai na camada correta.',
        '   user_explicit > reference_visual > brand_kb > inferred.',
        '6. flags: blocker para o que impede geracao; warning para inferencias',
        '   com risco; suggestion para recomendacoes ao user.',
    ])
    return '\n'.join(parts)


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


def _extract_usage(resp, cache_ttl: str = '1h') -> Dict[str, Any]:
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cache_write_rate = Decimal('6.0') if cache_ttl == '1h' else Decimal('3.75')
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
        + cache_write_rate * Decimal(cache_creation) / Decimal(1_000_000)
        + Decimal('0.30') * Decimal(cache_read) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'cache_creation_input_tokens': cache_creation,
        'cache_read_input_tokens': cache_read,
        'total_tokens': in_tokens + out_tokens + cache_creation + cache_read,
        'cost_usd': float(cost),
    }
