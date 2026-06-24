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
    # Studio watchdog: detect stalled/timed-out pipelines every 2 minutes
    'studio-watchdog': {
        'task': 'studio.watchdog_pipelines',
        'schedule': 120.0,
        'options': {'queue': 'studio_queue'},
    },
    # Memory: суммаризация брошенных чатов (>24ч без активности, без summary) — каждые 2 часа
    'memory-summarize-stale-chats': {
        'task': 'aitext.tasks.summarize_stale_chats',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # Daily digest: check every minute who needs a digest right now
    'telegram-daily-digest': {
        'task': 'telegram_bot.tasks.send_daily_digests',
        'schedule': crontab(minute='*'),
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')