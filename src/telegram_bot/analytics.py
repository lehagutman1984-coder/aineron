import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


def log_event(tg_user, event_type: str, network=None, cost: int = 0, **meta):
    """Log a TelegramEvent + UsageEvent. Sync, never raises."""
    try:
        from telegram_bot.models import TelegramEvent
        TelegramEvent.objects.create(
            telegram_user=tg_user,
            event_type=event_type,
            network=network,
            cost=cost,
            meta=meta or {},
        )
    except Exception as e:
        logger.debug(f'log_event TelegramEvent failed ({event_type}): {e}')

    # Mirror to unified UsageEvent
    try:
        from aitext.usage import log_usage_event
        user = tg_user.user if tg_user else None
        log_usage_event(
            user=user,
            event_type=event_type,
            channel='bot',
            network=network,
            cost=cost,
            **meta,
        )
    except Exception as e:
        logger.debug(f'log_event UsageEvent failed ({event_type}): {e}')


async_log_event = sync_to_async(log_event, thread_sensitive=True)
