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
| 2026-05-19 | Etapa 3 (Celery task imagem) | Celery task `generate_post_image_task` rodando Gemini 3 Pro Image. View `generate_image` roteia para Celery quando `post.pipeline_used='local'`. Substitui N8N `gerarimagem-appiamkt`. Custo ~$0.04 por imagem. Latência ~25-60s. Ver §15. |
| 2026-05-20 | Etapa 4 (Galerias + lightbox + upload estruturado) | Modal ganhou 3 seções abaixo do tema: galeria de logos da KB (multi-select), galeria de references da KB (multi-select + textarea de uso), upload estruturado (cada arquivo com select de `usage_type` + textarea de `usage_description`). Lightbox global vanilla. Endpoint `GET /posts/api/org-assets/` lista assets com presigned URLs. Campo novo `Post.local_pipeline_context` (JSONField) persiste seleções. Task respeita as seleções ao montar prompts. Ver §16. |

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

---

## 15. Etapa 3 — Celery task imagem via Gemini (implementada)

### Arquivos novos
- [app/apps/posts/services/gemini_image_generator.py](../app/apps/posts/services/gemini_image_generator.py) — service que encapsula chamada Gemini 3 Pro Image

### Arquivos modificados
- [app/apps/posts/tasks.py](../app/apps/posts/tasks.py) — adicionada task `generate_post_image_task` + helpers
- [app/apps/posts/views_actions.py](../app/apps/posts/views_actions.py) — view `generate_image` roteia para Celery quando `post.pipeline_used='local'` (antes do bloco N8N)

### Fluxo da Etapa 3

```
[ User clica "Gerar Imagem" no detalhe do post (com pipeline_used='local') ]
         ↓
[ POST /posts/<id>/generate-image/ ]
         ↓
[ views_actions.generate_image()
   ├─ Cria PostChangeRequest
   ├─ status='image_generating'
   ├─ Detecta post.pipeline_used == 'local'
   └─ generate_post_image_task.delay(post.id, message) ]
         ↓
[ Celery worker iamkt_celery
   ├─ Carrega Post + KB + paleta + tipografia
   ├─ Coleta referências (logos + KB images + post images)
   ├─ Gera presigned URLs (24h) para cada
   ├─ Service gemini_image_generator:
   │    ├─ Baixa cada referência → base64
   │    ├─ Ordena (logos primeiro, depois refs)
   │    ├─ Monta prompt textual com regras por tipo (replica N8N)
   │    ├─ Monta parts multimodais: text + inline_data[]
   │    ├─ POST gemini-3-pro-image-preview:generateContent
   │    └─ Extrai base64 da resposta
   ├─ Upload PNG no S3 (org-{X}/imagensgeradas/{ts}-post{id}-generated.png)
   ├─ Atualiza Post (image_s3_key, image_s3_url, generated_images[])
   ├─ status='image_ready'
   └─ Loga AIUsageLog (Gemini)
]
```

### Service Gemini — prompt textual

Replica integralmente a lógica do node `Code in JavaScript4` do N8N workflow `gerarimagem-appiamkt`:

- **Regras de uso por tipo** (`USAGE_RULES_BY_TYPE`):
  - `logotipo` / `logo` → aplicar sem alteração
  - `referencia_post` / `referencia_kb` → inspiração de estilo, fotografia, iluminação
  - `produto` → aplicar fielmente ao original (sem reinterpretar)
  - `icone`, `fundo`/`background`, `post_image` etc.
- **Priorização** (`TYPE_PRIORITY`): logos antes, depois referências, depois outros
- **Prompt completo** inclui: briefing, texto que deve aparecer, análise das referências, descrição da cena, diretrizes de marca (paleta, tipografia, visual_brief), qualidade

### Custo medido

| Métrica | Valor |
|---------|-------|
| Modelo | `gemini-3-pro-image-preview` |
| Custo por imagem (estimado) | **~$0.04** |
| Latência (sync direto) | ~25s |
| Latência (async via Celery) | ~25-60s (incluindo cold start) |

### Status transitions completas

| Estágio | Status do Post |
|---------|---------------|
| Texto sendo gerado | `generating` |
| Texto pronto, aguardando user | `pending` |
| Imagem sendo gerada | `image_generating` |
| Imagem pronta | `image_ready` |
| Aprovado por user | `approved` |

### Resultados validados (testes em homol)

Posts gerados end-to-end (texto Claude → imagem Gemini):

| Post | Tema | Resultado visual |
|------|------|------------------|
| 52 | 5 dicas Instagram pequenos negócios | Flat lay com café, smartphone Instagram, teclado, planta, caderno + título/subtítulo/CTA exatos + branding "ACME Corp" |
| 54 | Workshop design thinking para times de produto | Equipe colaborativa em mesa com post-its + título/subtítulo/CTA exatos + branding "ACME Corp" |

### Gaps Etapa 3

- [ ] Sem polling/notificação UI: user precisa recarregar pra ver imagem
- [ ] Aspect ratio segue `post.post_format` (Gemini interpreta livremente — pode não respeitar exato em todos os casos)
- [ ] Sem regeneração com `message` específico (já passado, mas prompt não usa ainda)
- [ ] AIUsageLog ainda defensivo (não existe na branch main)
- [ ] Custo flat-rate estimado em `$0.04` — não puxa usageMetadata real do Gemini (campo `cost_usd` é placeholder)

---

## 16. Etapa 4 — Galerias + lightbox + upload estruturado (implementada)

### Arquivos novos
- [app/apps/posts/migrations/0017_add_local_pipeline_context.py](../app/apps/posts/migrations/0017_add_local_pipeline_context.py)

### Arquivos modificados
- [app/apps/posts/models.py](../app/apps/posts/models.py) — campo `Post.local_pipeline_context` (JSONField)
- [app/apps/posts/views_api.py](../app/apps/posts/views_api.py) — endpoint `get_org_assets`
- [app/apps/posts/urls.py](../app/apps/posts/urls.py) — `path('api/org-assets/', views_api.get_org_assets, ...)`
- [app/apps/posts/views_gerar_local.py](../app/apps/posts/views_gerar_local.py) — aceita `selected_logo_ids`, `selected_reference_ids`, `references_usage_description`; persiste em `local_pipeline_context` e em `PostReferenceImage.usage_type`/`usage_description`
- [app/apps/posts/tasks.py](../app/apps/posts/tasks.py) — `_collect_references` e `_logos_from_org` filtram por seleção; refs_usage_general é concatenado ao kb_summary (Claude) e ao marketing_input_summary (Gemini)
- [app/apps/posts/templates/posts/posts_list.html](../app/apps/posts/templates/posts/posts_list.html) — 3 seções novas no modal + lightbox global
- [app/static/js/posts.js](../app/static/js/posts.js) — `loadOrgAssets`, `renderLogosGallery`, `renderReferencesGallery`, lightbox, upload estruturado
- [app/static/css/posts.css](../app/static/css/posts.css) — estilos `.asset-gallery`, `.asset-thumb`, `.uploaded-image-card`, `.image-lightbox`

### Schema do `Post.local_pipeline_context`
```json
{
  "selected_logo_ids": [32],
  "selected_reference_ids": [42, 43],
  "references_usage_description": "usar como inspiração de paleta..."
}
```

### Fluxo da UI

```
[ User abre o modal ]
   ↓
[ loadOrgAssets() → GET /posts/api/org-assets/?type=all → JSON com logos+refs (presigned URLs) ]
   ↓
[ renderLogosGallery + renderReferencesGallery → thumbs clicáveis ]
   ↓
[ Click no thumb = toggle selecionado (borda roxa + ✓)
  Double-click no thumb = abre lightbox em tela cheia ]
   ↓
[ Upload de novas imagens → ingestUploadedFiles → cards com select de tipo + textarea ]
   ↓
[ Submit → payload inclui selected_logo_ids, selected_reference_ids, references_usage_description
  + cada reference_image[] tem usage_type + usage_description ]
   ↓
[ Backend persiste em Post.local_pipeline_context + PostReferenceImage ]
   ↓
[ Task usa apenas os logos/refs selecionados + descrição geral no prompt ]
```

### Tipos de uso disponíveis (`usage_type`)
- `produto` — aplicar fielmente ao original (sem reinterpretar) — Gemini recebe regra especial
- `pessoa` — speaker, retrato
- `cenario` — lugar, ambiente
- `referencia_estilo` — paleta, fotografia, mood
- `icone` — elemento gráfico
- `fundo` — textura/background
- `outro` — fallback

### Endpoint `GET /posts/api/org-assets/`
Query params: `?type=logos|references|all` (default `all`)

Response:
```json
{
  "success": true,
  "logos": [
    {"id": 32, "name": "...", "logo_type": "principal", "is_primary": false, "file_format": "png", "url": "<presigned>"}
  ],
  "references": [
    {"id": 42, "title": "...", "description": "...", "usage_description": "...", "width": 1080, "height": 1350, "url": "<presigned>"}
  ]
}
```

### Lightbox global
- Elemento único `#imageLightbox` (fora dos modais)
- `openLightbox(url)` / `closeLightbox()` JS expostos
- Fecha com click no overlay, no botão × ou tecla ESC
- Funciona para qualquer thumb (galerias e uploads)

### UX dos thumbs
- **Single-click**: toggle de seleção (borda roxa + checkmark)
- **Double-click**: abre lightbox em tela cheia
- **Shift/Alt + click**: também abre lightbox (atalho)
- Badge no canto inferior esquerdo: tipo do logo (`principal`, `horizontal`, etc.)

### Validado em homol
Post 57 (org 25 Colletivo Real):
- 1 logo selecionado, 2 refs selecionadas, descrição geral preenchida
- Claude gerou texto coerente com brand ("Design que nasce da colaboração", "vozes plurais")
- `local_pipeline_context` persistido corretamente

### Gaps Etapa 4
- [ ] View N8N atual (`gerar_post`) não aceita os campos novos — segue ignorando (compat)
- [ ] Sem teste de lightbox em viewport mobile
- [ ] Endpoint `get_org_assets` não paginado (assumindo KBs com < 50 logos/refs)

### Refinos pós-validação (2026-05-20)
- **Logo é single-select** (1 por post): galeria de logos agora deseleciona os outros ao escolher um novo. Backend defensivamente trunca `selected_logo_ids[:1]`. Hint atualizado no modal.

### Iteração de fidelidade de produto (2026-05-20)

**Problema observado:** Gemini regredia para modelos antigos (TM6 ao invés de TM7) por "name-as-anchor failure" — o nome "Thermomix" no prompt textual ativava priors do training data mais fortes que o sinal visual.

**Caminhos testados (4 versões do mesmo post):**

| Versão | Estratégia | Resultado |
|--------|-----------|-----------|
| v1 | Prompt básico, sem regras | TM6 (modelo antigo) |
| v2 | + Bloco "REGRA CRÍTICA FIDELIDADE" + TYPE_PRIORITY[produto]=1 | Híbrido TM6/TM7 |
| v3 | + Claude Vision com bracket-naming, KEEP_UNCHANGED, negative-naming | TM7-like mas com formato estranho |
| v4 | Trocar para `nano-banana-pro-preview` | Regrediu para TM5 |
| **v5** | **SIMPLIFICAÇÃO RADICAL** — sem Claude Vision, sem listas, sem citar marca no `image_prompt`. Apenas "o produto da IMAGEM N anexada" | **TM7 fiel** ✅ |

**Lição:** simplicidade venceu. Toda a engenharia anterior (Claude Vision, bracket-naming, KEEP_UNCHANGED) **introduzia ruído**. O Gemini é melhor em **dereferenciação por imagem** ("o produto da imagem 2") do que em interpretar listas longas de specs.

**Mudanças aplicadas:**

1. **Gemini prompt simplificado** ([gemini_image_generator.py:_build_prompt_text](../app/apps/posts/services/gemini_image_generator.py)):
   ```
   # REFERENCIAS VISUAIS (anexadas ACIMA deste texto, na ordem)
   IMAGEM 1: logotipo da marca — aplicar exatamente como aparece
   IMAGEM 2: o produto principal — use exatamente como aparece (mesmas cores,
            mesmo formato, mesmos detalhes)

   # CENA
   {image_prompt}
   ```
   Sem KEEP_UNCHANGED, sem bracket-naming, sem negative-naming, sem identificar produto pelo nome.

2. **Claude (texto) não menciona marca/produto no `image_prompt`** ([claude_post_generator.py:SYSTEM_PROMPT](../app/apps/posts/services/claude_post_generator.py)):
   - Antes: "destaque para o robô de cozinha Thermomix em cor branca..."
   - Agora: "destaque para o produto principal em uma cozinha minimalista..."
   - Eliminado conflito entre cor textual (Claude inventava) vs cor real da imagem.

3. **Claude Vision desativado** (mantida função no código pra rollback rápido): economia de $0.005/post e -5s latência. Não traz benefício mensurável vs prompt simples.

4. **Modelo mantido em `gemini-3-pro-image-preview`**: Nano Banana Pro regrediu pra TM5. Override via env var `GEMINI_IMAGE_MODEL` continua disponível pra testes.

**Custo final por post:** ~$0.05 (texto + imagem). **Latência:** ~25-30s.

**Limitação remanescente:** mesmo com simplicidade, ~10-15% dos casos podem ainda regredir para modelo similar do training data. Mitigação atual: usuário pode clicar "Gerar Imagem" novamente — preserva histórico e gera nova candidata.

---

## 17. Smart Pillow Overlay — Em desenvolvimento (PARADO AQUI 2026-05-20)

### Contexto e descoberta crítica

Após validar que a simplificação radical (§16) trouxe ganhos, fizemos um teste decisivo no **post 62** (org Thermomix, "Conheça a Thermomix TM7"). Geramos 3 versões do mesmo post variando o `text_render_mode`:

| Modo | Comportamento | Produto rendido | Texto na imagem |
|------|---------------|----------------|-----------------|
| `inline` (atual) | Gemini renderiza texto e imagem | TM6/TM7 híbrido | Bonito, integrado |
| `sanitized` | Substitui "Thermomix"/"TM7" por `[produto]` no prompt | **TM5 (regrediu)** | Gemini reinventa texto |
| `pillow` (overlay simples) | Gemini gera só cena, sem texto | **TM7 fiel** ✅ | Faixa preta no topo + pill verde (feio) |

### 🎯 Descoberta chave

**Quando o Gemini não recebe texto pra renderizar no prompt, o produto sai FIEL.** A razão: o texto a renderizar (que continha "Thermomix TM7") era o que ativava o **name-anchor failure** — o Gemini puxava o modelo mais conhecido do training data. Sem esse anchor textual, o modelo se ancora apenas na imagem de referência.

Por isso o modo `pillow` foi a única estratégia que entregou o **TM7 correto** (display tablet horizontal separado embaixo).

**Mas:** o overlay simples (faixa preta + pill verde) é esteticamente pobre — tipografia genérica, layout fixo, sem identidade da marca.

### Plano Smart Pillow Overlay

Combinar o melhor dos 2 mundos:
- **Fidelidade do produto** via ausência de texto no prompt (Gemini puro)
- **Tipografia e layout da marca** via overlay Pillow inteligente

```
┌────────────────────────────────────────────────────────────┐
│ INPUT: PNG da cena (Gemini) + post + KB                    │
├────────────────────────────────────────────────────────────┤
│ 1. Carregar FONTE da KB                                    │
│    Typography model → CustomFont S3 (TTF) ou Google Fonts  │
│    → FontResolver (UA Android 2.3.5 força TTF)             │
│    → Fallback: DejaVu Bold                                 │
│                                                            │
│ 2. Carregar LAYOUT SPEC                                    │
│    a. Cache em kb.brand_layout_spec (JSONField novo)      │
│    b. Se vazio: Claude Vision analisa 1-3 references da KB │
│       e extrai padrões (title_position, size_pct, weight,  │
│       logo_position, cta_style, alignment, padding etc.)   │
│    c. Se não há references: wireframe fallback por aspect  │
│                                                            │
│ 3. Resolver LOGO URL                                       │
│    selected_logo_ids[0] do local_pipeline_context          │
│    → presigned URL S3 (24h)                                │
│                                                            │
│ 4. Pillow render                                           │
│    apply_text_overlay(png, title, sub, cta, layout_spec,   │
│                      title_font, subtitle_font, logo_url) │
│    - 9 anchors de posição (top-left até bottom-right)      │
│    - Auto-contrast (luminância da região)                  │
│    - CTA styles: pill | block | outline | underline | none │
│    - Logo composite com aspect-fit                         │
└────────────────────────────────────────────────────────────┘
```

### Arquivos criados (não-commitados)

1. [app/apps/posts/services/font_resolver.py](../app/apps/posts/services/font_resolver.py) — portado/adaptado do branch Colletivo
   - `resolve_font_for_kb(kb, usage_filter, weight)` — entrypoint
   - `_load_custom_font()` — baixa TTF/OTF do S3
   - `_load_google_font()` — Google Fonts CSS API com UA Android 2.3.5
   - `system_dejavu_path()` — fallback final

2. [app/apps/posts/services/brand_layout_analyzer.py](../app/apps/posts/services/brand_layout_analyzer.py)
   - `analyze_brand_layout_from_references(kb, force_refresh=False)` — Claude Sonnet 4.5 Vision analisa até 3 refs
   - System prompt detalhado com valores limitados
   - Cache em `kb.brand_layout_spec` (skippa se já analisado)
   - Custo: ~$0.01 por análise, 1x por org

3. [app/apps/posts/services/layout_wireframes.py](../app/apps/posts/services/layout_wireframes.py)
   - `wireframe_for_aspect(aspect, formato_px)` → spec padrão
   - Regras por aspect: 1:1, 4:5, 9:16, 16:9, 1200x630
   - Heurística por w/h ratio quando aspect não reconhecido

4. [app/apps/knowledge/migrations/0024_add_brand_layout_spec.py](../app/apps/knowledge/migrations/0024_add_brand_layout_spec.py)
   - Aplicada ✅

### Arquivos modificados (não-commitados)

5. [app/apps/knowledge/models.py](../app/apps/knowledge/models.py)
   - `KnowledgeBase.brand_layout_spec` (JSONField) — cache do layout analisado

6. [app/apps/posts/services/gemini_image_generator.py](../app/apps/posts/services/gemini_image_generator.py)
   - `apply_text_overlay()` reescrito (smart): aceita `layout_spec`, fontes resolvidas, `logo_url`
   - Helpers novos: `_anchor_to_xy()`, `_x_for_alignment()`, `_resolve_text_color()`, `_auto_contrast_color()`, `_draw_text_backdrop()`, `_draw_cta()`, `_draw_logo_on_overlay()`
   - `generate_post_image()` ganhou args `pillow_layout_spec`, `pillow_title_font_path`, `pillow_subtitle_font_path`, `pillow_logo_url`

7. [app/apps/posts/tasks.py](../app/apps/posts/tasks.py)
   - `_prepare_pillow_overlay(post, kb, formato_px)` — orquestra todas as 3 camadas (font + layout + logo)
   - `_resolve_logo_url_for_overlay(post, kb)` — pega selected_logo_ids[0] ou primary
   - Chamada de `generate_post_image()` agora passa `**pillow_kwargs`

### 🐛 BUGS DESCOBERTOS NO ÚLTIMO TESTE (parar aqui)

Após implementar tudo e gerar a v4 do post 62 com Smart Pillow:

**Bug 1 — Gemini ignorou "não renderizar texto"**
- A regra `# IMPORTANTE — NAO RENDERIZAR NENHUM TEXTO` foi insuficiente.
- Resultado: Gemini AINDA escreveu "thermomix", "Conheça a Thermomix TM7", "Official Distributor", "Praticidade para toda a família" na própria imagem PNG.
- Em cima disso, o Pillow desenhou outra camada de texto → **texto duplo sobreposto** na imagem final.

**Bug 2 — Claude Vision extraiu spec ruim**
```json
{
  "title_size_pct": 5,         // muito pequeno
  "subtitle_size_pct": 4,      // QUASE IGUAL ao título (deveria ser ~50%)
  "title_weight": "regular",   // títulos quase sempre são bold
  "logo_position": "none",     // KB tem logo, mas Claude disse não usar
  "cta_style": "none",
  "alignment": "center"
}
```
- Claude interpretou as references como "minimalistas" e diminuiu/zerou tudo.
- KB org=15 (Thermomix) tem 3 references que foram analisadas — `kb.brand_layout_spec.reference_image_ids = [51, 50, 48]`.

**Bug 3 — Sem sanity checks**
- O spec extraído passou direto pro renderer sem validação.
- Não há invariantes garantidas (title ≥ subtitle, weight bold, logo se KB tem logo, etc.).

### Imagem do bug (post 62 v4 — não salva em S3 ainda)

Visual mostra:
- Texto "Conheça a Thermomix TM7" pequeno (Pillow)
- Sobreposto com "thermomix" + "Conheça a Thermomix TM7" + "Official Distributor" do Gemini
- Subtitle "Praticidade para toda a família na sua cozinha"
- Produto TM6/TM7 híbrido no centro
- Layout aspect ratio errado (parece 1200x630 mas ficou esmagado)

### Plano detalhado de retomada (amanhã)

**Prioridade 1 — Fix Bug 1 (Gemini renderiza texto sem permissão)**

Tentativas em ordem de agressividade:

a. **Repetir instrução múltiplas vezes** no prompt:
```
# IMPORTANTE — NAO RENDERIZAR NENHUM TEXTO

# REGRA #1: NAO HÁ TEXTO NESTA TAREFA. NAO desenhe letras, palavras,
slogans, números, símbolos textuais, marcas registradas ou QUALQUER
caractere alfanumérico.

# REGRA #2: Se você encontrar impulso de desenhar texto (mesmo no produto,
no logo, em embalagens, em sinalização do ambiente), IGNORE.

# REGRA #3: Tarefa visual pura — apenas o produto, ambiente, luz e
composição. Textos serão adicionados depois em pós-processamento.
```

b. **Adicionar exemplo negativo**: "Output WRONG: imagem com qualquer texto visível. Output CORRECT: imagem pura sem texto."

c. **Fallback de pós-processamento OCR**: se Gemini desobedecer, detectar texto via Tesseract/Pillow OCR e **borrar** essa região antes de aplicar Pillow overlay. Caro mas garantido.

**Prioridade 2 — Fix Bug 2 (spec ruim)**

a. **Sanity checks pós-Claude** em `analyze_brand_layout_from_references()`:
```python
def _sanitize_layout_spec(spec, kb):
    # title >= 7 (legibilidade mobile)
    spec['title_size_pct'] = max(7, float(spec.get('title_size_pct', 7)))
    # subtitle <= title * 0.55
    spec['subtitle_size_pct'] = min(
        float(spec.get('subtitle_size_pct', 3)),
        spec['title_size_pct'] * 0.55,
    )
    # weight: bold por default
    if spec.get('title_weight') not in ('bold', 'extrabold', 'black'):
        spec['title_weight'] = 'bold'
    # logo: se KB tem logo cadastrado, força posição (não 'none')
    if kb.logos.exists() and spec.get('logo_position', 'none') == 'none':
        spec['logo_position'] = 'top-right'  # default
    # cta_style: se vier 'none' mas post tem cta, força pill
    # (decisão runtime no overlay)
    return spec
```

b. **Melhorar prompt do brand_layout_analyzer** com exemplos numéricos:
```
- "minimalista" NÃO significa título pequeno. Significa POUCOS elementos.
  Título mínimo: 7% da altura para legibilidade mobile.
- Subtítulo SEMPRE menor que título — proporção ~1:2 ou ~1:2.5
- Marca premium ≠ texto fino. Bold ainda é o padrão para títulos.
```

**Prioridade 3 — Validação ponta-a-ponta**

1. Limpar `kb.brand_layout_spec` da org 15 (forçar re-análise)
2. Rodar Smart Pillow no post 62 novamente
3. Validar visualmente — title size razoável, sem texto duplo, logo presente

### Estado git ao parar

- Branch: `feature/novo-modal-gerar-post`
- Working tree: **3 arquivos modificados + 4 arquivos novos não commitados**
- Migration 0024 aplicada no DB local
- Último commit: `64e83a8` (simplificação radical, antes do Smart Pillow)

### Comandos úteis para retomar

```bash
# Ver status do trabalho não-commitado
git status

# Ver diff do que falta commitar
git diff app/apps/posts/services/gemini_image_generator.py

# Testar Smart Pillow direto
docker compose exec -T -e POST_TEXT_RENDER_MODE=pillow iamkt_web python manage.py shell -c "
from apps.posts.models import Post
from apps.posts.tasks import generate_post_image_task
p = Post.objects.get(id=62)
p.status='pending'; p.save()
generate_post_image_task(p.id, '')
p.refresh_from_db()
print(p.images.order_by('-order').first().s3_url)
"

# Forçar re-análise do layout (depois de mudar prompt)
docker compose exec -T iamkt_web python manage.py shell -c "
from apps.knowledge.models import KnowledgeBase
kb = KnowledgeBase.objects.filter(organization_id=15).first()
kb.brand_layout_spec = {}
kb.save()
print('cache limpado')
"

# Listar todas as imagens geradas do post 62
docker compose exec -T iamkt_web python manage.py shell -c "
from apps.posts.models import Post
p = Post.objects.get(id=62)
for img in p.images.order_by('order'):
    print(f'order={img.order} key={img.s3_key}')
"
```

### Posts de referência para testes

| Org | Post ID | Tema | Caso de uso |
|-----|---------|------|-------------|
| 15 (Thermomix) | 62 | "Conheça a Thermomix TM7" | Bug histórico do TM6/TM7 — bom teste de fidelidade de produto |
| 15 (Thermomix) | 61 | "Março é o Mês do Consumidor" | Funcionou no v5 simplificado — base de referência |
| 15 (Thermomix) | 60 | "Jantar Romântico Sem Estresse" | Cena com produto + casal — teste de composição |
| 25 (Colletivo) | 57 | "Workshop colaborativo Colletivo" | Org diferente, sem produto físico — teste de generalização |
| 2 (ACME) | 54 | "Workshop design thinking" | Org de teste — sem produto físico |
