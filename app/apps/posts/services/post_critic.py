"""
Designer-critic skill — segunda passada com olhos novos.

Recebe a imagem ja renderizada (preview), o layout_document atual + contexto
do orquestrador, e emite edits cirurgicos pra revisar o layout, ou aprova.

Filosofia (alinhada com o resto da arquitetura):
- Olhos NOVOS: pelo prompt, age como designer revisando trabalho de outro.
- Sem checklist. Olho de designer.
- Edits cirurgicos por campo (target_role|target_index + field + new_value).
- Loop iterativo (ate 3) gerenciado pelo task.

Custo: ~$0.03-0.05 por iteracao (image + ~1500 tokens out).
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
MAX_TOKENS = 3000

# Carrega o conhecimento do critico: base compartilhada (shared_skill/) +
# specifica do critico (critic_skill/). Concatena em UM bloco que vira prefixo
# cacheable no system prompt (1h TTL — escrita 1x/hora, leitura 90% off depois).
_SERVICES_DIR = Path(__file__).parent
_SHARED_DIR = _SERVICES_DIR / 'shared_skill'
_CRITIC_DIR = _SERVICES_DIR / 'critic_skill'


def _load_skill_for_critic() -> str:
    """Skill do critico: shared/* + critic SKILL.md + critic payload-examples."""
    parts = []
    files = [
        # Base compartilhada (carregada por designer + critico)
        _SHARED_DIR / 'formats-and-safe-zones.md',
        _SHARED_DIR / 'typography-scale.md',
        _SHARED_DIR / 'contrast-rules.md',
        _SHARED_DIR / 'design-principles.md',
        # Especifica do critico
        _CRITIC_DIR / 'SKILL.md',
        _CRITIC_DIR / 'references' / 'payload-examples.md',
    ]
    for fp in files:
        try:
            parts.append(f'\n\n=== ARQUIVO: {fp.name} ===\n\n')
            parts.append(fp.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[critic] skill file faltando: %s', fp)
    return ''.join(parts)


DESIGNER_SKILL = _load_skill_for_critic()
if not DESIGNER_SKILL:
    logger.warning('[critic] DESIGNER_SKILL vazio — pastas shared_skill/critic_skill nao encontradas')


CRITIC_SYSTEM_PROMPT = """Voce e designer senior revisando esta arte JA
RENDERIZADA com olhos novos. NAO foi voce que fez — voce esta vendo pela
primeira vez.

Voce tem acesso a um REPERTORIO DE SKILL (abaixo) — principios + sintomas +
edits tipicos. Use como referencia ativa, NAO como checklist mecanico.
Aplique olho de senior.

Quando propor edits, seja CIRURGICO: mude o minimo necessario, um campo
de cada vez. Cada edit tem motivo claro. Se um elemento esta OK, nao
toque nele.

=================================================================
""" + DESIGNER_SKILL + """
=================================================================


FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "approved": true | false,
  "rationale": "<sua leitura como designer, em prosa, max 3-4 frases>",
  "edits": [
    {
      "target_role": "<role do elemento: titulo|subtitulo|cta|logo|grafismo>" | null,
      "target_index": <int — indice do elemento na lista, alternativa ao role> | null,
      "field": "<nome do campo: y_pct|x_pct|width_pct|height_pct|font_size_pct|color|forma|raio_pct|weight|align|content>",
      "new_value": <valor novo (numero, string ou hex)>,
      "reason": "<razao curta em 1 frase>"
    }
  ]
}

Use target_role quando o role e unico (titulo, subtitulo, cta, logo).
Use target_index quando ha multiplos elementos do mesmo role (varios grafismos).
Se approved=true, edits pode ser [] ou omitido.
Se approved=false, retorne pelo menos 1 edit.
NUNCA retorne os dois (approved=true E edits com itens).

Retorne APENAS o JSON. Sem texto antes ou depois.
"""


def critique(
    *,
    post,
    orchestration: Dict[str, Any],
    layout_document: Dict[str, Any],
    png_preview_bytes: bytes,
    paleta: List[Dict[str, Any]],
    iteration: int = 1,
    max_iterations: int = 3,
) -> Optional[Dict[str, Any]]:
    """Chama o designer-critic sobre a imagem renderizada.

    Returns dict {'approved', 'rationale', 'edits', 'usage'} ou None se
    falhou. O caller aplica edits via apply_edits().
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[critic] ANTHROPIC_API_KEY ausente')
        return None
    if not png_preview_bytes:
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning('[critic] anthropic SDK indisponivel')
        return None

    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.b64encode(png_preview_bytes).decode('ascii')
    user_text = _build_critic_text(
        post=post, orchestration=orchestration,
        layout_document=layout_document, paleta=paleta,
        iteration=iteration, max_iterations=max_iterations,
    )

    # System como LIST com cache_control 1h. A skill (estatica) eh cacheada:
    # 1a chamada da hora paga write (+100%), proximas 90% off.
    system_blocks = [
        {
            'type': 'text',
            'text': CRITIC_SYSTEM_PROMPT,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
    ]
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/png',
                            'data': b64,
                        },
                    },
                    {'type': 'text', 'text': user_text},
                ],
            }],
        )
    except Exception:
        logger.exception('[critic] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    parsed = _parse_json(raw)
    if not parsed:
        logger.error('[critic] parse JSON falhou. Raw: %s', raw[:300])
        return None

    usage = _extract_usage(resp, cache_ttl='1h')
    parsed['usage'] = usage
    parsed['model'] = MODEL
    logger.info(
        '[critic] iter=%d approved=%s edits=%d tokens=%d cost=$%s',
        iteration, parsed.get('approved'), len(parsed.get('edits') or []),
        usage.get('total_tokens', 0), usage.get('cost_usd', 0),
    )
    return parsed


def _build_critic_text(*, post, orchestration, layout_document, paleta,
                       iteration, max_iterations) -> str:
    """Texto de contexto que vai junto da imagem renderizada."""
    paleta_str = ', '.join(
        f"{(c.get('hex') or '').strip()}"
        for c in (paleta or []) if c.get('hex')
    ) or '(sem paleta)'
    elements = (layout_document or {}).get('elements') or []
    lines = [
        '== Briefing ==',
        f'Titulo: {post.title or "(sem)"}',
        f'Subtitulo: {post.subtitle or "(sem)"}',
        f'CTA: {post.cta or "(sem)"}',
        f'Formato: {post.post_format.aspect_ratio if post.post_format else "?"}',
        '',
        f'== Paleta da marca == {paleta_str}',
        '',
        '== Plano original do designer (1a passada) ==',
        f'Wireframe critique: {(orchestration or {}).get("wireframe_critique", "")[:400]}',
        f'Rules: {(orchestration or {}).get("rules", "")[:400]}',
        '',
        '== Elementos atuais (use target_index ou target_role nos edits) ==',
    ]
    for i, el in enumerate(elements):
        role = el.get('role') or '?'
        if role == 'grafismo':
            lines.append(
                f"  [{i}] grafismo forma={el.get('forma')} cor={el.get('cor')} "
                f"x={el.get('x_pct')} y={el.get('y_pct')} "
                f"w={el.get('width_pct')} h={el.get('height_pct')}"
                + (f" cantos={el.get('cantos')}" if el.get('cantos') else "")
            )
        else:
            lines.append(
                f"  [{i}] {role} x={el.get('x_pct')} y={el.get('y_pct')} "
                f"w={el.get('width_pct')} h={el.get('height_pct')} "
                f"fs={el.get('font_size_pct')} color={el.get('color')} "
                f"align={el.get('align')} "
                f"content={(el.get('content') or '')[:60]!r}"
            )
    lines.extend([
        '',
        f'== Iteracao: {iteration} de ate {max_iterations} ==',
        '(Aprove se ja esta bom. Cada iteracao adicional custa tokens. '
        'Nao revise por revisar.)',
        '',
        'Olhe a imagem renderizada acima. Aprove ou proponha edits cirurgicos.',
    ])
    return '\n'.join(lines)


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
    """Extrai tokens/custos incluindo CACHE (creation + read).

    cache_ttl: '5m' (write +25%) ou '1h' (write +100%) — define o multiplicador
    de cobranca de cache_creation_input_tokens.
    """
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    # Sonnet pricing: $3/M input, $15/M output
    # Cache: write 5m = +25% ($3.75/M); write 1h = +100% ($6/M)
    # Cache read: -90% ($0.30/M)
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
