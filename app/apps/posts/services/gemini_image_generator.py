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

    # 6. Se modo='pillow', aplica SMART overlay de texto sobre a imagem
    if text_render_mode == 'pillow':
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

    return {
        'png_bytes': png_bytes,
        'mime_type': mime_type,
        'cost_usd': float(COST_PER_IMAGE_USD),
        'model': model_used,
        'usage': response_json.get('usageMetadata', {}),
        'prompt_text': prompt_text,
        'text_render_mode': text_render_mode,
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
) -> str:
    """
    Prompt SIMPLES — confia na dereferenciacao por imagem ("o produto da
    imagem N anexada"). Sem nomes, sem KEEP_UNCHANGED extenso, sem
    bracket/negative naming. Inspirado em prompts curtos de catalogo
    e lifestyle que funcionam bem com Gemini.

    product_analyses fica como argumento mas e ignorado nesta versao
    (mantido para compatibilidade — pode ser util em futuras iteracoes).
    """
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

    parts = [
        '# TAREFA',
        'Crie uma fotografia profissional para um post de rede social.',
        '',
        '# REFERENCIAS VISUAIS (anexadas ACIMA deste texto, na ordem)',
        attachments_text,
        combination_rules,
        '',
        '# CENA',
        post.image_prompt or '(propor um cenario adequado ao briefing)',
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
    ]

    # Texto a renderizar — colocado no FINAL com isolamento explicito (Fluxo A)
    if text_render_mode == 'pillow':
        parts.extend([
            '',
            '# IMPORTANTE — NAO RENDERIZAR NENHUM TEXTO',
            'Esta cena NAO deve conter NENHUM texto, palavra, slogan, '
            'numero, letra ou caractere. Apenas a cena visual pura com o '
            'produto. Textos serao adicionados depois em pos-processamento.',
        ])
    else:
        parts.extend([
            '',
            '# TEXTO A RENDERIZAR LITERALMENTE NA ARTE',
            'Os textos abaixo sao APENAS para serem ESCRITOS sobre a cena. '
            'NAO use o conteudo deles como descricao visual do produto. '
            'O produto e exclusivamente o que aparece na IMAGEM anexada acima.',
            f'- Titulo: "{title_for_prompt}"',
            f'- Subtitulo: "{subtitle_for_prompt}"',
        ])
        if cta_for_prompt:
            parts.append(f'- CTA: "{cta_for_prompt}"')
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


# ============================================================
# Fluxo C — Overlay de texto via Pillow (Fluxo 2 / text_render_mode='pillow')
# ============================================================

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
    title_size = max(20, int(H * float(spec.get('title_size_pct', 7)) / 100))
    subtitle_size = max(14, int(H * float(spec.get('subtitle_size_pct', 3)) / 100))
    cta_size = max(14, int(H * 0.028))

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
    if logo_url and spec.get('logo_position', 'none') != 'none':
        try:
            _draw_logo_on_overlay(
                overlay, logo_url,
                position=spec['logo_position'],
                size_pct=float(spec.get('logo_size_pct', 12)),
                padding=padding, canvas_size=(W, H),
            )
        except Exception:
            logger.exception('Falha ao desenhar logo no overlay')

    # ---- TEXTO bloco titulo + subtitulo ----------------------------------
    title_lines = _wrap_text(title, title_font, W - 2 * padding, draw)
    subtitle_lines = _wrap_text(subtitle, subtitle_font, W - 2 * padding, draw) if spec.get('subtitle_offset', 'below_title') == 'below_title' else []

    line_h_title = title_size * 1.15
    line_h_sub = subtitle_size * 1.30
    gap_title_sub = int(H * 0.012)

    total_text_h = (
        int(line_h_title * len(title_lines))
        + (gap_title_sub if subtitle_lines else 0)
        + int(line_h_sub * len(subtitle_lines))
    )

    # Anchor do bloco baseado em title_position
    text_x, text_y = _anchor_to_xy(
        anchor=spec.get('title_position', 'top-left'),
        canvas_size=(W, H),
        block_size=(W - 2 * padding, total_text_h),
        padding=padding,
    )

    # ---- Cores: auto_contrast lê luminância da região onde o texto vai ---
    color_hint = spec.get('title_color_hint', 'auto_contrast')
    text_color = _resolve_text_color(
        img, text_x, text_y, W - 2 * padding, total_text_h,
        hint=color_hint, paleta=paleta or [],
    )
    bg_treatment = spec.get('background_treatment', 'none')
    if bg_treatment in ('dark_overlay', 'color_block', 'light_overlay'):
        _draw_text_backdrop(
            draw, text_x, text_y, W - 2 * padding, total_text_h,
            treatment=bg_treatment, paleta=paleta or [], padding=padding,
        )

    # Desenha titulo
    y = text_y
    for line in title_lines:
        line_x = _x_for_alignment(line, title_font, draw, text_x, W - 2 * padding, alignment)
        draw.text((line_x, y), line, fill=text_color + (255,), font=title_font)
        y += int(line_h_title)

    if subtitle_lines:
        y += gap_title_sub
        for line in subtitle_lines:
            line_x = _x_for_alignment(line, subtitle_font, draw, text_x, W - 2 * padding, alignment)
            draw.text((line_x, y), line, fill=text_color + (220,), font=subtitle_font)
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
    # auto_contrast: amostra luminancia media da regiao
    return _auto_contrast_color(img, x, y, w, h)


def _auto_contrast_color(img, x, y, w, h):
    """Amostra cor media da regiao e retorna branco ou preto conforme contraste."""
    try:
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img.size[0], x + w)
        y2 = min(img.size[1], y + h)
        crop = img.crop((x1, y1, x2, y2)).convert('RGB')
        # Amostra reduzida
        small = crop.resize((8, 8))
        pixels = list(small.getdata())
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)
        lum = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
        return (255, 255, 255) if lum < 140 else (20, 20, 20)
    except Exception:
        return (20, 20, 20)


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
        return

    try:
        logo = Image.open(BytesIO(data)).convert('RGBA')
    except Exception:
        return

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
