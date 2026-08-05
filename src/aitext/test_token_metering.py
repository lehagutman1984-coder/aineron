"""
Sprint 1 (TOKEN_OVERAGE_BILLING_PLAN.md): token_metering.record_usage().

Django TestCase (SQLite): python manage.py test aitext.test_token_metering
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, Chat, Message, MessageTokenUsage, NeuralNetwork
from aitext.token_metering import apply_overage, compute_overage, record_usage

User = get_user_model()


def _make_network(**kwargs):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    defaults = dict(
        name='Test Model', slug='test-model-metering', model_name='claude-opus-5',
        category=cat, cost_per_message=22, cost_kopecks=2200, provider='openrouter',
    )
    defaults.update(kwargs)
    return NeuralNetwork.objects.create(**defaults)


class RecordUsageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='metering', email='metering@t.ru', password='x')
        self.network = _make_network()
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})
        self.message = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.COMPLETED, content='ok',
        )

    @override_settings(TOKEN_METERING_ENABLED=False)
    def test_noop_when_disabled(self):
        row = record_usage(
            self.message, self.network, 'web', 1850, 10428,
            source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200,
        )
        self.assertIsNone(row)
        self.assertFalse(MessageTokenUsage.objects.filter(message=self.message).exists())

    @override_settings(TOKEN_METERING_ENABLED=True)
    def test_writes_row_when_enabled(self):
        row = record_usage(
            self.message, self.network, 'web', 1850, 10428,
            source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200,
        )
        self.assertIsNotNone(row)
        row.refresh_from_db()
        self.assertEqual(row.prompt_tokens, 1850)
        self.assertEqual(row.completion_tokens, 10428)
        self.assertEqual(row.source, MessageTokenUsage.Source.PROVIDER)
        self.assertTrue(row.flat_was_charged)
        self.assertEqual(row.flat_kopecks, 2200)
        self.assertEqual(row.model_name, 'claude-opus-5')
        self.assertEqual(row.channel, MessageTokenUsage.Channel.WEB)

    @override_settings(TOKEN_METERING_ENABLED=True)
    def test_idempotent_update_or_create_no_duplicate_row(self):
        # SSE-путь может вызвать record_usage дважды на одно сообщение (основной
        # путь + гипотетический повтор) — OneToOneField не должен бросать
        # IntegrityError, должен просто обновить ту же строку.
        record_usage(self.message, self.network, 'web', 100, 200,
                      source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200)
        record_usage(self.message, self.network, 'web', 150, 300,
                      source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200)

        self.assertEqual(MessageTokenUsage.objects.filter(message=self.message).count(), 1)
        row = MessageTokenUsage.objects.get(message=self.message)
        self.assertEqual(row.prompt_tokens, 150)
        self.assertEqual(row.completion_tokens, 300)

    @override_settings(TOKEN_METERING_ENABLED=True)
    def test_flat_was_charged_false_for_free_or_unlimited_message(self):
        # §2.3.1 плана: ноль легитимен для бесплатных/безлимитных сообщений —
        # flat_was_charged должен быть явным False, а не выводиться из
        # flat_kopecks == 0 где-то ниже по цепочке (Спринт 2, compute_overage).
        row = record_usage(
            self.message, self.network, 'web', 100, 200,
            source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=False, flat_kopecks=0,
        )
        self.assertFalse(row.flat_was_charged)
        self.assertEqual(row.flat_kopecks, 0)

    @override_settings(TOKEN_METERING_ENABLED=True)
    def test_never_raises_on_bad_input(self):
        # record_usage не должен ронять генерацию ни при каких обстоятельствах.
        row = record_usage(None, self.network, 'web', 1, 2, source='provider')
        self.assertIsNone(row)


@override_settings(TOKEN_METERING_ENABLED=True, TOKEN_OVERAGE_USD_RUB=80,
                    TOKEN_OVERAGE_MARKUP=1.6, TOKEN_OVERAGE_MIN_FRACTION=0.25,
                    TOKEN_OVERAGE_MIN_KOPECKS=100, TOKEN_OVERAGE_CAP_MULTIPLE=2.0,
                    TOKEN_OVERAGE_ABS_CAP_KOPECKS=4000, TOKEN_OVERAGE_MODELS=[])
class ComputeOverageTests(TestCase):
    """
    §2.3 плана. Числа для Opus 5 worst-case и Fable 5 worst-case НЕ совпадают
    с иллюстративной таблицей §2.4 самого плана — там при ручном подсчёте cap
    посчитан как flat×CAP_MULTIPLE без max(..., ABS_CAP_KOPECKS), что
    противоречит формуле §2.3 в том же документе (расхождение найдено и
    зафиксировано здесь при реализации, см. Sprint 2 "Реализовано" в плане).
    "Реальный инцидент" (единственный число-в-число сверяемый пример) сходится
    точно: 21,60 ₽ → 34,56 ₽ → 12,56 ₽.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='overage', email='overage@t.ru', password='x')
        self.opus5 = _make_network(model_name='claude-opus-5', slug='ov-opus5', cost_kopecks=2200)
        self.fable5 = _make_network(model_name='claude-fable-5', slug='ov-fable5', cost_kopecks=900)
        self.unaudited = _make_network(model_name='gpt-4o', slug='ov-gpt4o', cost_kopecks=1000)
        self.chat = Chat.objects.create(user=self.user, network=self.opus5, title='t', settings={})

    def _row(self, network, prompt_tokens, completion_tokens, flat_kopecks, flat_was_charged=True):
        message = Message.objects.create(chat=self.chat, role='assistant', status=Message.Status.COMPLETED, content='ok')
        row = record_usage(
            message, network, 'web', prompt_tokens, completion_tokens,
            source=MessageTokenUsage.Source.PROVIDER,
            flat_was_charged=flat_was_charged, flat_kopecks=flat_kopecks if flat_was_charged else 0,
        )
        return row

    def test_typical_message_no_overage(self):
        row = self._row(self.opus5, 1850, 600, 2200)
        cost, overage = compute_overage(row)
        self.assertEqual(cost, 194)
        self.assertEqual(overage, 0)

    def test_real_incident_matches_plan_exactly(self):
        row = self._row(self.opus5, 1850, 10428, 2200)
        cost, overage = compute_overage(row)
        self.assertEqual(cost, 2160)
        self.assertEqual(overage, 1256)  # 12,56 ₽ — сходится с §2.4 плана

    def test_opus5_worst_case_not_capped(self):
        row = self._row(self.opus5, 1850, 16384, 2200)
        cost, overage = compute_overage(row)
        self.assertEqual(cost, 3351)
        # raw overage (3162) < cap (max(4400, 4000)=4400) — cap не срабатывает,
        # итог = target ровно (маржа = MARKUP точно).
        self.assertEqual(overage, 3162)

    def test_fable5_worst_case_hits_abs_cap(self):
        row = self._row(self.fable5, 1850, 16384, 900)
        cost, overage = compute_overage(row)
        self.assertEqual(cost, 6702)
        # raw overage (9823) > cap (max(1800, 4000)=4000) — cap срабатывает.
        self.assertEqual(overage, 4000)
        total = 900 + overage
        self.assertLess(total, cost)  # даже с overage у потолка — убыток (осознанный, §2.4)

    def test_flat_was_charged_false_forces_zero_overage(self):
        # §2.3.1: безлимитный/бесплатный пользователь у потолка токенов не
        # должен получить overage ни при каких обстоятельствах — guard первый.
        row = self._row(self.opus5, 1850, 16384, 2200, flat_was_charged=False)
        cost, overage = compute_overage(row)
        self.assertEqual(cost, 3351)  # себестоимость всё равно считается — для отчёта
        self.assertEqual(overage, 0)

    def test_unaudited_model_returns_none_cost_zero_overage(self):
        row = self._row(self.unaudited, 1850, 600, 1000)
        cost, overage = compute_overage(row)
        self.assertIsNone(cost)
        self.assertEqual(overage, 0)

    def test_allowlist_restricts_to_listed_models(self):
        row = self._row(self.opus5, 1850, 10428, 2200)
        with override_settings(TOKEN_OVERAGE_MODELS=['claude-fable-5']):
            cost, overage = compute_overage(row)
            self.assertEqual(overage, 0)  # opus5 не в allowlist

    def test_apply_overage_persists_to_row(self):
        row = self._row(self.opus5, 1850, 10428, 2200)
        apply_overage(row)
        row.refresh_from_db()
        self.assertEqual(row.cost_kopecks, 2160)
        self.assertEqual(row.overage_kopecks, 1256)
        self.assertEqual(row.settled_kopecks, 0)  # Спринт 3, не трогаем здесь
