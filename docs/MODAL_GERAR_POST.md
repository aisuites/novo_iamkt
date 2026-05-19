# Modal "Gerar Post" — mapeamento e evolução

**Status:** documento vivo. Atualizar a cada mudança no fluxo.
**Branch ativa:** `feature/novo-modal-gerar-post`
**Última atualização:** 2026-05-19 (mapeamento inicial)

---

## 1. Visão geral

Modal único de geração de posts que atende **todas as organizações** do iamkt. Disparado a partir da página `/posts/` (lista de posts). Todo o processamento de IA é **delegado ao N8N** via webhook async; o Django apenas cria o `Post` em status `generating` e dispara o trigger.

> Este modal é separado do fluxo exclusivo da Colletivo (que vive em `feature/colletivo-gerar-post` e usa Compose Engine determinístico).

---

## 2. Mapeamento técnico — arquivos chave

| Camada | Arquivo | Localização relevante |
|--------|---------|----------------------|
| Template HTML | [app/apps/posts/templates/posts/posts_list.html](../app/apps/posts/templates/posts/posts_list.html) | linhas 275–385 (bloco `#modalGerarPost`) |
| JavaScript | [app/static/js/posts.js](../app/static/js/posts.js) | funções principais (§7) |
| View backend | [app/apps/posts/views_gerar.py](../app/apps/posts/views_gerar.py) | `gerar_post()` linhas 18–318 |
| Callback N8N | [app/apps/posts/views_gerar.py](../app/apps/posts/views_gerar.py) | função `webhook_callback` (mesma app) |
| URL pattern | [app/apps/posts/urls.py](../app/apps/posts/urls.py) | linha 13: `path('gerar/', views_gerar.gerar_post, name='gerar')` |
| CSS do modal | [app/static/css/posts.css](../app/static/css/posts.css) | linhas 1499–1523 (`.modal-overlay`) |
| Disparador | [app/apps/posts/templates/posts/posts_list.html](../app/apps/posts/templates/posts/posts_list.html) | header da página, botão "🎨 Gerar Post" |

---

## 3. Campos do modal (estado atual)

Ordem visual no form:

| # | Campo | Tipo | Obrigatório | Notas |
|---|-------|------|-------------|-------|
| 1 | Rede Social | select | sim | Instagram, Facebook, LinkedIn, WhatsApp |
| 2 | Formato | select dinâmico | sim | Carregado via `GET /posts/api/formatos/?rede_social=X`. Mostra dimensões (ex: 1080x1350) |
| 3 | CTA | radio Sim/Não | não | Padrão: Sim |
| 4 | Carrossel | toggle button | não | Quando ativo libera campo Qtd imagens |
| 5 | Qtd imagens | number (2-5) | só se carrossel | Padrão 3 quando ativo |
| 6 | Tema | textarea | sim | Max 3000 chars. Placeholder "Restrições, exemplos, referências..." |
| 7 | Imagens de Referência | file input | não | Até 5 arquivos JPG/PNG; preview inline |

**Botões finais:** "Cancelar" (btn-outline-secondary) + "Enviar ao agente" (btn-primary, `id="btnEnviarPost"`).

**Não há preview visual** do post no modal — somente preview das imagens uploaded.

---

## 4. Fluxo de dados (estado atual)

```
[ User clica em "🎨 Gerar Post" no header de /posts/ ]
         ↓
[ Modal abre via onclick inline (display='block') ]
         ↓
[ Rede selecionada → JS loadPostFormats() → GET /posts/api/formatos/ ]
         ↓
[ User preenche tema, escolhe CTA, carrossel, anexa imagens ]
         ↓
[ User clica "Enviar ao agente" ]
         ↓
[ JS uploadReferenceImages() — só se houver imagens
   ├─ POST /knowledge/reference/upload-url/ (presigned URL)
   ├─ PUT direto pro S3
   └─ retorna [{s3_key, url, name}]
         ↓
[ JS requestPostFromAgent() — POST /posts/gerar/ {rede, post_format_id, tema, cta_requested, is_carousel, image_count, reference_images} ]
         ↓
[ Backend gerar_post()
   ├─ Valida rede + tema + formato
   ├─ Cria Post(status='generating')
   ├─ Cria PostReferenceImage para cada imagem
   ├─ Busca KB.n8n_compilation (ou monta resumo manual)
   └─ POST async pro N8N webhook (X-Webhook-Secret)
         ↓
[ JS fecha modal + window.location.reload() em 2s ]

   ... tempo depois ...

[ N8N termina processamento e chama POST /posts/webhook/callback/
   ├─ Valida token + IP + rate limit
   └─ Atualiza Post (caption, hashtags, post_images, status='ready') ]
```

**Importante:** fluxo é **assíncrono via N8N**, não Celery. Django nunca chama Anthropic/OpenAI/Gemini direto neste modal.

---

## 5. Models tocados

### Leitura
- **Post** — id, organization, user, status, created_at
- **PostFormat** — id, social_network, name, width, height, aspect_ratio, is_active
- **KnowledgeBase** — `n8n_compilation` (preferido), fallback para `nome_empresa`, `missao`, `posicionamento`, `tom_voz_externo`, `publico_externo`, `proposta_valor`

### Escrita
- **Post** (create):
  - `organization`, `user`, `requested_theme`, `social_network`, `content_type`, `formats`, `post_format` (FK)
  - `cta_requested`, `is_carousel`, `image_count`
  - `reference_images` (lista)
  - `status='generating'`, `caption=''`, `hashtags=''`
  - `ia_provider`, `ia_model_text`
- **PostReferenceImage** (create): `post` (FK), `s3_key`, `s3_url`, `original_name`, `order`

### Campos preparados mas NÃO usados pelo modal atual
`PostReferenceImage` tem 4 campos de "uso" da imagem que o modal atual não coleta — provavelmente preparados para fase futura:
- `usage_description` (TextField)
- `aspects_to_use` (TextField)
- `importance` (CharField)
- `usage_type` (CharField)

---

## 6. Payload de exemplo

### Request `POST /posts/gerar/`
```json
{
  "rede_social": "instagram",
  "post_format_id": 1,
  "cta_requested": true,
  "is_carousel": false,
  "image_count": 1,
  "tema": "Lançamento da campanha de natal com tom afetivo e familiar",
  "reference_images": [
    {"s3_key": "org-X/refs/abc.jpg", "url": "https://...", "name": "natal-ref.jpg"}
  ]
}
```

### Payload enviado ao N8N (webhook)
```json
{
  "organization": {...},
  "post_id": 123,
  "rede_social": "instagram",
  "formato": {...},
  "tema": "...",
  "knowledge_base": {
    "compilation": "...",
    "fallback_fields": {"nome_empresa": "...", ...}
  },
  "cta_requested": true,
  "is_carousel": false,
  "image_count": 1,
  "reference_images": [...]
}
```

### Callback `POST /posts/webhook/callback/` (do N8N para Django)
Atualiza `Post` com `caption`, `hashtags`, lista de imagens geradas e `status='ready'`.

---

## 7. JavaScript — funções principais

Arquivo: [app/static/js/posts.js](../app/static/js/posts.js)

| Função | Linhas | Responsabilidade |
|--------|--------|------------------|
| `loadPostFormats()` | 357–396 | Busca formatos via API conforme rede selecionada |
| `updateFormatoDimensions()` | 401–407 | Atualiza dimensões exibidas ao trocar formato |
| `toggleCarrossel()` | 696–702 | Mostra/oculta campo "Qtd imagens" |
| `uploadReferenceImages()` | 744–815 | Upload pro S3 via presigned URL |
| `requestPostFromAgent()` | 818–871 | Monta payload + POST `/posts/gerar/` |
| Form submit handler | 874–944 | Orquestra coleta → upload → request → close → reload |

**Validações JS:**
- Tema obrigatório (não-vazio)
- Rede obrigatória
- Formato obrigatório (após escolher rede)

**Abertura do modal:** `onclick="document.getElementById('modalGerarPost').style.display='block'"` — inline no botão do header.

---

## 8. Backend — view `gerar_post`

Arquivo: [app/apps/posts/views_gerar.py](../app/apps/posts/views_gerar.py) (linhas 18–318)

**Decorators:**
- `@login_required`
- `@require_http_methods(["POST"])`

**Validações:**
- `rede_social` ∈ {instagram, facebook, linkedin, whatsapp}
- `tema` não-vazio
- `post_format_id` (novo) OU `formato` (legado, string) — retrocompatibilidade
- Se `is_carousel`: `image_count` ∈ [2, 5]

**Configurações lidas de `settings`:**
- `N8N_WEBHOOK_GERAR_POST` — URL do webhook
- `N8N_WEBHOOK_SECRET` — header de autenticação
- `N8N_WEBHOOK_TIMEOUT` — default 30s

**Response (JsonResponse):**
```json
{
  "success": true,
  "id": 123,
  "status": "generating",
  "formatos": {...},
  "post": {...}
}
```

**Comportamento de erro:**
- Erros de validação → 400 com `{"success": false, "error": "..."}`
- Falha ao chamar N8N → Post permanece em `status='generating'`, retorna 500 ou 503
- Logging extensivo em pontos críticos

---

## 9. Observações importantes

1. **Sem TODO/FIXME** identificados no código atual — base estável.
2. **Retrocompatibilidade ativa**: view aceita tanto `post_format_id` (FK novo) quanto `formato` (string legado), com fallback.
3. **Fallback de KB**: se `n8n_compilation` está vazio, backend monta resumo manual a partir de 6 campos da `KnowledgeBase`.
4. **Reuso de endpoint**: imagens de referência usam endpoint do app Knowledge (`/knowledge/reference/upload-url/`) por reutilização — armazenadas em `PostReferenceImage`.
5. **Rate limiting**: callback `/posts/webhook/callback/` tem rate limit por IP via cache.
6. **CSS grid**: layout do form usa CSS Grid (2 colunas para rede+formato, 3 colunas para CTA+carrossel+qtd).
7. **Toda IA via N8N**: nenhuma chamada direta de SDK Anthropic/OpenAI no Django para este fluxo.

---

## 10. Gaps observados (candidates a refatoração)

> Esta seção é a lista de problemas / pontos a melhorar. Será atualizada conforme decidirmos o escopo da refatoração.

- [ ] **Sem preview visual** do post antes de gerar — user envia "às cegas"
- [ ] **Campos do PostReferenceImage não coletados** (`usage_description`, `aspects_to_use`, `importance`, `usage_type`) — preparados mas modal não pergunta
- [ ] **Abertura inline com `onclick`** — mistura JS no template (não escalável)
- [ ] **Reload da página em 2s após submit** — UX hard reload; poderia ser progressivo via polling/WebSocket
- [ ] **Dependência forte do N8N** — qualquer erro/lentidão no N8N quebra a UX sem feedback claro
- [ ] **Modal único para todos os clientes** — não respeita particularidades de brandbook
- [ ] **Tema como textarea livre** — sem estrutura (sem campos de título/data/CTA específicos)
- [ ] **Imagens de referência sem descrição de uso** — o N8N não sabe COMO usar cada imagem
- [ ] **Sem escolha explícita de logo/assets** quando a KB tem múltiplas variantes

---

## 11. Histórico de mudanças neste documento

| Data | Autor | Mudança |
|------|-------|---------|
| 2026-05-19 | Sessão inicial | Mapeamento inicial do modal atual (§§1–10) |
| 2026-05-19 | Etapa 1 (UI dos 2 botões) | Renomeado "Enviar ao agente" → "Enviar N8N". Adicionado "Enviar Fluxo interno" (visível só em homol/dev). Adicionado campo `Post.pipeline_used` + flag `settings.ENABLE_LOCAL_PIPELINE`. Ver §13. |
| 2026-05-19 | Etapa 2 (Endpoint + Celery task texto) | Criado `/posts/gerar-local/` + Celery task `generate_post_text_task` rodando Claude Sonnet 4.5 com prompt caching. Substitui o N8N `gerar-post-appiamkt`. Custo ~$0.01 por post. Ver §14. |

---

## 12. Decisões já tomadas

| # | Decisão | Justificativa |
|---|---------|---------------|
| D1 | 2 botões paralelos (N8N + Fluxo interno) ao invés de feature flag por org | Mais seguro, A/B test orgânico, reversível instantaneamente |
| D2 | Botão "Fluxo interno" visível apenas quando `settings.ENABLE_LOCAL_PIPELINE=True` (default: `ENVIRONMENT != 'production'`) | Permite teste em homol/dev sem afetar produção |
| D3 | Campo novo `Post.pipeline_used` (choices: `n8n`, `local`, default `n8n`) | Rastreio explícito de qual pipeline gerou cada post |
| D4 | Modelo IA texto no fluxo interno: **Claude Sonnet 4.5** (não OpenAI Assistant) | Mais barato, melhor com structured output, nativo no AIUsageLog |
| D5 | Modelo IA imagem no fluxo interno: **Gemini 3 Pro Image** (mesmo do N8N) | Não muda o que já funciona; reaproveita prompt do N8N |
| D6 | Fluxo interno mantém **2 cliques separados** (texto → user aprova → imagem) | Igual ao N8N atual; user precisa aprovar texto antes da imagem |
| D7 | Cores dos botões: N8N=primary (azul), Local=warning (laranja) | Sinaliza visualmente o caráter experimental do fluxo local |

## 13. Etapa 1 — UI dos 2 botões (implementada)

### Mudanças
**Settings** ([app/sistema/settings/base.py:14-23](../app/sistema/settings/base.py#L14-L23)):
```python
ENABLE_LOCAL_PIPELINE = config(
    'ENABLE_LOCAL_PIPELINE',
    default=(ENVIRONMENT != 'production'),
    cast=bool,
)
```

**Model** ([app/apps/posts/models.py](../app/apps/posts/models.py)):
- Novo campo `Post.pipeline_used` (CharField max=10, choices=[('n8n', ...), ('local', ...)], default='n8n')
- `Post.ia_provider` choices ganhou `'anthropic'`

**Migration**: [app/apps/posts/migrations/0015_add_pipeline_used.py](../app/apps/posts/migrations/0015_add_pipeline_used.py)

**View context** ([app/apps/posts/views.py:107](../app/apps/posts/views.py#L107)):
- `enable_local_pipeline = settings.ENABLE_LOCAL_PIPELINE` no contexto da `posts_list`

**View gerar atual** ([app/apps/posts/views_gerar.py:154](../app/apps/posts/views_gerar.py#L154)):
- `pipeline_used='n8n'` ao criar Post

**Template** ([app/apps/posts/templates/posts/posts_list.html:375-386](../app/apps/posts/templates/posts/posts_list.html#L375-L386)):
- "Enviar ao agente" → "Enviar N8N"
- Novo botão "Enviar Fluxo interno" dentro de `{% if enable_local_pipeline %}`
- `data-pipeline="n8n"` e `data-pipeline="local"` para identificação JS

**JS** ([app/static/js/posts.js:875-889](../app/static/js/posts.js#L875-L889)):
- Handler do submit lê `e.submitter.dataset.pipeline`
- Para `pipeline === 'local'`: mostra toast "em construção" e aborta (até Etapa 2)
- Para `pipeline === 'n8n'`: fluxo atual intocado

### Como testar
1. Abrir `/posts/` em homol/dev (`ENVIRONMENT=development`)
2. Clicar em "🎨 Gerar Post"
3. Modal mostra os 2 botões lado a lado
4. "Enviar N8N" — comportamento idêntico ao anterior
5. "Enviar Fluxo interno" — após Etapa 2, dispara Celery task
6. Em produção (`ENVIRONMENT=production` ou `ENABLE_LOCAL_PIPELINE=False`), só "Enviar N8N" aparece

---

## 14. Etapa 2 — Endpoint + Celery task texto (implementada)

### Arquivos novos
- [app/apps/posts/services/__init__.py](../app/apps/posts/services/__init__.py)
- [app/apps/posts/services/claude_post_generator.py](../app/apps/posts/services/claude_post_generator.py) — service que encapsula chamada Claude Sonnet 4.5
- [app/apps/posts/tasks.py](../app/apps/posts/tasks.py) — Celery task `generate_post_text_task`
- [app/apps/posts/views_gerar_local.py](../app/apps/posts/views_gerar_local.py) — view do endpoint `/posts/gerar-local/`
- [app/apps/posts/migrations/0016_add_visual_brief_and_slides.py](../app/apps/posts/migrations/0016_add_visual_brief_and_slides.py)

### Arquivos modificados
- [app/apps/posts/models.py](../app/apps/posts/models.py) — campos novos `Post.visual_brief` (TextField) e `Post.slides_data` (JSONField)
- [app/apps/posts/urls.py](../app/apps/posts/urls.py) — `path('gerar-local/', views_gerar_local.gerar_post_local, name='gerar_local')`
- [app/static/js/posts.js](../app/static/js/posts.js) — `requestPostFromAgent(payload, pipeline)` roteia para endpoint correto
- [app/requirements.txt](../app/requirements.txt) — adicionado `anthropic==0.101.0`

### Fluxo da pipeline interna

```
[ User clica em "Enviar Fluxo interno" ]
         ↓
[ JS detecta data-pipeline='local' do botao ]
         ↓
[ JS uploadReferenceImages() se houver imagens (mesmo endpoint S3) ]
         ↓
[ JS POST /posts/gerar-local/ {rede, post_format_id, tema, ...} ]
         ↓
[ Backend views_gerar_local.gerar_post_local()
   ├─ Valida payload (mesma logica do gerar/)
   ├─ Cria Post(pipeline_used='local', status='generating', ia_provider='anthropic')
   ├─ Cria PostReferenceImage por imagem
   └─ Dispara generate_post_text_task.delay(post.id) ]
         ↓
[ Celery worker iamkt_celery
   ├─ Carrega Post + KB
   ├─ Monta resumo da KB (prefere n8n_compilation, fallback manual)
   ├─ Chama Claude Sonnet 4.5 via service (com prompt caching)
   ├─ Parse JSON: {title, subtitle, image_prompt, caption, hashtags, visual_brief, cta_text}
   ├─ Para carrossel: parse {slides[], caption, hashtags, cta_text}
   ├─ Atualiza Post (todos os campos textuais)
   ├─ Loga em AIUsageLog (se disponivel nesta branch)
   └─ Status final: 'pending' (texto pronto, aguarda user disparar imagem)
]
         ↓
[ Frontend recarrega lista, ve post com texto pronto ]
```

### Service Claude — schema de saída

JSON puro retornado por Claude Sonnet 4.5 (post único):
```json
{
  "title": "string max 60 chars",
  "subtitle": "string max 90 chars",
  "image_prompt": "descricao detalhada da cena/composicao",
  "visual_brief": "diretrizes de marca para o gerador de imagem",
  "caption": "legenda completa 200-500 chars",
  "hashtags": ["array", "sem", "hashtag", "no", "inicio"],
  "cta_text": "max 8 palavras ou string vazia"
}
```

Carrossel:
```json
{
  "slides": [
    {"title": "...", "subtitle": "...", "image_prompt": "...", "visual_brief": "..."}
  ],
  "caption": "legenda geral do carrossel",
  "hashtags": [...],
  "cta_text": "..."
}
```

### Custo medido

| Métrica | Valor |
|---------|-------|
| Modelo | `claude-sonnet-4-5` |
| Pricing | $3/M input + $15/M output (cache write $3.75/M, cache read $0.30/M) |
| Tokens médios por chamada | ~670 in / ~545 out |
| Custo por post (sem cache) | **~$0.010** |
| Custo por post (com cache hit no system) | **~$0.005** estimado |
| Latência | ~10-12s end-to-end (Claude + Celery overhead) |

### Status do Post durante o fluxo

| Momento | Status |
|---------|--------|
| Criado | `generating` |
| Task em retry (falha temporária) | `failed` (será reprocessado) |
| Texto gerado, aguardando user disparar imagem | `pending` |
| User clica "Gerar Imagem" (Etapa 3) | `image_generating` |
| Imagem pronta | `image_ready` |

### Como testar end-to-end

```bash
# Sync (debug, sem Celery)
docker compose exec -T iamkt_web python manage.py shell -c "
from apps.posts.tasks import generate_post_text_task
generate_post_text_task(POST_ID)  # sem .delay()
"

# Async (real, via worker)
docker compose exec -T iamkt_web python manage.py shell -c "
from apps.posts.tasks import generate_post_text_task
generate_post_text_task.delay(POST_ID)
"

# Via UI: abre /posts/, modal, "Enviar Fluxo interno"
```

### Gaps Etapa 2

- [ ] `AIUsageLog` ainda não existe nesta branch (defensivamente skippa) — virá quando branch Colletivo mergear ou criarmos aqui
- [ ] Sem polling/notificação na UI: user precisa recarregar pra ver o texto pronto
- [ ] Sem prompt customizado por org (KB compilation é genérica)
- [ ] Sem suporte a Vision (referencias passam só como URLs textuais, Claude não analisa visualmente ainda)
