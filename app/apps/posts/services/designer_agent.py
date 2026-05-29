"""
Designer agent (orquestrador-designer) — recebe copy_payload + briefing + KB
+ refs + modal choices e produz designer_payload com wireframe_plan completo,
image_prompts e auto-aprovação.

Carrega skill estruturada (shared_skill/ + designer_skill/) como system
prompt cacheado 1h. Loop interno de até 2 iterações se approval.status='iterate'.
"""

import base64
import json
import logging
import os
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 12000  # designer_payload eh grande (wireframe + image_prompts)
MAX_INTERNAL_ITERATIONS = 2  # se status='iterate', tenta de novo

_SERVICES_DIR = Path(__file__).parent
_SHARED_DIR = _SERVICES_DIR / 'shared_skill'
_DESIGNER_DIR = _SERVICES_DIR / 'designer_skill'


def _load_skill() -> str:
    parts = []
    files = [
        _SHARED_DIR / 'formats-and-safe-zones.md',
        _SHARED_DIR / 'typography-scale.md',
        _SHARED_DIR / 'contrast-rules.md',
        _SHARED_DIR / 'design-principles.md',
        _DESIGNER_DIR / 'SKILL.md',
        _DESIGNER_DIR / 'references' / 'wireframe-examples.md',
        _DESIGNER_DIR / 'references' / 'prompt-library.md',
        _DESIGNER_DIR / 'references' / 'render-order-guide.md',
    ]
    for fp in files:
        try:
            parts.append(f'\n\n=== ARQUIVO: {fp.name} ===\n\n')
            parts.append(fp.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('[designer] skill file faltando: %s', fp)
    return ''.join(parts)


DESIGNER_SKILL_FULL = _load_skill()


SYSTEM_INTRO = """Você é o designer do iamkt — 3º agente do pipeline. Recebe
strategic_payload (do estrategista), copy_payload (do copywriter), KB, refs e
modal_choices. Produz designer_payload conforme schema do Passo 8 do skill.

REGRAS NAO NEGOCIAVEIS:
- Voce NAO decide intencao, framework, image_style, mood ou composicao geral.
  Tudo isso ja veio em strategic_payload.visual_direction — voce OBEDECE.
- Se visual_direction.image_style for lifestyle/produto-hero/editorial/ilustracao,
  voce DEVE criar elemento type=image com mechanism=gemini e gemini_prompt_id.
  Pular Gemini nesses casos e ERRO grave.
- Se image_style for sem-imagem ou dado/grafico, NAO crie elemento image gemini.
- O framework do copywriter veio do strategist — sua hierarquia visual reforca
  esse framework, nao escolhe outro.

Aplique os passos 1-10. Retorne APENAS o JSON do schema do Passo 8, sem texto
antes/depois, sem markdown."""


def generate_design(
    *,
    post,
    copy_payload: Dict[str, Any],
    kb_summary: str,
    paleta: List[Dict[str, Any]],
    tipografia: List[Dict[str, Any]],
    references: List[Dict[str, Any]] = None,
    kb_dossiers: List[Dict[str, Any]] = None,
    modal_choices: Optional[Dict[str, Any]] = None,
    strategic_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Roda o designer agent. Retorna dict:
        {'payload': <JSON designer>, 'usage': <tokens/custo>, 'model': MODEL,
         'iterations': <quantas vezes rodou internamente>}
    Ou None se falhou.

    O designer pode emitir approval.status='iterate' — nesse caso roda de novo
    com o feedback do iterate_on. Max MAX_INTERNAL_ITERATIONS.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('[designer] ANTHROPIC_API_KEY ausente')
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning('[designer] anthropic SDK indisponivel')
        return None

    client = anthropic.Anthropic(api_key=api_key)
    references = references or []
    kb_dossiers = kb_dossiers or []
    modal_choices = modal_choices or {}

    system_blocks = [
        {
            'type': 'text',
            'text': SYSTEM_INTRO,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
        {
            'type': 'text',
            'text': DESIGNER_SKILL_FULL,
            'cache_control': {'type': 'ephemeral', 'ttl': '1h'},
        },
    ]

    # Loop interno de iteracoes (designer pode auto-pedir revisao)
    previous_feedback: List[str] = []
    accumulated_usage = {
        'input_tokens': 0, 'output_tokens': 0,
        'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0,
        'total_tokens': 0, 'cost_usd': 0.0,
    }

    for iteration in range(1, MAX_INTERNAL_ITERATIONS + 1):
        content_blocks = _build_user_content(
            post=post, copy_payload=copy_payload, kb_summary=kb_summary,
            paleta=paleta, tipografia=tipografia, references=references,
            kb_dossiers=kb_dossiers, modal_choices=modal_choices,
            previous_feedback=previous_feedback,
            iteration=iteration,
            strategic_payload=strategic_payload or {},
        )

        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=[{'role': 'user', 'content': content_blocks}],
            )
        except Exception:
            logger.exception('[designer] erro Claude (iter %d)', iteration)
            return None

        raw = ''.join(
            blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text'
        )
        payload = _parse_json(raw)
        if not payload:
            logger.error('[designer] parse JSON falhou (iter %d). Raw: %s',
                         iteration, raw[:400])
            return None

        usage = _extract_usage(resp, cache_ttl='1h')
        _accumulate_usage(accumulated_usage, usage)

        approval = payload.get('approval') or {}
        status = approval.get('status', 'approved')
        logger.info(
            '[designer] iter=%d status=%s confidence=%s tokens=%d cost=$%.4f',
            iteration, status, approval.get('confidence', '?'),
            usage.get('total_tokens', 0), usage.get('cost_usd', 0),
        )

        if status == 'approved' or status == 'blocked' or iteration == MAX_INTERNAL_ITERATIONS:
            return {
                'payload': payload,
                'usage': accumulated_usage,
                'model': MODEL,
                'iterations': iteration,
            }

        # status == 'iterate' — alimenta o feedback e tenta novamente
        iterate_on = approval.get('iterate_on') or []
        previous_feedback.append(
            f"Iteracao {iteration} sugeriu revisar: {'; '.join(iterate_on)}"
        )

    return None


def _build_user_content(*, post, copy_payload, kb_summary, paleta, tipografia,
                        references, kb_dossiers, modal_choices,
                        previous_feedback, iteration,
                        strategic_payload) -> List[Dict[str, Any]]:
    """Monta o conteudo multimodal: texto + (se houver) imagens das refs."""
    blocks: List[Dict[str, Any]] = []

    # Texto principal
    formato = post.post_format
    fmt = {
        'name': formato.aspect_ratio if formato else 'unknown',
        'width_px': formato.width if formato else 1080,
        'height_px': formato.height if formato else 1080,
        'aspect_ratio': formato.aspect_ratio if formato else '1:1',
    }
    user_text = _build_user_text(
        post=post, copy_payload=copy_payload, kb_summary=kb_summary,
        paleta=paleta, tipografia=tipografia, fmt=fmt,
        references_meta=[(i + 1, r) for i, r in enumerate(references)],
        kb_dossiers=kb_dossiers, modal_choices=modal_choices,
        previous_feedback=previous_feedback, iteration=iteration,
        strategic_payload=strategic_payload,
    )

    # Imagens anexadas pro designer ver visualmente
    for i, ref in enumerate(references, 1):
        url = ref.get('url')
        if not url:
            continue
        try:
            b64, mime = _download_image_b64(url)
            if b64:
                blocks.append({
                    'type': 'image',
                    'source': {'type': 'base64', 'media_type': mime, 'data': b64},
                })
        except Exception as exc:
            logger.warning('[designer] falha download imagem %d: %s', i, exc)

    blocks.append({'type': 'text', 'text': user_text})
    return blocks


def _build_user_text(*, post, copy_payload, kb_summary, paleta, tipografia,
                     fmt, references_meta, kb_dossiers, modal_choices,
                     previous_feedback, iteration,
                     strategic_payload) -> str:
    paleta_str = ', '.join(
        f"{(c.get('hex') or '').strip()} ({c.get('tipo') or 'cor'})"
        for c in (paleta or []) if c.get('hex')
    ) or '(sem paleta)'
    tipo_str = ', '.join(
        f"{(t.get('nome') or '?')}({t.get('uso') or '?'})"
        for t in (tipografia or [])[:5]
    ) or '(sem tipografia)'

    lines = []

    if iteration > 1 and previous_feedback:
        lines.append('== ITERACAO INTERNA ==')
        lines.append(f'Esta e a iteracao {iteration}. Em iteracoes anteriores '
                     'voce mesmo pediu revisao com:')
        for f in previous_feedback:
            lines.append(f'  - {f}')
        lines.append('Corrija os problemas e emita designer_payload final.')
        lines.append('')

    if strategic_payload:
        vd = strategic_payload.get('visual_direction') or {}
        cd = strategic_payload.get('copy_direction') or {}
        intent = strategic_payload.get('intention') or {}
        bt = strategic_payload.get('brand_tone') or {}
        lines.extend([
            '== STRATEGIC_PAYLOAD (do estrategista) — OBRIGATORIO OBEDECER ==',
            '(este eh seu brief mestre. nao re-decida. execute.)',
            f'  intention.primary: {intent.get("primary", "?")}',
            f'  intention.visual_triggers: {intent.get("visual_triggers", [])}',
            f'  brand_tone.visual: {bt.get("visual", "?")}',
            f'  brand_tone.contrast_level: {bt.get("contrast_level", "?")}',
            f'  brand_tone.whitespace: {bt.get("whitespace", "?")}',
            '',
            '  visual_direction (seu brief de execucao):',
            f'    image_style: {vd.get("image_style", "?")}  '
            '<-- isto decide se voce DEVE criar elemento image gemini',
            f'    composition: {vd.get("composition", "?")}',
            f'    color_mood: {vd.get("color_mood", "?")}',
            f'    typography_style: {vd.get("typography_style", "?")}',
            f'    special_elements: {vd.get("special_elements", [])}',
            f'    hierarchy: {json.dumps(vd.get("hierarchy", []), ensure_ascii=False)}',
            '',
            f'  copy_direction.framework: {cd.get("framework", "?")}  '
            '<-- sua hierarquia visual reforca este framework',
            f'  copy_direction.key_message: {cd.get("key_message", "?")}',
            '',
        ])

    lines.extend([
        '== COPY_PAYLOAD (do copywriter) ==',
        json.dumps(copy_payload, ensure_ascii=False)[:4000],
        '',
        '== BRIEFING ==',
        f'Rede social: {post.social_network or "instagram"}',
        f'Formato: {fmt["name"]} ({fmt["width_px"]}x{fmt["height_px"]}px, AR {fmt["aspect_ratio"]})',
        f'Tema/contexto: {post.requested_theme or "(sem tema)"}',
        '',
        '== KB_PAYLOAD ==',
        f'Resumo da marca: {(kb_summary or "(sem resumo)")[:1500]}',
        f'Paleta: {paleta_str}',
        f'Tipografia: {tipo_str}',
        '',
        '== MODAL_CHOICES (escolhas diretas do user — prioridade maxima) ==',
        f'logo_position: {modal_choices.get("logo_position") or "(automatica)"}',
        f'reference_aspects: {modal_choices.get("reference_aspects") or {}}',
        f'logo_ids: {modal_choices.get("selected_logo_ids") or []}',
        '',
    ])

    if references_meta:
        lines.append('== REFERENCIAS VISUAIS ANEXADAS (imagens acima deste texto) ==')
        for i, ref in references_meta:
            tipo = ref.get('tipo', '?')
            usage_desc = (ref.get('usage_description') or '').strip()
            line = f'  Imagem {i}: tipo={tipo}'
            if usage_desc:
                line += f' | uso: "{usage_desc}"'
            lines.append(line)
        lines.append('')

    if kb_dossiers:
        lines.append('== DOSSIES VISUAIS DA KB (analise extraida das refs) ==')
        for i, d in enumerate(kb_dossiers, 1):
            aspects = d.get('aspects') or []
            dossier_slim = d.get('dossier') or {}
            lines.append(f'  Dossie KB {i} [aspectos: {", ".join(aspects)}]:')
            lines.append(
                f'    {json.dumps(dossier_slim, ensure_ascii=False)[:2000]}'
            )
        lines.append('')

    lines.extend([
        '== TAREFA ==',
        'Aplique os passos 1-10 do skill carregada. Construa wireframe_plan',
        'completo, image_prompts deterministicos, faca auto-aprovacao (Passo 9).',
        'Retorne APENAS o JSON do schema do Passo 8.',
        '',
        'LEMBRETES IMPORTANTES (iamkt):',
        f'- Canvas: {fmt["width_px"]}x{fmt["height_px"]}px. Use estes px em x/y/width/font_size.',
        '- A integracao converte automaticamente para %_pct na hora de renderizar.',
        '- Para `asset_path` use convencoes logicas: "logo:bottom-right", "logo:auto",',
        '  ou se houver upload de produto, "image:upload_<image_n>".',
        '- O orquestrador resolve `asset_path` para URLs S3 reais.',
        '- Se aprovar (status="approved"), confirme que CADA elemento do copy esta',
        '  no wireframe e cada elemento Gemini tem um image_prompt.',
    ])
    return '\n'.join(lines)


_CLAUDE_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB hard limit da API Anthropic
_CLAUDE_IMAGE_SAFE_BYTES = int(4.5 * 1024 * 1024)  # margem de seguranca


def _shrink_image_for_claude(data: bytes, ct: str) -> tuple:
    """Garante que a imagem cabe no limite de 5MB do Claude.
    Estrategia: JPEG quality 85, se nao bastar redimensiona para 2048x2048.
    Retorna (bytes, content_type)."""
    if len(data) <= _CLAUDE_IMAGE_SAFE_BYTES:
        return data, ct
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        for max_side in (None, 2048, 1536, 1024):
            if max_side and (img.width > max_side or img.height > max_side):
                img.thumbnail((max_side, max_side), Image.LANCZOS)
            for quality in (85, 75, 65):
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=quality, optimize=True)
                out = buf.getvalue()
                if len(out) <= _CLAUDE_IMAGE_SAFE_BYTES:
                    logger.info(
                        '[designer] imagem comprimida %d->%d bytes (%sx%s q%d)',
                        len(data), len(out), img.width, img.height, quality,
                    )
                    return out, 'image/jpeg'
        logger.warning('[designer] nao conseguiu reduzir imagem abaixo de 4.5MB (%d bytes)', len(out))
        return out, 'image/jpeg'
    except Exception:
        logger.exception('[designer] falha redimensionar imagem')
        return data, ct


def _download_image_b64(url: str):
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
    # Limite de 5MB do Claude — recomprime se necessario.
    if len(data) > _CLAUDE_IMAGE_SAFE_BYTES:
        data, ct = _shrink_image_for_claude(data, ct)
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


def _extract_usage(resp, cache_ttl: str = '1h') -> Dict[str, Any]:
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {}
    in_tokens = getattr(usage, 'input_tokens', 0) or 0
    out_tokens = getattr(usage, 'output_tokens', 0) or 0
    cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cache_write_rate = Decimal('6.0') if cache_ttl == '1h' else Decimal('3.75')
    cost = (
        Decimal('3.0') * Decimal(in_tokens) / Decimal(1_000_000)
        + Decimal('15.0') * Decimal(out_tokens) / Decimal(1_000_000)
        + cache_write_rate * Decimal(cache_creation) / Decimal(1_000_000)
        + Decimal('0.30') * Decimal(cache_read) / Decimal(1_000_000)
    )
    return {
        'input_tokens': in_tokens,
        'output_tokens': out_tokens,
        'cache_creation_input_tokens': cache_creation,
        'cache_read_input_tokens': cache_read,
        'total_tokens': in_tokens + out_tokens + cache_creation + cache_read,
        'cost_usd': float(cost),
    }


def _accumulate_usage(acc: Dict[str, Any], one: Dict[str, Any]) -> None:
    for k in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
              'cache_read_input_tokens', 'total_tokens'):
        acc[k] = acc.get(k, 0) + (one.get(k, 0) or 0)
    acc['cost_usd'] = acc.get('cost_usd', 0.0) + (one.get('cost_usd', 0.0) or 0.0)
