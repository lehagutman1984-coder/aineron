"""
Тесты оплаты криптовалютой (Crypto Pay / @CryptoBot) — API замокан.
"""
import hashlib
import hmac
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from users.models import PaymentHistory

User = get_user_model()

TEST_TOKEN = 'test-crypto-token'

_INVOICE_OK = {
    'invoice_id': 12345,
    'status': 'active',
    'bot_invoice_url': 'https://t.me/CryptoBot?start=IVxyz',
    'web_app_invoice_url': 'https://pay.crypt.bot/IVxyz',
}

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

_CRYPTO_ON = dict(CRYPTO_PAY_ENABLED=True, CRYPTO_PAY_TOKEN=TEST_TOKEN, CACHES=_LOCMEM_CACHE)


def make_user(email='crypto@test.ru', kopecks=0):
    user = User.objects.create(email=email, username=email.split('@')[0])
    User.objects.filter(pk=user.pk).update(
        balance_kopecks=kopecks, pages_count=kopecks // 100,
    )
    user.refresh_from_db()
    return user


def sign_body(body: bytes, token: str = TEST_TOKEN) -> str:
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


@override_settings(**_CRYPTO_ON)
class CryptoTopupTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def _topup(self, amount=500):
        with mock.patch('users.crypto_payments._api_call', return_value=_INVOICE_OK):
            return self.client.post('/api/v1/billing/crypto/topup/', {'amount': amount}, format='json')

    # ── конфиг / флаг ────────────────────────────────────────────────────────

    def test_config_enabled(self):
        resp = self.client.get('/api/v1/billing/crypto/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['enabled'])
        self.assertIn('USDT', resp.json()['assets'])

    @override_settings(CRYPTO_PAY_ENABLED=False)
    def test_config_disabled_by_flag(self):
        resp = self.client.get('/api/v1/billing/crypto/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['enabled'])

    @override_settings(CRYPTO_PAY_ENABLED=False)
    def test_topup_disabled_returns_503(self):
        resp = self._topup()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['error']['code'], 'crypto_disabled')

    # ── создание инвойса ─────────────────────────────────────────────────────

    def test_topup_creates_pending_payment(self):
        resp = self._topup(500)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['invoice_id'], 12345)
        self.assertTrue(data['pay_url'].startswith('https://t.me/'))
        payment = PaymentHistory.objects.get(id=data['payment_id'])
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.payment_method, 'crypto')
        self.assertEqual(payment.payment_id, '12345')
        self.assertEqual(payment.amount_kopecks, 50_000)

    def test_topup_amount_out_of_range(self):
        resp = self._topup(1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'invalid_amount')

    def test_topup_provider_error_marks_failed(self):
        from users.crypto_payments import CryptoPayError
        with mock.patch('users.crypto_payments._api_call', side_effect=CryptoPayError('down')):
            resp = self.client.post('/api/v1/billing/crypto/topup/', {'amount': 500}, format='json')
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(PaymentHistory.objects.filter(user=self.user, status='failed').count(), 1)

    # ── поллинг статуса ──────────────────────────────────────────────────────

    def test_status_settles_paid_invoice(self):
        payment_id = self._topup(500).json()['payment_id']
        paid = dict(_INVOICE_OK, status='paid')
        with mock.patch('users.crypto_payments._api_call', return_value={'items': [paid]}):
            resp = self.client.get(f'/api/v1/billing/crypto/status/{payment_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')
        self.assertEqual(resp.json()['balance_kopecks'], 50_000)

    def test_status_expired_marks_failed(self):
        payment_id = self._topup(500).json()['payment_id']
        expired = dict(_INVOICE_OK, status='expired')
        with mock.patch('users.crypto_payments._api_call', return_value={'items': [expired]}):
            resp = self.client.get(f'/api/v1/billing/crypto/status/{payment_id}/')
        self.assertEqual(resp.json()['status'], 'failed')
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 0)

    def test_status_foreign_payment_404(self):
        payment_id = self._topup(500).json()['payment_id']
        other = make_user('other@test.ru')
        self.client.force_authenticate(user=other)
        resp = self.client.get(f'/api/v1/billing/crypto/status/{payment_id}/')
        self.assertEqual(resp.status_code, 404)


@override_settings(**_CRYPTO_ON, INTL_MODE=True, INTL_KOPECKS_PER_USD=10000)
class IntlModeTests(APITestCase):
    """INTL_MODE: пополнение в USD-номинале, Robokassa отключена."""

    def setUp(self):
        self.user = make_user('intl@test.ru')
        self.client.force_authenticate(user=self.user)

    def test_config_usd_mode(self):
        resp = self.client.get('/api/v1/billing/crypto/')
        data = resp.json()
        self.assertEqual(data['mode'], 'usd')
        self.assertEqual(data['kopecks_per_usd'], 10000)
        self.assertEqual(data['min_amount'], 1)

    def test_usd_topup_credits(self):
        with mock.patch('users.crypto_payments._api_call', return_value=_INVOICE_OK):
            resp = self.client.post('/api/v1/billing/crypto/topup/', {'amount_usd': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['currency'], 'USD')
        self.assertEqual(data['credits'], 50_000)
        payment = PaymentHistory.objects.get(id=data['payment_id'])
        self.assertEqual(payment.amount_kopecks, 50_000)

    def test_usd_topup_settle_credits_balance(self):
        with mock.patch('users.crypto_payments._api_call', return_value=_INVOICE_OK):
            payment_id = self.client.post(
                '/api/v1/billing/crypto/topup/', {'amount_usd': 10}, format='json',
            ).json()['payment_id']
        paid = dict(_INVOICE_OK, status='paid')
        with mock.patch('users.crypto_payments._api_call', return_value={'items': [paid]}):
            resp = self.client.get(f'/api/v1/billing/crypto/status/{payment_id}/')
        self.assertEqual(resp.json()['status'], 'success')
        self.assertEqual(resp.json()['balance_kopecks'], 100_000)

    def test_usd_topup_out_of_range(self):
        resp = self.client.post('/api/v1/billing/crypto/topup/', {'amount_usd': 0.5}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_robokassa_tariff_pay_disabled(self):
        from users.models import Tariff
        tariff = Tariff.objects.create(
            display_name='Test', price=100, pages_count=100, is_active=True,
        )
        resp = self.client.post(f'/api/v1/billing/tariffs/{tariff.id}/pay/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error']['code'], 'intl_card_disabled')

    def test_robokassa_buy_pages_disabled(self):
        resp = self.client.post('/api/v1/billing/pages/buy/', {'pages': 100}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error']['code'], 'intl_card_disabled')


@override_settings(**_CRYPTO_ON)
class CryptoWebhookTests(APITestCase):
    WEBHOOK = '/users/api/payment/crypto/webhook/'

    def setUp(self):
        self.user = make_user()
        self.payment = PaymentHistory.objects.create(
            user=self.user,
            payment_type='pages',
            payment_method='crypto',
            invoice_id='crypto-12345',
            payment_id='12345',
            amount=500,
            amount_kopecks=50_000,
            pages_count=500,
            status='pending',
            description='test',
        )

    def _post_webhook(self, body: dict, signature: str | None = None):
        raw = json.dumps(body).encode()
        return self.client.generic(
            'POST', self.WEBHOOK, raw,
            content_type='application/json',
            HTTP_CRYPTO_PAY_API_SIGNATURE=signature if signature is not None else sign_body(raw),
        )

    def _paid_update(self):
        return {
            'update_id': 1,
            'update_type': 'invoice_paid',
            'payload': {'invoice_id': 12345, 'status': 'paid', 'payload': str(self.payment.id)},
        }

    def test_webhook_settles_payment(self):
        resp = self._post_webhook(self._paid_update())
        self.assertEqual(resp.status_code, 200)
        self.payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.payment.status, 'success')
        self.assertEqual(self.user.balance_kopecks, 50_000)

    def test_webhook_repeat_is_idempotent(self):
        self._post_webhook(self._paid_update())
        self._post_webhook(self._paid_update())
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 50_000)

    def test_webhook_bad_signature_403(self):
        resp = self._post_webhook(self._paid_update(), signature='deadbeef')
        self.assertEqual(resp.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 0)

    @override_settings(CRYPTO_PAY_ENABLED=False)
    def test_webhook_disabled_403(self):
        resp = self._post_webhook(self._paid_update())
        self.assertEqual(resp.status_code, 403)

    def test_webhook_unknown_invoice_ok_no_credit(self):
        update = {
            'update_id': 2,
            'update_type': 'invoice_paid',
            'payload': {'invoice_id': 99999, 'status': 'paid', 'payload': '999999'},
        }
        resp = self._post_webhook(update)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 0)

    def test_webhook_settle_race_single_credit(self):
        # settle вызывается и вебхуком, и поллингом — начисление одно (reference)
        from users.crypto_payments import settle_crypto_payment
        self.assertTrue(settle_crypto_payment(self.payment))
        self.payment.refresh_from_db()
        self.assertFalse(settle_crypto_payment(self.payment))
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 50_000)
