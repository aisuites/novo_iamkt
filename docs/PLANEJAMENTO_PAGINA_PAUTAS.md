# 📋 PLANEJAMENTO - PÁGINA DE PAUTAS

**Data Criação:** 01/02/2026  
**Status:** Planejamento Inicial  
**Objetivo:** Documentar estrutura e funcionamento da página de gerenciamento de pautas

---

## 🎯 VISÃO GERAL

A página de Pautas será o centro de criação inteligente de conteúdo, onde usuários gerenciam a base estratégica da marca e acionam ferramentas de IA para gerar pautas, criar posts e evoluir continuamente.

---

## 📐 ESTRUTURA DA PÁGINA

### **1. Header Global**
- **Reutilização:** Mesmo header já existente em toda aplicação
- **Estilo:** CSS global já implementado
- **Funcionalidade:** Navegação consistente

### **2. Sidebar**
- **Reutilização:** Mesmo sidebar já existente
- **Lógica:** Mesmas funcionalidades de navegação
- **Estilo:** Estilos globais aplicados

### **3. Seção Principal - Central de Criação Inteligente**

#### **Layout:**
- **Esquerda:** Nome da empresa + texto descritivo
- **Direita:** Botão "Gerar Pauta"

#### **Conteúdo:**
```
[NOME DA EMPRESA]

Central de Criação Inteligente - Não é slogan — é a única estratégia possível. 
Aqui você gerencia a base estratégica da sua marca e aciona as ferramentas de IA 
para gerar pautas, criar posts e evoluir continuamente em um cenário de 
turbulência permanente.

[GERAR PAUTA]
```

#### **Referência:** Imagem pizza da Lu (estrutura similar)

### **4. Bloco de Filtros**
- **Referência:** Imagem da aplicação antiga
- **Estrutura:** Fiel à referência
- **Estilo:** Cores e estilos da aplicação atual
- **Funcionalidade:** Filtrar pautas por critérios diversos

### **5. Bloco de Paginação**
- **Referência:** Imagem anexada
- **Estrutura:** Fiel à referência
- **Estilo:** Cores e estilos da aplicação atual
- **Funcionalidade:** Navegação entre páginas de resultados

### **6. Cards de Pautas**
- **Referência:** Imagem de referência
- **Estrutura:** Fiel à referência
- **Conteúdo de cada card:**
  - Título da pauta
  - Conteúdo/Descrição
  - Botão: Editar
  - Botão: Excluir
  - Botão: Gerar Post

---

## 🎨 DESIGN E ESTILO

### **Diretrizes:**
- **Cores:** Paleta da aplicação atual
- **Tipografia:** Fontes já definidas no sistema
- **Componentes:** Reutilizar classes CSS existentes
- **Responsividade:** Mobile-first, seguindo padrões da aplicação

### **Referências Visuais:**
- Pizza da Lu: Estrutura da seção principal
- App antiga: Estrutura de filtros
- Imagem anexada: Estrutura de paginação e cards

---

## 🔧 REGRAS DE IMPLEMENTAÇÃO

### **1. Reutilização Máxima**
- ✅ Header global existente
- ✅ Sidebar existente
- ✅ CSS global
- ✅ Componentes compartilhados
- ❌ NADA novo será criado sem necessidade

### **2. Consistência**
- Mesmos padrões de navegação
- Mesmos estilos visuais
- Mesmas interações UX
- Mesmas validações e segurança

### **3. Performance**
- Lazy loading para cards
- Paginação otimizada
- Cache de filtros
- Reaproveitamento de assets

---

## 📱 RESPONSIVIDADE

### **Breakpoints:**
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

### **Adaptações:**
- Cards empilhados em mobile
- Filtros colapsáveis
- Botões adaptativos
- Texto responsivo

---

## 🔐 SEGURANÇA

### **Validações:**
- Multi-tenancy (filtrar por organization)
- Rate limiting para geração de pautas
- Permissões por usuário
- Sanitização de conteúdo

### **Controles:**
- CSRF em formulários
- Validação de inputs
- Auditoria de ações
- Logs de acesso

---

## 📊 MODELO DE DADOS

### **Pauta (Topic/Suggestion)**
```python
class Pauta:
    id: UUID (primary_key)
    organization: ForeignKey  # Apenas empresa logada
    user: ForeignKey
    
    # Dados principais
    title: CharField (max_length=200)
    content: TextField
    rede_social: CharField (choices: FACEBOOK, INSTAGRAM, LINKEDIN, TWITTER)
    
    # Status simplificado
    status: Enum (requested, generated)
    
    # Dados N8N
    n8n_id: IntegerField (ID retornado pelo N8N)
    n8n_data: JSONField (dados completos do processo)
    generation_request: JSONField (payload enviado ao N8N)
    
    # AUDITORIA SIMPLIFICADA
    created_at: DateTime
    updated_at: DateTime
    
    # Quem solicitou
    requested_by: ForeignKey(User, related_name='pautas_solicitadas')
    requested_at: DateTime
    
    # Quem editou (última edição)
    last_edited_by: ForeignKey(User, related_name='pautas_editadas', null=True, blank=True)
    last_edited_at: DateTime(null=True, blank=True)
    
    # Histórico completo (JSON array)
    audit_history: JSONField(default=list)  # [{action, user, timestamp, details}]
    
    ```

### **Modelo de Posts (com vínculo da pauta)**
```python
class Post:
    id: UUID (primary_key)
    organization: ForeignKey
    user: ForeignKey
    
    # Dados principais
    title: CharField (max_length=200)
    content: TextField
    rede_social: CharField (choices)
    
    # VÍNCULO COM PAUTA
    pauta_origem: ForeignKey(Pauta, related_name='posts_gerados', null=True, blank=True)
    
    # Status e workflow
    status: Enum (draft, approved, published, archived)
    
    # Dados N8N
    n8n_id: IntegerField
    n8n_data: JSONField
    
    # Auditoria
    created_at: DateTime
    created_by: ForeignKey(User)
    
    # Histórico
    audit_history: JSONField(default=list)
```

### **Campos de Auditoria Simplificados:**
- **requested_by/requested_at:** Quem e quando solicitou a geração
- **last_edited_by/last_edited_at:** Última edição manual
- **audit_history:** Array completo com todas as ações
  ```json
  [
    {"action": "created", "user": 1, "timestamp": "2026-02-01T20:00:00Z", "details": {"n8n_id": 156}},
    {"action": "edited", "user": 1, "timestamp": "2026-02-01T20:05:00Z", "details": {"fields": ["title", "content"]}},
    {"action": "deleted", "user": 1, "timestamp": "2026-02-01T20:10:00Z", "details": {"reason": "Exclusão solicitada"}}
  ]
  ```

### **Vínculo Pauta → Post:**
- **Post.pauta_origem:** ForeignKey para Pauta
- **Pauta.posts_gerados:** Related_name para acessar posts criados a partir desta pauta
- **Exemplo:** Post gerado a partir da pauta 123 terá `pauta_origem_id = 123`

### **Mapeamento Payload N8N → Modelo:**
```python
# Do payload N8N:
{
    "id": 156,           → n8n_id
    "titulo": "...",     → title
    "texto": "...",      → content
    "rede": "Instagram"  → rede_social
}

# Campos adicionais preenchidos pelo sistema:
organization = request.user.organization
user = request.user
status = 'draft' (padrão ao criar)
created_at = timezone.now()
```

---

## 🔄 FLUXO DE USUÁRIO

### **Fluxo Principal:**
1. Usuário acessa página de pautas
2. Visualiza pautas existentes (cards)
3. Aplica filtros se necessário
4. Navega pela paginação
5. Interage com cards:
   - Editar pauta (expande card inline)
   - Excluir pauta
   - Gerar post a partir da pauta
6. Clica em "Gerar Pauta" → abre modal para criar nova

### **Fluxo de Edição de Pauta (Inline):**
1. Usuário clica em "Editar" no card
2. Card se expande
3. Campos "Título" e "Conteúdo" ficam editáveis
4. Botões disponíveis: "Salvar" e "Cancelar"
5. Ao salvar:
   - Dados são persistidos no banco
   - Card volta ao estado normal (compacto)
   - Valores atualizados são exibidos
6. Ao cancelar:
   - Card volta ao estado normal
   - Alterações são descartadas

---

## 🌐 INTEGRAÇÃO N8N - GERAÇÃO DE PAUTAS

### **Endpoint N8N (Envio):**
`https://n8n.srv812718.hstgr.cloud/webhook/gerar-pauta-wind`

### **Endpoint N8N (Retorno/Webhook):**
`https://n8n.srv1080437.hstgr.cloud/webhook/gerar-pauta-prod`

### **Payload Enviado para N8N:**
```json
{
  "empresa": "teste3@teste3.com",
  "usuario": "teste3@teste3.com",
  "rede": "Facebook",
  "tema": "mamografia",
  "organization_id": 7,
  "audit_log_id": 21,
  "knowledge_base": {
    "kb_id": 22,
    "company_name": "DRA INDIANARA",
    "marketing_input_summary": "Identidade da Marca: A DRA INDIANARA visa fornecer assistência de qualidade em oncologia, com a missão de ser uma referência em tratamentos oncológicos humanizados e de alta qualidade. Seu diferencial está em uma equipe qualificada e um ambiente acolhedor. Perfil e necessidades do público-alvo: A clínica atende pacientes diagnosticados com câncer e seus familiares, focando em oferecer suporte emocional e informações relevantes. Posicionamento e Mensagens-Chave: A DRA INDIANARA se diferencia pela maneira acolhedora e humana como oferece tratamentos, prometendo cuidado e esperança. Tom de Voz e Estilo de Comunicação: A comunicação deve ser clara e empática, utilizando palavras que demonstrem confiança e acolhimento. Paleta visual e estilo gráfico: A paleta de cores inclui tons de verde e amarelo suave (#F2F7CA, #506148) e a tipografia é composta por 'Roboto' e 'Open Sans', transmitindo limpeza e modernidade. Oportunidades e Direções de Conteúdo: O conteúdo deve focar em temas sobre oncologia humanizada, apoio emocional e histórias de sucesso. Diretriz final de uso: Este resumo está pronto para ser usado por um agente criativo para gerar conteúdos de marketing consistentes com a identidade e estratégia da marca."
  },
  "webhookUrl": "https://n8n.srv1080437.hstgr.cloud/webhook/gerar-pauta-prod",
  "executionMode": "production"
}
```

### **Payload Retornado pelo N8N:**
```json
[
  {
    "success": true,
    "pautas_criadas": 5,
    "pautas": [
      {
        "id": 156,
        "titulo": "IA: O Motor por Trás da Transformação Digital",
        "texto": "Explore como 75% das organizações globais estão usando IA para transformar suas operações e ganhar eficiência, com insights práticos para empresários navegarem essa mudança de paradigma.",
        "rede": "Instagram"
      },
      {
        "id": 157,
        "titulo": "Inovação no Marketing: O Que o Futuro Reserva?",
        "texto": "Uma análise crítica sobre como a IA está moldando estratégias de marketing digital, com foco em personalização e automação para criar experiências únicas e impactantes para seus clientes.",
        "rede": "Instagram"
      },
      {
        "id": 158,
        "titulo": "Decisões Inteligentes: Como a IA Está Revolucionando a Gestão Empresarial",
        "texto": "Descubra as tendências mais impactantes da IA nas decisões empresariais, da segurança cibernética à automação avançada, e como essas inovações podem aumentar sua vantagem competitiva.",
        "rede": "Instagram"
      },
      {
        "id": 159,
        "titulo": "Sucesso em 2024: Lições de Empresas que Usaram IA para Transformar o Marketing",
        "texto": "Análise de casos de sucesso no uso de IA no marketing, destacando como grandes marcas têm alcançado resultados extraordinários através de estratégias inovadoras potencializadas pela tecnologia.",
        "rede": "Instagram"
      },
      {
        "id": 160,
        "titulo": "Implementação Estratégica: Maximize os Benefícios da IA em Sua Empresa",
        "texto": "Oferecemos um guia prático para integrar IA em suas operações, focando na criação de valor real e auxiliar sua equipe a se concentrar em atividades estratégicas, otimizando processos e decisões empresariais.",
        "rede": "Instagram"
      }
    ]
  }
]
```

### **Fluxo de Geração de Pautas:**
1. Usuário clica em "Gerar Pauta"
2. Modal abre com campos:
   - Tema (input text)
   - Rede Social (select: Facebook, Instagram, etc)
   - Botões: "Gerar" e "Cancelar"
3. Usuário preenche e clica "Gerar"
4. Sistema monta payload com:
   - Dados do usuário e organização
   - KnowledgeBase completa (marketing_input_summary)
   - Tema e rede selecionados
5. Envia para N8N
6. N8N processa e retorna array de pautas
7. Sistema salva cada pauta no banco
8. Cards são atualizados na página (sem refresh)
9. Notificação de sucesso exibida

---

## 📝 MODAL DE CRIAÇÃO DE PAUTAS

### **Campos do Modal:**
- **Tema:** Input text (obrigatório)
  - Placeholder: "Ex: mamografia, marketing digital, etc"
- **Rede Social:** Select (obrigatório)
  - Opções: Facebook, Instagram, LinkedIn, Twitter, etc
- **Botões:** "Gerar Pauta" e "Cancelar"

### **Validações:**
- Tema: mínimo 3 caracteres, máximo 100
- Rede: seleção obrigatória
- Rate limiting: 1 requisição por minuto por usuário

### **Estados do Modal:**
- **Normal:** Campos vazios, botão "Gerar Pauta" habilitado
- **Processando:** Loading, botão desabilitado, mensagem "Gerando pautas..."
- **Sucesso:** Modal fecha, notificação aparece, cards atualizados
- **Erro:** Mensagem de erro exibida, modal permanece aberto

---

## 🚀 PRÓXIMOS PASSOS

### **Concluído:**
- ✅ Estrutura geral da página
- ✅ Fluxo de edição inline (card expansível)
- ✅ Integração N8N com payloads completos
- ✅ Modal de criação com validações
- ✅ Modelo de dados detalhado

### **Pendente de Definição:**
- [ ] Fluxo do botão "Gerar Post" (a partir da pauta)
- [ ] Estrutura dos filtros (campos específicos)
- [ ] Lógica de paginação (limit, offset)
- [ ] Funcionalidade de exclusão (confirmação?)
- [ ] Tags e categorização das pautas
- [ ] Status workflow (draft → approved → published)
- [ ] Integração com módulo de Posts

---

## ❓ RESPOSTAS DEFINIDAS PELO USUÁRIO

### **1. Filtros: ✅ DEFINIDO**
- **Campos:** rede social, status, data
- **Implementação:** 
  ```html
  <!-- Filtros na página -->
  <select name="rede">Facebook, Instagram, LinkedIn...</select>
  <select name="status">Requested, Generated</select>
  <input type="date" name="data_inicio">
  <input type="date" name="data_fim">
  ```

### **2. Paginação: ✅ DEFINIDO**
- **Cards por página:** 5
- **Busca textual:** Não implementada inicialmente
- **Implementação:** Django Paginator com 5 itens por página

### **3. Botão "Gerar Post": ✅ DEFINIDO**
- **Fluxo:** Clica → abre modal → preencher → "Gerar" → envia para N8N (fluxo diferente)
- **Modal:** Conforme imagem de referência
- **Payload:** Diferente do de pautas (definir posteriormente)
- **Endpoint:** Outro endpoint N8N específico para posts
- **Vínculo:** Post criado terá ForeignKey `pauta_origem` para a pauta de origem

### **4. Exclusão: ✅ DEFINIDO**
- **Tipo:** Exclusão FÍSICA (não arquivamento)
- **Confirmação:** Modal de confirmação obrigatória
- **Escopo:** Apenas pautas da empresa logada podem ser excluídas
- **Auditoria:** Registro em audit_history antes de excluir


### **5. Permissões: ✅ PARCIALMENTE DEFINIDO**
- **Habilitação por empresa:** Verificar se empresa contratou o módulo
- **Mensagem indisponibilidade:** "Ferramenta não disponível. Entre em contato para contratar."
- **Visibilidade:** Apenas pautas da organização do usuário (multi-tenancy)
- **Ações:** Todos os usuários podem criar/editar (se módulo contratado)

### **6. Performance: 📋 RECOMENDAÇÕES**
- **Lazy Loading:** 
  - **Recomendação:** Não necessário com apenas 5 cards por página
  - Implementar apenas se crescimento for grande
- **Cache:**
  - **Recomendação:** Redis para pautas recentes (últimas 24h)
  - Cache por organização para performance
- **Limite por organização:**
  - **Recomendação:** Limite baseado no plano contratado
  - Ex: Plano Básico: 100 pautas/mês, Premium: Ilimitado

---

## 🔧 IMPLEMENTAÇÕES RECOMENDADAS


### **1. Filtros na View**
```python
def pautas_list_view(request):
    queryset = Pauta.objects.filter(organization=request.user.organization)
    
    # Aplicar filtros
    rede = request.GET.get('rede')
    if rede:
        queryset = queryset.filter(rede_social=rede)
    
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)
    
    # ... outros filtros
    
    paginator = Paginator(queryset, 5)
    page = request.GET.get('page')
    pautas = paginator.get_page(page)
```

### **2. Middleware de Verificação de Módulo**
```python
class ModuleCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/pautas/'):
            if not request.user.organization.has_pautas_module:
                return render('module_not_available.html')
        return self.get_response(request)
```

---

## 🚀 PRÓXIMOS PASSOS (ATUALIZADO)

### **Concluído:**
- ✅ Estrutura geral da página
- ✅ Fluxo de edição inline (card expansível)
- ✅ Integração N8N com payloads completos
- ✅ Modal de criação com validações
- ✅ Modelo de dados completo com auditoria
- ✅ Filtros definidos (rede, status, data)
- ✅ Paginação: 5 cards por página
- ✅ Fluxo "Gerar Post" (modal → N8N)
- ✅ Permissões por empresa/módulo
- ✅ Recomendações de performance

### **Pendentes:**
- ✅ NENHUMA!

### **Próximo Passo Imediato:**
✅ **PRONTO PARA IMPLEMENTAR!**

---

---

## 🚀 IMPLEMENTAÇÃO - PODEMOS COMEÇAR

### **Estrutura de Arquivos a Criar:**
```
app/apps/pautas/
├── __init__.py
├── models.py          # Modelo Pauta
├── views.py           # Views de listagem, criação, edição, exclusão
├── urls.py            # URLs do app
├── forms.py           # Formulários
├── services/
│   ├── __init__.py
│   └── n8n_service.py # Serviço N8N para pautas
└── migrations/

templates/pautas/
├── pautas_list.html   # Página principal
└── partials/
    ├── pauta_card.html      # Card individual
    ├── pauta_card_edit.html # Card editável
    └── modal_gerar_pauta.html # Modal de criação
```

### **Passos da Implementação:**
1. **Criar modelo Pauta** (com auditoria)
2. **Criar serviço N8N** (envio e webhook)
3. **Criar views** (listagem, CRUD)
4. **Criar templates** (página, cards, modais)
5. **Criar URLs** e configurar
6. **Adicionar middleware** de verificação de módulo
7. **Testar integração** N8N

### **Dados Disponíveis em Banco:**
- ✅ **Empresa:** `organization.name`
- ✅ **Usuário:** `user.email`
- ✅ **Organization ID:** `organization.id`
- ✅ **Knowledge Base:** `kb.id`, `kb.company_name`, `kb.marketing_input_summary`
- ✅ **Audit Log:** Sistema existente para rastreio

**Status:** 🎯 **PRONTO PARA COMEÇAR IMPLEMENTAÇÃO**

---
