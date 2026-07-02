# Playbook — Onboarding de nova org, coleta de arquivos (Drive→S3) e arquétipos

Runbook prático dos 3 fluxos que usamos para colocar uma marca nova no ar com
pipeline de arte próprio (ex.: `todxs`, `vb-gastronomia`, `samsung-healthcare`).
Vive na branch `chore/seed-todxs-onboarding`.

Regras de ambiente (ver também o memory `project_runtime_docker`):
- Tudo roda **dentro do container**: `docker compose exec -T iamkt_web python manage.py ...`
  (o container tem credenciais AWS + models Django + internet; o host não).
- Gunicorn **sem auto-reload**: mudança de **código** exige
  `docker compose restart iamkt_web iamkt_celery`. Mudança de **template/estático**
  exige `collectstatic` + restart do `iamkt_web`. Mudança só de **dado no banco**
  não exige restart.
- `./app` é montado em `/app` no container; `docs-aplicacao/` **não** é montado
  (para levar arquivos locais ao container use `docker compose cp ... iamkt_web:/tmp/...`).

---

## 1) Criar uma empresa (org)

Padrão: um management command **idempotente, sem migrations** por org, em
`app/apps/core/management/commands/seed_<slug>.py` (espelhar
`seed_samsung_healthcare.py` / `seed_vb_gastronomia.py`).

O que ele cria/atualiza:
- **Organization** (`slug`, `name`, `tagline`, `plan_type='premium'`, `is_active`,
  `posts_enabled`, `pautas_enabled`).
- **User dono de teste** (`create_user`, `is_active`, `profile='operacional'`);
  vincula `user.organization` e define `org.owner`. Sem signals de email → não
  dispara nada (ver memory `feedback_no_emails`).
- **KnowledgeBase** (DNA da marca): `nome_empresa, missao, visao, valores,
  descricao_produto, publico_externo/interno, posicionamento, diferenciais,
  proposta_valor, tom_voz_externo, palavras_recomendadas[], palavras_evitar[]`.
  Ao consolidar de material oficial, **marcar a procedência** no texto
  (`[OFICIAL]` / `[NÃO PUBLICADA]` / `[INFERÊNCIA IAMKT]`) — reduz alucinação.
- **ColorPalette** (cores; `color_type` = primary|secondary|accent, `hex_code`
  `#RRGGBB`, `order`).
- **Typography** (papéis): `font_source='google'` (stand-in) OU `'upload'`
  ligado a um `CustomFont`. ⚠️ `Typography.usage` é `varchar(50)` — rótulos curtos.

Uso:
```bash
docker compose exec -T iamkt_web python manage.py seed_<slug> --dry-run   # valida (rollback)
docker compose exec -T iamkt_web python manage.py seed_<slug>             # aplica
# opções: --owner-email / --owner-password / --plan / --no-owner / --no-activate
```

Flags por org (em `Organization`) úteis: `archetype_selector_enabled` (mostra o
seletor de template no modal), quotas (`quota_posts_dia/mes`), `posts_enabled`.

Acesso ao **editor avançado** é admin-only → marcar o usuário de teste
`is_staff=True` enquanto valida:
```python
u = User.objects.get(email__iexact='...'); u.is_staff = True; u.save(update_fields=['is_staff'])
```

Assets (logos, fontes reais, imagens de referência) = **etapa 2**, feita pelo
fluxo Drive→S3 abaixo (dependem de arquivos + S3).

---

## 2) Coleta de arquivos do Drive → S3

Método autossuficiente (HTML + `urllib` + `boto3`), **dentro do container**. Não
usa o conector MCP do Drive. A pasta precisa estar compartilhada por link.

**Passo 1 — listar (id + nome)** via `embeddedfolderview` (o `/drive/folders/...`
é JS e não dá pra regexar):
```python
import re, urllib.request
from urllib.request import Request, urlopen
html = urlopen(Request(f'https://drive.google.com/embeddedfolderview?id={FOLDER_ID}#list',
                       headers={'User-Agent':'Mozilla/5.0'}), timeout=30).read().decode('utf-8','ignore')
ids   = re.findall(r'entry-([A-Za-z0-9_-]{25,})"', html)   # IDs do Drive têm ~33 chars
names = re.findall(r'flip-entry-title">([^<]+)</div>', html)
entries = list(zip(ids, names))   # filtra headers curtos tipo 'entry-last-modified'
```

**Passo 2 — baixar** cada arquivo pelo download direto (+ validar magic bytes):
```python
data = urlopen(Request(f'https://drive.google.com/uc?export=download&id={FID}',
                       headers={'User-Agent':'Mozilla/5.0'}), timeout=60).read()
assert data[:8] == b'\x89PNG\r\n\x1a\n'    # PNG; JPEG = b'\xff\xd8\xff'; OTF/CFF = b'OTTO'
```

**Passo 3 — subir ao S3 + criar o registro** (bucket privado → consumo por
presigned URL):
```python
from django.conf import settings
from apps.core.services.s3_service import S3Service
client = S3Service._get_s3_client()
s3_key = f'org-{org.id}/logos/nome-kebab.png'   # ou /fonts/  ou /references/
client.put_object(Bucket=settings.AWS_BUCKET_NAME, Key=s3_key, Body=data,
                  ContentType='image/png', StorageClass='INTELLIGENT_TIERING')
s3_url = S3Service.get_public_url(s3_key)
```

**Padrão de s3_key:** `org-{org.id}/{logos|fonts|references}/{nome-kebab}.{ext}`.

**Models por tipo de asset** (todos FK → `KnowledgeBase`):
- **Logo**: `name, logo_type(principal|horizontal|vertical|icone|monocromatico),
  s3_key, s3_url, file_format, is_primary`.
- **CustomFont**: `name (=font-family), font_type(titulo|corpo|destaque),
  s3_key, s3_url, file_format(ttf|otf|woff|woff2)`. Depois religar `Typography`
  para `font_source='upload'` + `custom_font=<CustomFont>`. Usar só a família
  **latina** (ignorar variantes `KR`/coreano) para conteúdo PT/EN.
- **ReferenceImage**: requer `perceptual_hash, file_size, width, height`
  (calcular com PIL + `imagehash.phash`). Dispara **análise visual** (dossiê
  Claude Vision) 1x: `analyze_reference_image_task.apply_async((ref.id,), countdown=10)`.
  ⚠️ Vision rejeita imagem **> ~5 MB ou > 8000 px** → **redimensionar** (ex.: lado
  maior 2048, JPEG q85) antes de subir/analisar. `usage_type=inspire|mimic|avoid`.

Para arquivos **locais** (ex.: fontes em `docs-aplicacao/<org>/`): copiar ao
container primeiro (`docker compose cp <arquivo> iamkt_web:/tmp/...`) e ler de lá,
já que `docs-aplicacao/` não é montado. Fontes do pipeline ficam versionadas em
`app/apps/posts/services/<org>/fonts/`.

Rodar os scripts via: `docker compose exec -T iamkt_web python manage.py shell < script.py`.

---

## 3) Usar arquétipos (pipeline de arte determinístico por org)

Cada org com arte própria tem um pipeline isolado (Pillow determinístico),
espelhando `todxs`/`vb`. Nenhuma outra org é afetada.

**Arquivos (espelhar para `<org>`):**
- `app/apps/posts/services/<org>/`
  - `wireframes.py` — `WIREFRAMES` (dict por chave de arquétipo) + `TOKENS`
    (cores) + `FONT_FILES` + `WF()`/`set_wireframes` (contextvar; banco pode
    sobrepor) + `archetypes_for_format` + `background_mode`. Cada zona:
    `key, category, role, box=[x,y,w,h] px, font, fs, max_linhas, leading,
    color(token|hex), case, align, fit`. Zonas de imagem: `fit=cover|contain`,
    `round_corners`, `radius`, `border`, `anchor/halign`.
  - `render.py` — `render_samsung(archetype, content, kb, assets)` →
    `{raw_png, final_png, elements, fonts_resolved}`. Fitter `_fit` (maior fonte
    que cabe em ≤max_linhas), gradiente, scrim, cantos arredondados, linha-guia.
  - `skill_brain.py` — 1 chamada Claude (`claude-sonnet-4-5`), **ciente do
    arquétipo**, mapeia o tema nas zonas + `caption/hashtags` (+ `image_prompt`
    quando precisa gerar imagem via Gemini). Respeita `tom_voz`/`palavras_evitar`.
  - `fonts/` — OTF/TTF bundled (render rápido/determinístico).
- `app/apps/posts/views_gerar_<org>.py` — cria `Post(pipeline_used='<org>')`,
  guarda `local_pipeline_context['<org>'] = {force_archetype, force_color, ...}`
  + `selected_reference_ids` / `selected_logo_ids`, dispara a task.
- `app/apps/posts/tasks_<org>.py` — `@shared_task generate_post_<org>_task`:
  brain → imagem (Gemini/ref) → `render_<org>` → upload S3 → persiste
  (`PostImage`, `designer_payload['_layout_elements']`, `raw_image_s3_key`,
  `status='image_ready'`).

**Ligações (checklist):**
1. Delegação: 1 `if org.slug == '<org>'` no topo de
   `views_gerar_simples.gerar_post_simples` → chama `gerar_post_<org>`.
2. ⚠️ **Registro Celery**: re-importar a task no **fim de `app/apps/posts/tasks.py`**
   (`from apps.posts.tasks_<org> import generate_post_<org>_task  # noqa`), senão
   o `.delay()` do front falha com *"Received unregistered task"* e o post trava
   em `generating`. **Testar sempre via `.delay()`**, não só `.run()` síncrono.
3. Catálogo: `python manage.py seed_archetypes --org <slug>` (o command é
   multi-org via `_wireframes_for(slug)`; importa `WIREFRAMES` → `PostArchetype`).
   `--resync-spec` reimporta a spec do código.
4. Flag: `org.archetype_selector_enabled = True`.
5. Thumbnails do slider: setar `PostArchetype.thumbnail` = uma `ReferenceImage`
   (o endpoint devolve `thumbnail_url` presigned); sem isso o card mostra só a
   letra da chave.

**Editor avançado (carregar/editar):**
- `render` deve emitir `_layout_elements` no schema do canvas: `role`
  (`titulo|subtitulo|image`), `content, x_pct, y_pct, width_pct, height_pct,
  font_size_pct` (base = `min(1080,1350)`), `font_key, weight, color, align,
  _leading`; logos/lockup como `role:'image'` com `url` **data-URI**.
- `views_overlay.overlay_data`: branch `pipeline_used=='<org>'` devolve
  `elements + raw_image_url + todxs_font_urls` (apontando p/ o endpoint de fonte
  da org) + `canvas_w/h`.
- Endpoint de fonte: view `<org>_font_file(post_id, key)` servindo os arquivos de
  `services/<org>/fonts/` + rota em `urls.py`
  (`<int:post_id>/<org>-font/<str:key>/`). O front (`posts_list.html`) já
  registra `data.todxs_font_urls` como `@font-face` e usa `el.font_key`.
- Botão "Edição Avançada" é admin-only (`is_staff`).
- **Pendente (genérico):** salvar/exportar com re-render do editor exige branch
  `<org>` em `save_elements`/`export_png` + função draw-from-elements.

**Modal (seletor de template):** `posts_list.html` tem o toggle
"Geração livre / Usar template". A galeria **"Imagens de referência existentes"**
(`orgRefsGallery`) fica fora do bloco escondido no modo template (só `logoField`
e `uploadRefField` somem) → dá pra escolher a imagem de produto no modo template.

**Especificidades Samsung (Relentless / Samsung Medison):** formato único feed 4:5;
accent `#3874B0` (≠ Samsung Blue `#1428A0`); brand_lockup = logo *Relentless
Innovation (Branco)* fixo inferior-direito.
- **A (Foto-topo):** foto via **Gemini** seguindo o tema; foto ancorada à direita
  (margem só à esquerda, sangra topo/direita), só o canto inferior-esquerdo
  arredondado (radius grande) + borda azul.
- **B (Produto-herói):** (1) imagem opaca → **fundo inteiro** + scrim navy à
  esquerda; (2) imagem transparente → compõe sobre gradiente navy; (3) sem
  imagem → **Gemini** gera. `guide_line` azul em ╰ (topo → desce → curva à
  direita), texto à direita da linha.
