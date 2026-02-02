from django.apps import AppConfig


class PautasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pautas'
    verbose_name = 'Pautas'
    
    def ready(self):
        import apps.pautas.signals
