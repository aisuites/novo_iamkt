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
- n_lines: em QUANTAS linhas visuais o texto está quebrado na arte.
- color: cor do texto em hex (#RRGGBB), a cor DOMINANTE dos glifos.
- align: left | center | right (alinhamento das linhas dentro do bloco).
- weight: regular | bold (peso visual do traço).

Para o CTA, meça TAMBÉM (se ele tiver um fundo tipo botão/pill):
- background_color: hex do fundo do botão (null se o texto está solto, sem fundo)
- radius_px: raio dos cantos arredondados do botão, em pixels
- (o bbox_pct do CTA deve cobrir o BOTÃO inteiro, não só o texto)

Se houver LOGO na arte final que NÃO está no fundo, meça também:
- logo: {bbox_pct: {x, y, w, h}}

REGRAS:
- Compare as duas imagens: transcreva APENAS o que foi ADICIONADO na final.
- USE A GRADE magenta da IMAGEM 2 para LER as coordenadas (linhas a cada
  10%): localize entre quais linhas cada borda do bloco está e interpole.
- Meça o y de CADA bloco INDEPENDENTEMENTE na grade — NUNCA derive a posição
  de um bloco a partir do bbox de outro.
- O bbox deve ser JUSTO: do topo da PRIMEIRA linha de texto à base da
  ÚLTIMA linha — sem folga acima/abaixo (bbox inflado desloca os vizinhos).
- PRECISÃO VERTICAL: y é a distância do TOPO do canvas ao TOPO do bloco.
  Valide cada y contra os terços da imagem (bloco no terço superior → y < 33;
  médio → 33-66; inferior → > 66) e confira que os blocos NÃO se sobrepõem:
  y(subtítulo) ≥ y(título)+h(título); y(cta) ≥ y(subtítulo)+h(subtítulo).
- Papel ausente na arte → null.
- Não invente texto; você só mede geometria/cor/alinhamento/peso.
- Responda SÓ com JSON:
{"titulo": {"bbox_pct": {...}, "font_px": N, "n_lines": N, "color": "#..", "align": "..", "weight": ".."} | null,
 "subtitulo": {...} | null,
 "cta": {..., "background_color": "#.."|null, "radius_px": N} | null,
 "logo": {"bbox_pct": {...}} | null}"""


def _overlay_measure_grid(png_b64):
    """Sobrepoe uma GRADE DE MEDICAO (linhas magenta a cada 10% com rotulos)
    na copia da imagem enviada ao modelo — modelos de visao medem coordenadas
    com muito mais precisao lendo uma grade visivel do que estimando a olho
    (bbox do titulo vinha 'gordo' e empurrava o subtitulo — post 260)."""
    import io
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert('RGB')
    W, H = img.size
    d = ImageDraw.Draw(img)
    mag = (255, 0, 200)
    for i in range(1, 10):
        x = int(W * i / 10)
        y = int(H * i / 10)
        d.line([(x, 0), (x, H)], fill=mag, width=1)
        d.line([(0, y), (W, y)], fill=mag, width=1)
        d.text((x + 3, 3), str(i * 10), fill=mag)
        d.text((3, y + 3), str(i * 10), fill=mag)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


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


def _solve_font_px(text, font_path, box_w_px, n_lines, estimate_px):
    """Resolve GEOMETRICAMENTE o corpo da fonte: maior tamanho cujo texto,
    quebrado por palavra na LARGURA MEDIDA do bloco, cabe em <= n_lines
    (com a TTF REAL da KB — mata o erro de estimativa visual do modelo).
    Fallback: estimativa do modelo."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from apps.posts.services.artkit.text import wrap_greedy
        if not font_path or not text or box_w_px <= 0:
            return estimate_px
        draw = ImageDraw.Draw(Image.new('RGB', (8, 8)))
        n_lines = max(1, int(n_lines or 1))
        lo, hi, best = 8, 300, None
        while lo <= hi:
            mid = (lo + hi) // 2
            font = ImageFont.truetype(font_path, mid)
            lines = wrap_greedy(text, font, box_w_px, draw)
            fits = (len(lines) <= n_lines
                    and all(draw.textlength(ln, font=font) <= box_w_px for ln in lines))
            if fits:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return float(best) if best else estimate_px
    except Exception:
        return estimate_px


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
            {'type': 'text', 'text': 'IMAGEM 2 — ARTE FINAL (com GRADE DE '
                                      'MEDIÇÃO magenta sobreposta: linhas a '
                                      'cada 10%, rótulos nas bordas — a grade '
                                      'NÃO faz parte da arte):'},
            # a grade re-encoda a copia em PNG — o media_type acompanha
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                         'data': _overlay_measure_grid(fin_b64)}},
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

        # Fontes REAIS da KB (por role) — usadas p/ resolver o corpo
        # geometricamente e garantir a tipografia definida no KB.
        try:
            from apps.posts.views_overlay import _get_font_paths
            font_paths = _get_font_paths(post) or {}
        except Exception:
            font_paths = {}

        elements = []
        for role in ('titulo', 'subtitulo', 'cta'):
            d = parsed.get(role)
            txt = known.get(role)
            if not d or not isinstance(d, dict) or not txt:
                continue
            bb = _norm_bbox(d.get('bbox_pct'))
            w_pct = _clamp(bb.get('w'), 2, 100, 60)
            font_px = _clamp(d.get('font_px'), 8, basis * 0.3, basis * 0.05)
            is_bold = (d.get('weight') or '') in ('bold', 'black', 'heavy',
                                                  'semibold')
            # Corpo GEOMETRICO: maior tamanho que preenche a largura medida
            # com a fonte real da KB em n_lines linhas (a estimativa visual
            # do modelo tende a subestimar). CRITICO: resolver com a MESMA
            # variante que o render vai usar — bold e mais LARGA; resolver
            # com a regular faz o fitter do render encolher o texto depois.
            solve_font = ((font_paths.get(role + '_bold') if is_bold else None)
                          or font_paths.get(role))
            font_px = _solve_font_px(txt, solve_font,
                                     w_pct / 100.0 * W,
                                     d.get('n_lines'), font_px)
            # Altura do bloco: CALCULADA (n_linhas x corpo x entrelinha) — a
            # medida visual vinha inflada e deslocava a percepcao dos vizinhos.
            n_lines = max(1, int(_clamp(d.get('n_lines'), 1, 8, 1)))
            h_pct_calc = round(n_lines * font_px * 1.2 / H * 100.0, 2)
            el = {
                'role': role,
                'content': txt,   # SEMPRE o texto real do Post, nunca do modelo
                'x_pct': round(_clamp(bb.get('x'), 0, 98, 5), 2),
                'y_pct': round(_clamp(bb.get('y'), 0, 98, 5), 2),
                'width_pct': round(w_pct, 2),
                'height_pct': h_pct_calc,
                'font_size_pct': round(font_px / basis * 100.0, 3),
                'color': (d.get('color') or '#FFFFFF'),
                'align': (d.get('align') if d.get('align') in ('left', 'center', 'right')
                          else 'left'),
                'weight': ('bold' if is_bold else 'regular'),
                '_source': 'vision_transcribe',
            }
            # CTA tipo botao: fundo/radius sao PROPRIEDADES do proprio elemento
            # (decisao do dono 2026-07-08) — o motor ja desenha o pill
            # (_draw_cta_background) e o texto centraliza no box.
            if role == 'cta' and (d.get('background_color') or '').strip():
                el['background_color'] = d['background_color'].strip()
                el['radius_pct'] = round(
                    _clamp(d.get('radius_px'), 0, W * 0.1, 8) / W * 100.0, 3)
                el['align'] = 'center'
                # dentro do pill, o corpo geometrico "preencher a largura"
                # nao vale (o botao tem padding) — mantem a estimativa visual.
                fp = _clamp(d.get('font_px'), 8, basis * 0.3, basis * 0.05)
                el['font_size_pct'] = round(fp / basis * 100.0, 3)
            elements.append(el)
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

        # Persiste as DIMENSOES REAIS da arte no ctx: o canvas do modal deve
        # ser o da imagem (post_format pode divergir — ex.: 1200x630 vs
        # 1424x752 do Gemini), senao o editor desenha em proporcao diferente.
        try:
            ctx = post.local_pipeline_context or {}
            si = ctx.get('simple_image') or {}
            si['canvas'] = [W, H]
            ctx['simple_image'] = si
            post.local_pipeline_context = ctx
            post.save(update_fields=['local_pipeline_context'])
        except Exception:
            logger.exception('[transcribe] falha ao persistir canvas post=%s', post.id)
        logger.info('[transcribe] post=%s -> %d elements (%s)', post.id,
                    len(elements), [e['role'] for e in elements])
        return elements, usage
    except Exception:
        logger.exception('[transcribe] falhou post=%s (nao-fatal)', post.id)
        return None, {}
