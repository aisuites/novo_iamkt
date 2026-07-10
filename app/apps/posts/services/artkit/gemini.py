"""
Caller Gemini dedicado ao single-shot da TODXS.

Envia o single_shot_prompt VERBATIM (sem o scaffolding/sanitizacao do
gemini_image_generator generico) + as imagens de marca (grafismo X, logo,
specimen). Reusa apenas os helpers de baixo nivel do gerador existente, sem
modifica-lo. Retorna a imagem + um debug sanitizado (sem base64) para trace.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal

from ..gemini_image_generator import _resolved_endpoint, _extract_image_from_response
from .trace import image_descriptor, strip_base64

logger = logging.getLogger(__name__)


def generate_singleshot(*, prompt_text: str, image_inputs: list, temperature: float = 0.4,
                        timeout: int = 180) -> dict:
    """
    image_inputs: lista de dicts {'b64', 'mime', 'role', 'name'}.
    Retorna {'png_bytes','mime_type','model','usage','cost_usd','debug'}.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY ausente no ambiente')

    parts = []
    img_descr = []
    for im in (image_inputs or []):
        if not im.get('b64'):
            continue
        parts.append({'inline_data': {'mime_type': im['mime'], 'data': im['b64']}})
        n_bytes = int(len(im['b64']) * 3 / 4)
        img_descr.append(image_descriptor(
            role=im.get('role', 'REF'), name=im.get('name', ''),
            mime=im['mime'], n_bytes=n_bytes,
        ))
    parts.append({'text': prompt_text})

    payload = {
        'contents': [{'parts': parts}],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
            'temperature': temperature,
        },
    }
    model_used, endpoint = _resolved_endpoint()

    # Trace do request: imagens como descritor (sem base64) + prompt completo.
    debug_request = {
        'model': model_used,
        'images': img_descr,
        'prompt': prompt_text,
        'generationConfig': payload['generationConfig'],
    }

    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        endpoint, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Gemini retornou HTTP {exc.code}: {err_body[:500]}')

    response_json = json.loads(data.decode('utf-8'))
    png_bytes, mime_type = _extract_image_from_response(response_json)
    if not png_bytes:
        raise RuntimeError(
            f'Gemini nao retornou imagem. Response: {json.dumps(response_json)[:400]}'
        )

    usage_meta = response_json.get('usageMetadata', {}) or {}
    input_tokens = int(usage_meta.get('promptTokenCount', 0) or 0)
    images_out = max(1, len(response_json.get('candidates', []) or []))
    input_cost = Decimal(input_tokens) * Decimal('0.10') / Decimal('1000000')
    output_cost = Decimal(images_out) * Decimal('0.04')
    cost = float(input_cost + output_cost)

    return {
        'png_bytes': png_bytes,
        'mime_type': mime_type or 'image/png',
        'model': model_used,
        'usage': {'input_tokens': input_tokens, 'output_tokens': 0, 'cost_usd': cost},
        'cost_usd': cost,
        'debug': {'request': debug_request, 'response': strip_base64(response_json)},
    }
