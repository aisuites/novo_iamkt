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
]

LOCAL_APPS = [
    'apps.core',
    'apps.knowledge',
    'apps.content',
    'apps.campaigns',
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

# IA CACHE
IA_CACHE_TTL = config('IA_CACHE_TTL', default=2592000, cast=int)  # 30 dias

# USAGE LIMITS
DEFAULT_MONTHLY_GENERATION_LIMIT = config('DEFAULT_MONTHLY_GENERATION_LIMIT', default=100, cast=int)
DEFAULT_MONTHLY_COST_LIMIT = config('DEFAULT_MONTHLY_COST_LIMIT', default=100.00, cast=float)
