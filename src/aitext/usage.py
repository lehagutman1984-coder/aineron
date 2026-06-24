"""
Unified usage event logging — web + bot → UsageEvent.
Thread-safe, graceful (never raises, only logs errors).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def log_usage_event(
    user,
    event_type: str,
    channel: str = 'web',
    network=None,
    cost: int = 0,
    **meta,
) -> None:
    """
    Write a UsageEvent record. Silently swallows all exceptions.

    Args:
        user: CustomUser instance or None
        event_type: UsageEvent.EventType value (e.g. 'message', 'image', 'error')
        channel: 'web' | 'bot' | 'api'
        network: NeuralNetwork instance or None
        cost: integer star cost (default 0)
        **meta: arbitrary key-value pairs stored in meta JSONField
    """
    try:
        from aitext.models import UsageEvent
        UsageEvent.objects.create(
            user=user,
            channel=channel,
            event_type=event_type,
            network=network,
            cost=cost,
            meta=meta or {},
        )
    except Exception as exc:
        logger.debug('log_usage_event failed (non-fatal): %s', exc)


async def async_log_usage_event(
    user,
    event_type: str,
    channel: str = 'bot',
    network=None,
    cost: int = 0,
    **meta,
) -> None:
    """Async wrapper — for use in async bot handlers."""
    from asgiref.sync import sync_to_async
    await sync_to_async(log_usage_event, thread_sensitive=True)(
        user, event_type, channel=channel, network=network, cost=cost, **meta
    )
