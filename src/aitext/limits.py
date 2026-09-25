"""
Лимиты бесплатных моделей (Groq).

Бесплатные модели (`NeuralNetwork.is_free=True`) доступны всем пользователям без
списания средств, но с дневным лимитом сообщений на пользователя
(`messages_limit`) — чтобы не исчерпать общую бесплатную квоту Groq на весь сервис.
"""
from django.db.models import F
from django.utils import timezone

from .models import NeuralNetworkDailyUsage


def claim_free_slot(usage, limit) -> bool:
    """Атомарно занимает слот дневного лимита: условный UPDATE count<limit.
    Раньше во всех местах было `if usage.count < limit: usage.count += 1; usage.save()` -
    чтение-изменение-запись без блокировки: N параллельных запросов проходили проверку
    разом (lost update), и все N сообщений становились бесплатными (deduct_stars=False)."""
    claimed = type(usage).objects.filter(pk=usage.pk, count__lt=limit).update(count=F('count') + 1) > 0
    if claimed:
        usage.count += 1  # локальный объект - для логов вызывающего кода
    return claimed


def consume_free_message(user, network):
    """
    Проверяет и учитывает бесплатное сообщение для is_free-модели.

    Возвращает True, если сообщение разрешено (и счётчик увеличен), либо False,
    если дневной лимит пользователя по этой модели исчерпан.
    Для не-бесплатных моделей всегда True (без побочных эффектов).
    """
    if not getattr(network, 'is_free', False):
        return True
    if network.messages_limit <= 0:
        # Бесплатно без дневного лимита.
        return True
    today = timezone.now().date()
    usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
        user=user, network=network, date=today, defaults={'count': 0}
    )
    return claim_free_slot(usage, network.messages_limit)
