"""
Pipeline SIMPLES (v2) — Fase 2, Etapa 3: Aplicacao de texto via modelo de imagem.

Envia ao Gemini (Nano Banana / GEMINI_IMAGE_MODEL):
  - a imagem de fundo gerada SEM texto;
  - SPECIMEN(s) de fonte: imagem PNG com o texto real renderizado no .ttf/.otf
    da marca, para o modelo replicar aquele desenho de letra;
  - o logo (PNG) quando houver, com posicionamento obrigatorio quando definido;
  - os textos EXATOS da Fase 1 e o briefing resolvido (Etapa 2).

Retorna a imagem final (texto aplicado) + o prompt enviado (para debug).

NOTA: a API REST generateContent do Gemini NAO aceita arquivo de fonte como
inlineData (HTTP 400 "Unsupported MIME type: font/ttf"). Por isso enviamos a
fonte como SPECIMEN renderizado (image/png), que e suportado e da ao modelo as
formas reais das letras.
"""

import base64
import io
import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

from apps.posts.services.gemini_image_generator import (
    _resolved_endpoint,
    _extract_image_from_response,
)

logger = logging.getLogger(__name__)


def _render_specimen(text: str, font_path: str, font_px: int = 110) -> bytes:
    """Renderiza `text` no `font_path` (.ttf/.otf) e devolve PNG (specimen)."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(font_path, font_px)
    except Exception:
        font = ImageFont.load_default()
    sample = (text or 'ABCDEÁÉÍ abcdeáéí 0123').strip()[:60] or 'Aa Bb Cc'
    tmp = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    bbox = tmp.textbbox((0, 0), sample, font=font)
    w = max(200, bbox[2] - bbox[0] + 60)
    h = max(120, bbox[3] - bbox[1] + 60)
    img = Image.new('RGB', (w, h), '#ffffff')
    draw = ImageDraw.Draw(img)
    draw.text((30, 20), sample, font=font, fill='#111111')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _build_prompt(*, textos, briefing, formato_px, has_logo, logo_position,
                  font_labels):
    """Monta o prompt de aplicacao de texto (em PT, instrucao direta)."""
    title = (textos.get('title') or '').strip()
    subtitle = (textos.get('subtitle') or '').strip()
    cta = (textos.get('cta') or '').strip()

    lines = [
        'TAREFA: aplicar texto sobre a imagem de fundo ANEXADA, produzindo um post '
        'profissional de redes sociais dentro das melhores praticas de design.',
        '',
        'FIDELIDADE DA IMAGEM (CRITICO): mantenha a imagem de fundo anexada EXATAMENTE '
        'como esta — nao altere cena, cores, objetos ou composicao. Apenas adicione os '
        'textos/elementos por cima e adeque ao formato final.',
        '',
        'FIDELIDADE DO TEXTO (CRITICO): escreva os textos com EXATIDAO ABSOLUTA, '
        'caractere por caractere, incluindo acentos. NAO traduza, NAO reescreva, NAO '
        'abrevie, NAO corrija.',
        '',
        'FONTE (CRITICO): replique EXATAMENTE o desenho de letra mostrado na(s) '
        'imagem(ns)-amostra de fonte anexada(s) ao desenhar os textos. ' + font_labels,
        '',
        f'TÍTULO (texto exato): «{title}»' if title else 'TÍTULO: (nenhum)',
        f'SUBTÍTULO (texto exato): «{subtitle}»' if subtitle else 'SUBTÍTULO: (nenhum)',
        '',
        f'FORMATO FINAL: {formato_px} px.',
    ]

    paleta_hex = briefing.get('paleta_hex') or []
    paleta_str = ', '.join(paleta_hex) if paleta_hex else '(paleta da marca)'

    # CTA — único elemento gráfico permitido, no formato pill
    if cta:
        lines += [
            '',
            f'CTA (texto exato): «{cta}»',
            '  → Desenhe o CTA como um PILL: retângulo de cantos TOTALMENTE arredondados,',
            '    com PADDING de respiro generoso nas laterais E em cima/baixo (o texto nunca encosta na borda).',
            f'    Cor de preenchimento do pill: escolha UMA cor da paleta {paleta_str} que CONTRASTE',
            '    com o fundo atrás dele; o texto do CTA em cor legível e contrastante sobre o pill.',
        ]
    else:
        lines += ['', 'CTA: nenhum — NÃO desenhe CTA, botão ou selo.']

    # Logo
    if has_logo:
        if logo_position:
            lines.append(f'LOGO: aplique o logo ANEXADO na posição OBRIGATÓRIA: {logo_position}.')
        else:
            lines.append('LOGO: aplique o logo ANEXADO de forma harmônica (posição a seu critério).')
    else:
        lines.append('LOGO: não aplicar logo.')

    # Restrição dura de elementos
    permitidos = ['título', 'subtítulo']
    if cta:
        permitidos.append('CTA (pill)')
    if has_logo:
        permitidos.append('logo')
    lines += [
        '',
        'ELEMENTOS PERMITIDOS (CRÍTICO): adicione SOMENTE ' + ', '.join(permitidos) + '.',
        'PROIBIDO adicionar QUALQUER outro elemento: grafismos, formas, ícones, molduras, '
        'faixas, linhas, texturas, gradientes, sombras decorativas, selos, badges, overlays '
        'ou efeitos visuais. Nada além do fundo intacto + os textos'
        + (' + o CTA pill' if cta else '') + (' + o logo' if has_logo else '') + '.',
        '',
        'BRIEFING DE LAYOUT (regras de ouro + diretrizes):',
        json.dumps(briefing, ensure_ascii=False, indent=2),
        '',
        'Respeite paleta (HEX), tipografia e a zona/alinhamento de texto do briefing. '
        'Garanta legibilidade, hierarquia visual e contraste.',
    ]
    return '\n'.join(lines)


def apply_text_to_image(*, background_png, font_paths, logo_png=None,
                        textos, briefing, formato_px, logo_position='',
                        temperature=0.4):
    """Chama o Gemini para aplicar texto sobre o fundo. Retorna dict.

    background_png: bytes do fundo sem texto
    font_paths: lista de caminhos .ttf/.otf a anexar
    logo_png: bytes do logo (opcional)
    Retorna: {png_bytes, prompt_text, model, usage}
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY ausente')

    parts = [
        {'inlineData': {'mimeType': 'image/png',
                        'data': base64.b64encode(background_png).decode('ascii')}}
    ]

    # SPECIMENS: renderiza o texto real em cada fonte e anexa como imagem.
    # (font_paths[0]=titulo -> usa o titulo; demais -> usa subtitulo/cta como amostra)
    title = (textos.get('title') or '').strip()
    sub_cta = ' '.join(x for x in [(textos.get('subtitle') or '').strip(),
                                    (textos.get('cta') or '').strip()] if x)
    font_labels_bits = []
    for idx, fp in enumerate(font_paths or []):
        sample = title if idx == 0 else (sub_cta or title)
        try:
            spec_png = _render_specimen(sample, fp)
        except Exception:
            logger.warning('[posts.simple] falha ao renderizar specimen: %s', fp)
            continue
        parts.append({'inlineData': {'mimeType': 'image/png',
                                     'data': base64.b64encode(spec_png).decode('ascii')}})
        font_labels_bits.append(os.path.basename(fp))
    font_labels = (
        f'Amostras de fonte anexadas (replique este desenho de letra): {", ".join(font_labels_bits)}.'
        if font_labels_bits else
        'Nenhuma amostra de fonte — use uma tipografia coerente com a marca.'
    )

    has_logo = bool(logo_png)
    if logo_png:
        parts.append({'inlineData': {'mimeType': 'image/png',
                                     'data': base64.b64encode(logo_png).decode('ascii')}})

    prompt_text = _build_prompt(
        textos=textos, briefing=briefing, formato_px=formato_px,
        has_logo=has_logo, logo_position=logo_position, font_labels=font_labels,
    )
    parts.append({'text': prompt_text})

    payload = {
        'contents': [{'parts': parts}],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
            'temperature': temperature,
        },
    }

    model_used, endpoint = _resolved_endpoint()
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        err = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Gemini (apply text) HTTP {exc.code}: {err[:500]}')

    response_json = json.loads(data.decode('utf-8'))
    png_bytes, _mime = _extract_image_from_response(response_json)
    if not png_bytes:
        raise RuntimeError(
            f'Gemini nao retornou imagem (apply text): {json.dumps(response_json)[:500]}'
        )

    usage_meta = response_json.get('usageMetadata', {}) or {}
    input_tokens = int(usage_meta.get('promptTokenCount', 0) or 0)
    cost = float(Decimal(input_tokens) * Decimal('0.10') / Decimal(1_000_000) + Decimal('0.04'))

    logger.info('[posts.simple] texto aplicado via %s (fontes=%d, logo=%s)',
                model_used, len(font_labels_bits), has_logo)
    return {
        'png_bytes': png_bytes,
        'prompt_text': prompt_text,
        'model': model_used,
        'usage': {'input_tokens': input_tokens, 'output_tokens': 0,
                  'total_tokens': input_tokens, 'cost_usd': cost},
    }
