"""
Лимиты бесплатных моделей (Groq).

Бесплатные модели (`NeuralNetwork.is_free=True`) доступны всем пользователям без
списания средств, но с дневным лимитом сообщений на пользователя
(`messages_limit`) — чтобы не исчерпать общую бесплатную квоту Groq на весь сервис.
"""
from django.utils import timezone

from .models import NeuralNetworkDailyUsage


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
    if usage.count >= network.messages_limit:
        return False
    usage.count += 1
    usage.save(update_fields=['count'])
    return True
