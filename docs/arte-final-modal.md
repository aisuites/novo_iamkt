# Arte Final Modal — Documentação Técnica Completa

> Branch: `feature/novo-modal-gerar-post`  
> Última atualização: 2026-05-29

---

## 1. Visão Geral

O modal "Arte Final" permite ao usuário visualizar e editar o post gerado (textos, logo, posições, cores, tamanhos) diretamente no browser e exportar o resultado final como PNG via Playwright (Chromium headless).

**Fluxo end-to-end:**
```
Fase 1 — Texto (Celery task: generate_post_text_task)
  └─ Strategist → Copywriter → salva copy_payload + _strategic_payload

Fase 2 — Imagem (Celery task: generate_post_image_task)
  ├─ prompt_designer.build_prompt()  → prompt EN para Gemini
  ├─ layout_engine.build_elements()  → _layout_elements (% coords)
  ├─ Gemini API                      → PNG raw (sem texto)
  ├─ render_layout_document (Pillow) → PNG final com textos/logo
  └─ Salva raw_image_s3_key + _layout_elements em designer_payload

Frontend — Modal "Arte Final"
  ├─ overlay_data()  → elements + URLs + font_names
  ├─ JS editor       → click para selecionar, editar posição/cor/tamanho/texto
  ├─ save_elements() → persiste edições no banco (ao fechar ou exportar)
  └─ export_png()    → urllib baixa S3 → data URIs → Playwright → PNG download
```

---

## 2. Pipeline de Geração

### 2.1 Flag de ativação

```python
# tasks.py — Fase 1 e Fase 2
use_new_pipeline = os.environ.get('POST_USE_NEW_PIPELINE', '').lower() in ('1', 'true', 'yes')
```

O pipeline novo só ativa quando `POST_USE_NEW_PIPELINE=true` **e** `copy_payload` contém `_strategic_payload` (prova que a Fase 1 rodou pelo novo fluxo).

### 2.2 Agentes (Fase 1 — generate_post_text_task)

| Agente | Arquivo | Saída |
|--------|---------|-------|
| Strategist | `services/strategist_agent.py` | `strategic_payload`: formato, paleta, composição, zona de texto (%), safe_zone |
| Copywriter | `services/copywriter_agent.py` | `copy_payload.variants[].copy`: headline, subtitulo, body, cta |

O `strategic_payload` é embutido em `copy_payload['_strategic_payload']` para que a Fase 2 o consuma sem busca adicional.

### 2.3 Campos de copy — distinção crítica

| Campo | Uso | Onde aparece |
|-------|-----|-------------|
| `headline` | Título principal | **Na imagem** (H1) |
| `subtitulo` | Subtítulo curto ≤12 palavras — visual da arte | **Na imagem** (H2) |
| `cta` | Call-to-action ≤5 palavras | **Na imagem** (pill) |
| `body` | Legenda/caption da rede social | **Só no post**, nunca na imagem |

> **Regra implementada no layout_engine:** `copy.get('subtitulo')` — o campo `body` (legenda) é ignorado para posicionamento na arte.

### 2.4 Fase 2 — Orquestração (generate_post_image_task)

```python
# 1. Prompt Gemini via prompt_designer
_prompt_result = build_prompt(strategic_payload, copy_payload, canvas_w, canvas_h, kb_dossiers)
orchestrator_image_prompt = _prompt_result.get('prompt', '')

# 2. Fontes da KB
_font_map = { 'titulo': pillow_title_font_path, 'subtitulo': pillow_subtitle_font_path, 'cta': ... }

# 3. Cor de fundo dominante da referência (para contraste do subtítulo)
_bg_color = _dominant_bg_from_dossiers(kb_dossiers)

# 4. Elementos de layout
_elements = layout_engine.build_elements(
    strategic_payload, copy_payload, canvas_w, canvas_h,
    paleta, fonts, modal_choices, bg_color=_bg_color
)
layout_document = {'elements': _elements}

# 5. Persiste para o modal HTML
post.designer_payload['_layout_elements'] = _elements
post.save(update_fields=['designer_payload'])

# 6. Gemini gera PNG raw
result = generate_post_image(image_prompt_override=orchestrator_image_prompt, ...)

# 7. Pillow renderiza texto sobre o PNG raw (render_layout_document)
png_bytes = render_layout_document(raw_png, elements=_elements, fonts=..., logo_url=...)

# 8. Upload S3 → salva raw_image_s3_key no Post
```

**Fallback:** Se `layout_engine` falhar, cai para `designer_payload.wireframe_plan` (caminho antigo via `_consume_designer_payload`).

---

## 3. layout_engine.py

**Filosofia:** A hierarquia define o tamanho da fonte. O fitting (shrink) só acontece se o texto for genuinamente longo demais. Nunca define tamanho pelo espaço disponível.

### 3.1 Escala tipográfica

```python
BASE_DIVISOR = 35   # canvas_h / 35 = "1rem do canvas"

SCALE = {
    'h1':   3.0,   # título — impacto máximo
    'h2':   1.4,   # subtítulo
    'cta':  1.2,   # call to action
    'body': 1.0,   # referência (não aparece na arte)
}

base_px = canvas_h / 35          # ex: 1080/35 ≈ 30.8px
h1_px   = int(base_px * 3.0)     # ≈ 92px
h2_px   = int(base_px * 1.4)     # ≈ 43px
cta_px  = int(base_px * 1.2)     # ≈ 36px
```

### 3.2 Ordem de renderização dos elementos

1. **Headline** — ancora no TOPO da zona de texto; `max_lines=3`; reduz até 60% do H1 se necessário
2. **CTA pill** — ancora na BASE da zona; `max_lines=1` (evita quebra); pill = `radius = height/2`
3. **Subtítulo** — flui entre headline e CTA; `max_h_av = cta_top - hl_bottom - 2×gap`
4. **Logo** — posição vem de `modal_choices['logo_position']` (ex: `'bottom-right'`) aplicando os insets da `safe_zone`

### 3.3 Pill CTA

```python
CTA_PILL_PAD_H = 10   # padding horizontal (px)
CTA_PILL_PAD_V = 7    # padding vertical (px)

pill_h   = cta_line_h + CTA_PILL_PAD_V * 2
pill_w   = text_width + CTA_PILL_PAD_H * 2   # limitado a zone_w_px
radius   = pill_h // 2   # pill totalmente arredondado
```

Dois elementos emitidos: `role='grafismo'` (fundo colorido) + `role='cta'` (texto branco centralizado).

### 3.4 Extração da zona de texto — `_extract_text_zone`

Parseia dois formatos emitidos pelo strategist:

```
Formato A (estruturado — preferencial):
  "bloco de texto ... (x=5% y=30% w=40% h=40%)"
  → retorna (w_pct=40, side='left', x_pct=5)

Formato B (livre):
  "esquerda (35%)"  /  "left 35%"  /  "direita (40%)"
  → retorna (pct, side, x_pct=0)

Fallback: (38, 'left', 0)
```

### 3.5 Cor do subtítulo — contraste automático

```python
def _contrast_color(bg_hex, fallback='#23282A'):
    if not bg_hex:
        return fallback        # cor da marca (seguro na maioria dos fundos)
    return '#23282A' if _is_light(bg_hex) else '#FFFFFF'
    # _is_light: luminância relativa = (0.2126R + 0.7152G + 0.0722B)/255 > 0.5
```

A cor de fundo `bg_hex` vem de `_dominant_bg_from_dossiers` — cor dominante (papel='dominante') da `paleta_observada` do dossier da KB.

### 3.6 Logo — margem de segurança

```python
lw_px = int(canvas_w * 0.15)   # 15% da largura
lh_px = int(canvas_h * 0.12)   # 12% da altura

# Usa os mesmos insets do safe_zone (safe_r, safe_b, etc.)
# Garante respiro consistente com o resto da composição
if 'right' in logo_pos:
    lx = canvas_w - lw_px - safe_r
```

### 3.7 `_fit_font` — fitting tipográfico

```python
def _fit_font(text, font_path, max_width, max_lines, size_start, size_min, max_height=99999):
    # Tenta size_start → decrementa 1px por vez até caber em max_lines × max_width
    # Retorna (font_size, lines, total_height_px)
    # Usa Pillow draw.textbbox para medir largura real com a fonte carregada
```

---

## 4. font_resolver.py

### 4.1 Estratégia em 4 camadas

```
1. CustomFont da KB (TTF/OTF privado no S3 — apps.knowledge.CustomFont)
2. Google Fonts via CSS API (font_source='google')
3. Cache local em /app/fonts_cache/
4. Fallback DejaVu do sistema
```

### 4.2 Regra de peso — mantém a família antes de trocar

```python
def _load_google_font(family, weight):
    # Gera sequência de pesos ordenados por proximidade ao solicitado:
    all_nums = [100, 200, 300, 400, 500, 600, 700, 800, 900]
    candidates = sorted(all_nums, key=lambda w: (abs(w - requested_num), w))
    # Tenta Lora 300 → 400 → 200 → 500 → ... até achar TTF disponível
    # NÃO troca para outra família — preserva a fonte da KB
```

**Problema que motivou:** Lora 300 não existe no Google Fonts. O código antigo trocava de família. Agora tenta `Lora 400` antes de desistir.

### 4.3 User-Agent Android para forçar TTF

```python
# Google Fonts serve WOFF2 para browsers modernos (Pillow não lê WOFF2)
# User-Agent Android 2.3.5 → Google retorna TTF
'User-Agent': 'Mozilla/5.0 (Linux; U; Android 2.3.5)'
```

### 4.4 `_pick_by_weight` — escolhe variante pelo nome

Entre Typographies que casam o `usage`, escolhe a que melhor bate com o peso pedido olhando o nome do arquivo (ex: `_Vorwerk-Bold` → bold=True → score+10 para peso bold).

---

## 5. gemini_image_generator.py

### 5.1 `_normalize_tipo` — ordem importa

```python
def _normalize_tipo(tipo):
    ...
    if 'referencia_layout' in t or 'layout' in t:  # ANTES de 'refer'
        return 'referencia_layout'
    if 'refer' in t:
        return 'referencia'
```

**Bug corrigido:** `referencia_layout` caía no branch `referencia` (genérico) porque a checagem de `'refer'` vinha primeiro. Invertida a ordem.

### 5.2 Labels por tipo de imagem

| Tipo normalizado | Label no prompt | Fidelidade |
|-----------------|----------------|-----------|
| `logo` | `BRAND LOGO` | aplicar SEM alteração |
| `produto` | `PRODUCT` | mesma identidade, ângulo pode variar moderadamente |
| `pessoa` | `MODEL` | mesma pessoa — rosto, cabelo, tom de pele idênticos |
| `cenario` | `SETTING` | ambiente exato — arquitetura, luz, atmosfera |
| `fundo` | `BACKGROUND TEXTURE` | referência de textura/tom |
| `referencia` | `STYLE REFERENCE` | inspiração de estilo apenas |
| `referencia_layout` | `GRAPHIC & LAYOUT REFERENCE` | replicar grafismos com fidelidade total |

### 5.3 Blocos do prompt (modos pillow/sanitized)

```
[REFERENCE ROLES]
  Image N (LABEL): regra de fidelidade.
  MANDATORY BRIEF FOR Image N — read and apply with full fidelity:
    <usage_description do grafismo — bloco dedicado, não parêntese inline>

[PRE-GENERATION — MANDATORY STEP]
  Examine Image N (GRAPHIC & LAYOUT REFERENCE) before generating.
  → Image N: descrição do grafismo

[SCENE]
  ... prompt principal ...

[FIDELITY REQUIREMENTS]
  All N referenced items must appear simultaneously. Graphic elements must
  match the GRAPHIC & LAYOUT REFERENCE exactly.
  AVOID / EVITE: altered product, different bag, generated face, merged elements...
```

**Decisão de design:** O brief do grafismo vai em `MANDATORY BRIEF FOR Image N` (bloco dedicado) — antes estava como `(user note: "...")` parentético, que tinha peso semântico fraco.

### 5.4 `text_render_mode`

| Modo | Comportamento |
|------|---------------|
| `inline` | Texto vai no prompt do Gemini — Gemini renderiza texto (pode introduzir erros) |
| `sanitized` | Substitui termos da marca por placeholders antes de enviar ao Gemini |
| `pillow` | Gemini gera apenas a cena (sem texto); Pillow aplica overlay depois |

No pipeline novo, sempre usa `pillow` (texto via `render_layout_document`).

### 5.5 `render_layout_document` (Pillow)

```python
def render_layout_document(png_bytes, elements, paleta, fonts, logo_url):
    # Ordem de renderização:
    # 1. Grafismos (faixas/shapes) — ficam ATRÁS de tudo
    # 2. Logo
    # 3. Textos (2 passadas):
    #    - 1a passada: coleta dados brutos, ordena por y_pct
    #    - 2a passada: calcula max_h (height_pct declarado OU gap até próximo bloco)
    #                  roda _fit_text_to_box com start_size = layout_engine's font_size_pct
    #                  min_size = max(12, int(start_size * 0.6))
    #                  — honra o tamanho do layout_engine; shrink só como segurança
```

**Bug corrigido:** O `min_size` antigo era `int(basis * 0.03) ≈ 32px`, ignorando completamente o `font_size_pct` calculado pelo `layout_engine`. Corrigido para `max(12, int(start_size * 0.6))`.

### 5.6 Custo Gemini

```python
input_cost  = input_tokens × $0.10 / 1M
output_cost = images_out   × $0.04 / imagem
real_cost   = input_cost + output_cost
```

---

## 6. prompt_designer.py

Claude (Sonnet 4.6) recebe o `strategic_payload` + `copy_payload` + `kb_dossiers` e gera o prompt em inglês para o Gemini.

### 6.1 System prompt — regras críticas

```
CRITICAL RULE — REFERENCE BY ROLE, NOT BY INDEX:
  Never say "IMAGE 1" or "IMAGE 2".
  Always mention the image by its ROLE LABEL.
  Example: "the GRAPHIC & LAYOUT REFERENCE image"

CRITICAL RULE — FIDELITY DECLARATION:
  a) Name the source by role
  b) Use strong language: "mandatory", "must", "exactly", "with full fidelity"
  c) Never: "inspired by", "similar to", "as in the reference"
```

### 6.2 Estrutura do prompt gerado (5 blocos)

```
== Canvas: WxH | Aspect ratio: X:X ==
== REFERENCE IMAGES SENT TO GEMINI (by role) ==
== VISUAL STYLE DESCRIPTION (from the GRAPHIC & LAYOUT REFERENCE image) ==
  recreation_prompt do dossier (extraído da análise 1× da KB)
== PALETTE FROM REFERENCE IMAGE ==
  bg_color = paleta_observada[papel='dominante'] → prioridade sobre brand palette
== GRAPHIC ELEMENTS — mandatory, replicate from the GRAPHIC & LAYOUT REFERENCE image ==
  assets_grafismos: tipo | color | style | POSITION | function
== COMPOSITION ZONES ==
  text overlay zone: left N% of frame — LOW VISUAL COMPLEXITY
== FIDELITY INSTRUCTION ==
== MANDATORY ==
  No text, no typography, no letters, no logos anywhere.
```

### 6.3 Fonte dos dados

- `recreation_prompt`: gerado pela análise visual da KB (dossiê visual — roda 1× por KB)
- `paleta_observada`: cores reais extraídas da referência (não a brand palette)
- `assets_grafismos`: lista de grafismos com posição, cor, estilo, função
- `composicao_ref`: espaço negativo e enquadramento da referência

---

## 7. html_renderer.py

### 7.1 Assinatura

```python
def build_html(elements, raw_image_url, logo_url, canvas_w, canvas_h, font_paths) -> str
```

> `raw_image_url` e `logo_url` **devem ser `data:image/...;base64,...`** URIs — nunca URLs externas. O Playwright não carrega URLs externas de dentro do headless Chromium.

### 7.2 Fontes embutidas

```python
# Cada fonte TTF é lida e embutida como base64 @font-face
@font-face {
    font-family: 'CustomFont_titulo';
    src: url('data:font/truetype;base64,...') format('truetype');
}
```

Cada `role` (titulo, subtitulo, cta) tem seu próprio `@font-face` com nome `CustomFont_<role>`.

### 7.3 Estrutura HTML gerada

```html
<div class="canvas">
  <img class="canvas-bg" src="data:image/jpeg;base64,...">  <!-- imagem Gemini -->

  <!-- Grafismo (pill) -->
  <div class="el el-pill" style="left:4.6%;top:79%;width:34%;height:8%;
       background:#5C1A1A;border-radius:43px;"></div>

  <!-- Logo -->
  <img class="el el-logo" src="data:image/png;base64,..."
       style="left:79%;top:4%;width:17%;height:10%;">

  <!-- Título -->
  <div class="el el-titulo" style="left:4.6%;top:14.8%;width:40%;
       color:#5C1A1A;font-size:92px;font-weight:bold;
       font-family:'CustomFont_titulo',serif;">Você cuida de si...</div>

  <!-- Subtítulo -->
  <div class="el el-subtitulo" style="...font-family:'CustomFont_subtitulo',serif;">
    O autocuidado estético...
  </div>

  <!-- CTA (texto sobre o pill) -->
  <div class="el el-cta" style="...display:flex;align-items:center;justify-content:center;">
    Conheça nossa abordagem
  </div>
</div>
```

---

## 8. views_overlay.py

### 8.1 Endpoints

| URL | Método | Função |
|-----|--------|--------|
| `/<id>/overlay-data/` | GET | JSON: elements, raw_image_url (presigned), logo_url (presigned), canvas, font_names |
| `/<id>/export-png/` | POST | Recebe elements editados → baixa imagens → data URIs → Playwright → PNG |
| `/<id>/save-elements/` | POST | Persiste elements em `designer_payload._layout_elements` |

### 8.2 Fluxo de export_png

```python
# 1. Lê elements editados do body JSON
elements = body.get('elements') or _get_elements(post)

# 2. Persiste posições editadas
_save_elements(post.pk, elements)

# 3. Gera presigned URLs novas (1h de validade, evita expiração)
raw_image_url = _get_raw_image_url(post)   # S3Service.generate_presigned_download_url
logo_url      = _get_logo_url(post)         # idem para o logo da KB

# 4. Baixa no servidor via urllib (server-side = sem CORS)
raw_image_data = _download_as_data_uri(raw_image_url)  # → "data:image/jpeg;base64,..."
logo_data      = _download_as_data_uri(logo_url)        # → "data:image/png;base64,..."

# 5. Monta HTML com data URIs embutidos
html = build_html(elements, raw_image_data, logo_data, canvas_w, canvas_h, font_paths)

# 6. Playwright captura screenshot
png_bytes = asyncio.run(_playwright_screenshot(html, canvas_w, canvas_h))
```

### 8.3 `_download_as_data_uri`

```python
def _download_as_data_uri(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        mime = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    # Retorna '' em caso de falha (não retorna a URL original — Playwright não carregaria)
```

### 8.4 `_save_elements`

```python
def _save_elements(post_pk, elements):
    post = Post.objects.get(pk=post_pk)
    dp = dict(post.designer_payload or {})
    dp['_layout_elements'] = elements
    Post.objects.filter(pk=post_pk).update(designer_payload=dp)
    # update() direto — evita conflitos de instância e race conditions
```

### 8.5 `_get_elements` — prioridade de leitura

```python
def _get_elements(post):
    # 1. designer_payload._layout_elements (edições salvas via save_elements)
    # 2. copy_payload._layout_elements (gerado pela Fase 1, antes de editar)
```

---

## 9. Frontend — Modal Arte Final (posts_list.html)

### 9.1 Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [×] Arte Final                                              │
├────────────────────────┬────────────────────────────────────┤
│  Preview da imagem     │  Painel de Propriedades            │
│  (overlay canvas)      │  ─────────────────────────────     │
│                        │  Elemento: [Título]                │
│  [Título aqui]         │  Texto: [_______________]          │
│  [Subtítulo]           │  Tamanho: [slider] 92px            │
│  [pill CTA]            │  Cor: [color picker]               │
│  [logo]                │  Fundo: [color picker]             │
│                        │  [B] Negrito                       │
│                        │  [←][↑][→] Alinhamento            │
│                        │  X: [0-100%]  Y: [0-100%]         │
│                        │                                    │
│                        │  [Baixar PNG]  [Fechar]            │
└────────────────────────┴────────────────────────────────────┘
```

### 9.2 Escala do canvas no modal

O overlay HTML tem dimensões menores que o canvas real (1080×1080 não cabe na tela). A escala é calculada após o modal abrir:

```javascript
// double requestAnimationFrame evita offsetWidth=0 no momento do open
requestAnimationFrame(() => requestAnimationFrame(() => {
    const rect = imgEl.getBoundingClientRect();
    scale = rect.width / canvasW;  // ex: 540/1080 = 0.5
    canvasH = rect.height;
    _renderAll();
}));
```

Todos os `font_size_px` multiplicam por `scale` no modal. No HTML de export (Playwright), o canvas é 1:1 — sem scale.

### 9.3 `_renderOne` — mapeamento de elementos

```javascript
function _renderOne(el, idx) {
    role = el.role.toLowerCase()

    if (role === 'grafismo') {
        // div com background color + border-radius calculado de raio_pct
        raio = (el.raio_pct/100 * canvasW * scale).toFixed(1) + 'px'
        // width_pct%, height_pct%, left:x_pct%, top:y_pct%

    } else if (role === 'logo') {
        // <img> com width_pct% + height_pct% + object-fit:contain
        // CRÍTICO: height_pct% obrigatório para que modal e PNG sejam idênticos

    } else if (['titulo','subtitulo','cta'].includes(role)) {
        // <div> com font-size = (font_size_pct/100 * canvasH * scale)px
        // fontFamily: titleFont (Google Fonts carregado dinamicamente)
    }

    // Elemento selecionado → outline dashed azul
    if (idx === selectedIdx) dom.style.outline = '2px dashed #0078d4'
}
```

### 9.4 Fontes no modal (Google Fonts)

```javascript
function _loadGoogleFont(family) {
    // Injeta <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=...">
    // Carregado uma vez por família ao abrir o modal
    // font_names.titulo vem do servidor (ex: 'Lora')
}
```

### 9.5 Persistência de posições

```javascript
// Ao fechar modal: captura dados ANTES de resetar variáveis
function closeModal() {
    const pid = currentPostId;
    const els = elements.slice();        // cópia do array
    modal.style.display = 'none';
    currentPostId = null; selectedIdx = null;
    _saveElements(pid, els);             // fire-and-forget
}

function _saveElements(postId, els) {
    fetch(`/posts/${postId}/save-elements/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN, 'Content-Type': 'application/json' },
        body: JSON.stringify({ elements: els }),
    }).catch(() => {});
}
```

`export_png` também persiste via `_save_elements(post.pk, elements)` no servidor antes de renderizar.

---

## 10. Modelo de Dados

### 10.1 Post.designer_payload (JSONField)

```json
{
  "_layout_elements": [
    {
      "role": "titulo",
      "content": "Você cuida de si para enfrentar mais?",
      "x_pct": 4.6, "y_pct": 14.8,
      "width_pct": 40.0, "height_pct": 35.0,
      "font_size_pct": 8.5,
      "color": "#5C1A1A",
      "weight": "bold", "align": "left",
      "padding_pct": 0
    },
    {
      "role": "subtitulo",
      "content": "O autocuidado estético é o alicerce da sua força interior",
      "x_pct": 4.6, "y_pct": 51.0,
      "width_pct": 38.0, "height_pct": 20.0,
      "font_size_pct": 3.7,
      "color": "#3D2B1F",
      "weight": "regular", "align": "left"
    },
    {
      "role": "grafismo", "forma": "faixa",
      "x_pct": 4.6, "y_pct": 79.0,
      "width_pct": 34.0, "height_pct": 8.0,
      "cor": "#5C1A1A", "raio_pct": 4.0, "opacidade": 100
    },
    {
      "role": "cta",
      "content": "Conheça nossa abordagem",
      "x_pct": 5.5, "y_pct": 79.6,
      "width_pct": 32.0, "height_pct": 6.0,
      "font_size_pct": 3.2,
      "color": "#FFFFFF",
      "weight": "bold", "align": "center"
    },
    {
      "role": "logo",
      "x_pct": 79.0, "y_pct": 4.0,
      "width_pct": 17.0, "height_pct": 10.0
    }
  ]
}
```

### 10.2 Campos do modelo Post relacionados

```python
raw_image_s3_key  = CharField(max_length=500)   # chave do PNG raw do Gemini no S3
raw_image_s3_url  = URLField()                   # URL pública (pode expirar)
designer_payload  = JSONField()                  # wireframe_plan + _layout_elements
copy_payload      = JSONField()                  # variants + _strategic_payload
local_pipeline_context = JSONField()             # logo_position, selected_logo_ids, etc.
```

---

## 11. Helpers do tasks.py

### `_parse_formato_px`
```python
def _parse_formato_px(formato_px: str):
    # '1080x1080' → (1080, 1080)
```

### `_dominant_bg_from_dossiers`
```python
def _dominant_bg_from_dossiers(kb_dossiers: list) -> str:
    # Extrai cor dominante (papel='dominante') da paleta_observada do dossier
    # Ignora dossiers de produto (aspects=['produto'])
    # Usado para calcular contraste automático do subtítulo
```

### `_prepare_pillow_overlay`
Resolve fontes da KB para os três roles (titulo, subtitulo, cta) via `font_resolver.resolve_font_for_kb`. Retorna dict com caminhos TTF locais.

### `_get_kb`
```python
def _get_kb(post):
    return KnowledgeBase.objects.filter(organization=post.organization).first()
```

### `_consume_designer_payload`
Adapta o `designer_payload.wireframe_plan` (formato antigo, px-based) para o `layout_document` que o `render_layout_document` entende. Usa `designer_payload_adapter.wireframe_plan_to_layout_document`.

---

## 12. URLs Registradas

```python
# app/apps/posts/urls.py
path('<int:post_id>/overlay-data/',   views_overlay.overlay_data,   name='overlay_data'),
path('<int:post_id>/export-png/',     views_overlay.export_png,     name='export_png'),
path('<int:post_id>/save-elements/',  views_overlay.save_elements,  name='save_elements'),
```

---

## 13. Bugs Resolvidos

| # | Problema | Causa | Solução |
|---|----------|-------|---------|
| 1 | Modal não abria | Projeto usa `display:none/flex`, não atributo `hidden` | `modal.style.display = 'flex'` |
| 2 | Texto invisível (scale=0) | `container.offsetWidth=0` no momento do open | Double `requestAnimationFrame` + `getBoundingClientRect()` |
| 3 | `image-preview-loader.js` SyntaxError | Script carregado 2× no template | Removida duplicata |
| 4 | CTA com 2 linhas | Lora mais largo que DejaVu; "Conheça nossa abordagem" quebrava | `max_lines=1` no CTA + regra ≤5 palavras no SKILL.md |
| 5 | Pillow ignorava font_size do layout_engine | `min_size = int(basis * 0.03) = 32px` overrideava tudo | `min_size = max(12, int(start_size * 0.6))` |
| 6 | Grafismo como "STYLE REFERENCE" | `referencia_layout` caía no branch `'refer'` genérico | Check explícito de `referencia_layout` antes de `'refer'` |
| 7 | Brief do grafismo fraco | Estava em `(user note: "...")` parentético | Bloco `MANDATORY BRIEF FOR Image N` dedicado |
| 8 | `[LAYOUT REFERENCE — replicate STRUCTURE only]` contradizia `[SCENE]` | Bloco redundante conflitante | Bloco removido |
| 9 | Lora 300 trocava de fonte | `_load_google_font` não tentava pesos vizinhos | Tenta todos os pesos da mesma família antes de desistir |
| 10 | Logo sem respiro | Margem calculada com variável `margin` errada | `safe_r`/`safe_b` do safe_zone em vez de margin local |
| 11 | Logo maior no modal que no PNG | `<img>` do logo no JS não tinha `height` definido | `height: el.height_pct + '%'` adicionado |
| 12 | PNG: imagem/logo não carregavam | Playwright headless não carrega URLs S3 externas (CORS) | `urllib` baixa server-side → data URI → sem rede no Playwright |
| 13 | Posições não salvas ao fechar | `closeModal` zerava `currentPostId` antes do fetch disparar | Captura `pid` e `els.slice()` antes de resetar |

---

## 14. Obstáculo Atual (2026-05-29)

### Problema
O `export_png` falha intermitentemente. Após reiniciar o serviço, o primeiro export funciona mas os subsequentes falham (imagem/logo não carregam no PNG).

### Hipótese mais provável
`_download_as_data_uri` retorna `''` (falha silenciosa no urllib) para o logo ou a imagem. Quando `logo_data = ''`, o logo simplesmente não aparece. Quando `raw_image_data = ''`, o export retorna `{'error': 'image_download_failed'}`.

### Investigação necessária
- Verificar logs `[overlay] download OK:` / `[overlay] falha ao baixar URL:` no servidor após um export que falha
- Confirmar se a presigned URL gerada em `_get_raw_image_url` está acessível via curl do servidor
- Verificar timeout de 30s (imagens 1080px podem ser pesadas)

### Solução implementada (atual)
```python
raw_image_data = _download_as_data_uri(raw_image_url)
logo_data      = _download_as_data_uri(logo_url)
# Presigned URLs novas geradas a cada request (expires_in=3600)
# Se falhar → '' → export retorna 500 com erro claro
```
