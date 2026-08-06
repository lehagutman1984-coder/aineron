"""
Sprint 1-3 (TOKEN_OVERAGE_BILLING_PLAN.md): token_metering — метрирование
(record_usage), расчёт доплаты (compute_overage/apply_overage) и её списание
(settle_overage, preflight_max_tokens, reconcile_unsettled_overage).

Django TestCase (SQLite): python manage.py test aitext.test_token_metering
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from aitext.models import Category, Chat, Message, MessageTokenUsage, NeuralNetwork
from aitext.token_metering import (
    apply_overage, compute_overage, preflight_max_tokens, record_usage, settle_overage,
)
from users.models import BalanceTransaction, UserSpending

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


_OVERAGE_SETTINGS = dict(
    TOKEN_METERING_ENABLED=True, TOKEN_OVERAGE_USD_RUB=80, TOKEN_OVERAGE_MARKUP=1.6,
    TOKEN_OVERAGE_MIN_FRACTION=0.25, TOKEN_OVERAGE_MIN_KOPECKS=100,
    TOKEN_OVERAGE_CAP_MULTIPLE=2.0, TOKEN_OVERAGE_ABS_CAP_KOPECKS=4000,
    TOKEN_OVERAGE_MODELS=[],
)


class _OverageBase(TestCase):
    """Общая фикстура Спринта 3: Opus 5, реальный инцидент 1850/10428 →
    доплата 1256 коп. (число закреплено ComputeOverageTests выше)."""

    OVERAGE_KOPECKS = 1256

    def setUp(self):
        self.user = User.objects.create_user(username='settle', email='settle@t.ru', password='x')
        self.network = _make_network(model_name='claude-opus-5', slug='settle-opus5', cost_kopecks=2200)
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})

    def _set_balance(self, kopecks):
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=kopecks)
        self.user.refresh_from_db(fields=['balance_kopecks'])

    def _usage_row(self, prompt_tokens=1850, completion_tokens=10428,
                   source=MessageTokenUsage.Source.PROVIDER):
        message = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.COMPLETED, content='ok',
        )
        row = record_usage(
            message, self.network, 'web', prompt_tokens, completion_tokens,
            source=source, flat_was_charged=True, flat_kopecks=2200,
        )
        apply_overage(row)
        row.refresh_from_db()
        return row


@override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
class SettleOverageTests(_OverageBase):
    """§3.2 плана — идемпотентность, §3.3 — политика при нехватке баланса."""

    def test_settles_once_and_writes_ledger_and_spending(self):
        self._set_balance(10000)
        row = self._usage_row()
        charged = settle_overage(row)
        self.assertEqual(charged, self.OVERAGE_KOPECKS)

        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, self.OVERAGE_KOPECKS)
        self.assertIsNotNone(row.settled_at)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000 - self.OVERAGE_KOPECKS)
        self.assertEqual(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.OVERAGE,
                reference=f'overage:{row.message_id}',
            ).count(), 1,
        )

    def test_double_settle_is_noop(self):
        # Главный риск спринта: ретрай Celery/реконсилер после успешного settle.
        self._set_balance(10000)
        row = self._usage_row()
        settle_overage(row)
        balance_after_first = User.objects.get(pk=self.user.pk).balance_kopecks

        self.assertEqual(settle_overage(row), 0)

        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, balance_after_first)
        self.assertEqual(
            BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).count(), 1)
        self.assertEqual(UserSpending.objects.filter(user=self.user).count(), 1)
        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, self.OVERAGE_KOPECKS)

    def test_ledger_exists_but_row_unmarked_marks_without_second_charge(self):
        # Падение процесса между spend_kopecks и update строки: транзакция в
        # ledger есть, settled_at пуст. Ровно тот случай, ради которого стоит
        # явная проба .exists() (идиома studio/billing.py) — spend_kopecks сам
        # вернул бы True и создал бы вторую UserSpending.
        self._set_balance(10000)
        row = self._usage_row()
        self.user.spend_kopecks(
            self.OVERAGE_KOPECKS, type=BalanceTransaction.Type.OVERAGE,
            reference=f'overage:{row.message_id}',
        )
        balance_after_manual = User.objects.get(pk=self.user.pk).balance_kopecks

        self.assertEqual(settle_overage(row), 0)

        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, balance_after_manual)
        self.assertEqual(
            BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).count(), 1)
        self.assertEqual(UserSpending.objects.filter(user=self.user).count(), 0)
        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, self.OVERAGE_KOPECKS)
        self.assertIsNotNone(row.settled_at)

    def test_insufficient_balance_leaves_row_unsettled_without_raising(self):
        # §3.3: preflight-клэмп сужает эту ситуацию, но не исключает (гонка с
        # параллельным запросом). Не падаем, не списываем частично — строку
        # подберёт реконсилер, после окна остаток прощается и уходит в алерт.
        self._set_balance(100)
        row = self._usage_row()
        self.assertEqual(settle_overage(row), 0)

        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 100)
        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, 0)
        self.assertIsNone(row.settled_at)
        self.assertFalse(BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).exists())
        self.assertFalse(UserSpending.objects.filter(user=self.user).exists())

    def test_aborted_stream_source_missing_settles_nothing(self):
        # §1.1(а): обрыв до usage-чанка → source=MISSING → overage 0 → списывать
        # нечего. Стоимость незавершённой генерации не угадываем.
        self._set_balance(10000)
        row = self._usage_row(source=MessageTokenUsage.Source.MISSING)
        self.assertEqual(row.overage_kopecks, 0)
        self.assertEqual(settle_overage(row), 0)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)
        self.assertFalse(BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).exists())

    @override_settings(TOKEN_OVERAGE_ENABLED=False)
    def test_disabled_settles_nothing(self):
        self._set_balance(10000)
        row = self._usage_row()
        self.assertEqual(settle_overage(row), 0)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)
        self.assertFalse(BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).exists())


@override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=True, **_OVERAGE_SETTINGS)
class SettleDryRunTests(_OverageBase):
    """Дефолт прода на момент этого спринта: считаем и пишем, деньги не трогаем."""

    def test_dry_run_computes_but_does_not_charge(self):
        self._set_balance(10000)
        row = self._usage_row()
        self.assertEqual(row.overage_kopecks, self.OVERAGE_KOPECKS)  # расчёт идёт

        self.assertEqual(settle_overage(row), 0)

        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, 0)
        self.assertIsNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)
        self.assertFalse(BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).exists())
        self.assertFalse(UserSpending.objects.filter(user=self.user).exists())


class PreflightClampTests(TestCase):
    """§3.3, вариант C. Клэмп обрезает ответ пользователю, поэтому обязан быть
    полным no-op, пока доплата не включена по-настоящему."""

    OPUS5_ARGS = dict(model_name='claude-opus-5', max_tokens=16384, prompt_tokens=1850, flat_kopecks=2200)

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_clamps_when_balance_too_low_for_worst_case(self):
        clamped = preflight_max_tokens(head_kopecks=500, **self.OPUS5_ARGS)
        self.assertLess(clamped, 16384)
        self.assertGreaterEqual(clamped, 1024)

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_healthy_balance_leaves_max_tokens_untouched(self):
        # worst-case overage для Opus 5 при потолке = 3162 коп. (см.
        # ComputeOverageTests.test_opus5_worst_case_not_capped)
        self.assertEqual(preflight_max_tokens(head_kopecks=5000, **self.OPUS5_ARGS), 16384)

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_never_goes_below_floor(self):
        clamped = preflight_max_tokens(
            model_name='claude-fable-5', max_tokens=16384, prompt_tokens=5000,
            flat_kopecks=900, head_kopecks=0,
        )
        self.assertEqual(clamped, 1024)

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_unaudited_model_untouched(self):
        self.assertEqual(
            preflight_max_tokens(model_name='gpt-4o', max_tokens=16384, prompt_tokens=1850,
                                 flat_kopecks=1000, head_kopecks=0),
            16384,
        )

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_free_or_unlimited_message_untouched(self):
        # flat_kopecks=0 ⇒ flat_was_charged=False ⇒ overage невозможен (§2.3.1),
        # обрезать ответ не за что.
        self.assertEqual(preflight_max_tokens(head_kopecks=0, **{**self.OPUS5_ARGS, 'flat_kopecks': 0}), 16384)

    @override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=True, **_OVERAGE_SETTINGS)
    def test_dry_run_never_clamps(self):
        self.assertEqual(preflight_max_tokens(head_kopecks=0, **self.OPUS5_ARGS), 16384)

    @override_settings(TOKEN_OVERAGE_ENABLED=False, TOKEN_OVERAGE_DRY_RUN=False, **_OVERAGE_SETTINGS)
    def test_disabled_never_clamps(self):
        self.assertEqual(preflight_max_tokens(head_kopecks=0, **self.OPUS5_ARGS), 16384)


@override_settings(TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False,
                    TOKEN_OVERAGE_SETTLE_FROM='2020-01-01', **_OVERAGE_SETTINGS)
class ReconcileUnsettledOverageTests(_OverageBase):
    """§3.4 — досписывает то, что не списалось инлайн, в окне 20мин–6ч."""

    def _age(self, row, **delta):
        MessageTokenUsage.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(**delta))

    def _run(self):
        from aitext.tasks import reconcile_unsettled_overage
        reconcile_unsettled_overage.apply()

    def test_settles_row_inside_window(self):
        self._set_balance(10000)
        row = self._usage_row()
        self._age(row, hours=1)

        self._run()

        row.refresh_from_db()
        self.assertEqual(row.settled_kopecks, self.OVERAGE_KOPECKS)
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000 - self.OVERAGE_KOPECKS)

    def test_ignores_too_fresh_row(self):
        # Младше 20 минут — инлайн-settle мог ещё не отработать.
        self._set_balance(10000)
        row = self._usage_row()
        self._age(row, minutes=5)

        self._run()

        row.refresh_from_db()
        self.assertIsNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)

    def test_ignores_row_older_than_window(self):
        # Старше 6 часов — остаток прощается (§3.3, вариант B как страховка).
        self._set_balance(10000)
        row = self._usage_row()
        self._age(row, hours=9)

        self._run()

        row.refresh_from_db()
        self.assertIsNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)

    def test_ignores_already_settled_row(self):
        self._set_balance(10000)
        row = self._usage_row()
        settle_overage(row)
        self._age(row, hours=1)
        balance_after_settle = User.objects.get(pk=self.user.pk).balance_kopecks

        self._run()

        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, balance_after_settle)
        self.assertEqual(
            BalanceTransaction.objects.filter(type=BalanceTransaction.Type.OVERAGE).count(), 1)

    @override_settings(TOKEN_OVERAGE_SETTLE_FROM='')
    def test_does_nothing_without_settle_from_cutoff(self):
        # Без отсечки реконсилер ретроактивно списал бы весь dry-run-период в
        # момент выключения TOKEN_OVERAGE_DRY_RUN.
        self._set_balance(10000)
        row = self._usage_row()
        self._age(row, hours=1)

        self._run()

        row.refresh_from_db()
        self.assertIsNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)

    @override_settings(TOKEN_OVERAGE_DRY_RUN=True)
    def test_dry_run_reconciler_is_noop(self):
        self._set_balance(10000)
        row = self._usage_row()
        self._age(row, hours=1)

        self._run()

        row.refresh_from_db()
        self.assertIsNone(row.settled_at)
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 10000)
