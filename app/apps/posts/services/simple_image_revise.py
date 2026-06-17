"""
Pipeline SIMPLES (v2) — ALTERACAO de IMAGEM (image-to-image), local.

Etapa A: gpt-4o-mini (VISAO) recebe a imagem final + o pedido (geralmente vago)
do usuario e escreve um PROMPT DE EDICAO claro, especifico e acionavel.
Etapa B: Gemini recebe a MESMA imagem final + esse prompt e devolve a nova imagem.

Razao da Etapa A: o usuario costuma explicar mal; o LLM traduz o pedido num
prompt bom, melhorando muito o resultado da edicao. Custo barato (gpt-4o-mini).
"""

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

from apps.posts.services.gemini_image_generator import (
    _resolved_endpoint,
    _extract_image_from_response,
)

logger = logging.getLogger(__name__)

_PROMPT_MODEL = 'gpt-4o-mini'
_COST_IN_PER_1M = Decimal('0.15')   # USD / 1M tokens input (gpt-4o-mini)
_COST_OUT_PER_1M = Decimal('0.60')  # USD / 1M tokens output (gpt-4o-mini)

_SYSTEM_PROMPT = """Voce escreve PROMPTS DE EDICAO DE IMAGEM para um modelo de \
imagem (Gemini). Recebe a IMAGEM ATUAL do post (a arte final, com texto e logo) e \
um PEDIDO do usuario — que costuma ser vago. Sua tarefa: transformar o pedido num \
prompt CLARO, ESPECIFICO e ACIONAVEL para EDITAR a imagem atual.

Regras:
- Aplique SOMENTE a mudanca pedida. Preserve tudo o que NAO foi mencionado:
  layout, enquadramento, identidade da marca, cores, grafismos, logo e os TEXTOS
  exatos (titulo/subtitulo/cta) como estao na imagem — nao reescreva nem traduza
  textos.
- Seja concreto: o QUE muda, ONDE e COMO. Sem ambiguidade.
- Responda em PT-BR, APENAS com o prompt de edicao (sem explicacoes, sem markdown).
"""

# Reforco enviado ao Gemini junto com o prompt da Etapa A.
_GEMINI_EDIT_WRAPPER = (
    'Edite a IMAGEM ANEXADA aplicando a alteracao abaixo. Preserve TODO o resto '
    'exatamente como esta (layout, enquadramento, cores, grafismos, logo e os '
    'TEXTOS exatos — NAO reescreva nem traduza textos). Alteracao pedida:\n'
)


def generate_edit_prompt(image_bytes: bytes, user_message: str) -> dict:
    """Etapa A: gpt-4o-mini (visao) -> prompt de edicao.
    Retorna {prompt, usage, model}."""
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY ausente')

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    b64 = base64.b64encode(image_bytes).decode('ascii')
    resp = client.chat.completions.create(
        model=_PROMPT_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': [
                {'type': 'text',
                 'text': 'PEDIDO DO USUARIO: ' + (user_message or '').strip()},
                {'type': 'image_url',
                 'image_url': {'url': f'data:image/png;base64,{b64}'}},
            ]},
        ],
    )
    prompt = (resp.choices[0].message.content or '').strip()
    if not prompt:
        raise RuntimeError('gpt-4o-mini nao devolveu prompt de edicao')

    u = getattr(resp, 'usage', None)
    in_tok = int(getattr(u, 'prompt_tokens', 0) or 0)
    out_tok = int(getattr(u, 'completion_tokens', 0) or 0)
    cost = (
        (Decimal(in_tok) / Decimal(1_000_000)) * _COST_IN_PER_1M
        + (Decimal(out_tok) / Decimal(1_000_000)) * _COST_OUT_PER_1M
    )
    usage = {
        'input_tokens': in_tok,
        'output_tokens': out_tok,
        'total_tokens': in_tok + out_tok,
        'cost_usd': float(round(cost, 6)),
    }
    logger.info('[posts.simple] edit_prompt gpt-4o-mini in=%s out=%s cost=$%s',
                in_tok, out_tok, usage['cost_usd'])
    return {'prompt': prompt, 'usage': usage, 'model': _PROMPT_MODEL}


def edit_image_with_gemini(image_bytes: bytes, edit_prompt: str,
                           temperature: float = 0.4) -> dict:
    """Etapa B: Gemini image-to-image. Imagem final + prompt de edicao -> nova
    imagem. Retorna {png_bytes, model, usage}."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY ausente')

    parts = [
        {'inlineData': {'mimeType': 'image/png',
                        'data': base64.b64encode(image_bytes).decode('ascii')}},
        {'text': _GEMINI_EDIT_WRAPPER + (edit_prompt or '').strip()},
    ]
    payload = {
        'contents': [{'parts': parts}],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
            'temperature': temperature,
        },
    }

    model_used, endpoint = _resolved_endpoint()
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        err = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Gemini (edit image) HTTP {exc.code}: {err[:500]}')

    response_json = json.loads(data.decode('utf-8'))
    png_bytes, _mime = _extract_image_from_response(response_json)
    if not png_bytes:
        raise RuntimeError(
            f'Gemini nao retornou imagem (edit): {json.dumps(response_json)[:400]}'
        )

    usage_meta = response_json.get('usageMetadata', {}) or {}
    in_tok = int(usage_meta.get('promptTokenCount', 0) or 0)
    cost = float(Decimal(in_tok) * Decimal('0.10') / Decimal(1_000_000) + Decimal('0.04'))
    logger.info('[posts.simple] edit_image gemini=%s in=%s cost=$%s',
                model_used, in_tok, cost)
    return {
        'png_bytes': png_bytes,
        'model': model_used,
        'usage': {'input_tokens': in_tok, 'output_tokens': 0,
                  'total_tokens': in_tok, 'cost_usd': cost},
    }
