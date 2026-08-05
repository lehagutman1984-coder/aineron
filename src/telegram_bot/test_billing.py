"""
Sprint 0 (TOKEN_OVERAGE_BILLING_PLAN.md): pre-charge за текстовые сообщения бота.

До этого спринта бот только проверял баланс (has_enough_kopecks) перед
генерацией, но никогда его не списывал — TEXT_BILLING_ENABLED использовался
в aitext/tasks.py, но нигде не был определён в settings.py, поэтому
getattr(settings, 'TEXT_BILLING_ENABLED', False) всегда был False.

Django TestCase (SQLite): python manage.py test telegram_bot.test_billing
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from aitext.billing import refund_message_billing
from aitext.models import Category, Chat, Message, NeuralNetwork
from telegram_bot.handlers.chat import _charge_text_message
from users.models import UserSpending

User = get_user_model()


def _make_network(**kwargs):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    defaults = dict(
        name='Test Model', slug='test-model-tg-billing',
        category=cat, cost_per_message=9, cost_kopecks=900, provider='openrouter',
    )
    defaults.update(kwargs)
    return NeuralNetwork.objects.create(**defaults)


class ChargeTextMessageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tgbill', email='tgbill@t.ru', password='x')
        self.network = _make_network()
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})
        self.assistant_msg = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.PENDING, content='',
        )

    def _set_balance(self, kopecks):
        self.user.balance_kopecks = kopecks
        self.user.save(update_fields=['balance_kopecks'])

    def test_charges_and_records_billing_reference(self):
        self._set_balance(5000)
        ok = _charge_text_message(self.user, self.assistant_msg, self.network, self.network.cost_kopecks)
        self.assertTrue(ok)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 5000 - self.network.cost_kopecks)

        self.assistant_msg.refresh_from_db()
        self.assertEqual(
            self.assistant_msg.settings.get('billing_reference'),
            f'chat:{self.assistant_msg.id}',
        )
        self.assertEqual(self.assistant_msg.settings.get('billing_kopecks'), self.network.cost_kopecks)
        self.assertTrue(
            UserSpending.objects.filter(user=self.user, amount_kopecks=self.network.cost_kopecks).exists()
        )

    def test_insufficient_balance_does_not_charge_or_record(self):
        self._set_balance(100)  # меньше network.cost_kopecks=900
        ok = _charge_text_message(self.user, self.assistant_msg, self.network, self.network.cost_kopecks)
        self.assertFalse(ok)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100)

        self.assistant_msg.refresh_from_db()
        self.assertNotIn('billing_reference', self.assistant_msg.settings or {})
        self.assertFalse(UserSpending.objects.filter(user=self.user).exists())

    def test_does_not_double_deduct_balance_on_retry(self):
        # Идемпотентность унаследована от users.models.spend_kopecks —
        # unique(type, reference): повторный вызов с тем же assistant_msg.id
        # не списывает деньги второй раз (тот же контракт, что уже принят
        # для веба, api/views/chats.py:138).
        self._set_balance(5000)
        _charge_text_message(self.user, self.assistant_msg, self.network, self.network.cost_kopecks)
        self.user.refresh_from_db()
        balance_after_first = self.user.balance_kopecks

        _charge_text_message(self.user, self.assistant_msg, self.network, self.network.cost_kopecks)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, balance_after_first)

    def test_refund_after_final_failure_returns_money(self):
        # refund_message_billing (aitext/billing.py) читает billing_reference/
        # billing_kopecks с message.settings и не завязан на канал (веб/бот) —
        # проверяем, что это действительно так для бот-сообщения.
        self._set_balance(5000)
        _charge_text_message(self.user, self.assistant_msg, self.network, self.network.cost_kopecks)
        self.user.refresh_from_db()
        balance_after_charge = self.user.balance_kopecks
        self.assistant_msg.refresh_from_db()

        ok = refund_message_billing(self.assistant_msg)
        self.assertTrue(ok)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, balance_after_charge + self.network.cost_kopecks)
