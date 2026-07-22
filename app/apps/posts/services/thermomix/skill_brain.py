"""
"Cérebro" de conteúdo do pipeline thermomix (1 chamada Claude).

Diferente das outras orgs (copy inteiro por IA), o tmx-A é um template de
EVENTO: quase tudo é fixo ou vem do briefing. O brain EXTRAI do tema os campos
variáveis (título, data, horários, cidade/UF, telefone, apresentador(a)) e
devolve "" quando o tema não trouxer a informação — a task mantém o
conteúdo-exemplo (DEFAULT_CONTENT) nesses casos, editável na Edição Avançada.

Retorna dict: {structured, model, usage, debug{request,response_raw}}.
"""
import json
import logging

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'  # alinhado com todxs/vb/samsung (C1.5)
MAX_TOKENS = 1200

_TONE = """Você é diretor de conteúdo da Thermomix (distribuidor oficial
Vorwerk no Brasil) para posts de rede social de WORKSHOPS/eventos de culinária.

TOM DE VOZ: caloroso, convidativo, prático, próximo — cozinha de verdade para
o dia a dia. Sem sensacionalismo, sem promessas absolutas, sem jargão técnico.
NUNCA invente data, horário, cidade, telefone ou nome de pessoa: esses campos
só saem do briefing; se o briefing não trouxer, devolva ""."""

_ZONES = """ARQUÉTIPO tmx-A ("Workshop: foto full-bleed + infos + retrato").
EXTRAIA do briefing (ou "" quando ausente — NUNCA invente):
- titulo: nome do workshop, ATÉ 2 linhas curtas (~11 caracteres por linha,
  ex.: "Cozinha do Dia a dia"). Se o tema não nomear o workshop, crie um nome
  CURTO fiel ao tema.
- data: SÓ a data no formato DD/MM (ex.: "27/07"). "" se ausente.
- horarios: no formato "às XXhXX ou XXhXX" (ou "às XXhXX" se um só horário).
  "" se ausente.
- selo_cidade: nome da cidade (ex.: "São Paulo"). "" se ausente.
- selo_estado: UF em 2 letras (ex.: "SP"). "" se ausente.
- reserva_2: no formato "do WhatsApp (XX) XXXXX-XXXX." com o telefone do
  briefing. "" se ausente.
- apresentadora: no formato "Com Nome Sobrenome" com o nome do briefing.
  "" se ausente.
- image_prompt: em INGLÊS, foto APETITOSA do prato/comida condizente com o
  tema (editorial food photography, natural light, real everyday Brazilian
  home cooking, generous negative space at the LEFT half for text). NUNCA
  texto, letras, logos, marcas, mãos com anéis, rostos.

FORMATO (JSON puro):
{"content":{"titulo":"","data":"","horarios":"","selo_cidade":"","selo_estado":"","reserva_2":"","apresentadora":""},"caption":"","hashtags":[],"image_prompt":""}"""


def run_skill_brain(*, brief: dict, brand: dict) -> dict:
    from apps.posts.services.artkit.brain import call_brain, parse_json, extract_usage

    system_prompt = _TONE + "\n\n" + _ZONES + "\n\nAlém disso produza: caption " \
        "(legenda 2-4 frases, tom Thermomix, convidando para o workshop) e " \
        "hashtags (3-6 palavras, sem #). Retorne APENAS o JSON."

    user_payload = {
        'tema': brief.get('tema'),
        'rede': brief.get('rede'),
        'archetype': brief.get('archetype'),
        'conteudo_padrao': brief.get('defaults') or {},
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
    usage = extract_usage(resp)

    return {
        'structured': structured,
        'model': MODEL,
        'usage': usage,
        'debug': {'request': user_payload, 'response_raw': raw},
    }
