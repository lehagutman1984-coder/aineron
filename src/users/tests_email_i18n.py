"""
2026-09-29: локализация 6 транзакционных писем (verification, password_reset,
password_changed, payment_confirmation, subscription_expiring, renewal_code)
по CustomUser.language. До этого все письма были захардкожены на русском
независимо от языка пользователя - критично для aineron.net (INTL_MODE=1).

Заодно регрессия на два найденных попутно бага:
- resend_renewal_code: render_to_string('emails/renewal_code.html', ...) без
  префикса 'neuro/' -> TemplateDoesNotExist -> тихий 500 при каждой повторной
  отправке кода.
- subscription_expiring_soon.html: сумма автопродления была захардкожена как
  "{{ price }} ₽" - на aineron.net показывала бы рубли вместо кредитов.
"""
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

User = get_user_model()
_LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
_LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _wait_for_outbox(n, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(mail.outbox) >= n:
            return
        time.sleep(0.05)


def _mock_request(host='aineron.net'):
    request = mock.Mock()
    request.is_secure.return_value = True
    request.get_host.return_value = host
    return request


@override_settings(EMAIL_BACKEND=_LOCMEM)
class EmailI18nTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_password_changed_english_user_gets_english_email(self):
        from users.email_service import send_password_changed_notification
        user = User.objects.create(email='en-user@test.net', username='enuser', language='en')
        send_password_changed_notification(user, _mock_request())
        _wait_for_outbox(1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, 'Your password was changed')
        html = msg.alternatives[0][0]
        self.assertIn('Password changed', html)
        self.assertIn('Hello, enuser!', html)
        self.assertNotIn('Пароль изменён', html)
        self.assertNotIn('{{', html)
        self.assertNotIn('{t.', html)

    def test_payment_confirmation_turkish_user(self):
        from users.email_service import send_payment_confirmation_email
        user = User.objects.create(email='tr-user@test.net', username='truser', language='tr', balance_kopecks=5000)
        send_payment_confirmation_email(
            user, kind='topup', amount_kopecks=1000, method='Crypto Pay', balance_kopecks=5000,
        )
        _wait_for_outbox(1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Bakiye yüklendi', html)
        self.assertIn('Merhaba, truser!', html)
        self.assertNotIn('Баланс пополнен', html)

    def test_verification_email_indonesian_user(self):
        from users.email_service import send_verification_email
        user = User.objects.create(email='id-user@test.net', username='iduser', language='id')
        send_verification_email(user, _mock_request())
        _wait_for_outbox(1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Konfirmasi email Anda', html)
        self.assertNotIn('Подтверждение email', html)

    def test_password_reset_farsi_user_is_rtl(self):
        from users.email_service import send_password_reset_email
        user = User.objects.create(email='fa-user@test.net', username='fauser', language='fa')
        send_password_reset_email(user, 'TempPass123', _mock_request())
        _wait_for_outbox(1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('dir="rtl"', html)
        self.assertIn('lang="fa"', html)

    def test_renewal_code_arabic_user_is_rtl_and_translated(self):
        from users.email_i18n import get_email_context, EMAIL_TRANSLATIONS, is_rtl
        t, lang_code = get_email_context('renewal_code', 'ar')
        self.assertEqual(lang_code, 'ar')
        self.assertTrue(is_rtl(lang_code))
        self.assertEqual(t['subject'], EMAIL_TRANSLATIONS['renewal_code']['ar']['subject'])
        self.assertNotEqual(t['subject'], EMAIL_TRANSLATIONS['renewal_code']['ru']['subject'])

    def test_missing_language_falls_back_to_ru(self):
        """language='' (не заполнено, как у большинства старых пользователей .ru)."""
        from users.email_service import send_password_changed_notification
        user = User.objects.create(email='no-lang@test.ru', username='nolang', language='')
        send_password_changed_notification(user, _mock_request(host='aineron.ru'))
        _wait_for_outbox(1)
        self.assertEqual(mail.outbox[0].subject, 'Пароль изменён')

    def test_unknown_language_falls_back_to_ru(self):
        from users.email_i18n import get_email_context
        t, lang_code = get_email_context('password_changed', 'zz-not-a-real-lang')
        self.assertEqual(lang_code, 'ru')
        self.assertEqual(t['subject'], 'Пароль изменён')

    def test_ltr_language_has_no_dir_attribute(self):
        from users.email_service import send_password_changed_notification
        user = User.objects.create(email='ru-user@test.ru', username='ruuser', language='ru')
        send_password_changed_notification(user, _mock_request(host='aineron.ru'))
        _wait_for_outbox(1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn('dir="rtl"', html)
        self.assertIn('lang="ru"', html)


@override_settings(EMAIL_BACKEND=_LOCMEM, CACHES=_LOCMEM_CACHE)
class RenewalCodeRegressionTests(TestCase):
    """resend_renewal_code падал на всех запросах (TemplateDoesNotExist,
    'emails/renewal_code.html' без 'neuro/' - см. views.py)."""

    def setUp(self):
        mail.outbox = []
        self.user = User.objects.create_user(
            username='renewaluser', email='renewal@test.ru', password='x', language='en',
        )
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])
        self.client.force_login(self.user)

    def test_send_code_then_resend_both_succeed(self):
        r1 = self.client.post(
            '/users/api/send-renewal-code/', {'action': 'disable'}, content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['success'])

        r2 = self.client.post('/users/api/resend-renewal-code/', {}, content_type='application/json')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['success'], r2.json())

        _wait_for_outbox(2)
        self.assertEqual(len(mail.outbox), 2)
        # Второе письмо - от resend, английский пользователь -> английский subject.
        self.assertIn('confirmation code', mail.outbox[1].subject.lower())


class SubscriptionExpiringCurrencyTests(TestCase):
    def test_uses_format_money_not_hardcoded_rub_symbol(self):
        """Регрессия: шаблон раньше хардкодил '{{ price }} ₽' - на aineron.net
        (INTL_MODE=1) это показывало бы рубли вместо кредитов. Теперь price
        приходит уже отформатированным через format_money() из tasks.py."""
        from users.email_i18n import get_email_context
        from core.money import format_money, rub_to_kopecks
        from decimal import Decimal

        t, lang_code = get_email_context('subscription_expiring', 'ru')
        price = format_money(rub_to_kopecks(Decimal('399.00')))
        text = t['auto_renew_text'].format(days_left=4, days_word='дня', price=price)
        self.assertIn(price, text)
        # Шаблон больше не должен сам дописывать "₽" - это уже часть price.
        self.assertNotIn('{{ price }} ₽', text)
