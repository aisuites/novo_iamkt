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

# Prioridade de ordenacao das imagens no prompt — logos primeiro.
TYPE_PRIORITY = {
    'logotipo': 0, 'logo': 0,
    'referencia': 10, 'referencia_post': 10, 'referencia_kb': 10,
    'produto': 5,
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
) -> Dict[str, Any]:
    """
    Gera UMA imagem final para o post via Gemini 3 Pro Image.

    references: lista de dicts {url, tipo} (urls presigned do S3)

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

    # 2. Monta texto do prompt (replica logica do node N8N "Code in JavaScript4")
    prompt_text = _build_prompt_text(
        post=post,
        sorted_refs=sorted_refs,
        paleta=paleta,
        tipografia=tipografia,
        publico_alvo=publico_alvo,
        marketing_input_summary=marketing_input_summary,
        formato_px=formato_px,
    )

    # 3. Monta payload Gemini
    payload = {
        'contents': [{
            'parts': [{'text': prompt_text}] + image_parts,
        }],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
        },
    }

    # 4. Chamada HTTP
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        GEMINI_ENDPOINT,
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
        'model': GEMINI_MODEL,
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
) -> str:
    """Reproduz o prompt textual do N8N Code in JavaScript4 (gerarimagem)."""
    # Conta tipos
    counts: Dict[str, int] = {}
    for ref in sorted_refs:
        t = str(ref.get('tipo', 'desconhecido')).lower()
        counts[t] = counts.get(t, 0) + 1

    running: Dict[str, int] = {}

    attachments_lines = []
    if sorted_refs:
        attachments_lines.append('\n\n### IMAGENS ANEXADAS (na ordem exata)')
        for i, ref in enumerate(sorted_refs, 1):
            tipo = str(ref.get('tipo', 'desconhecido')).lower()
            running[tipo] = running.get(tipo, 0) + 1
            label = tipo.replace('_', ' ').replace('-', ' ').upper()
            n = running[tipo]
            total = counts[tipo]
            rule = USAGE_RULES_BY_TYPE.get(tipo) or _infer_rule(tipo)
            counter = f'#{n}/{total}' if total > 1 else ''
            attachments_lines.append(f'{i}) {label} {counter} — {rule}')
    attachments_text = '\n'.join(attachments_lines)

    parts = [
        'Voce e um diretor de arte senior e designer de social media.',
        '',
        'Crie UMA imagem final (sem variacoes) para um post de rede social, '
        'pronta para publicacao.',
        attachments_text,
        '',
        '### BRIEFING',
        f'- Rede social: {post.social_network or "instagram"}',
        f'- Formato (px): {formato_px}',
        f'- Publico-alvo: {publico_alvo or "geral"}',
        f'- Perfil/identidade da empresa (resumo): {marketing_input_summary or "(sem resumo)"}',
        '',
        '### TEXTO QUE DEVE APARECER NA ARTE (copie exatamente)',
        f'- Titulo (principal): {post.title or ""}',
        f'- Subtitulo (secundario): {post.subtitle or ""}',
        f'- CTA (opcional): {post.cta or ""} (se vazio, nao usar)',
        '',
        '### ANALISE DAS IMAGENS DE REFERENCIA',
        '- Analise as imagens de referencia e extraia delas quais sao os elementos '
        'graficos utilizados como linhas, circulos ou semi-circulos e degrades. '
        'SEJA FIEL! NAO INVENTE!',
        '- Analise fotografia, iluminacao e enquadramento.',
        '- Analise o estilo da tipografia utilizada.',
        '- Analise o background e estilo das imagens.',
        '- Analise os alinhamentos e espacamento dos textos.',
        '- Analise o posicionamento do logotipo.',
        '- SEGUINDO FIELMENTE OS ITENS ANALISADOS CRIE UM KEY VISUAL PARA SER '
        'APLICADO NA GERACAO DE NOVAS IMAGENS.',
        '',
        '### IMAGEM / CENA',
        post.image_prompt or '(sem prompt especifico)',
        '',
        'ADAPTE A DESCRICAO DA IMAGEM/CENA PARA O KEY VISUAL DESENVOLVIDO COM '
        'BASE NAS IMAGENS DE REFERENCIA para que o resultado final seja fiel as '
        'referencias, mantendo composicao, cores, posicionamento de textos e '
        'logos, alinhamento de texto, utilizacao de elementos graficos como '
        'degrades, linhas, circulos ou semi-circulos de background. Isso e uma '
        'premissa de criacao, obrigatorio. Entao, mesmo que a descricao da imagem '
        'seja diferente das imagens de referencia voce deve ter como regra de '
        'ouro as imagens de referencia, pegando da descricao de imagem/cena '
        'apenas a essencia da ideia e nada de layout. Lembre-se de manter TODOS '
        'OS ELEMENTOS graficos que sao considerados key visual. NUNCA acrescente '
        'nenhum elemento visual que nao faca parte das imagens de referencia.',
        '',
        '### DIRETRIZES DE MARCA',
        f'- Paleta: {json.dumps(paleta, ensure_ascii=False)}',
        f'- Tipografia: {json.dumps(tipografia, ensure_ascii=False)}',
        f'- Visual brief: {getattr(post, "visual_brief", "") or "(sem visual_brief)"}',
        '- SEJA FIEL AO KEY VISUAL IDENTIFICADO NAS IMAGENS DE REFERENCIA. NAO '
        'INVENTE ELEMENTOS. PREMISSA OBRIGATORIA.',
        '- Legibilidade alta para celular.',
        '- Nao inventar dados.',
        '- Nao invente elementos graficos que nao foram apresentados nas referencias.',
        '- Verifique se nas referencias ha pessoas; se nao houver, nao utilize.',
        '- Nao copiar textos de imagens anexadas.',
        '- Se houver imagens do tipo LOGO, aplicar fielmente.',
        '- Use os posicionamentos e espacamento de texto das referencias como guia.',
        '',
        '### QUALIDADE',
        '- Sem artefatos',
        '- Sem textos cortados',
        '- Sem marca dagua',
        '- Nao gerar mockup (e a arte final)',
        '',
        'Gere a arte final agora.',
    ]
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
