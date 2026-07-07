"""
Skill brain da VB Gastronomia — 1 chamada Claude que, a partir do tema + marca +
arquetipo, devolve:
  - o TEXTO das zonas do arquetipo (titulo, apoio, ...), no tom da VB;
  - a RECEITA da ILUSTRAÇÃO (JSON do illustrate.py), de um objeto/comida que se
    RELACIONA com o texto do post (ex.: tema fala de peixe -> ilustração de peixe);
  - caption + hashtags.

Usa a skill `vb-gastronomia-ilustracoes` (SKILL.md + referências + exemplos) como
contexto cacheado, para compor receitas válidas no traço da marca.
"""
import json
import logging
import os
from pathlib import Path

import anthropic

from ..post_orchestrator import _parse_json, _extract_usage

logger = logging.getLogger(__name__)
MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 3000

_ILLU = Path(__file__).parent / 'illustration'


def _illustration_skill_text() -> str:
    parts = []
    for rel in ['SKILL.md', 'references/estilo.md', 'references/vocabulario.md',
                'references/receitas.md']:
        p = _ILLU / rel
        if p.exists():
            parts.append(f'\n\n=== {rel} ===\n\n' + p.read_text(encoding='utf-8'))
    # receitas-exemplo (JSON)
    for name in ['peixe', 'ovo', 'tomate']:
        jp = _ILLU / 'assets' / 'exemplos' / f'{name}.json'
        if jp.exists():
            parts.append(f'\n\n=== exemplo {name}.json ===\n\n' + jp.read_text(encoding='utf-8'))
    return ''.join(parts)


_SKILL_TEXT = _illustration_skill_text()

# Zonas de texto por arquetipo (o que o brain deve preencher).
ARCH_ZONES = {
    '01': ('titulo (pergunta/gancho do cotidiano corporativo, caixa baixa, ATE ~10 palavras, '
           'cabe em 3-4 linhas curtas), apoio (CTA, ATE 8 palavras, cabe em 2 linhas — '
           'frase curta e direta)'),
    '02': '(arte SEM texto — apenas a foto + grafismos + logo). Nao preencha content.',
    '03': ('titulo (destaque curto, ATE ~6 palavras, cabe em 2 linhas), apoio '
           '(frase DESCRITIVA do conteudo/beneficio, de 6 a 9 palavras, que PREENCHA '
           '2 linhas — sera exibida GRANDE como texto vertical ao lado da foto; ex.: '
           '"como utilizar temperos de forma pratica no dia-a-dia")'),
    '04': ('titulo (mensagem INSTITUCIONAL da marca — frase calorosa sobre cuidar do '
           'bem-estar e da alimentacao de quem trabalha nas empresas; caixa baixa; '
           'de 8 a 12 palavras; cabe em 4-5 linhas curtas), apoio (CTA curto e '
           'convidativo, ATE 5 palavras, cabe em 2 linhas — ex.: "venha conhecer '
           'nossos servicos")'),
}

SYSTEM = """\
Voce e o motor de conteudo da VB Gastronomia (gastronomia corporativa; tom
proximo, caloroso, acessivel, convidativo, com autoridade leve). Recebe um tema e
um arquetipo e devolve UM objeto JSON, sem texto fora do JSON.

Acima esta a skill de ILUSTRACAO da marca (traco grafico: figuras flat montadas
com poucas pecas). O briefing indica o MODO do arquetipo:

- MODO=ilustracao: componha uma RECEITA de ilustracao de um objeto/comida que se
  RELACIONE com o texto do post (peixe->peixe, ovo->ovo, salada->folha). Pode
  adaptar uma receita-exemplo. Flat, 3-7 pecas, cores SOMENTE da paleta
  (oliva,laranja,terracota,cinza,vinho,creme,preto,amarelo,branco), canvas
  [1000,520]. Preencha "ilustracao" e "objeto_ilustracao".

- MODO=foto: a arte usa uma FOTO de comida (gerada depois). Preencha "foto" com um
  conceito CURTO do prato/cena que casa com o tema (ex.: "bowl de salada colorida
  servido com colher de madeira"). NAO preencha "ilustracao". Estilo VB: luz
  natural, fundo neutro/claro, comida protagonista, apetitosa, sem texto.

- MODO=texto: a arte usa SOMENTE texto sobre cor (grafismos decorativos sao fixos).
  NAO preencha "ilustracao" nem "foto" — preencha apenas "content".

Regras de texto:
- Use SOMENTE o tom da VB. Caixa baixa no titulo. Nunca invente fatos/numeros.
- Preencha as zonas pedidas para o arquetipo; deixe vazio o que nao se aplica.

Formato EXATO da resposta (apenas este JSON; campos nao usados = vazio/null):
{
  "objeto_ilustracao": "peixe|ovo|... (so no modo ilustracao)",
  "content": { "titulo": "...", "apoio": "..." },
  "ilustracao": { "canvas":[1000,520], "bg":"transparent", "pecas":[ ... ] },
  "foto": "conceito curto do prato/cena (so no modo foto)",
  "caption": "legenda no tom VB",
  "hashtags": ["semacento", "..."]
}
"""


def run_vb_brain(*, tema: str, archetype: str, brand: dict) -> dict:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente no ambiente')

    from .specs import SP
    sp = SP().get(archetype) or {}
    _has_photo = sp.get('bg', {}).get('type') == 'photo' or sp.get('foto_frame')
    _has_illu = bool(sp.get('ilustracao'))
    modo = 'foto' if _has_photo else ('ilustracao' if _has_illu else 'texto')
    zonas = ARCH_ZONES.get(archetype, 'titulo, apoio')
    # Cor de fundo da arte: a ilustracao NAO pode usa-la (peca invisivel).
    _bg_cor = (sp.get('bg') or {}).get('color') or ''
    _bg_regra = (f'\nCOR DE FUNDO da arte: {_bg_cor} — NUNCA use {_bg_cor} nas pecas '
                 f'da ilustracao (ficariam invisiveis); prefira cores de CONTRASTE '
                 f'da paleta.' if (_has_illu and _bg_cor) else '')
    user_text = f"""\
== TEMA DO POST ==
{tema}

== ARQUETIPO ==
{archetype} — MODO={modo} — zonas: {zonas}{_bg_regra}

== MARCA (VB Gastronomia) ==
Tom de voz: {brand.get('tom_voz') or ''}
Vocabulario recomendado: {', '.join(brand.get('palavras_recomendadas') or [])}
Evitar: {', '.join(brand.get('palavras_evitar') or [])}

Produza o JSON (texto + receita de ilustracao relacionada ao tema).
"""

    system_blocks = [
        {'type': 'text', 'text': _SKILL_TEXT,
         'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
        {'type': 'text', 'text': SYSTEM,
         'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
    ]
    client = anthropic.Anthropic(api_key=api_key, max_retries=6)
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system_blocks,
        messages=[{'role': 'user', 'content': user_text}],
    )
    raw = ''.join(b.text for b in resp.content if getattr(b, 'type', None) == 'text')
    structured = _parse_json(raw)
    usage = _extract_usage(resp, cache_ttl='1h')
    if not structured or 'content' not in structured:
        logger.error('[vb.skill_brain] output invalido. Raw: %s', raw[:400])
    return {'structured': structured, 'usage': usage, 'model': MODEL,
            'debug': {'request': {'system': SYSTEM, 'user': user_text}, 'response_raw': raw}}
