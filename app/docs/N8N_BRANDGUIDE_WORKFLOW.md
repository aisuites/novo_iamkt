# N8N Workflow — Analise de Brandguide

> Guia completo para implementar o workflow N8N que recebe o PDF processado pelo IAMKT,
> analisa com IA (Vision) e devolve os resultados via callback.
>
> **Versao N8N testada:** 2.12.3 (Self Hosted)

---

## Indice

1. [Visao Geral do Fluxo](#1-visao-geral-do-fluxo)
2. [Payload Recebido do IAMKT](#2-payload-recebido-do-iamkt)
3. [Payload Esperado no Callback](#3-payload-esperado-no-callback)
4. [Etapa 1 — Callback Mock (sem IA)](#4-etapa-1--callback-mock-sem-ia)
5. [Etapa 2 — Triagem de Paginas com IA](#5-etapa-2--triagem-de-paginas-com-ia)
6. [Etapa 3 — Analise Profunda + Brand Visual Spec](#6-etapa-3--analise-profunda--brand-visual-spec)
7. [Tratamento de Erros](#7-tratamento-de-erros)
8. [Como Testar](#8-como-testar)
9. [Custos por Chamada](#9-custos-por-chamada)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Visao Geral do Fluxo

```
IAMKT                        N8N Workflow                      OpenAI API
─────                        ──────────────                    ──────────
Upload PDF
  → PDF → PNGs
  → POST webhook ──────→ [Webhook]
                           │
                         [Respond to Webhook] → 200 OK
                           │
                         [Code: preparar triagem]
                           │
                         [HTTP Request: OpenAI] ──────────→ gpt-4.1-mini (Vision)
                           │                                    classificacao
                         [Code: filtrar paginas high]           ←────────
                           │
                         [HTTP Request: OpenAI] ──────────→ gpt-4o (Vision)
                           │                                    analise profunda
                         [Code: montar payload final]           ←────────
                           │
                         [HTTP Request: callback]
                           │
  ← POST /webhook/bg/ ←───┘
  → Salva resultados
```

**Por que HTTP Request em vez do no OpenAI nativo:**
O no "Message a model" do N8N 2.12 nao suporta envio de imagens (Vision) nativamente.
Usar HTTP Request direto para a API OpenAI garante controle total sobre o formato multimodal
(image_url + text no mesmo content array).

---

## 2. Payload Recebido do IAMKT

```json
{
  "brandguide_id": 15,
  "knowledge_base_id": 1,
  "organization_id": 23,
  "total_pages": 60,
  "pdf_url": "https://app-iamkt-uploads.s3.us-east-1.amazonaws.com/org-23/brandguides/.../original.pdf",
  "pages": [
    {
      "page_number": 1,
      "s3_url": "https://app-iamkt-uploads.s3.us-east-1.amazonaws.com/.../page_001.png",
      "extracted_text": "Guide para aplicação\nSistema de ID\nFor Tomorrow"
    },
    {
      "page_number": 2,
      "s3_url": "https://...page_002.png",
      "extracted_text": "LOGOTIPO\nO logotipo foi desenhado com espaços abertos..."
    }
  ],
  "callback_url": "https://app.iamkt.com.br/knowledge/webhook/brandguide/",
  "existing_kb": {
    "nome_empresa": "For Tomorrow",
    "missao": "...",
    "visao": "...",
    "valores": "...",
    "posicionamento": "...",
    "tom_voz_externo": "...",
    "brand_visual_spec": null
  }
}
```

**Acesso no N8N:** `{{ $json.body.brandguide_id }}`, `{{ $json.body.pages }}`, etc.

---

## 3. Payload Esperado no Callback

### Headers obrigatorios

```
Content-Type: application/json
X-INTERNAL-TOKEN: <mesmo valor de N8N_WEBHOOK_SECRET do .env do IAMKT>
```

### Body (sucesso)

```json
{
  "brandguide_id": 15,
  "status": "completed",
  "page_classifications": [
    {"page_number": 1, "category": "capa", "relevance": "low"},
    {"page_number": 2, "category": "logotipo", "relevance": "high"},
    {"page_number": 15, "category": "tipografia", "relevance": "high"},
    {"page_number": 35, "category": "cores", "relevance": "high"},
    {"page_number": 50, "category": "aplicacoes", "relevance": "high"}
  ],
  "suggested_kb_fields": {
    "nome_empresa": "For Tomorrow Institute",
    "posicionamento": "Marca minimalista, tecnica e elegante, associada a engenharia e tecnologia",
    "diferenciais": "Identidade visual com espacos abertos, movimento pulsante, sistema modular de grafismo",
    "proposta_valor": "Inovacao e impacto futuro atraves da tecnologia",
    "tom_voz_externo": "Tecnico, minimalista, direto. Preza por clareza e legibilidade.",
    "palavras_recomendadas": ["inovacao", "futuro", "transformacao", "impacto", "tecnologia"],
    "palavras_evitar": ["barato", "simples", "basico", "rapido"]
  },
  "brand_visual_spec": {
    "versao": "1.0",
    "logo": {
      "variacoes": ["preferencial", "vertical", "contracao", "reduzida"],
      "descricao_visual": "Logotipo com espacos abertos, contraste de forma, movimento pulsante",
      "area_seguranca": "Altura da letra M do logotipo",
      "reducao_minima_digital_px": 110
    },
    "cores": {
      "institucional": [
        {"nome": "Preto Institucional", "hex": "#000000", "uso": "Cor principal, textos, backgrounds"},
        {"nome": "Branco Institucional", "hex": "#FFFFFF", "uso": "Fundos, textos sobre preto"}
      ],
      "iniciativas": [
        {"nome": "Azul", "hex": "#0055FF", "uso": "Demarcacao de eventos e projetos"},
        {"nome": "Verde", "hex": "#00AA55", "uso": "Demarcacao de eventos e projetos"},
        {"nome": "Rosa", "hex": "#FF0066", "uso": "Demarcacao de eventos e projetos"}
      ],
      "regras": [
        "Preto e branco sao as cores principais, usadas com prioridade",
        "Usar apenas 1 cor de iniciativa por peca, combinada com preto e branco",
        "Nunca misturar duas cores de iniciativas na mesma peca"
      ]
    },
    "tipografia": {
      "primaria": {
        "familia": "Supreme",
        "peso_padrao": "Regular",
        "disponivel_google_fonts": true,
        "fallback": "IBM Plex Sans"
      },
      "hierarquia": {
        "titulo": {"caixa": "ALTA", "tamanho_relativo": "X", "posicao": "topo-esquerda"},
        "texto_principal": {"caixa": "normal", "tamanho_relativo": "X/2"},
        "texto_secundario": {"caixa": "normal", "tamanho_relativo": "2X/3"}
      }
    },
    "grid": {
      "quadrado": {"colunas": 2, "linhas": 2, "quando_usar": "Pecas quadradas"},
      "retangular": {"colunas": 2, "linhas": 3, "quando_usar": "Pecas retangulares"},
      "regras": ["Textos, imagens e grafismos enquadrados nas areas do grid"]
    },
    "grafismo": {
      "origem": "Abstracao das formas do logotipo",
      "tipo": "Padronagem geometrica",
      "modulos": 8,
      "repeticao": ["vertical", "horizontal"],
      "uso": "Elemento decorativo de apoio, recortado em modulos e repetido"
    },
    "estilo_composicao": {
      "mood": "Minimalista, alto contraste, futurista sobrio",
      "abordagem": "Espacos abertos, tipografia forte, grafismos geometricos",
      "principios": [
        "Menos e mais - evitar poluicao visual",
        "Espacos vazios sao intencionais",
        "Contraste forte entre texto e fundo",
        "Movimento pulsante e modular"
      ]
    }
  }
}
```

### Body (erro)

```json
{
  "brandguide_id": 15,
  "status": "error",
  "error_message": "Descricao do erro aqui"
}
```

### Categorias validas

`capa`, `indice`, `logotipo`, `tipografia`, `cores`, `grafismo`, `grid`, `aplicacoes`, `informacional`, `outro`

### Relevancias validas

`high` (pagina-chave), `medium` (apoio), `low` (capa/indice/vazia)

---

## 4. Etapa 1 — Callback Mock (sem IA)

**Objetivo:** validar que o loop IAMKT → N8N → IAMKT funciona.
**Status:** ✅ VALIDADO

### Estrutura

```
[Webhook] → [Respond to Webhook] → [Code (mock)] → [HTTP Request (callback)]
```

### 4.1 — Webhook

| Campo | Valor |
|-------|-------|
| HTTP Method | POST |
| Path | `analyze_brandguide` |
| Respond | `Using 'Respond to Webhook' Node` |

### 4.2 — Respond to Webhook

| Campo | Valor |
|-------|-------|
| Respond With | JSON |
| Response Body | `{ "accepted": true }` |
| Response Code | 200 |

### 4.3 — Code (mock)

```javascript
const input = $('Webhook').first().json.body;

return {
  json: {
    brandguide_id: input.brandguide_id,
    callback_url: input.callback_url,
    status: 'completed',
    page_classifications: input.pages.map(p => ({
      page_number: p.page_number,
      category: 'outro',
      relevance: 'medium'
    })),
    suggested_kb_fields: {
      nome_empresa: 'TESTE N8N - callback funcionou!',
      posicionamento: 'Mock gerado pelo N8N sem IA real'
    },
    brand_visual_spec: {
      versao: '1.0-mock',
      cores: {
        institucional: [
          { nome: 'Preto Mock', hex: '#000000', uso: 'Teste' },
          { nome: 'Branco Mock', hex: '#FFFFFF', uso: 'Teste' }
        ]
      },
      tipografia: {
        primaria: { familia: 'Supreme', peso_padrao: 'Regular' }
      }
    }
  }
};
```

### 4.4 — HTTP Request (callback)

| Campo | Valor |
|-------|-------|
| Method | POST |
| URL | `={{ $json.callback_url }}` |
| Send Headers | ON |
| Header 1 | `X-INTERNAL-TOKEN` = `<valor de N8N_WEBHOOK_SECRET>` |
| Header 2 | `Content-Type` = `application/json` |
| Send Body | ON |
| Body Content Type | JSON |
| Specify Body | Using JSON |

**JSON Body (copiar e colar):**

```
={{ JSON.stringify({
  brandguide_id: $json.brandguide_id,
  status: $json.status,
  page_classifications: $json.page_classifications,
  suggested_kb_fields: $json.suggested_kb_fields,
  brand_visual_spec: $json.brand_visual_spec
}) }}
```

---

## 5. Etapa 2 — Triagem de Paginas com IA

**Objetivo:** classificar cada pagina por categoria usando gpt-4.1-mini com Vision.
**Custo:** ~$0.01 por PDF de 60 paginas.

### Estrutura

```
[Webhook] → [Respond] → [Code: prep triagem] → [HTTP Request: OpenAI] → [Code: callback] → [HTTP Request: callback]
```

**IMPORTANTE:** Usamos HTTP Request direto para a API OpenAI (nao o no nativo) porque
precisamos de Vision (enviar imagem + texto na mesma mensagem).

### 5.1 — Code: Preparar chamada de triagem

Este no recebe as paginas do webhook e monta o payload para a API OpenAI.
Envia TODAS as paginas de uma vez com detalhamento `low` (economico).

**Copiar e colar no no Code:**

```javascript
// =====================================================
// NO: "Preparar chamada de triagem"
// ENTRADA: recebe dados do Webhook
// SAIDA: payload formatado para a API OpenAI
// =====================================================

const input = $('Webhook').first().json.body;
const pages = input.pages || [];

// Montar mensagens multimodal: uma imagem por pagina + texto extraido
const userContent = [];

// Instrucao inicial
userContent.push({
  type: "text",
  text: `Analise este brandguide de ${pages.length} paginas. Para CADA pagina, retorne a classificacao.`
});

// Cada pagina: imagem + texto (max 30 paginas por request para nao estourar contexto)
const pagesToAnalyze = pages.slice(0, 30);

for (const page of pagesToAnalyze) {
  userContent.push({
    type: "image_url",
    image_url: {
      url: page.s3_url,
      detail: "low"
    }
  });
  userContent.push({
    type: "text",
    text: `--- Pagina ${page.page_number} ---\nTexto extraido: ${(page.extracted_text || '(sem texto)').substring(0, 200)}`
  });
}

// Se tem mais de 30 paginas, classificar o resto apenas pelo texto
const remainingPages = pages.slice(30);
if (remainingPages.length > 0) {
  userContent.push({
    type: "text",
    text: `\n\nAs paginas ${31} a ${pages.length} nao tem imagem. Classifique pelo texto:\n` +
      remainingPages.map(p =>
        `Pagina ${p.page_number}: ${(p.extracted_text || '(sem texto)').substring(0, 150)}`
      ).join('\n')
  });
}

const openaiPayload = {
  model: "gpt-4.1-mini",
  messages: [
    {
      role: "system",
      content: `Voce e um analista especializado em brandguides/manuais de identidade visual.

Sua tarefa: classificar CADA pagina do brandguide em uma categoria e uma relevancia.

CATEGORIAS (escolha exatamente UMA por pagina):
- capa: pagina de capa, titulo do documento
- indice: sumario, indice, lista de secoes
- logotipo: variações do logo, area de seguranca, reducao minima, submarcas
- tipografia: fontes da marca, hierarquia tipografica, pesos, estilos
- cores: paleta de cores, codigos hex/RGB, regras de uso de cor
- grafismo: padronagens, elementos graficos, modulos decorativos
- grid: grade de construcao, sistema de layout, posicionamento de elementos
- aplicacoes: exemplos de uso (cartao, garrafa, poster, mockup, social media)
- informacional: textos explicativos gerais, creditos, contatos
- outro: nao se encaixa em nenhuma categoria acima

RELEVANCIA:
- high: pagina essencial para entender a identidade visual (cores, tipografia, grid, grafismo, logotipo principal)
- medium: pagina de apoio (variações de logo, exemplos, textos complementares)
- low: pagina sem informacao visual util (capa, indice, creditos, paginas vazias)

REGRAS:
- Responda APENAS com JSON valido, sem markdown, sem explicacao
- O JSON deve ser um array com um objeto por pagina
- Cada objeto tem: page_number (int), category (string), relevance (string)

Exemplo de resposta:
[
  {"page_number": 1, "category": "capa", "relevance": "low"},
  {"page_number": 2, "category": "logotipo", "relevance": "high"}
]`
    },
    {
      role: "user",
      content: userContent
    }
  ],
  max_tokens: 4000,
  temperature: 0.1,
  response_format: { type: "json_object" }
};

return {
  json: {
    openai_payload: openaiPayload,
    webhook_data: {
      brandguide_id: input.brandguide_id,
      callback_url: input.callback_url,
      pages: input.pages,
      existing_kb: input.existing_kb
    }
  }
};
```

### 5.2 — HTTP Request: Chamada OpenAI (triagem)

| Campo | Valor |
|-------|-------|
| Method | POST |
| URL | `https://api.openai.com/v1/chat/completions` |
| Authentication | Predefined Credential Type → OpenAI API |
| **OU** Authentication | Generic → Header Auth |
| Header Auth Name | `Authorization` |
| Header Auth Value | `Bearer sk-SUACHAVEOPENAI` |
| Send Headers | ON |
| Header 1 | `Content-Type` = `application/json` |
| Send Body | ON |
| Body Content Type | JSON |
| Specify Body | Using JSON |

**JSON Body (expressao):**

```
={{ JSON.stringify($json.openai_payload) }}
```

### 5.3 — Code: Processar resultado da triagem + preparar analise profunda

Este no pega o resultado do GPT-4.1-mini (triagem), filtra paginas relevantes
e prepara a chamada de analise profunda com GPT-4o.

**Copiar e colar:**

```javascript
// =====================================================
// NO: "Processar resultado da triagem"
// ENTRADA: resposta da OpenAI (triagem) via "Chamada OpenAI (triagem)"
// SAIDA: classificacoes + payload para analise profunda
// =====================================================

const webhookData = $('Preparar chamada de triagem').first().json.webhook_data;
const openaiResponse = $('Chamada OpenAI (triagem)').first().json;

// Parsear classificacoes da triagem
let classifications = [];
try {
  const content = openaiResponse.choices?.[0]?.message?.content || '[]';
  const parsed = JSON.parse(content);
  // Pode vir como array direto ou como { classifications: [...] }
  classifications = Array.isArray(parsed) ? parsed : (parsed.classifications || parsed.pages || []);
} catch(e) {
  // Fallback: classificar tudo como 'outro'
  classifications = webhookData.pages.map(p => ({
    page_number: p.page_number,
    category: 'outro',
    relevance: 'medium'
  }));
}

// Filtrar paginas com relevance=high para analise profunda
const highPages = classifications.filter(c => c.relevance === 'high');
const highPageNumbers = new Set(highPages.map(c => c.page_number));

// Pegar URLs das paginas relevantes (max 20 para controlar custo)
const relevantPages = webhookData.pages
  .filter(p => highPageNumbers.has(p.page_number))
  .slice(0, 20);

// Montar payload para analise profunda (GPT-4o Vision)
const userContent = [];

userContent.push({
  type: "text",
  text: `Analise estas ${relevantPages.length} paginas-chave de um brandguide. ` +
    `Elas foram identificadas como as mais relevantes de um total de ${webhookData.pages.length} paginas. ` +
    `A empresa se chama "${webhookData.existing_kb?.nome_empresa || 'nao informado'}".`
});

for (const page of relevantPages) {
  userContent.push({
    type: "image_url",
    image_url: {
      url: page.s3_url,
      detail: "high"
    }
  });
  userContent.push({
    type: "text",
    text: `--- Pagina ${page.page_number} (${highPages.find(c => c.page_number === page.page_number)?.category || 'outro'}) ---\n${(page.extracted_text || '').substring(0, 500)}`
  });
}

const deepPayload = {
  model: "gpt-4o",
  messages: [
    {
      role: "system",
      content: `Voce e um diretor de arte e estrategista de marca senior com 20 anos de experiencia.

Sua tarefa: analisar as paginas-chave de um brandguide (manual de identidade visual) e extrair TODAS as informacoes em um JSON estruturado.

VOCE DEVE RETORNAR EXATAMENTE ESTE FORMATO JSON (preencha todos os campos):

{
  "suggested_kb_fields": {
    "nome_empresa": "Nome completo da empresa/marca conforme aparece no brandguide",
    "posicionamento": "Como a marca se posiciona - descreva baseado no tom visual, nas escolhas tipograficas e na estetica geral. Seja especifico.",
    "diferenciais": "O que torna esta marca visualmente unica. Identifique elementos diferenciadores.",
    "proposta_valor": "Qual valor a marca transmite visualmente. O que ela promete ao publico.",
    "tom_voz_externo": "Descreva o tom de comunicacao que a identidade visual sugere: formal/informal, tecnico/acessivel, serio/descontraido, minimalista/exuberante.",
    "palavras_recomendadas": ["lista", "de", "palavras", "que", "combinam", "com", "o", "posicionamento"],
    "palavras_evitar": ["lista", "de", "palavras", "que", "nao", "combinam"]
  },
  "brand_visual_spec": {
    "versao": "1.0",
    "logo": {
      "variacoes": ["liste todas as variacoes encontradas: preferencial, vertical, horizontal, contracao, reduzida, icone, monocromatico"],
      "descricao_visual": "Descreva o logotipo em detalhes: formas, aberturas, peso visual, estilo",
      "area_seguranca": "Descreva a regra de area de seguranca se encontrada no brandguide",
      "reducao_minima_digital_px": 0,
      "reducao_minima_impresso_mm": 0
    },
    "cores": {
      "institucional": [
        {
          "nome": "Nome da cor conforme o brandguide",
          "hex": "#RRGGBB",
          "uso": "Quando e como usar esta cor"
        }
      ],
      "iniciativas": [
        {
          "nome": "Nome da cor",
          "hex": "#RRGGBB",
          "uso": "Quando usar"
        }
      ],
      "regras": [
        "Escreva CADA regra de uso de cor encontrada no brandguide",
        "Ex: 'Usar apenas 1 cor de destaque por peca'",
        "Ex: 'Sempre combinar com preto e branco'"
      ]
    },
    "tipografia": {
      "primaria": {
        "familia": "Nome exato da fonte principal",
        "peso_padrao": "Regular/Bold/Light/etc",
        "disponivel_google_fonts": true,
        "fallback": "Nome da fonte alternativa (se mencionada no brandguide)"
      },
      "secundaria": {
        "familia": "Nome da fonte secundaria (se houver)",
        "peso_padrao": "Regular",
        "uso": "Para que e usada (corpo de texto, destaques, etc)"
      },
      "hierarquia": {
        "titulo": {
          "fonte": "Nome da fonte usada em titulos",
          "caixa": "ALTA ou normal",
          "tamanho_relativo": "X (base para calculo dos demais)",
          "posicao": "Posicao preferencial no layout (ex: topo-esquerda)"
        },
        "texto_principal": {
          "fonte": "Nome",
          "caixa": "normal",
          "tamanho_relativo": "proporcao em relacao ao titulo (ex: X/2)"
        },
        "texto_secundario": {
          "fonte": "Nome",
          "caixa": "normal",
          "tamanho_relativo": "proporcao (ex: 2X/3)"
        }
      }
    },
    "grid": {
      "quadrado": {
        "colunas": 2,
        "linhas": 2,
        "quando_usar": "Pecas quadradas ou com proporcoes proximas"
      },
      "retangular": {
        "colunas": 2,
        "linhas": 3,
        "quando_usar": "Pecas retangulares (2x no menor, 3x no maior)"
      },
      "regras": [
        "Regras de posicionamento encontradas no brandguide",
        "Ex: 'Titulos no topo a esquerda'"
      ]
    },
    "grafismo": {
      "origem": "De onde vem o grafismo (ex: abstracao das formas do logotipo)",
      "tipo": "Tipo do grafismo (padronagem geometrica, organica, linhas, etc)",
      "modulos": 0,
      "repeticao": ["vertical", "horizontal"],
      "uso": "Como e onde usar (overlay, fundo, moldura, etc)",
      "descricao_visual": "Descreva visualmente como sao os modulos: formas, aberturas, espessura de linhas, estilo geometrico",
      "aplicacoes_layout": [
        {
          "formato": "nome do formato (ex: feed_retangular, story, quadrado)",
          "grid": "grid usado (ex: 2x3, 2x2)",
          "posicao_grafismo": "Onde o grafismo fica no layout (ex: coluna direita ocupando 2/3 da altura)",
          "relacao_com_texto": "Como grafismo se relaciona com o texto (ex: ao lado, atras, nunca sobrepoe)",
          "cor_grafismo": "Cor usada no grafismo neste exemplo (ex: cor de iniciativa sobre fundo preto)",
          "exemplo_pagina": 0
        }
      ],
      "regras_aplicacao": [
        "COPIE cada regra de uso do grafismo encontrada no brandguide",
        "Ex: Grafismo sempre ocupa uma area do grid, nunca sobrepoe texto",
        "Ex: Usar apenas 1 modulo por peca",
        "Ex: Cor do grafismo segue a cor de iniciativa escolhida para a peca"
      ]
    },
    "estilo_composicao": {
      "mood": "Descricao do mood/atmosfera geral: ex 'minimalista e futurista'",
      "abordagem": "Abordagem de design: ex 'espacos abertos com tipografia forte'",
      "principios": [
        "COPIE cada principio de composicao encontrado no brandguide",
        "Ex: Espacos vazios sao intencionais e fazem parte do design",
        "Ex: Titulos e chamadas no topo a esquerda",
        "Ex: Texto principal posicionado apos titulo",
        "Ex: Texto secundario e flexivel, funciona como apoio"
      ]
    }
  }
}

REGRAS CRITICAS:
1. CORES: Extraia TODOS os codigos HEX que aparecem nos SWATCHES OFICIAIS da paleta.
   - NAO extraia cores de fotos, mockups ou exemplos de aplicacao
   - Leia o HEX diretamente dos quadrados/circulos de cor da paleta
   - Inclua TODAS: institucional (preto, branco) E iniciativas/destaque (cada cor separada)
   - Se o brandguide mostra exemplos "Preto + Azul", "Preto + Verde", extraia CADA cor individual
2. NOME EMPRESA: Use o nome que aparece NO BRANDGUIDE, NAO o valor de existing_kb
3. TIPOGRAFIA: Identifique a fonte PRINCIPAL e tambem a fonte de APOIO/FALLBACK
   - Se menciona "na impossibilidade de usar X, use Y", Y e o fallback
4. GRID: Copie dimensoes exatas e TODAS as regras de posicionamento
5. GRAFISMO - MUITO IMPORTANTE:
   - Descreva visualmente como sao os modulos (formas, estilo)
   - Para cada EXEMPLO DE LAYOUT no brandguide (paginas de "exemplos de grade"),
     descreva: onde o grafismo fica, em qual grid, com qual cor, relacao com texto
   - Copie TODAS as regras de aplicacao do grafismo
   - Essas informacoes serao usadas por um agente de IA para gerar imagens de posts
6. ESTILO COMPOSICAO: Copie os principios de composicao LITERALMENTE como escritos
7. Retorne APENAS JSON valido, sem markdown
8. Se nao encontrar algo, use null (nao invente)`
    },
    {
      role: "user",
      content: userContent
    }
  ],
  max_tokens: 6000,
  temperature: 0.2,
  response_format: { type: "json_object" }
};

return {
  json: {
    deep_payload: deepPayload,
    classifications: classifications,
    webhook_data: webhookData
  }
};
```

### 5.4 — HTTP Request: Chamada OpenAI (analise profunda)

| Campo | Valor |
|-------|-------|
| Method | POST |
| URL | `https://api.openai.com/v1/chat/completions` |
| Authentication | Mesma credential da triagem |
| Send Body | ON → JSON |

**JSON Body:**

```
={{ JSON.stringify($json.deep_payload) }}
```

**Options → Timeout:** `120000` (2 min — analise profunda pode demorar)

### 5.5 — Code: Montar payload final para callback (com tokens)

Este no combina tudo e inclui o rastreamento de tokens consumidos.

**Copiar e colar:**

```javascript
// =====================================================
// NO: "Montar payload final"
// ENTRADA: resposta da OpenAI (analise profunda) via "Chamada OpenAI (analise profunda)"
// SAIDA: payload completo para callback incluindo tokens consumidos
// =====================================================

// Dados dos nos anteriores (pelos nomes exatos)
const webhookData = $('Preparar chamada de triagem').first().json.webhook_data;
const classifications = $('Processar resultado da triagem').first().json.classifications;
const deepResponse = $('Chamada OpenAI (analise profunda)').first().json;

// Parsear resultado da analise profunda
let analysisResult = {};
try {
  const content = deepResponse.choices?.[0]?.message?.content || '{}';
  analysisResult = JSON.parse(content);
} catch(e) {
  analysisResult = {};
}

// ===== CAPTURA DE TOKENS =====
// A API OpenAI retorna 'usage' em cada response

// Tokens da triagem (do HTTP Request 1)
let triagemUsage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
try {
  const triagemResponse = $('Chamada OpenAI (triagem)').first().json;
  triagemUsage = triagemResponse.usage || triagemUsage;
} catch(e) {}

// Tokens da analise profunda (do HTTP Request 2)
const deepUsage = deepResponse.usage || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

// Pricing por 1M tokens (atualizar quando mudar)
const PRICING = {
  'gpt-4.1-mini': { input: 0.40, output: 1.60 },
  'gpt-4o':       { input: 2.50, output: 10.00 },
};

function estimateCost(usage, model) {
  const p = PRICING[model] || { input: 0, output: 0 };
  return {
    input_cost:  (usage.prompt_tokens / 1_000_000) * p.input,
    output_cost: (usage.completion_tokens / 1_000_000) * p.output,
    total_cost:  ((usage.prompt_tokens / 1_000_000) * p.input) +
                 ((usage.completion_tokens / 1_000_000) * p.output),
  };
}

const triagemCost = estimateCost(triagemUsage, 'gpt-4.1-mini');
const analiseCost = estimateCost(deepUsage, 'gpt-4o');

const ai_usage = {
  triagem: {
    model: 'gpt-4.1-mini',
    prompt_tokens: triagemUsage.prompt_tokens,
    completion_tokens: triagemUsage.completion_tokens,
    total_tokens: triagemUsage.total_tokens,
    estimated_cost_usd: Math.round(triagemCost.total_cost * 10000) / 10000,
  },
  analise: {
    model: 'gpt-4o',
    prompt_tokens: deepUsage.prompt_tokens,
    completion_tokens: deepUsage.completion_tokens,
    total_tokens: deepUsage.total_tokens,
    estimated_cost_usd: Math.round(analiseCost.total_cost * 10000) / 10000,
  },
  total: {
    total_tokens: triagemUsage.total_tokens + deepUsage.total_tokens,
    estimated_cost_usd: Math.round((triagemCost.total_cost + analiseCost.total_cost) * 10000) / 10000,
  },
  timestamp: new Date().toISOString(),
};

return {
  json: {
    brandguide_id: webhookData.brandguide_id,
    callback_url: webhookData.callback_url,
    status: 'completed',
    page_classifications: classifications,
    suggested_kb_fields: analysisResult.suggested_kb_fields || {},
    brand_visual_spec: analysisResult.brand_visual_spec || null,
    ai_usage: ai_usage,
  }
};
```

### 5.6 — HTTP Request: Callback para IAMKT

| Campo | Valor |
|-------|-------|
| Method | POST |
| URL | `={{ $json.callback_url }}` |
| Header | `X-INTERNAL-TOKEN` = `<N8N_WEBHOOK_SECRET>` |
| Header | `Content-Type` = `application/json` |
| Body | JSON → Using JSON |

**JSON Body (copiar e colar):**

```
={{ JSON.stringify({
  brandguide_id: $json.brandguide_id,
  status: $json.status,
  page_classifications: $json.page_classifications,
  suggested_kb_fields: $json.suggested_kb_fields,
  brand_visual_spec: $json.brand_visual_spec,
  ai_usage: $json.ai_usage
}) }}
```

---

## 6. Etapa 3 — Workflow Completo (Producao)

Apos validar as etapas anteriores, o workflow de producao fica assim:

```
[Webhook]
    │
[Respond to Webhook] → 200 OK
    │
[Code 1: Preparar triagem]
    │  Monta payload multimodal para GPT-4.1-mini
    │  Todas as paginas com detail=low
    ▼
[HTTP Request 1: OpenAI Triagem]
    │  POST api.openai.com → gpt-4.1-mini
    │  Retorna: classificacao por pagina
    ▼
[Code 2: Filtrar + preparar analise]
    │  Filtra paginas com relevance=high
    │  Monta payload multimodal para GPT-4o
    │  So paginas relevantes com detail=high
    ▼
[HTTP Request 2: OpenAI Analise]
    │  POST api.openai.com → gpt-4o
    │  Retorna: suggested_kb_fields + brand_visual_spec
    ▼
[Code 3: Montar payload final]
    │  Combina triagem + analise
    ▼
[HTTP Request 3: Callback IAMKT]
    │  POST callback_url com resultado
    ▼
    FIM
```

**Total de nos: 7** (Webhook, Respond, Code×3, HTTP Request×3)

---

## 7. Tratamento de Erros

Adicionar um no **Error Trigger** ao workflow. Conectar a um Code + HTTP Request
que envia o callback de erro para o IAMKT.

### Error Trigger → Code (erro) → HTTP Request (callback erro)

**No Code (nome sugerido: "Preparar callback de erro") — copiar e colar:**

```javascript
// =====================================================
// NO: "Preparar callback de erro"
// ENTRADA: Error Trigger (captura qualquer falha do workflow)
// SAIDA: payload de erro para callback
// =====================================================

let brandguideId = null;
let callbackUrl = null;

try {
  brandguideId = $('Webhook').first().json.body?.brandguide_id;
  callbackUrl = $('Webhook').first().json.body?.callback_url;
} catch(e) {}

const errorInfo = $input.first().json;
const errorMessage = errorInfo.message || errorInfo.description || JSON.stringify(errorInfo).substring(0, 500);

return {
  json: {
    brandguide_id: brandguideId,
    status: 'error',
    error_message: 'Erro no workflow N8N: ' + errorMessage,
    callback_url: callbackUrl || 'https://app.iamkt.com.br/knowledge/webhook/brandguide/'
  }
};
```

**HTTP Request (nome sugerido: "Callback erro para IAMKT") — mesma config do "Callback para IAMKT" (secao 5.6):**

```
={{ JSON.stringify({
  brandguide_id: $json.brandguide_id,
  status: $json.status,
  error_message: $json.error_message
}) }}
```

---

## 8. Como Testar

### Verificar env configurada

```bash
docker compose exec iamkt_web python manage.py shell -c "
from django.conf import settings
print('WEBHOOK:', settings.N8N_WEBHOOK_ANALYZE_BRANDGUIDE)
print('SITE_URL:', settings.SITE_URL)
print('SECRET:', settings.N8N_WEBHOOK_SECRET[:10] + '...')
"
```

### Fazer upload de teste

1. Abrir https://app.iamkt.com.br/knowledge/ ou /knowledge/perfil/
2. No Bloco 5, subir um PDF
3. Status esperado: `Processando documento` → `Analisando com IA` → `Processamento concluido`

### Logs de debug

```bash
# Celery → ver task e chamada ao N8N
docker compose logs iamkt_celery_brandguide -f | grep brandguide

# Web → ver callback chegando
docker compose logs iamkt_web -f | grep brandguide_cb
```

### Verificar resultado no banco

```bash
docker compose exec iamkt_web python manage.py shell -c "
from apps.knowledge.models import KnowledgeBase
kb = KnowledgeBase.objects.get(organization_id=23)
import json
if kb.brand_visual_spec:
    print('BRAND VISUAL SPEC:')
    print(json.dumps(kb.brand_visual_spec, indent=2, ensure_ascii=False)[:2000])
if kb.n8n_analysis and kb.n8n_analysis.get('brandguide'):
    print()
    print('SUGGESTED FIELDS:')
    print(json.dumps(kb.n8n_analysis['brandguide']['suggested_fields'], indent=2, ensure_ascii=False)[:1000])
"
```

---

## 9. Custos por Chamada

| Etapa | Modelo | Paginas | Tokens | Custo |
|-------|--------|---------|--------|-------|
| Triagem | gpt-4.1-mini | 60 (low) | ~7.000 | ~$0.01 |
| Analise | gpt-4o | 15-20 (high) | ~35.000 | ~$0.10 |
| **Total** | | | | **~$0.11** |

### Projecao mensal

| Clientes/mes | Custo analise |
|-------------|---------------|
| 10 | ~$1.10 |
| 50 | ~$5.50 |
| 200 | ~$22.00 |

---

## 10. Troubleshooting

### N8N retorna 500 no webhook

- Workflow nao esta ativado (toggle ON no canto superior direito)
- Nos nao estao conectados corretamente
- Webhook configurado como "Respond: Immediately" mas tem no "Respond to Webhook" no workflow

### Callback retorna 401

- `X-INTERNAL-TOKEN` no HTTP Request deve ser = `N8N_WEBHOOK_SECRET` do `.env` do IAMKT
- IP do N8N precisa estar em `N8N_ALLOWED_IPS` no `.env` do IAMKT

### Status preso em "Analisando com IA"

N8N nao fez callback. Verificar:
1. Executions no N8N (algum no falhou?)
2. Error Trigger nao configurado (callback de erro nunca foi enviado)

Fix manual:
```bash
docker compose exec iamkt_web python manage.py shell -c "
from apps.knowledge.models import BrandguideUpload
bg = BrandguideUpload.objects.filter(processing_status='analyzing').first()
if bg:
    bg.processing_status = 'error'
    bg.error_message = 'Timeout: N8N nao retornou'
    bg.save()
    print(f'Corrigido bg.id={bg.id}')
"
```

### OpenAI retorna erro de token/rate limit

- Verificar credencial OpenAI no N8N
- Verificar se tem saldo na conta OpenAI
- gpt-4o tem rate limit mais apertado que gpt-4.1-mini
- Timeout da chamada pode ser curto (aumentar para 120s)

### Brandguide vai direto para completed (sem analisar)

`N8N_WEBHOOK_ANALYZE_BRANDGUIDE` vazio no `.env`. Adicionar e recriar containers:
```bash
echo 'N8N_WEBHOOK_ANALYZE_BRANDGUIDE=https://...' >> .env
docker compose down iamkt_web iamkt_celery_brandguide
docker compose up -d iamkt_web iamkt_celery_brandguide
```
