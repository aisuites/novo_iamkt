"""
Agente TRANSCRITOR (C3 do redesenho): a arte PUBLICADA do fluxo simple vira
ELEMENTS canonicos (P5) -> o post ganha Edicao Avancada.

Vantagem sobre a pedreira da colletivo (reanalyze_template_v3): aqui NOS
SABEMOS os textos exatos aplicados (post.title/subtitle/cta) e temos as DUAS
imagens (fundo sem texto + arte final). O Claude visao so precisa localizar
GEOMETRIA/COR/ALINHAMENTO de cada texto (e do logo, se aplicado) — o content
dos elements vem dos campos do Post, nunca do modelo.

Q1 (conservador, validado com o dono): o publicado CONTINUA o PNG do Gemini;
so vira re-render Pillow quando o usuario EDITA e salva (ai ele ve o resultado).
"""
import base64
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 2000

_SYSTEM = """Você localiza elementos numa arte de rede social.
Receberá DUAS imagens: (1) o FUNDO sem texto; (2) a ARTE FINAL com textos
(e possivelmente um logo) aplicados sobre esse fundo. Receberá também os
TEXTOS EXATOS que foram aplicados, por papel (titulo/subtitulo/cta).

Sua tarefa: para cada papel presente na arte final, medir com PRECISÃO:
- bbox_pct: {x, y, w, h} do BLOCO do texto, em PERCENTUAL do canvas com
  valores de 0 a 100 (ex.: {"x": 8.5, "y": 27, "w": 62, "h": 14}) — NUNCA
  frações 0-1. x,w relativos à LARGURA; y,h relativos à ALTURA. O bbox cobre
  TODAS as linhas do texto daquele papel.
- font_px: altura APROXIMADA do corpo da fonte em PIXELS (altura de uma
  linha de texto ≈ 1.2x o corpo; meça a altura das maiúsculas e estime).
- color: cor do texto em hex (#RRGGBB), a cor DOMINANTE dos glifos.
- align: left | center | right (alinhamento das linhas dentro do bloco).
- weight: regular | bold (peso visual do traço).

Se houver LOGO na arte final que NÃO está no fundo, meça também:
- logo: {bbox_pct: {x, y, w, h}}

REGRAS:
- Compare as duas imagens: transcreva APENAS o que foi ADICIONADO na final.
- Papel ausente na arte → null.
- Não invente texto; você só mede geometria/cor/alinhamento/peso.
- Responda SÓ com JSON:
{"titulo": {"bbox_pct": {...}, "font_px": N, "color": "#..", "align": "..", "weight": ".."} | null,
 "subtitulo": {...} | null,
 "cta": {...} | null,
 "logo": {"bbox_pct": {...}} | null}"""


def _fetch_b64(url, max_bytes=4_500_000):
    from apps.posts.services.artkit.image import shrink_for_ai
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 IAMKT'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    mime = 'image/png'
    if data[:3] == b'\xff\xd8\xff':
        mime = 'image/jpeg'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        mime = 'image/webp'
    data, mime = shrink_for_ai(data, mime, max_bytes=max_bytes)
    return base64.b64encode(data).decode('ascii'), mime


def _presign(s3_key, fallback=''):
    try:
        from apps.core.services.s3_service import S3Service
        return S3Service.generate_presigned_download_url(s3_key, expires_in=600)
    except Exception:
        return fallback


def transcribe_published_art(post):
    """Transcreve a arte publicada -> (elements canonicos, usage) ou (None, {}).

    NUNCA levanta excecao para o caller (falha = post continua nao-editavel,
    nada quebra)."""
    import os

    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning('[transcribe] ANTHROPIC_API_KEY ausente — skip')
            return None, {}
        # SEMPRE mede o ORIGINAL do Gemini (gemini_final_s3_key) — o publicado
        # (image_s3_key) pode ja ser um re-render Pillow de elements antigos,
        # e medir um re-render envenena a transcricao (licao do post 255).
        si = (post.local_pipeline_context or {}).get('simple_image') or {}
        final_key = si.get('gemini_final_s3_key') or post.image_s3_key
        if not final_key or not post.raw_image_s3_key:
            logger.info('[transcribe] post=%s sem raw/final — skip', post.id)
            return None, {}

        raw_b64, raw_mime = _fetch_b64(_presign(post.raw_image_s3_key))
        fin_b64, fin_mime = _fetch_b64(_presign(final_key))

        known = {
            'titulo': (post.title or '').strip(),
            'subtitulo': (post.subtitle or '').strip(),
            'cta': (post.cta or '').strip(),
        }
        from PIL import Image
        import io
        W, H = Image.open(io.BytesIO(base64.b64decode(fin_b64))).size

        user_blocks = [
            {'type': 'text', 'text': 'IMAGEM 1 — FUNDO sem texto:'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': raw_mime,
                                         'data': raw_b64}},
            {'type': 'text', 'text': 'IMAGEM 2 — ARTE FINAL:'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': fin_mime,
                                         'data': fin_b64}},
            {'type': 'text', 'text': (
                f'Canvas: {W}x{H} pixels.\n'
                f'TEXTOS APLICADOS (por papel):\n{json.dumps(known, ensure_ascii=False)}\n\n'
                'Meça e responda o JSON.')},
        ]

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # sonnet-4-6 NAO suporta prefill de assistant — parse_json extrai o
        # JSON do texto livre.
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=_SYSTEM,
            messages=[{'role': 'user', 'content': user_blocks}],
        )
        raw_text = ''.join(
            b.text for b in resp.content if getattr(b, 'type', None) == 'text')
        from apps.posts.services.artkit.brain import parse_json, extract_usage
        parsed = parse_json(raw_text) or {}
        usage = extract_usage(resp)
        logger.info('[transcribe] post=%s parsed=%s', post.id,
                    json.dumps(parsed, ensure_ascii=False)[:800])

        basis = min(W, H)

        def _clamp(v, lo, hi, default):
            try:
                return max(lo, min(hi, float(v)))
            except (TypeError, ValueError):
                return default

        def _norm_bbox(bb):
            """Defensivo: modelo às vezes devolve frações 0-1 — converte p/ %."""
            bb = bb or {}
            try:
                vals = [float(bb.get(k)) for k in ('x', 'y', 'w', 'h')
                        if bb.get(k) is not None]
                if vals and all(v <= 1.5 for v in vals):
                    return {k: (float(bb.get(k) or 0) * 100.0) for k in ('x', 'y', 'w', 'h')}
            except (TypeError, ValueError):
                pass
            return bb

        elements = []
        for role in ('titulo', 'subtitulo', 'cta'):
            d = parsed.get(role)
            txt = known.get(role)
            if not d or not isinstance(d, dict) or not txt:
                continue
            bb = _norm_bbox(d.get('bbox_pct'))
            font_px = _clamp(d.get('font_px'), 8, basis * 0.3, basis * 0.05)
            elements.append({
                'role': role,
                'content': txt,   # SEMPRE o texto real do Post, nunca do modelo
                'x_pct': round(_clamp(bb.get('x'), 0, 98, 5), 2),
                'y_pct': round(_clamp(bb.get('y'), 0, 98, 5), 2),
                'width_pct': round(_clamp(bb.get('w'), 2, 100, 60), 2),
                'height_pct': round(_clamp(bb.get('h'), 0, 100, 0), 2),
                'font_size_pct': round(font_px / basis * 100.0, 3),
                'color': (d.get('color') or '#FFFFFF'),
                'align': (d.get('align') if d.get('align') in ('left', 'center', 'right')
                          else 'left'),
                'weight': ('bold' if (d.get('weight') or '') in ('bold', 'black',
                                                                 'heavy', 'semibold')
                           else 'regular'),
                '_source': 'vision_transcribe',
            })
        lg = parsed.get('logo')
        if lg and isinstance(lg, dict):
            bb = _norm_bbox(lg.get('bbox_pct'))
            elements.append({
                'role': 'logo',
                'x_pct': round(_clamp(bb.get('x'), 0, 98, 80), 2),
                'y_pct': round(_clamp(bb.get('y'), 0, 98, 4), 2),
                'width_pct': round(_clamp(bb.get('w'), 2, 60, 14), 2),
                'height_pct': round(_clamp(bb.get('h'), 0, 60, 0), 2),
                '_source': 'vision_transcribe',
            })

        if not elements:
            logger.info('[transcribe] post=%s modelo nao localizou elementos', post.id)
            return None, usage
        logger.info('[transcribe] post=%s -> %d elements (%s)', post.id,
                    len(elements), [e['role'] for e in elements])
        return elements, usage
    except Exception:
        logger.exception('[transcribe] falhou post=%s (nao-fatal)', post.id)
        return None, {}
