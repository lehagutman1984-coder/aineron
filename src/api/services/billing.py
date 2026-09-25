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
        stars_charged=kopecks // 100,
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


# ---------------------------------------------------------------------------
# Резерв -> генерация -> расчёт (reserve / settle)
#
# Инцидент 2026-09-25: эндпоинты проверяли только `balance <= 0` до запроса и
# списывали ПОСЛЕ ответа апстрима; при нехватке средств ошибка глоталась
# (warning), а апстрим (apimart) уже выставил нам счёт. Пользователь с 5,56 ₽
# бесплатно получал ответы Opus/Fable по 50-800 ₽.
#
# Теперь: до обращения к апстриму атомарно резервируем worst-case стоимость
# (prompt + max_tokens) через spend_kopecks (условный UPDATE, без TOCTOU), после
# ответа возвращаем разницу. Если баланса не хватает на весь max_tokens —
# сужаем max_tokens до доступного; если не хватает даже на минимальный ответ —
# InsufficientStarsError (402 с подсказкой пополнить баланс).
# ---------------------------------------------------------------------------

MIN_RESERVE_OUT_TOKENS = 256


def top_up_url() -> str:
    from django.conf import settings
    return f"{getattr(settings, 'SITE_URL', 'https://aineron.ru').rstrip('/')}/account/billing/"


def low_balance_threshold_kopecks() -> int:
    from django.conf import settings
    return int(getattr(settings, 'API_LOW_BALANCE_KOPECKS', 5000))


def estimate_text_tokens(text) -> int:
    """Консервативная (завышающая) оценка токенов: лучше зарезервировать чуть
    больше и вернуть разницу, чем недорезервировать. ASCII ~3 симв/токен,
    остальное (кириллица, CJK, эмодзи) ~1 токен на символ."""
    if not text:
        return 0
    text = str(text)
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_chars
    return int(ascii_chars / 3) + other + 1


def estimate_messages_tokens(messages) -> int:
    """Оценка prompt-токенов для OpenAI-формата messages (str / список частей)."""
    total = 0
    for m in messages or []:
        total += 4  # служебные токены роли/разделителей
        content = m.get('content') if isinstance(m, dict) else m
        if isinstance(content, str):
            total += estimate_text_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    total += estimate_text_tokens(part)
                elif isinstance(part.get('text'), str):
                    total += estimate_text_tokens(part['text'])
                elif part.get('type') in ('image_url', 'image', 'input_image'):
                    total += 2000  # картинка: фиксированная оценка
                else:
                    total += estimate_text_tokens(str(part))
        elif content is not None:
            total += estimate_text_tokens(str(content))
        if isinstance(m, dict) and m.get('tool_calls'):
            total += estimate_text_tokens(str(m['tool_calls']))
    return total


def _org_rub_for(kopecks: int):
    return kopecks_to_rub(kopecks * _org_kopecks_per_star() // 100)


def _available_kopecks(user, organization) -> int:
    """Доступный плательщику баланс в копейках личного кошелька."""
    if organization is not None:
        organization.refresh_from_db(fields=['balance_rub'])
        return int(organization.balance_rub * 100) * 100 // max(1, _org_kopecks_per_star())
    user.refresh_from_db(fields=['balance_kopecks'])
    return int(user.balance_kopecks)


def _debit(user, organization, kopecks: int, reference: str, ledger_type: str = 'spend') -> bool:
    """Атомарно списывает kopecks у плательщика. False при нехватке средств."""
    if kopecks <= 0:
        return True
    if organization is not None:
        from django.db.models import F
        cost_rub = _org_rub_for(kopecks)
        return bool(type(organization).objects.filter(
            id=organization.id, balance_rub__gte=cost_rub
        ).update(balance_rub=F('balance_rub') - cost_rub))
    return bool(user.spend_kopecks(kopecks, type=ledger_type, reference=reference))


def _credit(user, organization, kopecks: int, reference: str):
    if kopecks <= 0:
        return
    if organization is not None:
        from django.db.models import F
        type(organization).objects.filter(id=organization.id).update(
            balance_rub=F('balance_rub') + _org_rub_for(kopecks)
        )
    else:
        user.add_kopecks(kopecks, type='refund', reference=reference)


class ApiReservation:
    """Резерв средств под один API-запрос. Создаётся reserve_for_request()."""

    def __init__(self, user, api_key, network, organization, request_id,
                 reserved_kopecks, prompt_tokens, max_tokens, balance_before, narrowed=False):
        self.user = user
        self.api_key = api_key
        self.network = network
        self.organization = organization
        self.request_id = request_id
        self.reserved_kopecks = reserved_kopecks
        self.prompt_tokens = prompt_tokens
        self.max_tokens = max_tokens
        self.balance_before = balance_before
        self.narrowed = narrowed
        self.closed = False

    @property
    def low_balance(self) -> bool:
        # Баланс ниже порога ИЛИ ответ пришлось сузить под баланс - пора пополнить.
        return self.narrowed or self.balance_before < low_balance_threshold_kopecks()

    def headers(self) -> dict:
        """Заголовки ответа: баланс на момент запроса и предупреждение о низком балансе."""
        h = {'X-Aineron-Balance-Kopecks': str(max(0, self.balance_before))}
        if self.low_balance:
            h['X-Aineron-Low-Balance'] = '1'
            h['X-Aineron-Top-Up-Url'] = top_up_url()
        return h


def insufficient_error_payload(exc) -> dict:
    """Тело поля error для 402: код insufficient_quota — контракт API."""
    return {
        'message': str(exc),
        'type': 'insufficient_quota',
        'code': 'insufficient_quota',
        'required_kopecks': getattr(exc, 'required_kopecks', None),
        'balance_kopecks': getattr(exc, 'balance_kopecks', None),
        'top_up_url': top_up_url(),
    }


def _insufficient(required: int, available: int):
    from api.exceptions import InsufficientStarsError
    from core.money import format_rub
    from django.conf import settings
    if getattr(settings, 'INTL_MODE', False):
        # aineron.net: сообщения API - на английском (внешние клиенты/SDK).
        msg = (f'Insufficient balance: this request needs at least {format_rub(required)}, '
               f'your balance is {format_rub(available)}. Top up your balance: {top_up_url()}')
    else:
        msg = (f'Недостаточно средств: для запроса нужно минимум {format_rub(required)}, '
               f'на балансе {format_rub(available)}. Пополните баланс: {top_up_url()}')
    exc = InsufficientStarsError(msg)
    exc.required_kopecks = required
    exc.balance_kopecks = available
    return exc


def reserve_for_request(user, api_key, network, prompt_tokens: int, max_tokens: int,
                        min_out_tokens: int = MIN_RESERVE_OUT_TOKENS) -> ApiReservation:
    """
    Резервирует средства ДО обращения к апстриму. Возвращает ApiReservation,
    у которого .max_tokens уже сужен до того, что плательщик способен оплатить.
    Бросает InsufficientStarsError, если не хватает даже на минимальный ответ
    (в этом случае апстрим вызывать нельзя вообще).
    """
    organization = getattr(api_key, 'organization', None) if api_key else None
    prompt_tokens = max(0, int(prompt_tokens or 0))
    max_tokens = max(1, int(max_tokens or 1))
    available = _available_kopecks(user, organization)
    rate = get_kopecks_per_1k(network)

    floor_out = min(max_tokens, min_out_tokens)
    min_cost = tokens_to_kopecks(network, prompt_tokens + floor_out)
    if available < min_cost:
        raise _insufficient(min_cost, available)

    out = max_tokens
    reserve = tokens_to_kopecks(network, prompt_tokens + out)
    if reserve > available:
        # Сужаем ответ до доступного баланса (итерациями — из-за округления вверх).
        affordable_total = int(Decimal(available) * 1000 / rate) if rate > 0 else 0
        out = max(floor_out, min(max_tokens, affordable_total - prompt_tokens))
        reserve = tokens_to_kopecks(network, prompt_tokens + out)
        for _ in range(20):
            if reserve <= available or out <= floor_out:
                break
            out = max(floor_out, int(out * 0.95))
            reserve = tokens_to_kopecks(network, prompt_tokens + out)
        if reserve > available:
            raise _insufficient(min_cost, available)
        logger.info(
            f'[API] max_tokens сужен {max_tokens} -> {out} под баланс '
            f'{available} коп. ({user.email}, {network.model_name})'
        )

    request_id = uuid.uuid4().hex[:12]
    if not _debit(user, organization, reserve, f'api:{request_id}'):
        # Гонка: параллельный запрос успел потратить баланс между проверкой и резервом.
        raise _insufficient(reserve, _available_kopecks(user, organization))

    return ApiReservation(user, api_key, network, organization, request_id,
                          reserve, prompt_tokens, out, available, narrowed=out < max_tokens)


def release_reservation(res: ApiReservation, reason: str = ''):
    """Полный возврат резерва: апстрим не отдал ничего (ошибка до генерации)."""
    if res.closed:
        return
    res.closed = True
    _credit(res.user, res.organization, res.reserved_kopecks, f'api:{res.request_id}')
    logger.info(f'[API] Резерв {res.reserved_kopecks} коп. возвращён ({res.user.email}). {reason}')


def settle_reservation(res: ApiReservation, usage: dict, fallback_completion_tokens: int = 0) -> int:
    """
    Финальный расчёт: возвращает неиспользованную часть резерва, доплачивает
    перерасход (если оценка prompt оказалась ниже фактической). Пишет TokenUsage.
    Fail-closed: если апстрим не вернул usage (total_tokens == 0), считаем по
    оценке prompt + fallback_completion_tokens, а не по нулю — иначе резерв
    вернулся бы целиком и ответ достался бы бесплатно.
    Возвращает фактически удержанную сумму в копейках.
    """
    from api.models import TokenUsage

    if res.closed:
        return 0
    res.closed = True

    prompt_tokens = int(usage.get('prompt_tokens', 0) or 0)
    completion_tokens = int(usage.get('completion_tokens', 0) or 0)
    total_tokens = int(usage.get('total_tokens', 0) or 0) or (prompt_tokens + completion_tokens)
    if total_tokens <= 0:
        prompt_tokens = res.prompt_tokens
        completion_tokens = max(0, int(fallback_completion_tokens or 0))
        total_tokens = prompt_tokens + completion_tokens
        logger.warning(f'[API] Апстрим не вернул usage ({res.network.model_name}) - '
                       f'расчёт по оценке: {total_tokens} токенов')

    actual = tokens_to_kopecks(res.network, total_tokens)
    charged = res.reserved_kopecks
    if actual < res.reserved_kopecks:
        _credit(res.user, res.organization, res.reserved_kopecks - actual, f'api:{res.request_id}')
        charged = actual
    elif actual > res.reserved_kopecks:
        extra = actual - res.reserved_kopecks
        if _debit(res.user, res.organization, extra, f'api:{res.request_id}:extra'):
            charged = actual
        else:
            logger.warning(f'[API] Перерасход {extra} коп. не списан (баланс исчерпан): '
                           f'{res.user.email}, {res.network.model_name}, req {res.request_id}')

    TokenUsage.objects.create(
        user=res.user,
        network=res.network if getattr(res.network, 'pk', None) else None,
        api_key=res.api_key,
        organization=res.organization,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        stars_charged=charged // 100,
        cost_kopecks=charged,
        request_id=res.request_id[:8],
    )
    logger.info(f'[API] Списано {charged} коп. ({total_tokens} токенов) у {res.user.email}')
    return charged


def flat_charge(user, api_key, kopecks: int, reference: str):
    """
    Атомарное фиксированное списание ДО работы (ASR/TTS и т.п.).
    Бросает InsufficientStarsError с подсказкой пополнения. Возвращает organization
    (или None) — нужна для flat_refund при ошибке апстрима.
    """
    organization = getattr(api_key, 'organization', None) if api_key else None
    if not _debit(user, organization, kopecks, reference):
        raise _insufficient(kopecks, _available_kopecks(user, organization))
    return organization


def flat_refund(user, organization, kopecks: int, reference: str):
    _credit(user, organization, kopecks, reference)
