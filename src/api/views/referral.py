import secrets
import string
from decimal import Decimal

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.authentication import CsrfExemptSessionAuthentication
from users.models import ReferralEarning, WithdrawalRequest


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
                'card_number': w.card_number,
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
        card_number = (request.data.get('card_number') or '').strip()

        if not amount_raw or not card_number:
            return Response(
                {'error': {'message': 'Укажите сумму и номер карты', 'code': 'missing_fields'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            return Response(
                {'error': {'message': 'Неверная сумма', 'code': 'invalid_amount'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {'error': {'message': 'Сумма должна быть больше нуля', 'code': 'invalid_amount'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.rub_balance < amount:
            return Response(
                {'error': {'message': 'Недостаточно средств на балансе', 'code': 'insufficient_balance'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.rub_balance -= amount
        user.save(update_fields=['rub_balance'])
        WithdrawalRequest.objects.create(user=user, amount=amount, card_number=card_number)

        return Response({'ok': True})
