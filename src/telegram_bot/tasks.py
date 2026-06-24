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


@shared_task(bind=True, max_retries=2, ignore_result=True,
             name='telegram_bot.tasks.send_reminders')
def send_reminders(self):
    """
    Runs every minute; dispatches due reminders that haven't been sent yet.
    Registered via DatabaseScheduler PeriodicTask (see management/commands/setup_periodic_tasks.py).
    """
    from django.utils import timezone as tz
    from telegram_bot.models import Reminder

    now = tz.now()
    due = list(Reminder.objects.filter(is_sent=False, remind_at__lte=now).select_related('tg_user'))
    if not due:
        return

    logger.info(f'send_reminders: {len(due)} due')
    ids_ok = []
    for reminder in due:
        try:
            text = f'Напоминание:\n\n{reminder.text}'
            async_to_sync(_bot_send)(reminder.tg_user.telegram_id, text)
            ids_ok.append(reminder.pk)
        except Exception as e:
            logger.warning(f'send_reminders: failed {reminder.pk}: {e}')

    if ids_ok:
        Reminder.objects.filter(pk__in=ids_ok).update(is_sent=True)


@shared_task(bind=True, max_retries=1, ignore_result=True,
             name='telegram_bot.tasks.summarize_poll')
def summarize_poll(self, poll_session_id: int):
    """Generate AI summary for a closed PollSession and deliver to creator."""
    from telegram_bot.models import PollSession
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client

    try:
        session = PollSession.objects.select_related('tg_user', 'tg_user__default_network').get(pk=poll_session_id)
    except PollSession.DoesNotExist:
        return

    if not session.options or not session.vote_counts:
        return

    lines = []
    for opt, cnt in zip(session.options, session.vote_counts):
        lines.append(f'  - {opt}: {cnt} голос(ов)')

    prompt = (
        f'Вопрос опроса: «{session.question}»\n'
        f'Результаты:\n' + '\n'.join(lines) + '\n\n'
        'Сделай краткий аналитический вывод: кто победил, что это значит, '
        'как можно использовать эти данные. Отвечай на русском, 3-5 предложений.'
    )

    network = session.tg_user.default_network
    if not network:
        network = NeuralNetwork.objects.filter(is_active=True, provider='openrouter').order_by('cost_per_message').first()
    if not network or not network.model_name:
        return

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=400,
            temperature=0.5,
        )
        summary = (resp.choices[0].message.content or '').strip()
    except Exception as e:
        logger.warning(f'summarize_poll: AI call failed: {e}')
        return

    PollSession.objects.filter(pk=poll_session_id).update(ai_summary=summary)

    text = f'Опрос завершён!\n\n<b>Вопрос:</b> {session.question}\n\n<b>AI-анализ:</b>\n{summary}'
    async_to_sync(_bot_send_html)(session.tg_user.telegram_id, text)


async def _bot_send_html(telegram_id: int, text: str):
    from aiogram import Bot
    from django.conf import settings as dj_settings
    bot = Bot(token=dj_settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode='HTML')
    finally:
        await bot.session.close()


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
