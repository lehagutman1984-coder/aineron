"""
Биллинг Sandbox API — поверх атомарных kopecks-операций CustomUser.

Схема (как у превью Studio, но без зависимости от studio.billing — Studio заморожена):
  reserve()     — при создании: списать max-стоимость TTL (ceil минут × цена);
  settle()      — при stop/expire: вернуть разницу за неиспользованные минуты;
  refund_full() — при ошибке старта: вернуть весь резерв.

Все операции идемпотентны по (type, reference) — повтор Celery/запроса не задвоит.
"""
import logging
import math

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def price_per_min_kopecks(size: str) -> int:
    prices = getattr(settings, 'SANDBOX_PRICE_KOPECKS', {'small': 50, 'standard': 100})
    return int(prices.get(size, prices.get('standard', 100)))


def max_cost_kopecks(size: str, ttl_seconds: int) -> int:
    minutes = max(1, math.ceil(ttl_seconds / 60))
    return minutes * price_per_min_kopecks(size)


def reserve(user, session) -> bool:
    """Списать max-стоимость сессии в резерв. False — не хватает баланса."""
    amount = max_cost_kopecks(session.size, session.ttl_seconds)
    ok = user.spend_kopecks(
        amount, type='sandbox', reference=f'sandbox:{session.pk}:reserve',
    )
    if ok:
        session.reserved_kopecks = amount
        session.save(update_fields=['reserved_kopecks'])
    return ok


def settle(session, duration_seconds: float) -> int:
    """Финальный расчёт: списано = ceil(минут) × цена (мин. 1 минута), но не больше
    резерва; разница возвращается. Возвращает charged_kopecks.

    Идемпотентно: возврат идёт одним reference sandbox:{pk}:settle — повторный вызов
    (гонка DELETE и reconcile) не начислит возврат дважды."""
    if session.reserved_kopecks <= 0:
        return 0
    minutes = max(1, math.ceil(max(0.0, duration_seconds) / 60))
    charged = min(minutes * price_per_min_kopecks(session.size), session.reserved_kopecks)
    refund = session.reserved_kopecks - charged
    if refund > 0:
        session.user.add_kopecks(
            refund, type='refund', reference=f'sandbox:{session.pk}:settle',
        )
    session.charged_kopecks = charged
    session.stopped_at = session.stopped_at or timezone.now()
    session.save(update_fields=['charged_kopecks', 'stopped_at'])
    logger.info('[sandbox] settle %s: charged=%s refund=%s', session.public_id, charged, refund)
    return charged


def refund_full(session) -> None:
    """Ошибка старта VM — вернуть весь резерв, сессию пометить failed."""
    if session.reserved_kopecks > 0:
        session.user.add_kopecks(
            session.reserved_kopecks, type='refund',
            reference=f'sandbox:{session.pk}:refund',
        )
    session.charged_kopecks = 0
    session.state = session.State.FAILED
    session.stopped_at = timezone.now()
    session.save(update_fields=['charged_kopecks', 'state', 'stopped_at'])
    logger.info('[sandbox] refund_full %s: %s коп.', session.public_id, session.reserved_kopecks)
