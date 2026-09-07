"""
Оплата криптовалютой (Trybit, ex-CryptoCloud) — второй крипто-канал рядом с
Crypto Pay, см. users/trybit_payments.py:
  GET  /api/v1/billing/trybit/                     — доступность канала + лимиты
  POST /api/v1/billing/trybit/topup/                — создать инвойс на пополнение
  GET  /api/v1/billing/trybit/status/{payment_id}/  — статус платежа (поллинг фронтом;
                                                      сам опрашивает Trybit — зачисление
                                                      работает даже без постбека)
"""
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from users.models import PaymentHistory, PageSaleSettings
from users.trybit_payments import (
    TrybitError, check_and_settle, create_invoice, trybit_enabled,
)

logger = logging.getLogger(__name__)

# Лимиты пополнения в USD (тот же диапазон, что и у Crypto Pay в USD-режиме)
USD_MIN = 1
USD_MAX = 1000


class TrybitConfigView(APIView):
    """GET /api/v1/billing/trybit/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Доступность оплаты через Trybit', tags=['Billing'])
    def get(self, request):
        s = PageSaleSettings.get_settings()
        enabled = trybit_enabled() and s.is_active
        return Response({
            'enabled': enabled,
            'min_amount': USD_MIN,
            'max_amount': USD_MAX,
        })


class TrybitTopupView(APIView):
    """POST /api/v1/billing/trybit/topup/  body: {"amount_usd": 10}"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Создать инвойс Trybit на пополнение', tags=['Billing'])
    def post(self, request):
        if not trybit_enabled():
            return Response({'error': {'message': 'Оплата через Trybit отключена', 'type': 'unavailable', 'code': 'trybit_disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        s = PageSaleSettings.get_settings()
        if not s.is_active:
            return Response({'error': {'message': 'Пополнение баланса временно недоступно', 'type': 'unavailable', 'code': 'disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from django.conf import settings as dj_settings

        try:
            amount_usd = float(request.data.get('amount_usd', 0))
        except (TypeError, ValueError):
            amount_usd = 0
        if amount_usd < USD_MIN or amount_usd > USD_MAX:
            return Response({'error': {'message': f'Amount must be between ${USD_MIN} and ${USD_MAX}', 'type': 'invalid_request_error', 'code': 'invalid_amount'}}, status=status.HTTP_400_BAD_REQUEST)

        price = round(amount_usd, 2)
        credit_kopecks = int(round(price * dj_settings.INTL_KOPECKS_PER_USD))
        description = f"aineron.net balance top-up: {credit_kopecks:,} credits (${price:g})"

        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            payment_method='trybit',
            invoice_id=f'trybit-pending-{request.user.id}',
            amount=price,
            amount_kopecks=credit_kopecks,
            pages_count=credit_kopecks // 100,
            status='pending',
            description=description,
        )

        try:
            invoice = create_invoice(price, order_id=str(payment.id))
        except TrybitError as e:
            payment.status = 'failed'
            payment.save(update_fields=['status', 'updated_at'])
            logger.error("[TRYBIT] Не удалось создать инвойс: %s", e)
            return Response({'error': {'message': 'Не удалось создать счёт. Попробуйте позже.', 'type': 'provider_error', 'code': 'trybit_invoice_failed'}}, status=status.HTTP_502_BAD_GATEWAY)

        payment.payment_id = str(invoice['uuid'])
        payment.invoice_id = str(invoice['uuid'])
        payment.save(update_fields=['payment_id', 'invoice_id', 'updated_at'])

        return Response({
            'payment_id': payment.id,
            'invoice_id': invoice['uuid'],
            'amount': f"{price:.2f}",
            'currency': 'USD',
            'credits': credit_kopecks,
            'pay_url': invoice.get('link'),
            'test_mode': invoice.get('test_mode'),
        })


class TrybitStatusView(APIView):
    """GET /api/v1/billing/trybit/status/{payment_id}/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Статус платежа Trybit', tags=['Billing'])
    def get(self, request, payment_id):
        try:
            payment = PaymentHistory.objects.get(
                id=payment_id, user=request.user, payment_method='trybit',
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
