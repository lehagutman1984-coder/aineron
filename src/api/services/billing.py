"""
Биллинг для dev-API: конвертация токенов → звёзды.
Делит единый кошелёк pages_count с web-чатом.
"""
import logging
import uuid

logger = logging.getLogger(__name__)

# Fallback: если stars_per_1k_tokens не задан, деривируем из cost_per_message.
# Допущение: среднее сообщение ≈ 500 токенов.
_DEFAULT_TOKENS_PER_MESSAGE = 500


def get_stars_per_1k(network) -> float:
    """Возвращает звёзд за 1000 токенов для данной сети."""
    rate = getattr(network, 'stars_per_1k_tokens', 0)
    if rate and rate > 0:
        return float(rate)
    # Дериват: cost_per_message / (avg_tokens_per_msg / 1000)
    cost = network.cost_per_message or 1
    return cost / (_DEFAULT_TOKENS_PER_MESSAGE / 1000)


def tokens_to_stars(network, total_tokens: int) -> int:
    """Конвертирует количество токенов в звёзды (минимум 1 при любом расходе)."""
    if total_tokens <= 0:
        return 0
    rate = get_stars_per_1k(network)
    stars = rate * total_tokens / 1000
    return max(1, round(stars))


def charge_for_tokens(user, network, usage: dict, api_key=None) -> int:
    """
    Списывает звёзды за использование токенов.
    usage: {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}
    Возвращает количество списанных звёзд.
    Бросает InsufficientStarsError при нехватке баланса.
    """
    from api.exceptions import InsufficientStarsError
    from api.models import TokenUsage

    total_tokens = usage.get('total_tokens', 0)
    stars = tokens_to_stars(network, total_tokens)

    if user.pages_count < stars:
        raise InsufficientStarsError(
            f'Недостаточно звёзд. Нужно {stars} зв., у вас {user.pages_count} зв.'
        )

    user.spend_pages(stars)

    TokenUsage.objects.create(
        user=user,
        network=network,
        api_key=api_key,
        prompt_tokens=usage.get('prompt_tokens', 0),
        completion_tokens=usage.get('completion_tokens', 0),
        total_tokens=total_tokens,
        stars_charged=stars,
        request_id=str(uuid.uuid4())[:8],
    )

    logger.info(f'[API] Списано {stars} зв. ({total_tokens} токенов) у {user.email}')
    return stars


def refund_stars(user, stars: int, reason: str = ''):
    """Возвращает звёзды при ошибке апстрима."""
    if stars > 0:
        user.add_pages(stars)
        logger.info(f'[API] Возвращено {stars} зв. пользователю {user.email}. Причина: {reason}')
