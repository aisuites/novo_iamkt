# 📁 ESTRUTURA PADRÃO DE APLICAÇÕES

**Versão:** 1.0  
**Data:** 08/01/2026  
**Baseado em:** Estrutura real das aplicações NTO, BOT, IAMKT e IaMKT  
**Objetivo:** Documentar fielmente a estrutura de diretórios e arquivos aplicada em todas as aplicações

---

## 🎯 VISÃO GERAL

Este documento reflete **exatamente** a estrutura de diretórios e arquivos aplicada nas aplicações Django do servidor. Serve como referência tanto para:
- ✅ **Criar novas aplicações** seguindo o padrão estabelecido
- ✅ **Entender a organização** das aplicações existentes
- ✅ **Manter consistência** entre todas as aplicações

---

## 📊 APLICAÇÕES ANALISADAS

| Aplicação | Localização | Django Apps | Status |
|-----------|-------------|-------------|--------|
| **NTO** | `/opt/nto/` | 3 (core, requisicoes, tarefas) | ✅ Referência completa |
| **BOT** | `/opt/bot/` | 1 (core) | ✅ Padrão básico |
| **IAMKT** | `/opt/iamkt/` | 1 (core) | ✅ Padrão básico |
| **IaMKT** | `/opt/iamkt/` | 1 (core) | ⚠️ Falta `apps/__init__.py` |

---

## 🏗️ ESTRUTURA COMPLETA - PADRÃO BÁSICO

### Nível Raiz do Projeto (`/opt/{app_name}/`)

```
/opt/{app_name}/
├── .env.development          # Variáveis de ambiente (desenvolvimento)
├── .env.example              # Template de variáveis (opcional mas recomendado)
├── Makefile                  # Comandos operacionais
├── README.md                 # Documentação da aplicação
├── docker-compose.yml        # Configuração Docker principal
├── docker-compose.solo.yml   # Override para modo desenvolvimento
├── app/                      # Código da aplicação Django
├── scripts/                  # Scripts auxiliares
└── docs/                     # Documentação (opcional)
```

**Arquivos Obrigatórios:**
- ✅ `.env.development`
- ✅ `Makefile`
- ✅ `README.md`
- ✅ `docker-compose.yml`
- ✅ `docker-compose.solo.yml`

**Arquivos Opcionais:**
- 📝 `.env.example` (recomendado)
- 📝 `docs/` (recomendado para apps complexas)

---

## 📦 ESTRUTURA DO DIRETÓRIO `app/`

### Visão Geral

```
app/
├── Dockerfile                # Build da imagem Docker
├── entrypoint.sh            # Script de inicialização
├── manage.py                # CLI do Django
├── requirements.txt         # Dependências Python
├── sistema/                 # Projeto Django (SEMPRE "sistema")
│   ├── __init__.py
│   ├── celery.py
│   ├── urls.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       └── development.py
├── apps/                    # Django apps da aplicação
│   ├── __init__.py         # ⚠️ OBRIGATÓRIO
│   └── core/               # App principal (sempre presente)
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── models.py
│       ├── views.py
│       ├── migrations/
│       │   └── __init__.py
│       └── templates/
│           └── core/
│               └── home.html
├── static/                  # Arquivos estáticos (desenvolvimento)
│   ├── css/
│   ├── img/
│   └── js/
├── staticfiles/             # Arquivos estáticos coletados (produção)
├── media/                   # Uploads de usuários
└── templates/               # Templates globais (opcional)
```

---

## 📄 DETALHAMENTO DE ARQUIVOS

### 1. Arquivos Raiz do `app/`

#### `Dockerfile`
```dockerfile
# Multi-stage build
FROM python:3.11-slim as python-base
# ... (ver documentação completa)
```
**Características:**
- Multi-stage build (builder + runtime)
- Usuário não-root (django:django)
- Healthcheck integrado
- Comando padrão: `gunicorn sistema.wsgi:application --bind 0.0.0.0:8000 --workers 3`

#### `entrypoint.sh`
```bash
#!/bin/bash
# Wait for PostgreSQL
# Wait for Redis
# Configure Django settings
# Execute command
```
**Características:**
- Aguarda dependências (PostgreSQL, Redis)
- Configura `DJANGO_SETTINGS_MODULE`
- Suporta múltiplos comandos (migrate, shell, celery)

#### `manage.py`
```python
#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')
    # ...
```
**Características:**
- Settings padrão: `sistema.settings.development`
- Permissão de execução: `chmod +x manage.py`

#### `requirements.txt`
```txt
Django==4.2.8
psycopg2-binary==2.9.9
redis==5.0.1
celery==5.3.4
gunicorn==21.2.0
# ... (ver arquivo completo em /opt/nto/app/requirements.txt)
```

---

### 2. Diretório `sistema/` (Projeto Django)

**⚠️ PADRÃO OBRIGATÓRIO:** O nome do projeto Django é **SEMPRE** `sistema/` em todas as aplicações.

**Motivo:** Cada app tem seu próprio diretório isolado (`/opt/nto/`, `/opt/bot/`), então o projeto Django interno pode ter o mesmo nome. Isso simplifica documentação e reduz erros.

#### Estrutura Completa

```
sistema/
├── __init__.py              # Import do Celery
├── celery.py               # Configuração Celery
├── urls.py                 # URLs principais
├── wsgi.py                 # WSGI application
└── settings/               # Settings modularizados
    ├── __init__.py
    ├── base.py            # Configurações base
    └── development.py     # Configurações de desenvolvimento
```

#### `sistema/__init__.py`
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```
**⚠️ CRÍTICO:** Este import é necessário para o Celery funcionar.

#### `sistema/celery.py`
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')

app = Celery('sistema')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```
**Características:**
- Nome Celery: `'sistema'` (padrão)
- Settings: `sistema.settings.development`
- Autodiscover tasks de todas as apps

#### `sistema/urls.py`
```python
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import home, health_check

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```
**Características:**
- Home page na raiz
- Admin Django em `/admin/`
- Health check em `/health/` (obrigatório para Docker)

#### `sistema/wsgi.py`
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')

application = get_wsgi_application()
```

#### `sistema/settings/base.py`
Configurações principais:
- `INSTALLED_APPS` (Django apps + apps customizadas)
- `MIDDLEWARE`
- `DATABASES` (via `dj_database_url`)
- `CACHES` (Redis)
- `CELERY_BROKER_URL` e `CELERY_RESULT_BACKEND`
- `STATIC_URL`, `STATIC_ROOT`, `MEDIA_URL`, `MEDIA_ROOT`

#### `sistema/settings/development.py`
```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'https://app-domain.com.br',
    'http://localhost:8000',
]
```

---

### 3. Diretório `apps/` (Django Apps)

#### Estrutura Mínima (1 app - padrão BOT/IAMKT/IaMKT)

```
apps/
├── __init__.py              # ⚠️ OBRIGATÓRIO
└── core/                    # App principal
    ├── __init__.py
    ├── admin.py            # Configuração Django Admin
    ├── apps.py             # Configuração da app
    ├── models.py           # Models do banco
    ├── views.py            # Views/Controllers
    ├── migrations/         # Migrações do banco
    │   └── __init__.py
    └── templates/          # Templates da app
        └── core/
            └── home.html
```

**⚠️ IMPORTANTE:** O arquivo `apps/__init__.py` é **OBRIGATÓRIO** em todas as aplicações.

#### Estrutura Expandida (múltiplas apps - padrão NTO)

```
apps/
├── __init__.py              # ⚠️ OBRIGATÓRIO
├── core/                    # App principal
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   └── migrations/
│       └── __init__.py
├── requisicoes/             # App de requisições
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── migrations/
│       └── __init__.py
└── tarefas/                 # App de tarefas
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    └── migrations/
        └── __init__.py
```

#### Arquivos Obrigatórios por App Django

Cada app Django **DEVE** ter:
- ✅ `__init__.py`
- ✅ `apps.py`
- ✅ `models.py`
- ✅ `views.py`
- ✅ `admin.py`
- ✅ `migrations/__init__.py`

#### `apps/core/apps.py`
```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'
```

#### `apps/core/admin.py`
```python
from django.contrib import admin
# Registrar models aqui
```

#### `apps/core/models.py`
```python
from django.db import models

# Models serão implementados conforme necessidade
```

#### `apps/core/views.py`
```python
from django.shortcuts import render
from django.http import JsonResponse

def home(request):
    """View da página inicial"""
    context = {
        'app_name': 'Nome da App',
        'version': '1.0.0',
    }
    return render(request, 'core/home.html', context)

def health_check(request):
    """Health check endpoint para Docker"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'app_name'
    })
```

#### `apps/core/templates/core/home.html`
Template HTML básico com:
- Design responsivo
- Status da aplicação
- Versão

---

### 4. Diretório `static/`

```
static/
├── css/                     # Arquivos CSS
├── img/                     # Imagens
└── js/                      # JavaScript
```

**Características:**
- Usado em desenvolvimento
- Arquivos são coletados para `staticfiles/` em produção
- Cada subdiretório pode estar vazio inicialmente

---

### 5. Outros Diretórios

#### `staticfiles/`
- Criado automaticamente
- Arquivos estáticos coletados via `collectstatic`
- Servido em produção

#### `media/`
- Uploads de usuários
- Configurado via `MEDIA_ROOT` e `MEDIA_URL`

#### `templates/`
- Templates globais (opcional)
- Templates específicos de apps ficam em `apps/{app}/templates/`

---

## 📋 DIRETÓRIO `scripts/`

```
scripts/
└── init.sql                 # Script de inicialização do PostgreSQL
```

**`init.sql`** (exemplo):
```sql
-- Script executado na primeira inicialização do PostgreSQL
-- Pode conter criação de extensões, funções, etc.
```

---

## 📚 DIRETÓRIO `docs/` (Opcional)

Presente apenas em aplicações complexas (exemplo: NTO).

```
docs/
├── CONTEXTO_PROJETO.md
├── models/
│   ├── README.md
│   ├── core-models.md
│   ├── requisicoes-models.md
│   └── tarefas-models.md
└── ...
```

---

## 🐳 ARQUIVOS DOCKER

### `docker-compose.yml`

Estrutura padrão:

```yaml
version: '3.8'

services:
  {app}_web:
    build:
      context: ./app
      dockerfile: Dockerfile
    container_name: {app}_web
    restart: unless-stopped
    depends_on:
      - {app}_postgres
      - {app}_redis
    volumes:
      - ./app:/app
      - {app}_media:/app/media
      - {app}_static:/app/staticfiles
    networks:
      - {app}_internal
      - traefik_proxy
    env_file:
      - .env.development
    deploy:
      resources:
        limits:
          memory: 1.5G
        reservations:
          memory: 512M
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_proxy"
      - "traefik.http.routers.{app}-https.rule=Host(`{app}.domain.com`)"
      - "traefik.http.routers.{app}-https.entrypoints=websecure"
      - "traefik.http.routers.{app}-https.tls=true"
      - "traefik.http.routers.{app}-https.tls.certresolver=cloudflare"
      - "traefik.http.routers.{app}-https.priority=200"
      - "traefik.http.services.{app}.loadbalancer.server.port=8000"

  {app}_celery:
    build:
      context: ./app
      dockerfile: Dockerfile
    container_name: {app}_celery
    restart: unless-stopped
    command: celery -A sistema worker -l info
    depends_on:
      - {app}_postgres
      - {app}_redis
    volumes:
      - ./app:/app
      - {app}_media:/app/media
    networks:
      - {app}_internal
    env_file:
      - .env.development
    healthcheck:
      test: ["CMD-SHELL", "celery -A sistema inspect ping -d celery@$$HOSTNAME || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M

  {app}_postgres:
    image: postgres:15-alpine
    container_name: {app}_postgres
    restart: unless-stopped
    volumes:
      - {app}_postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - {app}_internal
    environment:
      POSTGRES_DB: {app}_db
      POSTGRES_USER: {app}_user
      POSTGRES_PASSWORD: secure_password
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M

  {app}_redis:
    image: redis:7-alpine
    container_name: {app}_redis
    restart: unless-stopped
    volumes:
      - {app}_redis_data:/data
    networks:
      - {app}_internal
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M

volumes:
  {app}_postgres_data:
    name: {app}_postgres_data
  {app}_redis_data:
    name: {app}_redis_data
  {app}_media:
    name: {app}_media
  {app}_static:
    name: {app}_static

networks:
  {app}_internal:
    name: {app}_internal
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.XX.0.0/24  # Incrementar para cada app
  
  traefik_proxy:
    name: traefik_proxy
    external: true
```

### `docker-compose.solo.yml`

Override para desenvolvimento com recursos expandidos:

```yaml
version: '3.8'

services:
  {app}_web:
    deploy:
      resources:
        limits:
          memory: 4G      # Expandido de 1.5G
        reservations:
          memory: 1G      # Expandido de 512M
    environment:
      - DEBUG=True
      - DJANGO_LOG_LEVEL=DEBUG
    ports:
      - "8000:8000"      # Porta exposta para acesso direto
    volumes:
      - ./app:/app:cached
      - {app}_dev_cache:/root/.cache

  {app}_celery:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    volumes:
      - ./app:/app:cached
      - {app}_dev_cache:/root/.cache

  {app}_postgres:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    command: >
      postgres
      -c shared_buffers=128MB
      -c work_mem=4MB
      -c log_statement=all
      -c log_duration=on

  {app}_redis:
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru

volumes:
  {app}_dev_cache:
    name: {app}_dev_cache
```

---

## 📝 ARQUIVO `.env.development`

```bash
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=app.domain.com,localhost
DJANGO_SETTINGS_MODULE=sistema.settings.development

# Database
DATABASE_URL=postgresql://{app}_user:password@{app}_postgres:5432/{app}_db

# Redis
REDIS_URL=redis://{app}_redis:6379/0

# Celery
CELERY_BROKER_URL=redis://{app}_redis:6379/0
CELERY_RESULT_BACKEND=redis://{app}_redis:6379/0

# Security
CSRF_TRUSTED_ORIGINS=https://app.domain.com,http://localhost:8000

# Environment
ENVIRONMENT=development
```

---

## 🛠️ ARQUIVO `Makefile`

```makefile
.PHONY: help setup up solo down restart logs shell dbshell validate migrate backup

ENV_FILE ?= development

help:
	@echo "🏗️  {APP_NAME} - Comandos Operacionais"
	@echo "  make setup    - Configuração inicial"
	@echo "  make up       - Iniciar serviços"
	@echo "  make solo     - Iniciar em modo desenvolvimento"
	@echo "  make down     - Parar serviços"
	@echo "  make logs     - Ver logs"
	@echo "  make shell    - Shell Django"
	@echo "  make dbshell  - Shell PostgreSQL"
	@echo "  make validate - Verificar isolamento"
	@echo "  make migrate  - Executar migrations"
	@echo "  make backup   - Backup PostgreSQL"

setup:
	@docker network ls | grep -q traefik_proxy || docker network create traefik_proxy

up: setup
	@docker compose --env-file .env.$(ENV_FILE) up -d

solo: setup
	@docker compose -f docker-compose.yml -f docker-compose.solo.yml --env-file .env.$(ENV_FILE) up -d

down:
	@docker compose down

restart:
	@make down
	@sleep 2
	@make up

logs:
	@docker compose logs -f

shell:
	@docker compose exec {app}_web bash

dbshell:
	@docker compose exec {app}_postgres psql -U {app}_user -d {app}_db

validate:
	@docker ps --format "{{.Names}}\t{{.Ports}}" | grep {app} | grep -E "(5432|6379)" || echo "✅ Nenhuma porta exposta"

migrate:
	@docker compose exec {app}_web python manage.py migrate

backup:
	@mkdir -p backups
	@docker compose exec -T {app}_postgres pg_dump -U {app}_user {app}_db > backups/{app}_backup_$(shell date +%Y%m%d_%H%M%S).sql
```

---

## 🔢 CONVENÇÕES DE NOMENCLATURA

### Nomes de Containers

**Padrão:** `{app}_{service}`

Exemplos:
- `nto_web`
- `nto_celery`
- `nto_postgres`
- `nto_redis`
- `bot_web`
- `iamkt_web`

### Nomes de Volumes

**Padrão:** `{app}_{tipo}`

Exemplos:
- `nto_postgres_data`
- `nto_redis_data`
- `nto_media`
- `nto_static`
- `nto_dev_cache` (modo SOLO)

### Nomes de Redes

**Padrão:**
- Interna: `{app}_internal`
- Compartilhada: `traefik_proxy` (externa)

Exemplos:
- `nto_internal`
- `bot_internal`
- `traefik_proxy`

### Subnets

**Padrão:** `172.XX.0.0/24` (incrementar XX para cada app)

| Aplicação | Subnet |
|-----------|--------|
| NTO | 172.20.0.0/24 |
| BOT | 172.21.0.0/24 |
| IAMKT | 172.22.0.0/24 |
| IaMKT | 172.23.0.0/24 |
| Próxima | 172.24.0.0/24 |

### Banco de Dados

**Padrão:**
- Database: `{app}_db`
- User: `{app}_user`
- Password: `dev_{app}_password_YYYY` (ano atual)

Exemplos:
- `nto_db` / `nto_user` / `dev_nto_password_2025`
- `bot_db` / `bot_user` / `dev_bot_password_2025`

---

## ✅ CHECKLIST DE ARQUIVOS OBRIGATÓRIOS

### Nível Raiz (`/opt/{app}/`)
- [ ] `.env.development`
- [ ] `Makefile`
- [ ] `README.md`
- [ ] `docker-compose.yml`
- [ ] `docker-compose.solo.yml`
- [ ] `app/` (diretório)
- [ ] `scripts/` (diretório)

### Diretório `app/`
- [ ] `Dockerfile`
- [ ] `entrypoint.sh`
- [ ] `manage.py`
- [ ] `requirements.txt`
- [ ] `sistema/` (diretório)
- [ ] `apps/` (diretório)
- [ ] `static/` (diretório)
- [ ] `staticfiles/` (diretório)
- [ ] `media/` (diretório)
- [ ] `templates/` (diretório - opcional)

### Diretório `sistema/`
- [ ] `__init__.py`
- [ ] `celery.py`
- [ ] `urls.py`
- [ ] `wsgi.py`
- [ ] `settings/__init__.py`
- [ ] `settings/base.py`
- [ ] `settings/development.py`

### Diretório `apps/`
- [ ] `__init__.py` ⚠️ **OBRIGATÓRIO**
- [ ] `core/` (diretório)

### Diretório `apps/core/`
- [ ] `__init__.py`
- [ ] `admin.py`
- [ ] `apps.py`
- [ ] `models.py`
- [ ] `views.py`
- [ ] `migrations/__init__.py`
- [ ] `templates/core/home.html`

### Diretório `static/`
- [ ] `css/` (diretório)
- [ ] `img/` (diretório)
- [ ] `js/` (diretório)

### Diretório `scripts/`
- [ ] `init.sql`

---

## 🔄 VARIAÇÕES ENTRE APLICAÇÕES

### Aplicação Básica (BOT, IAMKT, IaMKT)

**Características:**
- 1 Django app (`core`)
- Estrutura mínima
- Sem documentação adicional

### Aplicação Complexa (NTO)

**Características:**
- 3 Django apps (`core`, `requisicoes`, `tarefas`)
- Diretório `docs/` com documentação
- Arquivo `initial_data.json` para fixtures
- Templates organizados por app

**Estrutura adicional:**
```
app/
├── apps/
│   ├── __init__.py
│   ├── core/
│   ├── requisicoes/
│   └── tarefas/
├── initial_data.json
└── templates/
    └── core/
        └── home.html
```

---

## ⚠️ INCONSISTÊNCIAS IDENTIFICADAS

### IaMKT - Falta `apps/__init__.py`

**Problema:** IaMKT não possui o arquivo `apps/__init__.py`

**Impacto:** Pode causar problemas de import em Python

**Solução:** Criar o arquivo:
```bash
touch /opt/iamkt/app/apps/__init__.py
```

**Status:** ⚠️ Pendente de correção

---

## 📚 REFERÊNCIAS

### Documentação Relacionada
- **Checklist de Nova Aplicação:** `/opt/docs/CHECKLIST_NOVA_APLICACAO.md`
- **Documentação do Servidor:** `/root/CascadeProjects/documentacao-servidor-padrao.md`

### Aplicações de Referência
- **NTO:** `/opt/nto/` (referência completa com múltiplas apps)
- **BOT:** `/opt/bot/` (referência padrão básico)
- **IAMKT:** `/opt/iamkt/` (referência padrão básico)
- **IaMKT:** `/opt/iamkt/` (referência padrão básico)

---

## 📊 RESUMO EXECUTIVO

### Estrutura Padrão

**Nível 1 - Raiz do Projeto:**
- 5 arquivos obrigatórios
- 2 diretórios obrigatórios (app, scripts)
- 1 diretório opcional (docs)

**Nível 2 - Diretório app/:**
- 4 arquivos obrigatórios
- 6 diretórios obrigatórios

**Nível 3 - Projeto Django (sistema/):**
- 4 arquivos obrigatórios
- 1 diretório obrigatório (settings)

**Nível 4 - Django Apps (apps/):**
- 1 arquivo obrigatório (`__init__.py`)
- Mínimo 1 app (core) com 6 arquivos obrigatórios

### Nomenclatura

- **Projeto Django:** Sempre `sistema`
- **Containers:** `{app}_{service}`
- **Volumes:** `{app}_{tipo}`
- **Redes:** `{app}_internal` + `traefik_proxy`
- **Subnets:** `172.XX.0.0/24` (incrementar)

### Comandos Principais

```bash
# Criar nova app
make setup
make solo

# Desenvolvimento
make logs
make shell
make dbshell

# Manutenção
make migrate
make backup
make validate
```

---

**Documento criado em:** 08/01/2026  
**Baseado em:** Estrutura real das aplicações NTO, BOT, IAMKT e IaMKT  
**Status:** ✅ Fiel à estrutura existente  
**Próxima ação:** Corrigir `apps/__init__.py` em IaMKT
