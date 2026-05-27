"""
Visual Asset Analyzer — agente Claude Sonnet 4.5 Vision que produz um
DOSSIE VISUAL OBJETIVO de uma imagem de referencia da KB.

A analise descreve a IMAGEM EM SI (composicao, iluminacao, grid matematico,
pessoas, ambiente, relacao texto x imagem, logo, assets, paleta, tipografia,
mood) + um recreation_prompt detalhado. NAO depende da intencao do usuario
(essa e aplicada depois, no momento de gerar o post).

Roda UMA vez por imagem (no upload / sweep no save / fallback no post) e o
resultado fica gravado em ReferenceImage.visual_analysis. Nunca reanalisa
salvo se for uma imagem nova.

Custo: ~$0.006-0.012 por chamada (Sonnet 4.5 com 1 imagem + ~700 tokens out).
"""

import base64
import json
import logging
import os
import re
import urllib.request
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-5'
# Dossie completo (com pessoas + ambiente + grid + recreation_prompt) chega a
# ~3-4k tokens. 5000 da folga para nao truncar o JSON (truncar = parse falha).
MAX_TOKENS = 5000
COST_INPUT_PER_M = Decimal('3.0')
COST_OUTPUT_PER_M = Decimal('15.0')


SYSTEM_PROMPT = """Voce e um diretor de arte senior catalogando uma imagem de
referencia visual para uma marca. Sua tarefa: ANALISAR a imagem anexada e
extrair TUDO que compoe a composicao visual dela, de forma OBJETIVA e
ESTRUTURADA, para que esse dossie possa ser reutilizado depois ao gerar novas
artes no mesmo estilo.

IMPORTANTE: descreva a IMAGEM EM SI. Nao tente adivinhar para que ela sera
usada. Seja concreto, especifico e acionavel — nada de "bonito", "agradavel",
"profissional" sozinhos.

========================================
REGRA INVIOLAVEL — NUNCA CITE NOMES DE MARCA OU PRODUTO
========================================
No recreation_prompt e em qualquer descritor, NUNCA escreva nomes proprios de
marca, modelo de produto ou termos que ativariam priors de um gerador de
imagem (ex: "Thermomix", "TM7", "iPhone", "Louis Vuitton", "Nike"). Descreva
por categoria generica + posicao + caracteristicas visuais. Ex: "o produto
principal centralizado no terco medio, superficie metalica escura".

========================================
O QUE EXTRAIR (preencha tudo que for observavel)
========================================
- descricao_geral: 1-2 frases do que a imagem mostra no todo.
- is_humanizada: true se ha pessoa(s) humana(s) visivel(is), senao false.
- pessoas: lista (vazia se nao humanizada). Para cada pessoa: faixa_etaria,
  genero_aparente, tom_pele, cabelo, expressao, vestuario, pose, enquadramento.
- ambiente: {tipo (interno/externo), descricao, estilo, elementos_cenario}.
- composicao: {enquadramento (close/medio/aberto), foco_principal,
  profundidade_de_campo, regra_dos_tercos (descreva onde caem os pontos de
  interesse), simetria, respiro/espaco_negativo}.
- iluminacao: {tipo (natural/artificial/mista), direcao, temperatura
  (quente/neutra/fria), intensidade, sombras, qualidade (dura/difusa)}.
- paleta_observada: lista de cores dominantes como {hex, nome, papel
  (dominante/secundaria/acento)}.
- tipografia_observada: {presente (bool), estilo (serif/sans/script/display),
  peso, caixa (alta/baixa/mista), descricao}. Vazio se nao ha texto.
- texto_x_imagem: {ha_texto (bool), posicao_texto (use as 9 ancoras:
  top-left..bottom-right), alinhamento (left/center/right), relacao_com_sujeito
  (sobreposto/ao_lado/area_limpa), contraste_fundo}.
- logo_na_referencia: {presente (bool), posicao (9 ancoras), tamanho_relativo,
  aplicacao (sobre_foto/area_solida/transparente), fundo}. Vazio se nao ha logo.
- assets_grafismos: lista de elementos graficos (formas, faixas, padroes,
  icones, molduras): {tipo, posicao, cor, estilo, funcao}.
- grid: {colunas (estimativa), zonas: lista de {nome, x_pct, y_pct,
  largura_pct, altura_pct, conteudo}, alinhamento_geral, margens_pct}.
  As zonas sao um mapa matematico aproximado (0-100) de onde cada bloco de
  conteudo (sujeito, titulo, logo, cta, grafismos) esta posicionado no canvas.
- mood: 2-4 palavras de atmosfera/sensacao (ex: "acolhedor, aspiracional").
- estilo_visual: rotulo do estilo (ex: "minimalista editorial",
  "flat-lay gourmet", "lifestyle quente").
- recreation_prompt: prompt DETALHADO em PORTUGUES (4-8 frases) que, dado a um
  gerador de imagem, recriaria uma arte no MESMO estilo/composicao/iluminacao.
  Descreva ambiente, luz, enquadramento, paleta, disposicao dos elementos e do
  espaco para texto. Sem citar marca/produto (REGRA INVIOLAVEL).

========================================
FORMATO DE SAIDA (JSON puro, sem markdown)
========================================
{
  "descricao_geral": "...",
  "is_humanizada": false,
  "pessoas": [],
  "ambiente": {"tipo": "...", "descricao": "...", "estilo": "...", "elementos_cenario": ["..."]},
  "composicao": {"enquadramento": "...", "foco_principal": "...", "profundidade_de_campo": "...", "regra_dos_tercos": "...", "simetria": "...", "espaco_negativo": "..."},
  "iluminacao": {"tipo": "...", "direcao": "...", "temperatura": "...", "intensidade": "...", "sombras": "...", "qualidade": "..."},
  "paleta_observada": [{"hex": "#RRGGBB", "nome": "...", "papel": "dominante"}],
  "tipografia_observada": {"presente": false, "estilo": "", "peso": "", "caixa": "", "descricao": ""},
  "texto_x_imagem": {"ha_texto": false, "posicao_texto": "", "alinhamento": "", "relacao_com_sujeito": "", "contraste_fundo": ""},
  "logo_na_referencia": {"presente": false, "posicao": "", "tamanho_relativo": "", "aplicacao": "", "fundo": ""},
  "assets_grafismos": [{"tipo": "...", "posicao": "...", "cor": "...", "estilo": "...", "funcao": "..."}],
  "grid": {"colunas": 0, "zonas": [{"nome": "...", "x_pct": 0, "y_pct": 0, "largura_pct": 0, "altura_pct": 0, "conteudo": "..."}], "alinhamento_geral": "", "margens_pct": 0},
  "mood": "...",
  "estilo_visual": "...",
  "recreation_prompt": "..."
}

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def analyze_reference_image(
    image_url: str,
) -> Optional[Dict[str, Any]]:
    """
    Analisa uma imagem de referencia e retorna o dossie visual objetivo.

    Args:
        image_url: URL (presigned) da imagem.

    Retorna dict com:
      - structured: dict do JSON parseado (o dossie)
      - raw_text: string crua
      - usage: dict {input_tokens, output_tokens, total_tokens, cost_usd}
      - model: nome do modelo
    Ou None em caso de falha (download/parse/API).
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[visual_analyzer] ANTHROPIC_API_KEY ausente — skip')
        return None

    b64, mime = _download_to_base64(image_url)
    if not b64:
        logger.warning('[visual_analyzer] falha ao baixar imagem: %s', image_url[:80])
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {'type': 'base64', 'media_type': mime, 'data': b64},
                        },
                        {
                            'type': 'text',
                            'text': (
                                'Analise esta imagem de referencia e produza o '
                                'JSON do dossie visual conforme o system prompt.'
                            ),
                        },
                    ],
                },
                {'role': 'assistant', 'content': '{'},  # prefill forca JSON
            ],
        )
    except Exception:
        logger.exception('[visual_analyzer] erro Claude')
        return None

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    structured = _parse_json(raw)
    if not structured:
        logger.error('[visual_analyzer] parse JSON falhou. Raw: %s', raw[:400])
        return None

    usage = _extract_usage(resp)
    logger.info(
        '[visual_analyzer] dossie OK | humanizada=%s | tokens=%d | cost=$%s',
        structured.get('is_humanizada'), usage.get('total_tokens', 0),
        usage.get('cost_usd', 0),
    )

    return {
        'structured': structured,
        'raw_text': raw,
        'usage': usage,
        'model': MODEL,
    }


GRAFICO_SYSTEM_PROMPT = """Voce e um designer grafico senior catalogando um
ELEMENTO GRAFICO da marca (grafismo, asset) — NAO uma foto/cena. Pode ser uma
forma, padrao, moldura, faixa, icone, textura, divisor ou selo. Sua tarefa:
descrever o elemento de forma OBJETIVA e ESTRUTURADA, mais COMO e ONDE aplica-lo
numa arte. Esse dossie e gravado e reutilizado depois.

Seja concreto. Nada de "bonito"/"moderno" sozinhos.

REGRA INVIOLAVEL: NUNCA cite nome de marca/produto.

O QUE EXTRAIR:
- descricao_geral: 1-2 frases do que o elemento e.
- tipo_elemento: forma_geometrica | padrao | moldura_borda | faixa | icone |
  textura | divisor | selo_badge | ilustracao | outro.
- formas: descricao das formas/linhas que compoem o elemento.
- cores: lista de {hex, nome, papel}.
- tem_transparencia: true se ha areas transparentes (fundo recortado).
- estilo: flat | gradiente | contorno | 3d | organico | geometrico | linha_fina | outro.
- orientacao_visual: vertical | horizontal | radial | quadrada | livre.
- complexidade: simples | media | complexa.
- onde_aplicar: lista de posicoes sugeridas numa arte (ex: "canto superior
  direito", "faixa no rodape", "moldura nas bordas", "fundo/marca dagua").
- como_aplicar: regras de uso (escala relativa, respiro, sobreposicao).
- contraste_fundo_ideal: claro | escuro | qualquer.
- texto_legivel_sobre: true se da para colocar texto por cima sem poluir.
- recreation_prompt: prompt curto (2-4 frases) em PORTUGUES para recriar este
  elemento grafico (formas, cores, estilo), sem citar marca.

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "descricao_geral": "...",
  "tipo_elemento": "...",
  "formas": "...",
  "cores": [{"hex": "#RRGGBB", "nome": "...", "papel": "dominante"}],
  "tem_transparencia": false,
  "estilo": "...",
  "orientacao_visual": "...",
  "complexidade": "...",
  "onde_aplicar": ["..."],
  "como_aplicar": "...",
  "contraste_fundo_ideal": "...",
  "texto_legivel_sobre": false,
  "recreation_prompt": "..."
}

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def analyze_brand_asset(
    image_url: str,
    file_format: str = 'png',
) -> Optional[Dict[str, Any]]:
    """
    Analisa um BrandgraficModule (grafismo/elemento) e retorna o dossie.
    SVG e rasterizado para PNG antes da Vision (Claude nao le SVG direto).

    Mesmo contrato de analyze_reference_image: retorna
    {structured, raw_text, usage, model} ou None.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[visual_analyzer] ANTHROPIC_API_KEY ausente — skip')
        return None

    raw_bytes, mime = _download_bytes(image_url)
    if not raw_bytes:
        logger.warning('[visual_analyzer] falha ao baixar grafismo: %s', image_url[:80])
        return None

    if (file_format or '').lower() == 'svg' or 'svg' in mime:
        png = _svg_to_png(raw_bytes)
        if not png:
            logger.warning('[visual_analyzer] SVG nao rasterizado (lib ausente?) — skip')
            return None
        raw_bytes, mime = png, 'image/png'

    if mime not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        mime = 'image/png'
    b64 = base64.b64encode(raw_bytes).decode('ascii')

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=GRAFICO_SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': b64}},
                        {'type': 'text', 'text': 'Analise este elemento grafico e produza o JSON conforme o system prompt.'},
                    ],
                },
                {'role': 'assistant', 'content': '{'},
            ],
        )
    except Exception:
        logger.exception('[visual_analyzer] erro Claude (grafismo)')
        return None

    raw = '{' + ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    structured = _parse_json(raw)
    if not structured:
        logger.error('[visual_analyzer] parse JSON grafismo falhou. Raw: %s', raw[:400])
        return None

    usage = _extract_usage(resp)
    logger.info(
        '[visual_analyzer] dossie grafismo OK | tipo=%s | tokens=%d | cost=$%s',
        structured.get('tipo_elemento'), usage.get('total_tokens', 0),
        usage.get('cost_usd', 0),
    )
    return {'structured': structured, 'raw_text': raw, 'usage': usage, 'model': MODEL}


def _svg_to_png(svg_bytes: bytes) -> Optional[bytes]:
    """Rasteriza SVG -> PNG. Usa PyMuPDF (ja instalado); cai para cairosvg /
    svglib se disponiveis. Retorna None se nenhuma lib funcionar."""
    # PyMuPDF (fitz) — ja presente no projeto, sem dependencia extra
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=svg_bytes, filetype='svg')
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
        return pix.tobytes('png')
    except Exception:
        pass
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes, output_width=1024)
    except Exception:
        pass
    try:
        import io
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        drawing = svg2rlg(io.BytesIO(svg_bytes))
        if drawing is None:
            return None
        out = io.BytesIO()
        renderPM.drawToFile(drawing, out, fmt='PNG')
        return out.getvalue()
    except Exception:
        logger.warning('[visual_analyzer] rasterizacao SVG indisponivel')
        return None


def _download_bytes(url: str) -> Tuple[Optional[bytes], str]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ct = resp.headers.get('Content-Type', 'image/png').split(';')[0].strip()
        return data, ct
    except Exception:
        return None, 'image/png'


def _download_to_base64(url: str) -> Tuple[Optional[str], str]:
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
        COST_INPUT_PER_M * Decimal(in_tokens) / Decimal(1_000_000)
        + COST_OUTPUT_PER_M * Decimal(out_tokens) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'total_tokens': in_tokens + out_tokens,
        'cost_usd': float(cost),
    }
