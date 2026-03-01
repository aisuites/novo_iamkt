# Fluxo Gerar Imagem — Documentação Completa

> Documento gerado em 01/03/2026 com base nas implementações realizadas no projeto vibemkt.  
> Objetivo: servir como referência completa para reimplementar o mesmo fluxo em outra aplicação.

---

## Visão Geral do Fluxo

```
Usuário clica "Gerar Imagem" no frontend
        ↓
POST /posts/<id>/generate-image/   [views_actions.py → generate_image()]
        ↓
1. Valida limite de alterações
2. Muda status do Post para 'image_generating'
3. Cria PostChangeRequest (rastreamento)
4. Envia email de notificação
5. Monta payload e envia POST para N8N (N8N_WEBHOOK_GERAR_IMAGEM)
        ↓
N8N processa e gera imagem no S3
        ↓
N8N chama POST /posts/webhook/n8n/  [views_webhook.py → n8n_post_callback()]
        ↓
1. Valida token + IP + rate limit
2. Localiza post por post_id (ou thread_id)
3. Atualiza PostImage(s) com URLs do S3
4. Atualiza post.image_s3_url, post.has_image = True
5. Muda status para 'pending' ou o que o N8N definir
```

---

## 1. Pré-requisitos

### 1.1 Variáveis de ambiente obrigatórias

```env
# URL do webhook N8N que receberá a solicitação de geração de imagem
N8N_WEBHOOK_GERAR_IMAGEM=https://n8n.suaempresa.com/webhook/gerar-imagem

# Segredo compartilhado entre app e N8N (enviado em X-Webhook-Secret)
N8N_WEBHOOK_SECRET=seu_segredo_aqui

# IPs autorizados a chamar o callback (separados por vírgula)
N8N_ALLOWED_IPS=1.2.3.4,5.6.7.8

# URL base da aplicação (usada para montar o callback_url)
APP_BASE_URL=https://suaapp.com.br

# Bucket S3 onde as imagens serão armazenadas
AWS_BUCKET_NAME=seu-bucket-s3

# Timeout em segundos para chamadas ao N8N
N8N_WEBHOOK_TIMEOUT=30

# Rate limit por IP para o endpoint de callback
N8N_RATE_LIMIT_PER_IP=10/minute

# Emails que recebem notificações de solicitação de imagem
NOTIFICATION_EMAILS_GESTAO=gestor@empresa.com,equipe@empresa.com
```

### 1.2 Configuração em `settings/base.py`

```python
APP_BASE_URL = config('APP_BASE_URL', default='https://suaapp.com.br').rstrip('/')

N8N_WEBHOOK_GERAR_IMAGEM = config('N8N_WEBHOOK_GERAR_IMAGEM', default='')
N8N_WEBHOOK_SECRET       = config('N8N_WEBHOOK_SECRET', default='')
N8N_WEBHOOK_TIMEOUT      = config('N8N_WEBHOOK_TIMEOUT', default=30, cast=int)
N8N_ALLOWED_IPS          = config('N8N_ALLOWED_IPS', default='127.0.0.1')
N8N_RATE_LIMIT_PER_IP    = config('N8N_RATE_LIMIT_PER_IP', default='10/minute')
AWS_BUCKET_NAME          = config('AWS_BUCKET_NAME', default='seu-bucket')
```

---

## 2. Models

### 2.1 `PostFormat` — novo model criado

Tabela global (não vinculada a organização) com formatos padrão de imagem por rede social.

```python
# app/apps/posts/models.py

class PostFormat(models.Model):
    NETWORK_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('twitter', 'Twitter/X'),
        ('tiktok', 'TikTok'),
        ('whatsapp', 'WhatsApp'),
    ]

    social_network = models.CharField(max_length=20, choices=NETWORK_CHOICES)
    name           = models.CharField(max_length=100)   # ex: "Feed Retrato", "Stories"
    width          = models.IntegerField()               # ex: 1080
    height         = models.IntegerField()               # ex: 1350
    aspect_ratio   = models.CharField(max_length=10)    # ex: "4:5", "9:16"
    is_active      = models.BooleanField(default=True)
    order          = models.IntegerField(default=0)

    class Meta:
        unique_together = [['social_network', 'name']]

    @property
    def dimensions(self):
        return f"{self.width}x{self.height}"
```

**Dados pré-populados via migration de dados (14 formatos):**

| Rede | Nome | Largura | Altura | Aspect Ratio |
|---|---|---|---|---|
| instagram | Feed Retrato | 1080 | 1350 | 4:5 |
| instagram | Feed Quadrado | 1080 | 1080 | 1:1 |
| instagram | Feed Paisagem | 1080 | 566 | 1.91:1 |
| instagram | Stories | 1080 | 1920 | 9:16 |
| instagram | Reels | 1080 | 1920 | 9:16 |
| facebook | Feed | 1200 | 630 | 16:9 |
| facebook | Feed Quadrado | 1080 | 1080 | 1:1 |
| facebook | Stories | 1080 | 1920 | 9:16 |
| linkedin | Feed | 1200 | 627 | 16:9 |
| linkedin | Feed Quadrado | 1080 | 1080 | 1:1 |
| linkedin | Stories | 1080 | 1920 | 9:16 |
| tiktok | Vídeo/Reels | 1080 | 1920 | 9:16 |
| whatsapp | Status | 1080 | 1920 | 9:16 |
| whatsapp | Imagem | 1080 | 1080 | 1:1 |

### 2.2 `Post` — campos relevantes ao fluxo

```python
class Post(models.Model):
    # Identificação
    organization    = ForeignKey('core.Organization', ...)
    user            = ForeignKey(User, ...)

    # Dados do post (enviados ao N8N)
    title           = CharField(max_length=220, blank=True)
    subtitle        = CharField(max_length=220, blank=True)
    cta             = CharField(max_length=160, blank=True)
    social_network  = CharField(max_length=20, choices=[...])
    content_type    = CharField(max_length=20, choices=['post','carrossel','story','reels'])
    formats         = JSONField(default=list)    # ex: ['feed'], ['stories'], ['feed','stories']
    is_carousel     = BooleanField(default=False)
    image_count     = PositiveSmallIntegerField(default=1)
    image_prompt    = TextField(blank=True)      # prompt gerado pelo agente de texto

    # Rastreamento N8N
    thread_id       = CharField(max_length=160, blank=True)  # ID de conversa/thread no N8N

    # Imagens de referência (enviadas pelo usuário no modal)
    reference_images = JSONField(default=list)
    # Formato: [{"name": "foto.jpg", "s3_key": "org-1/posts/...", "s3_url": "https://..."}]

    # Imagem gerada
    has_image       = BooleanField(default=False)
    image_s3_key    = CharField(max_length=500, blank=True)
    image_s3_url    = URLField(max_length=1000, blank=True)
    image_width     = IntegerField(null=True, blank=True)
    image_height    = IntegerField(null=True, blank=True)
    generated_images = JSONField(default=list)   # array legado

    # FK para formato (opcional — derivado automaticamente se None)
    post_format     = ForeignKey('PostFormat', null=True, blank=True, on_delete=SET_NULL)

    # Status do ciclo de vida
    status = CharField(choices=[
        ('pending',          'Pendente de Aprovação'),
        ('generating',       'Agente Gerando Conteúdo'),
        ('image_generating', 'Agente Gerando Imagem'),
        ('image_ready',      'Imagem Disponível'),
        ('approved',         'Aprovado'),
        ('agent',            'Agente Alterando — Aguarde'),
        ('rejected',         'Rejeitado'),
    ])

    revisions_remaining = PositiveSmallIntegerField(default=2)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

### 2.3 `PostImage` — imagens geradas (múltiplas por post)

```python
class PostImage(models.Model):
    post      = ForeignKey(Post, on_delete=CASCADE, related_name='images')
    s3_key    = CharField(max_length=500, blank=True)
    s3_url    = URLField(max_length=1000, blank=True)
    width     = IntegerField(null=True, blank=True)
    height    = IntegerField(null=True, blank=True)
    order     = PositiveSmallIntegerField(default=0)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
```

### 2.4 `PostChangeRequest` — rastreamento de solicitações

```python
class PostChangeRequest(models.Model):
    class ChangeType(models.TextChoices):
        TEXT  = 'text',  'Texto'
        IMAGE = 'image', 'Imagem'

    post            = ForeignKey(Post, on_delete=CASCADE, related_name='change_requests')
    message         = TextField()
    requester_name  = CharField(max_length=160, blank=True)
    requester_email = EmailField(max_length=254, blank=True)
    change_type     = CharField(max_length=10, choices=ChangeType.choices)
    is_initial      = BooleanField(default=False)
    # is_initial=True → primeira solicitação (sem mensagem customizada)
    # is_initial=False → solicitação de ALTERAÇÃO (com mensagem do usuário)
    created_at      = DateTimeField(auto_now_add=True)
```

### 2.5 Relacionamentos entre models

```
Organization
    └── Post (FK organization)
            ├── PostFormat (FK post_format, null=True)
            ├── PostImage (FK post, related_name='images')
            └── PostChangeRequest (FK post, related_name='change_requests')

KnowledgeBase (FK organization)
    ├── Logo (FK kb, related_name='logos')
    ├── ReferenceImage (FK kb, related_name='reference_images')
    ├── ColorPalette (FK kb, related_name='colors')
    └── Typography (FK kb, related_name='typography_settings')
```

---

## 3. Migrations criadas

| Arquivo | O que faz |
|---|---|
| `posts/migrations/0009_add_postformat_model.py` | Cria a tabela `PostFormat` e adiciona FK `post_format` no model `Post` |
| `posts/migrations/0010_populate_postformat.py` | Migration de dados: popula 14 formatos padrão na tabela `PostFormat` |

---

## 4. URLs

```python
# app/apps/posts/urls.py

urlpatterns = [
    path('<int:post_id>/generate-image/', views_actions.generate_image,  name='generate_image'),
    path('webhook/n8n/',                  views_webhook.n8n_post_callback, name='n8n_post_callback'),
    path('reference/upload-url/',         views_upload.generate_reference_upload_url, name='reference_upload_url'),
    path('reference/create/',             views_upload.create_reference_image,         name='reference_create'),
]
```

---

## 5. View: `generate_image()` — disparo do fluxo

**Arquivo:** `app/apps/posts/views_actions.py`  
**Endpoint:** `POST /posts/<id>/generate-image/`  
**Autenticação:** `@login_required`

### 5.1 Etapas internas

**Etapa 1 — Busca e validação do post**
```python
post = Post.objects.select_related('organization', 'user')
             .prefetch_related('change_requests')
             .get(id=post_id, organization=request.organization)
```

**Etapa 2 — Verificação de limite de alterações**
- Conta `PostChangeRequest` do tipo `IMAGE` com `is_initial=False`
- Se já houver ≥ 1 alteração E a requisição tiver mensagem → retorna erro 400
- Limite atual: **1 alteração de imagem** por post

**Etapa 3 — Atualização de status**
```python
post.status = 'image_generating'
post.save(update_fields=['status', 'updated_at'])
```

**Etapa 4 — Criação de `PostChangeRequest`**
```python
PostChangeRequest.objects.create(
    post=post,
    message=message or 'Solicitação de geração de imagem',
    requester_name=requester_name,
    requester_email=requester_email,
    change_type=PostChangeRequest.ChangeType.IMAGE,
    is_initial=not bool(message),   # True se sem mensagem = solicitação inicial
)
```

**Etapa 5 — Envio de email de notificação**

| Situação | Função chamada | Template |
|---|---|---|
| `is_initial=True` (primeira vez) | `_notify_image_request_email()` | `emails/post_image_request.html` |
| `is_initial=False` (alteração) | `_notify_revision_request()` | `emails/post_change_request.html` |

- Destinatários: grupo `gestao` → `NOTIFICATION_EMAILS_GESTAO` no `.env`
- Prazo calculado: **6 horas úteis** (seg–sex, 09:00–17:00) via `_calculate_image_deadline()`
- Email não é enviado se `NOTIFICATION_EMAILS_GESTAO` estiver vazio

**Etapa 6 — Montagem do payload para N8N**

Ver seção 6.

---

## 6. Payload enviado ao N8N

**Enviado via:** `POST` para `settings.N8N_WEBHOOK_GERAR_IMAGEM`  
**Headers:**
```
Content-Type: application/json
X-Webhook-Secret: <N8N_WEBHOOK_SECRET>
```

**Corpo completo:**
```json
{
  "callback_url":              "https://suaapp.com.br/posts/webhook/n8n/",
  "post_id":                   42,
  "thread_id":                 "thread_abc123",
  "kb_id":                     "1",
  "s3_bucket":                 "vibemkt-femme-arquivos",
  "s3_pasta":                  "/org-1/imagensgeradas/",
  "quantidade":                1,

  "rede_social":               "instagram",
  "formato_px":                "1080x1350",
  "aspect_ratio":              "4:5",

  "publico_alvo":              "Mulheres 25-45 anos, classe B/C...",
  "titulo":                    "Título do post",
  "subtitulo":                 "Subtítulo do post",
  "cta":                       "Saiba mais",
  "prompt":                    "Descrição da imagem gerada pelo agente de texto",

  "marketing_input_summary":   "Resumo completo do briefing de marketing...",

  "paleta": [
    {"nome": "Rosa Principal", "hex": "#FF5C8D", "tipo": "primary"},
    {"nome": "Creme",          "hex": "#FFF5EE", "tipo": "secondary"}
  ],

  "tipografia": [
    {
      "uso":    "TITULO",
      "origem": "google",
      "nome":   "Montserrat",
      "peso":   "700",
      "url":    "https://fonts.googleapis.com/css2?family=Montserrat:wght@700"
    },
    {
      "uso":    "CORPO",
      "origem": "google",
      "nome":   "Open Sans",
      "peso":   "400",
      "url":    "https://fonts.googleapis.com/css2?family=Open+Sans"
    }
  ],

  "referencias": [
    {"tipo": "logotipo",  "url": "https://s3.amazonaws.com/org-1/logos/logo.png"},
    {"tipo": "referencia","url": "https://s3.amazonaws.com/org-1/referencias/img1.jpg"},
    {"tipo": "referencia","url": "https://s3.amazonaws.com/org-1/posts/ref-usuario.jpg"}
  ]
}
```

### 6.1 Origem de cada campo

| Campo | Origem |
|---|---|
| `callback_url` | `settings.APP_BASE_URL` + `reverse('posts:n8n_post_callback')` |
| `post_id` | `post.id` |
| `thread_id` | `post.thread_id` (vazio se nova solicitação — N8N cria e devolve) |
| `kb_id` | `KnowledgeBase.objects.filter(organization=post.organization).first().id` |
| `s3_bucket` | `settings.AWS_BUCKET_NAME` |
| `s3_pasta` | Montado dinamicamente: `/org-{org_id}/imagensgeradas/` |
| `quantidade` | `post.image_count` |
| `rede_social` | `post.social_network` |
| `formato_px` | Derivado de `PostFormat` pela combinação `rede_social + formato` (ver 6.2) |
| `aspect_ratio` | Derivado do mesmo `PostFormat` |
| `publico_alvo` | `kb.publico_externo` |
| `titulo` | `post.title` |
| `subtitulo` | `post.subtitle` |
| `cta` | `post.cta` |
| `prompt` | `post.image_prompt` (gerado pelo agente de texto na etapa anterior) |
| `marketing_input_summary` | `kb.n8n_compilation['marketing_input_summary']` |
| `paleta` | `kb.colors.all()` → `ColorPalette` |
| `tipografia` | `kb.typography_settings.all()` → `Typography` |
| `referencias[tipo=logotipo]` | `kb.logos.all()` → `Logo.s3_url` |
| `referencias[tipo=referencia]` (KB) | `kb.reference_images.all()` → `ReferenceImage.s3_url` |
| `referencias[tipo=referencia]` (post) | `post.reference_images` → JSONField com `s3_url` por item |

### 6.2 Lógica de resolução de `formato_px` e `aspect_ratio`

```python
FORMATO_MAP = {
    'feed':      ['Feed Retrato', 'Feed', 'Feed Quadrado', 'Imagem'],
    'stories':   ['Stories', 'Status'],
    'reels':     ['Reels', 'Vídeo/Reels', 'Stories'],
    'both':      ['Feed Retrato', 'Feed', 'Feed Quadrado', 'Imagem'],
    'story':     ['Stories', 'Status'],
    'carrossel': ['Feed Retrato', 'Feed', 'Feed Quadrado', 'Imagem'],
    'post':      ['Feed Retrato', 'Feed', 'Feed Quadrado', 'Imagem'],
}

# Prioridade 1: FK post.post_format (se preenchido manualmente)
# Prioridade 2: busca na tabela PostFormat por rede_social + formato do post
pf = post.post_format
if not pf:
    formato_post = post.formats[0] if post.formats else post.content_type
    for nome in FORMATO_MAP.get(formato_post, ['Feed', 'Feed Retrato']):
        pf = PostFormat.objects.filter(
            social_network=post.social_network,
            name=nome,
            is_active=True,
        ).first()
        if pf:
            break
```

**Exemplos de resultado:**
| Rede | Formato | `formato_px` | `aspect_ratio` |
|---|---|---|---|
| instagram | feed | 1080x1350 | 4:5 |
| instagram | stories | 1080x1920 | 9:16 |
| facebook | feed | 1200x630 | 16:9 |
| linkedin | feed | 1200x627 | 16:9 |
| whatsapp | feed | 1080x1080 | 1:1 |
| whatsapp | stories | 1080x1920 | 9:16 |

---

## 7. View: `n8n_post_callback()` — retorno do N8N

**Arquivo:** `app/apps/posts/views_webhook.py`  
**Endpoint:** `POST /posts/webhook/n8n/`  
**Autenticação:** `@csrf_exempt` (segurança feita manualmente em camadas)

### 7.1 Camadas de segurança

| Camada | Verificação | Código de erro |
|---|---|---|
| 1 | Header `X-INTERNAL-TOKEN` deve ser igual a `N8N_WEBHOOK_SECRET` | 401 |
| 2 | IP do cliente deve estar em `N8N_ALLOWED_IPS` (suporta Cloudflare via `HTTP_CF_CONNECTING_IP`) | 403 |
| 3 | Rate limit: máx `N8N_RATE_LIMIT_PER_IP` requests por minuto por IP (via Django cache) | 429 |
| 4 | Body deve ser JSON válido | 400 |
| 5 | `post_id` ou `thread_id` obrigatório no payload | 400 |
| 6 | Post deve existir no banco (busca por `post_id` ou `thread_id`) | 404 |

### 7.2 Payload esperado do N8N

```json
{
  "post_id":        42,
  "thread_id":      "thread_abc123",
  "status":         "pending",
  "titulo":         "Título gerado",
  "subtitulo":      "Subtítulo",
  "legenda":        "Legenda completa...",
  "hashtags":       ["#marca", "#produto"],
  "cta":            "Saiba mais",
  "descricaoImagem": "Prompt da imagem gerada",
  "imagens": [
    {
      "url":   "https://s3.amazonaws.com/bucket/org-1/imagensgeradas/imagem1.jpg",
      "s3_key": "org-1/imagensgeradas/imagem1.jpg"
    }
  ]
}
```

> **Nota:** O N8N pode enviar o payload como objeto `{}` ou como array `[{}]` — o webhook normaliza automaticamente.

> **Aliases aceitos:** `titulo`/`title`, `subtitulo`/`subtitle`, `legenda`/`caption`, `descricaoImagem`/`image_prompt`/`visual_brief`, `cta`/`cta_text`

### 7.3 Processamento das imagens

```python
# 1. Apaga todas as PostImage anteriores do post
PostImage.objects.filter(post=post).delete()

# 2. Cria uma PostImage para cada imagem recebida
for order, img in enumerate(imagens_processadas):
    url    = img.get('url', '')
    s3_key = img.get('s3_key', '')
    if not s3_key and url:
        s3_key = urlparse(url).path.lstrip('/')   # deriva da URL se não fornecido

    PostImage.objects.create(post=post, s3_url=url, s3_key=s3_key, order=order)

# 3. Atualiza campos principais do Post com a primeira imagem
post.image_s3_url = imagens_processadas[0]['url']
post.image_s3_key = imagens_processadas[0]['s3_key']
post.has_image    = True
```

### 7.4 Atualização do `thread_id`

- Se o N8N devolver `thread_id` e o post ainda não tiver → salva no `post.thread_id`
- Isso permite que solicitações futuras de alteração reabram o mesmo contexto no N8N

---

## 8. Upload de imagens de referência (frontend)

Antes de submeter o formulário "Gerar Post", o frontend faz o upload das imagens de referência para o S3.

**Arquivo:** `app/static/js/posts.js` — função `uploadReferencesToS3(files)`

### 8.1 Fluxo de upload (3 etapas)

**Etapa 1 — Obter Presigned URL**
```
POST /posts/reference/upload-url/
Body (form-urlencoded): fileName, fileType, fileSize
Resposta: { success: true, data: { upload_url, s3_key, organization_id } }
```

**Etapa 2 — Upload direto para S3 via PUT**
```
PUT <upload_url>
Headers: Content-Type, x-amz-server-side-encryption: AES256,
         x-amz-storage-class: INTELLIGENT_TIERING,
         x-amz-meta-original-name, x-amz-meta-organization-id,
         x-amz-meta-category: posts
Body: arquivo binário
```

**Etapa 3 — Confirmar upload**
```
POST /posts/reference/create/
Body (JSON): { s3Key, name }
Resposta: { success: true, data: { name, s3_key, s3_url, previewUrl } }
```

**Resultado salvo no payload do post:**
```json
"reference_images": [
  { "name": "foto.jpg", "s3_key": "org-1/posts/abc123.jpg", "s3_url": "https://..." }
]
```

### 8.2 Views de upload

**Arquivo:** `app/apps/posts/views_upload.py`

- `generate_reference_upload_url()` — gera Presigned URL via `S3Service`
- `create_reference_image()` — valida acesso à organização, retorna URL pública

---

## 9. Notificações por email

### 9.1 Solicitação inicial de imagem (`is_initial=True`)

**Função:** `_notify_image_request_email(post, request=None)`  
**Arquivo:** `app/apps/posts/utils.py`  
**Template:** `emails/post_image_request.html`  
**Assunto:** `🎨 Nova solicitação de imagem - Post #<id>`

**Contexto do template:**
```python
{
    'post':         post,
    'organization': post.organization,
    'post_url':     f"{SITE_URL}/admin/posts/post/{post.id}/change/",
    'requested_at': last_change_request.created_at,
    'deadline':     "DD/MM/YY às HH:MM",   # 6 horas úteis
}
```

### 9.2 Solicitação de alteração de imagem (`is_initial=False`)

**Função:** `_notify_revision_request(post, message, payload, user, request)`  
**Template:** `emails/post_change_request.html`  
**Assunto:** `🔄 Solicitação de alteração de imagem - Post #<id>`

**Contexto adicional:** `message`, `requester_name`

### 9.3 Cálculo do prazo de entrega

```python
def _calculate_image_deadline(requested_at):
    """
    Retorna datetime com 6 horas úteis após requested_at.
    Horário comercial: seg–sex, 09:00–17:00.
    Ignora fins de semana e horas fora do expediente.
    """
```

### 9.4 Configuração dos destinatários

```python
# apps/core/emails.py
recipient_emails = get_notification_emails('gestao')
# → lê NOTIFICATION_EMAILS_GESTAO do .env, retorna lista de emails
# → se vazio, email não é enviado (não lança erro)
```

---

## 10. Audit log

```python
def _post_audit(post, action, user, meta=None):
    logger.info(f'[AUDIT] Post {post.id} - Action: {action} - User: {user} - Meta: {meta}')
```

Ação registrada no fluxo Gerar Imagem: `'image_requested'`  
> TODO no código: implementar sistema de auditoria persistente se necessário.

---

## 11. Admin

### 11.1 `PostFormatAdmin`

```python
@admin.register(PostFormat)
class PostFormatAdmin(admin.ModelAdmin):
    list_display   = ['social_network', 'name', 'width', 'height', 'aspect_ratio', 'is_active', 'order']
    list_filter    = ['social_network', 'is_active']
    list_editable  = ['order', 'is_active']
```

Acessível em: `Admin → Posts → Formatos de Post`

### 11.2 `PostAdmin` (campos adicionados)

Campo `post_format` adicionado no fieldset **Imagem** do `PostAdmin`.

---

## 12. Response da view `generate_image()`

```json
{
  "success":          true,
  "id":               42,
  "serverId":         42,
  "status":           "image_generating",
  "statusLabel":      "Agente Gerando Imagem",
  "imageStatus":      "generating",
  "imageChanges":     0,
  "imageRequestedAt": "2026-02-20T19:00:00+00:00"
}
```

---

## 13. Tratamento de erros

| Situação | Resposta |
|---|---|
| Post não encontrado | `404 {"success": false, "error": "Post não encontrado"}` |
| Limite de alterações atingido | `400 {"success": false, "error": "Limite de solicitações de imagem atingido."}` |
| Timeout ao chamar N8N | Log de erro, retorna sucesso ao frontend (o registro já foi criado) |
| Erro de conexão com N8N | Idem — fluxo registrado mas N8N não acionado |
| Token inválido no callback | `401 Unauthorized` |
| IP não autorizado no callback | `403 Unauthorized IP` |
| Rate limit no callback | `429 Rate limit exceeded` |

---

## 14. Checklist para reimplementação em outra aplicação

- [ ] Criar model `PostFormat` com migration de dados (14 formatos)
- [ ] Adicionar FK `post_format` no model de post (null=True, blank=True)
- [ ] Adicionar campos no model de post: `thread_id`, `reference_images`, `has_image`, `image_s3_key`, `image_s3_url`, `image_prompt`, `post_format`
- [ ] Criar model `PostImage` (múltiplas imagens por post)
- [ ] Criar model `PostChangeRequest` com `change_type` e `is_initial`
- [ ] Configurar variáveis de ambiente: `N8N_WEBHOOK_GERAR_IMAGEM`, `N8N_WEBHOOK_SECRET`, `N8N_ALLOWED_IPS`, `APP_BASE_URL`, `AWS_BUCKET_NAME`
- [ ] Implementar view `generate_image()` com as 6 etapas descritas na seção 5
- [ ] Implementar webhook `n8n_post_callback()` com as 7 camadas de segurança
- [ ] Implementar views de upload S3 para imagens de referência
- [ ] Criar templates de email: `post_image_request.html` e `post_change_request.html`
- [ ] Configurar `NOTIFICATION_EMAILS_GESTAO` no `.env`
- [ ] Registrar models no admin
- [ ] Configurar no N8N: webhook de entrada (recebe payload da seção 6) + callback para `/posts/webhook/n8n/` com header `X-INTERNAL-TOKEN`

---

## 15. Arquivos modificados / criados no projeto

| Arquivo | Tipo | O que foi feito |
|---|---|---|
| `app/apps/posts/models.py` | Modificado | Adicionado `PostFormat` e FK `post_format` no `Post` |
| `app/apps/posts/migrations/0009_add_postformat_model.py` | Criado | Cria tabela `PostFormat` e FK no `Post` |
| `app/apps/posts/migrations/0010_populate_postformat.py` | Criado | Popula 14 formatos padrão |
| `app/apps/posts/views_actions.py` | Modificado | Implementada lógica completa de `generate_image()` com N8N |
| `app/apps/posts/views_webhook.py` | Modificado | Adaptado `n8n_post_callback()` para processar múltiplos `PostImage` |
| `app/apps/posts/views_upload.py` | Criado | Upload de imagens de referência via S3 Presigned URLs |
| `app/apps/posts/views_gerar.py` | Modificado | Filtro de `reference_images` vazios antes de salvar |
| `app/apps/posts/admin.py` | Modificado | Adicionado `PostFormatAdmin` e campo `post_format` no `PostAdmin` |
| `app/apps/posts/utils.py` | Existente | `_notify_image_request_email`, `_notify_revision_request`, `_calculate_image_deadline` |
| `app/static/js/posts.js` | Modificado | Adicionada função `uploadReferencesToS3()` chamada antes do submit |
| `app/sistema/settings/base.py` | Modificado | Adicionados `N8N_WEBHOOK_GERAR_IMAGEM` e `APP_BASE_URL` |
| `app/.env.example` | Modificado | Documentadas novas variáveis |
