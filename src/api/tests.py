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
