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


def _discounted_price(price, percent):
    from decimal import Decimal, ROUND_HALF_UP
    return (Decimal(price) * (100 - percent) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _resolve_discount_promo(user, code_str):
    """
    Валидация скидочного промокода при оплате тарифа.
    Возвращает (promo, None) или (None, Response с ошибкой).
    """
    try:
        promo = PromoCode.objects.get(code__iexact=code_str)
    except PromoCode.DoesNotExist:
        return None, Response({'error': {'message': 'Промокод не найден', 'type': 'invalid_request_error', 'code': 'promo_not_found'}}, status=status.HTTP_400_BAD_REQUEST)
    if not promo.is_valid():
        return None, Response({'error': {'message': 'Промокод недействителен или истёк', 'type': 'invalid_request_error', 'code': 'promo_expired'}}, status=status.HTTP_400_BAD_REQUEST)
    if promo.discount_percent <= 0:
        return None, Response({'error': {'message': 'Этот промокод начисляет баланс — примените его в разделе «Промокод»', 'type': 'invalid_request_error', 'code': 'promo_not_discount'}}, status=status.HTTP_400_BAD_REQUEST)
    if UsedPromoCode.objects.filter(user=user, promo_code=promo).exists():
        return None, Response({'error': {'message': 'Промокод уже был использован', 'type': 'invalid_request_error', 'code': 'promo_already_used'}}, status=status.HTTP_400_BAD_REQUEST)
    return promo, None


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
            'balance_kopecks': user.balance_kopecks,
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

        # Скидочный промокод: снижает сумму первого платежа, кредит тарифа — полный.
        # Использование фиксируется в вебхуке после успешной оплаты.
        promo = None
        promo_code_str = (request.data.get('promo_code') or '').strip()
        if promo_code_str:
            promo, promo_error = _resolve_discount_promo(request.user, promo_code_str)
            if promo_error:
                return promo_error

        price = _discounted_price(tariff.price, promo.discount_percent) if promo else tariff.price

        merchant_login = settings.ROBOKASSA_LOGIN
        password1 = settings.ROBOKASSA_PASS1
        inv_id = _make_invoice_id()
        out_sum = f"{float(price):.2f}"
        description = f"Тариф {tariff.display_name}"
        if promo:
            description += f" (промокод −{promo.discount_percent}%)"

        receipt_data = {
            "items": [{
                "name": tariff.display_name[:128],
                "quantity": 1,
                "sum": float(price),
                "tax": "none",
            }]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
        signature = _robokassa_signature(merchant_login, out_sum, inv_id, receipt_json, password1)

        from core.money import rub_to_kopecks
        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='subscription',
            tariff=tariff,
            promo_code=promo,
            invoice_id=str(inv_id),
            amount=price,
            amount_kopecks=rub_to_kopecks(price),
            pages_count=tariff.pages_count,
            status='pending',
            description=description,
        )

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        return Response({
            'payment_id': payment.id,
            'invoice_id': inv_id,
            'amount': str(price),
            'discount_percent': promo.discount_percent if promo else 0,
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

    @extend_schema(summary='Настройки пополнения баланса', tags=['Billing'])
    def get(self, request):
        s = PageSaleSettings.get_settings()
        return Response(PageSaleSettingsSerializer(s).data)


class BuyPagesView(APIView):
    """POST /api/v1/billing/pages/buy/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Пополнить баланс (Robokassa)', tags=['Billing'])
    def post(self, request):
        pages = int(request.data.get('pages', 0))
        s = PageSaleSettings.get_settings()
        if not s.is_active:
            return Response({'error': {'message': 'Пополнение баланса временно недоступно', 'type': 'unavailable', 'code': 'disabled'}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if pages < s.min_pages_for_purchase or pages > s.max_pages_for_purchase:
            return Response({'error': {'message': f'Pages must be between {s.min_pages_for_purchase} and {s.max_pages_for_purchase}', 'type': 'invalid_request_error', 'code': 'invalid_pages'}}, status=status.HTTP_400_BAD_REQUEST)

        price = float(s.price_per_page) * pages
        merchant_login = settings.ROBOKASSA_LOGIN
        password1 = settings.ROBOKASSA_PASS1
        inv_id = _make_invoice_id()
        out_sum = f"{price:.2f}"
        description = f"Пополнение баланса на {pages} ₽"

        receipt_data = {
            "items": [{
                "name": f"Пополнение баланса ({pages} ₽)",
                "quantity": 1,
                "sum": price,
                "tax": "none",
            }]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
        signature = _robokassa_signature(merchant_login, out_sum, inv_id, receipt_json, password1)

        from core.money import rub_to_kopecks
        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            invoice_id=str(inv_id),
            amount=price,
            amount_kopecks=rub_to_kopecks(price),
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
        code_str = (request.data.get('code') or '').strip()
        if not code_str:
            return Response({'error': {'message': 'Promo code is required', 'type': 'invalid_request_error', 'code': 'missing_code'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code__iexact=code_str)
        except PromoCode.DoesNotExist:
            return Response({'error': {'message': 'Промокод не найден', 'type': 'invalid_request_error', 'code': 'promo_not_found'}}, status=status.HTTP_400_BAD_REQUEST)

        if not promo.is_valid():
            return Response({'error': {'message': 'Промокод недействителен или истёк', 'type': 'invalid_request_error', 'code': 'promo_expired'}}, status=status.HTTP_400_BAD_REQUEST)

        if promo.discount_percent > 0:
            return Response({'error': {'message': f'Это скидочный промокод (−{promo.discount_percent}% на тариф) — введите его при покупке тарифа', 'type': 'invalid_request_error', 'code': 'promo_is_discount'}}, status=status.HTTP_400_BAD_REQUEST)

        # Фиксируем использование ДО начисления: unique (user, promo_code)
        # гасит гонку двойного применения (как в legacy users/views.py)
        from django.db import IntegrityError
        from django.db.models import F
        try:
            UsedPromoCode.objects.create(user=request.user, promo_code=promo)
        except IntegrityError:
            return Response({'error': {'message': 'Промокод уже был использован', 'type': 'invalid_request_error', 'code': 'promo_already_used'}}, status=status.HTTP_400_BAD_REQUEST)
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F('used_count') + 1)
        request.user.add_kopecks(promo.kopecks, type='promo', reference=f'promo:{promo.pk}:{request.user.id}')
        PaymentHistory.objects.create(
            user=request.user,
            payment_type='promo',
            invoice_id=f'promo-{promo.pk}',
            amount=0,
            amount_kopecks=0,
            pages_count=promo.stars,
            status='success',
            description=f'Промокод {code_str}: +{promo.stars} ₽',
        )

        from core.money import format_rub
        return Response({
            'ok': True,
            'stars_added': promo.stars,
            'kopecks_added': promo.kopecks,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
            'message': f'Промокод принят! Начислено {format_rub(promo.kopecks)}.',
        })


class PromoCheckView(APIView):
    """
    POST /api/v1/billing/promo/check/ — проверить промокод перед оплатой.
    body: {"code": "...", "tariff_id": 3}  (tariff_id опционален)
    Ничего не списывает и не фиксирует — только валидация и расчёт цены.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Проверить промокод', tags=['Billing'])
    def post(self, request):
        code_str = (request.data.get('code') or '').strip()
        if not code_str:
            return Response({'error': {'message': 'Promo code is required', 'type': 'invalid_request_error', 'code': 'missing_code'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code__iexact=code_str)
        except PromoCode.DoesNotExist:
            return Response({'error': {'message': 'Промокод не найден', 'type': 'invalid_request_error', 'code': 'promo_not_found'}}, status=status.HTTP_400_BAD_REQUEST)

        if not promo.is_valid():
            return Response({'error': {'message': 'Промокод недействителен или истёк', 'type': 'invalid_request_error', 'code': 'promo_expired'}}, status=status.HTTP_400_BAD_REQUEST)

        if UsedPromoCode.objects.filter(user=request.user, promo_code=promo).exists():
            return Response({'error': {'message': 'Промокод уже был использован', 'type': 'invalid_request_error', 'code': 'promo_already_used'}}, status=status.HTTP_400_BAD_REQUEST)

        result = {
            'ok': True,
            'code': promo.code,
            'type': 'discount' if promo.discount_percent > 0 else 'balance',
            'discount_percent': promo.discount_percent,
            'kopecks': promo.kopecks,
        }
        tariff_id = request.data.get('tariff_id')
        if promo.discount_percent > 0 and tariff_id:
            try:
                tariff = Tariff.objects.get(id=tariff_id, is_active=True, is_free=False)
            except (Tariff.DoesNotExist, ValueError, TypeError):
                return Response({'error': {'message': 'Tariff not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)
            price = _discounted_price(tariff.price, promo.discount_percent)
            result['price'] = str(tariff.price)
            result['discounted_price'] = str(price)
        return Response(result)


class StarsUsageView(APIView):
    """GET /api/v1/billing/stars-usage/ — аналитика трат звёзд из UserSpending"""
    permission_classes = [IsAuthenticated]

    _MODEL_RE = re.compile(r' с (.+?)(?:\s*\(|$)')

    @extend_schema(summary='Аналитика трат', tags=['Billing'])
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
            .annotate(kopecks=Sum('amount_kopecks'), requests=Count('id'))
            .order_by('day')
        )

        by_desc = list(
            qs.values('description')
            .annotate(kopecks=Sum('amount_kopecks'), requests=Count('id'))
            .order_by('-kopecks')[:30]
        )

        def extract_model(desc):
            m = self._MODEL_RE.search(desc)
            return m.group(1).strip() if m else desc

        by_model: dict = {}
        for row in by_desc:
            name = extract_model(row['description'])
            if name not in by_model:
                by_model[name] = {'name': name, 'kopecks': 0, 'requests': 0}
            by_model[name]['kopecks'] += row['kopecks'] or 0
            by_model[name]['requests'] += row['requests'] or 0

        totals = qs.aggregate(total_kopecks=Sum('amount_kopecks'), total_requests=Count('id'))
        prev_totals = prev_qs.aggregate(total_kopecks=Sum('amount_kopecks'), total_requests=Count('id'))

        total_kopecks = totals['total_kopecks'] or 0
        avg_per_day_kopecks = round(total_kopecks / days, 1)

        for row in by_model.values():
            row['stars'] = row['kopecks'] // 100
        for row in by_day:
            row['stars'] = (row['kopecks'] or 0) // 100

        return Response({
            'period_days': days,
            'totals': {
                'total_stars': total_kopecks // 100,
                'total_kopecks': total_kopecks,
                'total_requests': totals['total_requests'] or 0,
                'avg_per_day': avg_per_day_kopecks / 100,
                'avg_per_day_kopecks': avg_per_day_kopecks,
            },
            'prev_period': {
                'total_stars': (prev_totals['total_kopecks'] or 0) // 100,
                'total_kopecks': prev_totals['total_kopecks'] or 0,
                'total_requests': prev_totals['total_requests'] or 0,
            },
            'by_day': [
                {
                    'date': str(row['day']),
                    'stars': row['stars'],
                    'kopecks': row['kopecks'] or 0,
                    'requests': row['requests'] or 0,
                }
                for row in by_day
            ],
            'by_model': sorted(by_model.values(), key=lambda x: -x['kopecks'])[:10],
        })


class SubscriptionAutoRenewView(APIView):
    """
    GET   /api/v1/billing/subscription/  — текущая подписка
    PATCH /api/v1/billing/subscription/  — включить/отключить автопродление
                                           body: {"auto_renew": true|false}

    Отключение автопродления = отмена подписки (требование Робокассы):
    последующие рекуррентные списания не производятся, доступ сохраняется
    до конца оплаченного периода.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Текущая подписка', tags=['Billing'])
    def get(self, request):
        subscription = request.user.active_subscription
        if not subscription:
            return Response({'subscription': None})
        return Response({'subscription': UserSubscriptionSerializer(subscription).data})

    @extend_schema(summary='Управление автопродлением подписки', tags=['Billing'])
    def patch(self, request):
        auto_renew = request.data.get('auto_renew')
        if not isinstance(auto_renew, bool):
            return Response(
                {'error': {'message': 'Поле auto_renew (bool) обязательно', 'type': 'invalid_request', 'code': 'invalid_request'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription = request.user.active_subscription
        if not subscription or not subscription.is_active:
            return Response(
                {'error': {'message': 'У вас нет активной подписки', 'type': 'invalid_request', 'code': 'no_subscription'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.auto_renew = auto_renew
        subscription.save(update_fields=['auto_renew', 'updated_at'])
        logger.info(
            "Автопродление %s для %s (подписка %s)",
            'включено' if auto_renew else 'отключено', request.user.email, subscription.id,
        )
        return Response({
            'success': True,
            'auto_renew': subscription.auto_renew,
            'message': 'Автопродление включено' if auto_renew else 'Автопродление отключено. Тариф будет активен до конца оплаченного периода.',
            'subscription': UserSubscriptionSerializer(subscription).data,
        })
