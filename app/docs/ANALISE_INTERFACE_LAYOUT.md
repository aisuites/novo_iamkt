# 📋 ANÁLISE PROFUNDA - INTERFACE E LAYOUT IAMKT

**Data:** 12/01/2026  
**Fonte:** Análise completa dos arquivos docs/onboarding/

---

## ✅ ESTRUTURA DE LAYOUT CONFIRMADA

### Layout Padrão (Arquivo 01_IAMKT_Visao_Geral.md, linhas 224-242)

```
┌─────────────────────────────────────────────────┐
│ Header: Logo | Notificações | Perfil | Área    │
├──────────┬──────────────────────────────────────┤
│          │                                       │
│ Sidebar  │     Área de Conteúdo                 │
│ (Menu)   │                                       │
│          │                                       │
│ ☰        │                                       │
│          │                                       │
│ Dashboard│                                       │
│ Base     │                                       │
│ Ferramen.│                                       │
│ Projetos │                                       │
│ Relatórs │                                       │
│          │                                       │
│ [Admin]  │                                       │
└──────────┴──────────────────────────────────────┘
```

### Características Obrigatórias

1. ✅ **Sidebar recolhível** com ícone ☰
2. ✅ **Responsivo**: mobile usa menu hambúrguer
3. ✅ **Design consistente** em todas as páginas
4. ✅ **Zero CSS inline** - tudo estruturado em arquivos
5. ✅ **Header fixo** com logo, notificações, perfil, área

---

## 📱 ESTRUTURA DE NAVEGAÇÃO

### Sidebar (Menu Lateral Esquerdo)

**Itens do Menu:**
1. 📊 Dashboard
2. 📚 Base FEMME (Base de Conhecimento)
3. 🛠️ Ferramentas
   - 📝 Geração de Pautas
   - 🎨 Geração de Posts
   - 📈 Monitoramento de Trends
   - 🔍 Pesquisa Web
   - 📱 Simulador de Feed
4. 🚀 Projetos/Campanhas
5. 📊 Relatórios
6. ⚙️ [Admin] (apenas para Admin/TI)

### Header (Topo Fixo)

**Elementos:**
- Logo FEMME (clicável → Dashboard)
- Notificações (sino com badge)
- Perfil do usuário (avatar + nome)
- Área atual (dropdown se múltiplas áreas)
- Botão Sair

---

## 🎨 PÁGINAS PRINCIPAIS

### 1. Dashboard
**Arquivo:** 09_IAMKT_Roadmap.md, linhas 92-108

**Elementos:**
- Cards informativos dinâmicos
- Estatísticas de uso
- Atividades recentes
- Trends em destaque
- Ações rápidas

### 2. Base de Conhecimento FEMME
**Arquivo:** 05_IAMKT_Base_Conhecimento.md, linhas 463-468

**Layout:** Interface Sanfona (Accordion)

```
┌─────────────────────────────────────────────────┐
│ CORAÇÃO DA INTELIGÊNCIA DE MARKETING            │
│                                                  │
│ Configure a Base FEMME usada por todas as       │
│ ferramentas de IA.                               │
│                                                  │
│ ▼ BLOCO 1: Identidade Institucional             │
│   [Campos do bloco 1...]                         │
│   [Botão: Salvar Bloco 1]                        │
│                                                  │
│ ▶ BLOCO 2: Público e Segmentos                  │
│                                                  │
│ ▶ BLOCO 3: Posicionamento e Diferenciais        │
│                                                  │
│ ▶ BLOCO 4: Tom de Voz e Linguagem               │
│                                                  │
│ ▶ BLOCO 5: Identidade Visual                    │
│                                                  │
│ ▶ BLOCO 6: Sites e Redes Sociais                │
│                                                  │
│ ▶ BLOCO 7: Dados e Insights                     │
│                                                  │
│ [Botão: Salvar Tudo]                             │
└─────────────────────────────────────────────────┘
```

**Características:**
- 7 blocos expansíveis (accordion)
- Salvamento individual por bloco
- Salvamento geral (todos de uma vez)
- Indicador de completude (%)
- Validações de campos obrigatórios

### 3. Geração de Pautas
**Arquivo:** 04_IAMKT_Funcionalidades_Fase1.md, linhas 111-119

**Interface:**
- Formulário de inputs (tema, público, objetivo, projeto, modelo IA)
- Lista de cards com título + descrição
- Seção "Fontes Pesquisadas" expansível em cada card
- Links clicáveis para validação
- Badge: "Fonte Confiável" ou "Web Genérica"
- Botões: Editar, Favoritar (estrela), Usar esta pauta

### 4. Geração de Posts
**Arquivo:** 04_IAMKT_Funcionalidades_Fase1.md, linhas 219-223

**Interface:**
- Formulário de inputs (tema, rede social, template, estilo, modo, modelo IA)
- Preview da imagem
- Legenda editável
- Contador de caracteres
- Botões: Gerar Novamente, Salvar, Enviar para Aprovação

### 5. Simulador de Feed
**Arquivo:** 04_IAMKT_Funcionalidades_Fase1.md, linhas 291-297

**Layout:** 3 colunas

```
┌──────────┬──────────────┬──────────┐
│ Biblioteca│  Feed Canvas │  Preview │
│  (Posts)  │  (Arrastar)  │  (Mock)  │
└──────────┴──────────────┴──────────┘
```

**Características:**
- Interface realista da rede social escolhida
- Scroll vertical no feed
- Reordenação: arrastar posts
- Remover posts: arrastar de volta

### 6. Monitoramento de Trends
**Arquivo:** 04_IAMKT_Funcionalidades_Fase1.md, linhas 470-473

**Dashboard de Trends:**
- Cards de trends com score
- Filtros: relevância, data, fonte
- Botão "Buscar Trends Agora" (manual)
- Gráfico de evolução temporal

### 7. Interface de Aprovação
**Arquivo:** 08_IAMKT_Workflow_Aprovacoes.md, linhas 180-183

**Dashboard do Gestor:**
- Lista de conteúdos pendentes
- Preview do conteúdo
- Opções: Aprovar, Solicitar Ajustes, Reprovar
- Campo de comentários
- Histórico de aprovações

---

## 🎨 DESIGN SYSTEM

### Cores (Base FEMME)
```css
--femme-purple: #58236d
--femme-purple-soft: #b8a1c6
--femme-purple-dark: #32123f
--femme-bg: #fefefe
--femme-border: #e7e3ee
```

### Tipografia
```css
--font-family: "Quicksand"
--font-size-base: 0.9rem
--font-size-xl: 1.1rem
--font-size-2xl: 1.4rem
```

### Espaçamentos
```css
--spacing-4: 1rem (16px)
--spacing-6: 1.5rem (24px)
--spacing-8: 2rem (32px)
```

### Border Radius
```css
--radius-lg: 12px
--radius-xl: 14px
--radius-2xl: 16px
```

### Sombras
```css
--shadow-sm: 0 2px 5px rgba(26, 10, 32, 0.08)
--shadow-md: 0 6px 16px rgba(88, 35, 109, 0.25)
--shadow-lg: 0 10px 30px rgba(88, 35, 109, 0.08)
```

---

## 📏 PADRÕES DE DESENVOLVIMENTO

### CSS (PLANO_DESENVOLVIMENTO_GENERICO.md, linhas 29-34)
- ✅ **Zero CSS inline**
- ✅ **CSS estruturado** em arquivos separados
- ✅ **Responsivo** (mobile-first)
- ✅ **Acessibilidade** (WCAG básicos)

### Performance (10_IAMKT_Especificacoes_Tecnicas.md, linhas 585-591)
- ✅ **Tempo de carregamento**: < 2s para páginas principais
- ✅ **Tempo resposta API**: < 500ms
- ✅ **Geração de conteúdo**: < 30s (async)
- ✅ **Uptime**: > 99.5%

### Segurança (PLANO_DESENVOLVIMENTO_GENERICO.md, linhas 35-39)
- ✅ **Autenticação obrigatória**: Todas as páginas protegidas
- ✅ **CSRF protection**: Todos os forms
- ✅ **Dados sanitizados**: Validação de inputs
- ✅ **Audit trail**: Log de ações críticas

---

## 🎯 IMPLEMENTAÇÃO NECESSÁRIA

### 1. Corrigir Erro Atual
- ✅ Corrigir `NoReverseMatch` para 'dashboard'
- ✅ Usar namespace correto: `'core:dashboard'`

### 2. Criar Sidebar Component
- Sidebar lateral esquerda
- Menu com ícones e labels
- Recolhível (ícone ☰)
- Responsivo (hambúrguer mobile)
- Active state nos itens

### 3. Atualizar Base Template
- Layout: Header + Sidebar + Content
- Sidebar fixa à esquerda (240px)
- Content area com padding adequado
- Responsivo (breakpoints)

### 4. Criar Templates Restantes
- Base de Conhecimento (accordion)
- Geração de Pautas (form + cards)
- Geração de Posts (form + preview)
- Simulador de Feed (3 colunas)
- Monitoramento de Trends (dashboard)
- Interface de Aprovação (lista + preview)

---

## ✅ CONCLUSÃO

**Estrutura de Layout Confirmada:**
- Header fixo no topo
- Sidebar lateral esquerda (recolhível)
- Área de conteúdo principal
- Footer (opcional)

**Próximos Passos:**
1. Corrigir erro de URL (namespace)
2. Criar sidebar component
3. Atualizar base.html com layout correto
4. Implementar templates conforme especificações
5. Testar responsividade
6. Validar performance

**Referência de Imagem:**
A imagem anexada pelo usuário mostra exatamente este layout:
- Sidebar roxa à esquerda com navegação
- Área de conteúdo à direita
- Header no topo
- Design limpo e moderno
