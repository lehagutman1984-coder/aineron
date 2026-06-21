import logging

logger = logging.getLogger(__name__)


def log_event(tg_user, event_type: str, network=None, cost: int = 0, **meta):
    """Log a TelegramEvent. Sync, never raises. Call from handlers/tasks."""
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
        logger.debug(f'log_event failed ({event_type}): {e}')
