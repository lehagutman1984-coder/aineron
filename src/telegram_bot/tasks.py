import logging
import time
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='telegram_bot.tasks.notify_low_balance')
def notify_low_balance():
    """Notify Telegram users with low balance. Run daily via Celery Beat."""
    try:
        from telegram_bot.models import TelegramUser
        from telegram_bot.notify import notify_user
        from django.core.cache import cache

        threshold = 5
        tg_users = list(
            TelegramUser.objects.select_related('user').filter(
                user__isnull=False, user__pages_count__lte=threshold,
            )
        )
        notified = 0
        for tu in tg_users:
            cache_key = f'tg_low_bal_{tu.telegram_id}'
            if cache.get(cache_key):
                continue
            notify_user(
                tu.telegram_id,
                f'Баланс заканчивается: <b>{tu.user.pages_count} зв.</b>\n'
                f'Пополни чтобы продолжить: /balance',
            )
            cache.set(cache_key, True, timeout=86400)
            notified += 1
        logger.info(f'notify_low_balance: {notified} notified')
    except Exception as e:
        logger.error(f'notify_low_balance error: {e}')


@shared_task(name='telegram_bot.tasks.broadcast_message', bind=True, max_retries=0)
def broadcast_message(self, text: str, admin_tg_id: int):
    """Send broadcast to all linked Telegram users. ~20 msg/s."""
    try:
        from telegram_bot.models import TelegramUser
        from telegram_bot.notify import notify_user

        tg_ids = list(
            TelegramUser.objects.filter(user__isnull=False).values_list('telegram_id', flat=True)
        )
        sent = 0
        failed = 0
        for tg_id in tg_ids:
            try:
                notify_user(tg_id, text)
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        try:
            notify_user(admin_tg_id, f'Рассылка завершена: {sent} отправлено, {failed} ошибок.')
        except Exception:
            pass
        logger.info(f'broadcast_message: {sent} sent, {failed} failed')
    except Exception as e:
        logger.error(f'broadcast_message error: {e}')
