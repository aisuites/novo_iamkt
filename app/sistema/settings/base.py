import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# CORE SETTINGS
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv())

# ENVIRONMENT
ENVIRONMENT = config('ENVIRONMENT', default='production')

# APPLICATION DEFINITION
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'compressor',
]

LOCAL_APPS = [
    'apps.core',
    'apps.knowledge',
    'apps.content',
    'apps.campaigns',
    'apps.pautas',
    'apps.posts',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.TenantMiddleware',  # Tenant detection
    'apps.core.middleware.TenantIsolationMiddleware',  # Tenant isolation
    'apps.core.middleware_onboarding.OnboardingRequiredMiddleware',  # Onboarding restriction
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
                'apps.core.context_processors.tenant_context',  # Tenant context
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema.wsgi.application'

# DATABASE
DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}

# INTERNATIONALIZATION
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True

# STATIC FILES
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# STATICFILES FINDERS (para django-compressor)
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

# DJANGO COMPRESSOR
COMPRESS_ENABLED = not DEBUG  # Apenas em produção
COMPRESS_OFFLINE = True  # Comprimir durante collectstatic
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.rCSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.rJSMinFilter',
]

# STATICFILES_STORAGE - Usar ManifestStaticFilesStorage para cache busting
# Isso resolve o problema do collectstatic não copiar arquivos corretamente
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# MEDIA FILES
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# EMAIL CONFIGURATION
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@iamkt.com.br')

# EMAIL NOTIFICATION GROUPS
NOTIFICATION_EMAILS_GESTAO = config('NOTIFICATION_EMAILS_GESTAO', default='')
NOTIFICATION_EMAILS_OPERACAO = config('NOTIFICATION_EMAILS_OPERACAO', default='')
NOTIFICATION_EMAILS_POSTS = config('NOTIFICATION_EMAILS_POSTS', default='')
NEWUSER_NOTIFICATION_EMAILS = config('NEWUSER_NOTIFICATION_EMAILS', default='')
NOTIFICATION_EMAIL_SUPORTE = config('NOTIFICATION_EMAIL_SUPORTE', default='suporte@aisuites.com.br')

# SITE URL (for emails)
SITE_URL = config('SITE_URL', default='https://iamkt.aisuites.com.br')

# DEFAULT PRIMARY KEY
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REDIS/CACHE
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/1')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# CELERY
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# CUSTOM USER MODEL
AUTH_USER_MODEL = 'core.User'

# AUTHENTICATION BACKENDS
# Backend customizado que permite login com email
AUTHENTICATION_BACKENDS = [
    'apps.core.backends.EmailBackend',  # Login com email (prioridade)
    'django.contrib.auth.backends.ModelBackend',  # Fallback para username
]

# LOGIN URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# AI INTEGRATIONS
# OpenAI
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
OPENAI_MODEL_TEXT = config('OPENAI_MODEL_TEXT', default='gpt-4')
OPENAI_MODEL_IMAGE = config('OPENAI_MODEL_IMAGE', default='dall-e-3')

# Google Gemini
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL_TEXT = config('GEMINI_MODEL_TEXT', default='gemini-pro')
GEMINI_MODEL_IMAGE = config('GEMINI_MODEL_IMAGE', default='gemini-pro-vision')

# Perplexity
PERPLEXITY_API_KEY = config('PERPLEXITY_API_KEY', default='')
PERPLEXITY_MODEL = config('PERPLEXITY_MODEL', default='pplx-7b-online')

# AWS S3
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='iamkt-assets')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_QUERYSTRING_EXPIRE = 604800  # 7 dias

# AWS S3 - Upload com Presigned URLs (bucket único com prefixos por organização)
AWS_REGION = config('AWS_REGION', default='us-east-1')  # Alias para compatibilidade
AWS_BUCKET_NAME = config('AWS_BUCKET_NAME', default='iamkt-uploads')  # Bucket único para toda aplicação

# IA CACHE
IA_CACHE_TTL = config('IA_CACHE_TTL', default=2592000, cast=int)  # 30 dias

# USAGE LIMITS
DEFAULT_MONTHLY_GENERATION_LIMIT = config('DEFAULT_MONTHLY_GENERATION_LIMIT', default=100, cast=int)
DEFAULT_MONTHLY_COST_LIMIT = config('DEFAULT_MONTHLY_COST_LIMIT', default=100.00, cast=float)

# N8N INTEGRATION
N8N_WEBHOOK_FUNDAMENTOS = config('N8N_WEBHOOK_FUNDAMENTOS', default='')
N8N_WEBHOOK_COMPILE_SEMSUGEST = config('N8N_WEBHOOK_COMPILA_SEM_SUGEST', default='')
N8N_WEBHOOK_COMPILE_COMSUGEST = config('N8N_WEBHOOK_COMPILA_COM_SUGEST', default='')
N8N_WEBHOOK_GERAR_PAUTA = config('N8N_WEBHOOK_GERAR_PAUTA', default='')
N8N_WEBHOOK_GERAR_POST = config('N8N_WEBHOOK_GERAR_POST', default='')
N8N_WEBHOOK_TIMEOUT = config('N8N_WEBHOOK_TIMEOUT', default=30, cast=int)
N8N_WEBHOOK_SECRET = config('N8N_WEBHOOK_SECRET', default='')
N8N_ALLOWED_IPS = config('N8N_ALLOWED_IPS', default='127.0.0.1')
N8N_RATE_LIMIT_PER_IP = config('N8N_RATE_LIMIT_PER_IP', default='10/minute')
N8N_RATE_LIMIT_PER_ORG = config('N8N_RATE_LIMIT_PER_ORG', default='5/minute')
N8N_MAX_RETRIES = config('N8N_MAX_RETRIES', default=3, cast=int)
N8N_RETRY_DELAY = config('N8N_RETRY_DELAY', default=5, cast=int)
# N8N_INTERNAL_TOKEN removido - usar N8N_WEBHOOK_SECRET para autenticação
