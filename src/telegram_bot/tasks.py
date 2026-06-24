import logging
import time
from celery import shared_task
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

_DIGEST_PROMPT = (
    "Сделай краткий ежедневный дайджест для пользователя AI-платформы. "
    "Включи: 1) Один интересный факт или новость об AI, "
    "2) Практический совет по работе с языковыми моделями, "
    "3) Краткую мотивирующую мысль. "
    "Формат: лаконично, 3 абзаца с эмодзи. Отвечай на русском."
)


@shared_task(bind=True, max_retries=2, ignore_result=True,
             name='telegram_bot.tasks.send_daily_digests')
def send_daily_digests(self):
    """
    Runs every minute; sends digest to users whose digest_hour:digest_minute
    matches the current Moscow time.
    """
    import pytz
    from datetime import datetime

    moscow = pytz.timezone('Europe/Moscow')
    now_moscow = datetime.now(moscow)
    current_hour = now_moscow.hour
    current_minute = now_moscow.minute

    try:
        from telegram_bot.models import TelegramUser
        users = list(TelegramUser.objects.filter(
            digest_enabled=True,
            digest_hour=current_hour,
            digest_minute=current_minute,
        ).select_related('user', 'default_network'))
    except Exception as e:
        logger.warning(f"send_daily_digests: query failed: {e}")
        return

    if not users:
        return

    logger.info(
        f"send_daily_digests: sending to {len(users)} users "
        f"at {current_hour}:{current_minute:02d} MSK"
    )
    for tg_user in users:
        try:
            _send_digest_to_user(tg_user)
        except Exception as e:
            logger.warning(f"send_daily_digests: failed for {tg_user.telegram_id}: {e}")


def _send_digest_to_user(tg_user):
    from aitext.tasks import get_laozhang_client
    from aitext.models import NeuralNetwork

    user = tg_user.user
    if not user:
        return

    network = tg_user.default_network
    if not network:
        network = (
            NeuralNetwork.objects
            .filter(is_active=True, handle_photo=False, handle_video=False)
            .order_by('cost_per_message')
            .first()
        )
    if not network or not network.model_name:
        return

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {"role": "system", "content": "Ты — полезный AI-ассистент платформы aineron.ru."},
                {"role": "user", "content": _DIGEST_PROMPT},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"send_daily_digests: AI call failed: {e}")
        return

    if not content.strip():
        return

    text = (
        f"*Ваш ежедневный AI-дайджест*\n\n{content}"
        f"\n\n_aineron.ru_ — отключить: /digest off"
    )
    async_to_sync(_bot_send)(tg_user.telegram_id, text)


async def _bot_send(telegram_id: int, text: str):
    from aiogram import Bot
    from django.conf import settings as dj_settings
    bot = Bot(token=dj_settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode='Markdown')
    finally:
        await bot.session.close()


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
