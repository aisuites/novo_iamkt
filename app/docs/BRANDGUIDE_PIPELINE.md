# Pipeline de Brandguide e Geracao de Conteudo - IAMKT

> Documentacao tecnica consolidada do fluxo de analise de identidade de marca e geracao de posts com alta fidelidade visual.
>
> **Principio central:** o fluxo atual continua funcionando 100%. As novas features sao **aditivas e opcionais**.

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Os Dois Modos de Operacao](#2-os-dois-modos-de-operacao)
3. [Setup da Marca - Fluxo Detalhado](#3-setup-da-marca---fluxo-detalhado)
4. [Brand Visual Spec](#4-brand-visual-spec)
5. [Marketing Input Summary (evolucao)](#5-marketing-input-summary-evolucao-do-existente)
6. [Geracao de Pautas](#6-geracao-de-pautas)
7. [Geracao de Posts](#7-geracao-de-posts)
8. [A/B Testing: Estilo Livre vs Renderizacao Controlada](#8-ab-testing-estilo-livre-vs-renderizacao-controlada)
9. [Imagens de Referencia com Intent](#9-imagens-de-referencia-com-intent)
10. [Extracao de Grafismos do PDF](#10-extracao-de-grafismos-do-pdf)
11. [Custos e Performance](#11-custos-e-performance)
12. [Hierarquia de Autoridade](#12-hierarquia-de-autoridade)
13. [Modelos de Dados](#13-modelos-de-dados)
14. [Webhooks e Endpoints](#14-webhooks-e-endpoints)

---

## 1. Visao Geral

### Problema que resolvemos

Gerar posts para redes sociais com identidade visual fiel a marca, considerando que:
- Algumas marcas tem brandguide formal (PDF estruturado)
- Outras marcas tem apenas referencias visuais (imagens soltas)
- Outras marcas tem apenas descricoes textuais
- O sistema precisa funcionar bem em todos os cenarios

### Arquitetura em 2 macro-fases

```
┌──────────────────────────────────────────────────────────────────┐
│                  SETUP (1x por cliente)                           │
│                                                                   │
│  Cadastro -> Preenchimento KB -> Analise IA -> Aprovacao         │
│     obrigatorio   (7 blocos)     (sugestoes)   (Visual Spec)     │
│                                                                   │
│  Upload opcional:                                                 │
│    - PDF brandguide (gera Brand Visual Spec completo)             │
│    - Imagens de referencia com intent (gera Spec inferido)        │
│    - Cores, fontes, logos (individuais)                           │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                GERACAO (recorrente, por post)                     │
│                                                                   │
│  Pauta -> Post request -> Texto + Briefing -> Aprovacao -> Imagem│
│  (opc)   (obj+tema)      (copywriter)         (usuario)   (gera) │
│                                                                   │
│  Modo A: Gemini so visual -> Compose Engine renderiza            │
│  Modo B: Gemini gera tudo junto (fluxo atual preservado)         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Os Dois Modos de Operacao

### Modo A - Renderizacao Controlada

**Quando:** cliente tem `brand_visual_spec` populado na KB (do PDF ou de imagens de referencia).

**Como:**
1. Layout Planner escolhe template baseado no objetivo do post
2. Copywriter gera texto ciente do espaco disponivel em cada area
3. Gemini gera apenas o conteudo visual (sem texto, sem logo, sem bordas)
4. Compose Engine renderiza programaticamente a peca final com Pillow

**Fidelidade:** ~95%

### Modo B - Estilo Livre (fluxo atual)

**Quando:** cliente nao tem `brand_visual_spec`, OU escolheu este modo.

**Como:**
1. Agente recebe KB completa + marketing_input_summary + referencias
2. Gemini gera imagem completa (com texto e layout embutidos)
3. Post entregue ao usuario como e hoje

**Fidelidade:** ~70% (dependente da qualidade do Gemini)

### Escolha do modo

```
if kb.brand_visual_spec:
    match post.generation_method:
        case 'free_style':       # Modo B mesmo tendo Spec
        case 'controlled_render': # Modo A
        case 'both':              # Gera ambos para comparar (A/B test)
else:
    # Sempre Modo B (comportamento atual)
```

---

## 3. Setup da Marca - Fluxo Detalhado

### Etapa 3.1 - Cadastro e Acesso

Sem alteracao em relacao ao fluxo atual.

### Etapa 3.2 - Preenchimento da Knowledge Base (obrigatorio)

**Mantem 100% do que existe hoje:**
- 7 blocos de preenchimento
- Upload de fontes customizadas (S3)
- Upload de logos (S3)
- Upload de imagens de referencia (S3)
- Cadastro manual de cores (ColorPalette)
- Gate de onboarding (70% completude)

**Novas adicoes:**

**3.2.1 - Upload opcional de PDF brandguide**
Novo bloco/secao dentro do Bloco 5 (Identidade Visual). Aceita PDF de ate 50 MB, 200 paginas. Processamento assincrono apos upload.

**3.2.2 - Campos de intent nas imagens de referencia**
Cada imagem de referencia (existente ou nova) passa a ter:

| Campo | Valor | Uso |
|-------|-------|-----|
| `usage_description` | Texto livre | "Gosto da composicao minimalista" |
| `aspects_to_use` | Lista de flags | `["paleta_cor", "mood", "composicao"]` |
| `importance` | `high` / `medium` / `low` | Peso na analise |
| `usage_type` | `inspire` / `mimic` / `avoid` | Como interpretar |

Valores possiveis para `aspects_to_use`:
- `paleta_cor` - Usar as cores
- `mood` - Usar a atmosfera/sentimento
- `composicao` - Usar o layout/enquadramento
- `tipografia_aplicada` - Se houver texto visivel
- `uso_fotografia` - Estilo de foto (luz, angulo)
- `estilo_ilustracao` - Tipo de desenho
- `grafismos` - Padroes visuais
- `tratamento_cor` - Saturacao, contraste

### Etapa 3.3 - Analise IA da KB

**Fluxo mantido:** envio automatico para N8N ao salvar, webhook `N8N_WEBHOOK_FUNDAMENTOS`, retorno em `n8n_analysis`.

**Melhorias:**
- Analise considera `usage_description` e `aspects_to_use` das imagens de referencia
- Se existe PDF brandguide: analise conjunta texto+visual (detalhado em 3.4)
- Se nao existe PDF mas existem imagens de referencia com intent: gera Brand Visual Spec INFERIDO

### Etapa 3.4 - Pipeline de Analise do PDF (quando existe)

```
PDF no S3
  │
  ▼
[CELERY] Conversao PDF->PNG (200 DPI)
  │  60 paginas viram 60 PNGs
  │  Upload para S3: /brandguide/pages/page_NNN.png
  ▼
[CELERY] Extracao de assets com PyMuPDF
  │  Identifica objetos embutidos (imagens, vetores)
  │  Salva candidatos em: /brandguide/assets/
  ▼
[CELERY] Extracao de texto auxiliar com pdfplumber
  │  Apenas como apoio para a IA
  ▼
[N8N] Envio para analise
  │  Payload: URLs das paginas + texto auxiliar + assets extraidos
  ▼
[GPT-4o Vision] Analise conjunta texto+visual
  │  - Classifica cada pagina por categoria
  │  - Identifica cores com contexto semantico
  │  - Identifica tipografia (nome, peso, fallback)
  │  - Identifica grid e regras de composicao
  │  - Identifica grafismos (e quais sao extraveis)
  │  - Preenche campos da KB
  │  - Gera Brand Visual Spec completo
  ▼
[N8N] Callback para IAMKT
  │  Payload: suggested_fields + brand_visual_spec + classified_pages
  ▼
[IAMKT] Salva como sugestoes pendentes de aprovacao
```

**Nota sobre extracao de cores:**
A extracao automatica por pixel (colorgram) foi removida. A IA Vision identifica cores **com contexto** (primaria vs secundaria vs acento) muito melhor que analise de pixels. Simplifica o pipeline e melhora a precisao.

### Etapa 3.5 - Aprovacao e Atualizacao

**Mantido do fluxo atual:**
- Usuario revisa sugestoes em `perfil_view`
- Aceita ou rejeita individualmente cada sugestao
- Campos aprovados atualizam a KB (mantendo os que permaneceram iguais)

**Novo:**
- Brand Visual Spec tambem passa por aprovacao (view visual, nao JSON cru)
- Grafismos extraidos sao apresentados com previews para aprovacao individual
- Usuario pode marcar grafismos como "usar" ou "descartar"

### Etapa 3.6 - Geracao do Marketing Summary

Apos aprovacao, novo envio ao N8N para geracao do `marketing_input_summary` (estrutura detalhada na secao 5).

### Etapa 3.7 - Liberacao para uso

KB fica completa, usuario tem acesso a geracao de pautas e posts.

---

## 4. Brand Visual Spec

### O que e

JSON estruturado que captura as regras visuais da marca. Usado como input para o Layout Planner e o Compose Engine no Modo A.

### Niveis de autoridade

| Source | Confidence | Exemplo |
|--------|-----------|---------|
| `brandguide_pdf` | `high` | Cliente enviou PDF estruturado |
| `reference_images` | `medium` | Apenas imagens de referencia com intent |
| `hybrid` | `high` | PDF + imagens complementares |
| `manual` | `medium` | Usuario preencheu manualmente |

Quando `confidence = medium`, a interface avisa o usuario que o spec foi **inferido** e exige validacao manual.

### Estrutura

```json
{
  "brand_visual_spec": {
    "versao": "1.0",
    "source": "brandguide_pdf",
    "confidence": "high",
    "requires_user_validation": false,
    "gerado_em": "2026-04-15T10:30:00Z",

    "logo": {
      "variacoes_disponiveis": ["preferencial", "vertical", "contracao", "reduzida"],
      "area_seguranca": "altura da letra M do logotipo",
      "reducao_minima_digital_px": 110,
      "descricao_visual": "Espacos abertos, movimento pulsante, alto contraste"
    },

    "tipografia": {
      "primaria": {
        "familia": "Supreme",
        "peso_padrao": "Regular",
        "disponivel_google_fonts": true,
        "fallback": "IBM Plex Sans",
        "source": "google_fonts"
      },
      "hierarquia": {
        "titulo": {
          "fonte": "Supreme Regular",
          "caixa": "ALTA",
          "tamanho_relativo": "X",
          "posicao_preferencial": "topo-esquerda"
        },
        "texto_principal": {
          "fonte": "Supreme Regular",
          "caixa": "normal",
          "tamanho_relativo": "X/2"
        },
        "texto_secundario": {
          "fonte": "Supreme Regular",
          "caixa": "normal",
          "tamanho_relativo": "2X/3"
        }
      }
    },

    "cores": {
      "institucional": [
        {"nome": "Preto", "hex": "#000000", "uso": "Principal, textos, backgrounds"},
        {"nome": "Branco", "hex": "#FFFFFF", "uso": "Fundos, textos sobre preto"}
      ],
      "iniciativas": [
        {"nome": "Azul", "hex": "#0055FF", "uso": "Eventos e projetos"},
        {"nome": "Verde", "hex": "#00AA55", "uso": "Eventos e projetos"},
        {"nome": "Rosa", "hex": "#FF0066", "uso": "Eventos e projetos"}
      ],
      "regras": [
        "Usar apenas 1 cor de iniciativa por peca",
        "Sempre combinar com preto e branco",
        "Nunca misturar duas cores de iniciativas"
      ]
    },

    "grid": {
      "quadrado": {"colunas": 2, "linhas": 2},
      "retangular": {"colunas": 2, "linhas": 3},
      "regras": ["Textos e imagens enquadrados nas areas do grid"]
    },

    "grafismos_disponiveis": [
      {
        "id": "mod_03",
        "nome": "Modulo vertical 03",
        "s3_url": "https://s3.../grafismos/mod_03.png",
        "tipo": "overlay",
        "uso": "apoio decorativo"
      }
    ],

    "estilo_composicao": {
      "abordagem": "Minimalista, alto contraste, espacos abertos",
      "mood": "Tech, limpo, futurista sobrio",
      "principios": [
        "Menos e mais",
        "Espacos vazios sao intencionais",
        "Contraste forte entre texto e fundo"
      ]
    },

    "paginas_referencia": {
      "cores": ["page_035.png", "page_036.png"],
      "aplicacoes": ["page_050.png", "page_052.png"]
    }
  }
}
```

### Brand Visual Spec INFERIDO (sem PDF)

Quando o cliente so tem imagens de referencia, o spec tem menos autoridade:

```json
{
  "brand_visual_spec": {
    "source": "reference_images",
    "confidence": "medium",
    "requires_user_validation": true,

    "cores_inferidas": [
      {"hex": "#2A3B4C", "contexto": "recorrente em 5 das 8 imagens"},
      {"hex": "#E8E4D9", "contexto": "fundo em 4 imagens"}
    ],

    "mood_inferido": "Aconchegante, artesanal, natural",
    "estilo_inferido": "Fotografia lifestyle com luz natural",

    "regras_fixas": false,
    "grid_definido": false,
    "grafismos_extraidos": false,

    "observacao": "Spec inferido de imagens de referencia. Validar antes de usar."
  }
}
```

Quando usado no Modo A, o Compose Engine opera com restricoes: sem grafismos aplicados, layout usando templates genericos.

---

## 5. Marketing Input Summary (evolucao do existente)

### O que ja existe

A aplicacao ja tem o campo `n8n_compilation.marketing_input_summary`, gerado pelo N8N apos aprovacao de sugestoes. Hoje e uma **string de texto livre** enviada como input em pautas e posts (ver [FLUXO_GERAR_IMAGEM.md](../../../docs-aplicacao/FLUXO_GERAR_IMAGEM.md)).

### O que muda

**Nao criamos campo novo.** Evoluimos o `n8n_compilation` existente adicionando um sub-bloco estruturado complementar, mantendo total compatibilidade com o que ja existe:

```python
# KnowledgeBase.n8n_compilation (JSONField existente):
{
  "received_at": "...",
  "four_week_marketing_plan": {...},
  "assessment_summary": "...",
  "improvements_summary": "...",

  # CAMPO EXISTENTE - mantido intocado (compatibilidade)
  "marketing_input_summary": "texto livre atual...",

  # NOVO - estrutura complementar (opcional, usada por agentes novos)
  "marketing_input_structured": {
    "versao": "1.0",
    "gerado_em": "2026-04-15",
    "essencia_marca": {...},
    "posicionamento_curto": "...",
    "publico_alvo_compacto": {...},
    "tom_voz_regras": {...},
    "visual_direction_resumo": {...}
  }
}
```

### Por que evoluir

| Aspecto | `marketing_input_summary` (atual) | `marketing_input_structured` (novo) |
|---------|----------------------------------|-------------------------------------|
| Formato | Texto livre | JSON estruturado |
| Uso | Agente le tudo | Agente pega secoes especificas |
| Token cost | Envia texto inteiro sempre | Envia so o que precisa |
| Parseavel | Nao | Sim |

### Estrategia de compatibilidade

- **Agentes antigos** (geracao de pauta e post atuais): continuam usando `marketing_input_summary` em texto - nada muda
- **Agentes novos** (Layout Planner, Copywriter com spec, Compose Engine): usam `marketing_input_structured` para pegar so o bloco que precisam
- **Sem migration:** e apenas formato dentro do JSONField ja existente

### Estrutura do bloco `marketing_input_structured`

```json
{
  "versao": "1.0",
  "gerado_em": "2026-04-15",

  "essencia_marca": {
    "uma_frase": "Instituto que conecta tecnologia e impacto social",
    "arquetipo": "Sabio + Criador",
    "personalidade": ["inovador", "tecnico", "acessivel"]
  },

  "posicionamento_curto": "Referencia em projetos de impacto futuro via tecnologia",

  "publico_alvo_compacto": {
    "primario": "Profissionais 28-45, curiosos sobre futuro",
    "dores": ["mundo muda rapido demais", "buscam proposito"],
    "desejos": ["estar na vanguarda", "contribuir com impacto"]
  },

  "proposta_valor_compacta": "Tecnologia do futuro aplicada hoje",

  "tom_voz_regras": {
    "sim": ["Direto e tecnico", "Otimista sem ingenuidade"],
    "nao": ["Corporatives", "Hype vazio"],
    "exemplos_boas_frases": [
      "O futuro nao acontece - e construido."
    ]
  },

  "palavras_chave_marca": ["inovacao", "futuro", "transformacao"],
  "palavras_proibidas": ["barato", "simples", "disrupcao"],

  "temas_estrategicos": [
    "Workshops de IA aplicada",
    "Cases de impacto social"
  ],

  "ganchos_narrativos": [
    "Contraste ontem/hoje/amanha",
    "Bastidores de projetos tecnicos"
  ],

  "ctas_recomendados": [
    "Inscreva-se pelo link na bio",
    "Leia no nosso Medium"
  ],

  "visual_direction_resumo": {
    "mood": "minimalista, alto contraste, futurista sobrio",
    "cores_dominantes": ["#000000", "#FFFFFF", "#0055FF"],
    "abordagem": "espacos abertos, tipografia forte"
  }
}
```

### Quando e gerado

- Junto com o `marketing_input_summary` existente (mesmo trigger): apos aprovacao de sugestoes
- Apos mudancas significativas na KB (nao em qualquer salvamento)
- Na mesma chamada ao N8N - o workflow passa a gerar os dois formatos

### Acesso no codigo

```python
# Codigo antigo (continua funcionando):
summary_text = kb.n8n_compilation.get('marketing_input_summary', '')

# Codigo novo:
structured = kb.n8n_compilation.get('marketing_input_structured', {})
tom_voz = structured.get('tom_voz_regras', {})
visual = structured.get('visual_direction_resumo', {})
```

---

## 6. Geracao de Pautas

Mantem o fluxo atual com pequena melhoria:

```
Usuario solicita pauta -> N8N recebe KB + marketing_input_summary
  -> Agente 1 (Perplexity): pesquisa mercado/tendencias do nicho
  -> Agente 2 (GPT): cruza com posicionamento e tom de voz
  -> Retorna: titulo + tema sugeridos
  -> Salvos na KB para uso em posts
```

**Melhoria:** quando existe Brand Visual Spec, as pautas sao sugeridas ja considerando o posicionamento visual da marca (evita temas que nao combinariam esteticamente).

---

## 7. Geracao de Posts

### Fluxo unificado (ambos modos)

```
Usuario solicita post
  │  Informa: rede_social, formato, CTA?, carrossel?, tema, objetivo, refs opcionais
  ▼
N8N recebe:
  │  KB completa + marketing_input_summary + Brand Visual Spec (se existir)
  │  + imagens de referencia (KB + post) com intent
  │  + parametros da solicitacao
  ▼
Agente 1 (GPT-4o) - Layout Planner (so no Modo A)
  │  Input: objetivo + Brand Visual Spec + formato
  │  Output: template escolhido + layout_plan com areas e restricoes
  │  SE Modo B: pula esta etapa
  ▼
Agente 2 (GPT-4o) - Copywriter
  │  Input: tema + KB + marketing_input_summary + (layout_plan se Modo A)
  │  Output: titulo, subtitulo, legenda, hashtags, CTA
  │  + image_brief (descricao para geracao da imagem)
  ▼
Callback para IAMKT
  │  Post criado com status 'pending'
  │  Textos e briefing disponiveis para revisao
  ▼
USUARIO REVISA TEXTO
  │  Pode: aprovar / editar / pedir revisao
  │  (mesmo comportamento atual)
  ▼
USUARIO CLICA "GERAR IMAGEM"
  │  So agora a imagem e gerada (economia se texto foi rejeitado)
  ▼
Agente 3 - Geracao de Imagem
  │  Modo A: Gemini gera apenas o visual (sem texto/logo)
  │           Compose Engine renderiza a peca final
  │  Modo B: Gemini gera imagem completa com tudo embutido
  │  Modo both: gera os dois para comparacao
  ▼
Post status: 'image_ready'
  │
  ▼
USUARIO REVISA IMAGEM
  │  Pode: aprovar / rejeitar / solicitar nova versao
```

### Campos novos no formulario de post

```
┌─────────────────────────────────────────────────────┐
│          GERAR NOVO POST                            │
│                                                     │
│  Rede Social:    [Instagram ▼]                      │
│  Formato:        [Feed 1080x1350 ▼]                 │
│  Tipo:           [Post unico ▼]                     │
│  Incluir CTA:    [X] Sim  [ ] Nao                   │
│  Tema:           [_______________________________]   │
│                                                     │
│  ★ Objetivo do post (NOVO):                         │
│  [Evento ▼]                                         │
│    - Evento                                         │
│    - Venda / Promocao                               │
│    - Conteudo educacional                           │
│    - Institucional / Branding                       │
│    - Bastidores / Cultura                           │
│    - Depoimento / Case                              │
│    - Datas comemorativas                            │
│    - Engajamento (enquete, quiz)                    │
│                                                     │
│  Imagens de referencia (opcional):                  │
│  [+ Upload de imagem]                               │
│    Cada imagem tem: descricao, aspects,             │
│    importancia, tipo de uso (NOVO)                  │
│                                                     │
│  ★ Metodo de geracao de imagem (se tem Spec):       │
│  ( ) Estilo livre (Gemini completo)                 │
│  ( ) Renderizacao controlada                        │
│  (•) Comparar os dois                               │
│                                                     │
│  [GERAR POST]                                       │
└─────────────────────────────────────────────────────┘
```

---

## 8. A/B Testing: Estilo Livre vs Renderizacao Controlada

### Por que

Ninguem sabe de antemao qual metodo entrega mais valor para cada marca. Comparar na pratica e a unica forma de descobrir.

### Como funciona

Campo novo no Post:

```python
generation_method = CharField(choices=[
    ('free_style', 'Estilo livre (Gemini completo)'),
    ('controlled_render', 'Renderizacao controlada'),
    ('both', 'Comparar os dois'),
], default='free_style')
```

Quando `generation_method='both'`:
- N8N gera texto uma vez so
- Dispara 2 geracoes de imagem em paralelo
- Interface mostra as duas lado a lado
- Usuario escolhe qual aprovar

### Metricas coletadas

Novo modelo `PostGenerationMetric`:

```python
- post (FK)
- method_used: 'free_style' | 'controlled_render'
- approved: boolean
- revisions_requested: int
- time_to_approval: duration
- user_rating: int (opcional)
- tokens_used: int
- cost_usd: decimal
```

Apos 2-3 meses, relatorio comparativo responde:
- Qual metodo tem maior taxa de aprovacao?
- Qual requer menos revisoes?
- Qual custa menos?
- Qual e avaliado melhor?

### Impacto em cota

Geracao `both` consome 2 unidades da cota diaria de posts. Pode ter cota separada "comparacao" (ex: 3x por semana).

---

## 9. Imagens de Referencia com Intent

### Problema atual

Usuario sobe 5-10 imagens sem contexto. A IA nao sabe:
- Se e para usar a paleta ou o estilo
- Se e exemplo positivo ou negativo
- Qual imagem e mais importante
- Como resolver conflitos entre imagens

### Solucao

Campos novos em `ReferenceImage` (KB) e `PostReferenceImage`:

| Campo | Tipo | Valores |
|-------|------|---------|
| `usage_description` | TextField | Texto livre |
| `aspects_to_use` | JSONField (list) | `paleta_cor`, `mood`, `composicao`, `tipografia_aplicada`, `uso_fotografia`, `estilo_ilustracao`, `grafismos`, `tratamento_cor` |
| `importance` | CharField | `high`, `medium`, `low` |
| `usage_type` | CharField | `inspire` (inspirar), `mimic` (seguir fielmente), `avoid` (evitar) |

### Interface

```
┌──────────────────────────────────────────┐
│  UPLOAD DE IMAGEM DE REFERENCIA          │
│                                          │
│  [📷 foto.jpg]                           │
│                                          │
│  Descricao breve:                        │
│  [____________________________________]  │
│                                          │
│  O que aproveitar?                       │
│  [X] Paleta de cores                     │
│  [X] Mood/atmosfera                      │
│  [X] Composicao                          │
│  [ ] Tipografia aplicada                 │
│  [ ] Uso de fotografia                   │
│                                          │
│  Importancia: ( ) Alta (•) Media ( ) Baixa│
│                                          │
│  Tipo:                                   │
│  (•) Inspirar                            │
│  ( ) Seguir fielmente                    │
│  ( ) EVITAR (nao quero parecer)          │
│                                          │
│  [SALVAR]                                │
└──────────────────────────────────────────┘
```

### Geracao do Brand Visual Spec INFERIDO

Quando o cliente nao tem PDF mas tem imagens de referencia bem descritas, o sistema consegue inferir um Brand Visual Spec:

```
Imagens de referencia com intent
  + fontes cadastradas
  + cores cadastradas (ColorPalette)
  + logos
  │
  ▼
IA Vision analisa conjunto:
  - Respeita aspects_to_use de cada imagem
  - Ignora imagens com usage_type='avoid' (ou usa como "nao fazer")
  - Prioriza imagens com importance='high'
  - Busca padroes consistentes no conjunto
  │
  ▼
Brand Visual Spec com source='reference_images'
  confidence='medium'
  requires_user_validation=true
  │
  ▼
Usuario valida/ajusta -> spec disponivel para uso
```

**Limitacoes:** sem grafismos extraidos, sem grid estruturado, sem hierarquia tipografica definida. O Compose Engine, quando usado com spec inferido, opera com templates genericos responsivos a paleta.

---

## 10. Extracao de Grafismos do PDF

### Cenarios possiveis

| Cenario | Como o grafismo esta no PDF | Extracao |
|---------|----------------------------|----------|
| A | Vetor embutido (SVG) | PyMuPDF extrai SVG - fidelidade 100% |
| B | Imagem embutida (PNG/JPG) | PyMuPDF extrai imagem |
| C | Parte do render da pagina | Recorte programatico baseado em coordenadas da IA |

### Pipeline

```
[1] PyMuPDF extrai TODOS os objetos embutidos
    │  Salva candidatos em S3: /brandguide/assets/raw/
    ▼
[2] IA Vision classifica cada asset:
    │  - Logo? (descarta, ja temos upload separado)
    │  - Grafismo/padrao? (mantem)
    │  - Foto/ilustracao exemplo? (descarta)
    ▼
[3] Para Cenario C (grafismo nao e objeto isolado):
    │  - IA identifica coordenadas na pagina
    │  - Backend recorta com Pillow
    │  - Aplica remocao de fundo (rembg) se aplicavel
    ▼
[4] Usuario revisa grafismos capturados
    │  Aprova quais usar
    │  Ajusta nomes/categorias
    ▼
[5] Grafismos aprovados salvos no modelo BrandgraficModule
    │  Disponiveis para Compose Engine usar como overlay
```

### Quando nao consegue extrair

Se nenhum grafismo e extraivel com fidelidade aceitavel, o Brand Visual Spec marca `grafismos_extraidos: false` e o Compose Engine opera sem overlay decorativo.

---

## 11. Custos e Performance

### Setup (1x por cliente)

| Item | Cenario PDF | Cenario so imagens ref |
|------|-------------|------------------------|
| Conversao PDF->PNG | ~60s | - |
| Extracao assets (PyMuPDF) | ~10s | - |
| Analise IA (triagem) | ~$0.01 | - |
| Analise IA (profunda) | ~$0.08 | ~$0.03 |
| Brand Visual Spec | ~$0.16 | ~$0.06 |
| Marketing Summary | ~$0.03 | ~$0.03 |
| **Total setup** | **~$0.28** | **~$0.12** |
| Tempo total | ~3 min | ~1 min |

### Por post

| Modo | Texto | Imagem | Composicao | **Total** |
|------|-------|--------|------------|-----------|
| B (estilo livre) | $0.02 | $0.04-0.08 | $0.00 | **$0.06-0.10** |
| A (controlado) | $0.02 | $0.04 | $0.00 (local) | **$0.06** |
| Both (comparacao) | $0.02 | $0.08-0.12 | $0.00 | **$0.10-0.14** |

### Projecao mensal

| Escala | Clientes | Posts/mes | Setup | Posts | **Total** |
|--------|----------|-----------|-------|-------|-----------|
| Inicio | 10 | 200 | $2.80 | $20 | **~$23** |
| Crescimento | 50 | 1.500 | $14 | $150 | **~$164** |
| Escala | 200 | 8.000 | $56 | $800 | **~$856** |

### Tempo percebido pelo usuario

| Acao | Tempo |
|------|-------|
| Upload + analise PDF | 2-3 min (background) |
| Solicitacao de post -> texto pronto | ~20s |
| Aprovacao + geracao de imagem | ~30s |
| Total ate post final | ~1 min |

---

## 12. Hierarquia de Autoridade

Quando ha conflito entre fontes de informacao visual, a ordem de prioridade e:

```
PRIORIDADE 1 - REGRAS FIXAS (nao negociaveis)
  Brand Visual Spec com source='brandguide_pdf'
  → Cores, tipografia, grid e grafismos sao leis

PRIORIDADE 2 - REGRAS INFERIDAS (validadas pelo usuario)
  Brand Visual Spec com source='reference_images' + validado
  → Direcoes visuais, nao regras absolutas

PRIORIDADE 3 - CADASTROS MANUAIS
  ColorPalette, Typography, Logo, CustomFont da KB
  → Valores especificos definidos pelo usuario

PRIORIDADE 4 - INSPIRACAO DIRECIONADA
  ReferenceImages da KB com intent
  → Aspectos especificos (cor, mood, composicao)
  → Respeitando aspects_to_use de cada imagem

PRIORIDADE 5 - CONTEXTO MOMENTANEO
  PostReferenceImages (subidas na solicitacao do post)
  → Mesma logica da P4, mas especifica para este post

PRIORIDADE 6 - TEMA E OBJETIVO
  Parametros da solicitacao
  → Influenciam conteudo, nao identidade visual
```

### Exemplo de resolucao de conflito

```
Cenario: cliente tem Brand Visual Spec (PDF) com paleta preto/branco/azul.
         Sobe imagem de referencia vermelha com aspects_to_use=['paleta_cor'].

Resolucao:
  P1 (Brand Spec) vence sobre P4 (Reference Image)
  → Paleta continua preto/branco/azul
  → Interface avisa: "Imagem de referencia conflita com brandguide.
     Aspecto 'paleta_cor' sera ignorado. Outros aspectos sao aplicados."
  → Usuario pode ajustar aspects_to_use ou remover a imagem
```

---

## 13. Modelos de Dados

### Modelos novos

#### BrandguideUpload

```python
class BrandguideUpload(models.Model):
    knowledge_base = ForeignKey(KnowledgeBase)
    original_filename = CharField(255)
    s3_key_pdf = CharField(500)
    s3_url_pdf = URLField(1000)
    total_pages = PositiveIntegerField()
    file_size = PositiveIntegerField()
    processing_status = CharField(
        choices=['uploaded', 'converting', 'extracting_assets',
                 'analyzing', 'completed', 'error']
    )
    error_message = TextField(blank=True)
    uploaded_by = ForeignKey(User)
    created_at = DateTimeField(auto_now_add=True)
    completed_at = DateTimeField(null=True)
```

#### BrandguidePage

```python
class BrandguidePage(models.Model):
    brandguide = ForeignKey(BrandguideUpload, related_name='pages')
    page_number = PositiveIntegerField()
    s3_key = CharField(500)
    s3_url = URLField(1000)
    width = PositiveIntegerField()
    height = PositiveIntegerField()
    extracted_text = TextField(blank=True)
    category = CharField(
        choices=['capa', 'logotipo', 'tipografia', 'cores',
                 'grafismo', 'grid', 'aplicacoes', 'informacional', 'outro']
    )
    relevance = CharField(choices=['low', 'medium', 'high'])
```

#### BrandgraficModule (grafismos extraidos)

```python
class BrandgraficModule(models.Model):
    knowledge_base = ForeignKey(KnowledgeBase)
    name = CharField(100)
    extraction_type = CharField(
        choices=['vector_embedded', 'image_embedded', 'cropped_from_page']
    )
    source_page = PositiveIntegerField(null=True)
    s3_key = CharField(500)
    s3_url = URLField(1000)
    file_format = CharField(choices=['svg', 'png'])
    has_transparency = BooleanField()
    width = PositiveIntegerField()
    height = PositiveIntegerField()
    orientation = CharField(choices=['vertical', 'horizontal', 'both'])
    usage_hint = CharField(blank=True)
    approved_by_user = BooleanField(default=False)
    is_active = BooleanField(default=True)
```

#### PostGenerationMetric (A/B testing)

```python
class PostGenerationMetric(models.Model):
    post = ForeignKey(Post)
    method_used = CharField(choices=['free_style', 'controlled_render'])
    approved = BooleanField(null=True)
    revisions_requested = PositiveIntegerField(default=0)
    time_to_approval_seconds = PositiveIntegerField(null=True)
    user_rating = PositiveSmallIntegerField(null=True)
    tokens_used = PositiveIntegerField(default=0)
    cost_usd = DecimalField(max_digits=8, decimal_places=4, default=0)
    created_at = DateTimeField(auto_now_add=True)
```

### Campos novos em modelos existentes

#### KnowledgeBase (adicionar)

```python
brand_visual_spec = JSONField(null=True, blank=True)
brand_visual_spec_source = CharField(
    choices=['brandguide_pdf', 'reference_images', 'hybrid', 'manual'],
    null=True, blank=True
)
brand_visual_spec_confidence = CharField(
    choices=['high', 'medium', 'low'],
    null=True, blank=True
)
brand_visual_spec_validated = BooleanField(default=False)

# marketing_input_structured NAO e campo proprio - vive dentro de
# n8n_compilation (JSONField ja existente)
```

#### ReferenceImage (adicionar)

```python
usage_description = TextField(blank=True)
aspects_to_use = JSONField(default=list)
importance = CharField(
    choices=['high', 'medium', 'low'],
    default='medium'
)
usage_type = CharField(
    choices=['inspire', 'mimic', 'avoid'],
    default='inspire'
)
```

#### PostReferenceImage (adicionar - mesmos campos)

```python
usage_description = TextField(blank=True)
aspects_to_use = JSONField(default=list)
importance = CharField(default='medium')
usage_type = CharField(default='inspire')
```

#### Post (adicionar)

```python
objetivo = CharField(
    choices=['evento', 'venda', 'educacional', 'institucional',
             'bastidores', 'depoimento', 'datas_comemorativas', 'engajamento'],
    default='institucional'
)
generation_method = CharField(
    choices=['free_style', 'controlled_render', 'both'],
    default='free_style'
)
layout_plan = JSONField(null=True, blank=True)
image_brief = TextField(blank=True)
comparison_image_s3_url = URLField(blank=True, max_length=1000)
comparison_image_s3_key = CharField(blank=True, max_length=500)
```

---

## 14. Webhooks e Endpoints

### Endpoints IAMKT novos

| Metodo | URL | Funcao |
|--------|-----|--------|
| POST | `/knowledge/brandguide/upload-url/` | Presigned URL para upload do PDF |
| POST | `/knowledge/brandguide/create/` | Confirma upload e inicia processamento |
| GET | `/knowledge/brandguide/status/` | Consulta status do processamento |
| GET | `/knowledge/brandguide/suggestions/` | Retorna sugestoes da analise |
| POST | `/knowledge/brandguide/approve/` | Aprova/rejeita sugestoes |
| POST | `/knowledge/brandguide/grafismos/approve/` | Aprova grafismos extraidos |
| POST | `/knowledge/webhook/brandguide/` | Callback N8N da analise do PDF |
| POST | `/knowledge/webhook/marketing-summary/` | Callback N8N do marketing summary |
| PUT | `/knowledge/reference-image/<id>/intent/` | Atualiza intent de imagem de referencia |

### Webhooks N8N

| Webhook | Direcao | Quando |
|---------|---------|--------|
| `N8N_WEBHOOK_ANALYZE_BRANDGUIDE` | IAMKT -> N8N | Apos extracao de assets do PDF |
| `N8N_WEBHOOK_INFER_VISUAL_SPEC` | IAMKT -> N8N | Quando nao ha PDF, apenas refs |
| `N8N_WEBHOOK_GENERATE_MARKETING_SUMMARY` | IAMKT -> N8N | Apos aprovacao de sugestoes |
| `/knowledge/webhook/brandguide/` | N8N -> IAMKT | Resultado da analise do brandguide |
| `/knowledge/webhook/marketing-summary/` | N8N -> IAMKT | Marketing summary gerado |

### Payloads detalhados estao em [PLANO_IMPLEMENTACAO.md](./PLANO_IMPLEMENTACAO.md)
