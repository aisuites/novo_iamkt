"""
Brand Layout Analyzer — usa Claude Sonnet 4.5 Vision para inferir spec de
layout (posicionamento de titulo, subtitulo, logo, CTA, alinhamento, peso
tipografico) a partir das imagens de referencia da KB.

Resultado e cacheado em KnowledgeBase.brand_layout_spec (so re-analisa
quando user adiciona/remove reference_images).

Custo: ~$0.01 por analise (1-2 references como imagens). Roda 1x por org.
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
MAX_REFS_TO_ANALYZE = 3   # economia: max 3 references por analise

SYSTEM_PROMPT = """Voce e um diretor de arte que avalia posts de redes sociais
para extrair PADROES DE LAYOUT que serao replicados em novas artes.

Analise as imagens anexadas (referencias visuais da marca) e retorne JSON
puro com um SPEC DE LAYOUT que captura como a marca posiciona elementos
textuais em suas artes.

REGRAS:
1. Observe TODAS as referencias e produza um spec COMUM que represente o
   padrao recorrente. Se houver inconsistencia, escolha o padrao majoritario.
2. Valores categoricos LIMITADOS — use APENAS os valores listados.
3. Numeros como porcentagem da altura do canvas (0-100).
4. Se uma feature nao aparece consistentemente, use o valor mais comum em
   posts de redes sociais para o tipo de marca.

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "title_position": "top-left|top-center|top-right|center-left|center|center-right|bottom-left|bottom-center|bottom-right",
  "title_size_pct": numero entre 4 e 12 (% da altura),
  "title_weight": "bold|extrabold|black|regular|medium",
  "title_color_hint": "auto_contrast|white|black|brand_primary|brand_secondary",
  "subtitle_offset": "below_title|separate_block",
  "subtitle_size_pct": numero entre 2 e 5,
  "subtitle_weight": "regular|light|medium",
  "logo_position": "top-left|top-center|top-right|bottom-left|bottom-center|bottom-right|none",
  "logo_size_pct": numero entre 6 e 20,
  "cta_style": "pill|underline|block|outline|none",
  "cta_position": "bottom-left|bottom-center|bottom-right|below_subtitle",
  "alignment": "left|center|right",
  "padding_pct": numero entre 3 e 10,
  "background_treatment": "none|gradient|color_block|dark_overlay|light_overlay",
  "design_rationale": "string curta descrevendo o padrao geral em portugues"
}

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def analyze_brand_layout_from_references(
    kb,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Analisa as reference_images da KB via Claude Vision e retorna spec de
    layout. Cacheia em kb.brand_layout_spec.

    Args:
        kb: KnowledgeBase
        force_refresh: ignora cache existente e re-analisa

    Retorna o dict do spec (mesmo schema que kb.brand_layout_spec).
    Se nao houver references, retorna None — chamador usa wireframe fallback.
    """
    if not kb:
        return None

    # Cache hit
    if not force_refresh:
        existing = kb.brand_layout_spec or {}
        if existing.get('analyzed_at') and existing.get('title_position'):
            logger.debug('[brand_layout] cache hit kb=%s', kb.id)
            return existing

    # Coleta refs aprovadas (ou todas se nao houver flag de aprovacao)
    try:
        refs_qs = kb.reference_images.all().order_by('-id')[:MAX_REFS_TO_ANALYZE]
        refs = list(refs_qs)
    except Exception:
        refs = []

    if not refs:
        logger.info('[brand_layout] kb=%s sem references, skip analise', kb.id)
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[brand_layout] ANTHROPIC_API_KEY ausente, skip')
        return None

    import anthropic
    from apps.core.services.s3_service import S3Service

    client = anthropic.Anthropic(api_key=api_key)

    # Baixa cada ref e converte pra base64
    content_blocks = []
    analyzed_ids = []
    for ref in refs:
        try:
            url = S3Service.generate_presigned_download_url(ref.s3_key, expires_in=3600)
            b64, mime = _download_to_base64(url)
            if not b64:
                continue
            content_blocks.append({
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': mime,
                    'data': b64,
                },
            })
            analyzed_ids.append(ref.id)
        except Exception as exc:
            logger.warning('[brand_layout] falha baixando ref %s: %s', ref.id, exc)

    if not content_blocks:
        logger.warning('[brand_layout] nenhuma ref baixada com sucesso')
        return None

    content_blocks.append({
        'type': 'text',
        'text': (
            f'Foram anexadas {len(content_blocks) - 0} imagens de referencia '
            f'da marca. Analise os padroes de layout textual e retorne o spec '
            f'em JSON conforme system prompt.'
        ),
    })

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {'role': 'user', 'content': content_blocks},
                {'role': 'assistant', 'content': '{'},
            ],
        )
    except Exception:
        logger.exception('[brand_layout] erro Claude Vision')
        return None

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    spec = _parse_json(raw)
    if not spec:
        logger.error('[brand_layout] parse JSON falhou. Raw: %s', raw[:300])
        return None

    # Anexa metadata e salva no cache
    from django.utils import timezone as dj_tz
    spec['analyzed_at'] = dj_tz.now().isoformat()
    spec['reference_image_ids'] = analyzed_ids
    spec['model'] = MODEL

    kb.brand_layout_spec = spec
    kb.save(update_fields=['brand_layout_spec'])

    logger.info(
        '[brand_layout] kb=%s spec gerado a partir de %d refs',
        kb.id, len(analyzed_ids),
    )
    return spec


def _download_to_base64(url: str):
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ct = resp.headers.get('Content-Type', 'image/png').split(';')[0].strip()
    except Exception as exc:
        logger.warning('Falha download ref: %s', exc)
        return None, 'image/png'
    # Detecta o tipo REAL pelos magic bytes. O Content-Type do S3 mente com
    # frequencia (ex.: JPEG salvo/servido como image/png); o Anthropic valida
    # os bytes contra o media_type declarado e rejeita com 400 se divergir.
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        ct = 'image/png'
    elif data[:3] == b'\xff\xd8\xff':
        ct = 'image/jpeg'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        ct = 'image/webp'
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        ct = 'image/gif'
    elif ct not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
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
