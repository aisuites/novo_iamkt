from .base import *

# Em desenvolvimento, usamos configurações menos restritivas
# mas mantemos a estrutura próxima da produção

# DESABILITAR CACHE DE TEMPLATES EM DESENVOLVIMENTO
for template_engine in TEMPLATES:
    template_engine['OPTIONS']['debug'] = True
    template_engine['APP_DIRS'] = False
    # Desabilitar cache de templates
    template_engine['OPTIONS']['loaders'] = [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]

# STATIC FILES - Usar storage simples em desenvolvimento (sem hash/manifest)
# Isso permite que alterações em CSS/JS apareçam imediatamente sem collectstatic
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# DESABILITAR WHITENOISE CACHE EM DESENVOLVIMENTO
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 0
