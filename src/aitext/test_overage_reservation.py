"""
2026-09-28 (ревью, раунд 3, TOKEN_OVERAGE_RESERVE_ENABLED): атомарный резерв
worst-case доплаты ДО обращения к апстриму — закрывает гонку параллельных
сообщений вокруг free_tier_guard/preflight_max_tokens (обе функции раньше
только ЧИТАЛИ баланс). reserve_overage_tokens/settle_overage (netto-зачёт
против резерва)/release_overage_reservation/resolve_overage_guard.

Django TestCase (SQLite): python manage.py test aitext.test_overage_reservation
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, Chat, Message, MessageTokenUsage, NeuralNetwork
from aitext.token_metering import (
    apply_overage, record_usage, release_overage_reservation,
    reserve_overage_tokens, resolve_overage_guard, settle_overage,
)
from users.models import BalanceTransaction, UserSpending

User = get_user_model()

_OVERAGE_SETTINGS = dict(
    TOKEN_METERING_ENABLED=True, TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False,
    TOKEN_OVERAGE_USD_RUB=80, TOKEN_OVERAGE_MARKUP=1.6,
    TOKEN_OVERAGE_MIN_FRACTION=0.25, TOKEN_OVERAGE_MIN_KOPECKS=100,
    TOKEN_OVERAGE_CAP_MULTIPLE=2.0, TOKEN_OVERAGE_ABS_CAP_KOPECKS=4000,
    TOKEN_OVERAGE_MODELS=[], TOKEN_OVERAGE_RESERVE_ENABLED=True,
)


def _make_network(**kwargs):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    defaults = dict(
        name='Opus Reserve', slug='opus-reserve', model_name='claude-opus-5',
        category=cat, cost_per_message=22, cost_kopecks=2200, provider='openrouter',
    )
    defaults.update(kwargs)
    return NeuralNetwork.objects.create(**defaults)


@override_settings(**_OVERAGE_SETTINGS)
class ReserveOverageTokensTests(TestCase):
    """Прямые тесты reserve_overage_tokens — race-сценарий из ревью."""

    def setUp(self):
        self.user = User.objects.create_user(username='res1', email='res1@t.ru', password='x')
        self.network = _make_network()

    def _set_balance(self, kopecks):
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=kopecks)
        self.user.refresh_from_db(fields=['balance_kopecks'])

    def test_reserve_succeeds_and_debits_atomically(self):
        self._set_balance(10000)
        tokens, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=1,
        )
        self.assertTrue(ok)
        self.assertGreater(reserved, 0)
        self.assertEqual(ref, 'overage-reserve:1')
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000 - reserved)
        self.assertEqual(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.OVERAGE, reference=ref,
            ).count(), 1,
        )

    def test_second_parallel_message_cannot_reserve_the_same_headroom(self):
        """Главный сценарий гонки: баланс хватает только на ОДНО полноразмерное
        резервирование — второе (параллельное) сообщение должно либо сузиться,
        либо провалиться, а не тихо получить те же деньги, что и первое."""
        first_tokens, first_reserved, _, first_ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=100,
        )
        self._set_balance(first_reserved)  # ровно столько, сколько ушло на первое

        second_tokens, second_reserved, second_ref, second_ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=101,
        )
        # Либо второе резервирование провалилось (баланс уже исчерпан первым),
        # либо оно сузилось до меньшей суммы — в любом случае НЕ получило те
        # же {first_reserved} коп., которые уже принадлежат первому сообщению.
        if second_ok:
            self.assertLessEqual(second_reserved, first_reserved)
            self.user.refresh_from_db()
            self.assertGreaterEqual(self.user.balance_kopecks, 0)  # баланс не ушёл в минус
        else:
            self.assertEqual(second_reserved, 0)
            self.assertIsNone(second_ref)

    def test_no_balance_at_all_fails_at_floor(self):
        self._set_balance(0)
        # Большой prompt - даже при floor (1024, минимальный completion) worst-case
        # overage всё равно выше порога (проверено: 50000 промпт-токенов -> 1328
        # коп. на floor, порог 550) - иначе "нечего резервировать" и "нет баланса"
        # неразличимы на floor с маленьким prompt.
        tokens, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 50000, 10428, 2200, message_id=2,
        )
        self.assertFalse(ok)
        self.assertEqual(reserved, 0)
        self.assertIsNone(ref)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 0)  # ничего не списано за неудачные попытки

    def test_non_eligible_model_or_zero_overage_reserves_nothing(self):
        self._set_balance(10000)
        # completion=1 -> worst-case overage ниже порога -> нечего резервировать
        tokens, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 1, 1, 2200, message_id=3,
        )
        self.assertTrue(ok)
        self.assertEqual(reserved, 0)
        self.assertIsNone(ref)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000)


@override_settings(**_OVERAGE_SETTINGS)
class SettleAgainstReservationTests(TestCase):
    """settle_overage() netto-зачёт факта против резерва."""

    def setUp(self):
        self.user = User.objects.create_user(username='res2', email='res2@t.ru', password='x')
        self.network = _make_network(slug='opus-reserve-2')
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})

    def _set_balance(self, kopecks):
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=kopecks)
        self.user.refresh_from_db(fields=['balance_kopecks'])

    def _reserved_message(self, prompt_tokens, completion_tokens, reserve_tokens):
        """Создаёт сообщение с реальным резервом (reserve_overage_tokens) под
        reserve_tokens, затем MessageTokenUsage с ФАКТИЧЕСКИМИ prompt/completion
        (может отличаться от того, под что резервировали)."""
        message = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.COMPLETED, content='ok',
            settings={},
        )
        _, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, prompt_tokens, reserve_tokens, 2200, message_id=message.pk,
        )
        self.assertTrue(ok)
        message.settings = {'overage_reserve_reference': ref}
        message.save(update_fields=['settings'])
        row = record_usage(
            message, self.network, 'web', prompt_tokens, completion_tokens,
            source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200,
        )
        apply_overage(row)
        row.refresh_from_db()
        return message, row, reserved

    def test_actual_below_reserved_refunds_difference(self):
        self._set_balance(10000)
        # Резервируем под полный 10428 (overage 1256 коп.), но реально
        # сгенерировалось меньше - 9000 (overage 798 коп., числа сверены через
        # model_pricing.cost_kopecks напрямую) - оба значения выше порога
        # (иначе overage_kopecks=0 и settle_overage выходит до reservation-веток).
        message, row, reserved = self._reserved_message(1850, 9000, reserve_tokens=10428)
        balance_after_reserve = User.objects.get(pk=self.user.pk).balance_kopecks
        self.assertLess(balance_after_reserve, 10000)  # резерв реально списан

        charged = settle_overage(row)
        self.assertEqual(charged, row.overage_kopecks)

        row.refresh_from_db()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(row.settled_kopecks, row.overage_kopecks)
        self.assertLess(row.overage_kopecks, reserved)  # факт меньше резерва — часть вернулась
        self.user.refresh_from_db()
        # Итоговый баланс = starting - overage (ровно факт, не резерв)
        self.assertEqual(self.user.balance_kopecks, 10000 - row.overage_kopecks)

    def test_zero_overage_still_releases_full_reservation(self):
        # 2026-10-01: живой баг (messages 3719/3721, claude-sonnet-5-5/opus-5-5).
        # Резервируем под worst-case (10428 токенов), но реальный ответ —
        # короткая реплика (26 токенов, как в живом инциденте): себестоимость
        # настолько мала, что overage_kopecks получается 0 (ниже порога/уже
        # покрыто flat) — это ДОЛЖНО означать полный возврат всего резерва,
        # а не "нечего зачитывать". До фикса settle_overage выходил по
        # overage<=0 ДО того, как вообще смотрел на резерв, и реальный
        # резерв оставался списанным навсегда.
        self._set_balance(10000)
        message, row, reserved = self._reserved_message(1850, 26, reserve_tokens=10428)
        self.assertGreater(reserved, 0)  # резерв реально был взят
        self.assertEqual(row.overage_kopecks, 0)  # факт не превышает порог/flat
        balance_after_reserve = User.objects.get(pk=self.user.pk).balance_kopecks
        self.assertLess(balance_after_reserve, 10000)  # резерв реально списан

        charged = settle_overage(row)
        self.assertEqual(charged, 0)  # ничего ДОПОЛНИТЕЛЬНО не списано

        row.refresh_from_db()
        self.assertIsNotNone(row.settled_at, "резерв с overage=0 обязан быть разрешён (release), не оставлен висеть")
        self.assertEqual(row.settled_kopecks, 0)
        self.user.refresh_from_db()
        # Весь неиспользованный резерв вернулся на баланс целиком.
        self.assertEqual(self.user.balance_kopecks, 10000)
        self.assertTrue(
            BalanceTransaction.objects.filter(
                user=self.user, type='refund', reference=f'overage-reserve:{message.pk}:refund',
            ).exists()
        )

    def test_actual_above_reserved_charges_extra(self):
        self._set_balance(10000)
        # Резервируем под меньший ответ (9000, overage 798 коп.), но факт
        # получился длиннее (10428, overage 1256 коп.) — редкий случай (ошибка
        # оценки prompt_tokens). Оба значения выше порога 550 коп. в этой
        # конфигурации (иначе overage_kopecks=0 и вся нетто-логика не вызывается).
        message, row, reserved = self._reserved_message(1850, 10428, reserve_tokens=9000)
        charged = settle_overage(row)
        self.assertEqual(charged, row.overage_kopecks)
        self.assertGreater(row.overage_kopecks, reserved)  # факт больше резерва

        row.refresh_from_db()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(row.settled_kopecks, row.overage_kopecks)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000 - row.overage_kopecks)
        self.assertTrue(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.OVERAGE,
                reference=f'overage-reserve:{message.pk}:extra',
            ).exists()
        )
        self.assertEqual(
            UserSpending.objects.filter(
                user=self.user, description__icontains='сверх резерва',
            ).count(), 1,
        )

    def test_extra_debit_fails_leaves_row_unsettled_then_reconciler_retry_collects(self):
        self._set_balance(10000)
        # Резерв (9000, overage 798 коп.) списан, баланс исчерпан ДО settle —
        # перерасход сверх резерва (факт 10428, overage 1256 коп.) не собрать.
        message, row, reserved = self._reserved_message(1850, 10428, reserve_tokens=9000)
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=0)
        self.user.refresh_from_db(fields=['balance_kopecks'])

        charged = settle_overage(row)
        self.assertEqual(charged, 0)
        row.refresh_from_db()
        self.assertIsNone(row.settled_at, "extra не собран - строка должна остаться незачтённой")
        self.assertEqual(row.settled_kopecks, 0)

        # Реконсилер топит баланс пользователю и повторяет settle_overage —
        # должен досписать ТОЛЬКО перерасход, не пытаться списать резерв заново.
        extra = row.overage_kopecks - reserved
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=extra)
        self.user.refresh_from_db(fields=['balance_kopecks'])
        charged_retry = settle_overage(row)
        self.assertEqual(charged_retry, row.overage_kopecks)
        row.refresh_from_db()
        self.assertIsNotNone(row.settled_at)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 0)  # extra списан ровно один раз

    def test_legacy_row_without_reservation_uses_old_path_unchanged(self):
        # Без message.settings['overage_reserve_reference'] - поведение как до
        # этой защиты (полное списание overage целиком, не netto-зачёт).
        self._set_balance(10000)
        message = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.COMPLETED, content='ok', settings={},
        )
        row = record_usage(
            message, self.network, 'web', 1850, 10428,
            source=MessageTokenUsage.Source.PROVIDER, flat_was_charged=True, flat_kopecks=2200,
        )
        apply_overage(row)
        row.refresh_from_db()
        self.assertFalse(BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.OVERAGE, reference__startswith='overage-reserve:',
        ).exists())

        charged = settle_overage(row)
        self.assertEqual(charged, row.overage_kopecks)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000 - row.overage_kopecks)
        self.assertTrue(BalanceTransaction.objects.filter(
            user=self.user, type=BalanceTransaction.Type.OVERAGE, reference=f'overage:{message.pk}',
        ).exists())


@override_settings(**_OVERAGE_SETTINGS)
class ReleaseOverageReservationTests(TestCase):
    """Освобождение резерва при финальном провале генерации (refund_message_billing)."""

    def setUp(self):
        self.user = User.objects.create_user(username='res3', email='res3@t.ru', password='x')
        self.network = _make_network(slug='opus-reserve-3')

    def _set_balance(self, kopecks):
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=kopecks)
        self.user.refresh_from_db(fields=['balance_kopecks'])

    def test_release_refunds_full_reserved_amount(self):
        self._set_balance(10000)
        _, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=5,
        )
        self.assertTrue(ok)
        balance_after_reserve = User.objects.get(pk=self.user.pk).balance_kopecks
        self.assertEqual(balance_after_reserve, 10000 - reserved)

        ok_release = release_overage_reservation(self.user, ref)
        self.assertTrue(ok_release)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 10000)  # полностью вернулось

    def test_release_is_idempotent(self):
        self._set_balance(10000)
        _, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=6,
        )
        release_overage_reservation(self.user, ref)
        balance_after_first_release = User.objects.get(pk=self.user.pk).balance_kopecks
        release_overage_reservation(self.user, ref)  # повторный вызов - no-op
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, balance_after_first_release)

    def test_refund_message_billing_releases_reservation(self):
        from aitext.billing import record_message_billing, refund_message_billing

        self._set_balance(10000)
        chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})
        message = Message.objects.create(
            chat=chat, role='assistant', status=Message.Status.PENDING, content='', settings={},
        )
        self.user.spend_kopecks(2200, type='spend', reference=f'chat:{message.pk}')
        record_message_billing(message, f'chat:{message.pk}', 2200)
        balance_after_flat = User.objects.get(pk=self.user.pk).balance_kopecks

        _, reserved, ref, ok = reserve_overage_tokens(
            self.user, self.network, 1850, 10428, 2200, message_id=message.pk,
        )
        self.assertTrue(ok)
        message.settings = {**message.settings, 'overage_reserve_reference': ref}
        message.save(update_fields=['settings'])
        balance_after_reserve = User.objects.get(pk=self.user.pk).balance_kopecks
        self.assertEqual(balance_after_reserve, balance_after_flat - reserved)

        refund_message_billing(message)
        self.user.refresh_from_db()
        # И плоское списание, И резерв overage должны вернуться полностью.
        self.assertEqual(self.user.balance_kopecks, 10000)


@override_settings(**_OVERAGE_SETTINGS)
class ResolveOverageGuardReserveTests(TestCase):
    """resolve_overage_guard с TOKEN_OVERAGE_RESERVE_ENABLED=True - интеграционный
    уровень (то, что реально вызывают api/views/chats.py и aitext/tasks.py)."""

    def setUp(self):
        self.user = User.objects.create_user(username='res4', email='res4@t.ru', password='x')
        self.network = _make_network(slug='opus-reserve-4')

    def _set_balance(self, kopecks):
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=kopecks)
        self.user.refresh_from_db(fields=['balance_kopecks'])

    def test_paying_user_gets_real_reservation_not_just_advisory(self):
        self._set_balance(10000)
        result = resolve_overage_guard(
            self.user, self.network, prompt_tokens=1850, max_tokens=10428, flat_kopecks=2200,
            head_kopecks=10000, balance_before_flat=10000, message_id=10, is_trial=False,
        )
        self.assertIn(result.action, ('ok', 'clamp'))
        self.assertIsNotNone(result.reserve_reference)
        self.user.refresh_from_db()
        self.assertLess(self.user.balance_kopecks, 10000)  # реально списано, не просто прочитано

    def test_trial_user_block_still_works_with_reserve_enabled(self):
        # free_tier_guard блокирует ДО того, как дело доходит до резерва -
        # включённый TOKEN_OVERAGE_RESERVE_ENABLED не должен ломать Rule D block.
        with override_settings(FREE_TIER_GUARD_ENABLED=True, FREE_TIER_MIN_MESSAGES=3):
            self._set_balance(50)
            result = resolve_overage_guard(
                self.user, self.network, prompt_tokens=50000, max_tokens=16384, flat_kopecks=2200,
                head_kopecks=50, balance_before_flat=2250, message_id=11, is_trial=True,
            )
            self.assertEqual(result.action, 'block')
            self.user.refresh_from_db()
            self.assertEqual(self.user.balance_kopecks, 50)  # ничего не резервировано при блоке

    def test_reserve_flag_disabled_falls_back_to_advisory_only(self):
        with override_settings(TOKEN_OVERAGE_RESERVE_ENABLED=False):
            self._set_balance(10000)
            result = resolve_overage_guard(
                self.user, self.network, prompt_tokens=1850, max_tokens=10428, flat_kopecks=2200,
                head_kopecks=10000, balance_before_flat=10000, message_id=12, is_trial=False,
            )
            self.assertIsNone(result.reserve_reference)
            self.user.refresh_from_db()
            self.assertEqual(self.user.balance_kopecks, 10000)  # advisory-only - ничего не списано
