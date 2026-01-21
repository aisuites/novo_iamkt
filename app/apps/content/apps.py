from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.content'
    
    def ready(self):
        """Importar signals quando app estiver pronto"""
        import apps.content.signals
