import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

# Устанавливаем настройки Django по умолчанию для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Используем строку конфигурации, все настройки Celery должны начинаться с 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим задачи во всех приложениях Django
app.autodiscover_tasks()

# Периодические задачи - ВРЕМЕННО для тестирования (каждую минуту)
app.conf.beat_schedule = {
    # Новая задача для проверки подписок, требующих продления - КАЖДУЮ МИНУТУ для теста
    'process-pending-renewals': {
        'task': 'users.tasks.process_pending_renewals',
        'schedule': crontab(minute='*'),  # Каждую минуту!
    },
    # Уведомления об окончании подписки - КАЖДУЮ МИНУТУ для теста
    'notify-upcoming-expiration': {
        'task': 'users.tasks.notify_upcoming_expiration',
        'schedule': crontab(minute='*'),  # Каждую минуту!
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')