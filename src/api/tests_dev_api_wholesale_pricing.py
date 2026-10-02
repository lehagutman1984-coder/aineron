"""
2026-10-02 (аудит безопасности, №15): цена токена в dev-API для аудированных
моделей (есть реальный опт в core.model_pricing.MODEL_WHOLESALE) должна
считаться от реальной себестоимости × TOKEN_OVERAGE_MARKUP, а не от цены
ОДНОГО web-сообщения, делённой на условные 500 токенов — та пропорция давала
~15-кратную переплату клиента dev-API против настоящей себестоимости модели.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, NeuralNetwork
from api.services.billing import message_cost_kopecks, tokens_to_kopecks
from core import model_pricing

User = get_user_model()


def _audited_network(model_name='claude-sonnet-5', cost_kopecks=3000, **kw):
    """model_name должен реально матчиться в MODEL_WHOLESALE (этот тест
    использует claude-sonnet-5 - (2.0, 10.0) $/1M, см. core/model_pricing.py)."""
    cat, _ = Category.objects.get_or_create(name='T15', defaults={'slug': 't15'})
    d = dict(
        name=model_name, slug=model_name, model_name=model_name, category=cat,
        cost_per_message=30, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True,
    )
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _unaudited_network(cost_kopecks=3000, **kw):
    cat, _ = Category.objects.get_or_create(name='T15', defaults={'slug': 't15'})
    d = dict(
        name='Unaudited Model', slug='unaudited-model', model_name='unaudited-model',
        category=cat, cost_per_message=30, cost_kopecks=cost_kopecks,
        provider='openrouter', is_active=True,
    )
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


@override_settings(MIN_CHARGE_KOPECKS=10, TOKEN_OVERAGE_USD_RUB=80, TOKEN_OVERAGE_MARKUP=1.6)
class WholesaleBasedPricingTests(TestCase):
    def test_audited_model_uses_real_wholesale_cost_not_message_proxy(self):
        """Старая формула (cost_kopecks=3000, 500 токенов/сообщение) давала бы
        3000/0.5=6000 коп/1k - заведомо выше любой реальной себестоимости для
        claude-sonnet-5 (2.0/10.0 $/1M). Новая формула должна считать заметно
        меньше для реалистичного запроса (1000 prompt + 500 completion)."""
        network = _audited_network()
        prompt_tokens, completion_tokens = 1000, 500

        actual = message_cost_kopecks(network, prompt_tokens, completion_tokens)
        old_proxy = tokens_to_kopecks(network, prompt_tokens + completion_tokens)

        # Прямой расчёт по тем же $/1M-ставкам, что в message_cost_kopecks
        # (не через model_pricing.cost_kopecks() - та округляет ВНУТРИ себя
        # до целой копейки ДО наценки, message_cost_kopecks считает точнее,
        # округляя один раз, в конце, см. комментарий в реализации).
        from core.money import ceil_kopecks
        in_usd, out_usd = model_pricing.wholesale_rates(network.model_name)
        usd = (Decimal(prompt_tokens) * Decimal(str(in_usd))
               + Decimal(completion_tokens) * Decimal(str(out_usd))) / Decimal('1000000')
        expected = ceil_kopecks(usd * Decimal('80') * Decimal('100') * Decimal('1.6'))

        self.assertEqual(actual, expected)
        self.assertLess(actual, old_proxy)  # принципиально дешевле старой оценки

    def test_unaudited_model_keeps_old_message_proxy_formula(self):
        """Модель без реального опта - старая консервативная оценка остаётся
        (лучше не занизить цену, чем остаться совсем без ориентира)."""
        network = _unaudited_network()
        self.assertIsNone(model_pricing.wholesale_rates(network.model_name))

        actual = message_cost_kopecks(network, 400, 100)
        expected = tokens_to_kopecks(network, 500)
        self.assertEqual(actual, expected)

    def test_explicit_kopecks_per_1k_tokens_still_wins_for_unaudited_model(self):
        """network.kopecks_per_1k_tokens, если явно выставлен, остаётся
        авторитетным для неаудированных моделей (get_kopecks_per_1k)."""
        network = _unaudited_network(kopecks_per_1k_tokens=Decimal('60.00'))
        actual = message_cost_kopecks(network, 400, 100)
        self.assertEqual(actual, 30)  # 60 коп/1k * 500 = 30

    def test_zero_tokens_cost_zero(self):
        network = _audited_network()
        self.assertEqual(message_cost_kopecks(network, 0, 0), 0)

    def test_min_charge_floor_still_applies_to_audited_models(self):
        """Очень маленький запрос к дешёвой аудированной модели всё равно не
        должен уйти ниже MIN_CHARGE_KOPECKS."""
        network = _audited_network(model_name='deepseek-v4-flash')
        actual = message_cost_kopecks(network, 1, 1)
        self.assertGreaterEqual(actual, 10)  # MIN_CHARGE_KOPECKS=10 из override_settings
