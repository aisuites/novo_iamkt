"""
Approach C — designer agent leve: recebe strategic_payload + copy_payload +
kb_dossiers e produz o image_prompt em inglês para o gerador de imagem.

Prioridade na construção do prompt:
  1. recreation_prompt do dossier KB (descreve como recriar a referência)
  2. Zonas de composição do card estratégico (onde texto vai cair por Pillow)
  3. Pessoas/iluminação do dossier (dados reais extraídos da referência)
  4. paleta_observada do dossier (cor de fundo real da referência)
  — brand palette da KB é usada apenas para elementos SEM referência
"""

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 1000


SYSTEM = """You are a creative director specializing in AI image generation prompts for Gemini.

You receive:
- A recreation_prompt (Portuguese) describing the reference image visual style
- A list of reference images with their ROLE LABELS (e.g. GRAPHIC & LAYOUT REFERENCE, PRODUCT, MODEL)
- Composition zones from the strategic card — spatial instructions for Pillow text overlay
- Supporting data (people, lighting, palette, graphic assets) extracted from the reference images

Your task: write ONE final image generation prompt in English for Gemini image generation.

CRITICAL RULE — REFERENCE BY ROLE, NOT BY INDEX:
Multiple images may be sent. Never say "IMAGE 1" or "IMAGE 2".
Always mention the image by its ROLE LABEL exactly as declared in the image index.
Example: "the GRAPHIC & LAYOUT REFERENCE image", "the PRODUCT image", "the MODEL image".

CRITICAL RULE — FIDELITY DECLARATION:
Whenever an element must be replicated from a reference image, the prompt MUST:
  a) Name the source by role: "the GRAPHIC & LAYOUT REFERENCE image"
  b) Declare fidelity as mandatory: "must appear in the final image exactly as shown in..."
     Use strong language: "mandatory", "must", "exactly", "with full fidelity".
  c) Never use weak words: "inspired by", "similar to", "as in the reference" (too vague).

Rules:
1. First line: "Using the provided reference images as visual authority:" — always.
2. Translate and adapt the recreation_prompt as the FOUNDATION. Stay faithful to it.
3. Background color: use paleta_observada dominant color from the data — NOT the brand palette.
4. Graphic elements: mention the GRAPHIC & LAYOUT REFERENCE image by role name, instruct
   the generator to extract the exact element from the GRAPHIC & LAYOUT REFERENCE image,
   and declare they must appear with full fidelity — exact position, color, shape, no relocation.
   Use the phrase: "extract the exact [element] from the GRAPHIC & LAYOUT REFERENCE image and
   replicate it with full fidelity".
5. People/models: if a MODEL image is provided, write "person exactly as shown in the MODEL image".
6. State composition zones: which % of the frame must remain visually calm for text overlay.
7. NEVER include text, words, typography, letters, numbers, logos or brand marks.
8. No vague words. Specific, deterministic, measurable instructions only.
9. Write only the prompt. No explanation, no JSON, no markdown.
10. End with: Aspect ratio: X:X
"""


def build_prompt(
    strategic_payload: Dict[str, Any],
    copy_payload: Dict[str, Any],
    canvas_w: int,
    canvas_h: int,
    kb_dossiers: List[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Gera o image_prompt via Claude usando recreation_prompt como base.

    Retorna {'prompt': str, 'usage': dict, 'model': MODEL, 'ref_image_url': str|None}
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user_text, ref_image_url = _build_user_text(
        strategic_payload, copy_payload, canvas_w, canvas_h, kb_dossiers or []
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{'role': 'user', 'content': user_text}],
        )
    except Exception:
        logger.exception('[prompt_designer] erro Claude')
        return None

    prompt_text = ''.join(
        b.text for b in resp.content if getattr(b, 'type', None) == 'text'
    ).strip()

    usage = _extract_usage(resp)
    logger.info('[prompt_designer] prompt gerado (%d chars) cost=$%.4f ref_image=%s',
                len(prompt_text), usage.get('cost_usd', 0), bool(ref_image_url))
    return {
        'prompt': prompt_text,
        'usage': usage,
        'model': MODEL,
        'ref_image_url': ref_image_url,
    }


def _build_user_text(strategic_payload, copy_payload, canvas_w, canvas_h,
                     kb_dossiers) -> tuple:
    """Retorna (user_text, ref_image_url)."""
    vd = strategic_payload.get('visual_direction') or {}
    fmt = strategic_payload.get('format') or {}
    dims = fmt.get('dimensions_px') or {}
    w = dims.get('width') or canvas_w
    h = dims.get('height') or canvas_h
    aspect_ratio = _aspect_ratio_str(w, h)

    # Separa dossiers de referência dos "image-first" (produto / pessoa_modelo).
    # Esses ja vao como IMAGEM ao Gemini via _collect_references — nao puxa o
    # dossier textual deles aqui para evitar duplicar/contradizer.
    _IMAGE_FIRST = {'produto', 'pessoa_modelo'}
    dossiers_ref = [
        d for d in kb_dossiers
        if not (d.get('aspects') and all(a in _IMAGE_FIRST for a in d.get('aspects')))
    ]

    # Extrai dados do dossier de referência RESPEITANDO os aspects que o user
    # escolheu no modal. Sem filtro, descricoes como "mulher negra de olhos
    # fechados" da referencia acabavam parando no prompt mesmo quando o user
    # so pediu "iluminacao" + "layout_composicao".
    #
    # Mapping aspect → campos do dossier liberados:
    #   layout_composicao  → composicao, grid, texto_x_imagem (so posicoes)
    #   iluminacao         → iluminacao
    #   estilo_pessoas     → pessoas (estilo apenas, sem detalhes etnicos)
    #   estilo_ambiente    → ambiente
    #   grafismos          → assets_grafismos
    #
    # paleta_observada eh global por dossier (entra se houver algum aspect
    # de estilo selecionado: nunca passa sozinha). recreation_prompt e
    # texto_e_imagem NUNCA entram crus (puxam a cena INTEIRA da referencia).
    ASPECT_FIELDS = {
        'layout_composicao': ('composicao', 'grid', 'texto_x_imagem'),
        'iluminacao':        ('iluminacao',),
        'estilo_pessoas':    ('pessoas',),
        'estilo_ambiente':   ('ambiente',),
        'grafismos':         ('assets_grafismos',),
    }

    paleta_observada = []
    assets_grafismos = []
    composicao_ref = {}
    pessoas_ref = []
    iluminacao_ref = {}
    ambiente_ref = {}
    grid_ref = {}
    texto_x_imagem_ref = {}
    ref_image_url = None
    aspects_combined = set()

    for d in dossiers_ref:
        dossier = d.get('dossier') or {}
        aspects_list = [a for a in (d.get('aspects') or []) if a in ASPECT_FIELDS]
        aspects_combined.update(aspects_list)

        # Libera campos por aspect. Se NENHUM aspect listado (ou
        # so aspects nao reconhecidos), nao puxa nada deste dossier para
        # evitar contaminacao da cena.
        if 'layout_composicao' in aspects_list:
            if not composicao_ref:
                composicao_ref = dossier.get('composicao') or {}
            if not grid_ref:
                grid_ref = dossier.get('grid') or {}
            if not texto_x_imagem_ref:
                texto_x_imagem_ref = dossier.get('texto_x_imagem') or {}
        if 'iluminacao' in aspects_list and not iluminacao_ref:
            iluminacao_ref = dossier.get('iluminacao') or {}
        if 'estilo_pessoas' in aspects_list and not pessoas_ref:
            pessoas_ref = dossier.get('pessoas') or []
        if 'estilo_ambiente' in aspects_list and not ambiente_ref:
            ambiente_ref = dossier.get('ambiente') or {}
        if 'grafismos' in aspects_list and not assets_grafismos:
            assets_grafismos = dossier.get('assets_grafismos') or []
        # Paleta entra junto com qualquer aspect de estilo (cor anda com tom)
        if aspects_list and not paleta_observada:
            paleta_observada = dossier.get('paleta_observada') or []
        if not ref_image_url:
            ref_image_url = d.get('s3_url') or d.get('ref_url')

    # recreation_prompt NAO entra mais cru. Foi substituido por blocos
    # filtrados (composicao, iluminacao, ambiente, paleta).
    recreation_prompt = None

    # Cor de fundo: paleta_observada (referência) > brand palette
    bg_color = 'white, pure studio white'
    bg_hex = '#FFFFFF'
    for c in paleta_observada:
        if c.get('papel') == 'dominante':
            bg_color = f'{c.get("nome", "white")} ({c.get("hex", "#FFFFFF")})'
            bg_hex = c.get('hex', '#FFFFFF')
            break

    # Zonas de composição do card estratégico
    composition_card = (vd.get('composition') or '').strip()
    spatial_zone = _extract_spatial_zone(composition_card)

    # Variante recomendada
    variants = copy_payload.get('variants') or []
    rec_id = copy_payload.get('recommended_variant') or 'v1'
    variant = next((v for v in variants if v.get('id') == rec_id), variants[0] if variants else {})
    copy = variant.get('copy') or {}

    lines = [
        f'== Canvas: {w}x{h}px | Aspect ratio: {aspect_ratio} ==',
        '',
        '== REFERENCE IMAGES SENT TO GEMINI (by role) ==',
        '- "the GRAPHIC & LAYOUT REFERENCE image" — contains the grafismos, composition zones and visual style.',
        '  → When describing any graphic element or person from this image, mention it by this role name',
        '    and declare it MANDATORY with full fidelity.',
        '',
    ]

    # ---- BLOCO 1: aspectos liberados pelo user (somente os marcados) ----
    if aspects_combined:
        lines.extend([
            '== STYLE ASPECTS BORROWED FROM REFERENCE (use ONLY for the aspects listed) ==',
            ('IMPORTANT: the SUBJECT (people, products) of the final image comes '
             'from the SCENE description below — NOT from the reference. Use the '
             'reference image only for the specific aspects listed here.'),
            '',
        ])
    if iluminacao_ref:
        lines.extend([
            'LIGHTING (from reference):',
            *[f'  - {k}: {v}' for k, v in iluminacao_ref.items() if v],
            '',
        ])
    if composicao_ref or grid_ref:
        lines.append('LAYOUT & COMPOSITION (from reference — STRUCTURE ONLY, NEVER copy the subject):')
        # Inclui apenas campos cujo schema do dossier eh estritamente
        # estrutural (numerico ou enquadramento abstrato). Campos de texto
        # livre como "simetria", "foco_principal", "regra_dos_tercos",
        # "profundidade_de_campo" descrevem o SUJEITO da ref (modelo, rosto,
        # prato...) e contaminam — sao pulados aqui.
        STRUCTURAL_COMP_FIELDS = ('enquadramento', 'espaco_negativo')
        for k in STRUCTURAL_COMP_FIELDS:
            v = composicao_ref.get(k)
            if v:
                lines.append(f'  - {k}: {v}')
        zonas = (grid_ref.get('zonas') or []) if isinstance(grid_ref, dict) else []
        if zonas:
            lines.append('  Grid zones (replicate the % positions; CONTENT comes from our scene):')
            for z in zonas:
                # Omite o "conteudo" da zona — descreve TEXTOS literais da
                # referencia (ex: "titulo 'Beleza Autentica'"). So % importa.
                lines.append(
                    f'    - {z.get("nome", "?")}: x={z.get("x_pct", 0)}% y={z.get("y_pct", 0)}% '
                    f'w={z.get("largura_pct", 0)}% h={z.get("altura_pct", 0)}%'
                )
        # Posicoes de texto (so como zonas reservadas — conteudo eh nosso)
        blocos = (texto_x_imagem_ref.get('blocos') or []) if isinstance(texto_x_imagem_ref, dict) else []
        if blocos:
            lines.append('  Text overlay zones (positions only — actual text content is added by us via overlay):')
            for b in blocos:
                lines.append(
                    f'    - {b.get("papel", "?")}: color={b.get("cor", "?")}, '
                    f'weight={b.get("peso", "?")}, align={b.get("alinhamento_paragrafo", "?")}'
                )
        lines.append('')
    if ambiente_ref:
        lines.extend([
            'AMBIENT STYLE (from reference):',
            *[f'  - {k}: {v}' for k, v in ambiente_ref.items() if v],
            '',
        ])
    if pessoas_ref:
        # PEOPLE STYLE so libera campos ESTRUTURAIS do dossier (pose, expressao,
        # enquadramento). Campos identitarios (tom_pele, cabelo, etnicidade,
        # idade, genero) sao do schema mas ficam de fora — a identidade do
        # sujeito vem do tema do user na SCENE description, nao da referencia.
        STRUCTURAL_PEOPLE_FIELDS = ('pose', 'expressao', 'enquadramento')
        lines.extend([
            'PEOPLE STYLE (structural only — pose, expression, framing — identity comes from SCENE):',
        ])
        for p in pessoas_ref:
            keep = {k: p[k] for k in STRUCTURAL_PEOPLE_FIELDS if p.get(k)}
            if keep:
                lines.append('  - ' + ', '.join(f'{k}: {v}' for k, v in keep.items()))
        lines.append('  Subject identity (ethnicity, hair, skin tone, age, gender) comes from the SCENE description, NOT from this reference.')
        lines.append('')

    # ---- BLOCO 2: paleta observada (prioridade sobre brand palette) ----
    if paleta_observada:
        lines.extend([
            '== PALETTE FROM REFERENCE IMAGE (use this, NOT the brand palette for background) ==',
        ])
        for c in paleta_observada:
            lines.append(f'  - {c.get("hex")} {c.get("nome")} — {c.get("papel")}')
        lines.extend([
            f'  Background MUST be: {bg_color} (dominant color from reference, as seen in reference image)',
            '',
        ])

    # ---- BLOCO 3: grafismos com posição exata do dossier ----
    # Filtra grafismos que sao TEXTO / LOGOTIPO da referencia — nao queremos
    # replicar marca de outra empresa no nosso post.
    TEXT_GRAPHIC_TYPES = {
        'destaque_tipografico', 'tipografia', 'texto', 'palavra',
        'logo', 'logotipo', 'marca', 'wordmark', 'lettering',
    }
    grafismos_nao_textuais = [
        g for g in assets_grafismos
        if (g.get('tipo') or '').lower() not in TEXT_GRAPHIC_TYPES
    ]
    if grafismos_nao_textuais:
        lines.extend([
            '== GRAPHIC ELEMENTS — replicate from the GRAPHIC & LAYOUT REFERENCE image ==',
            'These NON-TEXTUAL graphic elements should appear: shape, color, position and style.',
            'Do NOT reproduce any letters, words or wordmarks from the reference image.',
        ])
        for g in grafismos_nao_textuais:
            lines.append(
                f'  - type: {g.get("tipo")} | color: {g.get("cor")} '
                f'| style: {g.get("estilo")} | POSITION: {g.get("posicao")} '
                f'| function: {g.get("funcao")}'
            )
        lines.append('')

    # ---- BLOCO 4: zonas de composição (card estratégico) ----
    lines.extend([
        '== COMPOSITION ZONES (Pillow will overlay text in these zones — keep them visually calm) ==',
    ])
    if spatial_zone:
        lines.append(f'  Text overlay zone: {spatial_zone} — must be LOW VISUAL COMPLEXITY (flat background, no subject, no graphic elements)')
    esn = composicao_ref.get('espaco_negativo')
    if esn:
        lines.append(f'  Negative space from reference: {esn} (as seen in reference image)')
    lines.append('')

    # ---- BLOCO 5: instrução de fidelidade à referência ----
    lines.extend([
        '== FIDELITY INSTRUCTION ==',
        'Follow the visual STYLE of the reference image for the aspects listed above (lighting, layout, ambient, palette).',
        'NEVER copy the subject (person, product, food, scene) from the reference image — the subject comes from the SCENE description.',
        'Do not invent graphic elements that are not mentioned above.',
        '',
        '== MANDATORY — NO TEXT, NO TYPOGRAPHY, NO LOGOS ==',
        'The generated image MUST have NO text of any kind. Specifically:',
        '  - NO title, NO subtitle, NO caption, NO CTA text, NO button text.',
        '  - NO letters, NO words, NO numbers, NO typography, NO lettering anywhere.',
        '  - NO logos, NO brand marks, NO watermarks, NO product labels with text.',
        'Titles/subtitles/CTA are added afterwards by an external overlay system — leave the corresponding zones VISUALLY CLEAN (flat, low complexity).',
        'If you would normally render text, render nothing in its place.',
        f'Aspect ratio: {aspect_ratio}',
    ])

    return '\n'.join(lines), ref_image_url


def _extract_spatial_zone(composition: str) -> str:
    """Extrai qual zona é reservada para texto."""
    if not composition:
        return 'left 40% of frame'
    lower = composition.lower()
    import re
    # Busca percentual de zona de texto
    m = re.search(r'(?:esquerda|left)[^\d]*(\d+)%', lower)
    if m:
        return f'left {m.group(1)}% of frame'
    m = re.search(r'(?:direita|right)[^\d]*(\d+)%', lower)
    if m:
        return f'right {m.group(1)}% of frame'
    if 'esquerda' in lower or 'left' in lower:
        return 'left 40% of frame'
    if 'direita' in lower or 'right' in lower:
        return 'right 40% of frame'
    return 'left 40% of frame'


def _aspect_ratio_str(w: int, h: int) -> str:
    from math import gcd
    g = gcd(int(w), int(h))
    return f'{w//g}:{h//g}'


def _extract_usage(resp) -> Dict[str, Any]:
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    i = getattr(usage, 'input_tokens', 0) or 0
    o = getattr(usage, 'output_tokens', 0) or 0
    cost = Decimal('3.0') * Decimal(i) / Decimal(1_000_000) + \
           Decimal('15.0') * Decimal(o) / Decimal(1_000_000)
    return {'input_tokens': i, 'output_tokens': o, 'cost_usd': float(cost)}
