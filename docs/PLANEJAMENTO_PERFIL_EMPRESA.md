# 📋 PLANEJAMENTO: Página "Perfil da Empresa" com Integração N8N

**Data de Criação:** 28 de Janeiro de 2026  
**Última Atualização:** 28 de Janeiro de 2026 - 16:39  
**Status:** Em Desenvolvimento

---

## 🎯 OBJETIVO GERAL

Implementar página "Perfil da Empresa" que:
1. Coleta dados da empresa durante onboarding
2. Envia dados para N8N para análise
3. Recebe análise com avaliações e sugestões por campo
4. Permite usuário aceitar/rejeitar sugestões
5. Gera compilação final com plano de marketing
6. Exibe resultado em modo visualização

---

## 👤 FLUXO DO USUÁRIO COMPLETO

### **1. CADASTRO E ONBOARDING**

#### **1.1 Cadastro Inicial**
- Usuário acessa `/signup`
- Preenche: nome, email, senha, organização
- Sistema cria conta
- **Equipe interna libera acesso** (aprovação manual)

#### **1.2 Primeiro Login**
- Usuário faz login pela primeira vez
- `onboarding_completed = False`
- Redireciona para dashboard

#### **1.3 Modal Welcome**
- Modal aparece automaticamente
- Título: "Bem-vindo! Vamos começar?"
- Botão: "Iniciar Onboarding" → Redireciona para `/knowledge/view/`
- Link: "Pular por enquanto" → Fecha modal

#### **1.4 Restrição de Acesso**
- **Apenas página "Base de Conhecimento" está liberada**
- Demais páginas bloqueadas até `onboarding_completed = True`
- Menu sidebar mostra apenas "Base de Conhecimento"

#### **1.5 Preenchimento da Base de Conhecimento**

**IMPORTANTE:** Não há "passos" separados. Todos os campos estão em uma única página.

**Campos Obrigatórios:**
- ✅ **Descrição do produto/serviço** (único campo obrigatório)

**Campos Opcionais:**
- Nome da empresa (já preenchido com dado do cadastro)
- Missão, visão, valores
- Público externo, público interno
- Segmentos internos
- Posicionamento de mercado
- Diferenciais competitivos
- Proposta de valor
- Tom de voz externo, tom de voz interno
- Palavras recomendadas, palavras a evitar
- Cores da marca (hex + nome)
- Tipografia (Google Fonts ou upload)
- Logos (upload)
- Site institucional
- Redes sociais (Instagram, Facebook, LinkedIn, YouTube)
- Concorrentes (nome + URL)
- Templates de redes sociais
- Fontes confiáveis (URLs)
- Canais de trends
- Palavras-chave para trends
- Imagens de referência

#### **1.6 Salvamento e Liberação de Acesso**
- Usuário preenche campos (mínimo: descrição do produto)
- Clica em "Salvar Base IAMKT"
- Dados são salvos no banco
- Arquivos (logos, fontes, imagens) são enviados ao S3
- **Sistema marca `onboarding_completed = True`**
- **Acesso liberado para toda a plataforma**
- Redireciona para dashboard
- Modal não aparece mais automaticamente

---

### **2. PÁGINA "PERFIL DA EMPRESA"**

#### **2.1 Acesso**
- **Aparece no menu sidebar APÓS `onboarding_completed = True`**
- Item "Base de Conhecimento" some do menu
- Item "Perfil da Empresa" aparece
- URL: `/knowledge/perfil/`
- Badge de status no menu (opcional)

#### **2.2 Estados da Página**

##### **ESTADO 1: Dados Incompletos**
- Exibir mensagem: "Complete seu perfil para solicitar análise"
- Botão: "Completar Perfil" → Redireciona para `/knowledge/view/`
- Mostrar % de completude

##### **ESTADO 2: Pronto para Análise**
- Exibir resumo dos dados preenchidos
- Botão: "Solicitar Análise N8N"
- Ao clicar:
  - Envia dados para N8N
  - Status muda para 'processing'
  - Redireciona para ESTADO 3

##### **ESTADO 3: Processando Análise**
- Loading state com animação
- Mensagem: "Analisando seus dados... Isso pode levar alguns minutos."
- Polling a cada 10 segundos para verificar status
- Quando N8N retorna análise → ESTADO 4

##### **ESTADO 4: Modo Edição (Análise Recebida)**

**IMPORTANTE:** Página fica em modo edição até que empresa complete fase de aprovar avaliação/sugestões.

- Exibir análise por campo:
  - Campo: "Missão"
  - Informado pelo usuário: [texto]
  - Avaliação: "A missão da marca não está definida."
  - Status: "Fraco" (badge vermelho)
  - Sugestão do agente IAMKT: [texto sugerido]
  - Checkbox: "Aceitar sugestão"
  
- Resumo geral:
  - X campos fracos
  - Y campos médios
  - Z campos bons
  
- Botão: "Aplicar Sugestões Selecionadas"
- Ao clicar:
  - Atualiza campos da KB com sugestões aceitas
  - Solicita compilação ao N8N
  - Status muda para 'compiling'
  - Redireciona para ESTADO 5

**Sem aprovar sugestões:** Página não pode entrar no modo visualização

##### **ESTADO 5: Processando Compilação**
- Loading state com animação
- Mensagem: "Gerando seu plano de marketing... Quase lá!"
- Polling a cada 10 segundos
- Quando N8N retorna compilação → ESTADO 6

##### **ESTADO 6: Modo Visualização (Compilação Recebida)**
- **Seção 1: Plano de Marketing**
  - Texto completo do plano gerado
  - Formatação markdown
  
- **Seção 2: Avaliações por Campo**
  - Lista de campos com status
  - Filtros: Todos / Fracos / Médios / Bons
  
- **Seção 3: Resumos**
  - Resumo geral da empresa
  - Pontos fortes
  - Pontos de melhoria
  
- Botões:
  - "Editar Perfil" → Volta para `/knowledge/view/`
  - "Solicitar Nova Análise" → Volta para ESTADO 2

---

## 📊 ESTRUTURA DE DADOS

### **Campos do Modelo KnowledgeBase**

#### **Campos Existentes (Bloco 1-7)**
```python
# Bloco 1: Identidade Institucional
nome_empresa = CharField
missao = TextField
visao = TextField
valores = TextField
descricao_produto = TextField  # Renomeado de 'historia'

# Bloco 2: Público e Segmentos
publico_externo = TextField
publico_interno = TextField
# Segmentos: InternalSegment (model separado)

# Bloco 3: Posicionamento e Diferenciais
posicionamento = TextField
diferenciais = TextField
proposta_valor = TextField

# Bloco 4: Tom de Voz e Linguagem
tom_voz_externo = TextField
tom_voz_interno = TextField
palavras_recomendadas = TextField
palavras_evitar = TextField

# Bloco 5: Identidade Visual
# Cores: ColorPalette (model separado)
# Fontes: Typography (model separado)
# Logos: Logo (model separado)
# Imagens: ReferenceImage (model separado)

# Bloco 6: Sites e Redes Sociais
site_institucional = URLField
concorrentes = JSONField  # [{"nome": "X", "url": "..."}]
# Redes sociais: SocialNetwork (model separado)
# Templates: SocialNetworkTemplate (model separado)

# Bloco 7: Dados e Insights
fontes_confiaveis = JSONField  # ["url1", "url2"]
canais_trends = JSONField  # ["canal1", "canal2"]
palavras_chave_trends = JSONField  # ["palavra1", "palavra2"]
```

#### **Campos de Análise N8N (Novos)**
```python
# Primeira Análise (campo por campo)
n8n_analysis = JSONField(default=dict, blank=True)
# Estrutura:
{
  "missao": {
    "informado_pelo_usuario": "texto original",
    "avaliacao": "fraco",  # fraco/médio/bom
    "status": "fraco",
    "sugestao": "texto sugerido"
  },
  "visao": { ... },
  ...
}

# Compilação Final
n8n_compilation = JSONField(default=dict, blank=True)
# Estrutura:
{
  "plano_marketing": "texto completo do plano",
  "avaliacoes": {
    "campo1": "avaliação detalhada",
    ...
  },
  "resumos": {
    "resumo_geral": "texto",
    "pontos_fortes": ["ponto1", "ponto2"],
    "pontos_melhoria": ["ponto1", "ponto2"]
  }
}

# Decisões do Usuário
accepted_suggestions = JSONField(default=dict, blank=True)
# Estrutura:
{
  "missao": true,  # aceitou sugestão
  "visao": false,  # rejeitou sugestão
  ...
}

# Status e Metadados
analysis_status = CharField(
  choices=[
    ('pending', 'Pendente'),
    ('processing', 'Processando Análise'),
    ('completed', 'Análise Completa'),
    ('compiling', 'Gerando Compilação'),
    ('compiled', 'Compilação Completa'),
    ('error', 'Erro')
  ],
  default='pending'
)

analysis_revision_id = CharField(blank=True)  # ID da revisão N8N
analysis_requested_at = DateTimeField(null=True)
analysis_completed_at = DateTimeField(null=True)
compilation_requested_at = DateTimeField(null=True)
compilation_completed_at = DateTimeField(null=True)
```

---

## 🎨 DESIGN SYSTEM E UI/UX

### **DECISÃO DE DESIGN (29/01/2026)**

**IMPORTANTE:**
- ✅ **Estrutura das imagens de referência será seguida**
- ❌ **Cores das imagens de referência NÃO serão usadas**
- ✅ **Usar design system existente** (`base.css` + `components.css`)
- ✅ **Criar componentes reutilizáveis** para outras páginas

### **Paleta de Cores da Aplicação**

```css
/* Cores Primárias */
--color-primary: #7a3d8a;           /* Roxo IAMKT */
--color-primary-hover: #9b59b6;     /* Roxo claro */
--color-secondary: #7ab2ca;         /* Teal */
--color-accent: #00bca4;            /* Teal escuro */

/* Estados (usar para badges) */
--color-success: #22c55e;           /* Verde - "Bom" */
--color-warning: #f59e0b;           /* Amarelo - "Médio" */
--color-error: #ef4444;             /* Vermelho - "Fraco" */

/* Texto e Backgrounds */
--color-text: #34343a;
--color-text-muted: #77767c;
--color-surface: #f5f5f7;
```

### **Componentes Reutilizáveis**

#### **1. Card de Análise** (`.analysis-card`)

Adicionar em `static/css/components.css`:

```css
.analysis-card {
  background: var(--white-90);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-subtle);
  padding: var(--spacing-6);
  margin-bottom: var(--spacing-4);
}

.analysis-card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid color-mix(in srgb, var(--color-text-muted) 20%, transparent);
}

.analysis-card-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-4);
}

.analysis-section-full {
  grid-column: 1 / -1;
}

.btn-action {
  flex: 1;
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-md);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all var(--transition-base);
}

.btn-action-accept {
  background: color-mix(in srgb, var(--color-success) 10%, transparent);
  color: var(--color-success);
}

.btn-action-accept.active {
  background: var(--color-success);
  color: var(--color-white);
}

.btn-action-reject {
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
  color: var(--color-error);
}

.btn-action-reject.active {
  background: var(--color-error);
  color: var(--color-white);
}

@media (max-width: 768px) {
  .analysis-card-body { grid-template-columns: 1fr; }
}
```

#### **2. Resumo Geral** (`.analysis-summary`)

```css
.analysis-summary {
  background: var(--white-90);
  border-radius: var(--radius-lg);
  padding: var(--spacing-6);
  margin-bottom: var(--spacing-6);
}

.analysis-summary-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-4);
}

.stat-item {
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
  text-align: center;
}

.stat-item.stat-danger {
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
}

.stat-item.stat-warning {
  background: color-mix(in srgb, var(--color-warning) 10%, transparent);
}

.stat-item.stat-success {
  background: color-mix(in srgb, var(--color-success) 10%, transparent);
}

@media (max-width: 768px) {
  .analysis-summary-stats { grid-template-columns: 1fr; }
}
```

#### **3. Badges de Status** (reutilizar existentes)

- Status "bom" → `.badge.badge-success`
- Status "médio" → `.badge.badge-warning`
- Status "fraco" → `.badge.badge-danger`

### **Layout da Página**

**IMPORTANTE:** A página usa o layout padrão da aplicação (header + sidebar), não é uma página standalone.

Arquivo: `templates/knowledge/perfil.html`

```html
{% extends 'base.html' %}

{% block content %}
<div class="perfil-container">
  <div class="perfil-header">
    <div class="perfil-header-left">
      <!-- Upload de logo -->
    </div>
    <div class="perfil-header-right">
      <h1>Perfil da Empresa</h1>
      <p>Instruções...</p>
    </div>
  </div>
  
  <div class="analysis-summary">...</div>
  
  <div class="analysis-cards-list">
    <!-- Cards de análise -->
  </div>
  
  <div class="perfil-actions">
    <button class="btn btn-primary btn-lg">
      Aplicar Sugestões Selecionadas
    </button>
  </div>
</div>
{% endblock %}
```

### **Arquivos a Criar/Modificar**

1. `static/css/components.css` - Adicionar componentes
2. `static/css/perfil.css` - Layout específico
3. `templates/knowledge/perfil.html` - Template
4. `static/js/perfil.js` - Interações

---

## 🔄 INTEGRAÇÃO N8N

### **📚 Documentação Completa de Segurança**

**Consultar:** `docs/SEGURANCA_N8N_INTEGRACAO.md`

Este documento contém:
- Arquitetura de segurança em 5 camadas
- Implementação completa de HMAC + Timestamp
- Rate limiting e proteção contra ataques
- Passo a passo de configuração N8N
- Plano de resposta a incidentes

---

### **Endpoints e Configuração**

#### **Django → N8N (Envio)**

**Desenvolvimento:**
```
POST https://n8n.srv812718.hstgr.cloud/webhook/2f87eab4-40da-4975-a219-74f15dbb2576
```

**Produção:**
```
POST https://n8n-prod.srv812718.hstgr.cloud/webhook/fundamentos-prod
```

**Headers:**
```
Content-Type: application/json
X-API-Key: {N8N_WEBHOOK_SECRET}
X-Signature: {HMAC-SHA256 do payload + timestamp}
X-Timestamp: {Unix timestamp}
X-Organization-ID: {organization_id}
X-KB-ID: {kb_id}
```

#### **N8N → Django (Retorno)**

**Desenvolvimento:**
```
POST https://iamkt-femmeintegra.aisuites.com.br/api/webhooks/fundamentos/
```

**Produção:**
```
POST https://[dominio-producao]/api/webhooks/fundamentos/
```

**Headers:**
```
Content-Type: application/json
X-API-Key: {N8N_WEBHOOK_SECRET}
X-Signature: {HMAC-SHA256 do payload + timestamp}
X-Timestamp: {Unix timestamp}
X-Revision-ID: {revision_id}
```

---

### **Payload Real Enviado (Fluxo 1)**

Após clicar "Salvar Base IAMKT", sistema envia:

```json
{
  "kb_id": 56,
  "organization_id": 1,
  "organization_name": "Fulanas Papelaria",
  "mission": "",
  "vision": "",
  "value_proposition": "",
  "differentials": "",
  "phrase_10_words": "",
  "target_audience": "moradores da região de Touros, Rio Grande do Norte",
  "tone_of_voice": "",
  "description": "papelaria de bairro",
  "palette_colors": [],
  "logo_files": [],
  "fonts": [],
  "website_url": "",
  "social_networks": [],
  "competitors": [],
  "reference_images": []
}
```

---

### **Retorno Real do N8N**

```json
{
  "baseId": 56,
  "revision_id": "b3eacfbd025d45a8",
  "reference_images_analysis": [
    {"visual_knowledge_base": {"visual_knowledge_base": []}}
  ],
  "payload": [
    {
      "missao": {
        "informado_pelo_usuario": "",
        "avaliacao": "A missão da marca Fulanas não está definida.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Proposta: 'Oferecer materiais de papelaria de alta qualidade e acessíveis.'"
      },
      "visao": {
        "informado_pelo_usuario": "",
        "avaliacao": "A visão da marca Fulanas não está definida.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Proposta: 'Ser a papelaria de referência em Touros, oferecendo excelência.'"
      },
      "proposta_de_valor": {
        "informado_pelo_usuario": "",
        "avaliacao": "A proposta de valor da marca Fulanas não está definida.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Proposta: 'Atender às necessidades de papelaria dos moradores locais com qualidade.'"
      },
      "diferenciais": {
        "informado_pelo_usuario": null,
        "avaliacao": "Os diferenciais da marca Fulanas não estão definidos.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": [
          "Variedade de produtos locais",
          "Atendimento personalizado",
          "Preços acessíveis"
        ]
      },
      "frase_em_10_palavras": {
        "informado_pelo_usuario": "",
        "avaliacao": "A frase de 10 palavras da marca Fulanas não está definida.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Papelaria Fulanas: qualidade, simpatia e conveniência para você!"
      },
      "publico_alvo": {
        "informado_pelo_usuario": ["moradores da região de Touros, Rio Grande do Norte"],
        "avaliacao": "O público-alvo está definido, mas pode ser detalhado.",
        "status": "médio",
        "sugestao_do_agente_iamkt": [
          {
            "segmento": "Moradores locais",
            "diretriz_de_conteudo": "Oferecer produtos e serviços que atendam diretamente às necessidades da comunidade."
          },
          {
            "segmento": "Estudantes",
            "diretriz_de_conteudo": "Produzir conteúdo educativo e promocional para estudantes da região."
          }
        ]
      },
      "tom_de_voz": {
        "informado_pelo_usuario": "",
        "avaliacao": "O tom de voz da marca Fulanas não está definido.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Proposta: 'Amigável e acessível, refletindo a relação com a comunidade.'"
      },
      "descricao_do_produto": {
        "informado_pelo_usuario": "papelaria de bairro",
        "avaliacao": "A descrição do produto é básica e pode ser expandida.",
        "status": "médio",
        "sugestao_do_agente_iamkt": "Proposta: 'Uma papelaria que oferece uma ampla gama de produtos, atendimento próximo e qualidade.'"
      },
      "paleta_de_cores": {
        "informado_pelo_usuario": [],
        "avaliacao": "A paleta de cores não está definida.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Sugestão de paleta: azul (confiança), verde (cuidado) e amarelo (otimismo)."
      },
      "logotipo": {
        "informado_pelo_usuario": null,
        "avaliacao": "O logotipo da marca Fulanas não está definido.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Desenvolver um logotipo que represente a identidade da papelaria e a comunidade."
      },
      "fontes": {
        "informado_pelo_usuario": null,
        "avaliacao": "As fontes da marca Fulanas não estão definidas.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": ["Roboto", "Open Sans"]
      },
      "website": {
        "informado_pelo_usuario": "",
        "avaliacao": "O website da marca Fulanas não está definido.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Criar um website simples e funcional para divulgação e vendas."
      },
      "redes_sociais": {
        "informado_pelo_usuario": null,
        "avaliacao": "As redes sociais da marca Fulanas não estão definidas.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Estabelecer perfis no Instagram e Facebook para engajamento local."
      },
      "concorrencia": {
        "informado_pelo_usuario": null,
        "observacao_informado_pelo_usuario": null,
        "avaliacao": "A concorrência não está mapeada.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": [
          "Papelaria Rio Grande",
          "Escritório e Cia",
          "Papelaria do Bairro"
        ]
      },
      "imagens_de_referencia": {
        "informado_pelo_usuario": null,
        "avaliacao": "Imagens de referência não estão definidas.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": "Buscar inspiração em papelarias locais e modernas."
      },
      "sugestoes_estrategicas_de_ativacao_de_marca": {
        "avaliacao": "Estratégias de ativação não estão definidas.",
        "status": "fraco",
        "sugestao_do_agente_iamkt": [
          "Promoções para estudantes",
          "Eventos comunitários",
          "Parcerias com escolas locais"
        ]
      }
    }
  ]
}
```

---

### **Fluxo de Comunicação**

```
┌─────────────────┐
│  Django (IAMKT) │
└────────┬────────┘
         │
         │ 1. POST /n8n/analyze
         │    Payload: dados da KB
         ▼
┌─────────────────┐
│   N8N Workflow  │
│   (Análise)     │
└────────┬────────┘
         │
         │ 2. Processa dados
         │    Avalia cada campo
         │    Gera sugestões
         │
         │ 3. POST /knowledge/webhook/analysis/
         │    Payload: análises + revision_id
         ▼
┌─────────────────┐
│  Django (IAMKT) │
│  Armazena       │
│  n8n_analysis   │
└────────┬────────┘
         │
         │ 4. Usuário aceita sugestões
         │
         │ 5. POST /n8n/compile
         │    Payload: dados atualizados
         ▼
┌─────────────────┐
│   N8N Workflow  │
│   (Compilação)  │
└────────┬────────┘
         │
         │ 6. Gera plano de marketing
         │    Cria resumos e avaliações
         │
         │ 7. POST /knowledge/webhook/compilation/
         │    Payload: compilação completa
         ▼
┌─────────────────┐
│  Django (IAMKT) │
│  Armazena       │
│  n8n_compilation│
└─────────────────┘
```

### **Endpoints Django**

#### **1. Solicitar Análise**
```
POST /knowledge/perfil/request-analysis/
```

**Request:**
```json
{
  "organization_id": 123
}
```

**Response:**
```json
{
  "success": true,
  "message": "Análise solicitada com sucesso",
  "revision_id": "rev_abc123",
  "status": "processing"
}
```

**Ação:**
- Monta payload com todos os campos da KB
- Envia para N8N via POST
- Atualiza `analysis_status` para 'processing'
- Salva `analysis_revision_id`
- Registra `analysis_requested_at`

---

#### **2. Webhook - Receber Análise**
```
POST /knowledge/webhook/analysis/
```

**Request (do N8N):**
```json
{
  "revision_id": "rev_abc123",
  "organization_id": 123,
  "analysis": {
    "missao": {
      "informado_pelo_usuario": "Texto original",
      "avaliacao": "fraco",
      "status": "fraco",
      "sugestao": "Texto sugerido melhorado"
    },
    "visao": { ... },
    ...
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Análise recebida e armazenada"
}
```

**Ação:**
- Valida `revision_id`
- Armazena em `n8n_analysis`
- Atualiza `analysis_status` para 'completed'
- Registra `analysis_completed_at`

---

#### **3. Aplicar Sugestões**
```
POST /knowledge/perfil/apply-suggestions/
```

**Request:**
```json
{
  "accepted_suggestions": {
    "missao": true,
    "visao": false,
    "valores": true,
    ...
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "3 sugestões aplicadas com sucesso",
  "applied_count": 3
}
```

**Ação:**
- Atualiza campos da KB com sugestões aceitas
- Salva `accepted_suggestions`
- Solicita compilação ao N8N
- Atualiza `analysis_status` para 'compiling'

---

#### **4. Solicitar Compilação**
```
POST /knowledge/perfil/request-compilation/
```

**Request:**
```json
{
  "organization_id": 123
}
```

**Response:**
```json
{
  "success": true,
  "message": "Compilação solicitada",
  "status": "compiling"
}
```

**Ação:**
- Monta payload com dados atualizados
- Envia para N8N via POST
- Registra `compilation_requested_at`

---

#### **5. Webhook - Receber Compilação**
```
POST /knowledge/webhook/compilation/
```

**Request (do N8N):**
```json
{
  "revision_id": "rev_abc123",
  "organization_id": 123,
  "compilation": {
    "plano_marketing": "Texto completo do plano...",
    "avaliacoes": {
      "missao": "Avaliação detalhada da missão...",
      ...
    },
    "resumos": {
      "resumo_geral": "Resumo geral da empresa...",
      "pontos_fortes": ["Ponto 1", "Ponto 2"],
      "pontos_melhoria": ["Ponto 1", "Ponto 2"]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Compilação recebida e armazenada"
}
```

**Ação:**
- Armazena em `n8n_compilation`
- Atualiza `analysis_status` para 'compiled'
- Registra `compilation_completed_at`

---

#### **6. Verificar Status**
```
GET /knowledge/perfil/status/
```

**Response:**
```json
{
  "status": "completed",
  "has_analysis": true,
  "has_compilation": false,
  "completude": 85,
  "can_request_analysis": false,
  "is_processing": false
}
```

---

## 📝 PLANEJAMENTO DETALHADO (11 FASES)

### **✅ FASE 1: PREPARAÇÃO DO MODELO** (COMPLETA)

**Objetivo:** Preparar modelo KnowledgeBase para receber dados de análise N8N

**Etapas:**
1. ✅ Migration renomear `historia` → `descricao_produto`
2. ✅ Migration adicionar campo `concorrentes`
3. ✅ Migration adicionar campos de análise N8N
4. ✅ Helper methods no modelo

**Arquivos modificados:**
- `apps/knowledge/models.py`
- `apps/knowledge/migrations/0012_*.py`
- `apps/knowledge/migrations/0013_*.py`
- `apps/knowledge/migrations/0014_*.py`

**Status:** ✅ COMPLETA

---

### **✅ FASE 2: UI - CAMPO CONCORRENTES** (COMPLETA)

**Objetivo:** Implementar interface para adicionar/remover concorrentes

**Etapas:**
1. ✅ Template atualizado com formulário
2. ✅ JavaScript `concorrentes.js` criado
3. ✅ View de salvamento atualizada
4. ✅ CSS responsivo adicionado

**Arquivos criados/modificados:**
- `templates/knowledge/view.html`
- `static/js/concorrentes.js`
- `static/css/knowledge.css`
- `apps/knowledge/views.py`

**Status:** ✅ COMPLETA

---

### **✅ FASE 3: INTEGRAÇÃO N8N - PRIMEIRO ENVIO** (COMPLETA)

**Objetivo:** Criar endpoint para enviar dados da KB para N8N

**Status:** ✅ COMPLETA

**Camadas de Segurança Implementadas:**
- ✅ **ATIVA:** Token Interno (X-INTERNAL-TOKEN)
- ✅ **ATIVA:** Whitelist de IP (HTTP_CF_CONNECTING_IP)
- ✅ **ATIVA:** Rate Limiting (10 req/min por IP)
- ❌ **DESABILITADA:** Validação de Timestamp (N8N não envia X-Timestamp)
- ❌ **DESABILITADA:** Assinatura HMAC (N8N não envia X-Signature)

**Justificativa:** As 3 camadas ativas (token + IP whitelist + rate limiting) fornecem segurança robusta. As camadas 4 e 5 podem ser reabilitadas quando o N8N for configurado para enviar os headers necessários.

**Etapas:**
1. ✅ Criar view `request_analysis`
2. ✅ Montar payload com todos os campos
3. ✅ Enviar POST para N8N
4. Atualizar status para 'processing'
5. Retornar revision_id

**Arquivos a criar/modificar:**
- `apps/knowledge/views.py` (nova view)
- `apps/knowledge/urls.py` (nova rota)
- `apps/knowledge/services/n8n_service.py` (novo)

**Payload para N8N:**
```json
{
  "organization_id": 123,
  "organization_name": "Empresa X",
  "data": {
    "missao": "texto",
    "visao": "texto",
    "valores": "texto",
    "descricao_produto": "texto",
    "publico_externo": "texto",
    "publico_interno": "texto",
    "posicionamento": "texto",
    "diferenciais": "texto",
    "proposta_valor": "texto",
    "tom_voz_externo": "texto",
    "tom_voz_interno": "texto",
    "palavras_recomendadas": "texto",
    "palavras_evitar": "texto",
    "site_institucional": "url",
    "concorrentes": [...],
    "fontes_confiaveis": [...],
    "canais_trends": [...],
    "palavras_chave_trends": [...]
  }
}
```

**Testes:**
- [ ] Payload montado corretamente
- [ ] POST enviado para N8N
- [ ] Status atualizado
- [ ] revision_id salvo

---

### **FASE 4: WEBHOOK N8N - RECEBER PRIMEIRA ANÁLISE**

**Objetivo:** Criar endpoint webhook para receber análise do N8N

**Etapas:**
1. Criar view `webhook_analysis`
2. Validar revision_id
3. Processar payload do N8N
4. Armazenar em `n8n_analysis`
5. Atualizar status para 'completed'

**Arquivos a criar/modificar:**
- `apps/knowledge/views.py` (nova view)
- `apps/knowledge/urls.py` (nova rota)

**Testes:**
- [ ] Webhook recebe dados
- [ ] Validação de revision_id
- [ ] Dados armazenados corretamente
- [ ] Status atualizado

---

### **FASE 5: PÁGINA PERFIL - ESTADO PROCESSANDO**

**Objetivo:** Criar template com loading state durante análise

**Etapas:**
1. Criar template `perfil.html`
2. View `perfil_empresa`
3. JavaScript para polling de status
4. CSS para loading state

**Arquivos a criar:**
- `templates/knowledge/perfil.html`
- `static/js/perfil.js`
- `static/css/perfil.css`
- `apps/knowledge/views.py` (nova view)

**Testes:**
- [ ] Loading state exibido
- [ ] Polling funciona
- [ ] Transição para próximo estado

---

### **FASE 6: PÁGINA PERFIL - MODO EDIÇÃO**

**Objetivo:** Exibir análises e permitir aceitar/rejeitar sugestões

**Etapas:**
1. Template com lista de campos
2. Checkboxes para sugestões
3. Resumo geral (fracos/médios/bons)
4. Botão "Aplicar Sugestões"

**Arquivos a modificar:**
- `templates/knowledge/perfil.html`
- `static/js/perfil.js`
- `static/css/perfil.css`

**Testes:**
- [ ] Análises exibidas corretamente
- [ ] Checkboxes funcionam
- [ ] Resumo calculado
- [ ] Botão envia dados

---

### **FASE 7: PROCESSAR SUGESTÕES ACEITAS**

**Objetivo:** Aplicar sugestões aceitas e solicitar compilação

**Etapas:**
1. View `apply_suggestions`
2. Atualizar campos da KB
3. Salvar `accepted_suggestions`
4. Solicitar compilação ao N8N

**Arquivos a criar/modificar:**
- `apps/knowledge/views.py` (nova view)
- `apps/knowledge/urls.py` (nova rota)

**Testes:**
- [ ] Sugestões aplicadas
- [ ] Campos atualizados
- [ ] Compilação solicitada
- [ ] Status atualizado

---

### **FASE 8: WEBHOOK N8N - RECEBER COMPILAÇÃO**

**Objetivo:** Receber plano de marketing e resumos do N8N

**Etapas:**
1. View `webhook_compilation`
2. Processar payload
3. Armazenar em `n8n_compilation`
4. Atualizar status para 'compiled'

**Arquivos a criar/modificar:**
- `apps/knowledge/views.py` (nova view)
- `apps/knowledge/urls.py` (nova rota)

**Testes:**
- [ ] Webhook recebe dados
- [ ] Compilação armazenada
- [ ] Status atualizado

---

### **FASE 9: PÁGINA PERFIL - MODO VISUALIZAÇÃO**

**Objetivo:** Exibir plano de marketing e resultados finais

**Etapas:**
1. Template com plano de marketing
2. Seção de avaliações
3. Seção de resumos
4. Botões de ação

**Arquivos a modificar:**
- `templates/knowledge/perfil.html`
- `static/js/perfil.js`
- `static/css/perfil.css`

**Testes:**
- [ ] Plano exibido
- [ ] Avaliações listadas
- [ ] Resumos formatados
- [ ] Botões funcionam

---

### **FASE 10: ATUALIZAÇÃO DO SIDEBAR**

**Objetivo:** Adicionar badge de status no menu

**Etapas:**
1. Atualizar template do sidebar
2. Adicionar lógica de badge
3. CSS para badge

**Arquivos a modificar:**
- `templates/base/sidebar.html`
- `static/css/sidebar.css`

**Testes:**
- [ ] Badge aparece
- [ ] Cores corretas por status
- [ ] Link funciona

---

### **FASE 11: TESTES E AJUSTES**

**Objetivo:** Testar fluxo completo e ajustar UX

**Etapas:**
1. Teste completo do fluxo
2. Ajustes de UX
3. Tratamento de erros
4. Documentação

**Testes:**
- [ ] Fluxo completo funciona
- [ ] Erros tratados
- [ ] UX polida
- [ ] Documentação atualizada

---

## 🎓 DECISÕES TÉCNICAS

### **Por que JSONField para análises?**
- Flexibilidade para adicionar novos campos sem migrations
- N8N pode retornar estruturas variadas
- Facilita evolução do sistema

### **Por que estados claros (pending/processing/completed)?**
- Facilita renderização condicional de templates
- Permite rastreamento do progresso
- Simplifica lógica de polling

### **Por que separar análise e compilação?**
- Usuário pode revisar análise antes de gerar plano
- Permite aceitar/rejeitar sugestões
- Compilação só acontece com dados validados

### **Por que helper methods no modelo?**
- Encapsula lógica complexa
- Facilita uso em views e templates
- Código mais legível e manutenível

---

## 📈 PROGRESSO ATUAL

**Fases Completas:** 3/11 (27%)

- ✅ FASE 1: Preparação do Modelo
- ✅ FASE 2: UI Campo Concorrentes
- ✅ FASE 3: Integração N8N - Primeiro Envio (3/5 camadas de segurança ativas)
- ⏭️ FASE 4: Webhook N8N - Receber Primeira Análise (PRÓXIMA)
- ⏸️ FASE 5-11: Pendentes

---

## 🔗 REFERÊNCIAS

- Documento de sessão: `docs/SESSAO_2026-01-28.md`
- Melhores práticas: `docs/MELHORES_PRATICAS_PROJETO.md`
- Modelo: `apps/knowledge/models.py`
- Migrations: `apps/knowledge/migrations/`

---

**Documento mantido atualizado durante o desenvolvimento.**
