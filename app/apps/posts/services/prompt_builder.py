"""
Approach B — builder determinístico de prompt Gemini a partir do strategic_payload.

Nenhum LLM envolvido. Lê os campos estruturados do card e monta o prompt em inglês
seguindo as regras do Gemini (sem texto, sem logo, aspect ratio correto).

Mapeamentos fixos:
  brand_tone.visual  → lighting/atmosphere template
  image_style        → subject/action description (tradução campo a campo)
  composition        → spatial zones in English
  color_mood         → palette instruction
  KB dossier pessoas → people description (reusa análise já feita)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapeamento tom visual → parâmetros de cena Gemini
_TONE_TO_SCENE = {
    'premium': {
        'lighting': 'soft diffused natural light, subtle shadow, refined studio quality',
        'atmosphere': 'refined, quiet, exclusive, aspirational',
        'avoid': 'busy backgrounds, saturated colors, harsh artificial lighting',
    },
    'jovem': {
        'lighting': 'bright high-key lighting, punchy contrast',
        'atmosphere': 'energetic, fun, vibrant, dynamic',
        'avoid': 'flat compositions, muted tones, stock photo feel',
    },
    'confiavel': {
        'lighting': 'clean studio or soft natural, cool temperature',
        'atmosphere': 'professional, trustworthy, clear',
        'avoid': 'chaotic compositions, overly casual feel',
    },
    'inspiracional': {
        'lighting': 'golden hour or soft window light, warm temperature',
        'atmosphere': 'hopeful, aspirational, human, genuine',
        'avoid': 'clinical feel, harsh shadows, posed model look',
    },
    'urgente': {
        'lighting': 'high contrast, dramatic',
        'atmosphere': 'intense, immediate, decisive',
        'avoid': 'soft moods, gentle tones, lots of negative space',
    },
    'criativo': {
        'lighting': 'mixed, intentional, textured',
        'atmosphere': 'curious, playful, distinctive',
        'avoid': 'generic stock, symmetric safety',
    },
}

# Mapeamento aspect ratio numérico → string Gemini
_AR_MAP = {
    (1, 1): '1:1',
    (16, 9): '16:9',
    (9, 16): '9:16',
    (4, 5): '4:5',
    (3, 2): '3:2',
}


def build_prompt(
    strategic_payload: Dict[str, Any],
    canvas_w: int,
    canvas_h: int,
    kb_dossiers: List[Dict[str, Any]] = None,
) -> str:
    """Constrói o prompt Gemini deterministicamente a partir do card estratégico.

    Retorna string em inglês pronta para enviar ao Gemini.
    """
    vd = strategic_payload.get('visual_direction') or {}
    bt = strategic_payload.get('brand_tone') or {}
    fmt = strategic_payload.get('format') or {}
    dims = fmt.get('dimensions_px') or {}

    w = dims.get('width') or canvas_w
    h = dims.get('height') or canvas_h
    aspect_ratio = _aspect_ratio_str(w, h)

    tone_key = (bt.get('visual') or 'premium').lower()
    scene = _TONE_TO_SCENE.get(tone_key, _TONE_TO_SCENE['premium'])

    parts = []

    # 1. Sujeito e ação (image_style do card)
    image_style = (vd.get('image_style') or '').strip()
    if image_style:
        parts.append(_translate_image_style(image_style, kb_dossiers))

    # 2. Composição/zonas (composition do card)
    composition = (vd.get('composition') or '').strip()
    if composition:
        parts.append(_translate_composition(composition))

    # 3. Iluminação (do tom visual + dossier se disponível)
    lighting = _extract_lighting(kb_dossiers) or scene['lighting']
    parts.append(f'Lighting: {lighting}')

    # 4. Paleta (color_mood do card — extrai hexas se houver)
    color_mood = (vd.get('color_mood') or '').strip()
    if color_mood:
        parts.append(_translate_color_mood(color_mood))

    # 5. Atmosfera
    parts.append(f'Atmosphere: {scene["atmosphere"]}')

    # 6. Parâmetros técnicos obrigatórios
    parts.extend([
        f'Aspect ratio: {aspect_ratio}',
        'Style: photorealistic, high-end commercial photography',
        'Technical: high resolution, sharp focus, 4k, professional quality',
        f'Avoid: {scene["avoid"]}',
        'MANDATORY: no text, no words, no typography, no letters, no numbers in the image',
        'MANDATORY: no logos, no brand marks, no watermarks',
    ])

    prompt = '\n'.join(p for p in parts if p.strip())
    logger.info('[prompt_builder] prompt gerado (%d chars)', len(prompt))
    return prompt


def _aspect_ratio_str(w: int, h: int) -> str:
    from math import gcd
    g = gcd(w, h)
    rw, rh = w // g, h // g
    return _AR_MAP.get((rw, rh), f'{rw}:{rh}')


def _translate_image_style(image_style: str, kb_dossiers: List[Dict] = None) -> str:
    """Converte image_style (PT) em subject description (EN).
    Usa dossier de pessoas se disponível pra ser mais específico.
    """
    lines = ['Subject and scene:']

    # Extrai descrição de pessoas do dossier se houver
    pessoas = _extract_pessoas(kb_dossiers)
    if pessoas:
        lines.append(f'  People: {pessoas}')

    # Extrai mood do dossier
    mood = _extract_mood(kb_dossiers)
    if mood:
        lines.append(f'  Mood: {mood}')

    # Adiciona image_style como instrução de cena complementar
    # (mantém em PT mas o Gemini entende bem PT também — ou traduz tokens-chave)
    scene_hint = _extract_scene_from_style(image_style)
    if scene_hint:
        lines.append(f'  Scene: {scene_hint}')

    return '\n'.join(lines)


def _extract_scene_from_style(image_style: str) -> str:
    """Extrai palavras-chave do image_style e converte pra EN."""
    mappings = {
        'lifestyle': 'lifestyle photography, natural and candid',
        'produto hero': 'product hero shot, clean and professional',
        'editorial': 'editorial style photography',
        'estúdio': 'studio photography',
        'estudio': 'studio photography',
        'busto': 'upper body portrait, three-quarter view',
        'perfil três-quartos': 'three-quarter profile',
        'mão tocando': 'hand gently touching face',
        'bochecha': 'cheek',
        'olhos fechados': 'eyes closed',
        'softbox': 'softbox lighting',
        'beauty lighting': 'beauty lighting',
        'casal': 'couple interacting naturally',
        'bancada': 'kitchen counter',
        'cozinha': 'kitchen environment',
        'serena': 'serene expression',
        'relaxada': 'relaxed expression',
        'sorriso': 'gentle smile',
    }
    result_parts = []
    lower = image_style.lower()
    for pt_key, en_val in mappings.items():
        if pt_key in lower and en_val not in result_parts:
            result_parts.append(en_val)
    return ', '.join(result_parts) if result_parts else image_style[:120]


def _translate_composition(composition: str) -> str:
    """Converte composition (PT com coordenadas) pra instrução EN."""
    lines = ['Composition:']

    mappings = {
        'zona esquerda': 'left zone',
        'zona direita': 'right zone',
        'canto superior esquerdo': 'top-left corner',
        'canto superior direito': 'top-right corner',
        'canto inferior direito': 'bottom-right corner',
        'canto inferior esquerdo': 'bottom-left corner',
        'base central': 'bottom center',
        'terço superior': 'upper third',
        'terço inferior': 'lower third',
        'centro': 'center',
        'assimétrico': 'asymmetric layout',
        'split': 'split layout',
        'espaço negativo': 'negative space',
        'respiro': 'breathing room, generous negative space',
        'grafismos': 'geometric decorative elements',
        'figura humana': 'human figure',
    }

    comp_en = composition
    for pt, en in mappings.items():
        comp_en = comp_en.replace(pt, en)

    # Extrai % se houver
    import re
    pct_mentions = re.findall(r'[\w\s]+=?\s*[≈~]?\s*(\d+)%', comp_en)
    lines.append(f'  {comp_en[:300]}')
    return '\n'.join(lines)


def _translate_color_mood(color_mood: str) -> str:
    """Extrai hexas e descreve a paleta em EN."""
    import re
    hexas = re.findall(r'#[0-9A-Fa-f]{6}', color_mood)
    if hexas:
        return f'Color palette: {", ".join(hexas)} — warm and cool tones balanced, no competing bright colors'
    return f'Color mood: {color_mood[:150]}'


def _extract_lighting(kb_dossiers: List[Dict] = None) -> Optional[str]:
    if not kb_dossiers:
        return None
    for d in kb_dossiers:
        if d.get('aspects') == ['produto']:
            continue
        dossier = d.get('dossier') or {}
        ilum = dossier.get('iluminacao') or {}
        if ilum:
            tipo = ilum.get('tipo', '')
            direcao = ilum.get('direcao', '')
            qualidade = ilum.get('qualidade', '')
            parts = [p for p in [tipo, direcao, qualidade] if p]
            if parts:
                return ', '.join(parts)
    return None


def _extract_pessoas(kb_dossiers: List[Dict] = None) -> Optional[str]:
    if not kb_dossiers:
        return None
    for d in kb_dossiers:
        if d.get('aspects') == ['produto']:
            continue
        dossier = d.get('dossier') or {}
        pessoas = dossier.get('pessoas') or []
        if pessoas:
            descs = []
            for ps in pessoas[:2]:
                parts = []
                if ps.get('pose'):
                    parts.append(ps['pose'])
                if ps.get('expressao'):
                    parts.append(f'expression: {ps["expressao"]}')
                if ps.get('tom_pele'):
                    parts.append(f'skin tone: {ps["tom_pele"]}')
                descs.append(', '.join(parts))
            return ' | '.join(descs)
    return None


def _extract_mood(kb_dossiers: List[Dict] = None) -> Optional[str]:
    if not kb_dossiers:
        return None
    for d in kb_dossiers:
        if d.get('aspects') == ['produto']:
            continue
        dossier = d.get('dossier') or {}
        mood = dossier.get('mood') or ''
        if mood:
            return mood
    return None
