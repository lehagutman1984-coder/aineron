from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, NeuralNetwork
from api.services.billing import charge_for_tokens, get_kopecks_per_1k, refund_kopecks, tokens_to_kopecks

User = get_user_model()


def _make_network(**kwargs):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    defaults = dict(
        name='Test Model', slug=f'test-model-{kwargs.get("cost_kopecks", 0)}',
        category=cat, cost_per_message=30, provider='openrouter',
    )
    defaults.update(kwargs)
    return NeuralNetwork.objects.create(**defaults)


@override_settings(MIN_CHARGE_KOPECKS=10)
class TokensToKopecksTests(TestCase):
    def test_zero_tokens_costs_nothing(self):
        network = _make_network(cost_kopecks=3000)
        self.assertEqual(tokens_to_kopecks(network, 0), 0)

    def test_uses_cost_kopecks_authoritative_field(self):
        # cost_kopecks=50 (0,50 ₽) за ~500 токенов (DEFAULT_TOKENS_PER_MESSAGE)
        network = _make_network(cost_kopecks=50, kopecks_per_1k_tokens=0)
        kopecks = tokens_to_kopecks(network, 500)
        self.assertEqual(kopecks, 50)

    def test_explicit_kopecks_per_1k_overrides_cost_kopecks(self):
        network = _make_network(cost_kopecks=3000, kopecks_per_1k_tokens=Decimal('20.00'))
        kopecks = tokens_to_kopecks(network, 1000)
        self.assertEqual(kopecks, 20)

    def test_min_charge_floor_applies_to_tiny_requests(self):
        network = _make_network(cost_kopecks=100, kopecks_per_1k_tokens=Decimal('1.00'))
        kopecks = tokens_to_kopecks(network, 1)  # почти ноль токенов -> должен применяться пол
        self.assertEqual(kopecks, 10)  # MIN_CHARGE_KOPECKS

    @override_settings(MIN_CHARGE_KOPECKS=50)
    def test_min_charge_floor_respects_override(self):
        network = _make_network(cost_kopecks=100, kopecks_per_1k_tokens=Decimal('1.00'))
        kopecks = tokens_to_kopecks(network, 1)
        self.assertEqual(kopecks, 50)

    def test_ceil_rounding_never_undercharges(self):
        network = _make_network(cost_kopecks=0, kopecks_per_1k_tokens=Decimal('3.00'))
        # 100 токенов * 3/1000 = 0.3 копейки -> ceil = 1, но ниже пола -> MIN_CHARGE_KOPECKS
        kopecks = tokens_to_kopecks(network, 100)
        self.assertGreaterEqual(kopecks, 1)


@override_settings(MIN_CHARGE_KOPECKS=10)
class ChargeForTokensPersonalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dev', email='dev@t.ru', password='x')
        self.user.set_kopecks(10000)  # 100 ₽
        self.network = _make_network(cost_kopecks=3000, kopecks_per_1k_tokens=Decimal('60.00'))

    def test_charge_deducts_balance_and_records_token_usage(self):
        from api.models import TokenUsage

        usage = {'prompt_tokens': 400, 'completion_tokens': 100, 'total_tokens': 500}
        kopecks = charge_for_tokens(self.user, self.network, usage)
        self.user.refresh_from_db(fields=['balance_kopecks'])

        self.assertEqual(kopecks, 30)  # 60 коп/1k * 500 = 30
        self.assertEqual(self.user.balance_kopecks, 10000 - 30)
        tu = TokenUsage.objects.get(user=self.user)
        self.assertEqual(tu.cost_kopecks, 30)
        self.assertEqual(tu.total_tokens, 500)

    def test_insufficient_balance_raises(self):
        from api.exceptions import InsufficientStarsError

        self.user.set_kopecks(1)
        usage = {'prompt_tokens': 400, 'completion_tokens': 100, 'total_tokens': 500}
        with self.assertRaises(InsufficientStarsError):
            charge_for_tokens(self.user, self.network, usage)

    def test_refund_returns_exact_amount(self):
        usage = {'prompt_tokens': 400, 'completion_tokens': 100, 'total_tokens': 500}
        kopecks = charge_for_tokens(self.user, self.network, usage)
        self.user.refresh_from_db(fields=['balance_kopecks'])
        balance_after_charge = self.user.balance_kopecks

        refund_kopecks(self.user, kopecks, reason='test', reference='req:1')
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, balance_after_charge + kopecks)


class ApplyPromoViewTests(TestCase):
    URL = '/api/v1/billing/promo/'

    def setUp(self):
        from rest_framework.test import APIClient
        from users.models import PromoCode

        self.user = User.objects.create_user(username='promo', email='promo@t.ru', password='x')
        self.user.set_kopecks(0)
        self.promo = PromoCode.objects.create(code='BONUS50', stars=50, usage_limit=2)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_apply_credits_balance_and_increments_used_count(self):
        resp = self.client.post(self.URL, {'code': 'BONUS50'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['kopecks_added'], 5000)

        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 5000)
        self.promo.refresh_from_db(fields=['used_count'])
        self.assertEqual(self.promo.used_count, 1)

    def test_code_lookup_is_case_insensitive(self):
        resp = self.client.post(self.URL, {'code': 'bonus50'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_second_apply_by_same_user_rejected_without_double_credit(self):
        self.client.post(self.URL, {'code': 'BONUS50'}, format='json')
        resp = self.client.post(self.URL, {'code': 'BONUS50'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 5000)

    def test_usage_limit_exhausts_code(self):
        from rest_framework.test import APIClient

        self.client.post(self.URL, {'code': 'BONUS50'}, format='json')
        other = User.objects.create_user(username='promo2', email='promo2@t.ru', password='x')
        other_client = APIClient()
        other_client.force_authenticate(other)
        self.assertEqual(other_client.post(self.URL, {'code': 'BONUS50'}, format='json').status_code, 200)

        third = User.objects.create_user(username='promo3', email='promo3@t.ru', password='x')
        third_client = APIClient()
        third_client.force_authenticate(third)
        resp = third_client.post(self.URL, {'code': 'BONUS50'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'promo_expired')

    def test_deactivated_code_rejected(self):
        self.promo.is_active = False
        self.promo.save()
        resp = self.client.post(self.URL, {'code': 'BONUS50'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'promo_expired')


@override_settings(ROBOKASSA_LOGIN='testlogin', ROBOKASSA_PASS1='testpass1', ROBOKASSA_PASS2='testpass2')
class DiscountPromoTests(TestCase):
    """Процентная скидка на тариф через промокод."""

    PAY_URL = '/api/v1/billing/tariffs/{id}/pay/'
    CHECK_URL = '/api/v1/billing/promo/check/'
    APPLY_URL = '/api/v1/billing/promo/'
    WEBHOOK_URL = '/users/api/payment-success/'

    def setUp(self):
        from decimal import Decimal as D
        from rest_framework.test import APIClient
        from users.models import PromoCode, Tariff

        self.user = User.objects.create_user(username='disc', email='disc@t.ru', password='x')
        self.user.set_kopecks(0)
        self.tariff = Tariff.objects.create(
            display_name='Про', price=D('899.00'), pages_count=1150, duration_days=30,
        )
        self.promo = PromoCode.objects.create(code='SALE10', discount_percent=10, usage_limit=5)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_pay_with_discount_promo_reduces_out_sum(self):
        from users.models import PaymentHistory

        resp = self.client.post(
            self.PAY_URL.format(id=self.tariff.id), {'promo_code': 'sale10'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['form']['fields']['OutSum'], '809.10')
        self.assertEqual(data['discount_percent'], 10)

        payment = PaymentHistory.objects.get(invoice_id=str(data['invoice_id']))
        self.assertEqual(payment.amount_kopecks, 80910)
        self.assertEqual(payment.promo_code_id, self.promo.pk)
        # Кредит тарифа — полный, скидка только на цену
        self.assertEqual(payment.pages_count, 1150)

    def test_pay_without_promo_keeps_full_price(self):
        resp = self.client.post(self.PAY_URL.format(id=self.tariff.id), {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['form']['fields']['OutSum'], '899.00')

    def test_balance_promo_rejected_at_checkout(self):
        from users.models import PromoCode

        PromoCode.objects.create(code='BAL100', stars=100)
        resp = self.client.post(
            self.PAY_URL.format(id=self.tariff.id), {'promo_code': 'BAL100'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'promo_not_discount')

    def test_discount_promo_rejected_in_balance_apply(self):
        resp = self.client.post(self.APPLY_URL, {'code': 'SALE10'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'promo_is_discount')
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 0)

    def test_promo_check_returns_discounted_price(self):
        resp = self.client.post(
            self.CHECK_URL, {'code': 'SALE10', 'tariff_id': self.tariff.id}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['type'], 'discount')
        self.assertEqual(data['discount_percent'], 10)
        self.assertEqual(data['discounted_price'], '809.10')

    def test_used_discount_promo_rejected(self):
        from users.models import UsedPromoCode

        UsedPromoCode.objects.create(user=self.user, promo_code=self.promo)
        resp = self.client.post(
            self.PAY_URL.format(id=self.tariff.id), {'promo_code': 'SALE10'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'promo_already_used')

    def test_webhook_marks_promo_used_once(self):
        import hashlib as _hashlib
        from django.test import Client as DjangoClient
        from users.models import UsedPromoCode

        resp = self.client.post(
            self.PAY_URL.format(id=self.tariff.id), {'promo_code': 'SALE10'}, format='json',
        )
        data = resp.json()
        inv_id = str(data['invoice_id'])
        out_sum = data['form']['fields']['OutSum']
        signature = _hashlib.md5(f'{out_sum}:{inv_id}:testpass2'.encode()).hexdigest().upper()

        webhook = DjangoClient()
        payload = {'OutSum': out_sum, 'InvId': inv_id, 'SignatureValue': signature}
        result = webhook.post(self.WEBHOOK_URL, payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content.decode(), f'OK{inv_id}')

        self.assertTrue(
            UsedPromoCode.objects.filter(user=self.user, promo_code=self.promo).exists()
        )
        self.promo.refresh_from_db(fields=['used_count'])
        self.assertEqual(self.promo.used_count, 1)

        # Полный кредит тарифа начислен, несмотря на скидку
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 1150 * 100)

        # Повтор вебхука не двигает счётчик
        result2 = webhook.post(self.WEBHOOK_URL, payload)
        self.assertEqual(result2.status_code, 200)
        self.promo.refresh_from_db(fields=['used_count'])
        self.assertEqual(self.promo.used_count, 1)


class RegisterReferralTests(TestCase):
    URL = '/api/v1/auth/register/'

    def setUp(self):
        self.referrer = User.objects.create_user(username='ref', email='ref@t.ru', password='x')
        self.referrer.referral_code = 'ABCD1234'
        self.referrer.save(update_fields=['referral_code'])

    def _client(self):
        from rest_framework.test import APIClient
        return APIClient()

    def test_register_with_ref_cookie_sets_referrer(self):
        client = self._client()
        client.cookies['ref_code'] = 'ABCD1234'
        resp = client.post(self.URL, {'email': 'new@t.ru', 'password': 'password123'}, format='json')
        self.assertEqual(resp.status_code, 201)

        new_user = User.objects.get(email='new@t.ru')
        self.assertEqual(new_user.referrer_id, self.referrer.pk)
        self.referrer.refresh_from_db(fields=['referral_clicks'])
        self.assertEqual(self.referrer.referral_clicks, 1)

    def test_register_with_ref_code_in_body(self):
        client = self._client()
        resp = client.post(
            self.URL,
            {'email': 'new2@t.ru', 'password': 'password123', 'ref_code': 'abcd1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        new_user = User.objects.get(email='new2@t.ru')
        self.assertEqual(new_user.referrer_id, self.referrer.pk)

    def test_unknown_ref_code_ignored(self):
        client = self._client()
        client.cookies['ref_code'] = 'NOSUCH99'
        resp = client.post(self.URL, {'email': 'new3@t.ru', 'password': 'password123'}, format='json')
        self.assertEqual(resp.status_code, 201)
        new_user = User.objects.get(email='new3@t.ru')
        self.assertIsNone(new_user.referrer_id)
