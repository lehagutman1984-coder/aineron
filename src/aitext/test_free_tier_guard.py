"""
ITEM 1, часть B (STATUS_AND_BACKLOG_PLAN_2026-09-25.md; инцидент 2026-09-27,
claude-opus-5, 50887 prompt-токенов на пробном балансе 10 руб.): защита
пробного (никогда не плативших) пользователя от одного сообщения, съедающего
весь стартовый баланс на дорогой модели, без опоры на overage-аудит.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, NeuralNetwork
from aitext.token_metering import free_tier_guard
from users.models import PaymentHistory, Tariff

User = get_user_model()

ON = dict(FREE_TIER_GUARD_ENABLED=True, TOKEN_OVERAGE_USD_RUB=100.0, TOKEN_OVERAGE_MARKUP=1.6,
          PRICING_K_RETAIL=105)
OFF = dict(ON, FREE_TIER_GUARD_ENABLED=False)


def _network(model_name, cost_kopecks, **kw):
    cat, _ = Category.objects.get_or_create(name='T', defaults={'slug': 't'})
    d = dict(name=model_name, slug=model_name, model_name=model_name, category=cat,
             cost_per_message=1, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _trial_user(balance_kopecks, email='trial@t.ru'):
    free = Tariff.get_default_tariff()
    u = User.objects.create_user(username=email, email=email, password='x')
    u.tariff = free
    u.set_kopecks(balance_kopecks)
    u.save(update_fields=['tariff'])
    return u


def _paying_user(balance_kopecks, email='paid@t.ru'):
    u = _trial_user(balance_kopecks, email)
    PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success')
    return u


@override_settings(**ON)
class FreeTierGuardTests(TestCase):
    def test_flag_off_is_noop(self):
        u = _trial_user(1000)
        net = _network('claude-opus-5', 709)
        with self.settings(**OFF):
            action, tokens, est = free_tier_guard(u, net, 50_887, 4000, 709, 1000)
        self.assertEqual((action, tokens), ('ok', 4000))

    def test_paying_user_is_never_restricted(self):
        u = _paying_user(1000)
        net = _network('claude-opus-5', 709)
        action, tokens, est = free_tier_guard(u, net, 50_887, 4000, 709, 1000)
        self.assertEqual((action, tokens), ('ok', 4000))

    def test_incident_replay_blocks_before_any_generation(self):
        """Ровно параметры реального инцидента: opus-5, 50887 prompt-токенов, баланс 1000 коп."""
        u = _trial_user(1000)
        net = _network('claude-opus-5', 709)
        action, tokens, est = free_tier_guard(u, net, 50_887, 4000, 709, 1000)
        self.assertEqual(action, 'block')
        self.assertEqual(tokens, 0)
        self.assertGreater(est, 1000)  # даже пол в 1024 токена не влезает в баланс

    def test_cheap_model_same_prompt_is_not_blocked(self):
        u = _trial_user(1000)
        net = _network('deepseek-v4-flash', 8)
        action, tokens, est = free_tier_guard(u, net, 50_887, 4000, 8, 1000)
        self.assertIn(action, ('ok', 'clamp'))

    def test_small_prompt_on_expensive_model_gets_clamped_not_blocked(self):
        u = _trial_user(1000)
        net = _network('claude-opus-5', 709)
        action, tokens, est = free_tier_guard(u, net, 200, 4000, 709, 1000)
        self.assertEqual(action, 'clamp')
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 4000)
        self.assertLessEqual(est, 1000)

    def test_clamp_never_exceeds_requested_max_tokens(self):
        u = _trial_user(100000)  # баланс с запасом - клэмп не должен расширять max_tokens
        net = _network('claude-opus-5', 709)
        action, tokens, est = free_tier_guard(u, net, 100, 500, 709, 100000)
        self.assertEqual(action, 'ok')
        self.assertEqual(tokens, 500)

    def test_unaudited_model_uses_retail_fallback_not_ok_by_default(self):
        """Модель без аудита опта (например, только что добавленная) всё равно защищена —
        через estimated_cost_kopecks по розничной цене, allowlist не нужен."""
        u = _trial_user(1000)
        # тир gpt-5.5-pro по розничной цене, но имя не попадает ни под один префикс MODEL_WHOLESALE
        net = _network('brand-new-unaudited-model-xyz', 5774)
        action, tokens, est = free_tier_guard(u, net, 50_887, 4000, 5774, 1000)
        self.assertEqual(action, 'block')

    def test_clamped_cost_is_always_within_balance(self):
        """На сетке промтов итоговая (клэмпнутая) стоимость никогда не превышает баланс."""
        u = _trial_user(1000)
        net = _network('gemini-3.6-flash', 107)
        for p in (0, 500, 5_000, 20_000, 60_000):
            action, tokens, est = free_tier_guard(u, net, p, 8000, 107, 1000)
            if action == 'block':
                continue
            self.assertLessEqual(est, 1000, f"p={p} action={action} tokens={tokens} est={est}")

    def test_zero_max_tokens_is_noop(self):
        u = _trial_user(1000)
        net = _network('claude-opus-5', 709)
        action, tokens, est = free_tier_guard(u, net, 100, 0, 709, 1000)
        self.assertEqual(action, 'ok')
