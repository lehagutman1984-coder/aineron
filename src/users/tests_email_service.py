"""
Проверка новых email-функций (2026-09-29): payment_confirmation.html и
password_changed_email.html реально рендерятся без ошибок шаблона и
отправляются (locmem backend, синхронно ждём daemon-поток).
"""
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core import mail

User = get_user_model()

_LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _wait_for_outbox(n, timeout=3.0):
    """Отправка идёт в daemon-потоке (см. email_service.py) — ждём, не спим вслепую."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(mail.outbox) >= n:
            return
        time.sleep(0.05)


@override_settings(EMAIL_BACKEND=_LOCMEM)
class PaymentConfirmationEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email='payer@test.ru', username='payer', balance_kopecks=15000)
        mail.outbox = []

    def test_topup_renders_and_sends(self):
        from users.email_service import send_payment_confirmation_email
        ok = send_payment_confirmation_email(
            self.user, kind='topup', amount_kopecks=10000, method='Robokassa', balance_kopecks=15000,
        )
        self.assertTrue(ok)
        _wait_for_outbox(1)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('100', msg.subject)  # 100 ₽
        self.assertEqual(msg.to, ['payer@test.ru'])
        html = msg.alternatives[0][0]
        self.assertIn('Баланс пополнен', html)
        self.assertNotIn('{{', html)  # ничего не осталось нерендеренным

    def test_subscription_renders_and_sends(self):
        from users.email_service import send_payment_confirmation_email
        ok = send_payment_confirmation_email(
            self.user, kind='subscription', amount_kopecks=50000, method='Robokassa',
            tariff_name='Pro', balance_kopecks=15000,
        )
        self.assertTrue(ok)
        _wait_for_outbox(1)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Pro', html)
        self.assertIn('Подписка', mail.outbox[0].subject)
        self.assertNotIn('{{', html)


@override_settings(EMAIL_BACKEND=_LOCMEM)
class PasswordChangedEmailTests(TestCase):
    def test_renders_and_sends(self):
        user = User.objects.create(email='changed@test.ru', username='changed')
        mail.outbox = []
        request = mock.Mock()
        request.is_secure.return_value = True
        request.get_host.return_value = 'aineron.ru'

        from users.email_service import send_password_changed_notification
        ok = send_password_changed_notification(user, request)
        self.assertTrue(ok)
        _wait_for_outbox(1)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Пароль изменён', html)
        self.assertNotIn('{{', html)
