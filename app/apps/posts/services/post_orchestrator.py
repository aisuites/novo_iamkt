"""
Post Orchestrator — agente Claude Sonnet 4.5 multimodal que recebe o
briefing + imagens anexadas + KB e decide:

1. O ROLE de cada imagem na cena final (produto_principal, premio_destaque,
   pessoa_protagonista etc — semantica, nao apenas usage_type)
2. A ESTRATEGIA de composicao (narrativa, flat-lay, destaque dramatico etc)
3. O PROMPT FINAL otimizado para o Gemini (substitui o image_prompt cru)
4. O TEXT_RENDER_MODE adequado (inline | pillow | sanitized)
5. WARNINGS quando o briefing tem ambiguidade

Substitui o _build_combination_rules hardcoded. Mais caro (+$0.02/post),
porem MUITO mais inteligente em casos como "sorteio com premio", "speaker
+ palco", "produto + pessoa demonstrando" etc.

Custo: ~$0.02-0.03 por chamada (Sonnet 4.5 com 2-4 imagens + ~800 tokens out).
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

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 3500

# Aspecto escolhido no modal -> diretriz explicita do que extrair da referencia.
# Substitui o texto livre "o que aproveitar" (removido do modal).
ASPECT_DIRECTIVES = {
    'layout_composicao': (
        'APROVEITE APENAS: LAYOUT e COMPOSICAO desta referencia — grid, posicao '
        'dos blocos de texto, hierarquia e enquadramento. Replique a ESTRUTURA '
        'visual no layout_document (posicao/tamanho dos blocos). Posicione o LOGO '
        'na MESMA ancora/posicao indicada em logo_na_referencia (ex: bottom-center). '
        'NAO copie o produto, a comida nem o cenario especifico, e NAO desenhe '
        'faixas/selos/grafismos da referencia (isso e o aspecto "grafismos").'
    ),
    'iluminacao': (
        'APROVEITE APENAS: a ILUMINACAO desta referencia — tipo, direcao, '
        'temperatura e qualidade da luz. NAO copie composicao, produtos nem cenario.'
    ),
    'estilo_ambiente': (
        'APROVEITE APENAS: o ESTILO DE AMBIENTE/CENARIO — superficies, materiais, '
        'mood e paleta de cena. NAO copie produtos nem o layout de texto.'
    ),
    'estilo_pessoas': (
        'APROVEITE APENAS: o ESTILO DAS PESSOAS — enquadramento, pose, faixa etaria, '
        'vestuario e mood. NAO copie rostos especificos.'
    ),
    'grafismos': (
        'APROVEITE: os GRAFISMOS da referencia (faixas, selos, divisores). Os '
        'elementos role="grafismo" serao INJETADOS deterministicamente no '
        'layout_document a partir do dossie — NAO os emita voce mesmo (evita '
        'aproximacoes). Sua tarefa aqui e: (1) posicionar o TEXTO relacionado '
        'POR CIMA dos grafismos com cor CONTRASTANTE (titulo branco sobre faixa '
        'colorida; CTA branco sobre selo circular colorido). (2) Considerar a '
        'faixa branca de rodape se logo_na_referencia indica fundo branco — '
        'logo cai sobre essa faixa branca. NAO copie a fotografia/produto/cenario.'
    ),
}

# Aspecto -> chaves do dossie que importam (envia so a fatia relevante,
# evita truncamento e ruido). 'descricao_geral' entra sempre como contexto.
ASPECT_DOSSIER_KEYS = {
    # layout = ESTRUTURA (sem grafismos: faixas/selos sao o aspecto 'grafismos')
    'layout_composicao': ['grid', 'composicao', 'texto_x_imagem',
                          'recreation_prompt', 'logo_na_referencia'],
    'iluminacao': ['iluminacao'],
    'estilo_ambiente': ['ambiente', 'mood', 'estilo_visual', 'paleta_observada'],
    'estilo_pessoas': ['pessoas', 'is_humanizada'],
    'grafismos': ['assets_grafismos', 'paleta_observada'],
}


def _slice_dossier(dossier: Dict[str, Any], aspects) -> Dict[str, Any]:
    """Retorna so a fatia do dossie relevante aos aspectos escolhidos (uniao das
    chaves de cada aspecto). Sempre inclui 'descricao_geral' como contexto curto.
    Sem aspecto conhecido -> dossie inteiro."""
    if not isinstance(dossier, dict):
        return {}
    if isinstance(aspects, str):
        aspects = [aspects]
    aspects = [a for a in (aspects or []) if a]
    wanted = []
    for a in aspects:
        for k in ASPECT_DOSSIER_KEYS.get(a, []):
            if k not in wanted:
                wanted.append(k)
    if not wanted:
        return dossier
    out = {}
    if dossier.get('descricao_geral'):
        out['descricao_geral'] = dossier['descricao_geral']
    for k in wanted:
        if k in dossier:
            out[k] = dossier[k]
    return out

SYSTEM_PROMPT = """Voce e um diretor de arte e estrategista de conteudo digital
senior. Sua missao: receber um briefing de post + imagens de referencia + KB
da marca e produzir uma instrucao FINAL otimizada para um gerador de imagem
(Gemini 3 Pro Image).

A diferenca entre voce e os geradores de imagem: VOCE ENTENDE A INTENCAO.

EXEMPLOS DE INTENCOES E COMO INTERPRETAR:
- "Sorteio do produto X e voce ganha o produto Y"
   -> X = produto principal/funcional, Y = premio em destaque (luz dramatica,
      pedestal, troféu visual)
- "Conheça nosso novo produto X"
   -> X = produto unico em destaque, sem distracoes
- "Speaker Z no evento Y"
   -> Z (pessoa) = protagonista, foto do rosto preservada
- "Combo: produto X + produto Y juntos"
   -> Ambos com peso igual (flat-lay, vitrine)
- "Use o produto X no cenario do palestrante Y"
   -> Pessoa interagindo com produto em destaque

REGRAS DE SAIDA:
1. Para cada IMAGEM anexada, atribua um ROLE semantico (nao apenas o
   usage_type tecnico — interprete a INTENCAO).
2. Escolha uma COMPOSITION STRATEGY que faca a narrativa do briefing fluir.
3. Produza o IMAGE_PROMPT_FINAL para o Gemini com REGRAS CRITICAS:

   a) NUNCA descreva produtos/pessoas em palavras. SEMPRE use referencia
      por imagem: "o produto da IMAGEM N", "a pessoa da IMAGEM N", "a bolsa
      da IMAGEM N". Descrever em palavras (ex: "uma bolsa de couro
      monogramada marrom") ativa priors do training data do Gemini e ele
      ignora a imagem anexada.

      ❌ ERRADO: "uma elegante bolsa de couro com padrao monogramado marrom
                  e fecho dourado"
      ✅ CERTO: "a bolsa da IMAGEM 3 (mesma identidade — pode aparecer de
                 outro angulo/posicao que combine com a cena)"

      ❌ ERRADO: "um processador de alimentos moderno com tela touchscreen"
      ✅ CERTO: "o produto da IMAGEM 4 (mesma identidade: modelo, cores,
                 materiais e display), reposicionado para compor a cena"

   a-bis) IDENTIDADE vs ANGULO. Mantenha a IDENTIDADE do produto/objeto
      (modelo, proporcoes, cores, materiais, acabamento, display) IDENTICA a
      foto. Mas o produto PODE ser mostrado de um ANGULO, POSICAO ou
      ENQUADRAMENTO diferente que combine com a cena — variacao MODERADA
      (leve giro/perspectiva), SEM rotacao exagerada e SEM inventar partes nao
      visiveis na foto. Para PESSOAS: preserve o rosto/identidade, mas a pose
      pode variar moderadamente. Objetivo: variedade de composicao sem perder
      fidelidade.

   b) NUNCA mencione nomes de marca, modelo de produto, ou caracteristicas
      especificas do produto em palavras. Apenas "o produto da IMAGEM N".

   c) NAO use pedestais flutuantes ou elementos no ar sem ancoragem fisica.
      Sempre coloque produtos sobre superficies REAIS (bancada, mesa,
      prateleira, chao). Pedestais flutuantes geram artefatos visuais
      ("produto voando").

   d) Descreva LIVREMENTE em palavras: ambiente, iluminacao, mood,
      composicao geral, elementos secundarios (ingredientes, plantas,
      texturas, paredes). Tudo que NAO seja produto/pessoa principal.

   d-bis) NAO INVENTE EFEITOS DE LUZ. Iluminacao deve ser REALISTA e NEUTRA
      (luz natural de janela, luz de estudio suave). NAO adicione glow, halo,
      reflexos coloridos, brilho neon, "luz de tecnologia" ou qualquer efeito
      de cor que NAO exista nas imagens de referencia da marca. Sem aura
      colorida ao redor do produto. So use tratamento de cor/efeito se ele
      aparecer explicitamente numa referencia anexada.

   d-ter) CENA CHEIA E NATURAL (NAO reserve zona de texto). Componha uma cena
      COMPLETA, bonita e realista que ocupa TODO o quadro — NAO deixe parede
      vazia, painel chapado, faixa lisa nem area "reservada" para texto. NADA
      de costura/emenda entre um bloco liso e a cena. O texto sera sobreposto
      depois (em divs) e se adapta a imagem; portanto a sua tarefa aqui e so a
      FOTO. Dica de composicao (nao obrigatoria): deixe o SUJEITO num lado e
      areas naturalmente mais calmas (parede, bancada, ceu) no outro — mas como
      parte organica da cena, nunca como um bloco artificial.

   e) Mantenha o prompt em 3-6 linhas. Direto, sem floreios.
4. Decida TEXT_RENDER_MODE:
   - 'inline' (Gemini desenha texto): se o titulo nao contem marcas/nomes
     proprios que ativam priors. Tem o melhor visual integrado.
   - 'pillow' (texto desenhado depois): se o titulo contem nomes proprios
     CRITICOS (marca/produto/modelo) que precisam ser literais OU se ja
     ha produtos sensiveis a name-anchor.
   - 'sanitized': raramente — quase nunca melhor que pillow.
5. LAYOUT PLAN — NAO reserve zonas vazias na imagem. A imagem do Gemini deve
   ser uma CENA CHEIA e natural. O posicionamento do texto e definido no
   layout_document (divs sobrepostas depois), NAO reservando espaco na foto.
   Voce ainda pode preencher main_subject_zone (onde o sujeito vai) e indicar
   no layout_document onde o texto cai, mas SEM pedir ao Gemini areas lisas.
   spatial_instructions deve ser SOMENTE uma descricao da cena cheia (sujeito,
   areas mais calmas naturais) — NUNCA "deixe livre", "area uniforme", "fundo
   limpo" ou qualquer reserva que gere painel/costura.

6. WARNINGS: se o briefing tem ambiguidades importantes (ex: "faltam regras
   do sorteio", "nao esta claro qual produto e o premio"), liste em
   warnings. Nao bloqueia geracao mas registra.

7. LAYOUT_DOCUMENT — o PLANO DO TEXTO COMO "DIVS" EDITAVEIS (parte mais
   importante). Voce PROJETA o texto final como um diretor de arte. Para cada
   bloco (titulo, subtitulo, cta) e o logo, defina um elemento com posicao e
   tamanho RELATIVOS ao canvas (%, 0-100). Este documento e renderizado por
   cima da imagem e depois EDITADO pelo usuario num canvas — entao precisa ser
   bem pensado e profissional.

   REGRAS DE DESIGN (pense como designer senior; NAO use valores minimos):
   - TAMANHO PROPORCIONAL: font_size_pct e % da MENOR dimensao do canvas.
     Titulo normalmente 8-14% (precisa ter IMPACTO). Subtitulo 45-60% do
     titulo. CTA ~ subtitulo. Titulo curto -> maior; titulo longo -> um pouco
     menor, mas NUNCA minusculo. Pense no tamanho que um designer usaria num
     post real — texto grande e legivel, nao perdido na arte.
   - HIERARQUIA: titulo > subtitulo > cta, legivel a distancia.
   - POSICAO: INSPIRE-SE na composicao da referencia de layout (dossie), mas
     ADAPTE ao briefing e ao formato. Texto e sujeito em LADOS OPOSTOS; texto
     sobre area clara/limpa da cena.
   - COR: titulo na cor PRIMARIA da marca (paleta) quando contrastar com o
     fundo; subtitulo/cta num neutro legivel da paleta (branco/grafite).
   - ALIGN: alinhamento de paragrafo por bloco (left|center|right|justify),
     espelhando a referencia.
   - PADDING: respiro interno (padding_pct) para o texto nao colar nas bordas.
   - x_pct/y_pct = canto SUPERIOR ESQUERDO do bloco; width_pct = largura onde
     o texto quebra. Garanta que o bloco CABE no canvas (x_pct+width_pct<=100).
   - O image_prompt_final e o spatial_instructions descrevem uma CENA CHEIA;
     NAO peca area lisa/reservada para o texto. O texto se adapta a cena via
     contraste/sombra na renderizacao — voce so escolhe o lado mais calmo.

7-bis. PRODUTOS SAO COMPOSTOS DEPOIS (cutout). Quando uma IMAGEM e do
   tipo "produto", ela sera CORTADA do fundo branco e COLADA por cima da cena
   pelo Pillow — ou seja, o produto NAO precisa estar na cena gerada pelo Gemini.
   Regras:
   - O image_prompt_final descreve a cena SEM o produto. Na posicao onde o
     produto sera colado, a cena tem uma SUPERFICIE CALMA E COERENTE (bancada,
     toalha, tabua) — parte natural da cena, NAO buraco/area vazia.
   - EMITA UM elemento {"role":"produto","image_n":N,"x_pct":..,"y_pct":..,
     "width_pct":..} no layout_document para CADA produto. image_n e o numero
     da IMAGEM original (1-based). A altura segue a proporcao da foto.
   - O produto fica ACIMA dos grafismos e ABAIXO do texto/logo na ordem de
     renderizacao — entao posicione produto em area que nao vai ter texto.

8. COMPOSICAO GUIADA PELO LAYOUT (ordem importa: PRIMEIRO decida o
   layout_document, DEPOIS descreva a cena). A cena NAO e independente do texto:
   voce ja sabe ONDE cada bloco de texto/logo vai cair, entao DESCREVA NO
   image_prompt_final o que existe de imagem ATRAS de cada bloco — de forma
   calma, simples e proposital, como parte ORGANICA da cena. NAO deixe o Gemini
   inventar elementos competindo com o texto naquela regiao.
   - Para a regiao sob o TITULO/SUBTITULO: descreva um fundo naturalmente mais
     calmo e de baixo contraste (parede de reboco, ceu, bancada lisa, bokeh
     suave, sombra) — REAL e continuo com a cena, NUNCA um painel/faixa chapada.
   - Para a regiao do SUJEITO (produto/pessoa): concentre ali o detalhe e o foco.
   - Para a regiao do CTA/LOGO: superficie simples e legivel (borda da bancada,
     canto de parede), sem rostos nem detalhes finos.
   - Garanta CONTRASTE entre o texto e o fundo planejado: se o bloco e claro,
     descreva fundo mais escuro naquela zona, e vice-versa. Diga isso na cena
     ("...no terco superior-esquerdo, parede neutra escura — onde caira o
     titulo claro..."). E orientacao de CONTEUDO da cena, NAO reserva de espaco.

FORMATO DE SAIDA (JSON puro, sem markdown):
{
  "image_roles": [
    {
      "image_n": 1,
      "tipo_original": "logo",
      "role": "marca",
      "treatment": "string descrevendo onde/como aplicar"
    },
    ...
  ],
  "composition_strategy": "string narrativa explicando a composicao geral",
  "image_prompt_final": "string final em PT-BR para o Gemini (3-6 linhas)",
  "text_render_mode": "inline" | "pillow" | "sanitized",
  "text_render_rationale": "string curta justificando a escolha",
  "layout_plan": {
    "title_zone": {
      "position": "top-left",
      "width_pct": 60,
      "height_pct": 22,
      "background_requirement": "uniforme/claro/sem rostos/sem texto"
    },
    "subtitle_zone": {
      "position": "top-left",
      "width_pct": 60,
      "height_pct": 8,
      "background_requirement": "uniforme/continuacao do titulo"
    },
    "logo_zone": {
      "position": "top-right",
      "width_pct": 12,
      "height_pct": 8,
      "background_requirement": "fundo limpo, sem elementos"
    },
    "cta_zone": {
      "position": "bottom-center",
      "width_pct": 50,
      "height_pct": 10,
      "background_requirement": "superficie uniforme — bancada, fundo simples, sem rostos"
    },
    "main_subject_zone": {
      "position": "center",
      "description": "produtos e pessoas concentrados aqui"
    }
  },
  "spatial_instructions_for_gemini": "string com instrucoes explicitas para o gerador de imagem respeitar as zonas reservadas. Sera injetada como bloco separado no prompt final.",
  "layout_document": {
    "elements": [
      {"role": "grafismo", "forma": "faixa", "cor": "#RRGGBB", "x_pct": 0, "y_pct": 0,
       "width_pct": 72, "height_pct": 16, "raio_pct": 4, "opacidade": 100},
      {"role": "titulo", "content": "<texto exato do titulo>", "x_pct": 6, "y_pct": 8,
       "width_pct": 55, "font_size_pct": 11, "weight": "bold", "case": "none",
       "color": "#RRGGBB", "align": "left", "padding_pct": 2},
      {"role": "subtitulo", "content": "<texto do subtitulo>", "x_pct": 6, "y_pct": 30,
       "width_pct": 50, "font_size_pct": 5.5, "weight": "regular", "case": "none",
       "color": "#RRGGBB", "align": "left", "padding_pct": 2},
      {"role": "grafismo", "forma": "selo", "cor": "#RRGGBB", "x_pct": 8, "y_pct": 58,
       "width_pct": 26, "height_pct": 15},
      {"role": "produto", "image_n": 1, "x_pct": 70, "y_pct": 65, "width_pct": 25},
      {"role": "cta", "content": "<cta ou string vazia>", "x_pct": 6, "y_pct": 88,
       "width_pct": 42, "font_size_pct": 5, "weight": "bold", "case": "none",
       "color": "#RRGGBB", "align": "left", "padding_pct": 2},
      {"role": "logo", "x_pct": 80, "y_pct": 4, "width_pct": 15}
    ]
  },
  "warnings": ["string de cada warning"]
}

NOTA sobre role="grafismo" (so quando o aspecto 'grafismos' foi pedido): forma
= "faixa" (retangulo arredondado, use raio_pct), "selo" (circulo) ou "linha"
(divisor). Use cores da PALETA da marca. O Pillow desenha o grafismo ATRAS do
texto, entao posicione o bloco de texto relacionado SOBRE o grafismo (mesmas
coordenadas aprox.) com cor contrastante. NAO emita grafismos se o aspecto
'grafismos' nao foi pedido para nenhuma referencia.

REGRAS CRITICAS para layout_plan:
- title_zone NUNCA deve incluir rosto humano, produto principal, ou texto visivel
- main_subject_zone deve estar AFASTADO das zonas de title/cta para nao competir
- Aspect ratio define onde o sujeito vai: 9:16/4:5/1:1 -> sujeito CENTRO-BAIXO,
  16:9 -> sujeito CENTRO-DIREITA (texto fica na esquerda)

REGRA DA IMAGEM: a imagem do Gemini e uma CENA CHEIA, bonita e natural, que
preenche TODO o quadro. NAO reserve area lisa/vazia para texto, NAO crie painel
ou faixa chapada, NAO deixe "espaco para texto", NAO adicione blur/haze/overlay/
vinheta. O texto entra por cima depois (divs) e se adapta. spatial_instructions
e so a descricao da cena cheia.

EXEMPLOS DE spatial_instructions_for_gemini:
- "Cena cheia: o produto da IMAGEM N em destaque sobre bancada, ambiente de
   cozinha real iluminado por luz natural, ingredientes ao redor, profundidade
   de campo natural. Composicao completa, sem areas vazias reservadas."
- "Foto lifestyle completa preenchendo o quadro; sujeito principal nitido,
   ambiente real ao redor, sem painel/faixa lisa e sem texto."

Retorne APENAS o JSON, sem texto antes ou depois, sem markdown."""


def orchestrate_post(
    *,
    post,
    references: List[Dict[str, Any]],
    kb_summary: str,
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    references_usage_description: str = '',
    formato_px: str = '',
    aspect_ratio: str = '',
    kb_dossiers: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Roda o orquestrador Claude Sonnet 4.5 multimodal.

    Args:
        post: Post Django (le title, subtitle, requested_theme, cta)
        references: lista de dicts {url, tipo, usage_description} — refs
            que vao pro Gemini (logos + grafismos + uploads)
        kb_summary: resumo textual da KB
        paleta: lista de cores
        tipografia: lista de fontes
        references_usage_description: texto livre do user sobre uso das refs

    Retorna dict com:
        {
          'orchestration': dict do JSON parseado (image_roles, strategy, etc),
          'usage': dict de tokens/custo,
          'model': str,
        }
    Ou None em caso de falha (caller usa fallback).
    """
    kb_dossiers = kb_dossiers or []

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[orchestrator] ANTHROPIC_API_KEY ausente')
        return None

    if not references and not kb_dossiers:
        logger.info('[orchestrator] sem refs nem dossies — skip orchestration')
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Monta content multimodal: lista de imagens + meta de cada + texto final
    content_blocks: List[Dict[str, Any]] = []
    image_meta_lines = []

    for i, ref in enumerate(references, 1):
        url = ref.get('url')
        tipo = str(ref.get('tipo', 'desconhecido')).lower()
        usage_desc = (ref.get('usage_description') or '').strip()

        meta = f'IMAGEM {i}: tipo_original={tipo}'
        if usage_desc:
            meta += f' | uso indicado pelo user: "{usage_desc}"'
        if tipo == 'produto':
            meta += (
                ' | MODO CUTOUT-COMPOSITE: esta imagem sera CORTADA (cutout) e '
                'COLADA por cima da cena por Pillow. NAO descreva o produto no '
                'image_prompt_final (a cena vem SEM o produto). EMITA um '
                "role='produto' no layout_document com image_n=" + str(i) +
                ', x_pct/y_pct/width_pct definindo onde colar.'
            )
        image_meta_lines.append(meta)

        if not url:
            continue
        try:
            b64, mime = _download_to_base64(url)
            if not b64:
                continue
            content_blocks.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': mime, 'data': b64},
            })
        except Exception as exc:
            logger.warning('[orchestrator] falha download imagem %d: %s', i, exc)

    # Texto final com briefing e metadados
    user_text = _build_user_text(
        post=post,
        kb_summary=kb_summary,
        paleta=paleta,
        tipografia=tipografia,
        references_usage_description=references_usage_description,
        image_meta_lines=image_meta_lines,
        formato_px=formato_px,
        aspect_ratio=aspect_ratio,
        kb_dossiers=kb_dossiers,
    )
    content_blocks.append({'type': 'text', 'text': user_text})

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {'role': 'user', 'content': content_blocks},
            ],
        )
    except Exception:
        logger.exception('[orchestrator] erro Claude')
        return None

    # Sonnet 4.6 nao aceita prefill de assistant; _parse_json extrai o JSON
    # mesmo com cercas markdown / texto ao redor.
    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    orchestration = _parse_json(raw)
    if not orchestration:
        logger.error('[orchestrator] parse JSON falhou. Raw: %s', raw[:400])
        return None

    # Sanity check basico do output
    if 'image_prompt_final' not in orchestration:
        logger.warning('[orchestrator] output sem image_prompt_final — invalido')
        return None

    usage = _extract_usage(resp)
    logger.info(
        '[orchestrator] post=%s tokens=%d cost=$%s strategy=%s mode=%s',
        post.id, usage.get('total_tokens', 0), usage.get('cost_usd', 0),
        (orchestration.get('composition_strategy') or '')[:80],
        orchestration.get('text_render_mode', '?'),
    )

    return {
        'orchestration': orchestration,
        'usage': usage,
        'model': MODEL,
    }


def _build_user_text(
    *,
    post,
    kb_summary: str,
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    references_usage_description: str,
    image_meta_lines: List[str],
    formato_px: str = '',
    aspect_ratio: str = '',
    kb_dossiers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    lines = [
        '== Briefing do post ==',
        f'Titulo: {post.title or "(sem titulo)"}',
        f'Subtitulo: {post.subtitle or "(sem subtitulo)"}',
        f'CTA: {post.cta or "(sem CTA)"}',
        f'Tema/contexto original: {post.requested_theme or "(sem tema)"}',
        f'Rede social: {post.social_network or "instagram"}',
        f'Formato da arte: {formato_px or "?"} (aspect_ratio: {aspect_ratio or "?"})',
        '',
        '== Marca (KB compilation) ==',
        kb_summary[:1500] if kb_summary else '(sem resumo da marca)',
        '',
        '== Cores da marca (paleta KB) — use para glow/acentos da cena ==',
        ', '.join(
            f"{(c.get('hex') or '').strip()} ({c.get('tipo') or 'cor'})"
            for c in (paleta or []) if c.get('hex')
        ) or '(sem paleta)',
        '',
        '== Imagens anexadas (na ordem mostrada ACIMA deste texto) ==',
        '\n'.join(image_meta_lines) if image_meta_lines else '(nenhuma)',
    ]
    if references_usage_description:
        lines.extend([
            '',
            '== Observacao geral do user sobre uso das referencias ==',
            references_usage_description,
        ])
    if kb_dossiers:
        lines.extend([
            '',
            '== Dossies de imagens de referencia da marca (KB) ==',
            '(Analise visual ja extraida dessas imagens. NAO sao imagens a',
            'reproduzir — sao referencias de ESTILO. Cada uma tem um ASPECTO que o',
            'user escolheu aproveitar (na linha "Instrucao"). Extraia SOMENTE aquele',
            'aspecto e funda no image_prompt_final / layout_document. O dossie abaixo',
            'ja vem FILTRADO para o aspecto escolhido. NUNCA copie produtos/pessoas',
            'especificos desses dossies.)',
        ])
        for i, d in enumerate(kb_dossiers, 1):
            dossier = d.get('dossier') or {}
            aspects = d.get('aspects')
            if aspects is None:  # compat: formato antigo com 'aspect' string
                _a = (d.get('aspect') or '').strip()
                aspects = [_a] if _a else []
            aspects = [a for a in aspects if a]
            free_text = (d.get('usage_description') or '').strip()
            directives = [ASPECT_DIRECTIVES[a] for a in aspects if a in ASPECT_DIRECTIVES]
            if directives:
                intent = '\n  '.join(directives)
            elif free_text:
                intent = free_text
            else:
                intent = '(uso geral / inspiracao — extraia o que melhor servir ao briefing)'
            sliced = _slice_dossier(dossier, aspects)
            header = f'-- Referencia KB {i}'
            header += f' [aspectos: {", ".join(aspects)}] --' if aspects else ' --'
            lines.append('')
            lines.append(header)
            lines.append(f'Instrucao: {intent}')
            lines.append(
                'Dossie (filtrado para os aspectos): '
                + json.dumps(sliced, ensure_ascii=False)[:5000]
            )

    lines.extend([
        '',
        '== Tarefa ==',
        'Analise as imagens + os dossies + o briefing acima e produza o JSON',
        'conforme instrucoes do system prompt. Foque em INTENCAO, nao apenas em',
        'usage_type tecnico. Para cada dossie da KB, extraia SOMENTE o aspecto da',
        'linha "Instrucao" e funda no image_prompt_final / layout_document.',
    ])
    return '\n'.join(lines)


def _download_to_base64(url: str):
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
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
        + Decimal('3.75') * Decimal(cache_write) / Decimal(1_000_000)
        + Decimal('0.30') * Decimal(cache_read) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'total_tokens': in_tokens + out_tokens,
        'cost_usd': float(cost),
    }


# =====================================================================
# ADAPTADOR DE LAYOUT POR FORMATO (text-only) — usado quando a ref de
# layout nasceu num aspect ratio diferente do post (ex: 1:1 -> 9:16).
# =====================================================================

_LAYOUT_ADAPT_SYSTEM = """Voce e um diretor de arte. Recebe um LAYOUT_SPEC de
texto pensado para um aspect ratio de ORIGEM e deve ADAPTA-LO para um aspect
ratio de DESTINO diferente, mantendo a INTENCAO mas reposicionando as ZONAS.

REGRAS:
- Mantenha title_align / subtitle_align / cta_align EXATAMENTE como vieram.
- Reposicione apenas as zonas em %: title_zone_pct, subtitle_zone_pct e as
  posicoes de logo/cta. Campos: x_pct, y_pct (canto superior esquerdo),
  width_pct. Tudo 0-100.
- Pense na proporcao: indo de 1:1 (quadrado) para 9:16 (vertical alto), um
  bloco de texto no terco esquerdo pode subir para o TOPO. De 1:1 para 16:9
  (horizontal), o texto tende a ficar de um LADO (esquerda) e o sujeito do outro.
- PESO DE OCUPACAO: mantenha o texto com peso visual SEMELHANTE ao da origem.
  O texto NAO deve dominar a arte — o sujeito (produto/pessoa) continua sendo o
  foco. NAO alargue a zona de texto alem do necessario (evite width_pct alto so
  para preencher espaco). Prefira manter o texto compacto num canto/faixa.
- NAO crie campos novos nem remova existentes. Devolva os MESMOS campos do
  input, apenas com as zonas/posicoes ajustadas ao destino.

Devolva APENAS o JSON do layout_spec adaptado, sem markdown."""


def adapt_layout_spec(
    layout_spec: Dict[str, Any],
    source_ar: float,
    target_ar: float,
    target_px: str = '',
) -> Optional[Dict[str, Any]]:
    """
    Reposiciona as zonas de um layout_spec da proporcao de origem para a de
    destino via Claude (text-only, barato). Mantem alinhamentos. Retorna o
    spec adaptado (merge sobre o original) ou None em falha.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key or not layout_spec:
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    user = (
        f'LAYOUT_SPEC (origem aspect_ratio={source_ar}):\n'
        f'{json.dumps(layout_spec, ensure_ascii=False)}\n\n'
        f'Adapte para o DESTINO: aspect_ratio={target_ar}'
        + (f', dimensoes={target_px}' if target_px else '')
        + '.\nDevolva o JSON adaptado.'
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=_LAYOUT_ADAPT_SYSTEM,
            messages=[
                {'role': 'user', 'content': user},
            ],
        )
    except Exception:
        logger.exception('[layout_adapt] erro Claude')
        return None

    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
    )
    adapted = _parse_json(raw)
    if not adapted:
        logger.warning('[layout_adapt] parse JSON falhou')
        return None
    merged = dict(layout_spec)
    merged.update(adapted)

    # Clamp de seguranca: o texto nao deve dominar a arte. Limita a largura das
    # zonas de texto (mesmo que o LLM tenha alargado demais).
    for key, cap in (('title_zone_pct', 60), ('subtitle_zone_pct', 72)):
        zone = merged.get(key)
        if isinstance(zone, dict) and zone.get('width_pct'):
            try:
                if float(zone['width_pct']) > cap:
                    zone['width_pct'] = cap
            except (TypeError, ValueError):
                pass

    merged['source'] = 'dossier_layout_aspect+format_adapted'
    return merged
