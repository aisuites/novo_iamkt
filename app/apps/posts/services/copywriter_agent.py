"""
Copywriter agent — geração estruturada de copy a partir do briefing.

Recebe o briefing + KB e produz copy_payload com variants + design_hints,
pronto para handoff ao designer_agent.

Carrega a skill estruturada (copywriter_skill/) como system prompt cacheado
1h. Custo otimizado: 1ª chamada da janela paga write (+100%), próximas leem
cache (-90%).
"""

import base64
import json
import logging
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 6000

_SKILL_DIR = Path(__file__).parent / 'copywriter_skill'


def _load_skill() -> str:
    parts = []
    files = [
        _SKILL_DIR / 'SKILL.md',
        _SKILL_DIR / 'references' / 'tone-guide.md',
        _SKILL_DIR / 'references' / 'hook-bank.md',
        _SKILL_DIR / 'references' / 'copy-examples.md',
    ]
    for fp in files:
        try:
            parts.append(f'\n\n=== ARQUIVO: {fp.name} ===\n\n')
            parts.append(fp.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[copywriter] skill file faltando: %s', fp)
    return ''.join(parts)


COPYWRITER_SKILL = _load_skill()


SYSTEM_INTRO = """Você é um copywriter especialista. Você recebe um briefing
do iamkt (marca SaaS B2B/B2C multi-tenant) e produz copy estruturado em JSON
seguindo a skill carregada abaixo (passos, regras de quality, schema de saída).

Aplique o passo a passo do skill. Retorne APENAS o JSON do schema do Passo 5,
sem texto antes/depois, sem markdown."""


def generate_copy(
    *,
    post,
    kb_summary: str,
    references: List[Dict[str, Any]] = None,
    copy_direction: Dict[str, Any] = None,
) -> Optional[Dict[str, Any]]:
    """Roda o copywriter agent. Retorna dict com:
        {'payload': <JSON do copy>, 'usage': <tokens/custo>, 'model': MODEL}
    Ou None em caso de falha.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[copywriter] ANTHROPIC_API_KEY ausente')
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning('[copywriter] anthropic SDK indisponivel')
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user_text = _build_user_text(
        post=post, kb_summary=kb_summary, references=references or [],
        copy_direction=copy_direction or {},
    )

    # System como LIST: introducao curta + skill (separadamente cacheaveis;
    # skill grande fica em cache de 1h).
    system_blocks = [
        {
            'type': 'text',
            'text': SYSTEM_INTRO,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
        {
            'type': 'text',
            'text': COPYWRITER_SKILL,
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
        logger.exception('[copywriter] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    payload = _parse_json(raw)
    if not payload:
        logger.error('[copywriter] parse JSON falhou. Raw: %s', raw[:400])
        return None

    usage = _extract_usage(resp, cache_ttl='1h')
    logger.info(
        '[copywriter] post=%s tokens=%d cost=$%s recommended=%s',
        post.id, usage.get('total_tokens', 0), usage.get('cost_usd', 0),
        payload.get('recommended_variant', '?'),
    )
    return {
        'payload': payload,
        'usage': usage,
        'model': MODEL,
    }


def _build_user_text(*, post, kb_summary: str,
                     references: List[Dict[str, Any]],
                     copy_direction: Dict[str, Any]) -> str:
    formato = post.post_format
    fmt_str = (
        f"{formato.aspect_ratio} ({formato.width or '?'}x{formato.height or '?'}px)"
        if formato else '?'
    )
    parts = [
        '== Briefing do post ==',
        f'Rede social: {post.social_network or "instagram"}',
        f'Formato: {fmt_str}',
        f'Tema/contexto original: {post.requested_theme or "(sem tema)"}',
        f'CTA solicitado: {"sim" if getattr(post, "cta_requested", True) else "nao"}',
    ]

    if copy_direction:
        parts.extend([
            '',
            '== BRIEF DO ESTRATEGISTA (copy_direction) — OBRIGATORIO ==',
            '(este e o brief de copy. obedeca. nao escolha framework diferente.)',
            f'  framework: {copy_direction.get("framework", "?")}',
            f'  angle: {copy_direction.get("angle", "?")}',
            f'  key_message: {copy_direction.get("key_message", "?")}',
            f'  cta_type: {copy_direction.get("cta_type", "?")}',
            f'  tone_notes: {copy_direction.get("tone_notes", "?")}',
        ])
    else:
        parts.extend([
            '',
            '== ATENCAO: sem copy_direction do strategist ==',
            '(modo legado — voce excepcionalmente decide framework sozinho)',
        ])

    parts.extend([
        '',
        '== Contexto da marca (KB) ==',
        kb_summary[:2000] if kb_summary else '(sem resumo da marca)',
    ])
    if references:
        parts.append('')
        parts.append('== Imagens anexadas (contexto pro design_hints) ==')
        for i, ref in enumerate(references, 1):
            tipo = ref.get('tipo', 'desconhecido')
            parts.append(f'  Imagem {i}: tipo={tipo}')
    parts.extend([
        '',
        '== Tarefa ==',
        'Aplique o passo a passo do skill carregada no system prompt e produza',
        'o JSON do schema do Passo 5 com variants + design_hints + metrics.',
        'TODAS as variantes devem usar o framework do brief — variantes diferem',
        'em EXECUCAO (palavras, ritmo, hook concreto), nunca em framework.',
        'design_hints sao instrucoes formais para o designer — sejam especificas',
        'e acionaveis, considerando o formato e o image_style ja decidido.',
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
