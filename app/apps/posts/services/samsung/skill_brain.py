"""
"Cérebro" de conteúdo do pipeline Samsung Healthcare (1 chamada Claude).

Ciente do arquétipo: mapeia o tema nas zonas do arquétipo escolhido
(A = foto-topo + agradecimento; B = produto-herói) respeitando o tom de voz
Samsung. Também produz caption + hashtags.

Retorna dict: {structured, model, usage, debug{request,response_raw}}.
"""
import json
import os
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-5'
MAX_TOKENS = 1500
COST_INPUT_PER_M = Decimal('3.0')
COST_OUTPUT_PER_M = Decimal('15.0')

_TONE = """Você é diretor de conteúdo da Samsung Healthcare (assinatura Relentless
Innovation / Samsung Medison) para posts de rede social.

TOM DE VOZ (obrigatório): técnico, objetivo, elegante, seguro, baseado em
evidências, claro, confiante. Parte do valor clínico, não do equipamento. A IA
é apoio ao médico, nunca protagonista nem substituta. NUNCA use:
"revolucionário", "disruptivo", "revolução", "o melhor do mundo", linguagem
emocional exagerada, promessas absolutas, sensacionalismo. Nunca invente fatos
ou números."""

_ZONES = {
    'A': """ARQUÉTIPO A ("Foto-topo + agradecimento" — cursos, institucional com
pessoas, agradecimento a equipe/parceiros). Preencha:
- kicker: rótulo curto (ex.: "CURSO DE", "WORKSHOP", "AGRADECIMENTO"), até ~18
  caracteres. Exibido em CAIXA ALTA.
- title: título principal, Title Case, ATÉ 2 linhas curtas (~34 char/linha).
- body: texto de apoio, ATÉ 3 linhas curtas (~40 char/linha).
- signature_name: nome da pessoa a assinar. EXTRAIA do texto do tema; NUNCA
  invente nome nem use o nome da empresa. "" se o tema não trouxer nome.
- signature_label: "Responsável médico técnico:" se houver signature_name;
  senão "".
- image_prompt: em INGLÊS, cena FOTOGRÁFICA realista para a foto do topo,
  condizente com o tema (grupo de profissionais de saúde / clínica / curso),
  estética Samsung (clara, limpa, minimalista, espaço, tecnologia discreta),
  composição horizontal. NUNCA texto, letras, logos, marcas na imagem.

FORMATO (JSON puro): {"archetype":"A","content":{"kicker":"","title":"","body":"","signature_label":"","signature_name":""},"caption":"","hashtags":[],"image_prompt":""}""",

    'B': """ARQUÉTIPO B ("Produto-herói" — destacar UMA tecnologia/feature; o
produto aparece grande na arte). Preencha:
- title: nome da tecnologia/feature em destaque (curto, ~1-2 linhas, ex.:
  "DeepUSFF", "Elastografia Hepática"). Aparecerá em AZUL. Sem ™ inventado.
- body: descrição do benefício clínico, ATÉ 4 linhas curtas (~34 char/linha),
  começando pelo valor clínico.
- image_prompt: em INGLÊS, cena do EQUIPAMENTO de ultrassom Samsung (o produto)
  em fundo navy escuro degradê, iluminação de estúdio dramática, produto grande
  centralizado. SEM texto, letras, logos ou marcas. (Usado só se o usuário não
  escolher uma imagem de produto.)

FORMATO (JSON puro): {"archetype":"B","content":{"title":"","body":""},"caption":"","hashtags":[],"image_prompt":""}""",
}


def _parse_json(text):
    if not text:
        return None
    s = text.strip()
    if s.startswith('```'):
        s = s.split('```', 2)[1] if '```' in s[3:] else s
        s = s.replace('json', '', 1).strip('` \n')
    try:
        return json.loads(s)
    except Exception:
        import re
        m = re.search(r'\{[\s\S]+\}', s)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def run_skill_brain(*, brief: dict, brand: dict) -> dict:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente')

    archetype = (brief.get('archetype') or 'A').strip().upper()
    zones = _ZONES.get(archetype, _ZONES['A'])
    system_prompt = _TONE + "\n\n" + zones + "\n\nAlém disso produza: caption " \
        "(legenda 2-4 frases, tom Samsung) e hashtags (3-6 palavras, sem #). " \
        "Retorne APENAS o JSON."

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    user_payload = {
        'tema': brief.get('tema'),
        'rede': brief.get('rede'),
        'archetype': archetype,
        'cta_requested': brief.get('cta_requested'),
        'marca': {
            'tom_voz': brand.get('tom_voz'),
            'palavras_recomendadas': brand.get('palavras_recomendadas'),
            'palavras_evitar': brand.get('palavras_evitar'),
            'resumo': brand.get('kb_summary'),
        },
    }
    user_text = ('Gere o JSON para este briefing (responda só o JSON):\n'
                 + json.dumps(user_payload, ensure_ascii=False))

    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system_prompt,
        messages=[{'role': 'user', 'content': user_text}],
    )
    raw = ''.join(getattr(b, 'text', '') for b in resp.content)
    structured = _parse_json(raw) or {}

    usage = getattr(resp, 'usage', None)
    in_tok = getattr(usage, 'input_tokens', 0) or 0
    out_tok = getattr(usage, 'output_tokens', 0) or 0
    cost = (COST_INPUT_PER_M * Decimal(in_tok) + COST_OUTPUT_PER_M * Decimal(out_tok)) / Decimal(1_000_000)

    return {
        'structured': structured,
        'model': MODEL,
        'usage': {'input_tokens': in_tok, 'output_tokens': out_tok,
                  'total_tokens': in_tok + out_tok, 'cost_usd': float(cost)},
        'debug': {'request': user_payload, 'response_raw': raw},
    }
