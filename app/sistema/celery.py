import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')

app = Celery('sistema')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule - Tasks Periódicas
app.conf.beat_schedule = {
    'monitor-trends-daily': {
        'task': 'apps.content.tasks.monitor_trends_task',
        'schedule': crontab(hour=9, minute=0),  # Diariamente às 9h
    },
    'cleanup-cache-weekly': {
        'task': 'apps.content.tasks.cleanup_old_cache_task',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Domingos às 2h
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
