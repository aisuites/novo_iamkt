"""
Mecanismo C — validador visual pós-Gemini.

Depois que o Gemini gera a cena (e antes do Pillow aplicar o texto), um
agente leve (Claude Sonnet 4.6) compara a cena gerada com o plano do designer
e responde: "essa imagem comporta o layout planejado?"

Se sim → segue para Pillow. Se não → pode disparar regeneração (decisão do
caller; este módulo só reporta o veredito).

Custo: ~$0.005-0.01 por validação. Vale o investimento porque evita aplicar
texto sobre rostos/produtos quando o Gemini não respeitou as zonas.
"""

import base64
import json
import logging
import os
import re
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 800


SYSTEM = """Você é um validador visual. Recebe uma imagem renderizada pelo
Gemini + o plano de layout que será aplicado por cima. Sua única tarefa:
decidir se a imagem comporta o layout planejado SEM CONFLITO.

Não revise design. Não proponha edits. Apenas valide compatibilidade física:
- As zonas onde o texto cairá têm fundo CALMO e ADEQUADO?
- As zonas de texto NÃO têm rosto, produto ou detalhe complexo embaixo?
- O sujeito principal está NA ZONA prevista pelo plano (não invadiu zona de texto)?

Retorne APENAS este JSON:
{
  "compatible": true | false,
  "confidence": "high" | "medium" | "low",
  "issues": ["lista breve de problemas concretos, se houver"],
  "recommendation": "proceed" | "regenerate"
}
"""


def validate_scene(*, png_bytes: bytes, wireframe_plan: Dict[str, Any],
                   canvas_w: int, canvas_h: int) -> Optional[Dict[str, Any]]:
    """Roda a validação. Retorna dict com {compatible, confidence, issues,
    recommendation, usage, model} ou None se falhou.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key or not png_bytes:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.b64encode(png_bytes).decode('ascii')
    summary = _build_layout_summary(wireframe_plan, canvas_w, canvas_h)

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {'type': 'base64', 'media_type': 'image/png', 'data': b64},
                    },
                    {'type': 'text', 'text': summary},
                ],
            }],
        )
    except Exception:
        logger.exception('[scene_validator] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    parsed = _parse_json(raw)
    if not parsed:
        logger.error('[scene_validator] parse JSON falhou. Raw: %s', raw[:200])
        return None

    usage = _extract_usage(resp)
    parsed['usage'] = usage
    parsed['model'] = MODEL
    logger.info(
        '[scene_validator] compatible=%s confidence=%s rec=%s cost=$%.4f',
        parsed.get('compatible'), parsed.get('confidence'),
        parsed.get('recommendation'), usage.get('cost_usd', 0),
    )
    return parsed


def _build_layout_summary(wireframe_plan: Dict[str, Any],
                          canvas_w: int, canvas_h: int) -> str:
    """Resumo curto das zonas planejadas para o validador checar."""
    elements = wireframe_plan.get('elements') or []
    lines = [
        f'Canvas: {canvas_w}x{canvas_h}px',
        '',
        'Plano de layout que será aplicado SOBRE a imagem mostrada acima:',
    ]
    for el in elements:
        et = (el.get('type') or '').lower()
        if et not in ('text', 'shape', 'logo', 'overlay'):
            continue  # imagem/background não vai por cima
        pos = el.get('position') or {}
        size = el.get('size') or {}
        eid = el.get('id', '?')
        lines.append(
            f'  - {eid} ({et}): x={pos.get("x_px",0)} y={pos.get("y_px",0)} '
            f'w={size.get("width_px","?")} h={size.get("height_px","?")}'
        )
    lines.extend([
        '',
        'A imagem do Gemini deve ter as zonas dos elementos TEXT/SHAPE/LOGO',
        'em áreas naturalmente calmas (sem rosto, produto ou detalhe sob elas).',
        'O sujeito principal pode estar visível em ÁREA SEPARADA do texto.',
        '',
        'Responda em JSON conforme o schema do system.',
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


def _extract_usage(resp) -> Dict[str, Any]:
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'total_tokens': in_tokens + out_tokens,
        'cost_usd': float(cost),
    }
