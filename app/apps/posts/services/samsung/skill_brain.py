"""
"Cérebro" de conteúdo do pipeline Samsung Healthcare (1 chamada Claude).

Ciente do arquétipo: mapeia o tema nas zonas do arquétipo escolhido
(A = foto-topo + agradecimento; B = produto-herói) respeitando o tom de voz
Samsung. Também produz caption + hashtags.

Retorna dict: {structured, model, usage, debug{request,response_raw}}.
"""
import json
import logging

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-5'
MAX_TOKENS = 1500

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


def run_skill_brain(*, brief: dict, brand: dict) -> dict:
    from apps.posts.services.artkit.brain import call_brain, parse_json, extract_usage

    archetype = (brief.get('archetype') or 'A').strip().upper()
    zones = _ZONES.get(archetype, _ZONES['A'])
    system_prompt = _TONE + "\n\n" + zones + "\n\nAlém disso produza: caption " \
        "(legenda 2-4 frases, tom Samsung) e hashtags (3-6 palavras, sem #). " \
        "Retorne APENAS o JSON."

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

    resp, raw = call_brain(model=MODEL, max_tokens=MAX_TOKENS,
                           system=system_prompt, user_text=user_text)
    structured = parse_json(raw) or {}
    usage = extract_usage(resp)  # sem cache blocks -> custo identico ao calculo antigo

    return {
        'structured': structured,
        'model': MODEL,
        'usage': usage,
        'debug': {'request': user_payload, 'response_raw': raw},
    }
