# TODXS — Arquétipos, Renderizador Determinístico e Seletor no Modal

> Documento **interno** (know-how). Cobre o pipeline EXCLUSIVO da org `todxs`
> (slug=`todxs`, id=35, KB id=34): geração determinística por arquétipo, o
> catálogo **data-driven**, o seletor no modal de gerar post e os pontos de
> paridade (geração == editor == download). Tudo vive na branch
> `chore/seed-todxs-onboarding` — **nunca no `main`**. `main` intocado em `6611e6c`.

---

## 0. Visão geral

A TODXS não usa o pipeline genérico de imagem. Ao gerar post, a org cai em
`gerar_post_todxs` (delegação por slug a partir de `gerar_post_simples`) e a arte
é montada por um **renderizador Pillow determinístico**, guiado por **arquétipos**
(modelos de layout A–F + variantes) com coordenadas medidas das peças da marca.

```
[Modal Gerar Post] ─POST /posts/gerar-simples/─► (slug=todxs) ─► gerar_post_todxs
   └─► Post(pipeline_used='todxs') ─► generate_post_todxs_task (Celery)
         1. skill_brain (Claude)  → Content Lock + escolhe/usa arquétipo + cor
         2. fundo                 → Gemini gera SÓ a foto (solid pula Gemini)
         3. render_todxs (Pillow) → compute_layout + draw_todxs (arte final)
   └─► status=image_ready
```

Texto **PRETO** obrigatório em A/B/C. Assets fixos: wordmark "TODXS Logotipo
Preto 7", símbolo "Grafismo X Preto 1".

---

## 1. Arquétipos (modelos de layout)

| Key | Nome | Formato | Fundo | Status |
|-----|------|---------|-------|--------|
| A | Capa tipográfica | feed | solid (sem Gemini) | ✅ validado |
| B | Foto + faixa | feed+story | photo | ✅ validado |
| B_DUO | Foto duotone + faixa | feed | photo (Gemini duotone) | ✅ validado |
| C | Notícia (P&B) | feed | photo (grayscale) | ✅ validado |
| C_DISPLAY | Display (manchete gigante) | feed | solid_photo | ✅ validado |
| D | Retrato + wordmark gigante | feed | photo | ⏳ pendente |
| E | Story — lista de blocos | story | solid | ⏳ revalidar |
| F | Story duotone + marca d'água | story | photo (duotone) | ⏳ pendente |

Cada arquétipo = uma **ficha (spec)**: zonas com `x/y/w/h/fs` (% do canvas),
fonte (display/medium/regular/caps_small), `caps`, `align`, `color`, `max_linhas`,
`leading` e flags (`center_v`, `flow_after`, `is_blocks`, `fixed_fs`). Detalhe
relevante: `fixed_fs` TRAVA o tamanho da fonte (não encolhe por texto) — usado no
kicker pra ele ter a mesma altura do logo em todo post.

---

## 2. Catálogo DATA-DRIVEN (a spec saiu do código pro banco)

**Antes:** a spec vivia em `services/todxs/wireframes.py` (dict `WIREFRAMES`).
**Agora:** vive no banco (`PostArchetype.spec`, JSON) por organização. O código é
fallback. Isso permite correção via admin sem deploy e prepara a Fase 2 (agente).

- **Modelo** `apps/posts/models.py:PostArchetype` — `organization`, `key`, `name`,
  `format` (feed/story/both), **`spec` (JSONField)**, `thumbnail` (→ReferenceImage),
  `order`, `is_active`. Migration `posts/0023`.
- **Leitura** `wireframes.WF()` devolve o dict `{key: spec}` ativo (um `contextvar`)
  ou, por padrão, o `WIREFRAMES` do código. `set_wireframes()` seta o contextvar.
- **Loader** `services/todxs/catalog.py:load_org_wireframes(org)` monta
  `{key: spec}` (banco SOBRE código). `apply_org_wireframes(org)` seta no contextvar
  — chamado no início de `generate_post_todxs_task`.
- **Quem lê WF():** `layout.compute_layout`, `pillow_render.build_background`/
  `render_todxs`, `skill_brain` (menu/force), helpers de `wireframes.py`.
- **Seed** `python manage.py seed_archetypes` popula a partir do código.
  `--resync-spec` reimporta (senão preserva edições do admin). `--org <slug>`.

> Correção pontual de layout = editar `PostArchetype.spec` no admin (reflete na
> próxima geração). Re-sincronizar do código = `seed_archetypes --resync-spec`.

---

## 3. Seletor de arquétipo no modal

Habilitado por org via flag **`Organization.archetype_selector_enabled`** (ligada
só na TODXS). Orgs sem a flag: modal idêntico ao de hoje (zero mudança).

- **Toggle** `Geração livre | Usar template` (acima da seção de logo).
  - **Geração livre** (default): a IA escolhe arquétipo + cor (fluxo atual).
  - **Usar template**: esconde logo/posição/refs; mostra **slider de thumbnails**
    (filtrado por feed/story) + **círculos da paleta** (cor inspiração).
- **Dados** `views_api.get_org_assets` (`/posts/api/org-assets/`) devolve, quando
  a flag está ligada: `archetype_selector_enabled`, `archetypes` (key, name, format,
  thumbnail presigned, order) e `palette` (nome+hex).
- **Front** `static/js/posts.js`: `setupArchetypeMode`/`renderArchetypeSlider`/
  `renderArchetypePalette`/`setGenMode`; HTML do toggle/painel em `posts_list.html`.
  Envia `archetype` + `color_hex` + `color_name`.
- **Back** `views_gerar_todxs` grava em `local_pipeline_context['todxs']`:
  `force_archetype`, `force_color`, `force_color_name`. A task usa `force_archetype`
  (skill_brain trava o arquétipo) e `force_color` (sobrepõe a cor da IA).
- **Thumbnails** mapeadas às ReferenceImage 60-68 da KB (8/8).

**Como habilitar para uma nova org:** (1) ligar `archetype_selector_enabled`;
(2) cadastrar as `PostArchetype` da org (hoje só TODXS tem — outra marca precisa
das specs dela; ver Fase 2). Os arquétipos atuais são da marca TODXS (fontes,
assets, cores dela) e não servem para outra marca.

---

## 4. Renderizador e PARIDADE (geração == editor == download)

Três caminhos desenham a MESMA arte e DEVEM bater:
1. **Geração** — `pillow_render.render_todxs` → `build_background` (fundo) +
   `compute_layout` (elementos explícitos) + `draw_todxs` (desenha).
2. **Editor/Save** — `views_overlay._todxs_rerender_published` → `draw_todxs` com
   os elementos salvos em `designer_payload._layout_elements`.
3. **Download/Export** — `views_overlay.export_png` → `draw_todxs`.
4. **Regenerar fundo** — `tasks.regenerate_background_task` (Gemini só na foto) →
   `_refresh_editable_post_image` → (todxs) `_todxs_rerender_published`.

**Regra de ouro do canvas:** as zonas usam coords em % de `W×H` (feed 1080×1350,
story 1080×1920). `draw_todxs` **normaliza o fundo para W×H (cover)** antes de
desenhar — porque o output do Gemini no regen vem em tamanho nativo (ex.: 928×1152)
e desalinharia faixa/título. No-op na geração original (já vem W×H).

> **Bug corrigido (commit 333244e):** o "alterar imagem de fundo" quebrava o
> download — (a) o fundo do Gemini não era normalizado pro canvas; (b) o refresh
> usava o renderizador HTML/Playwright genérico, não o `draw_todxs`. Os dois furos
> eram exclusivos do caminho de regen. Corrigidos.

---

## 5. O que está FEITO

- ✅ Arquétipos A, B (feed+story), B_DUO, C, C_DISPLAY validados (medidos por pixel).
- ✅ Catálogo data-driven (PostArchetype + WF + catalog + seed). Round-trip
  banco==código verificado.
- ✅ Flag por org + admin (Organization + PostArchetype, spec editável).
- ✅ Endpoint do modal (flag + arquétipos + thumbnails + paleta).
- ✅ Modal: toggle + slider + círculos de cor; `force_archetype`/`force_color`.
- ✅ 8 thumbnails mapeadas.
- ✅ Paridade geração/editor/regen/download (normalização de canvas + renderizador
  todxs no regen).
- ✅ E2E: post 205 (A + cor forçada) e 206 (B_DUO + regen) — download == modal.
- ✅ Commit `333244e` na branch.

## 6. O que FALTA

- ⏳ **Arquétipos D, E, F** — validar com as specs medidas (usuário manda JSON+SVG+ref,
  um de cada vez). E tem versão inicial a revalidar; D e F pendentes.
- ⏳ **Fase 2 — criação self-service de arquétipos:** admin sobe wireframe (SVG/PDF)
  + imagem de referência; um **agente (Claude vision)** extrai a **spec JSON**
  (zonas, coords, fontes, tratamento), salva no `PostArchetype`, admin revisa e
  corrige. A base data-driven já está pronta (o agente só precisa escrever a spec).
- ⏳ **Thumbnail do B** — hoje usa a feed (ref 62); a story (ref 61, rosa) sobrou.
- ⏳ **Fonte Vinila real** — hoje `caps_small` usa CallingCode como stand-in
  (CustomFont id 91). Subir a Vinila e trocar.
- ⏳ **Reverter `is_staff`** do usuário `teste.todxs` (ligado para testes).
- ⏳ Verificar o modal no browser (toggle/slider visual) — backend/render já OK.

---

## 7. Arquivos-chave

| Camada | Arquivo |
|--------|---------|
| Specs (código/fallback) | `apps/posts/services/todxs/wireframes.py` |
| Loader data-driven | `apps/posts/services/todxs/catalog.py` |
| Layout determinístico | `apps/posts/services/todxs/layout.py` |
| Render Pillow | `apps/posts/services/todxs/pillow_render.py` |
| Skill brain (Claude) | `apps/posts/services/todxs/skill_brain.py` |
| Assets (wordmark/símbolo/cor) | `apps/posts/services/todxs/assets.py` |
| Task de geração | `apps/posts/tasks_todxs.py` |
| Entrada (cria Post) | `apps/posts/views_gerar_todxs.py` |
| Editor/export/regen-render | `apps/posts/views_overlay.py`, `apps/posts/tasks.py` |
| Modelo do catálogo | `apps/posts/models.py:PostArchetype` |
| Endpoint do modal | `apps/posts/views_api.py:get_org_assets` |
| Modal (HTML/JS) | `apps/posts/templates/posts/posts_list.html`, `static/js/posts.js` |
| Seed | `apps/posts/management/commands/seed_archetypes.py` |

**Rollback:** `git reset --hard 2caa6f0` (antes da Fase 1) ou voltar ao `main`
(`6611e6c`, zero TODXS). Migrations no deploy: aplicar `core/0012` e `posts/0023`
+ rodar `seed_archetypes` (e ligar a flag da org).
