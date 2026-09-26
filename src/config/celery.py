import os
import sys
from celery import Celery
from celery.signals import celeryd_init
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
@celeryd_init.connect
def _allow_async_unsafe_for_gevent_worker(sender=None, options=None, **kwargs):
    """Воркер на gevent (--pool=gevent): все greenlet'ы живут в ОДНОМ потоке ОС. Когда одна
    задача внутри async_to_sync (доставка в Telegram, Deep Research/Agent -> notify_user_rich)
    ждёт сеть, «запущенный цикл событий» виден как активный для всего потока, и ORM-вызов
    ЛЮБОЙ соседней задачи падает с SynchronousOnlyOperation ("You cannot call this from an
    async context"). Воспроизведено на проде 2026-09-26: агент и Deep Research, запущенные
    одновременно, - у исследования упали и шаг, и обработчик ошибки (деньги списаны, возврата
    нет, статус навсегда 'running'). Проверка Django защищает от блокировки цикла событий, а
    здесь чужой цикл принадлежит другому greenlet'у и ORM его не блокирует - штатный обход
    для gevent-воркеров. Выставляем ТОЛЬКО в процессе воркера: в web/manage.py переменная
    ломала бы системную проверку async.E001."""
    pool = str((options or {}).get('pool') or '')
    if 'gevent' in pool or 'gevent' in ' '.join(sys.argv):
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'


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