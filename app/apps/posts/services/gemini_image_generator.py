"""
Gerador de imagem para posts usando Gemini 3 Pro Image.

Substitui o workflow N8N 'gerarimagem-appiamkt'. Replica o prompt textual
sofisticado do node 'Code in JavaScript4' (com regras por tipo de imagem:
logo, referencia_post, etc.) + parts multimodais inline_data.

Pricing Gemini 3 Pro Image: ~$0.03-0.05 por imagem gerada.
"""

import base64
import json
import logging
import os
import urllib.request
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

GEMINI_MODEL = 'gemini-3-pro-image-preview'
GEMINI_ENDPOINT = (
    f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
)

# Override opcional do modelo via env (ex: para testar Nano Banana sem mudar
# codigo). Settings: GEMINI_IMAGE_MODEL=gemini-2.5-flash-image-preview
def _resolved_endpoint() -> tuple:
    """Retorna (model, endpoint) respeitando override de env."""
    model = os.environ.get('GEMINI_IMAGE_MODEL', GEMINI_MODEL)
    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent'
    )
    return model, endpoint

# Custo estimado (valor pode ser ajustado conforme pricing oficial).
COST_PER_IMAGE_USD = Decimal('0.04')

# Regras de uso por tipo de imagem — copiadas do node N8N "Code in JavaScript4".
USAGE_RULES_BY_TYPE = {
    'logo': 'aplicar SEM alteracao, sem distorcer, respeitando proporcao.',
    'logotipo': 'aplicar SEM alteracao, sem distorcer, respeitando proporcao.',
    'referencia': (
        'usar apenas como inspiracao de estilo, presenca de pessoas, FOTOGRAFIA, '
        'ILUMINACAO, ENQUADRAMENTO, USO DE ELEMENTOS GRAFICOS E SE TORNAR KEY '
        'VISUAL (nao copiar textos).'
    ),
    'referencia_post': (
        'usar apenas como inspiracao de estilo, presenca de pessoas, FOTOGRAFIA, '
        'ILUMINACAO, ENQUADRAMENTO, USO DE ELEMENTOS GRAFICOS E SE TORNAR KEY '
        'VISUAL (nao copiar textos).'
    ),
    'referencia_kb': (
        'usar apenas como inspiracao de estilo, presenca de pessoas, FOTOGRAFIA, '
        'ILUMINACAO, ENQUADRAMENTO, USO DE ELEMENTOS GRAFICOS E SE TORNAR KEY '
        'VISUAL (nao copiar textos).'
    ),
    'icone': 'usar como elemento grafico/icone, mantendo legibilidade.',
    'post_image': 'usar como referencia de imagens que devem aparecer na imagem final.',
    'fundo': 'usar como referencia de textura/fundo (sem competir com o texto).',
    'background': 'usar como referencia de textura/fundo (sem competir com o texto).',
    'produto': 'aplicar FIELMENTE ao produto original — sem reinterpretar formas, cores ou logos.',
}

# Prioridade de ordenacao das imagens no prompt — logos e produtos primeiro
# para garantir que aparecam destacados no contexto multimodal.
TYPE_PRIORITY = {
    'logotipo': 0, 'logo': 0,
    'produto': 1,
    'pessoa': 2, 'cenario': 3, 'fundo': 4, 'background': 4,
    'icone': 5,
    'referencia': 10, 'referencia_post': 10, 'referencia_kb': 10, 'referencia_estilo': 10,
}


def generate_post_image(
    *,
    post,
    references: List[Dict[str, Any]],
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    publico_alvo: str,
    marketing_input_summary: str,
    formato_px: str,
    product_analyses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Gera UMA imagem final para o post via Gemini 3 Pro Image, usando
    tecnicas de subject preservation pesquisadas:

      1. Imagens BEFORE text no array `contents` (modelo "ancora" visual)
      2. Frame como EDIT, nao generate
      3. Nome unico inventado pro produto ("THIS_PRODUCT")
      4. Lista KEEP_UNCHANGED vs CHANGE/ADD explicita
      5. Bracket-naming + negative-naming (do Claude Vision)
      6. Reference + Relationship + Scenario framework
      7. temperature=0.5

    references: lista de dicts {url, tipo} (urls presigned do S3)
    product_analyses: lista de dicts vindos do Claude Vision com
        {product_name, distinctive_features, keep_unchanged_list, ...}
        — um por imagem com tipo='produto'. Ordem importa.

    Retorna:
        {
          'png_bytes': bytes,
          'mime_type': 'image/png' | 'image/jpeg',
          'cost_usd': float,
          'model': str,
          'usage': dict (raw),
        }
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY ausente no ambiente')

    # 1. Baixa cada referencia, converte para base64
    image_parts: List[Dict[str, Any]] = []
    sorted_refs = _sort_references(references)
    for ref in sorted_refs:
        url = ref.get('url')
        if not url:
            continue
        b64, mime = _download_to_base64(url)
        if b64:
            image_parts.append({
                'inline_data': {'mime_type': mime, 'data': b64}
            })

    # 2. Monta texto do prompt — inclui analises do produto se houver
    prompt_text = _build_prompt_text(
        post=post,
        sorted_refs=sorted_refs,
        paleta=paleta,
        tipografia=tipografia,
        publico_alvo=publico_alvo,
        marketing_input_summary=marketing_input_summary,
        formato_px=formato_px,
        product_analyses=product_analyses or [],
    )

    # 3. Monta payload Gemini — IMAGENS PRIMEIRO, depois texto (subject anchor)
    payload = {
        'contents': [{
            'parts': image_parts + [{'text': prompt_text}],
        }],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
            'temperature': 0.5,
        },
    }

    # 4. Chamada HTTP
    model_used, endpoint = _resolved_endpoint()
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': api_key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Gemini retornou HTTP {exc.code}: {err_body[:500]}')

    response_json = json.loads(data.decode('utf-8'))

    # 5. Extrai imagem base64 dos candidates
    png_bytes, mime_type = _extract_image_from_response(response_json)
    if not png_bytes:
        raise RuntimeError(
            f'Gemini nao retornou imagem. Response: {json.dumps(response_json)[:500]}'
        )

    return {
        'png_bytes': png_bytes,
        'mime_type': mime_type,
        'cost_usd': float(COST_PER_IMAGE_USD),
        'model': model_used,
        'usage': response_json.get('usageMetadata', {}),
        'prompt_text': prompt_text,
    }


# ---- Helpers ---------------------------------------------------------------


def _sort_references(references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordena por prioridade (logos primeiro)."""
    def key(ref):
        tipo = str(ref.get('tipo', '')).lower()
        return TYPE_PRIORITY.get(tipo, 50)
    return sorted(references, key=key)


def _download_to_base64(url: str) -> Tuple[Optional[str], str]:
    """Baixa imagem de URL (presigned) e retorna (base64_str, mime_type)."""
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'Mozilla/5.0 IAMKT GeminiClient'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type', 'image/png').split(';')[0].strip()
    except Exception as exc:
        logger.warning('Falha ao baixar referencia %s: %s', url[:100], exc)
        return None, 'image/png'

    if content_type not in ('image/png', 'image/jpeg', 'image/webp'):
        content_type = 'image/png'
    return base64.b64encode(data).decode('ascii'), content_type


def _build_prompt_text(
    *,
    post,
    sorted_refs: List[Dict[str, Any]],
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    publico_alvo: str,
    marketing_input_summary: str,
    formato_px: str,
    product_analyses: List[Dict[str, Any]],
) -> str:
    """
    Prompt SIMPLES — confia na dereferenciacao por imagem ("o produto da
    imagem N anexada"). Sem nomes, sem KEEP_UNCHANGED extenso, sem
    bracket/negative naming. Inspirado em prompts curtos de catalogo
    e lifestyle que funcionam bem com Gemini.

    product_analyses fica como argumento mas e ignorado nesta versao
    (mantido para compatibilidade — pode ser util em futuras iteracoes).
    """
    # Mapeia tipo -> linha descritiva curta
    refs_lines: List[Tuple[int, str]] = []
    for i, ref in enumerate(sorted_refs, 1):
        tipo = str(ref.get('tipo', 'desconhecido')).lower()
        if 'logo' in tipo:
            refs_lines.append((i, f'IMAGEM {i}: logotipo da marca — aplicar exatamente como aparece (sem distorcer, sem mudar cor)'))
        elif 'produto' in tipo:
            refs_lines.append((i, f'IMAGEM {i}: o produto principal — use exatamente como aparece (mesmas cores, mesmo formato, mesmos detalhes)'))
        elif 'pessoa' in tipo:
            refs_lines.append((i, f'IMAGEM {i}: pessoa — usar exatamente como aparece (mesmo rosto, mesma aparencia)'))
        elif 'fundo' in tipo or 'background' in tipo:
            refs_lines.append((i, f'IMAGEM {i}: textura/fundo de referencia'))
        elif 'icone' in tipo:
            refs_lines.append((i, f'IMAGEM {i}: elemento grafico/icone'))
        else:
            refs_lines.append((i, f'IMAGEM {i}: referencia visual (inspiracao de estilo, fotografia, iluminacao — nao copiar textos)'))

    attachments_text = '\n'.join(line for _, line in refs_lines)

    parts = [
        '# TAREFA',
        'Crie uma fotografia profissional para um post de rede social.',
        '',
        '# REFERENCIAS VISUAIS (anexadas ACIMA deste texto, na ordem)',
        attachments_text,
        '',
        '# CENA',
        post.image_prompt or '(propor um cenario adequado ao briefing)',
        '',
        '# TEXTO QUE DEVE APARECER NA ARTE',
        f'- Titulo: {post.title or ""}',
        f'- Subtitulo: {post.subtitle or ""}',
    ]
    if post.cta:
        parts.append(f'- CTA: {post.cta}')

    parts.extend([
        '',
        '# BRIEFING',
        f'- Rede social: {post.social_network or "instagram"}',
        f'- Formato (px): {formato_px}',
        f'- Publico-alvo: {publico_alvo or "geral"}',
        '',
        '# DIRETRIZES',
        f'- Paleta da marca para textos: {json.dumps(paleta, ensure_ascii=False)}',
        f'- Tipografia: {json.dumps(tipografia, ensure_ascii=False)}',
        '- Aplique paleta e tipografia somente nos textos do post — nao nos elementos anexados.',
        '- Nao copie textos visiveis nas imagens anexadas (sao referencia visual).',
        '- Verifique presenca de pessoas nas referencias; se nao houver, nao adicione.',
        '',
        '# QUALIDADE',
        '- Fotorrealista, sem artefatos, sem textos cortados, sem marca dagua.',
        '- Nao gerar mockup — esta e a arte final.',
        '- Legibilidade alta para celular.',
    ])
    parts.extend([
        '',
        'Gere a arte final agora.',
    ])
    return '\n'.join(parts)


def _infer_rule(tipo: str) -> str:
    """Fallback de regra quando o tipo nao esta no map."""
    if 'logo' in tipo:
        return USAGE_RULES_BY_TYPE['logo']
    if 'refer' in tipo:
        return USAGE_RULES_BY_TYPE['referencia']
    if 'icon' in tipo:
        return USAGE_RULES_BY_TYPE['icone']
    if 'fundo' in tipo or 'background' in tipo:
        return USAGE_RULES_BY_TYPE['fundo']
    if 'produto' in tipo:
        return USAGE_RULES_BY_TYPE['produto']
    return 'usar como referencia conforme o tipo indicado.'


def _extract_image_from_response(response: Dict[str, Any]) -> Tuple[Optional[bytes], str]:
    """Encontra a primeira parte com inline_data nos candidates."""
    candidates = response.get('candidates') or []
    if not candidates:
        return None, 'image/png'

    parts = candidates[0].get('content', {}).get('parts', [])
    for p in parts:
        inline = p.get('inlineData') or p.get('inline_data')
        if inline and inline.get('data'):
            mime = inline.get('mimeType') or inline.get('mime_type') or 'image/png'
            return base64.b64decode(inline['data']), mime
    return None, 'image/png'
