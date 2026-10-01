"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 11/22):
регрессионный тест — сбой между гейтом статуса и начислением баланса (Crypto
Pay / Trybit) теперь откатывает ВСЁ, платёж остаётся pending (следующий
вебхук/поллинг повторит), а не "success без денег навсегда".

Запуск: python manage.py test users.tests_crypto_trybit_atomicity
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from users import crypto_payments, trybit_payments
from users.models import PaymentHistory

User = get_user_model()


def _user(email):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.set_kopecks(0)
    return u


def _payment(user, method, payment_id):
    return PaymentHistory.objects.create(
        user=user, payment_type='pages', payment_method=method,
        invoice_id=f'{method}-pending-{user.id}', payment_id=payment_id,
        amount='1.00', amount_kopecks=10000, status='pending',
    )


class CryptoSettleAtomicityTests(TestCase):
    def test_crash_during_credit_rolls_back_status_gate(self):
        user = _user('cryptoatomic@t.ru')
        payment = _payment(user, 'crypto', 'INV-C1')
        with mock.patch.object(User, 'add_kopecks', side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):
                crypto_payments.settle_crypto_payment(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(payment.status, 'pending')  # НЕ 'success' без денег
        self.assertEqual(user.balance_kopecks, 0)

    def test_normal_settle_still_credits(self):
        user = _user('cryptoatomic2@t.ru')
        payment = _payment(user, 'crypto', 'INV-C2')
        ok = crypto_payments.settle_crypto_payment(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(payment.status, 'success')
        self.assertEqual(user.balance_kopecks, 10000)


class TrybitSettleAtomicityTests(TestCase):
    def test_crash_during_credit_rolls_back_status_gate(self):
        user = _user('trybitatomic@t.ru')
        payment = _payment(user, 'trybit', 'INV-T1')
        with mock.patch.object(User, 'add_kopecks', side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):
                trybit_payments.settle_trybit_payment(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(user.balance_kopecks, 0)

    def test_normal_settle_still_credits(self):
        user = _user('trybitatomic2@t.ru')
        payment = _payment(user, 'trybit', 'INV-T2')
        ok = trybit_payments.settle_trybit_payment(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(payment.status, 'success')
        self.assertEqual(user.balance_kopecks, 10000)
