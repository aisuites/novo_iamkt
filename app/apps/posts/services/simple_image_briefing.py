"""
Pipeline SIMPLES (v2) — Fase 2, Etapa 2: Agente de Regras / Briefing Resolver.

Valida o que foi preenchido no modal e resolve a hierarquia de decisao:

    1. Selecoes do modal = REGRA DE OURO
       - referencia selecionada -> seus objetivos/aspectos sao obrigatorios
       - logo selecionado -> se houve logo_position, ela manda; senao busca
         descricao de aplicacao numa ref; senao fica a criterio do gerador
    2. Topico nao coberto na selecao -> segue a KB
    3. Nem na KB -> criatividade/escolha do agente gerador de imagem

Saida: JSON estruturado (briefing) consumido pelo aplicador de texto (Gemini).
Modelo: OpenAI gpt-4o-mini (coerente com a Fase 1).
"""

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

MODEL = 'gpt-4o-mini'
TEMPERATURE = 0.3
MAX_TOKENS = 1500


SYSTEM_PROMPT = """Você é um Diretor de Arte que resolve REGRAS de layout para um post de redes sociais.
Recebe: as seleções do modal (referências e seus objetivos, logo e posição), a base de conhecimento da marca (KB) e os textos já definidos.
Sua missão é resolver cada decisão de design seguindo ESTRITAMENTE esta hierarquia de prioridade:

1. SELEÇÕES DO MODAL = regra de ouro (obrigatórias, não podem ser contrariadas).
   - Se há referência selecionada: seus objetivos/aspectos são obrigatórios.
   - Se há logo: quando há posição escolhida, ela é obrigatória; se não há posição
     escolhida, verifique se alguma referência selecionada tem descrição de aplicação
     do logo — se tiver, siga-a; se não, deixe a critério do gerador de imagem (livre).
2. Quando um tópico NÃO foi abordado nas seleções -> siga a KB (paleta, tipografia, layout da marca).
3. Quando não há nem na KB -> deixe a critério criativo do gerador de imagem.

Para cada decisão, marque a ORIGEM: "modal" | "kb" | "criatividade".

Retorne APENAS um JSON válido (sem markdown, sem comentários) neste schema:
{
  "logo": {"usar": true/false, "posicao": "string ou null", "origem": "modal|kb|criatividade"},
  "referencias": [{"objetivo": "string", "origem": "modal|kb"}],
  "paleta_hex": ["#RRGGBB"],
  "tipografia": "string (qual fonte/estilo usar e por quê)",
  "zona_texto": "string (onde os textos devem ficar, respeitando a marca)",
  "elementos_graficos": "string (overlays/formas/texturas, se houver)",
  "diretrizes": "string (consolidação das regras de ouro + fallbacks aplicados)",
  "decisoes_livres": ["string (o que ficou a critério criativo do gerador)"]
}"""


def _parse_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def resolve_briefing(*, kb_summary, modal_selections, textos, formato):
    """Resolve as regras do modal e devolve o briefing estruturado.

    modal_selections: dict com has_logo, logo_position, reference_aspects,
                      references_usage_description, reference_descriptions[]
    textos: dict com title/subtitle/cta da Fase 1
    Retorna: dict (briefing). Em falha, devolve um briefing minimo seguro.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY ausente')

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    user_text = (
        '📌 SELEÇÕES DO MODAL\n'
        f'{json.dumps(modal_selections, ensure_ascii=False, indent=2)}\n\n'
        '📌 TEXTOS JÁ DEFINIDOS (Fase 1)\n'
        f'{json.dumps(textos, ensure_ascii=False, indent=2)}\n\n'
        f'📌 FORMATO FINAL\n{formato}\n\n'
        '📌 BASE DE CONHECIMENTO DA MARCA (KB)\n'
        f'{kb_summary}\n'
    )

    kwargs = dict(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_text},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    try:
        resp = client.chat.completions.create(response_format={'type': 'json_object'}, **kwargs)
    except TypeError:
        resp = client.chat.completions.create(**kwargs)

    briefing = _parse_json(resp.choices[0].message.content or '')
    if not briefing:
        logger.warning('[posts.simple] briefing nao parseavel — usando fallback minimo')
        briefing = {
            'logo': {
                'usar': bool(modal_selections.get('has_logo')),
                'posicao': modal_selections.get('logo_position') or None,
                'origem': 'modal' if modal_selections.get('logo_position') else 'criatividade',
            },
            'referencias': [],
            'paleta_hex': [],
            'tipografia': '',
            'zona_texto': '',
            'elementos_graficos': '',
            'diretrizes': 'Fallback: seguir KB e boas praticas de design.',
            'decisoes_livres': ['layout completo a criterio do gerador'],
        }

    u = getattr(resp, 'usage', None)
    usage = {
        'input_tokens': int(getattr(u, 'prompt_tokens', 0) or 0),
        'output_tokens': int(getattr(u, 'completion_tokens', 0) or 0),
        'total_tokens': int(getattr(u, 'total_tokens', 0) or 0),
        'cost_usd': 0.0,
    }
    # custo gpt-4o-mini
    from decimal import Decimal
    usage['cost_usd'] = float(
        Decimal(usage['input_tokens']) / Decimal(1_000_000) * Decimal('0.15')
        + Decimal(usage['output_tokens']) / Decimal(1_000_000) * Decimal('0.60')
    )

    logger.info('[posts.simple] briefing resolvido (logo=%s pos=%s)',
                briefing.get('logo', {}).get('usar'), briefing.get('logo', {}).get('posicao'))
    return {'briefing': briefing, 'usage': usage, 'model': MODEL}
