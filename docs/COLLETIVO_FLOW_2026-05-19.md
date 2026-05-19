# Fluxo exclusivo Colletivo — Documentação completa

**Branch:** `feature/colletivo-gerar-post`
**Data do documento:** 2026-05-19
**Status:** F1–F7 completas. F8 e F9 pendentes (e devem ser pausadas para revisão da fundação descrita em §13).

---

## 1. Sumário executivo

Foi construído um pipeline alternativo de geração de posts para a organização **Colletivo** (org_id=23, slug=`colletivo`) baseado em **Pillow Compose Engine** (renderização determinística) em vez de geração pura por IA. A motivação é respeitar com fidelidade as regras do brandbook do cliente Institute For Tomorrow (subcliente da Colletivo).

A arquitetura atual:

```
Briefing → Orchestrator (Claude Haiku, F8) → execution_plan
        → ComposeEngine (Pillow)
            ├── FontResolver  (TTFs reais via Google Fonts CSS API)
            ├── AssetResolver (Logo + Grafismos via presigned S3 URL)
            └── _fit_text_in_bbox + token color resolution
        → PNG → S3
```

F1–F4 (KB schema, brandguide upload, extração inicial via N8N) eram pré-existentes. F5–F7 e iterações foram implementadas neste branch (~$1.40 gasto em IA durante desenvolvimento).

---

## 2. Estado git e rollback

**Tags remotas como pontos seguros de rollback:**
| Tag | Commit | Cobre |
|-----|--------|-------|
| `pre-colletivo-2026-05-13` | 522b319 | Estado antes de qualquer trabalho Colletivo |
| `pre-colletivo-v2-spec` | 522b319 | Antes do spec v2 |
| `rollback-f7-done` | 1e5bce1 | Após F7 base (Asset Resolver) |
| `rollback-f7-complete` | 3ab25fc | Após F7.9 (reanalyze v3) — **último estado seguro** |

**Branch local sincronizada com `origin/feature/colletivo-gerar-post`** (working tree limpo, ahead 1 commit do prompt v4 iterado se não pushado ainda — checar `git status`).

---

## 3. Commits ordenados (cronologia da feature)

| # | Hash | Mensagem curta |
|---|------|----------------|
| 1 | `a6e305d` | feat(colletivo): infra base do Compose Engine — spec v2 + 26 templates da Colletivo |
| 2 | `250fddd` | feat(colletivo): F5 Compose Engine — renderizador determinístico via Pillow |
| 3 | `c3def9d` | feat(colletivo): F6 Font Resolver — TTFs reais via Google Fonts CSS API |
| 4 | `98a240a` | chore: gitignore app/fonts_cache (TTFs baixados em runtime) |
| 5 | `f6089f3` | fix(knowledge): aspect_ratio default='' previne NotNullViolation em upload manual |
| 6 | `1e5bce1` | feat(colletivo): F7 Asset Resolver — logos e grafismos reais da KB via S3 |
| 7 | `be3cd58` | feat(colletivo): F7+ natural placement (anchor+scale) e color block detection |
| 8 | `3ab25fc` | feat(colletivo): F7.9 reanalyze_template_v3 — Claude re-analisa template+assets |
| 9 | `(local)` | feat(colletivo): F7.10 prompt iterado — rosa pastel, 1 logo, sem overlap |

---

## 4. F1–F4 (pré-existentes relevantes)

### 4.1 Brandguide upload + análise (N8N)
- View `apps/knowledge/views_brandguide.py` — upload de PDF do brandbook.
- Análise feita via N8N + GPT-4o (não Claude). Retorna JSON estruturado com cores, tipografia, regras.
- Resultado salvo em `KnowledgeBase.brand_visual_spec` (JSONField).

### 4.2 KB schema (pré-existente, ampliado nesse branch)

Models relevantes em `apps/knowledge/models.py`:
- `KnowledgeBase` — root da organização
- `Logo` — logotipos da marca (uma logo principal + variantes)
- `BrandgraficModule` — grafismos PNG/SVG (letterforms, módulos decorativos)
- `CustomFont` — fontes TTF privadas
- `ReferenceImage` — imagens de referência visual
- `VisualTemplate` — arte pronta usada como base de composição
- `ColorPalette`, `Typography` — paletas e fontes
- `BrandguideUpload`, `BrandguidePage` — uploads PDF
- `Competitor`, `InternalSegment`, `SocialNetwork`, `SocialNetworkTemplate`

### 4.3 Campos novos adicionados nesse branch
- `KnowledgeBase.brand_visual_spec_v1_backup` (JSONField, null=True) — backup automático antes de overwrite v2
- `VisualTemplate.template_spec` (JSONField, default=dict) — spec estrutural com regions/bbox/tokens
- `VisualTemplate.aspect_ratio` (CharField, max_length=50, blank=True, default='') — ex: 1:1, 4:5, 16:9, produto_fisico_cilindrico
- `Post.visual_template` (FK → VisualTemplate, null=True)
- `Post.execution_plan` (JSONField, null=True) — plano gerado pelo orchestrator (F8)
- `AIUsageLog` em `apps/core/models.py` — model novo para rastreio de custos

### 4.4 Migrations criadas
- `knowledge.0024_knowledgebase_brand_visual_spec_v1_backup_and_more.py` (gitignore conflito com `*_backup_*` resolvido com -f)
- `knowledge.0025_alter_visualtemplate_aspect_ratio.py` (max_length 20 → 50)
- `knowledge.0026_alter_visualtemplate_aspect_ratio_default.py` (default='')
- `posts.0015_post_execution_plan_post_visual_template.py`
- `core.0010_aiusagelog.py`
- `campaigns.0004` e `content.0006` (side effects de FK)

---

## 5. F5 — Compose Engine

**Arquivo:** `app/apps/posts/compose_engine.py`

### Responsabilidade
Renderizar um `VisualTemplate.template_spec` + content data + brand spec → PNG via Pillow. Sem IA para layout.

### Constantes principais
```python
ASPECT_DIMENSIONS = {
    '1:1':  (1080, 1080),
    '4:5':  (1080, 1350),
    '9:16': (1080, 1920),
    '16:9': (1920, 1080),
}
SYSTEM_FONTS = {  # fallback Ubuntu (DejaVu)
    'regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'bold':    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'oblique': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
}
TEXT_TYPES = {'title', 'subtitle', 'body_text', 'secondary_text', 'tag'}
```

### Fluxo de render
1. `render()`: resolve dimensões pelo `format_aspect`, cria canvas RGB, ordena regions por z-order (graphic=0, image=1, logo=2, text=3 = back→front), itera renderizando cada region.
2. `_render_region`: dispatcher por `tipo`. Aceita 2 modos de posicionamento:
   - `bbox_pct = {x, y, w, h}` (modo restritivo — força tamanho)
   - `placement = {anchor, scale_pct, scale_dim, offset_pct}` (modo natural — preserva aspect ratio do asset, apenas para logo/graphic)
3. `_render_text`: usa `_fit_text_in_bbox` para auto-redimensionar fonte até caber.
4. `_render_image/logo/graphic_placeholder`: tenta asset real via `AssetResolver`; fallback é wireframe.

### Token color resolution
`_resolve_color(value)` aceita:
- HEX direto: `#FF0047`
- Token: `institucional.preto` → consulta `brand.cores`
- Multi-alternativa: `'#000000 (em fundo branco) | #FFFFFF (em fundo preto)'` → pega primeira hex válida.

### Management command de teste
`apps/posts/management/commands/render_template.py`:
```bash
python manage.py render_template --template-id 30 --output /tmp/test.png
python manage.py render_template --org-slug colletivo --first 3
```

---

## 6. F6 — Font Resolver

**Arquivo:** `app/apps/posts/font_resolver.py`

### Estratégia em camadas (ordem de prioridade)
1. **CustomFont da KB** (upload privado do usuário, ex: Supreme oficial)
2. **Cache local** em `/app/fonts_cache/` (compartilhado entre orgs)
3. **Google Fonts CSS API** via download
4. **Substituto público** se a fonte é privada/paga (ex: Supreme → IBM Plex Sans)
5. **Fallback DejaVu** do sistema

### Achado crítico — User-Agent
Google Fonts CSS API retorna formato baseado em capabilities do browser detectado pelo UA:
- Modernos → **WOFF2** (Pillow não decodifica)
- Antigos → **TTF**

Solução:
```python
'User-Agent': 'Mozilla/5.0 (Linux; U; Android 2.3.5)'
```
Android 2.3.5 é antigo o suficiente para garantir TTF.

### Fontes mapeadas (20 famílias Google Fonts)
IBM Plex Sans, Inter, Lora, Epilogue, Roboto, Open Sans, Montserrat, Poppins, Raleway, Nunito, Work Sans, Rubik, PT Sans, Merriweather, Oswald, Playfair Display, Mulish, Karla, DM Sans, Lato.

### Fallback de fontes privadas
```python
PRIVATE_FONT_FALLBACK = {
    'supreme':         'ibm plex sans',  # brand book For Tomorrow:
                                          # "Na impossibilidade de usar Supreme, use IBM Plex Sans"
    'general sans':    'inter',
    'cabinet grotesk': 'inter',
    'satoshi':         'inter',
}
```

### API pública
```python
resolver = FontResolver(brand_visual_spec=brand, kb=kb)
path = resolver.resolve(font_token='primaria.supreme', weight='bold')
path = resolver.resolve_with_fallback(font_token=..., system_fallback=DejaVu_path)
```

---

## 7. F7 — Asset Resolver

**Arquivo:** `app/apps/posts/asset_resolver.py`

### Responsabilidade
Carregar Logo e BrandgraficModule reais do S3 (bucket privado) para uso no Compose Engine.

### Achado crítico — S3 privado
Bucket é privado: URL direta retorna `HTTP 403 Forbidden`. Necessário gerar presigned URL via `S3Service.generate_presigned_download_url(s3_key)`.

### Estratégia em camadas
1. **Cache local** em `/app/assets_cache/` (compartilhado entre renders)
2. **Presigned URL** via `S3Service`
3. **Fallback URL direta** (caso s3_key esteja ausente)
4. **Open + convert RGBA** via Pillow

### API pública
```python
resolver = AssetResolver(kb=kb)

logo_img = resolver.resolve_logo(variant='preferencial')  # PIL.Image RGBA
graf_img = resolver.resolve_graphic_module(module_number=1, orientation='vertical')
img      = resolver.resolve_image_from_content({'s3_url': '...'})  # ou string URL

# Helper de colagem
resolver.paste_fit(canvas, asset, x, y, w, h, mode='contain'|'cover'|'stretch')
```

### Mapa de variantes de logo
`LOGO_VARIANT_MAP` traduz `template_spec.logo_variant` → `Logo.logo_type`:
- `preferencial` → `principal`
- `horizontal` → `horizontal`
- `vertical` → `vertical`
- `icone` → `icone`
- `monocromatico|preto|branco` → `monocromatico`

### Modos de fit
- `contain`: preserva aspect ratio, centraliza, deixa espaço vazio
- `cover`: preserva aspect ratio, cobre tudo, pode cortar bordas
- `stretch`: estica para preencher bbox exata

---

## 8. F7+ — Natural placement e color block detection

### 8.1 Natural placement
**Problema:** logo 1000×211 forçado em bbox 25%×6% deformava (stretch ruim).

**Solução:** schema novo `region.placement` em vez de `bbox_pct`:
```json
{
  "tipo": "logo",
  "logo_variant": "preferencial",
  "placement": {
    "anchor": "bottom-left",       // 9 anchors: top/center/bottom × left/center/right
    "scale_pct": 18,                // % do canvas
    "scale_dim": "width",           // "width" | "height"
    "offset_pct": {"x": 5, "y": 5}  // afastamento da borda
  }
}
```

`_natural_bbox(placement, asset_w, asset_h)` calcula bbox final preservando aspect ratio nativo. Funciona para `tipo: 'logo'` e `tipo: 'graphic'`. Coexiste com `bbox_pct` (se region tem placement, ignora bbox).

### 8.2 Color block detection
**Problema:** muitas regions tipo `graphic` no spec não são grafismos PNG, são barras de destaque coloridas (`background_highlight_pink_*` com `graphic_module_number='nao_aplicavel'`). Forçar carregar PNG estragava o layout.

**Solução:** `_render_graphic_placeholder` agora detecta:
```python
is_color_block = (
    not module_num or
    str(module_num).strip().lower() in (
        '', 'nao_aplicavel', 'na', 'none', 'indeterminado'
    )
)
```
Se `is_color_block`: desenha retângulo sólido com `color_token`.
Senão: carrega BrandgraficModule real PNG.

---

## 9. F7.9 — reanalyze_template_v3

**Arquivo:** `app/apps/posts/management/commands/reanalyze_template_v3.py`

### Responsabilidade
Re-analisar VisualTemplates passando JUNTO ao Claude Sonnet 4.5:
- PNG do template original (`s3_url`)
- PNG do logo da KB
- PNG de cada BrandgraficModule
- `brand_visual_spec` (cores + tipografia)

Resultado: `template_spec_v3` com regions calibradas (bboxes/placements corretos, distinção color block vs PNG real).

### Modelo + custo
- Model: `claude-sonnet-4-5` (knowledge cutoff 2026-01)
- Pricing usado: $3/M input, $15/M output
- Custo medido: **~$0.04 por template** (9.4k input + 700–1500 output tokens)
- 26 templates da Colletivo = **~$1.10 one-time**

### Args
```bash
--ids 28,30,32        # IDs explícitos
--org-slug colletivo  # default
--first N             # primeiros N da KB (alternativo a --ids)
--save                # persiste; default é dry-run
--dump-prompt         # debug
```

### Logging
Cada chamada registrada em `AIUsageLog` com:
- `provider=ANTHROPIC`
- `model='claude-sonnet-4-5'`
- `purpose=OTHER`
- `raw_usage={template_id, template_name, context: 'reanalyze_template_v3'}`

### Backup
Spec v3 preserva o v2 em `spec['_v2_backup']` (sem precisar de campo extra no model). Também injeta `format_aspect` e `background_color` do v2 quando o Claude esquece de incluir.

---

## 10. F7.10 — Iteração do prompt

### Issues observadas no v3 (renders feios) e correções aplicadas no prompt
| # | Issue | Causa | Correção no prompt |
|---|-------|-------|-------------------|
| 1 | Cor magenta forte (`#E23D96`) onde deveria ser rosa pastel | Claude pegou o token certo (`iniciativas.rosa`), mas o brand spec não tem "rosa_claro". Não é erro do Claude | Regra explícita: se a cor do template é variação mais clara/escura que NÃO existe no brand, use **HEX direto** (ex: `#FFD6E5`) + campo `color_rationale` explicando |
| 2 | Bboxes textuais sobrepostos (title + date + body no mesmo lugar) | Prompt não impedia | Regra ANTI-SOBREPOSIÇÃO: textos NUNCA com bbox sobreposto entre si. Sobreposição com graphic color block continua permitida (fundo + texto) |
| 3 | Logo duplicado no template 32 | Prompt não limitava quantidade | Regra: EXATAMENTE 1 region tipo `logo` por template, a menos que o template visual mostre múltiplos logos visíveis |
| 4 | Texto empilhado palavra-por-palavra ("SXSW / 2025 / LISBOA" cada uma em linha) | bbox.w estreito demais, `_fit_text_in_bbox` quebra | Regra: bbox.w >= 18 para texto com mais de 8 caracteres |

### User content reformulado
Antes: dump JSON do `brand.cores` (lista de dicts com hex+rgb+cmyk+uso). Verboso e confuso.
Agora: tabela legível
```
== Tokens de cor disponíveis ==
  institucional.preto = #000000  (Preto)
  iniciativas.rosa    = #E23D96  (Rosa)
  iniciativas.amarelo = #FFC324  (Amarelo)
  ...
```

### Resultado validado em templates 28/30/32
Renders v4 mostram melhora estética drástica:
- Layouts limpos, sem sobreposições textuais
- Rosa pastel `#FFD6E5` (não mais magenta)
- 1 logo cada
- Textos legíveis em linhas naturais

Custo da iteração: $0.127 (3 templates × ~$0.042)

---

## 11. Bugs encontrados e corrigidos durante o desenvolvimento

| Bug | Sintoma | Causa raiz | Fix |
|-----|---------|------------|-----|
| GitHub token ausente | git push falha | sem PAT configurado | `gh auth login` |
| Acentos quebram S3 upload | botocore reject "Ativó" | unicode NFD form | `_ascii_safe_metadata` via NFKD em `s3_service.py` (commit `522b319`) |
| Logo upload 5000×5000 limit | rejeita logos grandes | constante baixa | aumentado para 10000×10000 (commit `52d9b15`) |
| JSON parse N8N | GPT-4o produz `])` | falha de formato no Code node | switch Assistant para `response_format: json_object` |
| Texto sobreposto no event_card_portrait_tall | render v0 quebrado | sem auto-fit | implementado `_fit_text_in_bbox` |
| Falha download de fontes | Google Fonts retorna WOFF2 | User-Agent moderno | UA Android 2.3.5 force TTF |
| `aspect_ratio` max_length=20 too short | "produto_fisico_cilindrico" (25 chars) falha | constante baixa | migration 0025 expand para 50 |
| Gitignore matching `*_backup_*` | migration 0024 ignorada | padrão captura nome de campo | `git add -f` |
| `NotNullViolation aspect_ratio` em upload manual | upload em `/knowledge/perfil/` quebra | campo `blank=True` mas sem `default=''` em Postgres NOT NULL | migration 0026 + restart gunicorn |
| `render_template --first 3` sem KB | AssetResolver sem KB → fallback sempre | command não passava `kb=template.knowledge_base` ao engine | corrigido |
| S3 403 Forbidden | logos/grafismos não baixam | bucket privado, URL direta não autoriza | usar `S3Service.generate_presigned_download_url(s3_key)` |
| `/app/assets_cache` permission denied | mkdir negado em container | UID django sem permissão | criar com `-u root` + `chown django:django` |
| Render v3 com aspect 1:1 errado | Claude não incluiu `format_aspect` no JSON | prompt não forçava | `_save_spec` injeta `format_aspect` de `template.aspect_ratio` se ausente |
| `cores` items como strings (não dicts) | crash em `tokens_text` | grupo `regras_de_combinacao` etc. são strings | filtrar com `isinstance(item, dict)` |

---

## 12. Custos consumidos (resumo)

| Item | Custo |
|------|-------|
| Análise brandguide inicial (N8N + GPT-4o) | ~$0.88 (pré-existente) |
| reanalyze_template_v3 em 3 templates teste (F7.9) | ~$0.13 |
| Iteração de prompt v4 em 3 templates (F7.10) | ~$0.13 |
| Brandguide v2 spec generation (Claude Sonnet 4.5 inicial) | ~$0.88 (commit `a6e305d`) |
| **Total gasto neste branch** | **~$2.02** |

Próximos gastos previstos:
- Escalar reanalyze_v3 para os 26 templates da Colletivo: ~$1.10 (aguarda confirmação)
- F8 orchestrator por post (Haiku 4.5): ~$0.001-0.01 por post
- F8 geração de foto via Gemini 3 Pro Image (opcional): ~$0.90 por foto

---

## 13. ⚠️ Análise da fundação — revisão necessária ANTES de F8/F9

Durante a iteração de F7 ficou claro que o problema raiz da qualidade visual NÃO é o engine, e sim a **fundação da KB** não ser rica o suficiente. Sem isso, qualquer modal de geração vai sofrer. Foram identificados 4 pontos de revisão estrutural.

### 13.1 Refluxo do upload+análise da KB (Frente 1)

**Estado atual:** upload PDF → análise automática extrai TUDO (incluindo imagens com perda de qualidade) → spec direto.

**Estado desejado:** 2 etapas separadas.

**Etapa 1 — Coletar (sem análise):**
Form com slots de upload paralelos. Análise NÃO é disparada automaticamente.
- Brandguide PDF
- Logos (model `Logo` existe)
- Grafismos (model `BrandgraficModule` existe)
- Fontes TTF (model `CustomFont` existe)
- Referências visuais (model `ReferenceImage` existe)
- Templates visuais (model `VisualTemplate` existe)
- **Grids** ← model novo (não existe)

**Etapa 2 — Botão "Analisar":**
IA lê o PDF + olha cada asset uploaded (com nome+tipo) + gera spec com **referências cruzadas** (ex: "regra X sobre uso do logo se aplica ao Logo id=26") + detecta candidate PostTypes. Análise NÃO extrai imagens do PDF — apenas o entendimento de regras de uso.

**Arquivos a tocar:**
- `apps/knowledge/views_brandguide.py` (separar upload de análise)
- pipeline de análise (provavelmente migrar de N8N para Claude direto, ou refatorar N8N)
- `apps/knowledge/management/commands/populate_*` (review)
- Frontend `/knowledge/perfil/` (UI com slots paralelos + botão "Analisar")

### 13.2 Model `Grid` (Frente 2)

Não existe. Schema sugerido:
```python
class BrandGrid(models.Model):
    knowledge_base = FK(KnowledgeBase)
    name           = CharField(max_length=200)
    s3_key         = CharField(max_length=500)
    s3_url         = URLField(max_length=1000)
    file_format    = CharField(max_length=10, choices=[('svg','SVG'),('png','PNG'),('pdf','PDF')])
    aspect_ratio   = CharField(max_length=50, blank=True, default='')
    description    = TextField(blank=True)
    usage_hint     = CharField(max_length=255, blank=True)
    approved_by_user = BooleanField(default=False)
    is_active      = BooleanField(default=True)
    uploaded_by    = FK(User, null=True)
    created_at     = DateTimeField(auto_now_add=True)
```

**Decisão pendente:** nome do model — `BrandGrid`, `LayoutGrid` ou só `Grid`?

### 13.3 Model `PostType` (Frente 3)

Não existe. Schema sugerido:
```python
class PostType(models.Model):
    knowledge_base = FK(KnowledgeBase)
    name           = CharField(max_length=100)   # "Evento", "Speaker", "Sinalização"
    description    = TextField(blank=True)
    required_content_fields = JSONField(default=list)
        # ex: ["title", "date", "speaker_name", "speaker_photo"]
    suggested_visual_templates = ManyToManyField(VisualTemplate)
        # OU FK(VisualTemplate) se 1:1
    example_briefing       = TextField(blank=True)
    default_aspect_ratio   = CharField(max_length=50, blank=True)
    extracted_from_brandguide = BooleanField(default=False)
    approved_by_user       = BooleanField(default=False)
    created_at             = DateTimeField(auto_now_add=True)
```

**Fluxo:**
- Durante "Analisar", IA detecta tipos candidatos (event, speaker, signage, product...).
- User valida/edita na UI.
- Resultado alimenta o select no modal de gerar post.

**Decisão pendente:** `PostType ↔ VisualTemplate` é m2m (1 type pode ter vários templates de aspect ratios diferentes) ou FK 1:1?

### 13.4 Refatorar prompt de análise (Frente 4)

**Estado atual:** análise PDF-only via N8N. `template_spec_v3` é processo SEPARADO (`reanalyze_template_v3` rodado manualmente depois).

**Estado desejado:** análise multimodal integrada que recebe:
- PDF (texto + páginas para visão)
- Lista de assets cadastrados (com nome, tipo, s3_url para baixar)
- Brand spec parcial (cores extraídas de upload manual)

E produz:
- `brand_visual_spec_v3` com regras cruzadas (cada regra aponta para asset_id)
- Lista candidate de `PostType`
- `template_spec_v3` cruzando templates uploaded + assets (substitui `reanalyze_template_v3` separado — vira parte do pipeline integrado)

### 13.5 Modal de gerar post — escopo expandido (Frente 5, DEPOIS)

Modal hoje (proposta original F9): briefing textarea + escolha de template.
Modal revisado: cada campo abaixo é populado da KB cadastrada.

- Select **PostType** (carrega `required_content_fields` dinamicamente)
- Select **logo variant** (de `kb.logos`)
- Select **grid** (de `kb.brand_grids`)
- Multi-select **grafismos** (de `kb.grafic_modules`)
- Campos de imagem **dinâmicos por PostType** (cada um = upload + textarea "descreva o uso desta imagem")
- Briefing textarea opcional (para nuances que o orchestrator interpreta)
- Backend orchestrator usa tudo + confronta com KB rules antes de gerar `execution_plan`

### 13.6 Decisões abertas que travam a implementação

1. **Nome do model Grid:** `BrandGrid`, `LayoutGrid` ou `Grid`?
2. **PostType ↔ VisualTemplate:** m2m ou FK 1:1?
3. **KBs já existentes (Colletivo):** re-rodar "Analisar" no novo fluxo gera custo de IA (~$1). Vale gastar ou marcamos como "legacy" e mantemos o spec atual?
4. **Botão Analisar:** aparece sempre que houver PDF? Bloqueia se faltar assets críticos (sem logos = não pode analisar)?
5. **Re-upload de brandguide existente:** já tem fluxo com modal de wipe — mantém ou refatora junto?

### 13.7 Ordem de implementação sugerida

1. **Frente 2 (Grid) + Frente 3 (PostType)** em paralelo — models novos, baratos, baixo risco.
2. **Frente 1 (refluxo upload) + Frente 4 (prompt análise)** juntos — mexem em pipeline existente, alto risco. Implementar em branch separada `feature/kb-foundation-v2`.
3. **Frente 5 (modal expandido)** quando base estiver sólida.
4. **F8 (orchestrator) + F9 (UI nova)** ficam pendentes até Frente 5 estar pronta.

### 13.8 Foto do speaker/lugar — solução flexível

Em vez de um campo rígido "speaker_photo_url", permitir uploads genéricos onde cada um carrega:
- Arquivo (upload)
- Textarea de **descrição de uso** (ex: "foto do palestrante principal", "foto do local do evento", "logo do parceiro Y")

O orchestrator interpreta a descrição + confronta com a KB para decidir onde aplicar cada foto. Mais flexível que campos fixos.

---

## 14. Arquivos críticos (referência rápida)

| Arquivo | Linhas | Responsabilidade |
|---------|--------|------------------|
| `app/apps/posts/compose_engine.py` | ~600 | Render Pillow determinístico |
| `app/apps/posts/font_resolver.py` | ~340 | TTFs reais via Google Fonts |
| `app/apps/posts/asset_resolver.py` | ~230 | Logos+grafismos via S3 |
| `app/apps/posts/management/commands/render_template.py` | ~110 | CLI de teste de render |
| `app/apps/posts/management/commands/reanalyze_template_v3.py` | ~490 | Re-análise IA do template |
| `app/apps/knowledge/management/commands/populate_colletivo_v2.py` | ~250 | Seed inicial 26 templates da Colletivo |
| `app/apps/knowledge/data/colletivo_spec_v2_seed.json` | ~120KB | JSON final consolidado v2 |
| `app/apps/knowledge/views_brandguide.py` | ~700 | Upload + análise do brandguide |
| `app/apps/knowledge/models.py` | ~1500 | Models da KB (todos os Logo/Grafismo/Template/etc.) |
| `app/apps/core/models.py` | ~1200 | AIUsageLog model |
| `app/apps/core/services/s3_service.py` | ~400 | S3 presigned URLs |

---

## 15. Próximas ações concretas

Aguarda decisão do usuário sobre **§13.6 (decisões abertas)** antes de tocar em código novo. Caminhos possíveis:

**A.** Pausar F8/F9 e implementar Frente 2+3 (models Grid e PostType). Baixo risco, valor imediato (UI de cadastro).

**B.** Escalar `reanalyze_template_v3` aos 26 templates da Colletivo (~$1.10) com o prompt atual v4 para ter UMA versão de produção do spec antes de qualquer mudança estrutural. Mantém F8/F9 viáveis na arquitetura atual enquanto se planeja a refundação.

**C.** Ir direto para a refundação completa (Frentes 1+4 em branch nova). Maior valor a longo prazo, maior tempo até ter algo demonstrável.

A recomendação interna é **A**: começar pelos models novos (Grid + PostType) que destravam a Frente 5 sem mexer no que já funciona.
