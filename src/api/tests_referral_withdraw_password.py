"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 18):
регрессионный тест — вывод реферальных денег требует текущий пароль
(CsrfExemptSessionAuthentication остаётся — так на всём API — но реквизиты
выплаты атакующий не может задать без пароля жертвы, same-site-контент
с курсом жертвы больше не уводит баланс одним POST).

Запуск: python manage.py test api.tests_referral_withdraw_password
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def _withdrawable_user(email='withdraw@t.ru', password='correct-horse-battery'):
    u = User.objects.create_user(username=email, email=email, password=password)
    u.can_convert_to_rub = True
    u.rub_balance = Decimal('500.00')
    u.save(update_fields=['can_convert_to_rub', 'rub_balance'])
    return u


class ReferralWithdrawPasswordTests(APITestCase):
    def test_withdraw_without_password_rejected(self):
        user = _withdrawable_user()
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/referral/withdraw/', {
            'amount': '100', 'payout_destination': 'attacker-wallet',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertEqual(user.rub_balance, Decimal('500.00'))

    def test_withdraw_with_wrong_password_rejected(self):
        user = _withdrawable_user()
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/referral/withdraw/', {
            'amount': '100', 'payout_destination': 'attacker-wallet', 'password': 'wrong-guess',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        user.refresh_from_db()
        self.assertEqual(user.rub_balance, Decimal('500.00'))

    def test_withdraw_with_correct_password_succeeds(self):
        user = _withdrawable_user()
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/referral/withdraw/', {
            'amount': '100', 'payout_destination': 'own-wallet', 'password': 'correct-horse-battery',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.rub_balance, Decimal('400.00'))
