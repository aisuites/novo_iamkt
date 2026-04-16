# Plano de Implementacao - Pipeline de Brandguide e Geracao

> Fases independentes, cada uma com rollback seguro.
> **Principio central:** o fluxo atual continua funcionando 100% em todos os pontos. Todas as adicoes sao opcionais.

---

## Status das Fases (atualizado 2026-04-16)

| Fase | Status | Branch | Tag |
|------|--------|--------|-----|
| 1 - Modelos + Intents | ✅ Concluida | `fase-1/modelo-e-intents` | `fim-fase-1` |
| 2 - Upload PDF + Conversao | ✅ Concluida | `fase-2/upload-pdf-e-conversao` | `fim-fase-2` |
| 3 - Analise IA + Brand Visual Spec | ✅ Concluida | `fase-3/analise-ia-pdf` | `fim-fase-3` |
| 4 - Brand Spec Inferido | Pendente | | |
| 5 - Marketing Summary | Pendente | | |
| 6 - Objetivo + Layout Planner | Pendente | | |
| 7 - Compose Engine | Pendente | | |
| 8 - A/B Testing | Pendente | | |

### Resultados validados em producao (Fase 3)

- PDF For Tomorrow (60 paginas) analisado com sucesso
- Custo total: ~$0.20 por brandguide (triagem $0.06 + analise $0.14)
- Tempo total (upload + conversao + analise): ~3-4 minutos
- Tokens rastreados e salvos em `BrandguideUpload.ai_usage`

### Pendencias e refinamentos (nao bloqueiam proximas fases)

#### P1 - Refinamento de prompts N8N (so N8N, zero deploy Django)

Ajustes no prompt de analise profunda para melhorar extracao:

1. **Cores de iniciativas com hex impreciso**
   - Problema: algumas cores HEX extraidas nao batem exatamente com os swatches
   - Melhoria: prompt deve pedir "extraia cores APENAS dos swatches oficiais da paleta,
     nao dos exemplos de aplicacao. Leia o HEX diretamente da imagem."
   - Cor faltante identificada: #FF0047 (vermelho/coral, canto inferior esquerdo da paleta)

2. **nome_empresa usando valor do existing_kb em vez do brandguide**
   - Problema: IA priorizou o nome existente na KB ("teste.uso@teste.uso")
   - Melhoria: prompt deve dizer "para nome_empresa, use o nome que aparece no
     BRANDGUIDE, ignorando o valor existente na KB"

3. **Grafismo - aplicacoes de layout nao capturadas**
   - Problema: paginas 31-37 (exemplos de grade com grafismo) nao foram descritas
   - Melhoria: expandir o brand_visual_spec.grafismo com `aplicacoes_layout`:
   ```json
   {
     "grafismo": {
       "origem": "...",
       "tipo": "...",
       "modulos": 8,
       "aplicacoes_layout": [
         {
           "formato": "feed_retangular",
           "grid": "2x3",
           "posicao_grafismo": "coluna direita, 2/3 da altura",
           "cor_grafismo": "cor de iniciativa sobre fundo preto",
           "exemplo_pagina": 34
         },
         {
           "formato": "quadrado",
           "grid": "2x2",
           "posicao_grafismo": "quadrante superior direito",
           "cor_grafismo": "preto sobre fundo branco",
           "exemplo_pagina": 36
         }
       ],
       "regras_aplicacao": [
         "Grafismo sempre ocupa uma area do grid, nunca sobrepoe texto",
         "Usar apenas 1 modulo por peca",
         "Cor do grafismo segue a cor de iniciativa escolhida"
       ]
     }
   }
   ```
   - Cabe no JSONField existente, sem migration

4. **Tipografia fallback**
   - Corrigido na ultima execucao: IBM Plex Sans agora e capturado
   - Monitorar para garantir consistencia

#### P2 - Extracao de assets visuais do PDF (Fase 7 - Compose Engine)

Implementar quando comecarmos a Fase 7:

1. **Extracao automatica com PyMuPDF**
   - Funcao no Celery que extrai objetos embutidos (vetores SVG, imagens PNG)
   - Classificacao por IA: grafismo vs logo vs foto/exemplo
   - Salvar como `BrandgraficModule` (modelo ja existe desde Fase 1)

2. **Upload manual de assets PNG**
   - Endpoint similar ao upload de logo
   - Interface no Bloco 5 para o usuario subir PNGs de grafismo
   - Criar registro `BrandgraficModule` com `extraction_type='manual_upload'`
   - Precisa adicionar 'manual_upload' nas choices do campo (migration simples)

3. **Link entre asset e padrao de aplicacao**
   - Associar cada `BrandgraficModule` ao `aplicacoes_layout` do brand_visual_spec
   - Compose Engine usa: spec diz "modulo 03 na coluna direita" + asset PNG do modulo 03

#### P3 - Melhorias de UX (ao longo das fases)

1. **Visualizacao do Brand Visual Spec para o usuario**
   - Hoje: JSON cru salvo no banco, usuario nao ve
   - Implementar: tela no perfil mostrando cores (swatches), fontes (previews),
     grid (diagrama), grafismos (thumbnails)
   - Fase sugerida: junto com Fase 4 ou 6

2. **Aprovacao granular do Brand Visual Spec**
   - Usuario valida cada secao (cores OK, tipografia OK, grid precisa ajuste)
   - Marca `brand_visual_spec_validated = True` quando tudo aprovado

---

## Estrategia de Seguranca

### Branches

```
main (producao - NUNCA tocamos direto)
  │
  └── feat/brandguide-pipeline (branch base do feature)
        │
        ├── fase-1/modelo-e-intents
        ├── fase-2/upload-pdf-e-conversao
        ├── fase-3/analise-ia-pdf
        ├── fase-4/brand-spec-inferido
        ├── fase-5/marketing-summary
        ├── fase-6/objetivo-post-e-layout-planner
        ├── fase-7/compose-engine
        └── fase-8/ab-testing-metricas
```

### Principio de rollback

- Toda alteracao em modelos existentes e aditiva (novos campos nullable)
- Toda nova funcionalidade vive em arquivos separados
- Integracoes com codigo existente usam `if/else` condicional:
  - `if kb.brand_visual_spec: novo_fluxo() else: fluxo_atual()`
- Em caso de falha, o sistema sempre cai para o comportamento atual

### Ordem recomendada de execucao

```
Fase 1 -> Fase 2 -> Fase 3 -> Fase 4 -> Fase 5 -> Fase 6 -> Fase 7 -> Fase 8
           │         │                                         │
           └─> APROVA ├─> Modo A comeca funcionar parcialmente │
                     └─> Modo A funciona completo <────────────┘
```

---

## FASE 1 - Modelos de Dados + Campos de Intent

### Objetivo
Criar estrutura de dados para receber as novas features, sem alterar nenhum comportamento atual.

### O que sera feito

**1.1 - Campos novos em modelos existentes (migration aditiva)**

```
Arquivo: app/apps/knowledge/models.py

KnowledgeBase (adicionar):
  - brand_visual_spec (JSONField, null=True)
  - brand_visual_spec_source (CharField, choices, null=True)
  - brand_visual_spec_confidence (CharField, null=True)
  - brand_visual_spec_validated (BooleanField, default=False)

  # NAO criamos marketing_summary - evoluimos o n8n_compilation existente
  # (ver Fase 5). Sem migration adicional para isso.

ReferenceImage (adicionar):
  - usage_description (TextField, blank=True)
  - aspects_to_use (JSONField, default=list)
  - importance (CharField, choices, default='medium')
  - usage_type (CharField, choices, default='inspire')
```

```
Arquivo: app/apps/posts/models.py

Post (adicionar):
  - objetivo (CharField, choices, default='institucional')
  - generation_method (CharField, choices, default='free_style')
  - layout_plan (JSONField, null=True)
  - image_brief (TextField, blank=True)
  - comparison_image_s3_url (URLField, blank=True)
  - comparison_image_s3_key (CharField, blank=True)

PostReferenceImage (adicionar):
  - usage_description (TextField, blank=True)
  - aspects_to_use (JSONField, default=list)
  - importance (CharField, default='medium')
  - usage_type (CharField, default='inspire')
```

**1.2 - Modelos novos**

```
Arquivo: app/apps/knowledge/models.py (adicionar ao final)

- BrandguideUpload
- BrandguidePage
- BrandgraficModule

Arquivo: app/apps/posts/models.py (adicionar ao final)

- PostGenerationMetric
```

**1.3 - Migration**

```
python manage.py makemigrations knowledge posts
python manage.py migrate
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `knowledge/models.py` | Adicionar campos + 3 modelos | ZERO (aditivo) |
| `posts/models.py` | Adicionar campos + 1 modelo | ZERO (aditivo) |
| Nova migration | Adicionar tabelas e colunas | ZERO (aditivo, tudo nullable) |

### Como testar

```bash
# Aplicar migration
python manage.py migrate

# Verificar no shell
python manage.py shell
>>> from apps.knowledge.models import BrandguideUpload, BrandguidePage, BrandgraficModule
>>> from apps.posts.models import PostGenerationMetric
>>> from apps.knowledge.models import KnowledgeBase, ReferenceImage
>>> kb = KnowledgeBase.objects.first()
>>> kb.brand_visual_spec  # deve retornar None
>>> ri = ReferenceImage.objects.first()
>>> ri.aspects_to_use  # deve retornar []
>>> ri.importance  # deve retornar 'medium'
>>> kb.brand_visual_spec  # deve retornar None
>>> kb.brand_visual_spec_validated  # deve retornar False

# Testar que nada quebrou
python manage.py test apps.knowledge apps.posts
```

### Rollback

```bash
python manage.py migrate knowledge 0019
python manage.py migrate posts 0013
git checkout main -- app/apps/knowledge/models.py
git checkout main -- app/apps/posts/models.py
```

### Criterio de aprovacao

- [ ] Migrations aplicadas sem erro
- [ ] Todos os testes existentes continuam passando
- [ ] Campos novos retornam valores default corretos
- [ ] Nenhuma funcionalidade atual foi afetada

---

## FASE 2 - Upload de PDF e Conversao

### Objetivo
Permitir upload opcional de PDF brandguide e converter em PNGs. Nenhum processamento de IA ainda.

### Dependencias
- Fase 1 aprovada
- Instalar: `pdf2image`, `PyMuPDF` (fitz), `pdfplumber`

### O que sera feito

**2.1 - Dependencias**

```
Arquivo: requirements.txt (adicionar)

pdf2image==1.17.0
PyMuPDF==1.24.0
pdfplumber==0.11.4
```

**2.2 - Settings**

```
Arquivo: app/sistema/settings/base.py (adicionar)

BRANDGUIDE_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
BRANDGUIDE_MAX_PAGES = 200
BRANDGUIDE_DPI = 200
```

**2.3 - Views de Upload**

```
Arquivo novo: app/apps/knowledge/views_brandguide.py

- generate_brandguide_upload_url(request)
- create_brandguide(request)  # dispara Celery task
- get_brandguide_status(request)
- delete_brandguide(request)
```

**2.4 - URLs**

```
Arquivo: app/apps/knowledge/urls.py (adicionar)

/brandguide/upload-url/   -> generate_brandguide_upload_url
/brandguide/create/       -> create_brandguide
/brandguide/status/       -> get_brandguide_status
/brandguide/<id>/delete/  -> delete_brandguide
```

**2.5 - Celery Task de Conversao**

```
Arquivo novo: app/apps/knowledge/tasks_brandguide.py

@shared_task(bind=True, max_retries=3)
def convert_brandguide_pdf_task(self, brandguide_id):
    """
    1. Baixa PDF do S3
    2. Converte paginas em PNG (200 DPI) com pdf2image
    3. Extrai assets embutidos com PyMuPDF
    4. Extrai texto auxiliar com pdfplumber
    5. Cria registros BrandguidePage
    6. Salva assets em S3 como candidatos
    7. Atualiza status para 'analyzing'
    8. Se Fase 3 ja implementada: dispara analyze_brandguide_task
    """
```

**2.6 - Interface de upload**

```
Arquivo novo: app/templates/knowledge/partials/brandguide_upload.html

- Dropzone para PDF
- Barra de progresso
- Status do processamento (polling)

Arquivo: app/templates/knowledge/view.html (adicionar include)

Dentro do Bloco 5 (Identidade Visual):
{% include 'knowledge/partials/brandguide_upload.html' %}
```

**2.7 - Dockerfile**

```
Arquivo: Dockerfile (verificar)

RUN apt-get install -y poppler-utils
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `requirements.txt` | Adicionar 3 libs | BAIXO |
| `knowledge/views_brandguide.py` | Arquivo NOVO | ZERO |
| `knowledge/tasks_brandguide.py` | Arquivo NOVO | ZERO |
| `knowledge/urls.py` | Adicionar 4 rotas | BAIXO |
| `sistema/settings/base.py` | Adicionar 3 constantes | ZERO |
| `templates/knowledge/partials/brandguide_upload.html` | Arquivo NOVO | ZERO |
| `templates/knowledge/view.html` | Adicionar include | BAIXO (aditivo) |
| `Dockerfile` | Garantir poppler | BAIXO |

### Como testar

```bash
# 1. Upload manual pela interface (ou curl)
# Usar o PDF For Tomorrow como teste

# 2. Verificar conversao
python manage.py shell
>>> from apps.knowledge.models import BrandguideUpload, BrandguidePage
>>> bg = BrandguideUpload.objects.last()
>>> bg.processing_status  # deve estar 'analyzing' (apos task)
>>> bg.pages.count()  # deve ser 60 (ou total real)
>>> page = bg.pages.first()
>>> page.s3_url  # abrir no browser para verificar qualidade

# 3. Verificar extracao de assets
>>> from apps.knowledge.models import BrandgraficModule
>>> # Assets ainda nao aprovados pelo usuario
>>> candidates = BrandgraficModule.objects.filter(
...     knowledge_base=bg.knowledge_base,
...     approved_by_user=False
... )
>>> candidates.count()
```

### Rollback

```bash
rm app/apps/knowledge/views_brandguide.py
rm app/apps/knowledge/tasks_brandguide.py
rm app/templates/knowledge/partials/brandguide_upload.html
git checkout main -- app/apps/knowledge/urls.py
git checkout main -- app/templates/knowledge/view.html
# Remover libs do requirements.txt
# Nenhum dado persistido e usado por outras features, pode deletar registros
```

### Criterio de aprovacao

- [ ] Upload de PDF funciona pela interface
- [ ] PNGs gerados com qualidade visual adequada
- [ ] Assets embutidos extraidos corretamente
- [ ] Status do processamento atualiza em tempo real
- [ ] Polling na interface funciona
- [ ] Task assincrona nao bloqueia request
- [ ] Tempo de processamento aceitavel (< 2 min para 60 paginas)

---

## FASE 3 - Analise IA do PDF + Brand Visual Spec

### Objetivo
Enviar PDF processado para N8N, receber analise conjunta texto+visual, preencher sugestoes na KB e gerar Brand Visual Spec.

### Dependencias
- Fase 2 aprovada
- Workflow N8N configurado: `N8N_WEBHOOK_ANALYZE_BRANDGUIDE`

### O que sera feito

**3.1 - Settings**

```
Arquivo: app/sistema/settings/base.py (adicionar)

N8N_WEBHOOK_ANALYZE_BRANDGUIDE = env('N8N_WEBHOOK_ANALYZE_BRANDGUIDE', default='')
```

**3.2 - Task de envio para N8N**

```
Arquivo: app/apps/knowledge/tasks_brandguide.py (adicionar)

@shared_task(bind=True, max_retries=2)
def analyze_brandguide_task(self, brandguide_id):
    """
    1. Carrega BrandguideUpload + BrandguidePages
    2. Monta payload (URLs das paginas + texto auxiliar + assets candidatos)
    3. POST para N8N_WEBHOOK_ANALYZE_BRANDGUIDE
    4. N8N processa (triagem + analise profunda) e chama callback
    """
```

**3.3 - Webhook de callback**

```
Arquivo: app/apps/knowledge/views_brandguide.py (adicionar)

@csrf_exempt
@require_POST
def brandguide_analysis_callback(request):
    """
    Recebe:
    - page_classifications (categoria de cada pagina)
    - suggested_kb_fields (campos para preenchimento)
    - brand_visual_spec (JSON completo)
    - approved_grafismos (IDs de grafismos validados)

    Processa:
    1. Valida token X-INTERNAL-TOKEN
    2. Valida IP (N8N_ALLOWED_IPS)
    3. Atualiza categorias nas BrandguidePages
    4. Salva suggested_kb_fields em kb.n8n_analysis (reusa campo)
    5. Salva brand_visual_spec em kb.brand_visual_spec
    6. Marca spec com source='brandguide_pdf', confidence='high'
    7. Atualiza BrandguideUpload status para 'completed'
    """
```

**3.4 - URL do callback**

```
Arquivo: app/apps/knowledge/urls.py (adicionar)

/webhook/brandguide/  -> brandguide_analysis_callback
```

**3.5 - Interface de aprovacao**

Adicionar secao no `perfil_view` ja existente para mostrar:
- Campos sugeridos da KB (ja existe, adaptar)
- Brand Visual Spec em formato visual (cores com swatches, fontes com previews)
- Grafismos extraidos com checkbox de aprovacao

```
Arquivo: app/templates/knowledge/perfil.html (adicionar secao)
Arquivo novo: app/templates/knowledge/partials/brand_visual_spec_review.html
Arquivo novo: app/templates/knowledge/partials/grafismos_approval.html
```

**3.6 - View de aprovacao de grafismos**

```
Arquivo: app/apps/knowledge/views_brandguide.py (adicionar)

def approve_grafismos(request):
    """Recebe lista de IDs aprovados, marca BrandgraficModule.approved_by_user=True"""
```

### Fluxo N8N (referencia)

```
Trigger: webhook recebe POST do IAMKT
  │
  ├── Fase A: Triagem (GPT-4.1-mini, low detail)
  │   Classifica paginas por categoria
  │
  ├── Fase B: Analise KB (GPT-4o Vision, high detail)
  │   Paginas relevantes -> campos da KB
  │
  ├── Fase C: Brand Visual Spec (GPT-4o Vision)
  │   Paginas visuais -> spec completo
  │
  └── Fase D: Classificacao de assets extraidos
      Recebe URLs dos assets -> classifica como grafismo/logo/descarte
      -> Retorna lista de grafismos validos

Callback: POST /knowledge/webhook/brandguide/
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `sistema/settings/base.py` | Adicionar 1 variavel | ZERO |
| `knowledge/tasks_brandguide.py` | Adicionar 1 task | ZERO |
| `knowledge/views_brandguide.py` | Adicionar 2 views | ZERO |
| `knowledge/urls.py` | Adicionar 2 rotas | BAIXO |
| `templates/knowledge/perfil.html` | Adicionar secao | BAIXO (aditivo) |
| `templates/knowledge/partials/*.html` | Arquivos NOVOS | ZERO |

### Como testar

```bash
# 1. Simular callback do N8N
curl -X POST http://localhost:8000/knowledge/webhook/brandguide/ \
  -H "X-INTERNAL-TOKEN: $N8N_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": 1,
    "brandguide_id": 1,
    "status": "completed",
    "page_classifications": [...],
    "suggested_kb_fields": {...},
    "brand_visual_spec": {...}
  }'

# 2. Verificar dados
>>> kb = KnowledgeBase.objects.get(id=1)
>>> kb.brand_visual_spec  # JSON populado
>>> kb.brand_visual_spec_source  # 'brandguide_pdf'
>>> kb.brand_visual_spec_confidence  # 'high'
```

### Rollback

```bash
# Remover arquivos e rotas novas
# Campo brand_visual_spec da Fase 1 permanece mas fica unused
# Nenhuma feature existente foi alterada
```

### Criterio de aprovacao

- [ ] Payload enviado para N8N corretamente
- [ ] Callback processa resposta sem erros
- [ ] Validacao de token e IP funciona
- [ ] KB preenchida com sugestoes
- [ ] Brand Visual Spec salvo
- [ ] Grafismos candidatos disponiveis para aprovacao
- [ ] Interface permite aprovar/rejeitar spec e grafismos
- [ ] Fluxo sem PDF continua funcionando identicamente

---

## FASE 4 - Templates Visuais, Assets e Brand Visual Spec Inferido

### Objetivo

Permitir que o usuario gerencie **templates visuais** (artes prontas como modelo) e
**assets** (grafismos isolados), e gerar Brand Visual Spec inferido para clientes sem PDF.

### Conceitos

```
TEMPLATE VISUAL: arte pronta usada como modelo para geracao de posts.
  Ex: layout do brandguide com grid + grafismo + texto posicionados.
  Uso: a IA recebe o template e SEGUE a estrutura fielmente.

ASSET (grafismo): elemento visual isolado com transparencia.
  Ex: modulo geometrico extraido do brandguide.
  Uso: overlay no Compose Engine ou referencia para a IA.

REFERENCIA: imagem de inspiracao generica (mood, estilo).
  Ex: imagem que o usuario sobe como moodboard.
  Uso: quando NAO tem template/asset definido (fluxo atual).
```

### Hierarquia de envio ao agente de IA (ao gerar post)

```
SE tem templates:
  → Usuario escolhe 1 template no modal "Gerar Post"
  → Envia: template escolhido + assets vinculados ao template
  → IA segue o modelo, usa os assets como referencia visual
  → NÃO envia imagens de referencia (template tem prioridade)

SE NAO tem templates mas tem assets:
  → Envia: assets + brand_visual_spec
  → IA usa grafismos nas regras do spec

SE NAO tem nada disso:
  → Envia: imagens de referencia da KB (fluxo atual preservado)
  → IA se inspira nas referencias
```

### Como templates e assets chegam ao sistema

```
CAMINHO 1 - Upload manual (prioridade)
  Usuario sobe:
    - PNGs/JPGs de templates (artes prontas)
    - PNGs/SVGs de assets (grafismos isolados com transparencia)
  → Resultado melhor pois sao arquivos originais de alta qualidade

CAMINHO 2 - Extracao do PDF (complementar, inteligente)
  SE usuario ja subiu templates manualmente → NAO extrai templates do PDF
  SE usuario ja subiu assets manualmente → NAO extrai assets do PDF
  SO extrai do PDF o que ficou FALTANDO:
    - Sem templates manuais? → Extrai paginas de "aplicacoes" como candidatos
    - Sem assets manuais? → Extrai objetos embutidos (SVG/PNG) como candidatos
  → Usuario revisa e aprova qualidade

CAMINHO 3 - Nenhum dos dois
  → Area fica vazia, fluxo normal com imagens de referencia
```

### Presenca nas 3 paginas

```
/knowledge/ (Bloco 5 - primeira etapa):
  - Upload de templates (drag & drop ou selecionar arquivo)
  - Upload de assets (drag & drop ou selecionar arquivo)
  - Lista/grid de templates e assets ja subidos com preview + botao remover
  - Se fez upload de PDF, mostra aviso: "templates e assets serao extraidos automaticamente
    para os itens que voce nao subiu manualmente"

/knowledge/perfil/ (segunda etapa - com sugestoes):
  - Templates extraidos do PDF (se houver) para aprovar/rejeitar
  - Assets extraidos do PDF para aprovar/rejeitar
  - Templates e assets manuais listados (ja aprovados)
  - Secao no Bloco 5 (Identidade Visual) apos imagens de referencia

/knowledge/perfil-visualizacao/ (terceira etapa - read-only):
  - Grid de thumbnails dos templates aprovados
  - Grid de thumbnails dos assets aprovados
  - Se nao tem nenhum: secao nao aparece (area vazia)
```

### O que sera feito

**4.1 - Modelo VisualTemplate (novo)**

```python
class VisualTemplate(models.Model):
    knowledge_base = ForeignKey(KnowledgeBase, related_name='visual_templates')
    name = CharField(max_length=200)
    template_type = CharField(choices=[
        ('feed', 'Feed'),
        ('story', 'Story'),
        ('quadrado', 'Quadrado'),
        ('carrossel_slide', 'Slide de Carrossel'),
        ('outro', 'Outro'),
    ])
    social_network = CharField(choices=[
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('twitter', 'Twitter/X'),
        ('whatsapp', 'WhatsApp'),
        ('universal', 'Universal (qualquer rede)'),
    ], default='universal')
    s3_key = CharField(max_length=500)
    s3_url = URLField(max_length=1000)
    width = PositiveIntegerField(default=0)
    height = PositiveIntegerField(default=0)
    source = CharField(choices=[
        ('manual_upload', 'Upload manual'),
        ('pdf_extracted', 'Extraido do PDF'),
    ])
    source_page = PositiveIntegerField(null=True, blank=True)
    # Assets vinculados a este template
    assets = ManyToManyField('BrandgraficModule', blank=True, related_name='templates')
    description = TextField(blank=True)
    approved_by_user = BooleanField(default=False)
    is_active = BooleanField(default=True)
    uploaded_by = ForeignKey(User, null=True, on_delete=SET_NULL)
    created_at = DateTimeField(auto_now_add=True)
```

**Nota:** `BrandgraficModule` ja existe desde Fase 1. Precisa adicionar `manual_upload`
ao choices de `extraction_type` (migration simples).

**4.2 - Migration**

```
python manage.py makemigrations knowledge
# Cria: VisualTemplate + altera BrandgraficModule.extraction_type choices
```

**4.3 - Settings**

```
N8N_WEBHOOK_INFER_VISUAL_SPEC = config('N8N_WEBHOOK_INFER_VISUAL_SPEC', default='')
```

**4.4 - Views de upload de templates e assets**

```
Arquivo: app/apps/knowledge/views_brandguide.py (adicionar)

- generate_template_upload_url(request)    # presigned URL para upload de template
- create_visual_template(request)          # confirma upload e cria registro
- delete_visual_template(request, id)      # deleta template + S3

- generate_asset_upload_url(request)       # presigned URL para upload de asset
- create_brandgrafic_module(request)       # confirma upload e cria registro (manual)
- delete_brandgrafic_module(request, id)   # deleta asset + S3
```

**4.5 - URLs**

```
/knowledge/template/upload-url/      -> generate_template_upload_url
/knowledge/template/create/          -> create_visual_template
/knowledge/template/<id>/delete/     -> delete_visual_template
/knowledge/asset/upload-url/         -> generate_asset_upload_url
/knowledge/asset/create/             -> create_brandgrafic_module
/knowledge/asset/<id>/delete/        -> delete_brandgrafic_module
```

**4.6 - Interface no Bloco 5 (/knowledge/)**

```
Arquivo novo: app/templates/knowledge/partials/templates_upload.html

Secao apos "Imagens de referencia" e "Brandguide da marca":
- "Templates visuais (opcional)"
  - Dropzone para upload de PNG/JPG
  - Grid de templates ja subidos com preview + remover
- "Assets de grafismo (opcional)"
  - Dropzone para upload de PNG/SVG
  - Grid de assets ja subidos com preview + remover

Arquivo: app/templates/knowledge/view.html (adicionar include no Bloco 5)
```

**4.7 - Interface no Perfil (/knowledge/perfil/)**

```
Arquivo: app/templates/knowledge/perfil.html (adicionar secao)

No Bloco 5 (Identidade Visual):
- Secao "Templates visuais"
  - Templates manuais: grid com thumbnails (ja aprovados)
  - Templates extraidos do PDF: grid com approve/reject
- Secao "Assets de grafismo"
  - Assets manuais: grid com thumbnails (ja aprovados)
  - Assets extraidos do PDF: grid com approve/reject
```

**4.8 - Interface no Perfil Visualizacao (/knowledge/perfil-visualizacao/)**

```
Arquivo: app/templates/knowledge/partials/perfil_visualizacao_linha2.html (adaptar)

Adicionar apos Logos e Imagens de Referencia:
- "Templates visuais" - grid de thumbnails (read-only)
- "Assets de grafismo" - grid de thumbnails (read-only)
- Se nao tem nenhum: secao nao renderiza
```

**4.9 - Logica inteligente de extracao do PDF**

```
Arquivo: app/apps/knowledge/tasks.py (adaptar finalize_brandguide_task)

Apos conversao do PDF, antes de disparar analise IA:
1. Contar templates manuais: VisualTemplate.objects.filter(kb=kb, source='manual_upload').count()
2. Contar assets manuais: BrandgraficModule.objects.filter(kb=kb, extraction_type='manual_upload').count()
3. Informar ao N8N no payload:
   - has_manual_templates: bool
   - has_manual_assets: bool
4. N8N decide: se ja tem manuais, NAO extrai do PDF. So extrai o que falta.
```

**4.10 - Task de inferencia do Brand Visual Spec (sem PDF)**

```
Arquivo: app/apps/knowledge/tasks.py (adicionar)

@shared_task(queue='brandguide')
def infer_visual_spec_task(knowledge_base_id):
    """
    Para clientes SEM PDF: gera Brand Visual Spec inferido a partir de:
    - Imagens de referencia (com intent)
    - Templates visuais (se houver)
    - Assets (se houver)
    - Cores cadastradas (ColorPalette)
    - Fontes cadastradas (Typography/CustomFont)
    Envia para N8N_WEBHOOK_INFER_VISUAL_SPEC
    Callback reusa /knowledge/webhook/brandguide/ com source='reference_images'
    """
```

**4.11 - Validacao de categorias no FileValidator**

```
Arquivo: app/apps/core/utils/file_validators.py (adicionar)

'templates': {
    'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
}  # max 10 MB

'assets': {
    'image/png': 'png', 'image/svg+xml': 'svg',
}  # max 5 MB (transparencia obrigatoria para PNG)
```

**4.12 - S3 paths**

```
Arquivo: app/apps/core/services/s3_service.py (adicionar templates)

'templates': 'org-{org_id}/templates/{timestamp}-{random}-{name}.{ext}'
'assets': 'org-{org_id}/assets/{timestamp}-{random}-{name}.{ext}'
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `knowledge/models.py` | Novo modelo VisualTemplate + alterar BrandgraficModule choices | BAIXO (aditivo) |
| Migration nova | Criar tabela + alterar choices | ZERO |
| `sistema/settings/base.py` | Adicionar 1 variavel | ZERO |
| `core/utils/file_validators.py` | Adicionar 2 categorias | ZERO |
| `core/services/s3_service.py` | Adicionar 2 path templates | ZERO |
| `knowledge/views_brandguide.py` | Adicionar 6 views (upload CRUD) | ZERO |
| `knowledge/urls.py` | Adicionar 6 rotas | BAIXO |
| `knowledge/tasks.py` | Adicionar infer task + adaptar extracao | BAIXO |
| `templates/knowledge/partials/templates_upload.html` | Arquivo NOVO | ZERO |
| `templates/knowledge/view.html` | Include no Bloco 5 | BAIXO (aditivo) |
| `templates/knowledge/perfil.html` | Secao de templates/assets | BAIXO (aditivo) |
| `templates/knowledge/partials/perfil_visualizacao_linha2.html` | Grid read-only | BAIXO |
| JS novo para upload de templates/assets | Arquivo NOVO | ZERO |

### Rollback

```bash
# Reverter migration: python manage.py migrate knowledge <migration_anterior>
# Remover views, URLs e templates novos
# Fluxo atual de imagens de referencia continua funcionando intacto
```

### Criterio de aprovacao

- [ ] Upload manual de templates funciona (presigned URL + create)
- [ ] Upload manual de assets funciona
- [ ] Templates aparecem no Bloco 5 da /knowledge/
- [ ] Templates aparecem no /knowledge/perfil/ (aprovacao)
- [ ] Templates aparecem no /knowledge/perfil-visualizacao/ (read-only)
- [ ] Se nao tem templates: area vazia, sem erro
- [ ] Assets seguem mesma logica
- [ ] Brand Visual Spec inferido funciona para KB sem PDF
- [ ] Extracao do PDF nao extrai templates se ja tem upload manual
- [ ] Extracao do PDF nao extrai assets se ja tem upload manual
- [ ] Fluxo atual (sem templates, sem assets) nao foi afetado
- [ ] Interface exibe aviso de validacao necessaria

---

## FASE 5 - Evolucao do Marketing Input Summary

### Objetivo
Evoluir o `n8n_compilation.marketing_input_summary` (que ja existe como texto livre) adicionando um sub-bloco estruturado `marketing_input_structured`, para que agentes novos possam consumir secoes especificas sem precisar do texto inteiro.

### Contexto

A aplicacao ja tem hoje:
- Campo `kb.n8n_compilation` (JSONField)
- Subcampo `kb.n8n_compilation['marketing_input_summary']` (texto livre)
- Workflow N8N de compilation ja existe e gera isso
- Pautas e posts atuais ja consomem esse texto

**Nao vamos criar campo novo nem duplicar logica.** Vamos apenas evoluir o JSON existente.

### Dependencias
- Fase 1 aprovada (campos do Brand Visual Spec existem)
- Workflow N8N de compilation atualizado para gerar tambem o bloco estruturado

### O que sera feito

**5.1 - Atualizar workflow N8N existente (externo ao Django)**

O workflow de compilation atualmente gera:
```json
{
  "marketing_input_summary": "texto livre...",
  "four_week_marketing_plan": {...},
  "assessment_summary": "...",
  "improvements_summary": "..."
}
```

Passa a gerar tambem:
```json
{
  "marketing_input_summary": "texto livre...",         // MANTIDO
  "marketing_input_structured": {                      // NOVO
    "versao": "1.0",
    "essencia_marca": {...},
    "posicionamento_curto": "...",
    "tom_voz_regras": {...},
    "visual_direction_resumo": {...},
    // ... demais secoes
  },
  "four_week_marketing_plan": {...},
  "assessment_summary": "...",
  "improvements_summary": "..."
}
```

**5.2 - Callback existente continua funcionando**

O webhook que recebe o resultado de compilation (ja existe em `knowledge/views_n8n.py::n8n_compilation_webhook`) nao precisa mudar - ele apenas salva o JSON completo no campo `n8n_compilation`. O bloco novo entra automaticamente.

Verificar apenas que nao ha validacao estrita que rejeite campos novos no JSON.

**5.3 - Helpers para acesso estruturado**

```
Arquivo novo: app/apps/knowledge/helpers_compilation.py

def get_structured_summary(kb) -> dict:
    """
    Retorna o marketing_input_structured se existe,
    ou dict vazio caso contrario (para novos agentes).
    """
    return (kb.n8n_compilation or {}).get('marketing_input_structured', {})

def get_summary_text(kb) -> str:
    """
    Retorna o marketing_input_summary (texto) se existe,
    ou string vazia (para agentes antigos).
    Ja e o que e usado hoje - encapsula o acesso.
    """
    return (kb.n8n_compilation or {}).get('marketing_input_summary', '')

def get_visual_direction(kb) -> dict:
    """
    Atalho para o bloco visual_direction_resumo do structured.
    Usado pelo Layout Planner e Compose Engine.
    """
    return get_structured_summary(kb).get('visual_direction_resumo', {})
```

**5.4 - Usar nos agentes novos**

Os agentes novos (Layout Planner na Fase 6, Compose Engine na Fase 7) usam os helpers para acessar apenas o bloco estruturado. Agentes antigos continuam com o texto via `get_summary_text()` ou acesso direto ao campo.

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `knowledge/helpers_compilation.py` | Arquivo NOVO (so helpers) | ZERO |
| Workflow N8N externo | Atualizar para gerar bloco novo | ZERO no Django |

**Nenhum campo criado. Nenhuma migration. Nenhum webhook novo. Nenhuma task nova.**

O trabalho e essencialmente:
1. Configurar o workflow N8N para gerar o bloco estruturado
2. Criar helpers de acesso
3. Garantir que o callback existente aceita o JSON expandido

### Como testar

```bash
# 1. Forcar geracao de compilation com novo formato
# (Ou mockar manualmente no shell)
python manage.py shell
>>> kb = KnowledgeBase.objects.get(id=1)
>>> kb.n8n_compilation = {
...   'marketing_input_summary': 'texto atual mantido...',
...   'marketing_input_structured': {
...     'essencia_marca': {'uma_frase': 'Teste'},
...     'visual_direction_resumo': {'mood': 'minimalista'}
...   }
... }
>>> kb.save()

# 2. Verificar helpers
>>> from apps.knowledge.helpers_compilation import get_structured_summary, get_summary_text, get_visual_direction
>>> get_summary_text(kb)          # 'texto atual mantido...'
>>> get_structured_summary(kb)     # dict completo
>>> get_visual_direction(kb)       # {'mood': 'minimalista'}

# 3. Verificar que agentes antigos nao quebraram
#    Criar um post -> payload deve conter marketing_input_summary em texto
#    Gerar uma pauta -> mesma validacao
```

### Rollback

```bash
# Remover arquivo de helpers
rm app/apps/knowledge/helpers_compilation.py

# Reverter workflow N8N para nao gerar o bloco estruturado
# (se ja foi atualizado)

# Dados ja salvos no n8n_compilation continuam no banco mas nao sao lidos
# Nenhuma feature atual e afetada
```

### Criterio de aprovacao

- [ ] N8N gera o bloco `marketing_input_structured` dentro do `n8n_compilation`
- [ ] Callback existente aceita o JSON expandido sem rejeitar
- [ ] Texto `marketing_input_summary` continua sendo gerado (nao foi removido)
- [ ] Helpers retornam dados corretos
- [ ] Helpers retornam valores vazios seguros quando bloco nao existe ainda
- [ ] Pautas e posts atuais continuam funcionando identicamente
- [ ] Nenhuma migration foi criada

---

## FASE 6 - Objetivo do Post + Layout Planner

### Objetivo
Permitir usuario escolher objetivo do post. Quando existe Brand Visual Spec, agente Layout Planner decide template.

### Dependencias
- Fase 1 aprovada (campos objetivo, generation_method, layout_plan existem)
- Workflow N8N atualizado para incluir Layout Planner

### O que sera feito

**6.1 - Formulario de post expandido**

```
Arquivo: app/apps/posts/views_gerar.py (adaptar gerar_post)

Aceitar campos novos no POST:
  - objetivo
  - generation_method
  - referencias com intent (usage_description, aspects_to_use, etc)

Arquivo: app/templates/posts/*.html (adaptar modal de geracao)

Adicionar:
  - Select de objetivo
  - Radio de generation_method (so aparece se kb tem brand_visual_spec)
  - Form expandido nas referencias anexadas
```

**6.2 - Logica de selecao de modo**

```
Arquivo: app/apps/posts/views_gerar.py

def gerar_post(request):
    # ... codigo existente ...

    # NOVO: decide se usa Layout Planner
    use_layout_planner = (
        kb.brand_visual_spec
        and post.generation_method in ('controlled_render', 'both')
    )

    payload = {
        # ... payload atual ...
        'objetivo': post.objetivo,
        'generation_method': post.generation_method,
        'use_layout_planner': use_layout_planner,
        'brand_visual_spec': kb.brand_visual_spec if use_layout_planner else None,
        'marketing_input_summary': get_summary_text(kb),       # texto (agentes antigos)
        'marketing_input_structured': get_structured_summary(kb), # estruturado (agentes novos)
    }

    # Envio para N8N (mesma URL atual)
    send_to_n8n(payload)
```

**6.3 - Workflow N8N**

N8N recebe o flag `use_layout_planner`. Se `true`, adiciona etapa antes do copywriter:

```
N8N Post Generation Flow:
  │
  ├── IF use_layout_planner:
  │     Agente Layout Planner (GPT-4o)
  │       Input: objetivo + Brand Visual Spec + formato
  │       Output: layout_plan (JSON com areas e restricoes)
  │
  ├── Agente Copywriter (GPT-4o)
  │     Input: tema + KB + marketing_input_structured + layout_plan (se houver)
  │     Output: titulo, subtitulo, legenda, hashtags, CTA, image_brief
  │
  └── Callback para IAMKT
      Payload inclui layout_plan (se gerado)
```

**6.4 - Callback do post (adaptar existente)**

```
Arquivo: app/apps/posts/views_webhook.py (adaptar n8n_post_callback)

Aceitar campos novos no payload:
  - layout_plan (salvar em post.layout_plan)
  - image_brief (salvar em post.image_brief)

Codigo existente continua funcionando para payloads antigos.
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `posts/views_gerar.py` | Adicionar campos + logica de modo | MEDIO (modifica fluxo atual, precisa testes) |
| `posts/views_webhook.py` | Aceitar campos novos | BAIXO (aditivo) |
| `templates/posts/*.html` | Expandir formulario | BAIXO |

### Como testar

```bash
# 1. Cliente SEM brand_visual_spec
#    Solicitar post com objetivo='evento'
#    Verificar: payload vai sem layout_plan, fluxo atual se mantem

# 2. Cliente COM brand_visual_spec + generation_method='controlled_render'
#    Solicitar post
#    Verificar: payload vai com use_layout_planner=true
#    N8N retorna com layout_plan populado
#    Post tem layout_plan salvo

# 3. Cliente COM brand_visual_spec + generation_method='free_style'
#    Verificar: payload vai sem layout_plan (usuario escolheu free style)
```

### Rollback

```bash
# Reverter views_gerar.py para versao sem logica de modo
# Campos objetivo/generation_method permanecem no modelo mas nao sao usados
# Fluxo atual nao e afetado
```

### Criterio de aprovacao

- [ ] Campo objetivo aparece no formulario
- [ ] Campo generation_method aparece so quando KB tem spec
- [ ] Fluxo sem spec funciona identico ao atual
- [ ] Fluxo com spec inclui layout_plan no post
- [ ] Callback processa corretamente ambos os casos
- [ ] Revisoes de texto ainda funcionam (decrementa revisions_remaining)

---

## FASE 7 - Compose Engine (Renderizacao Programatica)

### Objetivo
Quando post tem layout_plan e Gemini gera imagem raw, renderizar peca final com Pillow.

### Dependencias
- Fase 6 aprovada
- Workflow N8N gera imagem raw (sem texto/logo) quando generation_method='controlled_render'

### O que sera feito

**7.1 - Font Resolver**

```
Arquivo novo: app/apps/posts/font_resolver.py

class FontResolver:
    def resolve(typography_config) -> str:
        """
        Retorna path local do TTF.

        Se source='upload':
          Baixa do S3 (CustomFont) -> /tmp/fonts/
        Se source='google':
          Verifica cache local em /var/lib/fonts/
          Se nao existe: baixa via Google Fonts API
          Cacheia
          Retorna path
        """
```

**7.2 - Compose Engine**

```
Arquivo novo: app/apps/posts/compose_engine.py

class PostComposer:
    def __init__(self, post):
        self.post = post
        self.kb = post.organization.knowledge_base
        self.spec = self.kb.brand_visual_spec
        self.plan = post.layout_plan

    def compose(self) -> bytes:
        """
        1. load_brand_assets()    - baixa fontes, logos, grafismos
        2. create_canvas()         - Pillow canvas no tamanho do formato
        3. apply_background()      - cor de fundo do layout_plan
        4. place_image()           - imagem raw do Gemini na area definida
        5. apply_grafismo()        - overlay de grafismo (se aplicavel)
        6. render_texts()          - titulo, subtitulo, CTA com fonte real
        7. place_logo()            - logo com area de seguranca
        8. return png_bytes
        """
```

**7.3 - Task de composicao**

```
Arquivo novo: app/apps/posts/tasks_compose.py

@shared_task(bind=True, max_retries=2)
def compose_post_image_task(self, post_id):
    """
    1. Carrega Post + verifica tem layout_plan + imagem raw
    2. Instancia PostComposer
    3. compose() -> bytes PNG
    4. Upload para S3
    5. Atualiza post.image_s3_url / image_s3_key
    6. Status -> 'image_ready'

    Fallback: se falhar, mantem imagem raw original (nao deixa usuario sem nada)
    """
```

**7.4 - Integracao no callback do post (PONTO CRITICO)**

```
Arquivo: app/apps/posts/views_webhook.py (modificar n8n_post_callback)

ANTES (linha ja existente):
    post.image_s3_url = imagem_do_gemini  # comportamento atual

DEPOIS (logica condicional):
    if post.layout_plan and post.generation_method in ('controlled_render', 'both'):
        # Imagem do Gemini e RAW, precisa compor
        post.raw_image_s3_url = imagem_do_gemini
        post.save()
        compose_post_image_task.delay(post.id)
    else:
        # Modo B (atual) - imagem completa direto
        post.image_s3_url = imagem_do_gemini
        post.save()
```

**Esta e a unica alteracao em codigo existente em toda a feature.** Ela tem fallback seguro: se a composicao falhar, a raw_image_s3_url permanece disponivel e pode ser usada.

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `posts/font_resolver.py` | Arquivo NOVO | ZERO |
| `posts/compose_engine.py` | Arquivo NOVO | ZERO |
| `posts/tasks_compose.py` | Arquivo NOVO | ZERO |
| `posts/views_webhook.py` | Adicionar IF condicional | MEDIO (modifica fluxo, mas com fallback) |
| `posts/models.py` | Adicionar raw_image_s3_url, raw_image_s3_key | BAIXO |

### Como testar

```bash
# 1. Testar FontResolver isoladamente
python manage.py shell
>>> from apps.posts.font_resolver import FontResolver
>>> resolver = FontResolver()
>>> path = resolver.resolve({'source': 'google', 'font_name': 'Montserrat', 'weight': 'Regular'})
>>> import os; os.path.exists(path)  # True

# 2. Testar Composer com post mockado
>>> from apps.posts.compose_engine import PostComposer
>>> composer = PostComposer(post)
>>> png_bytes = composer.compose()
>>> # Salvar localmente e abrir para inspecao visual

# 3. Teste end-to-end
#    Criar post com generation_method='controlled_render'
#    Aguardar callback do Gemini
#    Verificar que compose_post_image_task foi disparada
#    Verificar imagem final no S3
#    Comparar visualmente com:
#      - Imagem raw do Gemini
#      - Brand guide original
```

### Rollback

```bash
# Opcao A: Reverter apenas o IF no callback
git checkout main -- app/apps/posts/views_webhook.py
# Posts passam a usar imagem completa do Gemini
# Compose engine fica sem uso mas nao quebra nada

# Opcao B: Rollback total
rm app/apps/posts/compose_engine.py
rm app/apps/posts/font_resolver.py
rm app/apps/posts/tasks_compose.py
git checkout main -- app/apps/posts/views_webhook.py
```

### Criterio de aprovacao

- [ ] Font Resolver resolve fonte do S3 (upload) corretamente
- [ ] Font Resolver baixa e cacheia fonte do Google Fonts
- [ ] Composer gera imagem com layout correto
- [ ] Cores aplicadas correspondem ao layout_plan
- [ ] Fonte correta renderizada (Supreme, nao parecida)
- [ ] Logo posicionado com area de seguranca
- [ ] Grafismo aplicado como overlay quando aplicavel
- [ ] Imagem raw preservada como fallback
- [ ] Falha na composicao nao deixa usuario sem imagem
- [ ] Fluxo atual (generation_method='free_style' ou sem spec) nao foi afetado

---

## FASE 8 - A/B Testing e Metricas

### Objetivo
Permitir geracao dupla (ambos os modos) para comparacao e coletar metricas para decisao baseada em dados.

### Dependencias
- Fase 7 aprovada

### O que sera feito

**8.1 - Geracao dupla**

```
Arquivo: app/apps/posts/views_webhook.py (adaptar)

Quando post.generation_method == 'both':
  - N8N gera 2 imagens em paralelo
  - Primeira callback: imagem do estilo livre -> post.image_s3_url
  - Segunda callback: imagem raw + composicao -> post.comparison_image_s3_url
```

**8.2 - Interface de comparacao**

```
Arquivo: app/templates/posts/*.html (adaptar)

Quando post tem comparison_image_s3_url:
  Mostra as duas imagens lado a lado
  Usuario seleciona qual aprovar (click ou radio)
  A nao-escolhida e descartada
```

**8.3 - Coleta de metricas**

```
Arquivo: app/apps/posts/signals.py (novo ou adaptar existente)

Eventos a capturar:
  - Post criado: registrar method_used em PostGenerationMetric
  - Post aprovado: registrar approved=True, time_to_approval
  - Revisao solicitada: incrementar revisions_requested
  - Custo registrado: por webhook do N8N com token counts
```

**8.4 - Dashboard de comparacao**

```
Arquivo novo: app/apps/posts/views_metrics.py

def ab_test_dashboard(request):
    """
    Retorna agregados por organization:
    - Total de posts por metodo
    - Taxa de aprovacao por metodo
    - Tempo medio ate aprovacao
    - Revisoes medias
    - Custo total
    """

Arquivo novo: app/templates/posts/ab_test_dashboard.html
```

### Arquivos tocados

| Arquivo | Acao | Risco |
|---------|------|-------|
| `posts/views_webhook.py` | Aceitar 2 callbacks para method=both | BAIXO |
| `posts/signals.py` | Novo arquivo ou adaptar | ZERO |
| `posts/views_metrics.py` | Arquivo NOVO | ZERO |
| `templates/posts/*.html` | Comparacao side-by-side | BAIXO |

### Rollback

```bash
# Desabilitar opcao 'both' no formulario
# Metricas continuam sendo coletadas para 'free_style' e 'controlled_render' individualmente
# Nenhum impacto funcional
```

### Criterio de aprovacao

- [ ] Modo 'both' gera as duas imagens em paralelo
- [ ] Interface mostra comparacao side-by-side
- [ ] Usuario escolhe qual aprovar
- [ ] Metricas coletadas para todas as geracoes
- [ ] Dashboard mostra comparativo por organization
- [ ] Cota consome 2x quando method=both

---

## Timeline Estimada

```
FASE 1: Modelos + Intents           ███░░░  0.5 sessao
FASE 2: Upload PDF + Conversao      ██████  1 sessao
FASE 3: Analise IA PDF              ██████  1-2 sessoes
FASE 4: Spec Inferido               ████░░  0.5 sessao
FASE 5: Marketing Summary           ████░░  0.5 sessao
FASE 6: Objetivo + Layout Planner   ██████  1-2 sessoes
FASE 7: Compose Engine              ██████████  2 sessoes
FASE 8: A/B Testing                 ████░░  1 sessao
                                    ─────────────────
                                    TOTAL: 7.5-9 sessoes
```

### Dependencias externas

- Workflows N8N precisam ser configurados para cada fase
- Credenciais de APIs (OpenAI, Gemini) configuradas
- Google Fonts API (ou alternativa) para FontResolver

### Valor entregue por fase

| Ate Fase | Valor |
|----------|-------|
| 1 | Estrutura pronta, nenhum comportamento mudou |
| 2 | Upload de PDF disponivel, visualizacao pagina a pagina |
| 3 | KB preenchida automaticamente + Brand Visual Spec para clientes com PDF |
| 4 | Brand Visual Spec tambem para clientes sem PDF |
| 5 | Marketing Summary otimiza todas as geracoes |
| 6 | Posts com objetivo + Layout Planner para clientes com spec |
| 7 | Posts com imagens de alta fidelidade ao brandguide |
| 8 | Comparacao A/B e decisoes baseadas em dados |

### Checkpoints de validacao

```
Apos cada fase:
  - Rodar suite de testes existente (regressao zero)
  - Criar/aprovar um post no modo antigo (garantia de continuidade)
  - Validar metricas basicas (tempo, custo, taxa de erro)

Se qualquer checkpoint falhar:
  - Rollback da fase
  - Investigar causa
  - Nao prosseguir para proxima fase ate resolver
```

---

## Checklist final de seguranca

Para cada PR:
- [ ] Suite de testes passa
- [ ] Post pode ser gerado SEM brand_visual_spec (fluxo atual)
- [ ] Post pode ser gerado COM generation_method='free_style' (fluxo atual)
- [ ] Rollback documentado e testado em staging
- [ ] Feature flag/config disponivel para desabilitar se necessario
- [ ] Logs adequados para troubleshooting
- [ ] Alertas de erro configurados (Sentry ou similar)
