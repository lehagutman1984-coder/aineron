"""
Цена платных «функций» (Agent Mode, Deep Research) и выбор модели секретаря.

STATUS_AND_BACKLOG_PLAN_2026-09-25.md, ITEM 1. Раньше цены были плоскими
(Agent 5 руб., Research 10 руб.) при ЛЮБОЙ модели пользователя: на GPT-5.5 Pro один
прогон агента стоил нам до ~390 руб. Теперь цена = max(фикс, ceil(k * cost_kopecks
выбранной модели)) и показывается пользователю ДО запуска.

Всё за флагом settings.FEATURE_MODEL_PRICING_ENABLED (по умолчанию 0): при 0 функции
возвращают прежние значения (плоские цены, шаги агента 1800 токенов, секретарь на
любой модели) - выкладка кода на оба инстанса ничего не меняет, пока флаг не включён.

Единственный источник цены: handler/view вызывает resolve_feature() ОДИН раз и
передаёт (network_id, price) в задачу - задача не пересчитывает цену и модель, иначе
пользователь мог бы увидеть цену модели A, а получить запуск на модели B.
"""
import logging
import math

from django.conf import settings

logger = logging.getLogger(__name__)

FEATURES = ('agent', 'research')


def enabled() -> bool:
    return bool(getattr(settings, 'FEATURE_MODEL_PRICING_ENABLED', False))


def flat_price_kopecks(feature: str) -> int:
    if feature == 'agent':
        return int(getattr(settings, 'AGENT_PRICE_KOPECKS', 500))
    if feature == 'research':
        return int(getattr(settings, 'RESEARCH_PRICE_KOPECKS', 1000))
    raise ValueError(f'unknown feature: {feature}')


def _multiplier(feature: str) -> float:
    if feature == 'agent':
        return float(getattr(settings, 'AGENT_MODEL_MULTIPLIER', 5))
    return float(getattr(settings, 'RESEARCH_MODEL_MULTIPLIER', 2))


def feature_price_kopecks(feature: str, network) -> int:
    """Цена запуска функции на модели `network` (копейки)."""
    flat = flat_price_kopecks(feature)
    if not enabled() or network is None:
        return flat
    cost = int(getattr(network, 'cost_kopecks', 0) or 0)
    return max(flat, math.ceil(_multiplier(feature) * cost))


def cheapest_text_network():
    from aitext.models import NeuralNetwork
    return (NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks').first())


def default_text_network(tg_user=None):
    """Модель по умолчанию пользователя бота, иначе самая дешёвая текстовая."""
    network = getattr(tg_user, 'default_network', None) if tg_user is not None else None
    if network is not None and network.is_active:
        return network
    return cheapest_text_network()


def resolve_feature(feature: str, tg_user=None, network=None):
    """(network, price_kopecks) для запуска функции.

    network - явно выбранная модель (например, модель веб-чата); иначе модель по
    умолчанию пользователя бота либо самая дешёвая текстовая. Если модели нет -
    (None, flat).
    """
    if network is None:
        network = default_text_network(tg_user)
    return network, feature_price_kopecks(feature, network)


def base_network_and_price(feature: str):
    """Самая дешёвая текстовая модель и цена на ней (кнопка «на базовой модели»)."""
    network = cheapest_text_network()
    return network, feature_price_kopecks(feature, network)


# ─── Возвраты строго по леджеру ───

def spent_kopecks(user, reference: str) -> int:
    """Сколько реально списано по reference (копейки, положительное число; 0 - не списывали)."""
    from users.models import BalanceTransaction
    row = (BalanceTransaction.objects
           .filter(user=user, type='spend', reference=reference)
           .values_list('amount_kopecks', flat=True).first())
    return abs(int(row)) if row else 0


def refund_spend_by_reference(user, reference: str) -> bool:
    """Возвращает РОВНО списанную по reference сумму (из леджера, не из настроек).

    Идемпотентно (unique(type, reference)). Раньше возвраты брали цену из settings:
    при цене, зависящей от модели, это возвращало бы не ту сумму, а гонка «кто первый
    вернул» (задача vs поллер бота) оставляла бы пользователя недовозвращённым.
    Возвращает True, если возврат выполнен сейчас или уже был; False - списания не было.
    """
    amount = spent_kopecks(user, reference)
    if amount <= 0:
        return False
    user.add_kopecks(amount, type='refund', reference=reference)
    return True


# ─── Параметры Agent Mode ───

def agent_step_max_tokens() -> int:
    """max_tokens промежуточных шагов агента (финальный ответ - всегда 1800)."""
    if enabled():
        return int(getattr(settings, 'AGENT_STEP_MAX_TOKENS', 700))
    return 1800


def agent_observation_chars() -> int:
    if enabled():
        return int(getattr(settings, 'AGENT_OBSERVATION_CHARS', 3000))
    return 4000


# ─── Секретарь ───

def resolve_business_network(tg_user):
    """Модель секретаря: модель владельца, если она не дороже порога, иначе запасная.

    Секретарь работает без участия владельца и продаётся с плоской ценой (1 руб. за
    ответ), поэтому дорогая модель по умолчанию не должна молча делать каждый ответ
    убыточным. При выключенном флаге - прежнее поведение (любая активная модель).
    """
    from aitext.models import NeuralNetwork

    network = getattr(tg_user, 'default_network', None)
    if network is None or not network.is_active:
        return cheapest_text_network()
    if not enabled():
        return network
    limit = int(getattr(settings, 'BUSINESS_MAX_MODEL_KOPECKS', 300))
    if int(network.cost_kopecks or 0) <= limit:
        return network
    slug = getattr(settings, 'BUSINESS_FALLBACK_MODEL_SLUG', '') or ''
    if slug:
        fallback = NeuralNetwork.objects.filter(slug=slug, is_active=True).first()
        if fallback is not None:
            return fallback
        logger.warning(f'BUSINESS_FALLBACK_MODEL_SLUG={slug!r} не найдена/неактивна')
    return cheapest_text_network()
