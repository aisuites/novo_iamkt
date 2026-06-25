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
da TODXS e devolve UM objeto JSON, sem texto fora do JSON.

Siga a logica da skill: Content Lock -> Visual Lock -> prompt single-shot.

Regras duras:
- A manchete vai em CAIXA ALTA, curta e com peso (<= 8 palavras). Texto longo vira
  corpo/subtitulo, nunca manchete.
- Use SOMENTE cores da paleta fornecida no briefing. Escolha UMA cor de destaque
  (+ preto + off-white). NAO repita a "ultima cor usada" informada.
- Escolha o arquetipo (A-F) pelo pilar/conteudo, conforme prompt-templates.md.
- O single_shot_prompt deve seguir as "Regras de ouro do single-shot": estrutura
  em ingles, TEXTO VISIVEL citado em portugues entre aspas com TODOS os acentos,
  zonas de texto (wireframe), estilo tipografico descrito (as fontes Ana Banana /
  Vinila nao existem no modelo), paleta restrita aos HEX informados e a lista de
  negativos. Respeite o ratio e o orcamento de texto do formato informado.
- O single_shot_prompt deve renderizar a ARTE FINAL JA COM O TEXTO (single-shot),
  pois nao havera etapa de Pillow.
- Nunca invente fatos ou numeros; use apenas o que o briefing fornecer.

LAYOUT / BLOCO SOLIDO (regra de aplicacao da marca):
- A marca aplica o texto sobre um CAMPO SOLIDO DE COR, nao flutuando sobre a foto.
  Quando houver foto, prefira split (foto numa metade + bloco solido de cor na
  outra, com o texto no bloco) — arquetipos A, D e E. So use texto direto sobre a
  foto (arquetipo B/F) se a area do texto for calma e o contraste garantido.
- A manchete e GIGANTE (ocupa ~40-55% da peca), grid rigido, margens generosas.

REFERENCIA DE APLICACAO (obrigatorio):
- Voce recebe uma lista de REFERENCIAS reais da marca (com resumo do dossie:
  zonas de texto, blocos, paleta, se tem foto). ESCOLHA a UNICA que melhor casa
  com o arquetipo/pilar/formato desta peca e devolva seu id em "reference_id".
- Em "reference_usage", escreva uma instrucao curta em INGLES do que o modelo de
  imagem deve EXTRAIR dessa referencia: a estrutura/zonas de texto, o BLOCO SOLIDO
  de cor atras do texto, a posicao do selo X / wordmark e a hierarquia/tamanho de
  fonte. Diga explicitamente para NAO copiar a foto/pessoa nem as cores da
  referencia (usar a nossa cor escolhida e o nosso texto).

Formato EXATO da resposta (apenas este JSON):
{
  "pilar": "Noticia|Educativo|Impacto|Historia",
  "content_lock": {
    "eyebrow": "string em CAPS (ex.: NOTICIA, IMPACTO E DIVERSIDADE)",
    "manchete": "string em CAPS, <= 8 palavras",
    "corpo": "string curta ou vazia",
    "footer": "TODXS"
  },
  "visual_lock": {
    "archetype": "A|B|C|D|E|F",
    "archetype_reason": "1 linha do porque",
    "color_name": "nome da cor escolhida",
    "color_hex": "#RRGGBB (da paleta)"
  },
  "reference_id": 0,
  "reference_usage": "english instruction: what to extract from the chosen reference (layout, reserved solid color block, text zones, X seal position, font hierarchy) and to NOT copy its photo/colors",
  "single_shot_prompt": "prompt completo para o modelo de imagem",
  "caption": "legenda para a rede no tom TODXS",
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

    return f"""\
== BRIEFING DO POST ==
Tema/pauta: {brief.get('tema')}
Rede social: {brief.get('rede')}
Formato: {brief.get('formato_label')}  (ratio {brief.get('ratio_label')}, {brief.get('formato_px')})
CTA solicitado: {'sim' if brief.get('cta_requested') else 'nao'}

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

    if not structured or 'single_shot_prompt' not in structured:
        logger.error('[todxs.skill_brain] output invalido. Raw: %s', raw[:400])

    logger.info(
        '[todxs.skill_brain] post brief tema=%r arquetipo=%s cor=%s tokens=%d cost=$%s',
        (brief.get('tema') or '')[:40],
        (structured or {}).get('visual_lock', {}).get('archetype'),
        (structured or {}).get('visual_lock', {}).get('color_hex'),
        usage.get('total_tokens', 0), usage.get('cost_usd', 0),
    )

    return {
        'structured': structured,
        'usage': usage,
        'model': MODEL,
        'debug': {'request': debug_request, 'response_raw': raw},
    }
