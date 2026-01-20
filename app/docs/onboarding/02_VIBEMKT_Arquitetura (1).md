# 🏗️ IAMKT - ARQUITETURA DO SISTEMA

**Documento:** 02 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 📊 VISÃO ARQUITETURAL

O IAMKT segue a **arquitetura padrão do servidor FEMME** com isolamento completo em rede Docker, garantindo segurança e escalabilidade.

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────┐
│                   IAMKT PLATFORM                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   GERAÇÃO    │  │     BASE     │  │  APROVAÇÃO   │  │
│  │  CONTEÚDO    │  │    FEMME     │  │  & WORKFLOW  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   APIs IA    │    │   AWS S3     │    │  Playwright  │
│ OpenAI/Gemini│    │   Storage    │    │  (Scraping)  │
│     Grok     │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## 🐳 COMPONENTES DOCKER

### Containers Principais

| Container | Descrição | Porta Interna | Porta Externa |
|-----------|-----------|---------------|---------------|
| **iamkt_web** | Django + Gunicorn | 8000 | ❌ Não exposta |
| **iamkt_celery** | Celery Worker | - | ❌ Não exposta |
| **iamkt_beat** | Celery Beat (scheduler) | - | ❌ Não exposta |
| **iamkt_postgres** | PostgreSQL 15.x | 5432 | ❌ Não exposta |
| **iamkt_redis** | Redis 7.x | 6379 | ❌ Não exposta |

**⚠️ IMPORTANTE:** Nenhuma porta é exposta externamente. Acesso apenas via Traefik (proxy reverso).

---

## 🌐 CONFIGURAÇÃO DE REDE

### Redes Docker

```yaml
networks:
  iamkt_internal:
    driver: bridge
    ipam:
      config:
        - subnet: 172.22.0.0/24
    internal: true  # Isolamento total
  
  traefik_proxy:
    external: true  # Compartilhada com Traefik
```

### Detalhes

| Elemento | Configuração |
|----------|-------------|
| **Rede Interna** | `iamkt_internal` (172.22.0.0/24) |
| **Rede Externa** | `traefik_proxy` (acesso via proxy reverso) |
| **Portas Expostas** | NENHUMA (isolamento completo) |
| **URL de Acesso** | https://iamkt-femmeintegra.aisuites.com.br |
| **IP Servidor** | 72.61.223.244 |
| **Subnet** | 172.22.0.0/24 (conforme padrão FEMME) |

---

## 💾 VOLUMES PERSISTENTES

```yaml
volumes:
  iamkt_postgres_data:
    name: iamkt_postgres_data
  
  iamkt_redis_data:
    name: iamkt_redis_data
  
  iamkt_media:
    name: iamkt_media
  
  iamkt_static:
    name: iamkt_static
```

### Descrição dos Volumes

- **iamkt_postgres_data**: Dados do PostgreSQL (banco de dados)
- **iamkt_redis_data**: Dados do Redis (cache + broker Celery)
- **iamkt_media**: Uploads temporários (antes de mover para S3)
- **iamkt_static**: Arquivos estáticos coletados (CSS, JS, imagens)

---

## 🔗 INTEGRAÇÕES EXTERNAS

### APIs de Inteligência Artificial

| Serviço | Uso | API | Fase |
|---------|-----|-----|------|
| **OpenAI GPT-4** | Geração de textos complexos | OpenAI API | Fase 1 |
| **OpenAI DALL-E 3** | Geração de imagens | OpenAI API | Fase 1 |
| **Google Gemini** | Textos + imagens (alternativa) | Google AI API | Fase 1 |
| **Grok (X.AI)** | Análises rápidas, trends | X.AI API | Fase 1 |
| **AWS Bedrock** | Insights avançados de dados | AWS API | Fase 2 |
| **VEO3** | Geração de vídeos com Avatar | Custom | Fase 2 |

### Armazenamento e Dados

| Serviço | Uso | Configuração |
|---------|-----|--------------|
| **AWS S3** | Armazenamento de assets | Buckets organizados |
| **AWS Athena** | Consultas analíticas | Conexão direta (Fase 2) |

**Buckets S3:**
- `iamkt-fonts/`: Fontes customizadas (.otf, .ttf)
- `iamkt-logos/`: Logotipos da marca
- `iamkt-references/`: Imagens de referência visual
- `iamkt-generated/`: Conteúdos gerados (imagens, docs)
- `iamkt-assets/`: Biblioteca de assets geral

### Web Scraping

| Ferramenta | Uso |
|------------|-----|
| **Playwright** | Sites dinâmicos com JavaScript |
| **BeautifulSoup** | Parsing de HTML estático |
| **Requests** | Requisições HTTP simples |

---

## 🔄 FLUXO DE DADOS

### 1. Geração de Conteúdo

```
Usuário
   │
   ├─> Frontend (Django View)
   │      │
   │      ├─> Busca Base FEMME (PostgreSQL)
   │      │
   │      ├─> Cria Celery Task (assíncrono)
   │      │      │
   │      │      ├─> Cache Redis (verifica se existe)
   │      │      │
   │      │      ├─> API IA (OpenAI/Gemini/Grok)
   │      │      │
   │      │      ├─> Salva resultado (PostgreSQL)
   │      │      │
   │      │      └─> Upload S3 (se imagem/arquivo)
   │      │
   │      └─> Retorna preview para usuário
   │
   └─> Usuário edita/aprova/salva
```

### 2. Monitoramento de Trends

```
Celery Beat (6h diariamente)
   │
   ├─> Task: monitor_trends
   │      │
   │      ├─> Scraping (Playwright)
   │      │   - Google Trends
   │      │   - Think with Google
   │      │   - Reddit
   │      │   - Twitter/X
   │      │
   │      ├─> IA analisa relevância
   │      │   (prompt com Base FEMME)
   │      │
   │      ├─> Salva em PostgreSQL
   │      │
   │      └─> Se crítico: envia email
   │
   └─> Dashboard atualizado
```

### 3. Web Scraping de Concorrentes

```
Gestor clica "Analisar Concorrente"
   │
   ├─> Celery Task: scrape_competitor
   │      │
   │      ├─> Playwright navega no site
   │      │
   │      ├─> Extrai conteúdo (HTML)
   │      │
   │      ├─> IA resume informações
   │      │   - Posicionamento
   │      │   - Diferenciais
   │      │   - Tom de voz
   │      │
   │      ├─> Salva em PostgreSQL
   │      │
   │      └─> Notifica gestor
   │
   └─> Relatório disponível
```

---

## ⚡ PROCESSAMENTO ASSÍNCRONO

### Celery Worker (iamkt_celery)

**Tasks Principais:**
- `generate_content`: Geração de conteúdo com IA
- `generate_image`: Geração de imagens (DALL-E/Gemini)
- `scrape_competitor`: Análise de sites concorrentes
- `web_research`: Pesquisa e insights da web
- `send_approval_email`: Notificação de aprovações

### Celery Beat (iamkt_beat)

**Tasks Agendadas:**

| Task | Frequência | Horário |
|------|-----------|---------|
| `monitor_trends` | Diário | 6h da manhã |
| `scrape_competitors` | Semanal | Domingo 0h |
| `cleanup_cache` | Mensal | 1º dia do mês 2h |

---

## 🔐 SEGURANÇA

### Medidas Implementadas

- ✅ **HTTPS obrigatório** via Traefik
- ✅ **Isolamento de rede** (sem portas expostas)
- ✅ **CSRF protection** em todos os forms Django
- ✅ **SQL Injection**: proteção via ORM Django
- ✅ **XSS**: escape automático de HTML nos templates
- ✅ **Credenciais**: variáveis de ambiente (nunca hardcoded)
- ✅ **S3 buckets privados**: signed URLs temporárias
- ✅ **Rate limiting**: prevenção de abuso de APIs
- ✅ **Audit trail**: log de todas ações críticas
- ✅ **Validação de uploads**: tipo e tamanho de arquivo
- ✅ **Permissões granulares**: por área e usuário

---

## 📊 BANCO DE DADOS

### PostgreSQL 15.x

**Extensões Utilizadas:**
- `uuid-ossp`: Geração de UUIDs
- `pg_trgm`: Busca full-text (similarity)

**Configurações:**
- `max_connections`: 100
- `shared_buffers`: 256MB
- `work_mem`: 4MB
- `maintenance_work_mem`: 64MB

### Redis 7.x

**Uso:**
- **Cache**: Respostas de IA (TTL 7 dias)
- **Broker Celery**: Fila de tarefas
- **Result Backend**: Resultados de tasks

**Configurações:**
- `maxmemory`: 256MB
- `maxmemory-policy`: allkeys-lru
- `appendonly`: yes

---

## 🚀 DEPLOYMENT

### Comandos Makefile

```bash
# Setup inicial
make setup

# Iniciar em modo desenvolvimento (solo)
make solo

# Iniciar em modo produção
make up

# Ver logs
make logs

# Shell Django
make shell

# Executar migrations
make migrate

# Backup do banco
make backup
```

### Healthcheck

Endpoint: `https://iamkt-femmeintegra.aisuites.com.br/health/`

**Response OK (200):**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery": "running"
}
```

---

**Próximo documento:** [03_IAMKT_Apps_Django.md](03_IAMKT_Apps_Django.md)
