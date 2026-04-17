# Resumo de Desenvolvimento — Sessao 15-16 Abril 2026

> Documento de referencia para retomar o desenvolvimento em qualquer servidor.
> Cobre tudo que foi implementado, bugs encontrados e corrigidos, decisoes
> tecnicas tomadas e o que falta fazer.

---

## Indice

1. [Contexto e Objetivo](#1-contexto-e-objetivo)
2. [O que foi implementado (por fase)](#2-o-que-foi-implementado-por-fase)
3. [Bugs encontrados e corrigidos](#3-bugs-encontrados-e-corrigidos)
4. [Decisoes tecnicas importantes](#4-decisoes-tecnicas-importantes)
5. [Estado atual de cada arquivo modificado](#5-estado-atual-de-cada-arquivo-modificado)
6. [O que falta fazer](#6-o-que-falta-fazer)
7. [Como retomar o desenvolvimento](#7-como-retomar-o-desenvolvimento)
8. [Pontos de rollback disponiveis](#8-pontos-de-rollback-disponiveis)

---

## 1. Contexto e Objetivo

O IAMKT e uma plataforma SaaS multi-tenant onde empresas preenchem uma base de
conhecimento (KB) e agentes de IA geram conteudo de marketing (pautas e posts).

O objetivo desta sessao foi implementar o **Pipeline de Brandguide**: permitir
que o usuario faca upload de um PDF de brandguide, a IA analise e extraia
identidade visual (cores, tipografia, grid, grafismos) automaticamente, e esses
dados sejam usados para gerar posts mais fieis a marca.

### Documentacao de referencia

| Documento | O que contem |
|-----------|-------------|
| [BRANDGUIDE_PIPELINE.md](BRANDGUIDE_PIPELINE.md) | Arquitetura completa do pipeline, modelos de dados, webhooks, custos |
| [PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md) | Plano em 8 fases com detalhes de cada item, rollback e criterios |
| [N8N_BRANDGUIDE_WORKFLOW.md](N8N_BRANDGUIDE_WORKFLOW.md) | Guia passo a passo para implementar o workflow N8N com prompts completos |
| [DOCUMENTACAO.md](../../DOCUMENTACAO.md) | Documentacao geral da aplicacao IAMKT |

---

## 2. O que foi implementado (por fase)

### Fase 1 — Modelos e campos de intent ✅ CONCLUIDA

**Commit:** `68ba060`
**Tag de rollback:** `fim-fase-1`

O que foi feito:
- 4 campos novos em `KnowledgeBase`: `brand_visual_spec` (JSONField), `brand_visual_spec_source`,
  `brand_visual_spec_confidence`, `brand_visual_spec_validated`
- 4 campos de intent em `ReferenceImage`: `usage_description`, `aspects_to_use`, `importance`, `usage_type`
- 8 campos novos em `Post`: `objetivo`, `generation_method`, `layout_plan`, `image_brief`,
  `raw_image_s3_url`, `raw_image_s3_key`, `comparison_image_s3_url`, `comparison_image_s3_key`
- 4 campos de intent em `PostReferenceImage` (mesmos do ReferenceImage)
- 3 modelos novos: `BrandguideUpload`, `BrandguidePage`, `BrandgraficModule`
- 1 modelo novo: `PostGenerationMetric` (para A/B testing futuro)
- Migrations: `knowledge.0020`, `posts.0014`

**Nota:** Todos os campos sao nullable ou tem default. Nenhuma tabela existente foi alterada
em estrutura, apenas campos adicionados. Registros existentes no banco ganharam defaults
automaticamente (testado com 17 KBs e 37 Posts).

### Fase 2 — Upload PDF + Conversao PNG ✅ CONCLUIDA

**Commit:** `625ed9b`
**Tag de rollback:** `fim-fase-2`

O que foi feito:
- Upload de PDF via presigned URL (mesmo padrao dos logos/referencias)
- Celery task `setup_brandguide_task` → chord de `convert_pages_batch_task` → `finalize_brandguide_task`
- Conversao em lotes de 5 paginas a 200 DPI (evita OOM no container de 512MB)
- Extracao de texto auxiliar com pdfplumber
- Worker dedicado `iamkt_celery_brandguide` (fila `brandguide`, concurrency=2, 768MB)
- Workers principais (`iamkt_celery`) nunca bloqueados por conversao de brandguide
- Interface de upload no Bloco 5 com barra de progresso real + polling de status
- Interface tambem na pagina /knowledge/perfil/

**Desafios enfrentados:**
- **OOM (Out of Memory)**: converter 60 paginas a 200 DPI de uma vez estourava 512MB do container.
  Solucao: processar em lotes de 5 com `first_page`/`last_page` do pdf2image, liberando memoria
  entre lotes. Cada batch task e independente (Celery chord).
- **N8N Code node travando**: payload muito grande (60 paginas com texto) travava o sandbox do N8N.
  Solucao: output leve (so `brandguide_id` + `callback_url`), dados pesados acessados via
  `$('Webhook')` direto.

**Dependencias adicionadas:**
- Python: `pdf2image==1.17.0`, `PyMuPDF==1.24.14`, `pdfplumber==0.11.4`
- Sistema: `poppler-utils` no Dockerfile
- Docker: novo service `iamkt_celery_brandguide` no docker-compose.yml

**Tempos medidos (PDF For Tomorrow, 60 paginas):**
- Conversao: ~68s (2 workers paralelos, batches de 5)
- Antes do fix de lotes: ~104s e crash por OOM

### Fase 3 — Analise IA via N8N + Brand Visual Spec ✅ CONCLUIDA

**Commit:** `21bad0d`
**Tag de rollback:** `fim-fase-3`

O que foi feito:
- Task `analyze_brandguide_task`: monta payload com presigned URLs de cada pagina + dados da KB,
  POST para `N8N_WEBHOOK_ANALYZE_BRANDGUIDE`
- Encadeamento automatico: `finalize_brandguide_task` detecta se webhook esta configurado e
  dispara analise. Se nao configurado, marca como `completed` (backward compat Fase 2).
- Webhook callback `brandguide_analysis_callback` em POST `/knowledge/webhook/brandguide/`:
  3 camadas de seguranca (token, IP whitelist, rate limit)
- Salva: `page_classifications` (categoria por pagina), `suggested_kb_fields`, `brand_visual_spec`
- Campo `ai_usage` (JSONField) em BrandguideUpload: rastreia tokens consumidos e custo estimado
- Guard contra callback de erro sobrescrevendo status `completed`

**Workflow N8N implementado e testado:**
- Triagem: GPT-4.1-mini com 60 imagens (low detail) → classifica paginas
- Analise profunda: GPT-4o com ~25 paginas relevantes (high detail) → extrai brand visual spec
- Callback com tokens consumidos + custo

**Resultados validados em producao (PDF For Tomorrow):**
- Custo total: ~$0.20 por brandguide (triagem $0.06 + analise $0.14)
- Tokens: ~175.000-200.000
- Cores extraidas: 8/9 (1 cor faltou — refinamento de prompt)
- Tipografia: Supreme + fallback IBM Plex Sans ✓
- Grid: 2x2 + 2x3 ✓
- Grafismo: 8 modulos ✓
- Classificacao: 53-59/60 paginas

**Desafios enfrentados:**
- **Presigned URLs**: as URLs publicas do S3 sao privadas. OpenAI nao conseguia baixar as imagens.
  Solucao: gerar presigned URLs (1h) no payload enviado ao N8N.
- **Error Trigger do N8N**: callback de erro de execucao anterior sobrescrevia status `completed`.
  Solucao: guard que ignora callback de erro se brandguide ja esta completed.
- **Cores imprecisas**: IA extraia cores de exemplos visuais, nao dos swatches oficiais.
  Solucao: prompt refinado pedindo "extraia apenas dos SWATCHES oficiais da paleta".

### Fase 4 — Templates Visuais + Assets ⚠️ PARCIALMENTE IMPLEMENTADA

**Commits:** `b8044cd` (backend) + `f5736c7` (frontend)

**O que foi feito:**

Backend (100% pronto):
- Modelo `VisualTemplate` (arte pronta como modelo para IA)
- `BrandgraficModule` com `manual_upload` adicionado ao choices
- 6 views CRUD: upload-url, create, delete para templates e assets
- 6 URLs em `/knowledge/template/*` e `/knowledge/asset/*`
- FileValidator: categorias `templates` (10MB, JPG/PNG/WebP) e `assets` (5MB, PNG/SVG)
- S3 paths: `org-{id}/templates/...` e `org-{id}/assets/...`
- Migration: `knowledge.0022`

Frontend (100% pronto):
- Partial `templates_assets_upload.html` no Bloco 5
- JS `templates-assets-upload.js` (presigned URL + upload + delete)
- Interface nas 3 paginas: `/knowledge/`, `/perfil/`, `/perfil-visualizacao/`
- Templates e assets so aparecem na visualizacao se tem dados

**O que falta na Fase 4:**
- Task `infer_visual_spec_task` (Brand Spec sem PDF, usando imagens de referencia)
- Logica inteligente de extracao do PDF (nao extrair se tem upload manual)
- Selecao de template no modal "Gerar Post"
- Vinculacao template ↔ assets (M2M)

### Fases 5-8 — NAO INICIADAS

| Fase | Descricao | Status |
|------|-----------|--------|
| 5 | Marketing Summary estruturado (evolucao do `n8n_compilation`) | So doc |
| 6 | Objetivo do post + Layout Planner | So doc |
| 7 | Compose Engine (renderizacao programatica com Pillow) | So doc |
| 8 | A/B Testing estilo livre vs renderizacao controlada | So doc |

---

## 3. Bugs encontrados e corrigidos

### Bug critico: Presigned URL do S3 com race condition de timestamp

**Commit:** `2814231`
**Arquivos:** `s3_service.py`, `perfil-references.js`, `perfil-logos.js`, `fonts.js`, `posts.js`

**Problema:** Upload para S3 falhava com 403 Forbidden intermitentemente.
O `x-amz-meta-upload-timestamp` era calculado 2x (uma no backend para assinar, outra no JS
para enviar). Se passasse 1 segundo entre as chamadas, a assinatura nao batia.

**Solucao:**
- Backend: calcular timestamp uma vez e reutilizar
- JS: usar `signed_headers` retornados pelo backend (4 arquivos corrigidos)

### Bug: Redes sociais nao salvavam na primeira etapa

**Commit:** `3cb9d6d`
**Arquivo:** `kb_services.py`

**Problema:** `SocialNetworkService.process_social_networks()` lia `social_instagram` mas
template envia `social_instagram_domain`. Campos nunca batiam → redes nao eram criadas.

**Solucao:** Ler `social_instagram_domain` com fallback + adicionar `https://` automatico.

### Bug: Site institucional nao salvava no save_all

**Commit:** `3cb9d6d`
**Arquivo:** `kb_services.py`

**Problema:** Template envia `site_institucional_domain` (sem https://), form espera
`site_institucional` (URL completa). `save_block` tinha processamento manual, `save_all` nao.

**Solucao:** Adicionado processamento de `site_institucional_domain` no `save_all_blocks`.

### Bug: Palavras recomendadas/evitar nao exibiam no perfil

**Commit:** `3cb9d6d`
**Arquivo:** `views.py`

**Problema:** View convertia JSONField list para comma-separated string (`"a, b, c"`).
JS `perfil-tags.js` esperava JSON parseavel (`["a", "b", "c"]`).

**Solucao:** Usar `json.dumps()` em vez de `', '.join()`.

### Bug: knowledge_base null no payload de geracao de post

**Commit:** `0411afa`
**Arquivo:** `views_gerar.py`

**Problema:** `marketing_input_summary` ausente em `n8n_compilation` de algumas orgs
fazia `knowledge_base_data = None` no payload enviado ao N8N.

**Solucao:** Fallback que monta resumo basico dos campos da KB quando summary nao existe.
Mantida mesma estrutura original do payload (4 campos).

### Bug: Imagens anteriores deletadas ao gerar nova

**Commit:** `0411afa`
**Arquivo:** `views_webhook.py`

**Problema:** `post.images.all().delete()` apagava todo o historico quando N8N devolvia
nova imagem.

**Solucao:** Manter imagens anteriores, adicionar novas com `order` incrementado.
Imagem mais recente vira a principal.

### Bug: Modal Editar Post com dark theme

**Commit:** `0411afa`
**Arquivo:** `posts.css`

**Problema:** CSS do modal usava cores hardcoded de dark theme (#17181d, #0e1017)
enquanto o resto da aplicacao usa light theme.

**Solucao:** Fundo branco, inputs claros, texto escuro, focus roxo.

### Bug: Middleware bloqueava /posts/preview-url/ em FLUXO 2

**Commit:** `625ed9b`
**Arquivo:** `middleware_onboarding.py`

**Problema:** Organizacoes com `suggestions_reviewed=False` (FLUXO 2) nao conseguiam
carregar imagens no perfil porque `/posts/preview-url/` era bloqueado pelo middleware
e redirecionado para `/knowledge/perfil/`.

**Solucao:** Adicionado `/posts/preview-url/` ao `ALLOWED_PATHS` do middleware.

### Bug: Delete de CustomFont standalone nao funcionava

**Commit:** `cbb7f68`
**Arquivo:** `views_perfil_fonts.py`

**Problema:** Botao X de fontes CustomFont passava ID como `custom_83` (variavel JS
inexistente) e backend so buscava em Typography.

**Solucao:** Template passa ID como string com aspas. Backend detecta prefixo `custom_`
e deleta CustomFont + S3 diretamente.

### Bug: Fontes duplicadas na perfil-visualizacao

**Commit:** `cbb7f68`
**Arquivo:** `perfil_visualizacao_linha2.html`

**Problema:** Template listava Typography E CustomFont sem filtrar. CustomFont ja
linkado a Typography aparecia 2x.

**Solucao:** `{% if not font.typography_usages.exists %}` pula CustomFont ja vinculado.

### Bug: Avaliacao negativa para campos com dados

**Commits:** `cbb7f68`, `53ec7c3`, `de9a2a3`
**Arquivo:** `views.py`

**Problema:** N8N dizia "nao ha arquivos informados" para logos, referencias, redes sociais,
tipografia e cores mesmo quando o usuario tinha feito upload/cadastro. A IA nao analisa
esses campos diretamente.

**Solucao:** Override que verifica se o campo tem dados no banco. Se tem, substitui avaliacao
negativa por "Dados cadastrados e disponiveis para uso" com badge "bom". Contagem de stats
movida para DEPOIS do override.

### Bug: Icones de redes sociais trocados

**Commit:** `53ec7c3`
**Arquivos:** `perfil.html`, `view.html`

**Problema:** Instagram usava SVG do Facebook, Facebook usava SVG do LinkedIn.
Placeholders usavam "femme" em vez de "iamkt".

**Solucao:** SVGs corrigidos + placeholders atualizados.

### Bug: KnowledgeBase nao podia ser deletada pelo admin

**Commit:** `3cb9d6d`
**Arquivo:** `admin.py`

**Problema:** `has_delete_permission` retornava `False` para todos, impedindo deletar
Organization via admin (cascade).

**Solucao:** Permite delete apenas para superusers.

---

## 4. Decisoes tecnicas importantes

### Dois modos de operacao (A e B)

Decidimos que o sistema funciona em 2 modos:
- **Modo A (com Brand Visual Spec):** IA gera imagem raw → Compose Engine renderiza com fontes,
  cores e grid exatos. Depende de Fase 7.
- **Modo B (sem Brand Visual Spec):** fluxo atual preservado intacto. Gemini gera imagem completa.

O codigo usa `if kb.brand_visual_spec:` para decidir. Modo B nunca e afetado.

### Fila dedicada para brandguide

Todas as tasks de brandguide rodam na fila `brandguide` consumida pelo worker
`iamkt_celery_brandguide`. Workers principais (`iamkt_celery`) processam apenas posts e pautas.
Isso garante que upload de PDF nunca bloqueia geracao de conteudo.

### Extracao de cores pela IA, nao por pixel

Decidimos NAO usar `colorgram.py` (extracao por pixel) para cores. A IA com Vision identifica
cores COM contexto semantico (primaria vs acento vs iniciativa) muito melhor que analise de pixels.

### Templates visuais vs Assets vs Referencias

- **Template:** arte pronta, modelo para a IA seguir fielmente
- **Asset:** grafismo isolado com transparencia, para overlay
- **Referencia:** inspiracao generica (mood, estilo)

Hierarquia de envio ao gerar post: template > assets > referencias.

### Extracao inteligente do PDF

Se o usuario ja fez upload manual de templates → nao extrair templates do PDF.
Se ja fez upload manual de assets → nao extrair assets do PDF.
So extrai do PDF o que ficou FALTANDO.

### Marketing Summary nao e campo novo

Decidimos NAO criar campo `marketing_summary` no modelo. Evoluimos o `n8n_compilation`
existente adicionando sub-bloco `marketing_input_structured` (JSONField ja existente).

---

## 5. Estado atual de cada arquivo modificado

### Modelos (Django)

| Arquivo | Mudancas |
|---------|----------|
| `knowledge/models.py` | +4 campos KB, +4 campos ReferenceImage, +3 modelos (BrandguideUpload, BrandguidePage, BrandgraficModule), +1 modelo (VisualTemplate), +1 choice manual_upload |
| `posts/models.py` | +8 campos Post, +4 campos PostReferenceImage, +1 modelo PostGenerationMetric |

### Migrations

| Migration | O que faz |
|-----------|-----------|
| `knowledge.0020` | brand_visual_spec, intents, BrandguideUpload, BrandguidePage, BrandgraficModule |
| `knowledge.0021` | ai_usage em BrandguideUpload |
| `knowledge.0022` | VisualTemplate, manual_upload choice |
| `posts.0014` | objetivo, generation_method, layout_plan, image_brief, raw/comparison URLs, intents, PostGenerationMetric |

### Views e backend

| Arquivo | Mudancas |
|---------|----------|
| `knowledge/views.py` | Contexto visual_templates/grafic_modules, override de avaliacao, contagem de stats pos-override, JSON para tags |
| `knowledge/views_brandguide.py` | Upload PDF, status, delete, callback N8N, CRUD templates/assets (6 views) |
| `knowledge/tasks.py` | Pipeline: setup→chord(batch)→finalize→analyze, presigned URLs |
| `knowledge/urls.py` | +5 rotas brandguide, +6 rotas templates/assets, +1 webhook |
| `knowledge/views_perfil_fonts.py` | Delete de CustomFont standalone com prefixo custom_ |
| `knowledge/kb_services.py` | Fix social_*_domain + https://, fix site_institucional no save_all |
| `knowledge/admin.py` | has_delete_permission para superusers |
| `posts/views_gerar.py` | Fallback para knowledge_base null (resumo basico da KB) |
| `posts/views_webhook.py` | Manter historico de imagens (nao deletar ao gerar nova) |
| `core/middleware_onboarding.py` | /posts/preview-url/ no ALLOWED_PATHS |
| `core/services/s3_service.py` | Timestamp unico, delete_prefix, paths templates/assets/brandguides |
| `core/utils/file_validators.py` | Categorias brandguides, templates, assets |
| `sistema/celery.py` | task_routes para fila brandguide |
| `sistema/settings/base.py` | BRANDGUIDE_*, N8N_WEBHOOK_ANALYZE_BRANDGUIDE |

### Templates HTML

| Arquivo | Mudancas |
|---------|----------|
| `knowledge/view.html` | Include brandguide_upload + templates_assets_upload, SVGs corrigidos, placeholders iamkt |
| `knowledge/perfil.html` | Tipos visual_templates/grafic_assets, upload na perfil, SVGs, skip grafic_assets card, delete fontes com aspas |
| `knowledge/partials/brandguide_upload.html` | NOVO: upload de PDF com status |
| `knowledge/partials/templates_assets_upload.html` | NOVO: upload de templates e assets |
| `knowledge/partials/perfil_visualizacao_linha2.html` | Cores com bolinha, tipografia Typography+CustomFont sem duplicata, templates/assets condicionais |
| `base/base.html` | Botao scroll-to-top |

### JavaScript

| Arquivo | Mudancas |
|---------|----------|
| `brandguide-upload.js` | NOVO: upload PDF + polling + status |
| `templates-assets-upload.js` | NOVO: upload templates/assets + delete |
| `perfil-references.js` | signed_headers do backend (fix S3) |
| `perfil-logos.js` | signed_headers do backend (fix S3) |
| `fonts.js` | signed_headers do backend (fix S3) |
| `posts.js` | signed_headers (fix S3), download de imagem via blob, botao download |

### CSS

| Arquivo | Mudancas |
|---------|----------|
| `knowledge.css` | Brandguide upload card + progress, website-field-wrapper flex:1 |
| `posts.css` | Modal light theme, botao download imagem |
| `base.css` | Botao scroll-to-top |
| `perfil-visualizacao.css` | compiling-message font-size 1rem |

### Docker e infra

| Arquivo | Mudancas |
|---------|----------|
| `Dockerfile` | +poppler-utils no runtime |
| `requirements.txt` | +pdf2image, +PyMuPDF, +pdfplumber |
| `docker-compose.yml` | Novo service iamkt_celery_brandguide, iamkt_celery com -Q celery |
| `.env` | N8N_WEBHOOK_ANALYZE_BRANDGUIDE |

---

## 6. O que falta fazer

### Prioridade ALTA (proximas sessoes)

1. **Selecao de template no modal "Gerar Post"**
   - Quando KB tem templates, mostrar grid de thumbnails no modal
   - Se escolher template: enviar template_image_url no payload (nao reference_images)
   - Fase 6 no plano, mas pode ser implementado antes

2. **Refinamento de prompts N8N** (so N8N, zero deploy Django)
   - Cores: pedir "extraia apenas dos SWATCHES oficiais da paleta"
   - Grafismo: pedir `aplicacoes_layout` com posicao, grid, cor por formato
   - nome_empresa: "use o nome do BRANDGUIDE, nao o valor existente na KB"
   - Prompt atualizado em N8N_BRANDGUIDE_WORKFLOW.md secao 5.3

3. **Aprovacao de sugestoes na perfil** (bug reportado mas nao debugado completamente)
   - Ao clicar "aceitar" sugestoes e salvar, `accepted_suggestions` chega vazio ao backend
   - Pode ser timing issue no JS ou modal de confirmacao
   - Precisa debug com browser console aberto

### Prioridade MEDIA

4. **Task `infer_visual_spec_task`** (Fase 4 pendente)
   - Gerar Brand Visual Spec para clientes SEM PDF (usando imagens de referencia)
   - Webhook `N8N_WEBHOOK_INFER_VISUAL_SPEC`
   - Callback reusa `/knowledge/webhook/brandguide/` com `source=reference_images`

5. **Extracao de assets do PDF** (Fase 7)
   - PyMuPDF para extrair grafismos embutidos como PNG/SVG
   - Logica inteligente: nao extrair se tem upload manual

6. **Visualizacao do Brand Visual Spec para o usuario**
   - Hoje: JSON salvo no banco, usuario nao ve
   - Implementar: tela mostrando cores (swatches), fontes (previews), grid, grafismos

### Prioridade BAIXA (futuro)

7. **Marketing Summary estruturado** (Fase 5)
8. **Layout Planner** (Fase 6) — agente que decide template baseado no objetivo do post
9. **Compose Engine** (Fase 7) — renderizacao programatica com Pillow
10. **A/B Testing** (Fase 8) — comparacao estilo livre vs renderizacao controlada
11. **Mensagem de prazo de imagem** — trocar calculo de horario comercial por "ate 10 minutos"

---

## 7. Como retomar o desenvolvimento

### Setup no novo servidor

```bash
cd /opt/iamkt
git pull origin main
docker compose build iamkt_web iamkt_celery
docker compose down
docker compose up -d
sleep 30
docker compose exec iamkt_web python manage.py migrate
docker compose exec iamkt_web python manage.py check
docker compose exec iamkt_web python manage.py collectstatic --noinput
```

### Variaveis de ambiente necessarias (adicionar ao .env)

```bash
# Obrigatorio para pipeline de brandguide
N8N_WEBHOOK_ANALYZE_BRANDGUIDE=https://n8n.srv1080437.hstgr.cloud/webhook/analyze_brandguide

# Opcionais (tem defaults)
BRANDGUIDE_MAX_FILE_SIZE=52428800   # 50 MB
BRANDGUIDE_DPI=200
BRANDGUIDE_BATCH_SIZE=5
```

### Estrutura de branches e tags

```
main (producao) ← onde estamos agora
  Tags de rollback:
    rollback-pre-brandguide-20260415  ← antes de tudo
    fim-fase-1                         ← modelos e intents
    fim-fase-2                         ← upload + conversao + worker
    fim-fase-3                         ← analise IA + brand visual spec
```

### Para testar o pipeline completo

1. Acessar `/knowledge/` → Bloco 5 → "Brandguide da marca" → upload PDF
2. Aguardar conversao (~1-2 min para 60 paginas)
3. Se `N8N_WEBHOOK_ANALYZE_BRANDGUIDE` configurado: analise IA automatica (~2-3 min)
4. Resultado em `kb.brand_visual_spec` (JSON no banco)

### Containers rodando

```
iamkt_web                 → Django (gunicorn)
iamkt_celery              → Worker principal (posts, pautas) - fila 'celery'
iamkt_celery_brandguide   → Worker brandguide (conversao PDF, analise) - fila 'brandguide'
iamkt_postgres            → PostgreSQL 15
iamkt_redis               → Redis 7
```

---

## 8. Pontos de rollback disponiveis

| Tag | Commit | O que reverte |
|-----|--------|---------------|
| `rollback-pre-brandguide-20260415` | `a394c73` | Remove TUDO do pipeline de brandguide |
| `fim-fase-1` | `68ba060` | Reverte para apos modelos/campos (sem upload/conversao) |
| `fim-fase-2` | `625ed9b` | Reverte para apos upload/conversao (sem analise IA) |
| `fim-fase-3` | `21bad0d` | Reverte para apos analise IA (sem templates/assets) |

```bash
# Para usar:
git checkout <tag>
docker compose exec iamkt_web python manage.py migrate
docker compose restart
```

**IMPORTANTE:** reverter migrations pode causar perda de dados nas tabelas novas.
Recomendado apenas em emergencia. Para desabilitar features sem perder dados,
basta remover as envs do `.env` e restartar.
