"""
Skill brain da TODXS — 1 chamada Claude que executa a skill `todxs-social-posts`.

Carrega a skill (SKILL.md + 3 references) como system cacheado (1h) e, a partir
do briefing + dados de marca da KB, devolve em UMA resposta:
  - Content Lock (eyebrow, manchete CAPS <=8 palavras, corpo opcional, footer)
  - Visual Lock (arquetipo A-F + 1 cor de destaque da paleta, rotacionando)
  - single_shot_prompt (prompt pronto p/ Gemini, arte final com texto embutido)
  - caption + hashtags no tom da marca

E a forma mais fiel/eficiente de usar a skill: ela ja foi desenhada para
produzir exatamente isso. Reusa _parse_json/_extract_usage do orquestrador.
"""
import logging
import os
from pathlib import Path

import anthropic

from ..post_orchestrator import _parse_json, _extract_usage

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 4000

_SKILL_DIR = Path(__file__).parent / 'skill'
_SKILL_FILES = ['SKILL.md', 'tone-of-voice.md', 'brand-spec.md', 'prompt-templates.md']


def _load_skill() -> str:
    parts = []
    for name in _SKILL_FILES:
        try:
            parts.append(f'\n\n=== ARQUIVO: {name} ===\n\n')
            parts.append((_SKILL_DIR / name).read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[todxs.skill_brain] arquivo de skill faltando: %s', name)
    return ''.join(parts)


SKILL_TEXT = _load_skill()

SYSTEM_INSTRUCTION = """\
Voce e o MOTOR da skill `todxs-social-posts` (acima). Recebe um briefing de post
da TODXS + um MENU DE ARQUETIPOS validos para o formato e devolve UM objeto JSON,
sem texto fora do JSON.

Logica: Content Lock -> escolher arquetipo -> MAPEAR o conteudo nas zonas do
arquetipo. Voce NAO escreve o prompt de imagem; voce so trava o texto e o mapeia.

Regras duras:
- Escolha o arquetipo SOMENTE entre as letras do menu (validas para este formato).
  Para pecas com mensagem (pauta/educativo/impacto/historia) prefira arquetipos
  COM zonas de texto. D e F sao pecas de marca/capa SEM texto de leitura — so use
  se o briefing for puramente institucional/capa.
- DIMENSIONE o copy ao ARQUETIPO (cada zona traz seu orcamento no menu):
  - zona DISPLAY (titulo grande) = CURTO E IMPACTANTE, poucas palavras, cabe no
    nº de linhas indicado (ex.: arquetipo A = titulo de ~3 a 6 palavras, 2 linhas).
    Pense numa MANCHETE/slogan, nao numa frase.
  - zona de APOIO pode ser mais longa (ate o nº de linhas da zona).
  - todo titulo em CAIXA ALTA. Texto longo vira "apoio", nunca titulo.
- Preencha em "content" SOMENTE as chaves que o arquetipo escolhido usa (veja as
  zonas no menu). Deixe as outras vazias.
- Use SOMENTE cores da paleta do briefing. Escolha UMA cor de destaque
  (+ preto + off-white). NAO repita a "ultima cor usada".
- Nunca invente fatos ou numeros; use apenas o que o briefing fornecer.

REFERENCIA: voce recebe REFERENCIAS reais da marca (resumo do dossie). Escolha a
UNICA que melhor casa com o arquetipo/pilar e devolva seu id em "reference_id".
Em "reference_usage", diga em INGLES o que extrair dela (layout, zonas, bloco de
cor, posicao do selo X / wordmark, hierarquia de fonte) e para NAO copiar a
foto/cores dela.

Formato EXATO da resposta (apenas este JSON):
{
  "pilar": "Noticia|Educativo|Impacto|Historia",
  "archetype": "<uma letra do menu>",
  "archetype_reason": "1 linha do porque",
  "color_name": "nome da cor", "color_hex": "#RRGGBB",
  "content": {
    "kicker": "tema/eyebrow em CAPS, ou vazio",
    "titulo": "manchete em CAPS (use \\n entre linhas se forem 2-3), ou vazio",
    "apoio": "texto de apoio curto em caixa normal, ou vazio",
    "assinatura": "TODXS ou tema, ou vazio",
    "blocos": ["bloco 1", "bloco 2", "bloco 3"],
    "footer": "TODXS",
    "pessoa": "CONCEITO DA FOTO ligado ao TEMA + ao titulo/apoio (se o arquetipo tem foto): QUEM (pessoa LGBTQIA+ cuja identidade queer LEIA CLARAMENTE e seja relevante ao tema - ex.: homem gay, mulher lesbica, pessoa trans/travesti, casal queer; etnia VARIADA, nao so negra) + CONTEXTO/cena/acao que comunica a mensagem. Ex.: rede de apoio -> casal queer se acolhendo; pajuba/cultura -> pessoa queer expressiva em cena cultural. Evite retrato generico que leia so como racial sem o recorte LGBT. Curto e visual. Vazio se sem foto."
  },
  "reference_id": 0,
  "reference_usage": "english: what to extract from the chosen reference (and not copy)",
  "caption": "legenda no tom TODXS",
  "hashtags": ["semacento", "..."]
}
"""


def _build_user_text(*, brief: dict, brand: dict) -> str:
    paleta = brand.get('paleta') or []
    paleta_str = '\n'.join(
        f'  - {c.get("nome")}: {c.get("hex")} ({c.get("tipo")})' for c in paleta
    ) or '  (paleta vazia)'
    rec = ', '.join(brand.get('palavras_recomendadas') or []) or '(nenhuma)'
    evi = ', '.join(brand.get('palavras_evitar') or []) or '(nenhuma)'
    last_color = brief.get('last_color_hex') or '(nenhuma — primeira peca)'

    refs = brand.get('references') or []
    if refs:
        refs_str = '\n'.join(
            f'  [id={r.get("id")}] {r.get("title")}: {r.get("resumo")}' for r in refs
        )
    else:
        refs_str = '  (nenhuma referencia disponivel)'

    from .wireframes import describe_for_brain, WIREFRAMES, zones_for
    fmt = brief.get('fmt') or 'feed'
    force = (brief.get('force_archetype') or '').strip().upper()
    if force and force in WIREFRAMES:
        w = WIREFRAMES[force]
        keys = ', '.join(z['key'] for z in zones_for(force, fmt)) or '(sem texto de leitura)'
        arquetipos_menu = (f"  {force} — {w['name']} | zonas: {keys}\n"
                           f"  >>> USE OBRIGATORIAMENTE o arquetipo {force} (ignore os demais) <<<")
    else:
        arquetipos_menu = describe_for_brain(fmt)

    return f"""\
== BRIEFING DO POST ==
Tema/pauta: {brief.get('tema')}
Rede social: {brief.get('rede')}
Formato: {brief.get('formato_label')}  (ratio {brief.get('ratio_label')}, {brief.get('formato_px')})
CTA solicitado: {'sim' if brief.get('cta_requested') else 'nao'}

== ARQUETIPOS VALIDOS PARA ESTE FORMATO (escolha UMA letra) ==
{arquetipos_menu}

== PALETA DA MARCA (use SOMENTE estes HEX) ==
{paleta_str}
Ultima cor de destaque usada (EVITE repetir): {last_color}

== TOM DE VOZ / DADOS DA MARCA (KB) ==
{brand.get('kb_summary') or ''}

Tom de voz externo: {brand.get('tom_voz') or ''}
Vocabulario recomendado: {rec}
Vocabulario a evitar: {evi}

== REFERENCIAS DE APLICACAO (escolha a melhor e devolva o id em reference_id) ==
{refs_str}

Produza o JSON conforme as instrucoes.
"""


def run_skill_brain(*, brief: dict, brand: dict) -> dict:
    """
    Executa a skill via Claude. Retorna:
      {
        'structured': {...} | None,
        'usage': {...}, 'model': str,
        'debug': {'request': {...sanitizado...}, 'response_raw': str},
      }
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente no ambiente')

    user_text = _build_user_text(brief=brief, brand=brand)

    system_blocks = [
        {'type': 'text', 'text': SKILL_TEXT,
         'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
        {'type': 'text', 'text': SYSTEM_INSTRUCTION,
         'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
    ]

    debug_request = {
        'model': MODEL,
        'system_files': [
            {'arquivo': n, 'chars': len((_SKILL_DIR / n).read_text(encoding='utf-8'))}
            for n in _SKILL_FILES if (_SKILL_DIR / n).exists()
        ],
        'system_instruction': SYSTEM_INSTRUCTION,
        'user': user_text,
    }

    client = anthropic.Anthropic(api_key=api_key, max_retries=6)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_blocks,
        messages=[{'role': 'user', 'content': user_text}],
    )

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    structured = _parse_json(raw)
    usage = _extract_usage(resp, cache_ttl='1h')

    if not structured or 'archetype' not in structured:
        logger.error('[todxs.skill_brain] output invalido. Raw: %s', raw[:400])

    logger.info(
        '[todxs.skill_brain] post brief tema=%r arquetipo=%s cor=%s tokens=%d cost=$%s',
        (brief.get('tema') or '')[:40],
        (structured or {}).get('archetype'),
        (structured or {}).get('color_hex'),
        usage.get('total_tokens', 0), usage.get('cost_usd', 0),
    )

    return {
        'structured': structured,
        'usage': usage,
        'model': MODEL,
        'debug': {'request': debug_request, 'response_raw': raw},
    }
