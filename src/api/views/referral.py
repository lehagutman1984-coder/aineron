import secrets
import string
from decimal import Decimal

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.authentication import CsrfExemptSessionAuthentication
from users.models import CustomUser, ReferralEarning, WithdrawalRequest


class ReferralView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not user.referral_code:
            alphabet = string.ascii_uppercase + string.digits
            user.referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))
            user.save(update_fields=['referral_code'])

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        referral_link = f"{site_url}/?ref={user.referral_code}"

        if user.can_convert_to_rub:
            balance = float(user.rub_balance)
            balance_type = 'rub'
        else:
            balance = user.pages_count
            balance_type = 'stars'
        balance_kopecks = user.balance_kopecks if not user.can_convert_to_rub else None

        earnings_qs = ReferralEarning.objects.filter(user=user).order_by('-created_at')[:50]
        earnings = [
            {
                'id': e.id,
                'amount_rub': float(e.amount_rub),
                'amount_stars': e.amount_stars,
                'tariff': e.tariff.display_name if e.tariff else None,
                'description': e.description,
                'created_at': e.created_at.isoformat(),
            }
            for e in earnings_qs
        ]

        withdrawals_qs = WithdrawalRequest.objects.filter(user=user).order_by('-created_at')[:50]
        withdrawals = [
            {
                'id': w.id,
                'amount': float(w.amount),
                'payout_destination': w.payout_destination,
                'status': w.status,
                'created_at': w.created_at.isoformat(),
                'processed_at': w.processed_at.isoformat() if w.processed_at else None,
                'note': w.note,
            }
            for w in withdrawals_qs
        ]

        return Response({
            'referral_link': referral_link,
            'referral_code': user.referral_code,
            'referral_clicks': user.referral_clicks,
            'balance': balance,
            'balance_kopecks': balance_kopecks,
            'balance_type': balance_type,
            'can_withdraw': user.can_convert_to_rub and user.rub_balance > 0,
            'earnings': earnings,
            'withdrawals': withdrawals,
        })


class ReferralWithdrawView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not user.can_convert_to_rub:
            return Response(
                {'error': {'message': 'Вывод недоступен для вашего аккаунта', 'code': 'not_allowed'}},
                status=status.HTTP_403_FORBIDDEN,
            )

        amount_raw = request.data.get('amount')
        payout_destination = (request.data.get('payout_destination') or '').strip()
        password = request.data.get('password') or ''

        if not amount_raw or not payout_destination or not password:
            return Response(
                {'error': {'message': 'Укажите сумму, реквизиты и пароль для вывода', 'code': 'missing_fields'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2026-10-01 (аудит безопасности, MEDIUM, №18): этот вью сознательно на
        # CsrfExemptSessionAuthentication, как и весь остальной DRF API в
        # проекте (см. authentication.py) — переводить ТОЛЬКО этот эндпоинт на
        # настоящий CSRF-токен сломал бы его без парной правки фронта (нигде
        # в проекте CSRF-токен сейчас не читается/не отправляется). У этого
        # конкретного вью риск выше обычного — реквизиты выплаты (куда уйдут
        # деньги) полностью задаёт тело запроса, а не фиксированная платёжная
        # система, т.е. same-site-контент с курсом жертвы мог бы увести весь
        # rub_balance на свой кошелёк одним POST. Требуем текущий пароль — тот
        # же паттерн, что уже есть у PasswordChangeView, и он защищает даже от
        # того, что CSRF-токен сам по себе не закрыл бы (same-origin JS может
        # прочитать non-HttpOnly csrf-куку, но не знает пароль пользователя).
        if not user.check_password(password):
            return Response(
                {'error': {'message': 'Неверный пароль', 'code': 'invalid_password'}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            return Response(
                {'error': {'message': 'Неверная сумма', 'code': 'invalid_amount'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # NaN/Infinity: Decimal('NaN') <= 0 бросает InvalidOperation (500) - отсекаем до сравнений.
        if not amount.is_finite() or amount <= 0:
            return Response(
                {'error': {'message': 'Сумма должна быть больше нуля', 'code': 'invalid_amount'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not amount.is_finite():
            return Response(
                {'error': {'message': 'Неверная сумма', 'code': 'invalid_amount'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Атомарное условное списание: read-modify-write давал двойной вывод при
        # параллельных запросах (оба видели старый баланс).
        from django.db import transaction
        from django.db.models import F
        with transaction.atomic():
            updated = CustomUser.objects.filter(
                pk=user.pk, rub_balance__gte=amount,
            ).update(rub_balance=F('rub_balance') - amount)
            if not updated:
                return Response(
                    {'error': {'message': 'Недостаточно средств на балансе', 'code': 'insufficient_balance'}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            WithdrawalRequest.objects.create(user=user, amount=amount, payout_destination=payout_destination)

        return Response({'ok': True})
