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
import re
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
    text_render_mode: str = 'inline',
    brand_keywords: Optional[List[str]] = None,
    pillow_layout_spec: Optional[Dict[str, Any]] = None,
    pillow_title_font_path: Optional[str] = None,
    pillow_subtitle_font_path: Optional[str] = None,
    pillow_logo_url: Optional[str] = None,
    spatial_instructions: Optional[str] = None,
    references_usage_general: str = '',
    kb_translations: Optional[List[Dict[str, Any]]] = None,
    layout_document: Optional[Dict[str, Any]] = None,
    image_prompt_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gera UMA imagem final para o post via Gemini 3 Pro Image.

    text_render_mode:
      'inline'    — texto (title/subtitle/cta) vai no prompt do Gemini
                    como hoje. Pode causar name-as-anchor failure se o
                    texto cita marca/produto.
      'sanitized' — substitui termos da marca em brand_keywords por
                    placeholders neutros no texto enviado ao prompt.
                    O texto na imagem ficara SANITIZADO (sem marca).
      'pillow'    — Gemini gera APENAS a cena (sem texto). Depois
                    aplica_se overlay de Pillow com title/subtitle/cta
                    sobre a imagem retornada. Tipografia controlada.

    brand_keywords: lista de strings a sanitizar (usado em mode='sanitized').
        Ex: ['Thermomix', 'TM7', 'Vorwerk']

    Retorna:
        {
          'png_bytes': bytes,
          'mime_type': 'image/png' | 'image/jpeg',
          'cost_usd': float,
          'model': str,
          'usage': dict (raw),
          'text_render_mode': str,
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
        text_render_mode=text_render_mode,
        brand_keywords=brand_keywords or [],
        spatial_instructions=spatial_instructions or '',
        references_usage_general=references_usage_general or '',
        kb_translations=kb_translations or [],
        image_prompt_override=image_prompt_override,
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

    # PNG CRU do Gemini (sem texto) — base do canvas editavel + debug.
    raw_png_bytes = png_bytes

    # 6. Render do texto sobre a imagem.
    #    Preferencial: layout_document (divs do orquestrador) — base do canvas.
    #    Fallback: apply_text_overlay (spec antigo) quando nao ha documento.
    if layout_document and (layout_document.get('elements')):
        try:
            png_bytes = render_layout_document(
                png_bytes,
                elements=layout_document.get('elements') or [],
                paleta=paleta,
                fonts={
                    'titulo': pillow_title_font_path,
                    'subtitulo': pillow_subtitle_font_path,
                    'cta': pillow_title_font_path,
                },
                logo_url=pillow_logo_url,
            )
            mime_type = 'image/png'
        except Exception:
            logger.exception('Falha ao renderizar layout_document — tenta overlay legado')
            layout_document = None  # cai no overlay abaixo
    if (not layout_document) and text_render_mode == 'pillow':
        try:
            png_bytes = apply_text_overlay(
                png_bytes,
                title=post.title or '',
                subtitle=post.subtitle or '',
                cta=post.cta or '',
                paleta=paleta,
                layout_spec=pillow_layout_spec or None,
                title_font_path=pillow_title_font_path,
                subtitle_font_path=pillow_subtitle_font_path,
                logo_url=pillow_logo_url,
            )
            mime_type = 'image/png'  # overlay sempre salva como PNG
        except Exception:
            logger.exception('Falha ao aplicar overlay Pillow — retornando PNG raw')

    # Calcula custo real combinando tokens input + cobranca flat por imagem
    usage_meta = response_json.get('usageMetadata', {}) or {}
    n_candidates = len(response_json.get('candidates', []) or [])
    images_out = max(1, n_candidates)
    input_tokens = int(usage_meta.get('promptTokenCount', 0) or 0)
    # Gemini 3 Pro Image pricing oficial:
    #   - Input text tokens: $0.10 / 1M
    #   - Output image: $0.04 por imagem 1024px
    input_cost = Decimal(input_tokens) * Decimal('0.10') / Decimal('1000000')
    output_cost = Decimal(images_out) * Decimal('0.04')
    real_cost = float(input_cost + output_cost)

    return {
        'png_bytes': png_bytes,
        'raw_png_bytes': raw_png_bytes,  # cena do Gemini SEM texto (base canvas)
        'mime_type': mime_type,
        'cost_usd': real_cost,
        'model': model_used,
        'usage': usage_meta,
        'prompt_text': prompt_text,
        'text_render_mode': text_render_mode,
        'images_generated': images_out,
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


def _normalize_tipo(tipo: str) -> str:
    """Normaliza variantes do usage_type em buckets canonicos."""
    t = (tipo or '').lower().strip()
    if 'logo' in t:
        return 'logo'
    if 'produto' in t:
        return 'produto'
    if 'pessoa' in t or 'speaker' in t or 'palestr' in t:
        return 'pessoa'
    if 'cenari' in t or 'lugar' in t or 'local' in t:
        return 'cenario'
    if 'fundo' in t or 'background' in t or 'textura' in t:
        return 'fundo'
    if 'icone' in t or 'ícone' in t:
        return 'icone'
    if 'refer' in t:
        return 'referencia'
    return t or 'desconhecido'


def _build_combination_rules(type_counts: Dict[str, int]) -> str:
    """
    Monta texto de regras adicionais conforme combinacao detectada.
    Adapta o prompt para que TODAS as imagens upload das tipos 'produto',
    'pessoa', 'cenario' apareçam juntas na arte final.

    Exemplos de output:
      - N produtos: "todos os produtos juntos na composicao"
      - 1 produto + 1 pessoa: "a pessoa interagindo com o produto"
      - N pessoas: "grupo de pessoas juntas"
      - 1 produto + 1 cenario: "produto inserido no cenario fornecido"
    """
    n_prod = type_counts.get('produto', 0)
    n_pess = type_counts.get('pessoa', 0)
    n_cena = type_counts.get('cenario', 0)
    total_must_appear = n_prod + n_pess + n_cena

    if total_must_appear <= 1:
        return ''

    lines = ['', '# COMBINACAO OBRIGATORIA DE ELEMENTOS', '']
    lines.append(
        f'Voce recebeu {total_must_appear} elementos que DEVEM aparecer JUNTOS na '
        f'arte final, na mesma cena:'
    )
    if n_prod > 0:
        lines.append(f'  - {n_prod} produto(s) — todos devem aparecer fielmente')
    if n_pess > 0:
        lines.append(f'  - {n_pess} pessoa(s) — todas devem aparecer com rosto/identidade preservados')
    if n_cena > 0:
        lines.append(f'  - {n_cena} cenario(s) — usar como ambiente da composicao')

    lines.append('')
    lines.append('Combine-os de forma harmonica e natural:')

    # Heuristicas de combinacao
    if n_pess >= 1 and n_prod >= 1:
        lines.append(
            f'  - A(s) pessoa(s) deve(m) estar INTERAGINDO com o(s) produto(s) '
            f'(segurando, usando, demonstrando) ou claramente associada(s) a ele(s).'
        )
    if n_prod >= 2 and n_pess == 0:
        lines.append(
            '  - Os produtos devem aparecer juntos como grupo (flat-lay, vitrine, '
            'composicao em bancada, ou cena onde todos sao visiveis ao mesmo tempo).'
        )
    if n_pess >= 2:
        lines.append(
            '  - As pessoas devem aparecer juntas (grupo, painel, conversa) '
            'mantendo identidade de cada uma.'
        )
    if n_cena >= 1:
        lines.append(
            '  - O cenario anexado define o AMBIENTE da cena — produtos e pessoas '
            'sao posicionados dentro desse ambiente, respeitando luz, perspectiva '
            'e atmosfera da referencia.'
        )

    lines.append('')
    lines.append(
        'REGRA CRITICA: NAO escolha apenas alguns elementos para destacar. TODOS '
        'os elementos listados acima sao obrigatorios na arte final. Se nao '
        'couber tudo na composicao, ajuste o enquadramento, escala ou angulo '
        '— mas nao omita nenhum.'
    )
    return '\n'.join(lines)


def _build_role_label_en(tipo_norm: str, usage_desc: str = '') -> tuple:
    """
    Retorna (LABEL_INGLES, FIDELITY_RULE_INGLES) baseado no tipo normalizado.
    Usado em modos pillow/sanitized para prompt hibrido (EN + PT).
    """
    desc_extra = f' (user note: "{usage_desc}")' if usage_desc else ''
    mapping = {
        'logo': (
            'BRAND LOGO',
            'apply exactly as shown — no distortion, no color change, no redesign',
        ),
        'produto': (
            'PRODUCT',
            'keep the SAME PRODUCT IDENTITY — exact model, shape proportions, '
            'label, color, display, finish, materials. It MAY be shown from a '
            'DIFFERENT angle/position/framing that fits the scene (MODERATE '
            'variation only — slight rotation/perspective, do NOT invent unseen '
            'parts, do NOT redesign or restyle the product)',
        ),
        'pessoa': (
            'MODEL',
            'same person — keep face, hair, skin tone, body shape identical. '
            'Pose and angle MAY vary moderately to fit the scene. Do not '
            'substitute or generate a different person',
        ),
        'cenario': (
            'SETTING',
            'use this exact environment as the scene background — preserve '
            'architecture, lighting and atmosphere',
        ),
        'fundo': (
            'BACKGROUND TEXTURE',
            'use as reference for texture and tone — do not place subjects '
            'on top of any text in this image',
        ),
        'icone': (
            'ICON',
            'apply as a graphic element, preserving legibility',
        ),
        'referencia': (
            'STYLE REFERENCE',
            'use as inspiration for photography style, lighting and mood ONLY '
            '— do not copy any specific element or text',
        ),
    }
    label, rule = mapping.get(tipo_norm, ('REFERENCE', 'use as visual reference'))
    return label, rule + desc_extra


def _build_reference_roles_en_block(sorted_refs: List[Dict[str, Any]]) -> str:
    """
    Bloco [REFERENCE ROLES] em ingles para modos pillow/sanitized.
    Lista cada imagem com label forte e regra de fidelidade absoluta.
    """
    if not sorted_refs:
        return ''
    lines = ['[REFERENCE ROLES]']
    # Conta tipos para distinguir duplicatas
    type_counts: Dict[str, int] = {}
    for ref in sorted_refs:
        t = _normalize_tipo(str(ref.get('tipo', '')).lower())
        type_counts[t] = type_counts.get(t, 0) + 1

    running: Dict[str, int] = {}
    for i, ref in enumerate(sorted_refs, 1):
        tipo_norm = _normalize_tipo(str(ref.get('tipo', '')).lower())
        usage_desc = (ref.get('usage_description') or '').strip()
        label, rule = _build_role_label_en(tipo_norm, usage_desc)
        running[tipo_norm] = running.get(tipo_norm, 0) + 1
        suffix = ''
        if type_counts[tipo_norm] > 1:
            suffix = f' #{running[tipo_norm]}/{type_counts[tipo_norm]}'
        lines.append(f'Image {i} ({label}{suffix}): {rule}.')
    return '\n'.join(lines)


def _build_fidelity_block_en(sorted_refs: List[Dict[str, Any]]) -> str:
    """
    Bloco [FIDELITY REQUIREMENTS] em ingles + EVITE/AVOID bilingue.
    Reforco final para combater fusion failures em multi-image.
    """
    if not sorted_refs:
        return ''
    n = len(sorted_refs)
    lines = [
        '[FIDELITY REQUIREMENTS]',
        f'All {n} referenced items must appear clearly and SIMULTANEOUSLY in '
        'the final frame. Do not merge, stylize, replace, or omit any '
        'referenced element. Product labels and brand details must remain '
        'legible. Any human face must match the reference exactly.',
        '',
        'AVOID / EVITE: altered product, different bag/accessory, generated face, '
        'similar-but-not-identical model, merged elements, stylized objects, '
        'invented details not present in references.',
    ]
    return '\n'.join(lines)


def _scene_has_inline_anchoring(image_prompt: str) -> bool:
    """
    Detecta se a SCENE ja contem ancoragem inline por filename
    no padrao "(arquivo: NOME.ext — ...)".

    Quando True, podemos omitir [REFERENCE ROLES] (redundante) e
    encurtar o bloco de fidelidade.
    """
    if not image_prompt:
        return False
    # Aceita "arquivo:", "arquivo :", ou variantes case-insensitive
    return bool(re.search(r'\(\s*arquivo\s*:', image_prompt, flags=re.IGNORECASE))


def _sanitize_brand_terms(text: str, keywords: List[str]) -> str:
    """
    Substitui termos da marca/produto em `text` por placeholders neutros.
    Case-insensitive. Usado em text_render_mode='sanitized'.

    Ex: ('Conheca a Thermomix TM7', ['Thermomix', 'TM7'])
        -> 'Conheca a [produto]'
    """
    if not text or not keywords:
        return text
    out = text
    # Ordena por tamanho DESC para nao deixar substring quebrar match (ex:
    # remove "Thermomix TM7" antes de "TM7")
    sorted_kw = sorted({k for k in keywords if k}, key=len, reverse=True)
    for kw in sorted_kw:
        # \b para boundary, ignorecase
        out = re.sub(rf'\b{re.escape(kw)}\b', '[produto]', out, flags=re.IGNORECASE)
    # Colapsa multiplos placeholders adjacentes
    out = re.sub(r'(\[produto\]\s*){2,}', '[produto] ', out)
    return out.strip()


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
    text_render_mode: str = 'inline',
    brand_keywords: List[str] = None,
    spatial_instructions: str = '',
    references_usage_general: str = '',
    kb_translations: List[Dict[str, Any]] = None,
    image_prompt_override: Optional[str] = None,
) -> str:
    """
    Prompt SIMPLES — confia na dereferenciacao por imagem ("o produto da
    imagem N anexada"). Sem nomes, sem KEEP_UNCHANGED extenso, sem
    bracket/negative naming. Inspirado em prompts curtos de catalogo
    e lifestyle que funcionam bem com Gemini.

    product_analyses fica como argumento mas e ignorado nesta versao
    (mantido para compatibilidade — pode ser util em futuras iteracoes).
    """
    # Sanitiza marca/modelo de TODO texto que vai ao Gemini (cena, instrucoes
    # espaciais do orchestrator, guidance do user). Citar a marca ativa priors
    # e o produto sai infiel. So o titulo/subtitulo (Pillow) mantem a marca.
    if brand_keywords:
        spatial_instructions = _sanitize_brand_terms(spatial_instructions or '', brand_keywords)
        references_usage_general = _sanitize_brand_terms(references_usage_general or '', brand_keywords)

    # Conta quantos de cada tipo (para nomear "produto principal" / "produto 2" etc)
    type_counts: Dict[str, int] = {}
    for ref in sorted_refs:
        t = _normalize_tipo(str(ref.get('tipo', '')).lower())
        type_counts[t] = type_counts.get(t, 0) + 1

    # Mapeia tipo -> linha descritiva curta (com numeracao quando ha varios do mesmo tipo)
    type_running: Dict[str, int] = {}
    refs_lines: List[Tuple[int, str]] = []
    for i, ref in enumerate(sorted_refs, 1):
        tipo_raw = str(ref.get('tipo', 'desconhecido')).lower()
        tipo_norm = _normalize_tipo(tipo_raw)
        type_running[tipo_norm] = type_running.get(tipo_norm, 0) + 1
        n = type_running[tipo_norm]
        total = type_counts[tipo_norm]
        usage_desc = (ref.get('usage_description') or '').strip()

        if tipo_norm == 'logo':
            line = f'IMAGEM {i}: logotipo da marca — aplicar exatamente como aparece (sem distorcer, sem mudar cor)'
        elif tipo_norm == 'produto':
            if total > 1:
                line = f'IMAGEM {i}: produto #{n}/{total} — use exatamente como aparece (mesmas cores, mesmo formato, mesmos detalhes)'
            else:
                line = f'IMAGEM {i}: o produto principal — use exatamente como aparece (mesmas cores, mesmo formato, mesmos detalhes)'
        elif tipo_norm == 'pessoa':
            if total > 1:
                line = f'IMAGEM {i}: pessoa #{n}/{total} — usar exatamente como aparece (mesmo rosto, mesma aparencia)'
            else:
                line = f'IMAGEM {i}: pessoa — usar exatamente como aparece (mesmo rosto, mesma aparencia)'
        elif tipo_norm == 'cenario':
            line = f'IMAGEM {i}: cenario/lugar — usar como ambiente da cena (manter elementos arquitetonicos)'
        elif tipo_norm == 'fundo':
            line = f'IMAGEM {i}: textura/fundo de referencia'
        elif tipo_norm == 'icone':
            line = f'IMAGEM {i}: elemento grafico/icone'
        else:
            line = f'IMAGEM {i}: referencia visual (inspiracao de estilo, fotografia, iluminacao — nao copiar textos)'

        # Se o user descreveu o uso da imagem, anexa
        if usage_desc:
            line += f'\n    Uso solicitado pelo usuario: "{usage_desc}"'
        refs_lines.append((i, line))

    attachments_text = '\n'.join(line for _, line in refs_lines)

    # Regra de "todas as imagens devem aparecer juntas" quando ha multiplas
    # imagens com tipos que devem aparecer (produto/pessoa/cenario).
    must_appear_count = (
        type_counts.get('produto', 0)
        + type_counts.get('pessoa', 0)
        + type_counts.get('cenario', 0)
    )
    combination_rules = _build_combination_rules(type_counts)

    # Define o que vai no bloco "TEXTO A RENDERIZAR" conforme o modo
    raw_title = post.title or ''
    raw_subtitle = post.subtitle or ''
    raw_cta = post.cta or ''

    if text_render_mode == 'sanitized':
        # Substitui termos da marca por placeholder neutro — evita ativar
        # priors do training data. O texto na imagem ficara sanitizado.
        title_for_prompt = _sanitize_brand_terms(raw_title, brand_keywords or [])
        subtitle_for_prompt = _sanitize_brand_terms(raw_subtitle, brand_keywords or [])
        cta_for_prompt = _sanitize_brand_terms(raw_cta, brand_keywords or [])
    elif text_render_mode == 'pillow':
        # NAO inclui texto no prompt — sera desenhado por Pillow apos
        title_for_prompt = ''
        subtitle_for_prompt = ''
        cta_for_prompt = ''
    else:  # 'inline'
        title_for_prompt = raw_title
        subtitle_for_prompt = raw_subtitle
        cta_for_prompt = raw_cta

    # Estrutura hibrida EN/PT em TODOS os modos:
    # - Headers + diretivas de fidelidade em INGLES (peso semantico forte
    #   no training data do Gemini, padrao validado pela comunidade)
    # - [SCENE] em PT-BR (preserva tom on-brand do Claude texto)
    # - Bloco de texto a renderizar em PT-BR (inline) — com instrucao explicita
    #   pro Gemini nao traduzir
    use_hybrid_en = True  # antes: text_render_mode in ('pillow', 'sanitized')

    # Fix C: bloco USER GUIDANCE com o texto livre "Como usar as referencias?"
    # que o user digitou no modal. Vai destacado entre REFERENCE ROLES e SCENE.
    user_guidance_block_en = ''
    user_guidance_block_pt = ''
    if references_usage_general:
        user_guidance_block_en = (
            '\n[USER GUIDANCE ON REFERENCES]\n'
            'The user provided explicit guidance on how the attached references '
            'should be used:\n'
            f'"{references_usage_general.strip()}"\n'
            'Treat this as a strong directive on style, treatment and mood.'
        )
        user_guidance_block_pt = (
            '\n# INSTRUCAO DO USUARIO SOBRE AS REFERENCIAS\n'
            'O usuario indicou como as referencias devem ser usadas:\n'
            f'"{references_usage_general.strip()}"\n'
            'Trate como diretriz forte de estilo, tratamento e mood.'
        )

    # Bloco [REFERENCE-DERIVED DIRECTIVES] — direcionamento textual derivado
    # do dossie visual (ReferenceImage.visual_analysis). So e usado como
    # fallback quando o orchestrator nao roda; no caminho normal o dossie ja
    # foi fundido no image_prompt_final pelo orchestrator.
    kb_directives_block_en = ''
    kb_directives_block_pt = ''
    if kb_translations:
        en_lines = [
            '',
            '[REFERENCE-DERIVED DIRECTIVES]',
            '(extracted from brand reference images via visual analysis — '
            'apply as directives to the generated scene)',
        ]
        pt_lines = [
            '',
            '# DIRETRIZES EXTRAIDAS DAS REFERENCIAS DA MARCA',
            '(analisadas das imagens de referencia da KB — aplicar a cena)',
        ]
        for t in kb_translations:
            category = (t.get('category') or 'general').replace('_', ' ').title()
            directives = (t.get('directives') or '').strip()
            user_desc = (t.get('usage_description_user') or '').strip()
            if not directives:
                continue
            en_lines.append('')
            en_lines.append(f'• {category}' + (f' (user asked: "{user_desc}")' if user_desc else '') + ':')
            en_lines.append(f'  {directives}')
            pt_lines.append('')
            pt_lines.append(f'• {category}' + (f' (user pediu: "{user_desc}")' if user_desc else '') + ':')
            pt_lines.append(f'  {directives}')
        kb_directives_block_en = '\n'.join(en_lines)
        kb_directives_block_pt = '\n'.join(pt_lines)

    # Detecta inline anchoring na SCENE — se presente, omite REFERENCE ROLES
    # (redundante) e adiciona breve nota explicativa antes da cena.
    # image_prompt_text: usa o override do orquestrador quando disponivel
    # (image_prompt_final). Senao, cai pra post.image_prompt (Fase 1).
    image_prompt_text = (image_prompt_override or post.image_prompt
                         or '(propor um cenario adequado ao briefing)')
    # Sanitiza marca/modelo da CENA em QUALQUER modo: citar a marca no prompt
    # ativa priors do Gemini (ele renderiza branding e ignora a foto anexa).
    # O titulo/subtitulo (desenhados via Pillow) podem manter a marca; a CENA nao.
    if brand_keywords:
        image_prompt_text = _sanitize_brand_terms(image_prompt_text, brand_keywords)
    inline_anchored = _scene_has_inline_anchoring(image_prompt_text)

    if use_hybrid_en:
        if inline_anchored:
            # MODO MINIMALISTA — confia que a SCENE ja contem (a) filename
            # inline com regras de fidelidade coladas e (b) descricao da
            # iluminacao incorporada. Sem TASK, USER GUIDANCE, COMBINACAO
            # ou REFERENCE-DERIVED DIRECTIVES separados.
            scene_with_kb = image_prompt_text
            kb_directive_lines = [
                (t.get('directives') or '').strip()
                for t in (kb_translations or [])
                if (t.get('directives') or '').strip()
            ]
            if kb_directive_lines:
                scene_with_kb = (
                    image_prompt_text.rstrip()
                    + '\n\n'
                    + ' '.join(kb_directive_lines)
                )
            parts = [scene_with_kb]
        else:
            # Modo verboso anterior (compatibilidade com posts sem inline
            # anchoring na SCENE) — mantem REFERENCE ROLES, USER GUIDANCE,
            # REFERENCE-DERIVED DIRECTIVES, COMBINACAO e TASK.
            parts = [
                '[TASK]',
                'Create a professional photograph for a social media post.',
                '',
                _build_reference_roles_en_block(sorted_refs),
                user_guidance_block_en,
                kb_directives_block_en,
                combination_rules,
                '',
                '[SCENE] (in Portuguese, on-brand)',
                image_prompt_text,
            ]
    else:
        parts = [
            '# TAREFA',
            'Crie uma fotografia profissional para um post de rede social.',
            '',
            '# REFERENCIAS VISUAIS (anexadas ACIMA deste texto, na ordem)',
            attachments_text,
            user_guidance_block_pt,
            kb_directives_block_pt,
            combination_rules,
            '',
            '# CENA',
            post.image_prompt or '(propor um cenario adequado ao briefing)',
        ]

    # Bloco COMPOSICAO DA CENA — descricao da cena cheia vinda do orchestrator.
    # NAO pedimos zonas reservadas: a cena preenche o quadro e o texto e
    # sobreposto depois (layout_document) adaptando-se por contraste.
    if spatial_instructions:
        parts.extend([
            '',
            '# COMPOSICAO DA CENA',
            spatial_instructions,
            'IMPORTANTE: a cena deve preencher TODO o quadro de forma natural. '
            'NAO crie painel, faixa lisa, area chapada nem "espaco reservado" '
            'para texto/logo, e NAO desenhe texto ou logo.',
        ])

    # === EXPERIMENT: bloco LAYOUT REFERENCE (start) ===
    # Lista as refs com tipo='referencia_layout' (anexadas pela tasks.py) com
    # instrucoes deterministicas. Facil reverter: delete entre os marcadores.
    _layout_ref_lines = []
    for _i, _ref in enumerate(sorted_refs, 1):
        if str(_ref.get('tipo', '')).lower() == 'referencia_layout':
            _u = (_ref.get('usage_description') or '').strip()
            if _u:
                _layout_ref_lines.append(f'IMAGE {_i} (LAYOUT REFERENCE): {_u}')
    if _layout_ref_lines:
        parts.extend([
            '',
            '[LAYOUT REFERENCE — replicate the STRUCTURE only]',
            'A IMAGEM(NS) abaixo e a referencia de LAYOUT/TEMPLATE da marca. ',
            'Use APENAS o que esta listado no brief abaixo (posicoes em %, '
            'cores, formas). NAO copie o sujeito/comida/produto especifico da '
            'referencia, NAO reproduza textos visiveis dentro de faixas/selos.',
            '',
            'REGRA DE ANGULO/PERSPECTIVA: o angulo/perspectiva da cena e dos '
            'objetos da nossa cena deve seguir o angulo/perspectiva mostrado na '
            'LAYOUT REFERENCE. Se a referencia e flat-lay cenital, a nossa cena '
            'tambem e flat-lay cenital. Se a referencia mostra o produto num '
            'angulo X, o produto da nossa cena aparece no MESMO angulo X.',
            *_layout_ref_lines,
        ])
    # === EXPERIMENT: bloco LAYOUT REFERENCE (end) ===

    if use_hybrid_en:
        # Briefing + diretrizes em ingles (modos pillow/sanitized)
        parts.extend([
            '',
            '[BRIEFING]',
            f'- Social network: {post.social_network or "instagram"}',
            f'- Format (px): {formato_px}',
            f'- Target audience: {publico_alvo or "general"}',
            '',
            '[BRAND GUIDELINES]',
            f'- Brand palette: {json.dumps(paleta, ensure_ascii=False)}',
            f'- Typography: {json.dumps(tipografia, ensure_ascii=False)}',
            '- Apply palette and typography ONLY to post text — not to referenced items.',
            '- Do not copy text visible inside reference images.',
            '- If no people in references, do not add people.',
            '',
            '[QUALITY]',
            '- Photorealistic, no artifacts, no cropped text, no watermark.',
            '- Not a mockup — this is the final artwork.',
            '- High legibility for mobile.',
        ])
        # Reforco final de fidelidade — so no modo verboso. No modo
        # minimalista (inline_anchored) as regras ja vivem inline na SCENE.
        if not inline_anchored:
            fidelity = _build_fidelity_block_en(sorted_refs)
            if fidelity:
                parts.extend(['', fidelity])
    else:
        # Modo inline em PT-BR (Gemini vai renderizar texto na imagem em PT)
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

    # Texto a renderizar — colocado no FINAL com isolamento explicito
    if text_render_mode == 'pillow':
        parts.extend([
            '',
            '[CRITICAL] DO NOT RENDER ANY TEXT OR BRAND LOGO IN THE IMAGE.',
            'This scene must contain:',
            '- NO text, words, slogans, numbers, letters, or characters',
            '- NO brand logos, brand marks, or company names',
            '- NO watermarks',
            'Only the visual scene with the referenced subjects '
            '(product/person/etc, EXCLUDING the logo). Both text AND the '
            'brand logo will be overlaid in post-processing — generate '
            'only the underlying scene.',
        ])
    elif text_render_mode == 'sanitized':
        # Sanitized mode raramente usado mas suportado
        parts.extend([
            '',
            '[TEXT TO RENDER LITERALLY ON THE ARTWORK]',
            'The texts below should be drawn ON the scene. Do NOT use their '
            'content as visual description of the product. The product is '
            'exclusively what appears in the reference IMAGE above.',
            f'- Title: "{title_for_prompt}"',
            f'- Subtitle: "{subtitle_for_prompt}"',
        ])
        if cta_for_prompt:
            parts.append(f'- CTA: "{cta_for_prompt}"')
    else:  # inline — Gemini renderiza o texto na imagem
        parts.extend([
            '',
            '[TEXT TO RENDER LITERALLY ON THE ARTWORK]',
            'CRITICAL: Render the following texts in BRAZILIAN PORTUGUESE '
            'exactly as written below. DO NOT TRANSLATE to English or any '
            'other language. The texts must appear in the image visually.',
            'These texts are for VISUAL RENDERING only — do not use them as '
            'descriptions of the product. The product is exclusively what '
            'appears in the referenced IMAGE above.',
            f'- Title (render exactly): "{title_for_prompt}"',
            f'- Subtitle (render exactly): "{subtitle_for_prompt}"',
        ])
        if cta_for_prompt:
            parts.append(f'- CTA (render exactly): "{cta_for_prompt}"')

    parts.extend([
        '',
        'Generate the final artwork now.' if use_hybrid_en else 'Gere a arte final agora.',
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


# ============================================================
# Fluxo C — Overlay de texto via Pillow (Fluxo 2 / text_render_mode='pillow')
# ============================================================

_DEJAVU_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU_REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

# Emojis e simbolos que as fontes de marca (TTF) nao renderizam -> viram tofu.
_EMOJI_RE = re.compile(
    '['
    '\U0001F000-\U0001FAFF'  # pictografos / emojis
    '\U00002600-\U000027BF'  # misc symbols + dingbats
    '\U00002190-\U000021FF'  # setas
    '\U00002B00-\U00002BFF'  # setas/simbolos
    '\U0001F1E6-\U0001F1FF'  # bandeiras
    '️‍'            # variation selector + ZWJ
    ']+',
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    if not text:
        return text
    return _EMOJI_RE.sub('', text).strip()


def _fit_text_to_box(text, font_path, fallback_path, max_w, max_h, start_size, draw, min_size=22):
    """Shrink-to-fit considerando LARGURA E ALTURA da caixa declarada.
    Retorna (font, lines, fit_ok). fit_ok=False quando chegou ao min_size sem
    caber (e renderiza no minimo, mas loga aviso)."""
    from PIL import ImageFont
    size = max(int(min_size), int(start_size))
    font = None
    lines = []
    for _ in range(14):
        try:
            font = ImageFont.truetype(font_path or fallback_path, size)
        except Exception:
            font = ImageFont.truetype(fallback_path, size)
        lines = _wrap_text(text, font, max_w, draw)
        widest = 0
        for ln in lines:
            try:
                bb = draw.textbbox((0, 0), ln, font=font)
                w = bb[2] - bb[0]
            except Exception:
                w = len(ln) * size * 0.55
            widest = max(widest, w)
        line_h = size * 1.18
        total_h = int(line_h * len(lines))
        width_ok = widest <= max_w
        height_ok = total_h <= max_h
        if width_ok and height_ok:
            return font, lines, True
        if size <= min_size:
            return font, lines, False
        scale_w = (max_w / widest) if not width_ok and widest > 0 else 1.0
        scale_h = (max_h / total_h) if not height_ok and total_h > 0 else 1.0
        scale = min(scale_w, scale_h) * 0.95
        size = max(min_size, int(size * max(0.55, scale)))
    return font, lines, False


def _fit_text(text, font_path, fallback_path, max_w, start_size, draw, min_size=22):
    """Shrink-to-fit: reduz o tamanho da fonte ate a linha mais larga caber em
    max_w (evita estouro/corte com palavras longas ou formatos estreitos).
    Retorna (font, lines)."""
    from PIL import ImageFont
    size = max(int(min_size), int(start_size))
    font = None
    lines = []
    for _ in range(8):
        try:
            font = ImageFont.truetype(font_path or fallback_path, size)
        except Exception:
            font = ImageFont.truetype(fallback_path, size)
        lines = _wrap_text(text, font, max_w, draw)
        widest = 0
        for ln in lines:
            try:
                bb = draw.textbbox((0, 0), ln, font=font)
                w = bb[2] - bb[0]
            except Exception:
                w = len(ln) * size * 0.55
            widest = max(widest, w)
        if widest <= max_w or size <= min_size:
            return font, lines
        # escala direto pro alvo (com folga), recomputa wrap na proxima volta
        size = max(min_size, int(size * max(0.55, (max_w / widest) * 0.97)))
    return font, lines


def apply_text_overlay(
    png_bytes: bytes,
    title: str = '',
    subtitle: str = '',
    cta: str = '',
    paleta: Optional[List[Dict[str, Any]]] = None,
    layout_spec: Optional[Dict[str, Any]] = None,
    title_font_path: Optional[str] = None,
    subtitle_font_path: Optional[str] = None,
    logo_url: Optional[str] = None,
) -> bytes:
    """
    SMART overlay de texto sobre a imagem usando Pillow.

    Args:
      png_bytes: PNG bytes da cena gerada pelo Gemini
      title/subtitle/cta: textos a renderizar
      paleta: lista de cores da marca (para derivar cores de fundo/CTA)
      layout_spec: dict do brand_layout_spec (analisado via Claude Vision
          das references da KB) OU wireframe fallback. Schema definido em
          KnowledgeBase.brand_layout_spec.
      title_font_path: caminho local do TTF para titulo (resolvido pelo
          FontResolver). None = DejaVu Bold.
      subtitle_font_path: idem subtitulo. None = DejaVu Regular.
      logo_url: URL presigned do logo da KB (opcional). Se fornecido, e
          desenhado na posicao layout_spec['logo_position'].

    Layout dinamico baseado em layout_spec:
      - title_position (9 anchors) define onde o titulo aparece
      - title_size_pct define tamanho relativo a altura
      - title_color_hint='auto_contrast' analisa luminancia da regiao
      - cta_style pode ser pill/underline/block
      - logo_position pode ser top-right/top-left etc

    Retorna novos PNG bytes com o texto desenhado.
    """
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    spec = layout_spec or _DEFAULT_LAYOUT_SPEC

    img = Image.open(BytesIO(png_bytes)).convert('RGBA')
    W, H = img.size
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ---- Tamanhos ---------------------------------------------------------
    # Base no MENOR lado do canvas (nao na altura): mantem o "peso" do texto
    # consistente entre formatos — no 9:16 a altura e enorme e inflava o texto.
    basis = min(W, H)
    title_size = max(20, int(basis * float(spec.get('title_size_pct', 7)) / 100))
    subtitle_size = max(14, int(basis * float(spec.get('subtitle_size_pct', 3)) / 100))
    cta_size = max(14, int(basis * 0.030))

    # ---- Fontes -----------------------------------------------------------
    tf_path = title_font_path or '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    sf_path = subtitle_font_path or '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    try:
        title_font = ImageFont.truetype(tf_path, title_size)
    except Exception:
        title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', title_size)
    try:
        subtitle_font = ImageFont.truetype(sf_path, subtitle_size)
    except Exception:
        subtitle_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', subtitle_size)
    try:
        cta_font = ImageFont.truetype(tf_path, cta_size)
    except Exception:
        cta_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', cta_size)

    padding = int(W * float(spec.get('padding_pct', 5)) / 100)
    alignment = spec.get('alignment', 'left')

    # ---- LOGO -------------------------------------------------------------
    logo_box = None
    if logo_url and spec.get('logo_position', 'none') != 'none':
        try:
            logo_box = _draw_logo_on_overlay(
                overlay, logo_url,
                position=spec['logo_position'],
                size_pct=float(spec.get('logo_size_pct', 12)),
                padding=padding, canvas_size=(W, H),
            )
        except Exception:
            logger.exception('Falha ao desenhar logo no overlay')

    def _hits_logo(bx, by, bw, bh):
        """True so quando o retangulo do texto realmente INTERSECTA a caixa do
        logo (horizontal E vertical). Evita texto por cima do logo sem cortar
        texto de uma coluna lateral quando o logo esta em outra posicao."""
        if not logo_box:
            return False
        lx, ly, lw, lh = logo_box
        m = int(H * 0.01)
        return not (bx + bw < lx - m or bx > lx + lw + m or
                    by + bh < ly - m or by > ly + lh + m)

    # ---- TEXTO: alinhamento/caixa POR BLOCO + zona % (replica layout ref) -
    # Compat: se os campos por-bloco nao existem, cai no comportamento antigo
    # (alignment global + subtitulo colado abaixo do titulo).
    title_align = spec.get('title_align', alignment)
    subtitle_align = spec.get('subtitle_align', alignment)
    color_hint = spec.get('title_color_hint', 'auto_contrast')
    subtitle_color_hint = spec.get('subtitle_color_hint', 'auto_contrast')
    title_color_hex = spec.get('title_color')
    subtitle_color_hex = spec.get('subtitle_color')
    bg_treatment = spec.get('background_treatment', 'none')

    def _block_color(hex_pref, bx, by, bw, bh, hint):
        """Cor do texto: usa a cor de marca (hex_pref) quando ela contrasta com
        o fundo (desfocado) da zona; senao cai pro hint/auto_contrast (legivel).
        Sem painel solido — a legibilidade vem do blur discreto da cena."""
        if hex_pref:
            try:
                rgb = _hex_to_rgb(hex_pref)
                rl = _region_luminance(img, bx, by, bw, bh)
                cl = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                if abs(cl - rl) >= 70:
                    return rgb
            except Exception:
                pass
        return _resolve_text_color(img, bx, by, bw, bh, hint=hint, paleta=paleta or [])
    line_h_title = title_size * 1.15
    line_h_sub = subtitle_size * 1.30
    gap_title_sub = int(H * 0.012)

    def _apply_case(txt, case):
        if case == 'alta':
            return txt.upper()
        if case == 'baixa':
            return txt.lower()
        return txt

    # Remove emojis/simbolos que a fonte da marca nao renderiza (evita tofu □)
    title = _apply_case(_strip_emoji(title), spec.get('title_case'))
    subtitle = _apply_case(_strip_emoji(subtitle), spec.get('subtitle_case'))
    cta = _strip_emoji(cta)

    def _block_origin(zone, default_anchor, block_w, block_h):
        """(x, y, largura) do bloco: usa zona % (x_pct/y_pct/width_pct) se
        presente, senao a ancora de 9 posicoes."""
        if isinstance(zone, dict) and zone.get('x_pct') is not None and zone.get('y_pct') is not None:
            zx = int(W * float(zone['x_pct']) / 100)
            zy = int(H * float(zone['y_pct']) / 100)
            zw = int(W * float(zone['width_pct']) / 100) if zone.get('width_pct') else block_w
            return zx, zy, max(zw, 50)
        ax, ay = _anchor_to_xy(default_anchor, (W, H), (block_w, block_h), padding)
        return ax, ay, block_w

    tzone = spec.get('title_zone_pct')
    szone = spec.get('subtitle_zone_pct')
    independent_subtitle = isinstance(szone, dict)

    title_block_w = (
        int(W * float(tzone['width_pct']) / 100)
        if isinstance(tzone, dict) and tzone.get('width_pct') else (W - 2 * padding)
    )
    # Shrink-to-fit: garante que o titulo CABE na largura da zona (sem corte)
    title_font, title_lines = _fit_text(
        title, tf_path, _DEJAVU_BOLD, title_block_w, title_size, draw,
    )
    line_h_title = title_font.size * 1.15
    # Hierarquia: o subtitulo deve ser BEM menor que o titulo FINAL (apos o
    # shrink, o titulo pode ter encolhido — o subtitulo nunca passa de ~55%).
    subtitle_size = min(subtitle_size, max(13, int(title_font.size * 0.55)))

    if independent_subtitle:
        sub_block_w = int(W * float(szone.get('width_pct', 80)) / 100)
    else:
        # colado abaixo do titulo -> mesma COLUNA de largura do titulo (nao a
        # largura total), pra respeitar a proporcao da referencia (~50%).
        sub_block_w = title_block_w
    show_sub = bool(subtitle) and (
        independent_subtitle or spec.get('subtitle_offset', 'below_title') == 'below_title'
    )
    if show_sub:
        subtitle_font, subtitle_lines = _fit_text(
            subtitle, sf_path, _DEJAVU_REG, sub_block_w, subtitle_size, draw,
        )
        line_h_sub = subtitle_font.size * 1.30
    else:
        subtitle_lines = []

    # ----- Bloco TITULO (com subtitulo colado, se nao for independente) ----
    title_h = int(line_h_title * len(title_lines))
    glued_sub_h = 0 if independent_subtitle else (
        (gap_title_sub + int(line_h_sub * len(subtitle_lines))) if subtitle_lines else 0
    )
    tx, ty, tw = _block_origin(tzone, spec.get('title_position', 'top-left'),
                               title_block_w, title_h + glued_sub_h)

    text_color = _block_color(title_color_hex, tx, ty, tw, title_h + glued_sub_h, color_hint)
    if bg_treatment in ('dark_overlay', 'color_block', 'light_overlay'):
        _draw_text_backdrop(
            draw, tx, ty, tw, title_h + glued_sub_h,
            treatment=bg_treatment, paleta=paleta or [], padding=padding,
        )

    y = ty
    for line in title_lines:
        if _hits_logo(tx, y, tw, int(line_h_title)):
            break
        line_x = _x_for_alignment(line, title_font, draw, tx, tw, title_align)
        draw.text((line_x, y), line, fill=text_color + (255,), font=title_font)
        y += int(line_h_title)

    if subtitle_lines and not independent_subtitle:
        y += gap_title_sub
        # cor PROPRIA do subtitulo (distinta do titulo), amostrada na regiao dele
        sub_region_h = int(line_h_sub * len(subtitle_lines))
        sub_color = _block_color(subtitle_color_hex, tx, y, tw, sub_region_h, subtitle_color_hint)
        for line in subtitle_lines:
            if _hits_logo(tx, y, tw, int(line_h_sub)):
                break  # nao desenha por cima do logo
            line_x = _x_for_alignment(line, subtitle_font, draw, tx, tw, subtitle_align)
            draw.text((line_x, y), line, fill=sub_color + (255,), font=subtitle_font)
            y += int(line_h_sub)

    # ----- Bloco SUBTITULO independente (zona propria) ---------------------
    if subtitle_lines and independent_subtitle:
        sub_h = int(line_h_sub * len(subtitle_lines))
        sx, sy, sw = _block_origin(szone, spec.get('subtitle_position', 'center-left'),
                                   sub_block_w, sub_h)
        # Anti-sobreposicao: se o titulo (longo) transbordou sua zona, empurra
        # o subtitulo para baixo do fim real do titulo.
        title_bottom = ty + int(line_h_title * len(title_lines))
        if sy < title_bottom + gap_title_sub:
            sy = title_bottom + gap_title_sub
        sub_color = _block_color(subtitle_color_hex, sx, sy, sw, sub_h, subtitle_color_hint)
        y = sy
        for line in subtitle_lines:
            if _hits_logo(sx, y, sw, int(line_h_sub)):
                break  # nao desenha por cima do logo
            line_x = _x_for_alignment(line, subtitle_font, draw, sx, sw, subtitle_align)
            draw.text((line_x, y), line, fill=sub_color + (255,), font=subtitle_font)
            y += int(line_h_sub)

    # ---- CTA --------------------------------------------------------------
    cta_style = spec.get('cta_style', 'pill')
    cta_position = spec.get('cta_position', 'bottom-center')
    if cta and cta_style != 'none':
        _draw_cta(
            draw, overlay, cta=cta, font=cta_font,
            style=cta_style, position=cta_position,
            canvas_size=(W, H), padding=padding,
            paleta=paleta or [],
        )

    out = Image.alpha_composite(img, overlay).convert('RGB')
    buf = BytesIO()
    out.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


# =====================================================================
# RENDER DO LAYOUT_DOCUMENT (divs do orquestrador) — base do canvas editavel
# =====================================================================

_DOC_ALIGN = {
    'esquerda': 'left', 'left': 'left',
    'centro': 'center', 'center': 'center',
    'direita': 'right', 'right': 'right',
    'justify': 'left', 'justificado': 'left',
}


def _doc_color(img, hex_str, x, y, w, h, paleta):
    """Cor do elemento: HONRA a cor escolhida pelo orquestrador (designer).
    Auto-contraste APENAS quando o orquestrador deixou null/em branco —
    delegacao explicita ao Pillow."""
    if hex_str:
        try:
            return _hex_to_rgb(hex_str)
        except Exception:
            pass
    return _auto_contrast_color(img, x, y, w, h)


def _draw_logo_at(overlay, logo_url, x, y, target_w):
    """Cola o logo numa posicao (x,y) explicita com largura target_w."""
    from io import BytesIO
    from PIL import Image
    try:
        req = urllib.request.Request(logo_url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        logo = Image.open(BytesIO(data)).convert('RGBA')
    except Exception:
        return None
    ratio = target_w / logo.size[0]
    target_h = max(16, int(logo.size[1] * ratio))
    logo = logo.resize((max(16, target_w), target_h), Image.LANCZOS)
    overlay.alpha_composite(logo, (x, y))
    return (x, y, target_w, target_h)


def render_layout_document(png_bytes, elements, paleta=None, fonts=None,
                           logo_url=None):
    """
    Renderiza o layout_document (lista de 'divs' do orquestrador) sobre a
    imagem do Gemini. Cada elemento ja traz posicao/tamanho RELATIVOS (%),
    cor, alinhamento, peso e padding decididos pelo diretor de arte — o Pillow
    so DESENHA (sem heuristica de tamanho; shrink-to-fit so como seguranca).
    fonts: {role: caminho_ttf} resolvido da KB.
    Mesmo modelo que o canvas editavel vai consumir.
    """
    from io import BytesIO
    from PIL import Image, ImageDraw
    img = Image.open(BytesIO(png_bytes)).convert('RGBA')
    W, H = img.size
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    basis = min(W, H)
    fonts = fonts or {}
    elements = elements or []

    def _px(v, total):
        try:
            return int(float(v) / 100.0 * total)
        except (TypeError, ValueError):
            return 0

    # Grafismos primeiro (faixas/selos/linhas) — texto, produto e logo ficam POR CIMA.
    for el in elements:
        if (el.get('role') or '').lower() in ('grafismo', 'shape', 'forma'):
            try:
                _draw_grafismo(draw, el, W, H, paleta)
            except Exception:
                logger.exception('[layout_doc] falha grafismo')

    # Logo primeiro (texto pode evitar sobreposicao se preciso)
    logo_box = None
    for el in elements:
        if (el.get('role') or '').lower() == 'logo' and logo_url:
            try:
                logo_box = _draw_logo_at(
                    overlay, logo_url,
                    _px(el.get('x_pct', 80), W), _px(el.get('y_pct', 4), H),
                    max(48, _px(el.get('width_pct', 14), W)),
                )
            except Exception:
                logger.exception('[layout_doc] falha logo')

    # 1a passada: coleta DADOS CRUS de cada bloco de texto (sem fitar ainda;
    # precisamos saber o gap para o proximo bloco para calcular max_h real).
    raw_blocks = []
    for el in elements:
        role = (el.get('role') or '').lower()
        if role in ('logo', 'grafismo', 'shape', 'forma', 'produto'):
            continue
        content = _strip_emoji((el.get('content') or '').strip())
        if not content:
            continue
        if (el.get('case') or '').lower() in ('upper', 'alta', 'uppercase'):
            content = content.upper()
        weight = (el.get('weight') or 'regular').lower()
        is_bold = weight in ('bold', 'black', 'heavy', 'semibold')
        raw_blocks.append({
            'role': role,
            'content': content,
            'x_pct': float(el.get('x_pct', 5) or 5),
            'y_pct': float(el.get('y_pct', 5) or 5),
            'width_pct': float(el.get('width_pct', 60) or 60),
            'height_pct': float(el.get('height_pct') or 0),  # 0 = sem declaracao
            'padding_pct': float(el.get('padding_pct', 0) or 0),
            'font_size_pct': float(el.get('font_size_pct', 6) or 6),
            'is_bold': is_bold,
            'fpath': fonts.get(role) or fonts.get('titulo') or (_DEJAVU_BOLD if is_bold else _DEJAVU_REG),
            'fb': _DEJAVU_BOLD if is_bold else _DEJAVU_REG,
            'align_raw': el.get('align') or 'left',
            'color_hex': el.get('color'),
        })

    # Ordena por y_pct p/ conseguir derivar max_h = gap ate o proximo bloco.
    raw_blocks.sort(key=lambda b: b['y_pct'])

    # 2a passada: para cada bloco, calcula max_h e roda auto-fit (largura+altura).
    blocks = []
    for i, rb in enumerate(raw_blocks):
        x = _px(rb['x_pct'], W)
        y = _px(rb['y_pct'], H)
        bw = max(60, _px(rb['width_pct'], W))
        pad = _px(rb['padding_pct'], W)
        # max_h: prefere height_pct declarado; senao gap pro proximo bloco
        # (com pequena folga p/ respiro) ou ate o fim do canvas.
        if rb['height_pct'] > 0:
            max_h_pct = rb['height_pct']
        else:
            next_y_pct = raw_blocks[i + 1]['y_pct'] if i + 1 < len(raw_blocks) else 100.0
            max_h_pct = max(4.0, next_y_pct - rb['y_pct'] - 1.0)  # 1% de folga
        max_h = _px(max_h_pct, H)
        start_size = max(14, int(basis * rb['font_size_pct'] / 100))
        min_size = max(12, int(basis * 0.03))  # piso: 3% da menor dim
        font, lines, fit_ok = _fit_text_to_box(
            rb['content'], rb['fpath'], rb['fb'],
            max(40, bw - 2 * pad), max_h, start_size, draw, min_size=min_size,
        )
        if not fit_ok:
            logger.warning(
                '[layout_doc] texto nao coube na caixa (role=%s len=%d max_h_px=%d) '
                'renderizado no min_size %d',
                rb['role'], len(rb['content']), max_h, min_size,
            )
        line_h = font.size * 1.18
        blocks.append({
            'role': rb['role'],
            'x': x, 'y': y, 'bw': bw, 'pad': pad, 'font': font, 'lines': lines,
            'line_h': line_h, 'total_h': int(line_h * len(lines)),
            'align': _DOC_ALIGN.get(str(rb['align_raw']).lower(), 'left'),
            'color_hex': rb['color_hex'],
            '_raw': rb,
            '_min_size': min_size,
            '_max_h': max_h,
        })

    # Hierarquia: confia no designer. Auto-fit ja garante que cada bloco cabe
    # na sua caixa declarada. Se o designer escolheu inverter visualmente,
    # respeitamos — nao impomos ratio.

    gap = int(H * 0.012)
    flow_y = 0
    for b in blocks:
        y = max(b['y'], flow_y)
        color = _doc_color(
            img, b['color_hex'], b['x'] + b['pad'], y, b['bw'] - 2 * b['pad'],
            b['total_h'], paleta,
        )
        yy = y
        for line in b['lines']:
            lx = _x_for_alignment(line, b['font'], draw, b['x'] + b['pad'],
                                  b['bw'] - 2 * b['pad'], b['align'])
            draw.text((lx, yy), line, fill=color + (255,), font=b['font'])
            yy += int(b['line_h'])
        flow_y = y + b['total_h'] + gap

    out = Image.alpha_composite(img, overlay).convert('RGB')
    buf = BytesIO()
    out.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _draw_grafismo(draw, el, W, H, paleta=None):
    """Desenha um elemento grafico (faixa arredondada / selo circular / linha)
    do layout_document. Cor vem do proprio elemento (cor da paleta da marca);
    fallback = primeira cor primaria da paleta. Desenhado ANTES do texto.
    """
    forma = (el.get('forma') or el.get('shape') or 'faixa').lower()
    cor = el.get('cor') or el.get('color') or ''
    rgb = None
    if cor:
        try:
            rgb = _hex_to_rgb(cor)
        except Exception:
            rgb = None
    if not rgb and paleta:
        for c in paleta:
            if c.get('hex'):
                try:
                    rgb = _hex_to_rgb(c['hex'])
                    break
                except Exception:
                    continue
    if not rgb:
        rgb = (0, 172, 70)

    def px(v, total, default=0):
        try:
            return int(float(v) / 100.0 * total)
        except (TypeError, ValueError):
            return default

    x = px(el.get('x_pct', 0), W)
    y = px(el.get('y_pct', 0), H)
    w = px(el.get('width_pct', 30), W)
    h = px(el.get('height_pct', 10), H)
    try:
        op = float(el.get('opacidade', el.get('opacity', 100)))
    except (TypeError, ValueError):
        op = 100.0
    alpha = max(0, min(255, int(op / 100.0 * 255)))
    fill = rgb + (alpha,)

    if forma in ('selo', 'circulo', 'circle', 'badge'):
        d = min(w, h) if (w and h) else max(w, h)
        draw.ellipse([x, y, x + d, y + d], fill=fill)
    elif forma in ('linha', 'divisor', 'line', 'rule'):
        th = max(2, h or px(0.4, H))
        draw.rectangle([x, y, x + w, y + th], fill=fill)
    else:  # faixa / banda / retangulo arredondado
        raio = px(el.get('raio_pct', 4), W)
        # cantos: dict {tl,tr,br,bl: bool} ou lista p/ canto organico (so
        # alguns arredondados, ex: so o canto inferior-direito).
        c = el.get('cantos')
        corners = None
        if isinstance(c, dict):
            corners = (bool(c.get('tl', True)), bool(c.get('tr', True)),
                       bool(c.get('br', True)), bool(c.get('bl', True)))
        elif isinstance(c, (list, tuple)) and c:
            keys = {str(k).lower() for k in c}
            corners = ('tl' in keys, 'tr' in keys, 'br' in keys, 'bl' in keys)
        try:
            if corners is not None:
                draw.rounded_rectangle(
                    [x, y, x + w, y + h], radius=raio, fill=fill, corners=corners
                )
            else:
                draw.rounded_rectangle(
                    [x, y, x + w, y + h], radius=raio, fill=fill
                )
        except Exception:
            draw.rectangle([x, y, x + w, y + h], fill=fill)


# Default layout spec (usado quando nada e passado)
_DEFAULT_LAYOUT_SPEC = {
    'title_position': 'top-left',
    'title_size_pct': 7,
    'title_weight': 'bold',
    'title_color_hint': 'auto_contrast',
    'subtitle_offset': 'below_title',
    'subtitle_size_pct': 3,
    'subtitle_weight': 'regular',
    'logo_position': 'top-right',
    'logo_size_pct': 12,
    'cta_style': 'pill',
    'cta_position': 'bottom-center',
    'alignment': 'left',
    'padding_pct': 5,
    'background_treatment': 'none',
}


def _anchor_to_xy(anchor: str, canvas_size, block_size, padding: int):
    """Converte anchor (9 posicoes) em coordenadas (x, y) do canto sup esq do bloco."""
    W, H = canvas_size
    bw, bh = block_size
    parts = anchor.lower().split('-')
    v = parts[0] if len(parts) > 0 else 'top'
    h = parts[1] if len(parts) > 1 else 'left'

    if h == 'left':
        x = padding
    elif h == 'right':
        x = W - padding - bw
    else:  # center
        x = (W - bw) // 2

    if v == 'top':
        y = padding
    elif v == 'bottom':
        y = H - padding - bh
    else:  # center
        y = (H - bh) // 2

    return x, y


def _x_for_alignment(line, font, draw, base_x, block_w, alignment):
    """Calcula x da linha respeitando alinhamento dentro do bloco."""
    if alignment in ('left', None):
        return base_x
    try:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
    except Exception:
        line_w = len(line) * (font.size if hasattr(font, 'size') else 12) * 0.55
    if alignment == 'right':
        return base_x + (block_w - line_w)
    # center
    return base_x + (block_w - line_w) // 2


def _resolve_text_color(img, x, y, w, h, hint: str, paleta):
    """Retorna RGB tuple para o texto baseado no hint."""
    if hint == 'white':
        return (255, 255, 255)
    if hint == 'black':
        return (20, 20, 20)
    if hint == 'brand_primary':
        return _pick_primary_color(paleta)
    if hint == 'brand_secondary':
        # Tenta segunda cor da paleta
        if len(paleta) >= 2:
            hex_str = paleta[1].get('hex') or ''
            if hex_str:
                return _hex_to_rgb(hex_str)
        return (40, 40, 40)
    if hint == 'brand_primary_safe':
        # Cor primaria da marca, MAS so se tiver contraste suficiente com a
        # regiao; senao cai pro auto_contrast (preto/branco) pra nao ficar
        # ilegivel. Garante "cor da KB" sem sacrificar leitura.
        cand = _pick_primary_color(paleta)
        region_lum = _region_luminance(img, x, y, w, h)
        cand_lum = 0.299 * cand[0] + 0.587 * cand[1] + 0.114 * cand[2]
        if abs(cand_lum - region_lum) >= 70:
            return cand
        return _auto_contrast_color(img, x, y, w, h)
    # auto_contrast: amostra luminancia media da regiao
    return _auto_contrast_color(img, x, y, w, h)


def _region_luminance(img, x, y, w, h) -> float:
    """Luminancia media (0-255) da regiao do canvas onde o texto vai."""
    try:
        x1, y1 = max(0, x), max(0, y)
        x2 = min(img.size[0], x + w)
        y2 = min(img.size[1], y + h)
        crop = img.crop((x1, y1, x2, y2)).convert('RGB').resize((8, 8))
        pixels = list(crop.getdata())
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)
        return 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
    except Exception:
        return 200.0


def _auto_contrast_color(img, x, y, w, h):
    """Amostra cor media da regiao e retorna branco ou preto conforme contraste."""
    return (255, 255, 255) if _region_luminance(img, x, y, w, h) < 140 else (20, 20, 20)


def _draw_text_backdrop(draw, x, y, w, h, treatment, paleta, padding):
    """Desenha caixa atras do texto (color_block, dark_overlay, light_overlay)."""
    pad = padding // 2
    box = (x - pad, y - pad, x + w + pad, y + h + pad)
    if treatment == 'dark_overlay':
        draw.rectangle(box, fill=(0, 0, 0, 160))
    elif treatment == 'light_overlay':
        draw.rectangle(box, fill=(255, 255, 255, 200))
    elif treatment == 'color_block':
        color = _pick_primary_color(paleta or [])
        draw.rectangle(box, fill=color + (220,))


def _draw_cta(draw, overlay, cta: str, font, style: str, position: str,
              canvas_size, padding: int, paleta):
    """Desenha o CTA no canvas. Suporta pill, block, underline, outline."""
    W, H = canvas_size
    try:
        bbox = draw.textbbox((0, 0), cta, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w, text_h = font.size * len(cta) // 2, font.size

    pad_x = int(font.size * 0.8)
    pad_y = int(font.size * 0.45)
    full_w = text_w + 2 * pad_x
    full_h = text_h + 2 * pad_y

    cta_color = _pick_primary_color(paleta or [])
    text_color = (255, 255, 255) if _is_dark_rgb(cta_color) else (20, 20, 20)

    cta_x, cta_y = _anchor_to_xy(
        anchor=position, canvas_size=(W, H),
        block_size=(full_w, full_h), padding=padding,
    )

    if style == 'pill':
        draw.rounded_rectangle(
            [(cta_x, cta_y), (cta_x + full_w, cta_y + full_h)],
            radius=full_h // 2, fill=cta_color + (255,),
        )
        draw.text((cta_x + pad_x, cta_y + pad_y), cta,
                  fill=text_color + (255,), font=font)
    elif style == 'block':
        draw.rectangle(
            [(cta_x, cta_y), (cta_x + full_w, cta_y + full_h)],
            fill=cta_color + (255,),
        )
        draw.text((cta_x + pad_x, cta_y + pad_y), cta,
                  fill=text_color + (255,), font=font)
    elif style == 'outline':
        draw.rounded_rectangle(
            [(cta_x, cta_y), (cta_x + full_w, cta_y + full_h)],
            radius=full_h // 2, outline=cta_color + (255,), width=3,
        )
        draw.text((cta_x + pad_x, cta_y + pad_y), cta,
                  fill=cta_color + (255,), font=font)
    elif style == 'underline':
        # Texto simples + linha embaixo
        draw.text((cta_x + pad_x, cta_y), cta,
                  fill=cta_color + (255,), font=font)
        underline_y = cta_y + text_h + int(font.size * 0.15)
        draw.line(
            [(cta_x + pad_x, underline_y),
             (cta_x + pad_x + text_w, underline_y)],
            fill=cta_color + (255,), width=2,
        )


def _draw_logo_on_overlay(overlay, logo_url: str, position: str,
                          size_pct: float, padding: int, canvas_size):
    """Baixa o logo, redimensiona para size_pct e cola no anchor escolhido."""
    from io import BytesIO
    from PIL import Image

    try:
        req = urllib.request.Request(
            logo_url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception as exc:
        logger.warning('Falha download logo overlay: %s', exc)
        return None

    try:
        logo = Image.open(BytesIO(data)).convert('RGBA')
    except Exception:
        return None

    W, H = canvas_size
    target_w = max(40, int(W * size_pct / 100))
    ratio = target_w / logo.size[0]
    target_h = max(20, int(logo.size[1] * ratio))
    logo = logo.resize((target_w, target_h), Image.LANCZOS)

    x, y = _anchor_to_xy(
        anchor=position, canvas_size=(W, H),
        block_size=(target_w, target_h), padding=padding,
    )
    overlay.alpha_composite(logo, (x, y))
    return (x, y, target_w, target_h)  # caixa do logo (p/ evitar texto por cima)


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    """Quebra texto em linhas respeitando max_width."""
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f'{cur} {w}'
        try:
            bbox = draw.textbbox((0, 0), trial, font=font)
            width = bbox[2] - bbox[0]
        except Exception:
            width = len(trial) * (font.size if hasattr(font, 'size') else 12) * 0.55
        if width <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _hex_to_rgb(hex_str: str) -> tuple:
    h = hex_str.lstrip('#')
    if len(h) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _pick_dark_color(paleta: List[Dict[str, Any]]) -> tuple:
    """Pega a cor mais escura da paleta da marca (para faixas de texto)."""
    darkest = (0, 0, 0)
    darkest_lum = 1.0
    for c in paleta:
        hex_str = c.get('hex') or ''
        if not hex_str:
            continue
        rgb = _hex_to_rgb(hex_str)
        lum = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0
        if lum < darkest_lum:
            darkest_lum = lum
            darkest = rgb
    return darkest


def _pick_primary_color(paleta: List[Dict[str, Any]]) -> tuple:
    """Pega a cor primaria mais saturada (CTA pill)."""
    if not paleta:
        return (99, 102, 241)  # purple-500 fallback
    best = (99, 102, 241)
    best_sat = -1
    for c in paleta:
        hex_str = c.get('hex') or ''
        if not hex_str:
            continue
        rgb = _hex_to_rgb(hex_str)
        # saturacao = (max - min) / max
        mx, mn = max(rgb), min(rgb)
        sat = (mx - mn) / mx if mx > 0 else 0
        if sat > best_sat:
            best_sat = sat
            best = rgb
    return best


def _is_dark_rgb(rgb: tuple) -> bool:
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) < 128
