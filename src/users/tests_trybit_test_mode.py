"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 12):
регрессионный тест на guard test_mode в users.trybit_payments.check_and_settle —
инвойс, помеченный провайдером как test_mode=true, не должен зачисляться как
настоящий платёж.

Запуск: python manage.py test users.tests_trybit_test_mode
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from users.models import PaymentHistory
from users import trybit_payments

User = get_user_model()


def make_user(email='trybit@test.ru'):
    user = User.objects.create(email=email, username=email.split('@')[0])
    User.objects.filter(pk=user.pk).update(balance_kopecks=0)
    user.refresh_from_db()
    return user


def make_payment(user, payment_id='INV-TEST1'):
    return PaymentHistory.objects.create(
        user=user, payment_type='pages', payment_method='trybit',
        invoice_id=f'trybit-pending-{user.id}', payment_id=payment_id,
        amount='1.00', amount_kopecks=10000, pages_count=100,
        status='pending',
    )


class TrybitTestModeGuardTests(TestCase):
    def test_test_mode_invoice_not_credited(self):
        user = make_user()
        payment = make_payment(user)
        with mock.patch.object(
            trybit_payments, 'get_invoice_info',
            return_value={'status': 'paid', 'test_mode': True},
        ):
            status = trybit_payments.check_and_settle(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(status, 'pending')
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(user.balance_kopecks, 0)

    def test_real_invoice_still_credited(self):
        user = make_user('trybit2@test.ru')
        payment = make_payment(user, 'INV-TEST2')
        with mock.patch.object(
            trybit_payments, 'get_invoice_info',
            return_value={'status': 'paid', 'test_mode': False},
        ):
            status = trybit_payments.check_and_settle(payment)
        payment.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(status, 'success')
        self.assertEqual(payment.status, 'success')
        self.assertEqual(user.balance_kopecks, 10000)

    @override_settings(TRYBIT_ALLOW_TEST_PAYMENTS=True)
    def test_explicit_override_flag_allows_test_mode_credit(self):
        user = make_user('trybit3@test.ru')
        payment = make_payment(user, 'INV-TEST3')
        with mock.patch.object(
            trybit_payments, 'get_invoice_info',
            return_value={'status': 'paid', 'test_mode': True},
        ):
            status = trybit_payments.check_and_settle(payment)
        payment.refresh_from_db()
        self.assertEqual(status, 'success')
        self.assertEqual(payment.status, 'success')
