"""
Биллинг для dev-API: конвертация токенов -> звёзды (личный) или рубли (орг).
Делит единый кошелёк pages_count с web-чатом для личных ключей.
Для ключей организации списывает из Organization.balance_rub.
"""
import logging
import os
import uuid

logger = logging.getLogger(__name__)

_DEFAULT_TOKENS_PER_MESSAGE = 500

# Стоимость 1 звезды в рублях для орг-биллинга (настраивается через env)
ORG_RUB_PER_STAR = float(os.environ.get('ORG_RUB_PER_STAR', '1.0'))


def get_stars_per_1k(network) -> float:
    """Возвращает звёзд за 1000 токенов для данной сети."""
    rate = getattr(network, 'stars_per_1k_tokens', 0)
    if rate and rate > 0:
        return float(rate)
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
    Списывает средства за использование токенов.
    - Личный ключ (api_key.organization is None): списывает звёзды у пользователя.
    - Ключ организации: списывает рубли из org.balance_rub.
    usage: {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}
    Возвращает количество списанных звёзд.
    Бросает InsufficientStarsError при нехватке баланса.
    """
    from api.exceptions import InsufficientStarsError
    from api.models import TokenUsage

    total_tokens = usage.get('total_tokens', 0)
    stars = tokens_to_stars(network, total_tokens)

    organization = getattr(api_key, 'organization', None) if api_key else None

    if organization is not None:
        # Org billing: deduct from org.balance_rub
        cost_rub = round(stars * ORG_RUB_PER_STAR, 2)
        if organization.balance_rub < cost_rub:
            raise InsufficientStarsError(
                f'Недостаточно баланса организации. '
                f'Нужно {cost_rub} руб., у организации {organization.balance_rub} руб.'
            )
        organization.balance_rub -= cost_rub
        organization.save(update_fields=['balance_rub'])
        logger.info(
            f'[ORG] Списано {cost_rub} руб. ({total_tokens} токенов) '
            f'с баланса {organization.name}'
        )
    else:
        # Personal billing: deduct stars
        if user.pages_count < stars:
            raise InsufficientStarsError(
                f'Недостаточно звёзд. Нужно {stars} зв., у вас {user.pages_count} зв.'
            )
        user.spend_pages(stars)
        logger.info(f'[API] Списано {stars} зв. ({total_tokens} токенов) у {user.email}')

    TokenUsage.objects.create(
        user=user,
        network=network,
        api_key=api_key,
        organization=organization,
        prompt_tokens=usage.get('prompt_tokens', 0),
        completion_tokens=usage.get('completion_tokens', 0),
        total_tokens=total_tokens,
        stars_charged=stars,
        request_id=str(uuid.uuid4())[:8],
    )

    return stars


def refund_stars(user, stars: int, reason: str = '', api_key=None):
    """Возвращает средства при ошибке апстрима."""
    if stars <= 0:
        return

    organization = getattr(api_key, 'organization', None) if api_key else None

    if organization is not None:
        cost_rub = round(stars * ORG_RUB_PER_STAR, 2)
        organization.balance_rub += cost_rub
        organization.save(update_fields=['balance_rub'])
        logger.info(f'[ORG] Возвращено {cost_rub} руб. организации {organization.name}. {reason}')
    else:
        user.add_pages(stars)
        logger.info(f'[API] Возвращено {stars} зв. пользователю {user.email}. {reason}')
