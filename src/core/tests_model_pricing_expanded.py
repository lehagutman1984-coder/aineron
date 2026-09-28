"""
ITEM 1 расширение (2026-09-28, после инцидента с claude-opus-5): полный аудит опта
для активного каталога, фикс точного/префиксного рассогласования allowlist'ов,
запасной расчёт себестоимости по розничной цене для будущих неаудированных моделей.
"""
from django.test import SimpleTestCase, TestCase, override_settings

from core import model_pricing as mp


class WholesaleTableTests(SimpleTestCase):
    """Каждая активная (на момент аудита 2026-09-28) текстовая модель должна
    резолвиться в ставки — иначе overage/free_tier_guard видит её как «не аудирована»."""

    ACTIVE_MODEL_NAMES = [
        'gpt-5.5-pro', 'claude-fable-5', 'claude-fable-5.1', 'gpt-6-astra', 'gpt-5.5',
        'claude-opus-4-8', 'claude-opus-5', 'claude-sonnet-4-6', 'gemini-3.1-pro-preview',
        'gpt-5.6-terra', 'claude-sonnet-5', 'gpt-5.6-sol', 'grok-4.6', 'grok-4.5',
        'qwen3.8-max', 'qwen3.6-max-preview', 'claude-haiku-4-5-20251001',
        'gemini-3.6-flash', 'gemini-3.7-flash', 'deepseek-v4-pro', 'gpt-5.6-luna',
        'deepseek-v4-flash',
    ]

    def test_every_active_model_has_wholesale_rates(self):
        missing = [m for m in self.ACTIVE_MODEL_NAMES if mp.wholesale_rates(m) is None]
        self.assertEqual(missing, [], f"без ставок: {missing}")

    def test_gpt_5_6_sol_uses_higher_apimart_rate_not_openrouter_list(self):
        # apimart (провайдер прода) дороже листа OpenRouter для этой модели —
        # берём безопасный максимум (PRICING_SIMPLIFICATION_PLAN.md §1.1).
        self.assertEqual(mp.wholesale_rates('gpt-5.6-sol'), (3.2, 16.0))

    def test_gpt_6_astra_wholesale_is_not_the_competitor_repriced_retail(self):
        # pricingPreviewModels.ts: retail пересчитана на конкурент×0.95, а не
        # на опт×K - опт указан в комментарии отдельно (840/4200 при K=105).
        self.assertEqual(mp.wholesale_rates('gpt-6-astra'), (8.0, 40.0))

    def test_longest_prefix_still_wins_for_fable_5_1(self):
        self.assertEqual(mp.wholesale_rates('claude-fable-5'), mp.wholesale_rates('claude-fable-5.1'))


class CanonicalKeyAndEligibilityTests(SimpleTestCase):
    def test_canonical_key_picks_longest_match(self):
        self.assertEqual(mp.canonical_key('claude-fable-5.1'), 'claude-fable-5')
        self.assertEqual(mp.canonical_key('gpt-5.5-pro'), 'gpt-5.5-pro')
        self.assertNotEqual(mp.canonical_key('gpt-5.5-pro'), 'gpt-5.5')

    def test_canonical_key_none_for_unaudited(self):
        self.assertIsNone(mp.canonical_key('some-future-model-xyz'))

    def test_eligible_with_empty_allowlist_means_whole_table(self):
        self.assertTrue(mp.overage_eligible('claude-opus-5', []))
        self.assertFalse(mp.overage_eligible('unknown-model', []))

    def test_fable_5_1_eligible_via_prefix_even_if_allowlist_only_lists_base(self):
        """Баг, найденный аудитом: model_name-точный allowlist не видел префиксные варианты."""
        self.assertTrue(mp.overage_eligible('claude-fable-5.1', ['claude-fable-5']))

    def test_backward_compat_exact_name_in_allowlist_still_works(self):
        self.assertTrue(mp.overage_eligible('claude-opus-5', ['claude-opus-5']))

    def test_not_eligible_when_allowlist_excludes_model(self):
        self.assertFalse(mp.overage_eligible('claude-opus-5', ['gpt-5.6-terra']))


class _FakeNetwork:
    def __init__(self, model_name, cost_kopecks):
        self.model_name = model_name
        self.cost_kopecks = cost_kopecks


@override_settings(TOKEN_OVERAGE_USD_RUB=100.0, PRICING_K_RETAIL=105)
class EstimatedCostFallbackTests(SimpleTestCase):
    def test_audited_model_delegates_to_real_cost(self):
        net = _FakeNetwork('claude-opus-5', 709)
        expected = mp.cost_kopecks('claude-opus-5', 50_887, 12_263)
        self.assertEqual(mp.estimated_cost_kopecks(net, 50_887, 12_263), expected)

    def test_fallback_is_an_upper_bound_over_random_split(self):
        """estimated_cost_kopecks (без аудита) не должен НЕДО-оценивать реальный опт ни при
        каком разбиении in/out-ставок, дающем ту же розничную цену на стандартном профиле."""
        import random
        random.seed(0)
        retail = 500  # гипотетическая неаудированная модель
        net = _FakeNetwork('future-model-xyz', retail)
        for _ in range(200):
            in_rate = random.uniform(0.1, 50)
            out_rate = random.uniform(0.1, 50)
            # подгоняем retail под эту пару ставок на стандартном профиле (6000/1500),
            # чтобы сравнение было честным (иначе retail и ставки не связаны)
            usd_standard = (6000 * in_rate + 1500 * out_rate) / 1_000_000
            retail_for_pair = round(usd_standard * 105 * 100)
            net.cost_kopecks = retail_for_pair
            p = random.randint(0, 60_000)
            o = random.randint(0, 20_000)
            real_usd = (p * in_rate + o * out_rate) / 1_000_000
            real_kopecks = round(real_usd * 100 * 100)  # R=100 руб/$ (override выше) -> копейки
            estimate = mp.estimated_cost_kopecks(net, p, o)
            self.assertGreaterEqual(estimate, real_kopecks - 1,  # -1: округления
                                    f"p={p} o={o} in={in_rate} out={out_rate} retail={retail_for_pair}")

    def test_fallback_zero_retail_is_zero(self):
        net = _FakeNetwork('free-ish', 0)
        self.assertEqual(mp.estimated_cost_kopecks(net, 1000, 1000), 0)

    def test_fallback_scales_with_prompt_size(self):
        net = _FakeNetwork('future-model-xyz', 500)
        small = mp.estimated_cost_kopecks(net, 100, 100)
        large = mp.estimated_cost_kopecks(net, 100_000, 100)
        self.assertGreater(large, small)
