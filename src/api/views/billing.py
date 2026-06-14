"""
Billing API для Next.js:
  GET  /api/v1/billing/tariffs/        — список тарифов + текущий статус подписки
  POST /api/v1/billing/tariffs/{id}/pay/ — создать платёж через Robokassa
  GET  /api/v1/billing/pages/          — настройки покупки звёзд
  POST /api/v1/billing/pages/buy/      — купить звёзды
  GET  /api/v1/billing/history/        — история платежей
  POST /api/v1/billing/promo/          — применить промокод
  GET  /api/v1/billing/stars-usage/    — аналитика трат звёзд (по дням + по моделям)
"""
import hashlib
import json
import logging
import random
import re
import time
from datetime import timedelta

from django.conf import settings
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from users.models import Tariff, PaymentHistory, PageSaleSettings, PromoCode, UsedPromoCode, UserSpending
from api.serializers.billing import (
    TariffSerializer, PaymentHistorySerializer,
    PageSaleSettingsSerializer, UserSubscriptionSerializer,
)

logger = logging.getLogger(__name__)


def _make_invoice_id() -> int:
    return int(time.time() * 1000) % 10_000_000 + random.randint(1, 999)


def _robokassa_signature(merchant_login, out_sum, inv_id, receipt_json, password1) -> str:
    sig_str = f"{merchant_login}:{out_sum}:{inv_id}:{receipt_json}:{password1}"
    return hashlib.md5(sig_str.encode('cp1251')).hexdigest()


class TariffListView(APIView):
    """GET /api/v1/billing/tariffs/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Список тарифов', tags=['Billing'])
    def get(self, request):
        tariffs = Tariff.objects.filter(is_active=True).order_by('price')
        user = request.user
        subscription = None
        if hasattr(user, 'active_subscription') and user.active_subscription:
            subscription = UserSubscriptionSerializer(user.active_subscription).data
        return Response({
            'tariffs': TariffSerializer(tariffs, many=True).data,
            'current_subscription': subscription,
            'pages_count': user.pages_count,
        })


class TariffPayView(APIView):
    """POST /api/v1/billing/tariffs/{id}/pay/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Создать платёж (Robokassa)', tags=['Billing'],
                   description='Возвращает параметры формы Robokassa. Фронтенд сам отправляет форму.')
    def post(self, request, tariff_id):
        try:
            tariff = Tariff.objects.get(id=tariff_id, is_active=True, is_free=False)
        except Tariff.DoesNotExist:
            return Response({'error': {'message': 'Tariff not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)

        merchant_login = settings.ROBOKASSA_LOGIN
        password1 = settings.ROBOKASSA_PASS1
        inv_id = _make_invoice_id()
        out_sum = f"{float(tariff.price):.2f}"
        description = f"Тариф {tariff.display_name}"

        receipt_data = {
            "items": [{
                "name": tariff.display_name[:128],
                "quantity": 1,
                "sum": float(tariff.price),
                "tax": "none",
            }]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
        signature = _robokassa_signature(merchant_login, out_sum, inv_id, receipt_json, password1)

        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='subscription',
            tariff=tariff,
            invoice_id=str(inv_id),
            amount=tariff.price,
            pages_count=tariff.pages_count,
            status='pending',
            description=description,
        )

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        return Response({
            'payment_id': payment.id,
            'invoice_id': inv_id,
            'form': {
                'action': 'https://auth.robokassa.ru/Merchant/Index.aspx',
                'method': 'POST',
                'fields': {
                    'MerchantLogin': merchant_login,
                    'OutSum': out_sum,
                    'InvId': str(inv_id),
                    'Description': description,
                    'SignatureValue': signature,
                    'IsTest': str(getattr(settings, 'ROBOKASSA_TEST_MODE', 0)),
                    'Culture': 'ru',
                    'Encoding': 'utf-8',
                    'SuccessURL': f"{site_url}/payment-success/",
                    'FailURL': f"{site_url}/users/pages/payment-fail/",
                    'Recurring': 'true',
                    'Receipt': receipt_json,
                },
            },
        })


class PageSaleSettingsView(APIView):
    """GET /api/v1/billing/pages/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Настройки покупки звёзд', tags=['Billing'])
    def get(self, request):
        s = PageSaleSettings.get_settings()
        return Response(PageSaleSettingsSerializer(s).data)


class BuyPagesView(APIView):
    """POST /api/v1/billing/pages/buy/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Купить звёзды (Robokassa)', tags=['Billing'])
    def post(self, request):
        pages = int(request.data.get('pages', 0))
        s = PageSaleSettings.get_settings()
        if not s.is_active:
            return Response({'error': {'message': 'Star purchases are disabled', 'type': 'unavailable', 'code': 'disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if pages < s.min_pages_for_purchase or pages > s.max_pages_for_purchase:
            return Response({'error': {'message': f'Pages must be between {s.min_pages_for_purchase} and {s.max_pages_for_purchase}', 'type': 'invalid_request_error', 'code': 'invalid_pages'}}, status=status.HTTP_400_BAD_REQUEST)

        price = float(s.price_per_page) * pages
        merchant_login = settings.ROBOKASSA_LOGIN
        password1 = settings.ROBOKASSA_PASS1
        inv_id = _make_invoice_id()
        out_sum = f"{price:.2f}"
        description = f"Покупка {pages} звёзд"

        receipt_data = {
            "items": [{
                "name": f"Звёзды ({pages} шт.)",
                "quantity": 1,
                "sum": price,
                "tax": "none",
            }]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
        signature = _robokassa_signature(merchant_login, out_sum, inv_id, receipt_json, password1)

        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            invoice_id=str(inv_id),
            amount=price,
            pages_count=pages,
            status='pending',
            description=description,
        )

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        return Response({
            'payment_id': payment.id,
            'invoice_id': inv_id,
            'form': {
                'action': 'https://auth.robokassa.ru/Merchant/Index.aspx',
                'method': 'POST',
                'fields': {
                    'MerchantLogin': merchant_login,
                    'OutSum': out_sum,
                    'InvId': str(inv_id),
                    'Description': description,
                    'SignatureValue': signature,
                    'IsTest': str(getattr(settings, 'ROBOKASSA_TEST_MODE', 0)),
                    'Culture': 'ru',
                    'Encoding': 'utf-8',
                    'SuccessURL': f"{site_url}/payment-success/",
                    'FailURL': f"{site_url}/users/pages/payment-fail/",
                    'Receipt': receipt_json,
                },
            },
        })


class PaymentHistoryView(APIView):
    """GET /api/v1/billing/history/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='История платежей', tags=['Billing'])
    def get(self, request):
        payments = PaymentHistory.objects.filter(
            user=request.user,
            status__in=['success', 'pending'],
        ).select_related('tariff').order_by('-created_at')[:50]
        return Response(PaymentHistorySerializer(payments, many=True).data)


class ApplyPromoView(APIView):
    """POST /api/v1/billing/promo/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Применить промокод', tags=['Billing'])
    def post(self, request):
        code_str = (request.data.get('code') or '').strip().upper()
        if not code_str:
            return Response({'error': {'message': 'Promo code is required', 'type': 'invalid_request_error', 'code': 'missing_code'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code=code_str)
        except PromoCode.DoesNotExist:
            return Response({'error': {'message': 'Промокод не найден', 'type': 'invalid_request_error', 'code': 'promo_not_found'}}, status=status.HTTP_400_BAD_REQUEST)

        if not promo.is_valid():
            return Response({'error': {'message': 'Промокод недействителен или истёк', 'type': 'invalid_request_error', 'code': 'promo_expired'}}, status=status.HTTP_400_BAD_REQUEST)

        if UsedPromoCode.objects.filter(user=request.user, promo_code=promo).exists():
            return Response({'error': {'message': 'Промокод уже был использован', 'type': 'invalid_request_error', 'code': 'promo_already_used'}}, status=status.HTTP_400_BAD_REQUEST)

        UsedPromoCode.objects.create(user=request.user, promo_code=promo)
        request.user.add_pages(promo.stars)
        PaymentHistory.objects.create(
            user=request.user,
            payment_type='promo',
            invoice_id=f'promo-{promo.pk}',
            amount=0,
            pages_count=promo.stars,
            status='success',
            description=f'Промокод {code_str}: +{promo.stars} звёзд',
        )

        return Response({
            'ok': True,
            'stars_added': promo.stars,
            'new_balance': request.user.pages_count,
            'message': f'Промокод принят! Начислено {promo.stars} звёзд.',
        })


class StarsUsageView(APIView):
    """GET /api/v1/billing/stars-usage/ — аналитика трат звёзд из UserSpending"""
    permission_classes = [IsAuthenticated]

    _MODEL_RE = re.compile(r' с (.+?)(?:\s*\(|$)')

    @extend_schema(summary='Аналитика трат звёзд', tags=['Billing'])
    def get(self, request):
        try:
            days = min(int(request.query_params.get('days', 30)), 90)
        except (TypeError, ValueError):
            days = 30

        now = timezone.now()
        since = now - timedelta(days=days)
        prev_since = since - timedelta(days=days)

        qs = UserSpending.objects.filter(user=request.user, created_at__gte=since)
        prev_qs = UserSpending.objects.filter(
            user=request.user, created_at__gte=prev_since, created_at__lt=since
        )

        by_day = list(
            qs.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(stars=Sum('amount'), requests=Count('id'))
            .order_by('day')
        )

        by_desc = list(
            qs.values('description')
            .annotate(stars=Sum('amount'), requests=Count('id'))
            .order_by('-stars')[:30]
        )

        def extract_model(desc):
            m = self._MODEL_RE.search(desc)
            return m.group(1).strip() if m else desc

        by_model: dict = {}
        for row in by_desc:
            name = extract_model(row['description'])
            if name not in by_model:
                by_model[name] = {'name': name, 'stars': 0, 'requests': 0}
            by_model[name]['stars'] += row['stars'] or 0
            by_model[name]['requests'] += row['requests'] or 0

        totals = qs.aggregate(total_stars=Sum('amount'), total_requests=Count('id'))
        prev_totals = prev_qs.aggregate(total_stars=Sum('amount'), total_requests=Count('id'))

        total_stars = totals['total_stars'] or 0
        avg_per_day = round(total_stars / days, 1)

        return Response({
            'period_days': days,
            'totals': {
                'total_stars': total_stars,
                'total_requests': totals['total_requests'] or 0,
                'avg_per_day': avg_per_day,
            },
            'prev_period': {
                'total_stars': prev_totals['total_stars'] or 0,
                'total_requests': prev_totals['total_requests'] or 0,
            },
            'by_day': [
                {
                    'date': str(row['day']),
                    'stars': row['stars'] or 0,
                    'requests': row['requests'] or 0,
                }
                for row in by_day
            ],
            'by_model': sorted(by_model.values(), key=lambda x: -x['stars'])[:10],
        })
