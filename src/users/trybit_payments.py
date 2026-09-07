"""
Оплата криптовалютой через Trybit (ex-CryptoCloud, docs.trybit.com) — второй,
независимый крипто-канал рядом с Crypto Pay (@CryptoBot), не вместо него:
шире охват сетей/монет, свой собственный провайдер на случай проблем с первым.

Флоу (тот же принцип, что и у Crypto Pay, см. crypto_payments.py):
  1. Фронт: POST /api/v1/billing/trybit/topup/ — создаём PaymentHistory(pending)
     и инвойс в Trybit (номинал в USD, оплата принимается в широком списке крипты).
  2. Пользователь оплачивает по ссылке (invoice['link'], https://pay.trybit.com/...).
  3. Зачисление — двумя независимыми путями (оба идемпотентны по reference):
     - webhook /users/api/payment/trybit/webhook/ (подпись — JWT HS256,
       подписан TRYBIT_SECRET_KEY, токен живёт 5 минут — см. docs.trybit.com/ru/api-reference-v2/postback);
     - поллинг статуса фронтом: GET /api/v1/billing/trybit/status/ сам
       опрашивает Trybit (POST /v2/invoice/merchant/info) — работает даже
       без настроенного постбека.

Включение: TRYBIT_ENABLED=1 + TRYBIT_SHOP_ID/TRYBIT_API_KEY/TRYBIT_SECRET_KEY
в .env. При выключенном флаге фронт скрывает блок оплаты (через /api/v1/billing/trybit/).
"""
import logging

import jwt
import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15


class TrybitError(Exception):
    """Ошибка обращения к Trybit API."""


def trybit_enabled() -> bool:
    return bool(
        getattr(settings, 'TRYBIT_ENABLED', False)
        and settings.TRYBIT_SHOP_ID and settings.TRYBIT_API_KEY and settings.TRYBIT_SECRET_KEY
    )


def _api_call(method: str, params: dict) -> dict:
    url = f"{settings.TRYBIT_API_URL}/{method}"
    try:
        response = requests.post(
            url,
            json=params,
            headers={'Authorization': f'Token {settings.TRYBIT_API_KEY}'},
            timeout=REQUEST_TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        raise TrybitError(f"Trybit API недоступен: {e}") from e
    if data.get('status') != 'success':
        raise TrybitError(f"Trybit API error: {data}")
    return data.get('result')


def create_invoice(amount_usd, order_id: str) -> dict:
    """
    Создаёт инвойс (номинал в USD). Возвращает result из POST /v2/invoice/create:
    uuid (INV-XXXXXXXX), link (https://pay.trybit.com/...), status, ...
    """
    return _api_call('v2/invoice/create', {
        'shop_id': settings.TRYBIT_SHOP_ID,
        'amount': float(amount_usd),
        'currency': 'USD',
        'order_id': order_id,
    })


def get_invoice_info(uuid: str) -> dict | None:
    result = _api_call('v2/invoice/merchant/info', {'uuids': [uuid]})
    items = result if isinstance(result, list) else []
    return items[0] if items else None


def _verify_postback_token(token: str) -> bool:
    """
    Постбек подписан JWT (HS256, TRYBIT_SECRET_KEY, живёт 5 минут) —
    см. docs.trybit.com/ru/api-reference-v2/postback.
    """
    if not token:
        return False
    try:
        jwt.decode(token, settings.TRYBIT_SECRET_KEY, algorithms=['HS256'])
        return True
    except jwt.PyJWTError as e:
        logger.warning("[TRYBIT] Неверный/просроченный токен постбека: %s", e)
        return False


def settle_trybit_payment(payment) -> bool:
    """
    Проводит оплаченный крипто-платёж: статус success + начисление баланса.
    Идемпотентна: атомарный гейт по статусу + add_kopecks с reference.
    Вызывается и вебхуком, и поллингом статуса.
    """
    from users.models import PaymentHistory

    claimed = PaymentHistory.objects.filter(pk=payment.pk).exclude(status='success').update(
        status='success', paid_at=timezone.now(),
    )
    if not claimed:
        return False
    payment.refresh_from_db(fields=['status', 'paid_at'])

    user = payment.user
    topup_kopecks = payment.amount_kopecks or (payment.pages_count * 100)
    user.add_kopecks(topup_kopecks, type='topup', reference=f'trybit:{payment.payment_id}')
    user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
    logger.info(
        "[TRYBIT] Пользователь %s пополнил баланс на %s коп. (инвойс %s)",
        user.email, topup_kopecks, payment.payment_id,
    )

    try:
        from telegram_bot.notify import notify_user
        from telegram_bot.i18n import t, resolve_language
        from core.money import format_money
        tg = getattr(user, 'telegram', None)
        if tg:
            lang = resolve_language(tg, None)
            if lang == 'ru':
                text = (
                    f"<b>Оплата криптовалютой прошла успешно!</b>\n\n"
                    f"Начислено: <b>{format_money(topup_kopecks)}</b>\n"
                    f"Баланс: <b>{format_money(user.balance_kopecks)}</b>"
                )
            else:
                text = (
                    f"<b>{t('crypto.paidTitle', lang)}</b>\n\n"
                    f"{t('crypto.credited', lang)}: <b>{format_money(topup_kopecks)}</b>\n"
                    f"{t('crypto.balance', lang)}: <b>{format_money(user.balance_kopecks)}</b>"
                )
            notify_user(tg.telegram_id, text)
    except Exception as tg_err:
        logger.warning("[TRYBIT] Telegram notify failed: %s", tg_err)
    return True


def check_and_settle(payment) -> str:
    """
    Опрашивает Trybit по инвойсу pending-платежа и проводит/закрывает его.
    Возвращает актуальный статус PaymentHistory.
    """
    from users.models import PaymentHistory

    if payment.status != 'pending' or not payment.payment_id:
        return payment.status
    try:
        invoice = get_invoice_info(payment.payment_id)
    except TrybitError as e:
        logger.warning("[TRYBIT] Проверка инвойса %s не удалась: %s", payment.payment_id, e)
        return payment.status
    if invoice is None:
        return payment.status
    inv_status = invoice.get('status')
    if inv_status in ('paid', 'overpaid'):
        settle_trybit_payment(payment)
        return 'success'
    if inv_status == 'canceled':
        PaymentHistory.objects.filter(pk=payment.pk, status='pending').update(status='failed')
        return 'failed'
    return payment.status


@csrf_exempt
@require_POST
def trybit_webhook(request):
    """POST /users/api/payment/trybit/webhook/ — постбек об оплате от Trybit."""
    from users.models import PaymentHistory

    if not trybit_enabled():
        return HttpResponseForbidden('disabled')

    try:
        import json
        update = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)

    token = update.get('token', '')
    if not _verify_postback_token(token):
        logger.warning("[TRYBIT] Постбек с неверной подписью (ip=%s)", request.META.get('REMOTE_ADDR'))
        return HttpResponseForbidden('bad signature')

    if update.get('status') != 'success':
        return JsonResponse({'ok': True})

    invoice_id = str(update.get('invoice_id') or '')
    order_id = update.get('order_id')  # наш PaymentHistory.id, положенный при создании

    payment = None
    if order_id:
        payment = PaymentHistory.objects.filter(pk=order_id, payment_method='trybit').first()
    if payment is None and invoice_id:
        payment = PaymentHistory.objects.filter(payment_id__icontains=invoice_id, payment_method='trybit').first()
    if payment is None:
        logger.error("[TRYBIT] Постбек по неизвестному инвойсу %s (order_id=%s)", invoice_id, order_id)
        return JsonResponse({'ok': True})

    settle_trybit_payment(payment)
    return JsonResponse({'ok': True})
