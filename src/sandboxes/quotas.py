"""
Квоты Sandbox API: дневной кап минут (Redis, fail-open как у превью) и лимит
одновременных сессий (по БД — источник истины биллинга).
"""
import logging
import math
import os
from datetime import date

from django.conf import settings

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'redis'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=int(os.environ.get('REDIS_DB', 0)),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def _daily_key(user_id) -> str:
    return f'sandbox:daily_min:{user_id}:{date.today().strftime("%Y%m%d")}'


def check_and_reserve_daily_cap(user_id, ttl_seconds: int) -> tuple[bool, int, int]:
    """INCR-first: атомарно занять минуты в дневном капе.
    Возвращает (allowed, used_min_before, cap_min). Fail-open при ошибке Redis."""
    cap = int(getattr(settings, 'SANDBOX_DAILY_CAP_MIN', 240))
    if cap <= 0:
        return True, 0, 0
    minutes = max(1, math.ceil(ttl_seconds / 60))
    try:
        r = _get_redis()
        pipe = r.pipeline()
        pipe.incrby(_daily_key(user_id), minutes)
        pipe.expire(_daily_key(user_id), 86400)
        new_total = int(pipe.execute()[0])
        if new_total > cap:
            r.decrby(_daily_key(user_id), minutes)
            return False, new_total - minutes, cap
        return True, new_total - minutes, cap
    except Exception:
        return True, 0, cap


def refund_daily_cap(user_id, ttl_seconds: int) -> None:
    """Вернуть минуты капа при ошибке старта."""
    if int(getattr(settings, 'SANDBOX_DAILY_CAP_MIN', 240)) <= 0:
        return
    try:
        _get_redis().decrby(_daily_key(user_id), max(1, math.ceil(ttl_seconds / 60)))
    except Exception:
        pass


def check_concurrent(user) -> tuple[bool, int, int]:
    """Лимит одновременных сессий по БД. Возвращает (allowed, active, limit)."""
    from .models import SandboxSession
    limit = int(getattr(settings, 'SANDBOX_MAX_CONCURRENT_PER_USER', 3))
    active = SandboxSession.objects.filter(
        user=user, state__in=SandboxSession.ACTIVE_STATES,
    ).count()
    return active < limit, active, limit
