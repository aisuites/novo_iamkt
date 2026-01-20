# Log de Desenvolvimento - IAMKT MVP

## Data: 12/01/2026

### ✅ Etapa 1.1-1.3: Fundação Completa

#### Apps Django Criadas
- ✅ `apps.core` - Autenticação, usuários, áreas, limites, auditoria
- ✅ `apps.knowledge` - Base de Conhecimento FEMME (7 blocos completos)
- ✅ `apps.content` - Geração de conteúdo, pautas, posts, trends, métricas
- ✅ `apps.campaigns` - Projetos e workflow de aprovação

#### Models Implementados

**Core (5 models):**
- `User` - Usuário customizado com perfis e múltiplas áreas
- `Area` - Áreas organizacionais com hierarquia
- `UsageLimit` - Limites mensais de uso por área
- `AuditLog` - Log de auditoria de ações críticas
- `SystemConfig` - Configurações globais do sistema

**Knowledge (6 models):**
- `KnowledgeBase` - Base FEMME singleton com 7 blocos temáticos
- `ReferenceImage` - Imagens de referência com hash perceptual
- `CustomFont` - Fontes customizadas
- `Logo` - Logos da empresa
- `Competitor` - Concorrentes
- `KnowledgeChangeLog` - Histórico de alterações

**Content (7 models):**
- `Pauta` - Pautas geradas por IA
- `GeneratedContent` - Conteúdo gerado (posts, imagens, legendas)
- `Asset` - Biblioteca de assets
- `TrendMonitor` - Monitoramento de trends
- `WebInsight` - Insights de pesquisa web
- `IAModelUsage` - Tracking detalhado de uso de IA
- `ContentMetrics` - Métricas do ciclo de vida do conteúdo

**Campaigns (4 models):**
- `Project` - Projetos/campanhas
- `Approval` - Workflow de aprovação
- `ApprovalComment` - Comentários de aprovação
- `ProjectContent` - Relacionamento projeto-conteúdo

**Total: 22 models implementados**

#### Configurações

**Settings (sistema/settings/base.py):**
- ✅ Apps registradas
- ✅ Custom User Model (`AUTH_USER_MODEL = 'core.User'`)
- ✅ Celery configurado
- ✅ Redis cache configurado
- ✅ Integrações IA (OpenAI, Gemini, Perplexity)
- ✅ AWS S3 configurado
- ✅ Limites de uso configuráveis

**Environment:**
- ✅ `.env.development` - Ambiente de desenvolvimento
- ✅ `.env.production` - Template para produção
- ✅ `.env.example` - Exemplo público
- ✅ `.env` - Link simbólico para development

**Dependencies (requirements.txt):**
- ✅ Django 4.2.8
- ✅ PostgreSQL (psycopg2-binary)
- ✅ Redis + Celery
- ✅ DRF + CORS
- ✅ OpenAI SDK
- ✅ Google Generative AI
- ✅ Boto3 (AWS S3)
- ✅ BeautifulSoup + Playwright
- ✅ pytrends
- ✅ imagehash

#### Django Admin
- ✅ Todos os 22 models registrados
- ✅ Interfaces customizadas com fieldsets
- ✅ Filtros e buscas configurados
- ✅ Inlines para relacionamentos
- ✅ Permissões especiais (KnowledgeBase singleton, logs read-only)

### 🔄 Próximas Etapas

**Etapa 1.4:** Criar migrations do banco de dados
**Etapa 1.5:** Criar utils para S3 (upload, signed URLs)
**Etapa 1.6:** Criar utils para integrações IA
**Etapa 1.7:** Criar Celery tasks básicos
**Etapa 1.8:** Criar fixtures com dados reais da FEMME

### 📝 Decisões Técnicas

1. **Base de Conhecimento Completa:** Implementados todos os 7 blocos desde o início (não simplificado)
2. **Dual IA Provider:** Suporte para OpenAI e Gemini desde MVP
3. **Perplexity para Pesquisa:** Substituição de scraping manual por API Perplexity
4. **Métricas Detalhadas:** Tracking completo de tokens, custos e tempos desde o início
5. **S3 Obrigatório:** Todos os arquivos no S3 desde desenvolvimento
6. **Aprovação Flexível:** Operacional pode auto-aprovar ou enviar para gestor
7. **Limite de 100 gerações:** Área Marketing começa com 100 gerações/mês

### 🎯 Requisitos Confirmados

- ✅ Base FEMME completa (7 blocos)
- ✅ Geração de Pautas (Base FEMME + OpenAI + Perplexity)
- ✅ Geração de Posts (GPT + Gemini)
- ✅ Arquitetura preparada para Simulador de Feed (Fase 2)
- ✅ Aprovação via web (operacional pode aprovar)
- ✅ Monitoramento de Trends (pytrends)
- ✅ Métricas de tokens, custo e tempo
- ✅ S3 para todos os arquivos
- ✅ Ambientes dev/prod separados

### ⚠️ Observações Importantes

- Aplicação isolada em `/opt/iamkt/`
- Não instalar dependências globalmente
- Manter isolamento de outras aplicações do servidor
- Fixtures serão criados com dados reais da FEMME
- S3 bucket de dev: `iamkt-assets-dev`
- S3 bucket de prod: `iamkt-assets`
