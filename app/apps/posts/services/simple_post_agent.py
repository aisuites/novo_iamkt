"""
Pipeline SIMPLES (v2) — agente unico de texto via OpenAI.

Substitui a cadeia strategist->copywriter->designer (pipeline 'local') por
UMA unica chamada a um "Diretor de Arte + Redator" que devolve title,
subtitle, cta_text, caption e hashtags. A CENA da imagem (image_prompt) NAO
vem mais daqui — quem a cria e o orquestrador (Claude) na Fase 1.

Modelo: gpt-4o-mini | temperature=1.00 | top_p=1.00 (parametros fixos por
decisao de produto para este experimento paralelo).

Disparado pela task generate_post_simple_task (pipeline_used='simple').
So gera TEXTO (fase 1). A fase de imagem sera adicionada depois.
"""

import json
import logging
import re
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

# Parametros fixos do experimento
MODEL = 'gpt-4o-mini'
TEMPERATURE = 1.00
TOP_P = 1.00
MAX_TOKENS = 2000

# Pricing gpt-4o-mini (USD por 1M tokens) — usado so para tracking de custo
_COST_IN_PER_1M = Decimal('0.15')
_COST_OUT_PER_1M = Decimal('0.60')


SYSTEM_PROMPT = """Você é um Diretor de Arte e Redator Publicitário Sênior especializado em social media e branding.
Sua missão é criar um plano de post completo, unindo texto e direção visual, com base no contexto da empresa, rede e formato solicitados. Todo conteúdo gerado deve ser em português do Brasil (mandatório)

🎨 DIRETRIZES GERAIS

Analise o contexto, Contexto da Empresa (Base de Conhecimento), Base de referência visual e as imagens recebidas (logos e referências visuais).
Analise paleta, estilo, aplicação de logo e identidade visual.

Gere título e subtítulo curtos, legíveis e pensados para uso na arte (não só como texto).

Escreva uma caption (legenda) com linguagem natural, envolvente, compatível com o tom da marca e personalizado a cada rede social.

Crie 4–8 hashtags relevantes, sem acentos ou spam, com uso estratégico de maiúsculas/minúsculas.

Escreva um CTA curto (texto a ser aplicado sobre a imagem ou botão de ação quando solicitado). Se vier com cta_requested = não, não crie CTA, ele será null.

Proíba o uso de marcas concorrentes, nomes próprios de terceiros ou logotipos não pertencentes à marca.

Retorne APENAS um JSON válido conforme o schema descrito abaixo (sem explicações extras).

📱 FOCO POR REDE

LinkedIn → tom institucional, técnico e inspirador.

Instagram → emocional, visual e humano.

Stories → descritivo e narrativo; indique o ritmo visual.

### Regras de Saída (obrigatórias):
- A saída DEVE ser **um único objeto JSON válido**, sem markdown, sem comentários, sem quebras de linha desformatadas.
- **Não use cercas como ``` ou tags como `json:`.**
- **Cada valor deve estar corretamente fechado com aspas, colchetes e chaves, obedecendo rigorosamente ao schema.**

Schema json obrigatório de saida:
{
  "title": "string",
  "subtitle": "string",
  "cta_text": "string",
  "caption": "string",
  "hashtags": ["string"]
}"""


def _build_user_text(*, kb_summary, rede, formato, is_carousel, image_count,
                     tema, cta_requested, logo_urls, reference_descriptions):
    """Monta a mensagem de contexto enviada ao agente."""
    refs_block = '\n'.join(
        f'- {r}' for r in reference_descriptions if r
    ) or 'Nenhuma descrição de referência disponível.'

    logos_block = '\n'.join(f'- {u}' for u in logo_urls if u) or 'Nenhum logo selecionado.'

    return f"""A seguir está o contexto completo da empresa e os detalhes da solicitação de post.

Use essas informações para criar um plano de arte e copy para um post de redes sociais, SEMPRE NO ESTILO ULTRA REALISTA E HUMANIZADO
seguindo as instruções do sistema e retornando APENAS o JSON no formato especificado.

---

📌 **Contexto da Empresa (Base de Conhecimento)**
{kb_summary}

📌 **Solicitação de Post**
Rede: {rede}
Formato: {formato}
Carrossel: {'sim' if is_carousel else 'nao'}
Tema: {tema}
Quantidade de imagens: {image_count}
cta_requested: {'sim' if cta_requested else 'nao'}

📎 **Imagens e Logos**
Logos:
{logos_block}

Imagens de referência (descrições já coletadas na KB + anexadas no modal, conforme o objetivo escolhido):
{refs_block}
"""


def _parse_json(text: str) -> dict:
    """Parser tolerante: tenta json.loads direto, depois extrai o maior bloco {...}."""
    if not text:
        return {}
    text = text.strip()
    # Remove cercas markdown caso o modelo desobedeça
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]+\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return {}


def generate_simple_post(*, kb_summary, rede, formato, is_carousel, image_count,
                         tema, cta_requested, logo_urls=None,
                         reference_descriptions=None):
    """
    Chama o agente unico (OpenAI gpt-4o-mini) e devolve o plano de post.

    Retorna: {'structured': dict, 'usage': dict, 'model': str}
    Lanca RuntimeError se faltar API key ou a resposta nao for parseavel.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY ausente — pipeline simples desabilitado')

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    user_text = _build_user_text(
        kb_summary=kb_summary,
        rede=rede,
        formato=formato,
        is_carousel=is_carousel,
        image_count=image_count,
        tema=tema,
        cta_requested=cta_requested,
        logo_urls=logo_urls or [],
        reference_descriptions=reference_descriptions or [],
    )

    kwargs = dict(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_text},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
    )
    try:
        resp = client.chat.completions.create(
            response_format={'type': 'json_object'}, **kwargs
        )
    except TypeError:
        # SDK antigo sem response_format — depende do parser tolerante
        resp = client.chat.completions.create(**kwargs)

    content = resp.choices[0].message.content or ''
    structured = _parse_json(content)
    if not structured:
        raise RuntimeError('Resposta do agente simples nao e JSON parseavel')

    # cta_requested=nao -> garante cta_text null
    if not cta_requested:
        structured['cta_text'] = None

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
        'total_tokens': int(getattr(u, 'total_tokens', in_tok + out_tok) or 0),
        'cost_usd': float(round(cost, 6)),
    }

    logger.info(
        '[posts.simple] generate_simple_post OK model=%s in=%s out=%s cost=$%s',
        MODEL, in_tok, out_tok, usage['cost_usd'],
    )
    return {'structured': structured, 'usage': usage, 'model': MODEL}
