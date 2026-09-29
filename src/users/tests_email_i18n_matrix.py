"""
Полная матрица 6 писем x 6 языков - страховка от опечатки в имени ключа
(Django-шаблон на отсутствующий {{ t.xxx }} не падает, а тихо рендерит
пустую строку, так что точечные тесты по 1 языку такое не поймают).
"""
import time
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from users.email_i18n import SUPPORTED_LANGS

User = get_user_model()
_LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _wait_for_outbox(n, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(mail.outbox) >= n:
            return
        time.sleep(0.05)


def _mock_request():
    request = mock.Mock()
    request.is_secure.return_value = True
    request.get_host.return_value = 'aineron.net'
    return request


@override_settings(EMAIL_BACKEND=_LOCMEM)
class EmailMatrixTests(TestCase):
    def _assert_clean(self, html, label):
        self.assertNotIn('{{', html, f'{label}: незаполненный {{{{ }}}} - опечатка в имени ключа')
        self.assertNotIn('{%', html, f'{label}: незакрытый тег шаблона')
        self.assertNotIn('None', html, f'{label}: None просочился в текст (незаданный context var)')

    def test_all_languages_verification(self):
        from users.email_service import send_verification_email
        for lang in SUPPORTED_LANGS:
            mail.outbox = []
            user = User.objects.create(email=f'v-{lang}@test.net', username=f'v{lang}', language=lang)
            send_verification_email(user, _mock_request())
            _wait_for_outbox(1)
            self._assert_clean(mail.outbox[0].alternatives[0][0], f'verification/{lang}')

    def test_all_languages_password_reset(self):
        from users.email_service import send_password_reset_email
        for lang in SUPPORTED_LANGS:
            mail.outbox = []
            user = User.objects.create(email=f'pr-{lang}@test.net', username=f'pr{lang}', language=lang)
            send_password_reset_email(user, 'TempPass1', _mock_request())
            _wait_for_outbox(1)
            self._assert_clean(mail.outbox[0].alternatives[0][0], f'password_reset/{lang}')

    def test_all_languages_password_changed(self):
        from users.email_service import send_password_changed_notification
        for lang in SUPPORTED_LANGS:
            mail.outbox = []
            user = User.objects.create(email=f'pc-{lang}@test.net', username=f'pc{lang}', language=lang)
            send_password_changed_notification(user, _mock_request())
            _wait_for_outbox(1)
            self._assert_clean(mail.outbox[0].alternatives[0][0], f'password_changed/{lang}')

    def test_all_languages_payment_confirmation_topup_and_subscription(self):
        from users.email_service import send_payment_confirmation_email
        for lang in SUPPORTED_LANGS:
            mail.outbox = []
            user = User.objects.create(
                email=f'pay-{lang}@test.net', username=f'pay{lang}', language=lang, balance_kopecks=5000,
            )
            send_payment_confirmation_email(
                user, kind='topup', amount_kopecks=1000, method='Test', balance_kopecks=5000,
            )
            _wait_for_outbox(1)
            self._assert_clean(mail.outbox[0].alternatives[0][0], f'payment_confirmation(topup)/{lang}')

            mail.outbox = []
            send_payment_confirmation_email(
                user, kind='subscription', amount_kopecks=39900, method='Test',
                tariff_name='Pro', balance_kopecks=5000,
            )
            _wait_for_outbox(1)
            self._assert_clean(mail.outbox[0].alternatives[0][0], f'payment_confirmation(subscription)/{lang}')

    def test_all_languages_subscription_expiring_both_branches(self):
        from users.email_service import send_verification_email  # noqa: F401 - unused, keeps import group tidy
        from django.template.loader import render_to_string
        from users.email_i18n import get_email_context, is_rtl, plural_days
        from core.money import format_money, rub_to_kopecks

        for lang in SUPPORTED_LANGS:
            for auto_renew in (True, False):
                t, lang_code = get_email_context('subscription_expiring', lang)
                username = f'sub{lang}'
                tariff_name = 'Pro'
                days_left = 4
                days_word = plural_days(days_left, lang_code)
                price = format_money(rub_to_kopecks(Decimal('399.00')))
                context = {
                    'username': username,
                    'tariff_name': tariff_name,
                    'expires_at': '01.01.2027',
                    'days_left': days_left,
                    'days_word': days_word,
                    'auto_renew': auto_renew,
                    'price': price,
                    'site_name': 'Aineron.net',
                    'site_url': 'https://aineron.net',
                    't': t,
                    'lang_code': lang_code,
                    'is_rtl': is_rtl(lang_code),
                    'greeting_title': t['greeting_title'].format(username=username),
                    'footer_copyright': t['footer_copyright'].format(site_name='Aineron.net'),
                    'timer_suffix': t['timer_suffix'].format(days_word=days_word),
                    'auto_renew_text': t['auto_renew_text'].format(days_left=days_left, days_word=days_word, price=price),
                    'no_renew_text': t['no_renew_text'].format(days_left=days_left, days_word=days_word, tariff_name=tariff_name),
                }
                html = render_to_string('neuro/emails/subscription_expiring_soon.html', context)
                self._assert_clean(html, f'subscription_expiring(auto_renew={auto_renew})/{lang}')

    def test_all_languages_renewal_code_both_actions(self):
        from django.template.loader import render_to_string
        from users.email_i18n import get_email_context, is_rtl

        for lang in SUPPORTED_LANGS:
            for action in ('enable', 'disable'):
                t, lang_code = get_email_context('renewal_code', lang)
                username = f'ren{lang}'
                action_word = t['action_enable'] if action == 'enable' else t['action_disable']
                context = {
                    'username': username,
                    'code': '123456',
                    'site_name': 'Aineron.net',
                    'site_url': 'https://aineron.net',
                    't': t,
                    'lang_code': lang_code,
                    'is_rtl': is_rtl(lang_code),
                    'greeting_title': t['greeting_title'].format(username=username),
                    'footer_copyright': t['footer_copyright'].format(site_name='Aineron.net'),
                    'action_word': action_word,
                    'btn_goto': t['btn_goto'].format(site_name='Aineron.net'),
                }
                html = render_to_string('neuro/emails/renewal_code.html', context)
                self._assert_clean(html, f'renewal_code({action})/{lang}')
