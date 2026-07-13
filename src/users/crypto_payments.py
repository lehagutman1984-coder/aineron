"""
Оплата криптовалютой через Crypto Pay API (@CryptoBot, https://help.crypt.bot/crypto-pay-api).

Флоу:
  1. Фронт: POST /api/v1/billing/crypto/topup/ — создаём PaymentHistory(pending)
     и инвойс в Crypto Pay (фиатный номинал в RUB, оплата в USDT/TON).
  2. Пользователь оплачивает по ссылке в @CryptoBot.
  3. Зачисление — двумя независимыми путями (оба идемпотентны по reference):
     - webhook /users/api/payment/crypto/webhook/ (подпись HMAC-SHA256);
     - поллинг статуса фронтом: GET /api/v1/billing/crypto/status/ сам
       опрашивает Crypto Pay — работает даже без настроенного вебхука.

Включение: CRYPTO_PAY_ENABLED=1 + CRYPTO_PAY_TOKEN в .env. При выключенном
флаге фронт скрывает блок оплаты (флаг отдаётся через /api/v1/billing/crypto/).
"""
import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15


class CryptoPayError(Exception):
    """Ошибка обращения к Crypto Pay API."""


def crypto_pay_enabled() -> bool:
    return bool(getattr(settings, 'CRYPTO_PAY_ENABLED', False) and settings.CRYPTO_PAY_TOKEN)


def _api_call(method: str, params: dict | None = None) -> dict:
    url = f"{settings.CRYPTO_PAY_API_URL}/{method}"
    try:
        response = requests.post(
            url,
            json=params or {},
            headers={'Crypto-Pay-API-Token': settings.CRYPTO_PAY_TOKEN},
            timeout=REQUEST_TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        raise CryptoPayError(f"Crypto Pay API недоступен: {e}") from e
    if not data.get('ok'):
        raise CryptoPayError(f"Crypto Pay API error: {data.get('error')}")
    return data['result']


def create_invoice(amount, description: str, payload: str, fiat: str = 'RUB') -> dict:
    """
    Создаёт фиатный инвойс (номинал в RUB или USD, оплата принимается в крипте).
    Возвращает объект Invoice: invoice_id, bot_invoice_url, web_app_invoice_url...
    """
    return _api_call('createInvoice', {
        'currency_type': 'fiat',
        'fiat': fiat,
        'amount': f"{float(amount):.2f}",
        'accepted_assets': settings.CRYPTO_PAY_ASSETS,
        'description': description[:1024],
        'payload': payload,
        'expires_in': 1800,  # 30 минут — фиксируем рублёвый номинал на время оплаты
    })


def get_invoice(invoice_id: str) -> dict | None:
    result = _api_call('getInvoices', {'invoice_ids': str(invoice_id)})
    items = result.get('items') or []
    return items[0] if items else None


def settle_crypto_payment(payment) -> bool:
    """
    Проводит оплаченный крипто-платёж: статус success + начисление баланса.
    Идемпотентна: атомарный гейт по статусу (как в Robokassa payment_success)
    + add_kopecks с reference. Вызывается и вебхуком, и поллингом статуса.
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
    user.add_kopecks(topup_kopecks, type='topup', reference=f'crypto:{payment.payment_id}')
    user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
    logger.info(
        "[CRYPTO] Пользователь %s пополнил баланс на %s коп. (инвойс %s)",
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
        logger.warning("[CRYPTO] Telegram notify failed: %s", tg_err)
    return True


def check_and_settle(payment) -> str:
    """
    Опрашивает Crypto Pay по инвойсу pending-платежа и проводит/закрывает его.
    Возвращает актуальный статус PaymentHistory.
    """
    from users.models import PaymentHistory

    if payment.status != 'pending' or not payment.payment_id:
        return payment.status
    try:
        invoice = get_invoice(payment.payment_id)
    except CryptoPayError as e:
        logger.warning("[CRYPTO] Проверка инвойса %s не удалась: %s", payment.payment_id, e)
        return payment.status
    if invoice is None:
        return payment.status
    if invoice.get('status') == 'paid':
        settle_crypto_payment(payment)
        return 'success'
    if invoice.get('status') == 'expired':
        PaymentHistory.objects.filter(pk=payment.pk, status='pending').update(status='failed')
        return 'failed'
    return payment.status


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = hashlib.sha256(settings.CRYPTO_PAY_TOKEN.encode()).digest()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or '')


@csrf_exempt
@require_POST
def crypto_pay_webhook(request):
    """POST /users/api/payment/crypto/webhook/ — уведомление invoice_paid от Crypto Pay."""
    from users.models import PaymentHistory

    if not crypto_pay_enabled():
        return HttpResponseForbidden('disabled')

    signature = request.headers.get('Crypto-Pay-Api-Signature', '')
    if not _verify_webhook_signature(request.body, signature):
        logger.warning("[CRYPTO] Вебхук с неверной подписью (ip=%s)", request.META.get('REMOTE_ADDR'))
        return HttpResponseForbidden('bad signature')

    try:
        update = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)

    if update.get('update_type') != 'invoice_paid':
        return JsonResponse({'ok': True})

    invoice = update.get('payload') or {}
    invoice_id = str(invoice.get('invoice_id') or '')
    payment_pk = invoice.get('payload')  # наш PaymentHistory.id, положенный при создании

    payment = None
    if payment_pk:
        payment = PaymentHistory.objects.filter(pk=payment_pk, payment_method='crypto').first()
    if payment is None and invoice_id:
        payment = PaymentHistory.objects.filter(payment_id=invoice_id, payment_method='crypto').first()
    if payment is None:
        logger.error("[CRYPTO] Вебхук по неизвестному инвойсу %s", invoice_id)
        return JsonResponse({'ok': True})

    settle_crypto_payment(payment)
    return JsonResponse({'ok': True})
