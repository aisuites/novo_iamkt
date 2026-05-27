"""
Gerador de texto para posts usando Claude Sonnet 4.5.

Substitui o OpenAI Assistant da pipeline N8N (asst_ETNKIHZhITWQtN0WKbPsnRwV).
Recebe contexto da empresa (KB) + briefing + referencias e retorna JSON
estruturado com title, subtitle, image_prompt, caption, hashtags, visual_brief,
cta_text — mesmo schema esperado pelo callback /posts/webhook/callback/.

Pricing Sonnet 4.5: $3/M input + $15/M output. Sistema usa prompt caching
no system message para reduzir custo de input em ~90% em chamadas subsequentes.

Tambem expoe analyze_product_image() que faz Claude Vision analisar a foto
do produto e retornar descricao estruturada para alimentar o prompt do
Gemini (tecnica de "subject preservation" — bracket-naming + negative-naming
+ lista KEEP_UNCHANGED).
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
MAX_TOKENS = 4000
COST_INPUT_PER_M = Decimal('3.0')
COST_OUTPUT_PER_M = Decimal('15.0')
COST_CACHE_WRITE_PER_M = Decimal('3.75')   # 1.25x input
COST_CACHE_READ_PER_M = Decimal('0.30')    # 0.1x input


SYSTEM_PROMPT = """Voce e um copywriter senior especializado em redes sociais.
Sua tarefa: receber um briefing + contexto da marca + referencias visuais e
produzir o conteudo textual de um post pronto para ser ilustrado por uma IA
geradora de imagem.

IDIOMA: TODO o conteudo deve ser em PORTUGUES DO BRASIL — inclusive o
image_prompt e o visual_brief. O gerador de imagem (Gemini 3 Pro) entende
portugues nativamente; nunca retorne ingles.

PRINCIPIOS:
1. Tom de voz: respeite EXATAMENTE o tom descrito no contexto da marca
2. CTA: se cta_requested=true, gere cta_text natural (max 8 palavras). Se false, cta_text=""
3. Hashtags: 5 a 12 hashtags relevantes EM PORTUGUES, retorne array de strings JA
   COM o caractere # no inicio. Ex: ["#produtividade", "#homeoffice", "#dicas"]
4. image_prompt (em PORTUGUES): descricao da CENA/AMBIENTE em volta dos
   elementos visuais, usando ANCORAGEM POR NOME DE ARQUIVO inline.
   - Mencione: ambiente, mood, iluminacao, enquadramento, paleta, elementos
     secundarios (ex: ingredientes, plantas, objetos contextuais)
   - CORES DOS EFEITOS = CORES DA MARCA. Glow, luz colorida, halo ou acento
     de cor devem usar as cores da marca (do contexto acima). NUNCA use azul/
     ciano "de tecnologia" por padrao, salvo se a marca for azul.
   - REGRA ABSOLUTA — NUNCA cite nomes proprios de marca ou produto no
     image_prompt (ex: NAO escreva "Thermomix", "Louis Vuitton", "iPhone",
     "Nike"). Eles ativam priors fortes do gerador de imagem que ignoram a
     foto anexa. Use SEMPRE descritor generico + ancora por arquivo.
   - INLINE ANCHORING — cada imagem uploadeada DEVE ser referenciada com
     o nome de arquivo literal entre parenteses, JUNTO com a regra de
     fidelidade colada inline. Padrao:
       "<descritor generico> da foto anexa (arquivo: NOME_DO_ARQUIVO —
        <REGRA DE FIDELIDADE EM PORTUGUES>)"
     Use o `original_name` informado em "Imagem N: ... (arquivo: ...)"
     na lista de uploads abaixo. Copie o filename EXATAMENTE como aparece.
   - Regras de fidelidade por tipo (SEMPRE encerre com "analise a imagem
     anexada para manter os detalhes"):
       produto/equipamento: "manter a mesma IDENTIDADE: modelo, proporcoes,
         cor, display, materiais, acabamento. Pode ser mostrado de outro
         angulo/posicao que combine com a cena (variacao moderada, sem
         rotacao exagerada nem inventar partes nao visiveis). Analise a
         imagem anexada para manter os detalhes"
       pessoa: "mesma pessoa: mesmo rosto, cabelo, tom de pele. Pose/angulo
         podem variar moderadamente. Nao substituir. Analise a imagem
         anexada para manter os detalhes"
       cenario/local: "usar como ambiente exato da cena: preservar
         arquitetura, iluminacao e atmosfera. Analise a imagem anexada
         para manter os detalhes"
       acessorio/bolsa/objeto: "manter a mesma IDENTIDADE: formato, cor,
         padrao, materiais. Pode variar angulo/posicao moderadamente para
         compor a cena, sem redesenhar. Analise a imagem anexada para
         manter os detalhes"
   - NUNCA descreva cores/formato/material dos elementos uploadeados em
     palavras (alem da regra de fidelidade) — descreve-los gera conflito
     com a imagem real anexada.
   - Quantas imagens houver, mencione cada uma com seu filename — todas
     DEVEM aparecer juntas na cena final.
   - NAO mencione textos a serem renderizados na imagem (papel do title).
   - EXEMPLO MULTI-IMAGEM (1 produto + 1 pessoa + 1 acessorio), assumindo
     que uploads sao thermomix-foto.png, modelo-mulher.jpg, bolsa-lv.jpg:
     "Ambiente sofisticado de cozinha contemporanea com bancada de marmore
     claro, iluminacao natural suave, atmosfera feminina e aspiracional.
     O produto principal da foto anexa (arquivo: thermomix-foto.png —
     reproduzir com fidelidade absoluta: formato, cor, display, materiais,
     acabamento. Sem alteracoes. Analise a imagem anexada para manter os
     detalhes) posicionado em destaque central sobre a bancada. A pessoa
     da foto anexa (arquivo: modelo-mulher.jpg — mesma pessoa, mesmo rosto,
     cabelo, tom de pele, expressao. Nao substituir. Analise a imagem
     anexada para manter os detalhes) interagindo naturalmente com o
     produto. Ao lado, o acessorio da foto anexa (arquivo: bolsa-lv.jpg —
     reproduzir com fidelidade absoluta: formato, cor, padrao, materiais.
     Analise a imagem anexada para manter os detalhes) apoiado
     elegantemente em primeiro plano. Flores frescas em tons pastel em
     vaso, ingredientes gourmet coloridos ao redor, paleta nude e branco,
     mood acolhedor."
   - EXEMPLO 1 PRODUTO SO (upload: equipamento.png):
     "Cozinha minimalista clean com bancada de marmore, luz natural quente
     entrando por janela lateral, o produto da foto anexa (arquivo:
     equipamento.png — reproduzir com fidelidade absoluta: formato, cor,
     display, materiais, acabamento. Sem alteracoes. Analise a imagem
     anexada para manter os detalhes) em destaque central, ingredientes
     frescos coloridos ao redor, atmosfera acolhedora e familiar."
5. visual_brief (em PORTUGUES): instrucao curta (1-2 frases) sobre como aplicar
   a marca no visual (logo, cores, key visual). Complementa o image_prompt.
6. title: max 60 chars, impactante, em portugues
7. subtitle: max 90 chars, complementa o title
8. caption: legenda completa do post (200-500 chars) em portugues

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "title": "...",
  "subtitle": "...",
  "image_prompt": "...",
  "visual_brief": "...",
  "caption": "...",
  "hashtags": ["#palavra1", "#palavra2"],
  "cta_text": "..."
}

Para CARROSSEL (multiplos slides), retorne:
{
  "slides": [
    {"title": "...", "subtitle": "...", "image_prompt": "...", "visual_brief": "..."},
    ...
  ],
  "caption": "...",
  "hashtags": ["#palavra1", ...],
  "cta_text": "..."
}

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def generate_post_text(
    *,
    knowledge_base_summary: str,
    rede_social: str,
    formato: Dict[str, Any],
    tema: str,
    cta_requested: bool,
    is_carousel: bool,
    image_count: int,
    reference_images: Optional[List[Dict[str, Any]]] = None,
    logo_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Gera texto do post via Claude Sonnet 4.5.

    Retorna dict com:
      - structured: dict parseado do JSON (title, subtitle, etc.)
      - raw_text: string crua retornada
      - usage: dict com tokens e custo
      - model: nome do modelo
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente no ambiente')

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    user_text = _build_user_message(
        knowledge_base_summary=knowledge_base_summary,
        rede_social=rede_social,
        formato=formato,
        tema=tema,
        cta_requested=cta_requested,
        is_carousel=is_carousel,
        image_count=image_count,
        reference_images=reference_images or [],
        logo_urls=logo_urls or [],
    )

    # Prompt caching no system para reduzir custo em chamadas repetidas
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                'type': 'text',
                'text': SYSTEM_PROMPT,
                'cache_control': {'type': 'ephemeral'},
            }
        ],
        messages=[
            {'role': 'user', 'content': user_text},
            # Prefill para forcar JSON valido sem cercas markdown
            {'role': 'assistant', 'content': '{'},
        ],
    )

    raw_text = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    structured = _parse_json(raw_text)
    if not structured:
        raise ValueError(f'Falha ao parsear JSON do Claude. Raw: {raw_text[:500]}')

    usage = _extract_usage(resp)

    return {
        'structured': structured,
        'raw_text': raw_text,
        'usage': usage,
        'model': MODEL,
    }


def _build_user_message(
    *,
    knowledge_base_summary: str,
    rede_social: str,
    formato: Dict[str, Any],
    tema: str,
    cta_requested: bool,
    is_carousel: bool,
    image_count: int,
    reference_images: List[Dict[str, Any]],
    logo_urls: List[str],
) -> str:
    """Monta a mensagem do usuario."""
    formato_str = (
        f"{formato.get('name', formato)} "
        f"({formato.get('width', '?')}x{formato.get('height', '?')}px, "
        f"{formato.get('aspect_ratio', '?')})"
        if isinstance(formato, dict) else str(formato)
    )

    parts = [
        '== Contexto da empresa ==',
        knowledge_base_summary,
        '',
        '== Briefing do post ==',
        f'Rede social: {rede_social}',
        f'Formato: {formato_str}',
        f'Tema: {tema}',
        f'CTA solicitado: {"sim" if cta_requested else "nao"}',
    ]

    if is_carousel:
        parts.append(f'Carrossel: SIM ({image_count} slides)')
        parts.append('Gere `slides[]` com 1 item por slide, mais 1 caption geral.')
    else:
        parts.append('Carrossel: nao (post unico)')

    if reference_images:
        parts.append('')
        parts.append('== Imagens UPLOADEADAS pelo usuario (devem aparecer na cena) ==')
        for i, ref in enumerate(reference_images, 1):
            usage_type = (ref.get('usage_type') or '').lower()
            usage_desc = ref.get('usage_description') or ''
            filename = (ref.get('name') or '').strip() or f'upload_{i}'
            # Mapeia tipo para descritor curto que o Claude vai usar no image_prompt
            if 'produto' in usage_type:
                descriptor = 'produto/equipamento'
            elif 'pessoa' in usage_type:
                descriptor = 'pessoa'
            elif 'cenari' in usage_type:
                descriptor = 'cenario/local'
            elif 'fundo' in usage_type or 'background' in usage_type:
                descriptor = 'fundo/textura'
            elif usage_type:
                descriptor = usage_type
            else:
                descriptor = 'imagem de referencia'
            extra = f' — uso indicado: "{usage_desc}"' if usage_desc else ''
            parts.append(
                f'  Imagem {i}: {descriptor} (arquivo: {filename}){extra}'
            )
        parts.append(
            '  >> IMPORTANTE: no image_prompt, referencie TODAS essas imagens '
            'usando o padrao INLINE ANCHORING — "<descritor> da foto anexa '
            '(arquivo: <NOME_EXATO_DO_ARQUIVO> — <regra de fidelidade>)". '
            'Copie cada filename EXATAMENTE como aparece acima. Todas as '
            'imagens devem aparecer juntas na cena final.'
        )

    if logo_urls:
        parts.append('')
        parts.append('== Logotipos disponiveis ==')
        for url in logo_urls:
            parts.append(f'  - {url}')

    parts.append('')
    parts.append('Produza o JSON conforme regras do system prompt.')

    return '\n'.join(parts)


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse seguro do JSON retornado pelo Claude."""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Tenta extrair primeiro objeto {} grande
        m = re.search(r'\{[\s\S]+\}', s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _extract_usage(resp: Any) -> Dict[str, Any]:
    """Extrai usage (tokens + custo) do response da Anthropic."""
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}

    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0

    cost = (
        COST_INPUT_PER_M * Decimal(in_tokens) / Decimal(1_000_000)
        + COST_OUTPUT_PER_M * Decimal(out_tokens) / Decimal(1_000_000)
        + COST_CACHE_WRITE_PER_M * Decimal(cache_write) / Decimal(1_000_000)
        + COST_CACHE_READ_PER_M * Decimal(cache_read) / Decimal(1_000_000)
    )

    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'cache_creation_input_tokens': cache_write,
        'cache_read_input_tokens': cache_read,
        'total_tokens': in_tokens + out_tokens,
        'cost_usd': float(cost),
    }


# ============================================================
# ANALISE VISUAL DE PRODUTO (Vision) — para forcar fidelidade no Gemini
# ============================================================

PRODUCT_ANALYSIS_SYSTEM = """Voce e um especialista em catalogacao visual de produtos.
Analise a imagem anexada (uma foto de produto) e retorne JSON estruturado
descrevendo o produto com PRECISAO. Foco em features VISUAIS distintivas
que diferenciam este modelo especifico de outros modelos similares.

REGRAS:
1. Identifique nome/modelo se for possivel pela visualizacao (ex: "Thermomix TM7
   modelo 2024", "iPhone 15 Pro Max", "Cafeteira Nespresso Vertuo"). Se nao
   conseguir identificar com seguranca, descreva o tipo generico ("robot de
   cozinha multifuncional", "smartphone premium", etc.) — nao invente.
2. Lista de features DISTINTIVAS visuais — coisas que se vc trocasse este
   produto por um similar antigo/novo, a pessoa NOTARIA. Ex: "display tablet
   horizontal de ~10 polegadas SEPARADO do bowl", nao "tem display" generico.
3. Cores observadas com precisao (hex aproximado quando possivel).
4. Lista keep_unchanged: features que NUNCA podem mudar ao recompor o produto
   em uma nova cena.
5. Se reconhecer o modelo, liste em negative_examples versoes similares com as
   quais o gerador de imagem comumente confunde (ex: TM7 vs TM6).

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "product_name": "string — nome especifico se identificavel, senao tipo generico",
  "product_variant_note": "string — observacao breve sobre modelo/versao",
  "distinctive_features": ["lista de descricoes visuais detalhadas"],
  "color_palette_observed": ["#RRGGBB descricao"],
  "keep_unchanged_list": ["lista de features que nao podem ser alteradas"],
  "negative_examples": ["NOT <modelo similar>: <diferenca chave>"]
}

Tudo em PORTUGUES. Retorne APENAS o JSON."""


def analyze_product_image(
    image_bytes: bytes,
    mime_type: str = 'image/png',
    brand_context: str = '',
) -> Dict[str, Any]:
    """
    Analisa visualmente uma foto de produto com Claude Sonnet 4.5 Vision
    e retorna descricao estruturada para alimentar o prompt do Gemini.

    brand_context: string opcional indicando empresa/segmento da KB (ex:
    "Thermomix — fabricante de robos de cozinha multifuncionais Vorwerk").
    Ajuda Claude a identificar com mais precisao a versao/modelo exata
    do produto na imagem.

    Retorna dict com:
      - structured: dict com {product_name, distinctive_features, ...}
      - usage: dict com tokens e custo
      - model: nome do modelo

    Custo: ~$0.005 por chamada (Sonnet 4.5 com 1 imagem + ~300 tokens out).
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente no ambiente')

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    b64 = base64.b64encode(image_bytes).decode('ascii')
    if mime_type not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        mime_type = 'image/png'

    user_intro = (
        'Analise este produto e retorne o JSON conforme instrucoes do system '
        'prompt.'
    )
    if brand_context:
        user_intro += (
            f'\n\nCONTEXTO DA MARCA (para ajudar na identificacao): '
            f'{brand_context}'
        )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=PRODUCT_ANALYSIS_SYSTEM,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': mime_type,
                        'data': b64,
                    },
                },
                {
                    'type': 'text',
                    'text': user_intro,
                },
            ],
        }, {
            'role': 'assistant',
            'content': '{',  # prefill para forcar JSON
        }],
    )

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    structured = _parse_json(raw) or {}

    usage = _extract_usage(resp)
    return {
        'structured': structured,
        'raw_text': raw,
        'usage': usage,
        'model': MODEL,
    }


def download_image_bytes(url: str) -> tuple:
    """Baixa imagem (presigned URL) e retorna (bytes, mime_type)."""
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ct = resp.headers.get('Content-Type', 'image/png').split(';')[0].strip()
    except Exception as exc:
        logger.warning('Falha ao baixar %s: %s', url[:80], exc)
        return None, 'image/png'
    if ct not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        ct = 'image/png'
    return data, ct
