"""
KB Reference Translator — agente Claude Sonnet 4.5 multimodal que analisa
imagens de referencia da KB + o usage_description que o user preencheu,
e EXTRAI direcionamento textual para o Gemini.

Substitui o padrao antigo de enviar imagens da KB como inline_data ao
Gemini (que tendia a diluir foco entre 5+ imagens). Em vez disso, refs
KB viram BLOCOS DE TEXTO no prompt — directives de fotografia, layout,
mood, cores etc.

Categorias decididas LIVREMENTE pelo Claude (sem mapping rigido de
palavras-chave). Mais flexivel: o user pode dizer qualquer coisa
("usar a luz desse jeito", "essa textura como fundo") e Claude decide
qual categoria semantica usar.

Uploads do post (produto, pessoa, etc) continuam indo como image_parts
ao Gemini com alta fidelidade. Logo continua como image_parts em modo
inline, mas e DESENHADO via Pillow em modo pillow.

Custo: ~$0.015-0.025 por chamada (1-3 imagens KB + ~600 tokens out).
Cache no Post.local_pipeline_context.kb_refs_translations (hash dos
inputs evita reanalise se nada mudou).
"""

import base64
import hashlib
import json
import logging
import os
import re
import urllib.request
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-5'
MAX_TOKENS = 1500


SYSTEM_PROMPT = """Voce e um diretor de arte experiente. Sua tarefa: receber
imagens de referencia da marca + o que o usuario disse sobre como usa-las,
e EXTRAIR direcionamento textual concreto para um gerador de imagem.

POR QUE ESSA EXTRACAO E IMPORTANTE:
Quando enviamos muitas imagens de referencia ao gerador de imagem, ele se
distrai e ignora as imagens criticas (produto, pessoa). Entao seu papel e
PEGAR a essencia visual da imagem + intencao do user e CONDENSAR em
instrucoes textuais. O gerador recebe SO essas instrucoes, nao a imagem.

PARA CADA IMAGEM, PRODUZA:

1. category: nome semantico curto (em ingles, lowercase com underscore)
   que descreve QUAL ASPECTO da imagem voce esta extraindo.
   Decida LIVREMENTE baseado na imagem + usage_description. Exemplos:
     - photography_lighting (estilo de foto, luz, mood)
     - color_palette (paleta especifica de cores)
     - layout_composition (posicionamento de elementos, areas de respiro)
     - typography_style (estilo de tipografia visivel)
     - texture_background (textura ou padrao de fundo)
     - people_characteristics (descricao de pessoas — idade, estilo, atitude)
     - product_packaging (estilo de produto/embalagem)
     - mood_atmosphere (atmosfera geral, sensacao)
     - props_styling (elementos secundarios, props, styling)
   Se nada se encaixa, invente uma categoria descritiva.

2. directives: 2-5 frases curtas, em PORTUGUES, que descrevem CONCRETAMENTE
   o que extrair da imagem.
   Seja ESPECIFICO E ACIONAVEL:
     - "Iluminacao natural quente vinda da janela lateral esquerda,
        sombras suaves e difusas, golden hour"
     - "Paleta dominante: bege quente (#D4B896), branco quebrado (#F5F1EA),
        verde sage (#A8B89A) como acento"
     - "Pessoas adultas 30-45 anos, expressao serena, look profissional
        casual, etnia diversa"
   EVITE generico: "estilo bonito", "boa iluminacao", "cores agradaveis".

3. Use sempre o usage_description do user como GUIA do que extrair. Se
   ele disse "use a iluminacao", foque em iluminacao. Se disse "use o
   layout", foque em posicionamento. Se ele foi vago, decida pelo que
   for mais util pra reproducao em outra cena.

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "translations": [
    {
      "ref_index": 1,
      "category": "photography_lighting",
      "directives": "Iluminacao natural quente vinda da janela lateral..."
    },
    ...
  ]
}

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def translate_kb_references(
    kb_refs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Analisa as imagens KB selecionadas + usage_description de cada e produz
    direcionamento textual.

    kb_refs: lista de dicts {url, usage_description, id (opcional)}

    Retorna:
      {
        'translations': [{'ref_index', 'category', 'directives'}],
        'usage': {input_tokens, output_tokens, cost_usd},
        'model': str,
        'input_hash': str  # para cache hit/miss
      }
    Ou None se falhar ou nao houver refs.
    """
    if not kb_refs:
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[kb_translator] ANTHROPIC_API_KEY ausente — skip')
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Monta content multimodal
    content: List[Dict[str, Any]] = []
    meta_lines = []
    for i, ref in enumerate(kb_refs, 1):
        url = ref.get('url')
        usage_desc = (ref.get('usage_description') or '').strip() or '(nao informado)'
        meta_lines.append(f'Imagem {i}: usage_description do user: "{usage_desc}"')
        if not url:
            continue
        b64, mime = _download_to_base64(url)
        if b64:
            content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': mime, 'data': b64},
            })

    user_text = (
        '\n'.join(meta_lines)
        + '\n\nAnalise cada imagem ACIMA e produza o JSON com translations '
          'conforme system prompt. Decida livremente a categoria conforme o '
          'usage_description e o que voce ve em cada imagem.'
    )
    content.append({'type': 'text', 'text': user_text})

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {'role': 'user', 'content': content},
                {'role': 'assistant', 'content': '{'},
            ],
        )
    except Exception:
        logger.exception('[kb_translator] erro Claude')
        return None

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    parsed = _parse_json(raw)
    if not parsed:
        logger.error('[kb_translator] parse JSON falhou. Raw: %s', raw[:300])
        return None

    translations = parsed.get('translations') or []

    # Anexa id da kb_reference original em cada translation (caso o user
    # consulte qual veio de qual)
    for i, t in enumerate(translations):
        idx = t.get('ref_index')
        if idx and 1 <= idx <= len(kb_refs):
            src = kb_refs[idx - 1]
            t['kb_reference_id'] = src.get('id')
            t['usage_description_user'] = src.get('usage_description', '')

    usage = _extract_usage(resp)
    logger.info(
        '[kb_translator] %d refs analisadas | %d translations | cost=$%s',
        len(kb_refs), len(translations), usage.get('cost_usd', 0),
    )

    return {
        'translations': translations,
        'usage': usage,
        'model': MODEL,
        'input_hash': _hash_inputs(kb_refs),
    }


def _hash_inputs(kb_refs: List[Dict[str, Any]]) -> str:
    """
    Hash dos inputs para cache: muda se ids OU descricoes mudarem.
    Permite skip da reanalise quando o user nao mexe nas refs.
    """
    payload = sorted([
        f'{r.get("id", "")}:{r.get("usage_description", "")}'
        for r in kb_refs
    ])
    return hashlib.sha1('|'.join(payload).encode('utf-8')).hexdigest()[:16]


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
