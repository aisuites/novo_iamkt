# 🗺️ IAMKT - ROADMAP DE DESENVOLVIMENTO

**Documento:** 09 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

O desenvolvimento do IAMKT está dividido em **2 grandes fases**:
- **Fase 1 (MVP)**: Funcionalidades essenciais - 2 a 3 meses
- **Fase 2 (Expansão)**: Funcionalidades avançadas - 2 a 3 meses

---

## 📦 FASE 1 - MVP (2-3 MESES)

### Objetivo
Entregar plataforma funcional com ferramentas essenciais de geração de conteúdo.

### Funcionalidades Prioritárias

✅ **Entregas Obrigatórias:**
1. Base de Conhecimento FEMME (7 blocos)
2. Geração de Pautas
3. Geração de Posts (imagem + legenda)
4. Simulador de Feed
5. Monitoramento de Trends
6. Pesquisa Web e Insights
7. Sistema de Aprovação
8. Gestão de Usuários por Áreas

---

### ETAPA 1: FUNDAÇÃO (Semanas 1-2)

#### 1.1 Setup Infraestrutura
**Duração:** 3 dias

- [x] Criar estrutura Docker
  - Containers: web, postgres, redis, celery, beat
  - Rede isolada 172.22.0.0/24
  - Volumes persistentes
- [x] Configurar Traefik
  - SSL/HTTPS automático
  - Routing para iamkt-femmeintegra.aisuites.com.br
- [x] Setup Django
  - Projeto "sistema/"
  - Apps: core, knowledge, content, campaigns
  - Arquivo __init__.py obrigatório em apps/

**Entregável:** Ambiente dev rodando com healthcheck

---

#### 1.2 Models Core
**Duração:** 4 dias

- [ ] App `core`
  - Model User (email obrigatório)
  - Model Area
  - Model UsageLimit
  - Model AuditLog
  - Model SystemConfig

- [ ] Migrations iniciais
- [ ] Admin Django configurado
- [ ] Fixtures com dados de teste

**Entregável:** Models criados e testados no admin

---

#### 1.3 Autenticação e Permissões
**Duração:** 3 dias

- [ ] Sistema de login/logout
- [ ] Middleware de permissões por área
- [ ] Decorators para views
  - `@login_required`
  - `@area_required(['pautas', 'posts'])`
  - `@perfil_required(['gestor', 'admin'])`
- [ ] Testes unitários de permissões

**Entregável:** Autenticação funcionando com controle de áreas

---

### ETAPA 2: BASE TEMPLATE (Semanas 3-4)

#### 2.1 Template Base e CSS
**Duração:** 4 dias

- [ ] Layout padrão
  - Header (logo, notificações, perfil)
  - Sidebar recolhível
  - Content area
  - Footer
- [ ] CSS estruturado (SEM inline)
  - `/static/css/base.css`
  - `/static/css/components.css`
  - `/static/css/pages.css`
- [ ] Responsivo (mobile-first)
- [ ] Design system FEMME (cores, tipografia)

**Entregável:** Template base funcionando em todas as páginas

---

#### 2.2 Dashboard Principal
**Duração:** 3 dias

- [ ] Dashboard por perfil
  - Admin: métricas globais
  - Gestor: aprovações + métricas área
  - Operacional: ferramentas + seus conteúdos
- [ ] Cards de métricas
- [ ] Quick actions
- [ ] Últimas atividades

**Entregável:** Dashboard funcional para cada perfil

---

#### 2.3 Sistema de Notificações
**Duração:** 3 dias

- [ ] Badge de notificações no header
- [ ] Modal de notificações
- [ ] Tipos: aprovação, alerta, info
- [ ] Marcar como lida
- [ ] Integração com workflow

**Entregável:** Sistema de notificações in-app funcionando

---

### ETAPA 3: BASE DE CONHECIMENTO (Semana 5)

#### 3.1 Models Knowledge
**Duração:** 3 dias

- [ ] Model KnowledgeBase (singleton)
- [ ] Model ColorPalette
- [ ] Model SocialNetwork
- [ ] Model SocialNetworkTemplate
- [ ] Model CustomFont
- [ ] Model ReferenceImage
- [ ] Model Competitor
- [ ] Model ChangeLog

**Entregável:** Models de knowledge completos

---

#### 3.2 Interface Sanfona
**Duração:** 4 dias

- [ ] Página de edição com accordion
- [ ] 7 blocos expansíveis
- [ ] Salvamento individual por bloco
- [ ] Salvamento geral
- [ ] Indicadores de completude
- [ ] Validações de campos obrigatórios

**Entregável:** Base FEMME editável via interface

---

### ETAPA 4: PRIMEIRA FERRAMENTA - PAUTAS (Semanas 6-7)

#### 4.1 Integração OpenAI
**Duração:** 3 dias

- [ ] Configurar API keys
- [ ] Wrapper para OpenAI API
- [ ] Sistema de cache Redis
- [ ] Tratamento de erros e retries
- [ ] Tracking de tokens e custos

**Entregável:** Integração OpenAI funcionando

---

#### 4.2 Geração de Pautas
**Duração:** 5 dias

- [ ] Formulário de inputs
  - Tema, público, objetivo, projeto, modelo IA
- [ ] Celery task assíncrona
- [ ] Busca fontes confiáveis + web genérica
- [ ] Montagem de prompt estruturado
- [ ] Interface de resultados
  - Cards de pautas
  - Fontes pesquisadas
  - Botões: editar, favoritar, usar
- [ ] Salvamento no histórico

**Entregável:** Geração de pautas completa e funcional

---

### ETAPA 5: POSTS E SIMULADOR (Semanas 8-9)

#### 5.1 Integração DALL-E 3
**Duração:** 2 dias

- [ ] Wrapper para DALL-E API
- [ ] Upload de imagem para S3
- [ ] Geração de thumbnails

**Entregável:** Geração de imagens funcionando

---

#### 5.2 Geração de Posts
**Duração:** 5 dias

- [ ] Formulário de inputs
  - Tema, rede social, template, estilo, modo
- [ ] Modo API: geração automática
- [ ] Modo Prompt Manual: gera prompt otimizado
- [ ] Geração paralela: imagem + legenda
- [ ] Preview individual do post
- [ ] Upload de imagem externa
- [ ] Vinculação a projeto obrigatória

**Entregável:** Geração de posts completa

---

#### 5.3 Simulador de Feed
**Duração:** 5 dias

- [ ] Workspace: biblioteca + mockup
- [ ] Drag-and-drop de posts
- [ ] Mockups por rede social
  - Instagram Feed, Stories
  - LinkedIn Feed
  - Facebook Feed
- [ ] Scroll no mockup
- [ ] Reordenação de posts
- [ ] Upload de imagem externa
- [ ] Export (screenshot, PPTX, link)

**Entregável:** Simulador de feed funcional

---

### ETAPA 6: TRENDS E PESQUISA (Semana 10)

#### 6.1 Monitoramento de Trends
**Duração:** 3 dias

- [ ] Scraping de fontes padrão
  - Google Trends API
  - Think with Google
  - Reddit
  - Twitter/X
- [ ] Scraping de fontes customizadas
- [ ] Análise de relevância com IA
- [ ] Celery Beat: task diária às 6h
- [ ] Dashboard de trends
- [ ] Alertas por email

**Entregável:** Monitoramento automático de trends

---

#### 6.2 Pesquisa Web
**Duração:** 3 dias

- [ ] Scraping com Playwright
- [ ] Extração e limpeza de conteúdo
- [ ] Análise com IA
- [ ] Geração de relatório
- [ ] Export PDF
- [ ] Salvamento no histórico

**Entregável:** Pesquisa web funcional

---

### ETAPA 7: WORKFLOW DE APROVAÇÃO (Semana 11)

#### 7.1 Sistema de Aprovação
**Duração:** 4 dias

- [ ] Model Approval
- [ ] Model ApprovalComment
- [ ] Envio para aprovação (operacional)
- [ ] Interface de aprovação (gestor)
  - Aprovar
  - Solicitar ajustes
  - Reprovar
- [ ] Thread de comentários
- [ ] Notificações email + in-app

**Entregável:** Workflow de aprovação completo

---

#### 7.2 Aprovação via Email
**Duração:** 2 dias

- [ ] Email parser
- [ ] Comandos: APROVADO, AJUSTES, REPROVADO
- [ ] Validação de segurança
- [ ] Processamento assíncrono
- [ ] Testes de integração

**Entregável:** Aprovação via email funcionando

---

### ETAPA 8: GESTÃO DE PROJETOS (Semana 12)

#### 8.1 Projetos e Campanhas
**Duração:** 3 dias

- [ ] Model Project com tipologia
- [ ] CRUD de projetos
- [ ] Vinculação de conteúdos
- [ ] Dashboard de projetos
- [ ] Métricas por projeto

**Entregável:** Gestão básica de projetos

---

#### 8.2 Integrações Finais
**Duração:** 3 dias

- [ ] Integração Gemini API
- [ ] Integração Grok API
- [ ] Sistema de fallback entre APIs
- [ ] Testes de integração completos

**Entregável:** Todas APIs integradas

---

### ETAPA 9: MÉTRICAS E RELATÓRIOS (Semana 13)

#### 9.1 Tracking de Uso
**Duração:** 3 dias

- [ ] Model IAModelUsage
- [ ] Tracking automático em cada geração
  - Tokens, custo, tempo, modelo
- [ ] Controle de limites por área
- [ ] Alertas aos 80%
- [ ] Bloqueio aos 100%

**Entregável:** Sistema de limites funcionando

---

#### 9.2 Dashboard de Métricas
**Duração:** 3 dias

- [ ] Métricas globais (admin)
- [ ] Métricas por área (gestor)
- [ ] Gráficos e visualizações
  - Chart.js ou similar
- [ ] Filtros por período
- [ ] Export CSV

**Entregável:** Dashboard de métricas completo

---

### ETAPA 10: TESTES E QA (Semanas 14-15)

#### 10.1 Testes Automatizados
**Duração:** 5 dias

- [ ] Testes unitários (coverage > 80%)
  - Models
  - Views
  - Utils
- [ ] Testes de integração
  - Workflows completos
  - APIs externas (mocked)
- [ ] Testes de permissões
- [ ] Testes de performance

**Entregável:** Suite de testes completa

---

#### 10.2 Testes Manuais e Correções
**Duração:** 5 dias

- [ ] Testes exploratórios
- [ ] Testes de usabilidade
- [ ] Correção de bugs encontrados
- [ ] Melhorias de UX
- [ ] Testes de segurança básicos

**Entregável:** Sistema estável para produção

---

### ETAPA 11: DOCUMENTAÇÃO (Semana 16)

#### 11.1 Documentação Técnica
**Duração:** 3 dias

- [ ] README completo
- [ ] Guia de instalação
- [ ] Guia de desenvolvimento
- [ ] Documentação de APIs
- [ ] Diagramas atualizados

**Entregável:** Docs técnica completa

---

#### 11.2 Documentação de Usuário
**Duração:** 2 dias

- [ ] Manual do usuário (PDF)
- [ ] Tutoriais em vídeo (opcional)
- [ ] FAQ
- [ ] Guia de troubleshooting

**Entregável:** Docs de usuário completa

---

### ETAPA 12: DEPLOY E PRODUÇÃO (Semana 17)

#### 12.1 Preparação para Produção
**Duração:** 3 dias

- [ ] Configurações de produção
  - DEBUG=False
  - ALLOWED_HOSTS
  - SECRET_KEY seguro
- [ ] Otimizações
  - Static files collected
  - Database indexes
  - Cache configurado
- [ ] Backup automatizado
- [ ] Monitoring (logs, erros)

**Entregável:** Sistema pronto para produção

---

#### 12.2 Deploy e Go-Live
**Duração:** 2 dias

- [ ] Deploy em produção
- [ ] Smoke tests em produção
- [ ] Migração de dados (se necessário)
- [ ] Treinamento usuários-chave
- [ ] Go-live oficial

**Entregável:** Sistema em produção!

---

## 🚀 FASE 2 - EXPANSÃO (2-3 MESES)

### Objetivo
Adicionar funcionalidades avançadas e integrações completas.

### Funcionalidades Planejadas

#### 1. Novas Ferramentas de Geração (1 mês)

**1.1 Geração de Textos para Blog**
- Templates: SEO Article, Tutorial, Case Study, Listicle
- Editor rico (WYSIWYG)
- Preview com formatação
- Export DOCX, HTML, PDF

**1.2 Roteiros de Vídeo**
- Templates: YouTube Long, Shorts/Reels, Explainer
- Marcações de tempo
- Sugestões de B-roll
- Export TXT, PDF

**1.3 Avatar Fê + VEO3**
- Integração com VEO3
- Avatar personalizado "Fê"
- Geração de vídeos curtos
- Preview antes de renderizar

**1.4 Apresentações (PPTX)**
- Templates corporativos
- Slides automáticos baseados em conteúdo
- Gráficos e imagens
- Export editável

---

#### 2. Calendário Editorial (2 semanas)

- [ ] View mensal/semanal/diária
- [ ] Drag-and-drop para agendar
- [ ] Filtros (tipo, área, status)
- [ ] Timeline view
- [ ] Export do calendário

---

#### 3. Integração Redes Sociais (3 semanas)

**3.1 Meta Business Suite**
- Conexão com Instagram/Facebook
- Postagem automática
- Agendamento
- Tracking de métricas

**3.2 LinkedIn API**
- Postagem em páginas empresa
- Agendamento
- Analytics básicos

**3.3 Twitter API**
- Postagem
- Threading automático
- Agendamento

---

#### 4. Biblioteca de Assets Completa (2 semanas)

- [ ] Upload em lote
- [ ] Categorias e tags avançadas
- [ ] Busca inteligente (OCR em imagens)
- [ ] Preview inline
- [ ] Tracking de uso
- [ ] Sugestões de IA

---

#### 5. AWS Athena + Bedrock (3 semanas)

**5.1 Integração Athena**
- Conexão com banco analítico
- Queries pré-definidas executáveis
- Cache de resultados
- Visualização de dados

**5.2 Insights com Bedrock**
- Análise de dados do Athena
- Geração de insights não óbvios
- Sugestões de campanhas
- Relatórios automáticos

---

#### 6. Analytics Avançados (2 semanas)

- [ ] Dashboard completo
- [ ] Análise de performance por:
  - Usuário
  - Área
  - Ferramenta
  - Modelo IA
  - Período
- [ ] Comparações e benchmarks
- [ ] Previsões (ML simples)
- [ ] Relatórios customizáveis
- [ ] Email automático semanal/mensal

---

#### 7. Colaboração Avançada (1 semana)

- [ ] Versionamento de conteúdo
- [ ] Co-edição (opcional)
- [ ] Compartilhamento entre áreas
- [ ] Templates compartilháveis
- [ ] Biblioteca de snippets

---

#### 8. Performance e Otimizações (1 semana)

- [ ] Otimização de queries
- [ ] Cache agressivo
- [ ] Lazy loading
- [ ] Compressão de assets
- [ ] CDN para static files

---

## 📊 CRONOGRAMA VISUAL

### Fase 1 (17 semanas)

```
Semanas 1-2  : ████ Fundação
Semanas 3-4  : ████ Templates
Semana 5     : ██ Base FEMME
Semanas 6-7  : ████ Pautas
Semanas 8-9  : ████ Posts + Simulador
Semana 10    : ██ Trends + Pesquisa
Semana 11    : ██ Aprovações
Semana 12    : ██ Projetos
Semana 13    : ██ Métricas
Semanas 14-15: ████ Testes
Semana 16    : ██ Documentação
Semana 17    : ██ Deploy

TOTAL: 17 semanas (≈ 4 meses)
```

### Fase 2 (8-12 semanas)

```
Mês 1: Novas Ferramentas
Mês 2: Calendário + Redes Sociais + Assets
Mês 3: Athena/Bedrock + Analytics + Otimizações

TOTAL: 8-12 semanas (≈ 2-3 meses)
```

---

## 🎯 CRITÉRIOS DE SUCESSO

### Fase 1 - MVP

| Métrica | Target |
|---------|--------|
| **Funcionalidades Core** | 100% implementadas |
| **Cobertura de Testes** | > 80% |
| **Performance** | < 2s carregamento de páginas |
| **Uptime** | > 99% após go-live |
| **Satisfação Usuários** | > 4/5 nas pesquisas |

### Fase 2 - Expansão

| Métrica | Target |
|---------|--------|
| **Novas Ferramentas** | 4/4 funcionando |
| **Integrações Sociais** | 3/3 redes conectadas |
| **Performance** | Mantida ou melhorada |
| **Adoção** | > 80% dos usuários usando novas features |

---

**Próximo documento:** [10_IAMKT_Especificacoes_Tecnicas.md](10_IAMKT_Especificacoes_Tecnicas.md)
