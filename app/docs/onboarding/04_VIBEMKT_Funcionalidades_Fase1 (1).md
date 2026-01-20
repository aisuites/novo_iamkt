# 🚀 IAMKT - FUNCIONALIDADES FASE 1

**Documento:** 04 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 FUNCIONALIDADES PRIORITÁRIAS - MVP

Fase 1 foca em:
1. ✅ **Geração de Pautas**
2. ✅ **Geração de Posts** (imagem + legenda)
3. ✅ **Simulador de Feed** (DIFERENCIAL CRÍTICO)
4. ✅ **Monitoramento de Trends**
5. ✅ **Pesquisa Web e Insights**

---

## 📝 1. GERAÇÃO DE PAUTAS

### Objetivo
Gerar ideias de conteúdo relevantes e alinhadas com a marca FEMME.

### Inputs do Usuário

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Tema** | Texto | ✅ | Tema principal ou palavra-chave |
| **Público-alvo** | Seleção | ✅ | Externo / Interno (da Base FEMME) |
| **Objetivo** | Seleção | ✅ | educar / converter / engajar |
| **Projeto/Campanha** | Seleção | ✅ | Vincular a projeto existente ou criar "Avulso" |
| **Modelo IA** | Seleção | ✅ | OpenAI / Gemini / Grok |

### Fluxo de Processamento

```
1. Usuário preenche formulário
   │
2. Sistema busca Base FEMME
   ├─> Identidade institucional
   ├─> Tom de voz
   ├─> Posicionamento
   ├─> Público-alvo (externo ou interno conforme seleção)
   └─> Fontes de pesquisa confiáveis (URLs pré-definidas)
   │
3. Pesquisa em duas frentes (paralelo)
   │
   ├─> A) Fontes Confiáveis (da Base FEMME)
   │   ├─> Scrape URLs pré-definidas
   │   └─> Extrai informações relevantes ao tema
   │
   └─> B) Pesquisa Web Genérica
       ├─> Google Search API ou scraping
       ├─> Busca: "{tema} {nicho FEMME}"
       └─> Extrai top 5-10 resultados
   │
4. Consulta trends recentes relacionados ao tema
   │
5. Monta prompt estruturado
   ├─> Tema do usuário
   ├─> Objetivo
   ├─> Público selecionado (externo/interno)
   ├─> Contexto da Base FEMME
   ├─> Informações das fontes confiáveis
   ├─> Informações da pesquisa web genérica
   └─> Trends relevantes
   │
6. Celery Task assíncrona
   ├─> Verifica cache Redis (hash do prompt)
   ├─> Se não existe: chama API IA
   ├─> IA gera 5-10 sugestões de pautas
   └─> Salva em cache (TTL 7 dias)
   │
7. Retorna resultado para usuário
   │
8. Usuário visualiza pautas
   ├─> Pode ver fontes pesquisadas
   ├─> Pode validar informações nas fontes
   ├─> Pode editar
   ├─> Pode marcar como favorita
   └─> Pode salvar no histórico
```

### Output

**Estrutura de cada pauta:**
```json
{
  "titulo": "Como manter a saúde cardiovascular após os 40",
  "descricao": "Artigo educativo sobre prevenção de doenças cardíacas",
  "formato_sugerido": "blog",
  "palavras_chave_seo": ["saúde cardiovascular", "prevenção", "exames cardiológicos"],
  "publico_alvo": "Externo",
  "tom_sugerido": "educativo e acolhedor",
  "fontes_pesquisadas": [
    {
      "url": "https://fonte-confiavel1.com.br/artigo",
      "titulo": "Prevenção Cardiovascular",
      "tipo": "fonte_confiavel"
    },
    {
      "url": "https://resultado-google.com/info",
      "titulo": "Estatísticas sobre saúde cardíaca",
      "tipo": "web_generica"
    }
  ]
}
```

**Interface:**
- Lista de cards com título + descrição
- **NOVO**: Seção "Fontes Pesquisadas" expansível em cada card
  - Links clicáveis para validação
  - Badge indicando se é "Fonte Confiável" ou "Web Genérica"
- Botão "Editar" em cada pauta
- Botão "Favoritar" (estrela)
- Botão "Usar esta pauta" (cria conteúdo baseado nela)

---

## 🎨 2. GERAÇÃO DE POSTS (IMAGEM + LEGENDA)

### Objetivo
Criar posts completos para redes sociais com imagem gerada por IA e legenda alinhada com a marca.

### Inputs do Usuário

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Tema/Mensagem** | Texto | ✅ | Mensagem principal do post |
| **Rede Social** | Seleção | ✅ | Instagram / LinkedIn / Facebook / YouTube / etc |
| **Template** | Seleção | ✅ | Feed 1:1 / Feed 4:5 / Stories / etc (dinâmico por rede) |
| **Estilo Imagem** | Seleção | ✅ | fotográfico / ilustração / abstrato / minimalista |
| **Modo de Geração** | Seleção | ✅ | API (automático) / Prompt Manual |
| **Modelo IA** | Seleção | ✅ | OpenAI (DALL-E 3) / Gemini |
| **Projeto/Campanha** | Seleção | ✅ | Vincular a projeto existente |

**Modo de Geração:**
- **API (automático)**: Sistema chama API e gera imagem direto
- **Prompt Manual**: Sistema gera prompt otimizado, usuário copia e usa no ChatGPT/Gemini diretamente

### Templates Disponíveis

#### Instagram
- **Feed 1:1**: 1080x1080px
- **Feed 4:5**: 1080x1350px (vertical)
- **Stories**: 1080x1920px (9:16)

#### LinkedIn
- **Feed**: 1200x627px

#### Facebook
- **Feed**: 1200x630px

### Fluxo de Processamento

```
1. Usuário preenche formulário
   │
2. Sistema busca Base FEMME
   ├─> Paleta de cores (hex codes)
   ├─> Imagens de referência (estilo visual)
   ├─> Tom de voz para legenda
   └─> Palavras recomendadas/evitar
   │
3. Celery Task assíncrona
   │
   ├─> GERAÇÃO DE IMAGEM
   │   ├─> Monta prompt para imagem
   │   │   - Tema do usuário
   │   │   - Estilo visual escolhido
   │   │   - Cores FEMME (ex: "#6B2C91, #E91E63")
   │   │   - Referências de estilo
   │   │   - Dimensões corretas
   │   │
   │   ├─> Verifica cache (hash do prompt de imagem)
   │   ├─> Chama API (DALL-E 3 ou Gemini)
   │   ├─> Recebe imagem base64
   │   ├─> Upload para S3
   │   └─> Salva URL em GeneratedContent
   │
   └─> GERAÇÃO DE LEGENDA
       ├─> Monta prompt para texto
       │   - Tema do usuário
       │   - Tom de voz FEMME
       │   - Palavras recomendadas
       │   - Limite de caracteres (por rede social)
       │   - Incluir hashtags
       │
       ├─> Chama API IA (texto)
       ├─> Gera legenda + hashtags
       └─> Salva em GeneratedContent
   │
4. Retorna preview completo
   │
5. Usuário visualiza no Simulador de Feed
```

### Output

**Estrutura do conteúdo gerado:**
```json
{
  "imagem_url": "https://s3.../generated/post_123.png",
  "legenda": "Cuide do seu coração! Após os 40, exames regulares são essenciais...",
  "hashtags": ["#SaudeCardiovascular", "#Prevencao", "#FEMME"],
  "rede_social": "instagram",
  "template": "feed_1x1",
  "metadados": {
    "tokens_imagem": 0,
    "tokens_texto": 350,
    "custo_usd": 0.045,
    "tempo_geracao": 25.3
  }
}
```

**Interface:**
- Preview da imagem
- Legenda editável
- Contador de caracteres
- Botão "Regenerar imagem"
- Botão "Regenerar legenda"
- Botão "Ver no Simulador de Feed" ⭐
- Botão "Salvar"
- Botão "Enviar para Aprovação"

---

## 📱 3. SIMULADOR DE FEED

### ⭐ DIFERENCIAL CRÍTICO

**Funcionalidade tipo "Preview" app** - Permite montar um feed completo arrastando posts criados (ou fazendo upload de imagens externas) para dentro de um mockup de celular, visualizando como o feed ficará na rede social.

### Diferença Importante

**❌ NÃO É:** Preview individual de um único post  
**✅ É:** Montador de feed completo com múltiplos posts

### Como Funciona

#### 1. Workspace do Simulador

```
┌─────────────────────────────────────────────────────────┐
│  📱 Simulador de Feed - Instagram                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌───────────────────┐    ┌─────────────────────────┐  │
│  │   BIBLIOTECA      │    │    MOCKUP CELULAR       │  │
│  │   DE POSTS        │    │                         │  │
│  │                   │    │  ┌─────────────────┐   │  │
│  │  [Post 1] drag   │    │  │   @femme        │   │  │
│  │  [Post 2] drag   │    │  ├─────────────────┤   │  │
│  │  [Post 3] drag   │    │  │ ┌─────────────┐ │   │  │
│  │  [Post 4] drag   │    │  │ │  POST 1     │ │   │  │
│  │                   │    │  │ └─────────────┘ │   │  │
│  │  [+ Upload]      │◄──┼──┤  ♥ 💬 ➤          │   │  │
│  │  [+ Externo]     │    │  │                 │   │  │
│  │                   │    │  │ ┌─────────────┐ │   │  │
│  └───────────────────┘    │  │ │  POST 2     │ │   │  │
│                            │  │ └─────────────┘ │   │  │
│                            │  │  ♥ 💬 ➤          │   │  │
│                            │  │                 │   │  │
│                            │  │ ┌─────────────┐ │   │  │
│                            │  │ │  POST 3     │ │   │  │
│                            │  │ └─────────────┘ │   │  │
│                            │  └─────────────────┘   │  │
│                            └─────────────────────────┘  │
│                                                          │
│  [ Trocar Rede Social ] [ Salvar Feed ] [ Exportar ]   │
└─────────────────────────────────────────────────────────┘
```

#### 2. Biblioteca de Posts (Esquerda)

**Origem dos Posts:**
- ✅ Posts criados no sistema (com status aprovado)
- ✅ Upload de imagem externa (JPG/PNG)
- ✅ Posts de outros projetos/campanhas
- ✅ Filtros: por projeto, por data, por status

**Ações:**
- Arrastar para mockup (drag-and-drop)
- Preview rápido (hover)
- Editar antes de adicionar
- Marcar favoritos

#### 3. Mockup de Celular (Direita)

**Características:**
- Interface realista da rede social escolhida
- **Scroll vertical** no feed (para ver todos os posts adicionados)
- Reordenação: arrastar posts para mudar ordem
- Remover posts: arrasta de volta para biblioteca
- Zoom in/out no mockup

**Visualização por Rede:**

##### Instagram
```
┌───────────────────┐
│  @femme      ⋮    │
│  São Gonçalo      │
├───────────────────┤
│                   │
│   [IMAGEM POST]   │
│                   │
├───────────────────┤
│  ♥ 💬 ➤           │
│                   │
│  **femme** Texto  │
│  ... ver mais     │
│                   │
│  há 2 horas       │
├───────────────────┤
│  (scroll↓)        │
│                   │
│  [PRÓXIMO POST]   │
└───────────────────┘
```

##### LinkedIn
```
┌───────────────────┐
│  [Logo] FEMME     │
│  2.543 seguidores │
│  há 1 hora • 🌍   │
├───────────────────┤
│  Texto do post... │
│  ... ver mais     │
│                   │
│   [IMAGEM POST]   │
│                   │
├───────────────────┤
│  👍 💡 ❤️  125     │
│  10 comentários   │
├───────────────────┤
│  (scroll↓)        │
└───────────────────┘
```

#### 4. Upload de Imagem Externa

**Fluxo:**
```
1. Botão [+ Upload Externo]
   │
2. Seleciona imagem (JPG/PNG)
   │
3. Sistema analisa imagem
   ├─> Detecta dimensões
   ├─> Sugere rede social compatível
   └─> Ajusta se necessário
   │
4. Pede informações mínimas
   ├─> Legenda
   ├─> Rede social
   ├─> Projeto relacionado
   │
5. Adiciona à biblioteca
   │
6. Usuário arrasta para mockup
```

**Importante:** Imagens externas também podem ser agendadas/publicadas pelo sistema (Fase 2).

#### 5. Funcionalidades Avançadas

##### Comparação de Feeds
- Abrir 2+ mockups lado a lado
- Comparar "antes vs depois"
- Comparar diferentes estratégias de sequência

##### Simulação de Engajamento
- Adicionar números fictícios de likes/comentários
- Visualizar como post performando bem aparece
- Testar chamadas para ação

##### Export
- **Screenshot do feed**: Imagem PNG do mockup
- **Apresentação**: Gera PPTX com todos os posts em sequência
- **Compartilhar**: Link para visualização (sem edição)

### Benefícios

1. **Planejamento Visual**: Ver como sequência de posts funciona junto
2. **Consistência**: Identificar se cores/estilos estão harmônicos
3. **Apresentação para Gestores**: Mostrar proposta completa de feed
4. **Decisão Estratégica**: Qual ordem de posts gera melhor narrativa
5. **Flexibilidade**: Usar posts do sistema + externos

### Separação Importante

**Gestão de Posts Individuais**: 
- Local: `/content/posts/`
- Função: Criar, editar, aprovar posts isolados
- Foco: Qualidade individual de cada conteúdo

**Simulador de Feed**:
- Local: `/content/feed-simulator/`
- Função: Montar sequência, visualizar conjunto
- Foco: Harmonia e estratégia do feed completo

---

## 📈 4. MONITORAMENTO DE TRENDS

### Objetivo
Identificar tendências relevantes para o nicho FEMME automaticamente.

### Fontes de Dados

#### Padrões (Pré-configuradas)
- **Google Trends**: tópicos relacionados a saúde/medicina/exames
- **Think with Google**: insights de marketing
- **Reddit**: subreddits de saúde (/r/health, /r/medicine)
- **Twitter/X**: trending topics filtrados

#### Customizadas (Configuráveis)
- URLs específicas definidas pelo usuário
- RSS feeds
- APIs externas específicas

### Execução

#### Automática
**Celery Beat - Diariamente às 6h**

```python
@periodic_task(run_every=crontab(hour=6, minute=0))
def monitor_trends_daily():
    """
    Executa monitoramento de trends diariamente
    """
    # 1. Busca em cada fonte
    for fonte in FONTES_TRENDS:
        dados = scrape_fonte(fonte)
        
        # 2. Para cada trend encontrado
        for trend in dados:
            # 3. IA analisa relevância
            relevancia = analisar_relevancia_ia(
                trend, 
                base_femme=get_knowledge_base()
            )
            
            # 4. Se relevância > 70: salva
            if relevancia['score'] >= 70:
                TrendMonitor.objects.create(
                    fonte=fonte,
                    titulo=trend['titulo'],
                    relevancia_score=relevancia['score'],
                    analise_ia=relevancia['analise'],
                    sugestao_aproveitamento=relevancia['sugestao']
                )
                
                # 5. Se crítico (>90): envia alerta
                if relevancia['score'] >= 90:
                    enviar_alerta_email(trend)
```

#### Manual
- Botão "Buscar Trends Agora" no dashboard
- Executa mesma task, mas de forma on-demand
- Feedback visual: "Buscando trends..." com loading

### Interface

**Dashboard de Trends:**

```
┌─────────────────────────────────────────────────┐
│  🔍 Monitoramento de Trends                      │
│                                                  │
│  Última atualização: Hoje às 6:00               │
│  [ Buscar Trends Agora ]                        │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ 🔥 CRÍTICO (Score: 95)                   │   │
│  │ "Novo protocolo para exames cardíacos"  │   │
│  │                                          │   │
│  │ Fonte: Think with Google                │   │
│  │ Detectado: Hoje às 6:15                 │   │
│  │                                          │   │
│  │ 💡 Sugestão: Criar post educativo       │   │
│  │ sobre o novo protocolo...               │   │
│  │                                          │   │
│  │ [ Ver Detalhes ] [ Criar Pauta ]        │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ ⚠️ ALTO (Score: 82)                      │   │
│  │ "Aumento de buscas por check-up..."     │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

**Filtros:**
- [ Todos ] [ Críticos ] [ Altos ] [ Médios ]
- Por fonte: [ Google Trends ] [ Reddit ] [ Twitter ]
- Por data: [ Hoje ] [ Última semana ] [ Último mês ]

---

## 🔍 5. PESQUISA WEB E INSIGHTS

### Objetivo
Coletar informações atualizadas da web sobre temas específicos e gerar insights.

### Inputs do Usuário

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Pergunta/Tema** | Texto | ✅ | O que pesquisar |
| **URLs Específicas** | Lista | ❌ | URLs para analisar (opcional) |
| **Tipo de Insight** | Seleção | ✅ | concorrentes / mercado / tecnologia / geral |

### Fluxo de Processamento

```
1. Usuário define pesquisa
   │
2. Celery Task assíncrona
   │
   ├─> SCRAPING
   │   ├─> Se URLs específicas: scrape essas URLs
   │   ├─> Senão: busca Google + scrape top 10 resultados
   │   ├─> Playwright para sites dinâmicos
   │   └─> BeautifulSoup para HTML estático
   │
   ├─> EXTRAÇÃO E LIMPEZA
   │   ├─> Remove scripts, styles, ads
   │   ├─> Extrai texto principal
   │   └─> Identifica h1, h2, parágrafos importantes
   │
   ├─> ANÁLISE IA
   │   ├─> Envia textos extraídos para IA
   │   ├─> Prompt: "Analise e resuma insights sobre {tema}"
   │   ├─> IA identifica:
   │   │   - Principais achados
   │   │   - Oportunidades
   │   │   - Ameaças
   │   │   - Tendências
   │   └─> Cita fontes (URLs)
   │
   └─> GERAÇÃO DE RELATÓRIO
       ├─> Estrutura relatório em markdown
       ├─> Gera PDF (reportlab)
       ├─> Upload PDF para S3
       └─> Salva em WebInsight
   │
3. Retorna resultado para usuário
```

### Output

**Estrutura do Insight:**
```json
{
  "query": "Principais concorrentes em exames laboratoriais no Brasil",
  "resumo": "Análise identificou 5 principais players...",
  "insights": [
    {
      "categoria": "Concorrentes",
      "achados": ["Empresa X lidera com 30% market share...", ...],
      "fontes": ["https://fonte1.com", "https://fonte2.com"]
    },
    {
      "categoria": "Oportunidades",
      "achados": ["Crescimento de 15% em exames preventivos...", ...],
      "fontes": ["https://fonte3.com"]
    }
  ],
  "recomendacoes": [
    "Investir em campanhas sobre exames preventivos",
    "Diferenciar atendimento focado em agilidade"
  ]
}
```

**Interface:**

```
┌───────────────────────────────────────────────┐
│  🔍 Pesquisa Web: Concorrentes em Lab         │
├───────────────────────────────────────────────┤
│                                                │
│  📊 RESUMO                                     │
│  Análise identificou 5 principais players...  │
│                                                │
│  🎯 INSIGHTS                                   │
│                                                │
│  Concorrentes                                  │
│  • Empresa X lidera com 30% market share      │
│    Fonte: [site1.com]                         │
│  • Empresa Y foca em atendimento domiciliar   │
│    Fonte: [site2.com]                         │
│                                                │
│  Oportunidades                                 │
│  • Crescimento de 15% em exames preventivos   │
│    Fonte: [site3.com]                         │
│                                                │
│  💡 RECOMENDAÇÕES                              │
│  • Investir em campanhas sobre prevenção      │
│  • Diferenciar atendimento por agilidade      │
│                                                │
│  [ Baixar PDF ] [ Nova Pesquisa ]             │
└───────────────────────────────────────────────┘
```

---

## 🎯 MÉTRICAS DE SUCESSO - FASE 1

### Funcionalidade

| Funcionalidade | Métrica | Target |
|----------------|---------|--------|
| **Geração de Pautas** | Tempo médio | < 15s |
| **Geração de Posts** | Tempo médio | < 30s |
| **Simulador de Feed** | Taxa de uso | > 80% dos posts |
| **Monitor Trends** | Trends detectados/dia | > 5 relevantes |
| **Pesquisa Web** | Tempo médio | < 45s |

### Qualidade

| Aspecto | Métrica | Target |
|---------|---------|--------|
| **Alinhamento Base FEMME** | Aprovação gestor | > 85% |
| **Relevância de Trends** | Score médio | > 75/100 |
| **Qualidade Insights** | Satisfação usuário | > 4/5 |

---

**Próximo documento:** [05_IAMKT_Base_Conhecimento.md](05_IAMKT_Base_Conhecimento.md)
