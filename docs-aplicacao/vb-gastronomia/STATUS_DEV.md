# VB Gastronomia — Status de Desenvolvimento

Pipeline de geração de arte **exclusivo da org `vb-gastronomia`** (id 38, KB 37),
determinístico por arquétipo (Pillow), espelhando o fluxo da TODXS. Vive na branch
`chore/seed-todxs-onboarding` (NÃO no `main`).

> Princípio: **espelhar TODXS agora** (specs por código), **refatorar no fim** para
> ficar data-driven e escalar para qualquer empresa sem código por-empresa.
> Toda mudança é **aditiva** (ramos `vb`) — nunca quebra TODXS nem o editor genérico.

## Arquitetura

```
Clique "Gerar Post" → gerar_post_simples → [slug==vb-gastronomia] → gerar_post_vb
  → Post(pipeline_used='vb') + local_pipeline_context.vb{force_archetype, force_color}
  → generate_post_vb_task.delay
       1. skill_brain (Claude sonnet) → texto das zonas (+ receita de ilustração se aplicável)
       2. [se precisa] FOTO via Gemini single-shot
       3. render_vb (Pillow determinístico) → raw (só fundo) + final + _layout_elements
       → status=image_ready
```

### Arquivos (todos na branch)
- `app/apps/posts/services/vb/specs.py` — fichas dos arquétipos (SPECS) + PALETTE.
- `app/apps/posts/services/vb/render.py` — motor Pillow (`render_vb`), grid de carimbos,
  guarda de contraste, texto vertical editável, bleed→within-bounds.
- `app/apps/posts/services/vb/skill_brain.py` — 1 chamada Claude (texto por arquétipo).
- `app/apps/posts/services/vb/illustration/` — skill de ilustração (illustrate.py + assets/recipes).
- `app/apps/posts/services/vb/fonts/` — Barlow Condensed (stand-in da Acumin Condensed).
- `app/apps/posts/tasks_vb.py` — `generate_post_vb_task` (orquestra brain + foto + render).
- `app/apps/posts/views_gerar_vb.py` — cria Post vb e dispara a task.
- `app/apps/core/management/commands/seed_vb_gastronomia.py` — seed da org/KB.
- **Tocados (aditivo):** `views_gerar_simples.py` (delegação por slug), `views_overlay.py`
  (ramos vb: overlay_data, fontes, save/export, debug), `posts_list.html` (rerender vb,
  texto rotacionado no editor), `tasks.py` (import da task p/ autodiscovery).

### Convenções-chave
- **raw = só o fundo**; todo o resto vira `_layout_elements` editável (espelha TODXS).
- **Editor:** texto = role titulo/subtitulo/cta; imagem (foto/logo/grafismo/grid) = role 'image'.
  Fonte por elemento (Barlow via `/posts/<id>/todxs-font/<key>/`).
- **Determinismo:** grid de carimbos tem seed do título (mesmo post → mesmo padrão).
- **Catálogo:** `PostArchetype` (org vb) alimenta o seletor do modal; key = '01'..'06',
  format feed/story. (A `spec` do PostArchetype não é usada pelo render vb — ele lê `specs.py`.)

## Arquétipos

| # | Formato | Nome | Status |
|---|---|---|---|
| 01 | feed | Hook sobre cor sólida (ilustração) | ✅ validado |
| 02 | feed | Foto protagonista + assinatura (cluster bleed + símbolo) | ✅ validado |
| 03 | feed | Informativo (foto emoldurada + título + **apoio vertical editável** + garfo bleed) | ✅ validado |
| 04 | story | Institucional sobre cor + **grid de carimbos** (bleed) | ✅ validado |
| 05 | story | (Foto) | ⬜ pendente |
| 06 | story | (Manifesto) | ⬜ pendente |

### Detalhes implementados (além do layout base)
- **03 — apoio vertical EDITÁVEL:** texto rotacionado (rot 90) emitido como elemento de
  TEXTO (não imagem) com `rotation`; editor renderiza girado e edita o conteúdo; Pillow
  re-desenha rotacionado no save/export. Posicionado acima do garfo, centralizado nele.
- **Guarda de contraste:** se a cor de fundo escolhida pelo usuário colide com a cor do
  texto, o texto vira uma cor da paleta que contrasta (creme em fundo escuro). Genérico.
- **04 — grid de carimbos (rodapé):** 5×5, 3 cores base + 1 destaque (só no miolo 3×3),
  carimbos oficiais recoloridos, alongados deitam na horizontal, preservando proporção.
- **Bleed → within-bounds:** elementos que sangram (grid 04, clusters 02/03) são
  **recortados na própria imagem** e emitidos dentro dos limites do canvas — assim o
  **editor avançado bate com o publicado** (antes descompassava por causa do
  `objectFit:contain` sobre caixa maior que o canvas). Helper `_emit_within_bounds`.

## O que falta

1. **Arquétipo 05** (story, foto) — validar 1 a 1.
2. **Arquétipo 06** (story, manifesto) — validar 1 a 1.
3. **REFATORAÇÃO FINAL — motor data-driven:** mover as specs por-código para a `spec`
   (JSON) do `PostArchetype` e fazer o render ler dali, para suportar qualquer empresa
   nova sem código por-empresa. (Fase 2: um agente extrai a spec a partir de wireframe+imagem.)
4. **Modal — upload de imagem:** opção de subir imagem em vez de (a) foto Gemini,
   (b) gerador de ilustração; aplica cor/efeito quando necessário, senão só posiciona/fit.
5. **Thumbnails do catálogo** para 04–06 (PostArchetype.thumbnail).

## Regras operacionais
- Runtime Docker: gunicorn **sem auto-reload** → mudança de código exige
  `docker compose restart iamkt_web iamkt_celery`.
- Nunca acionar fluxos que enviem email ao testar.
- Deploy: rollback primeiro, incremental, nunca `makemigrations` no deploy.
