"""
Оплата криптовалютой (Crypto Pay / @CryptoBot):
  GET  /api/v1/billing/crypto/                     — доступность канала + лимиты
  POST /api/v1/billing/crypto/topup/               — создать крипто-инвойс на пополнение
  GET  /api/v1/billing/crypto/status/{payment_id}/ — статус платежа (поллинг фронтом;
                                                     сам опрашивает Crypto Pay — зачисление
                                                     работает даже без вебхука)
"""
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from users.models import PaymentHistory, PageSaleSettings
from users.crypto_payments import (
    CryptoPayError, check_and_settle, create_invoice, crypto_pay_enabled,
)

logger = logging.getLogger(__name__)


class CryptoConfigView(APIView):
    """GET /api/v1/billing/crypto/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Доступность оплаты криптовалютой', tags=['Billing'])
    def get(self, request):
        s = PageSaleSettings.get_settings()
        enabled = crypto_pay_enabled() and s.is_active
        return Response({
            'enabled': enabled,
            'assets': [a.strip() for a in settings.CRYPTO_PAY_ASSETS.split(',') if a.strip()],
            'min_amount': s.min_pages_for_purchase,
            'max_amount': s.max_pages_for_purchase,
        })


class CryptoTopupView(APIView):
    """POST /api/v1/billing/crypto/topup/  body: {"amount": 500}  (рубли)"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Создать крипто-инвойс на пополнение', tags=['Billing'])
    def post(self, request):
        if not crypto_pay_enabled():
            return Response({'error': {'message': 'Оплата криптовалютой отключена', 'type': 'unavailable', 'code': 'crypto_disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        s = PageSaleSettings.get_settings()
        if not s.is_active:
            return Response({'error': {'message': 'Пополнение баланса временно недоступно', 'type': 'unavailable', 'code': 'disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            amount = int(request.data.get('amount', 0))
        except (TypeError, ValueError):
            amount = 0
        if amount < s.min_pages_for_purchase or amount > s.max_pages_for_purchase:
            return Response({'error': {'message': f'Сумма должна быть от {s.min_pages_for_purchase} до {s.max_pages_for_purchase} ₽', 'type': 'invalid_request_error', 'code': 'invalid_amount'}}, status=status.HTTP_400_BAD_REQUEST)

        price = float(s.price_per_page) * amount
        description = f"Пополнение баланса aineron.ru на {amount} ₽"

        from core.money import rub_to_kopecks
        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            payment_method='crypto',
            invoice_id=f'crypto-pending-{request.user.id}',
            amount=price,
            amount_kopecks=rub_to_kopecks(price),
            pages_count=amount,
            status='pending',
            description=description,
        )

        try:
            invoice = create_invoice(price, description, payload=str(payment.id))
        except CryptoPayError as e:
            payment.status = 'failed'
            payment.save(update_fields=['status', 'updated_at'])
            logger.error("[CRYPTO] Не удалось создать инвойс: %s", e)
            return Response({'error': {'message': 'Не удалось создать счёт. Попробуйте позже.', 'type': 'provider_error', 'code': 'crypto_invoice_failed'}}, status=status.HTTP_502_BAD_GATEWAY)

        payment.payment_id = str(invoice['invoice_id'])
        payment.invoice_id = f"crypto-{invoice['invoice_id']}"
        payment.save(update_fields=['payment_id', 'invoice_id', 'updated_at'])

        return Response({
            'payment_id': payment.id,
            'invoice_id': invoice['invoice_id'],
            'amount': f"{price:.2f}",
            'pay_url': invoice.get('bot_invoice_url'),
            'web_url': invoice.get('web_app_invoice_url') or invoice.get('mini_app_invoice_url'),
            'expires_in': 1800,
        })


class CryptoStatusView(APIView):
    """GET /api/v1/billing/crypto/status/{payment_id}/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Статус крипто-платежа', tags=['Billing'])
    def get(self, request, payment_id):
        try:
            payment = PaymentHistory.objects.get(
                id=payment_id, user=request.user, payment_method='crypto',
            )
        except PaymentHistory.DoesNotExist:
            return Response({'error': {'message': 'Payment not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)

        current = check_and_settle(payment)
        request.user.refresh_from_db(fields=['balance_kopecks'])
        return Response({
            'payment_id': payment.id,
            'status': current,
            'balance_kopecks': request.user.balance_kopecks,
        })
