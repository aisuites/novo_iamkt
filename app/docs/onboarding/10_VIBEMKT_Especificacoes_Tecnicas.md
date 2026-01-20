# ⚙️ IAMKT - ESPECIFICAÇÕES TÉCNICAS

**Documento:** 10 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

Este documento consolida todas as especificações técnicas do IAMKT: stack, configurações, variáveis de ambiente, requisitos de performance e segurança.

---

## 🏗️ STACK TECNOLÓGICA COMPLETA

### Backend

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Python** | 3.11+ | Linguagem principal |
| **Django** | 4.2.8 | Framework web |
| **PostgreSQL** | 15.x | Banco de dados relacional |
| **Redis** | 7.x | Cache + broker Celery |
| **Celery** | 5.3.4 | Task queue assíncrona |
| **Gunicorn** | 21.2.0 | WSGI server |

### Frontend

| Tecnologia | Uso |
|------------|-----|
| **HTML5** | Estrutura |
| **CSS3** | Estilização (sem inline!) |
| **JavaScript (Vanilla)** | Interatividade |
| **Fetch API** | Chamadas AJAX |
| **Chart.js** | Gráficos |

### Infraestrutura

| Componente | Tecnologia |
|------------|------------|
| **Containerização** | Docker + Docker Compose |
| **Proxy Reverso** | Traefik v2.x |
| **SSL/TLS** | Let's Encrypt (via Traefik) |
| **Rede** | Docker Bridge (172.22.0.0/24) |

### Integrações Externas

| Serviço | Uso | Fase |
|---------|-----|------|
| **OpenAI API** | GPT-4 + DALL-E 3 | 1 |
| **Google Gemini** | Texto + Imagens | 1 |
| **Grok (X.AI)** | Análise rápida | 1 |
| **AWS S3** | Storage de assets | 1 |
| **AWS Athena** | Queries analíticas | 2 |
| **AWS Bedrock** | Insights avançados | 2 |
| **Playwright** | Web scraping | 1 |

---

## 📦 BIBLIOTECAS PYTHON

### Core Django
```
django==4.2.8
psycopg2-binary==2.9.9
gunicorn==21.2.0
whitenoise==6.6.0
django-environ==0.11.2
```

### Processamento Assíncrono
```
celery==5.3.4
redis==5.0.1
django-celery-beat==2.5.0
django-celery-results==2.5.1
```

### APIs de IA
```
openai==1.12.0
google-generativeai==0.3.2
anthropic==0.18.1
```

### AWS
```
boto3==1.34.44
django-storages==1.14.2
```

### Web Scraping
```
playwright==1.41.2
beautifulsoup4==4.12.3
requests==2.31.0
lxml==5.1.0
```

### Utilitários
```
Pillow==10.2.0
python-magic==0.4.27
reportlab==4.0.9
python-dotenv==1.0.1
```

### Dev/Testes
```
pytest==8.0.0
pytest-django==4.7.0
pytest-cov==4.1.0
black==24.1.1
flake8==7.0.0
```

---

## 🐳 CONFIGURAÇÃO DOCKER

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    container_name: iamkt_web
    build: .
    command: gunicorn sistema.wsgi:application --bind 0.0.0.0:8000 --workers 3
    volumes:
      - ./app:/app
      - iamkt_static:/app/staticfiles
      - iamkt_media:/app/media
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://iamkt_user:${DB_PASSWORD}@iamkt_postgres:5432/iamkt_db
      - REDIS_URL=redis://iamkt_redis:6379/0
      - CELERY_BROKER_URL=redis://iamkt_redis:6379/0
    depends_on:
      - postgres
      - redis
    networks:
      - iamkt_internal
      - traefik_proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.iamkt.rule=Host(`iamkt-femmeintegra.aisuites.com.br`)"
      - "traefik.http.routers.iamkt.entrypoints=websecure"
      - "traefik.http.routers.iamkt.tls=true"
      - "traefik.http.routers.iamkt.tls.certresolver=letsencrypt"
      - "traefik.http.services.iamkt.loadbalancer.server.port=8000"
    restart: unless-stopped

  celery:
    container_name: iamkt_celery
    build: .
    command: celery -A sistema worker -l info
    volumes:
      - ./app:/app
    environment:
      - DATABASE_URL=postgresql://iamkt_user:${DB_PASSWORD}@iamkt_postgres:5432/iamkt_db
      - REDIS_URL=redis://iamkt_redis:6379/0
      - CELERY_BROKER_URL=redis://iamkt_redis:6379/0
    depends_on:
      - postgres
      - redis
    networks:
      - iamkt_internal
    restart: unless-stopped

  beat:
    container_name: iamkt_beat
    build: .
    command: celery -A sistema beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./app:/app
    environment:
      - DATABASE_URL=postgresql://iamkt_user:${DB_PASSWORD}@iamkt_postgres:5432/iamkt_db
      - REDIS_URL=redis://iamkt_redis:6379/0
      - CELERY_BROKER_URL=redis://iamkt_redis:6379/0
    depends_on:
      - postgres
      - redis
    networks:
      - iamkt_internal
    restart: unless-stopped

  postgres:
    container_name: iamkt_postgres
    image: postgres:15-alpine
    volumes:
      - iamkt_postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=iamkt_db
      - POSTGRES_USER=iamkt_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    networks:
      - iamkt_internal
    restart: unless-stopped

  redis:
    container_name: iamkt_redis
    image: redis:7-alpine
    volumes:
      - iamkt_redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    networks:
      - iamkt_internal
    restart: unless-stopped

networks:
  iamkt_internal:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.22.0.0/24

  traefik_proxy:
    external: true

volumes:
  iamkt_postgres_data:
    name: iamkt_postgres_data
  iamkt_redis_data:
    name: iamkt_redis_data
  iamkt_static:
    name: iamkt_static
  iamkt_media:
    name: iamkt_media
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    python3-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Instalar Playwright browsers
RUN playwright install chromium

# Copiar código da aplicação
COPY ./app /app

# Criar diretórios necessários
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Coletar static files (será rodado no entrypoint)
# RUN python manage.py collectstatic --noinput

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Usuário não-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expor porta (apenas documentação, não expõe de fato)
EXPOSE 8000

# Comando será sobrescrito no docker-compose
CMD ["gunicorn", "sistema.wsgi:application", "--bind", "0.0.0.0:8000"]
```

---

## 🔐 VARIÁVEIS DE AMBIENTE

### Arquivo .env (Desenvolvimento)

```bash
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,iamkt-femmeintegra.aisuites.com.br
DJANGO_SETTINGS_MODULE=sistema.settings.development

# Database
DB_PASSWORD=strong_password_here
DATABASE_URL=postgresql://iamkt_user:${DB_PASSWORD}@iamkt_postgres:5432/iamkt_db

# Redis
REDIS_URL=redis://iamkt_redis:6379/0
CELERY_BROKER_URL=redis://iamkt_redis:6379/0
CELERY_RESULT_BACKEND=redis://iamkt_redis:6379/0

# AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=iamkt-assets
AWS_S3_REGION_NAME=us-east-1

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_ORG_ID=org-...

# Google AI
GOOGLE_AI_API_KEY=AIza...

# Grok (X.AI)
GROK_API_KEY=xai-...

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@femme.com.br
EMAIL_HOST_PASSWORD=app_password_here
DEFAULT_FROM_EMAIL=IAMKT <noreply@femme.com.br>

# Athena (Fase 2)
ATHENA_DATABASE=femme_analytics
ATHENA_WORKGROUP=primary
ATHENA_S3_OUTPUT=s3://iamkt-athena-results/

# Sentry (Opcional)
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=development
```

### Arquivo .env.production (Produção)

```bash
# Django
DEBUG=False
SECRET_KEY=generate-strong-key-with-python-secrets
ALLOWED_HOSTS=iamkt-femmeintegra.aisuites.com.br
DJANGO_SETTINGS_MODULE=sistema.settings.production

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

# (Resto igual ao desenvolvimento, com valores de produção)
```

---

## ⚡ CONFIGURAÇÕES DJANGO

### settings/base.py

```python
import os
from pathlib import Path
import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'django_celery_beat',
    'django_celery_results',
    'storages',
    
    # Local apps
    'apps.core',
    'apps.knowledge',
    'apps.content',
    'apps.campaigns',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sistema.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes

# Cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 28800  # 8 hours

# AWS S3
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'private'
AWS_S3_ENCRYPTION = True
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour

# APIs de IA
OPENAI_API_KEY = env('OPENAI_API_KEY')
OPENAI_ORG_ID = env('OPENAI_ORG_ID', default='')
GOOGLE_AI_API_KEY = env('GOOGLE_AI_API_KEY')
GROK_API_KEY = env('GROK_API_KEY')

# Timeouts
OPENAI_TIMEOUT = 60
GEMINI_TIMEOUT = 60
GROK_TIMEOUT = 30

# Cache IA (TTL em segundos)
IA_CACHE_TTL = 604800  # 7 dias

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'iamkt.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

---

## 📊 REQUISITOS DE PERFORMANCE

### Targets de Performance

| Métrica | Target | Medição |
|---------|--------|---------|
| **Tempo de carregamento** | < 2s | Páginas principais |
| **Tempo resposta API** | < 500ms | Endpoints Django |
| **Geração de conteúdo** | < 30s | Tasks Celery (async) |
| **Uptime** | > 99.5% | Monitoramento 24/7 |
| **Concurrent users** | 50+ | Usuários simultâneos |
| **Database queries** | < 50ms | Queries otimizadas |
| **Cache hit rate** | > 70% | Redis |

### Otimizações

#### Database
```python
# Indexes importantes
class Meta:
    indexes = [
        models.Index(fields=['usuario', '-created_at']),
        models.Index(fields=['area', 'status']),
        models.Index(fields=['-relevancia_score', '-created_at']),
    ]
```

#### Queries
```python
# Use select_related e prefetch_related
conteudos = GeneratedContent.objects.select_related(
    'usuario', 'area', 'template'
).prefetch_related(
    'projetos', 'assets'
)

# Paginação
from django.core.paginator import Paginator
paginator = Paginator(queryset, 25)
```

#### Cache
```python
from django.core.cache import cache

# Cache de view
def dashboard(request):
    cache_key = f'dashboard_{request.user.id}'
    data = cache.get(cache_key)
    
    if not data:
        data = generate_dashboard_data(request.user)
        cache.set(cache_key, data, 300)  # 5 minutos
    
    return render(request, 'dashboard.html', data)
```

---

## 🔒 SEGURANÇA

### Checklist de Segurança

#### Django Settings
- [x] `DEBUG = False` em produção
- [x] `SECRET_KEY` forte e único
- [x] `ALLOWED_HOSTS` configurado corretamente
- [x] `SECURE_SSL_REDIRECT = True`
- [x] `SESSION_COOKIE_SECURE = True`
- [x] `CSRF_COOKIE_SECURE = True`
- [x] `SECURE_HSTS_SECONDS = 31536000`
- [x] `X_FRAME_OPTIONS = 'DENY'`

#### Autenticação
- [x] Passwords hasheados (Argon2)
- [x] Rate limiting no login
- [x] Two-factor auth (Fase 2)
- [x] Session timeout (8 horas)

#### Permissões
- [x] Decorators em todas views sensíveis
- [x] Validação de área em cada ação
- [x] Audit log de ações críticas

#### Dados
- [x] SQL Injection: ORM Django
- [x] XSS: Templates auto-escaped
- [x] CSRF: Token obrigatório
- [x] Uploads: Validação de tipo e tamanho
- [x] S3: Buckets privados
- [x] Credenciais: Variáveis de ambiente

#### Network
- [x] HTTPS obrigatório
- [x] Rede Docker isolada
- [x] Nenhuma porta exposta
- [x] Traefik como único ponto de entrada

---

## 🧪 TESTES

### Configuração pytest

```python
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = sistema.settings.test
python_files = tests.py test_*.py *_tests.py
addopts = --cov=apps --cov-report=html --cov-report=term-missing
```

### Exemplos de Testes

```python
# tests/test_models.py
import pytest
from apps.core.models import User, Area

@pytest.mark.django_db
def test_user_creation():
    user = User.objects.create_user(
        username='test',
        email='test@femme.com.br',
        password='testpass123',
        perfil='operacional'
    )
    assert user.email == 'test@femme.com.br'
    assert user.perfil == 'operacional'

@pytest.mark.django_db
def test_area_permissions():
    area = Area.objects.create(
        nome='Marketing',
        ferramentas_permitidas=['pautas', 'posts']
    )
    assert 'pautas' in area.ferramentas_permitidas
    assert 'blog' not in area.ferramentas_permitidas
```

---

## 📈 MONITORAMENTO

### Healthcheck Endpoint

```python
# apps/core/views.py
from django.http import JsonResponse
from django.db import connection

def healthcheck(request):
    # Testa database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except:
        db_status = "error"
    
    # Testa Redis
    from django.core.cache import cache
    try:
        cache.set('healthcheck', 'ok', 10)
        cache.get('healthcheck')
        redis_status = "connected"
    except:
        redis_status = "error"
    
    # Testa Celery
    from celery import current_app
    try:
        celery_status = "running" if current_app.control.inspect().active() else "stopped"
    except:
        celery_status = "error"
    
    status = 200 if all([
        db_status == "connected",
        redis_status == "connected",
        celery_status == "running"
    ]) else 503
    
    return JsonResponse({
        "status": "healthy" if status == 200 else "unhealthy",
        "database": db_status,
        "redis": redis_status,
        "celery": celery_status
    }, status=status)
```

### Logs Importantes

- **Django logs**: `/app/logs/iamkt.log`
- **Celery logs**: stdout/stderr (via Docker)
- **Nginx/Traefik logs**: `/var/log/traefik/`
- **PostgreSQL logs**: `/var/log/postgresql/`

---

## 🚀 DEPLOY E COMANDOS

### Makefile

```makefile
.PHONY: setup up down logs shell migrate test

setup:
	docker-compose build
	docker-compose run --rm web python manage.py migrate
	docker-compose run --rm web python manage.py collectstatic --noinput
	docker-compose run --rm web python manage.py createsuperuser

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec web python manage.py shell

migrate:
	docker-compose exec web python manage.py makemigrations
	docker-compose exec web python manage.py migrate

test:
	docker-compose exec web pytest

backup:
	docker-compose exec postgres pg_dump -U iamkt_user iamkt_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Comandos Úteis

```bash
# Iniciar em dev
make up

# Ver logs
make logs

# Shell Django
make shell

# Migrations
make migrate

# Testes
make test

# Backup
make backup

# Parar tudo
make down
```

---

## 🎉 CONCLUSÃO

Esta especificação técnica cobre todos os aspectos do IAMKT:
- ✅ Stack completa
- ✅ Configuração Docker
- ✅ Variáveis de ambiente
- ✅ Performance targets
- ✅ Segurança
- ✅ Testes
- ✅ Monitoramento
- ✅ Deploy

**Sistema pronto para desenvolvimento e produção!**

---

**Fim da Documentação IAMKT (10/10)**  
**Versão:** 1.0  
**Data:** Janeiro 2026
