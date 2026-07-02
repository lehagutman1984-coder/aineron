"""
Биллинг для dev-API: конвертация токенов -> копейки.
Делит единый рублёвый кошелёк (balance_kopecks) с web-чатом для личных ключей.
Для ключей организации списывает из Organization.balance_rub.

Инвариант: 1 звезда (legacy) = 1 рубль = 100 копеек. См. src/core/money.py, BILLING_MIGRATION_PLAN.md
"""
import logging
import uuid
from decimal import Decimal

from core.money import apply_min_charge, ceil_kopecks, kopecks_to_rub

logger = logging.getLogger(__name__)

_DEFAULT_TOKENS_PER_MESSAGE = 500


def get_kopecks_per_1k(network) -> Decimal:
    """Возвращает копеек за 1000 токенов для данной сети."""
    rate = getattr(network, 'kopecks_per_1k_tokens', 0)
    if rate and rate > 0:
        return Decimal(rate)
    cost_kopecks = getattr(network, 'cost_kopecks', 0) or (network.cost_per_message or 1) * 100
    return Decimal(cost_kopecks) / (Decimal(_DEFAULT_TOKENS_PER_MESSAGE) / 1000)


def tokens_to_kopecks(network, total_tokens: int) -> int:
    """Конвертирует количество токенов в копейки (с полом MIN_CHARGE_KOPECKS при любом расходе)."""
    if total_tokens <= 0:
        return 0
    rate = get_kopecks_per_1k(network)
    raw = ceil_kopecks(rate * total_tokens / 1000)
    return apply_min_charge(raw)


def _org_kopecks_per_star() -> int:
    from django.conf import settings
    return int(getattr(settings, 'ORG_KOPECKS_PER_STAR', 100))


def charge_for_tokens(user, network, usage: dict, api_key=None) -> int:
    """
    Списывает средства за использование токенов.
    - Личный ключ (api_key.organization is None): списывает копейки с баланса пользователя.
    - Ключ организации: списывает рубли из org.balance_rub (атомарно, той же ORM-схемой F()).
    usage: {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}
    Возвращает количество списанных копеек.
    Бросает InsufficientStarsError при нехватке баланса.
    """
    from django.db.models import F
    from api.exceptions import InsufficientStarsError
    from api.models import TokenUsage

    total_tokens = usage.get('total_tokens', 0)
    kopecks = tokens_to_kopecks(network, total_tokens)
    request_id = str(uuid.uuid4())[:8]

    organization = getattr(api_key, 'organization', None) if api_key else None

    if organization is not None:
        # Org billing: 1 звезда (100 коп.) = ORG_KOPECKS_PER_STAR коп. орг-баланса.
        # По умолчанию унифицировано с личным тарифом (1:1), настраивается через env.
        cost_rub = kopecks_to_rub(kopecks * _org_kopecks_per_star() // 100)
        organization.refresh_from_db(fields=['balance_rub'])
        if organization.balance_rub < cost_rub:
            raise InsufficientStarsError(
                f'Недостаточно баланса организации. '
                f'Нужно {cost_rub} руб., у организации {organization.balance_rub} руб.'
            )
        updated = type(organization).objects.filter(
            id=organization.id, balance_rub__gte=cost_rub
        ).update(balance_rub=F('balance_rub') - cost_rub)
        if not updated:
            raise InsufficientStarsError(
                f'Недостаточно баланса организации. Нужно {cost_rub} руб.'
            )
        organization.refresh_from_db(fields=['balance_rub'])
        logger.info(
            f'[ORG] Списано {cost_rub} руб. ({total_tokens} токенов) '
            f'с баланса {organization.name}'
        )
    else:
        # Personal billing: deduct kopecks
        if not user.has_enough_kopecks(kopecks):
            from core.money import format_rub
            raise InsufficientStarsError(
                f'Недостаточно средств. Нужно {format_rub(kopecks)}, у вас {format_rub(user.balance_kopecks)}.'
            )
        user.spend_kopecks(kopecks, type='spend', reference=f'api:{request_id}')
        logger.info(f'[API] Списано {kopecks} коп. ({total_tokens} токенов) у {user.email}')

    TokenUsage.objects.create(
        user=user,
        network=network,
        api_key=api_key,
        organization=organization,
        prompt_tokens=usage.get('prompt_tokens', 0),
        completion_tokens=usage.get('completion_tokens', 0),
        total_tokens=total_tokens,
        stars_charged=max(1, round(kopecks / 100)) if kopecks else 0,
        cost_kopecks=kopecks,
        request_id=request_id,
    )

    return kopecks


def refund_kopecks(user, kopecks: int, reason: str = '', api_key=None, reference: str = ''):
    """Возвращает средства при ошибке апстрима. Возвращает ровно списанную сумму (без пересчёта)."""
    if kopecks <= 0:
        return

    organization = getattr(api_key, 'organization', None) if api_key else None

    if organization is not None:
        from django.db.models import F
        cost_rub = kopecks_to_rub(kopecks * _org_kopecks_per_star() // 100)
        type(organization).objects.filter(id=organization.id).update(
            balance_rub=F('balance_rub') + cost_rub
        )
        logger.info(f'[ORG] Возвращено {cost_rub} руб. организации {organization.name}. {reason}')
    else:
        user.add_kopecks(kopecks, type='refund', reference=reference)
        logger.info(f'[API] Возвращено {kopecks} коп. пользователю {user.email}. {reason}')
