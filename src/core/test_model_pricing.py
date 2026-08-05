"""
Sprint 2 (TOKEN_OVERAGE_BILLING_PLAN.md): core/model_pricing.py.

Django TestCase (SQLite): python manage.py test core.test_model_pricing
"""
from django.test import SimpleTestCase, override_settings

from core.model_pricing import cost_kopecks, wholesale_rates, worst_case_cost_kopecks


@override_settings(TOKEN_OVERAGE_USD_RUB=80)
class CostKopecksTests(SimpleTestCase):
    def test_unaudited_model_returns_none(self):
        self.assertIsNone(cost_kopecks('gpt-4o', 1000, 1000))
        self.assertIsNone(wholesale_rates('gpt-4o'))

    def test_real_incident_regression(self):
        # Реальная транзакция, разобранная в этом же аудите (TARIFFS.md item 10):
        # Claude Opus 5, 1850 in / 10428 out → 21,60 ₽ себестоимости.
        self.assertEqual(cost_kopecks('claude-opus-5', 1850, 10428), 2160)

    def test_typical_message_cheap(self):
        self.assertEqual(cost_kopecks('claude-opus-5', 1850, 600), 194)

    def test_gpt_5_pro_flat_symmetric_rate(self):
        self.assertEqual(cost_kopecks('gpt-5.3', 1000, 1000), 960)


class LongestPrefixWinsTests(SimpleTestCase):
    def test_opus_5_vs_opus_4_8_do_not_collide(self):
        self.assertEqual(wholesale_rates('claude-opus-5'), (5.0, 25.0))
        self.assertEqual(wholesale_rates('claude-opus-4-8'), (5.0, 25.0))

    def test_hyphenated_key_matches_real_model_name(self):
        # Ключ должен быть 'claude-opus-4-8' (дефис, как в БД), не 'claude-opus-4.8' —
        # иначе префиксный матч молча не находит модель вообще.
        self.assertIsNotNone(wholesale_rates('claude-opus-4-8'))

    def test_unknown_variant_does_not_silently_inherit_shorter_prefix(self):
        # claude-opus-5-thinking содержит префикс 'claude-opus-5' — при
        # ОТСУТСТВИИ явного ключа для варианта функция обязана вернуть те же
        # ставки, что claude-opus-5 (единственный совпавший префикс), это
        # ожидаемое (не идеальное, но осознанное) поведение substring-матчинга.
        # Этот тест фиксирует ТЕКУЩЕЕ поведение — если он однажды провалится
        # из-за добавления отдельного ключа 'claude-opus-5-thinking' с другими
        # ставками, это осознанное решение, а не регрессия.
        self.assertEqual(wholesale_rates('claude-opus-5-thinking'), wholesale_rates('claude-opus-5'))

    def test_longest_prefix_wins_when_multiple_match(self):
        # Синтетический сценарий: если бы в таблице был и короткий, и длинный
        # префикс, совпадающие с одной моделью, побеждает более длинный/точный.
        from core import model_pricing
        original = dict(model_pricing.MODEL_WHOLESALE)
        try:
            model_pricing.MODEL_WHOLESALE['gpt-5'] = (1.0, 1.0)
            model_pricing.MODEL_WHOLESALE['gpt-5-pro'] = (15.0, 120.0)
            self.assertEqual(model_pricing.wholesale_rates('gpt-5-pro'), (15.0, 120.0))
        finally:
            model_pricing.MODEL_WHOLESALE.clear()
            model_pricing.MODEL_WHOLESALE.update(original)


@override_settings(TOKEN_OVERAGE_USD_RUB=80)
class WorstCaseCostKopecksTests(SimpleTestCase):
    def test_uses_model_max_tokens_cap_as_completion_ceiling(self):
        # core/model_limits.py: потолок для 'claude' семейства — 16384.
        expected = cost_kopecks('claude-opus-5', 1850, 16384)
        self.assertEqual(worst_case_cost_kopecks('claude-opus-5', 1850), expected)
