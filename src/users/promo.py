"""
Общая логика погашения промокода на баланс — используется веб-API
(`api/views/billing.py::ApplyPromoView`) и Telegram-ботом (`/promo`),
чтобы не дублировать транзакционную защиту от двойного применения.

Скидочные промокоды (discount_percent > 0) здесь не гасятся — они вводятся
отдельно при оплате тарифа.

GROWTH_PLAN_RU.md §7.7: защита от мультиаккаунтов при погашении промокодов —
не на регистрации (грубо, банит легитимных пользователей за одним NAT), а
здесь, в точке реальной выдачи денег:
- дневной лимит успешных погашений с одного IP (`PROMO_REDEEM_IP_DAILY_CAP`);
- требование подтверждённого email — только для веб-пути (`require_email_verified`).
  Боту его передавать нельзя: standalone-аккаунты, созданные прямо в Telegram
  (`telegram_bot/handlers/start.py::_create_standalone_account`), получают
  placeholder-адрес `tg{id}@telegram.local` и никогда не проходят email-верификацию
  — для них подтверждённая привязка к Telegram-аккаунту и есть эквивалент
  верификации.
"""
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from core.money import format_money
from users.models import PaymentHistory, PromoCode, UsedPromoCode

# Без 0/O/1/I — визуально не путаются при ручном вводе кода с телефона
_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _promo_ip_key(ip: str) -> str:
    return f'promoredeem_ip:{ip}:{timezone.now().date().isoformat()}'


def _reserve_ip_quota(ip: str) -> bool:
    """Атомарный check-and-increment дневного лимита погашений по IP.

    Fail-open при сбое Redis — падение кэша не должно блокировать легитимных
    пользователей, это мягкая защита от фарма, а не биллинговая корректность.
    """
    cap = int(getattr(settings, 'PROMO_REDEEM_IP_DAILY_CAP', 3))
    if cap <= 0 or not ip:
        return True
    key = _promo_ip_key(ip)
    try:
        cache.add(key, 0, timeout=86400)
        count = cache.incr(key)
    except Exception:
        return True
    return count <= cap


class _IpQuotaExceeded(Exception):
    """Внутренний сигнал для отката UsedPromoCode в той же atomic-транзакции —
    наружу никогда не просачивается, см. redeem_promo_code."""


def generate_unique_promo_code(prefix: str = '', suffix_len: int = 8) -> str:
    """Подбирает случайный ещё не занятый код промокода.

    Используется management-командой generate_promo_codes и admin-action
    в PromoCodeAdmin — общее место, чтобы не разъезжались алфавит/формат.
    """
    prefix = (prefix or '').strip().upper()
    for _ in range(20):
        suffix = ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(suffix_len))
        code = f'{prefix}-{suffix}' if prefix else suffix
        if not PromoCode.objects.filter(code__iexact=code).exists():
            return code
    raise RuntimeError('Не удалось подобрать уникальный промокод за 20 попыток')


def redeem_promo_code(user, code_str, intl=False, ip=None, require_email_verified=False):
    """Погашает промокод на баланс пользователя.

    ip: IP запроса для дневного лимита погашений (веб-путь; бот его не передаёт
        — у Telegram-запросов нет IP пользователя).
    require_email_verified: включать проверку подтверждённого email. Только для
        веб-пути — у ботовых standalone-аккаунтов email не верифицируется в
        принципе (см. модульный докстринг).

    Возвращает dict:
    - при успехе: {'ok': True, 'stars_added', 'kopecks_added',
      'new_balance', 'new_balance_kopecks', 'message'}
    - при ошибке: {'ok': False, 'error_code', 'message'}
    """
    code_str = (code_str or '').strip()
    if not code_str:
        msg = 'Promo code is required' if intl else 'Введите промокод'
        return {'ok': False, 'error_code': 'missing_code', 'message': msg}

    try:
        promo = PromoCode.objects.get(code__iexact=code_str)
    except PromoCode.DoesNotExist:
        msg = 'Promo code not found' if intl else 'Промокод не найден'
        return {'ok': False, 'error_code': 'promo_not_found', 'message': msg}

    if not promo.is_valid():
        msg = 'Promo code is invalid or expired' if intl else 'Промокод недействителен или истёк'
        return {'ok': False, 'error_code': 'promo_expired', 'message': msg}

    if promo.discount_percent > 0:
        msg = (
            f'This is a discount code (−{promo.discount_percent}% on a plan) — enter it at checkout'
            if intl else
            f'Это скидочный промокод (−{promo.discount_percent}% на тариф) — введите его при покупке тарифа'
        )
        return {'ok': False, 'error_code': 'promo_is_discount', 'message': msg}

    if require_email_verified and not user.email_verified:
        msg = (
            'Please verify your email before redeeming a promo code'
            if intl else
            'Подтвердите email на сайте, прежде чем активировать промокод'
        )
        return {'ok': False, 'error_code': 'email_not_verified', 'message': msg}

    # Фиксируем использование ДО начисления: unique (user, promo_code)
    # гасит гонку двойного применения (как в legacy users/views.py).
    # Savepoint обязателен: без него пойманный здесь IntegrityError
    # отравляет внешнюю транзакцию (TransactionManagementError на следующий
    # запрос) в контекстах, где эта функция вызвана внутри atomic-блока —
    # см. тот же фикс в api/views/memory.py (B12).
    #
    # IP-квота резервируется ЗДЕСЬ, внутри той же atomic-транзакции, а не до
    # неё: иначе повторная попытка погасить уже использованный код (частый
    # случай — юзер дважды жмёт кнопку) сжигала бы IP-лимит раньше, чем мы
    # успевали понять, что это дубль, а не новое погашение. При превышении
    # квоты _IpQuotaExceeded откатывает уже созданный UsedPromoCode — код
    # остаётся доступен для повтора завтра или с другого IP.
    try:
        with transaction.atomic():
            UsedPromoCode.objects.create(user=user, promo_code=promo)
            if ip and not _reserve_ip_quota(ip):
                raise _IpQuotaExceeded
    except IntegrityError:
        msg = 'Promo code already used' if intl else 'Промокод уже был использован'
        return {'ok': False, 'error_code': 'promo_already_used', 'message': msg}
    except _IpQuotaExceeded:
        msg = (
            'Too many promo codes redeemed from this network today — try again tomorrow'
            if intl else
            'Слишком много промокодов погашено с этой сети сегодня — попробуйте завтра'
        )
        return {'ok': False, 'error_code': 'ip_limit_exceeded', 'message': msg}

    PromoCode.objects.filter(pk=promo.pk).update(used_count=F('used_count') + 1)
    user.add_kopecks(promo.kopecks, type='promo', reference=f'promo:{promo.pk}:{user.id}')

    description = (
        f'Promo code {code_str}: +{format_money(promo.kopecks)}' if intl
        else f'Промокод {code_str}: +{format_money(promo.kopecks)}'
    )
    PaymentHistory.objects.create(
        user=user,
        payment_type='promo',
        invoice_id=f'promo-{promo.pk}',
        amount=0,
        amount_kopecks=0,
        pages_count=promo.stars,
        status='success',
        description=description,
    )

    message = (
        f'Promo code accepted! Credited {format_money(promo.kopecks)}.' if intl
        else f'Промокод принят! Начислено {format_money(promo.kopecks)}.'
    )
    return {
        'ok': True,
        'stars_added': promo.stars,
        'kopecks_added': promo.kopecks,
        'new_balance': user.pages_count,
        'new_balance_kopecks': user.balance_kopecks,
        'message': message,
    }
