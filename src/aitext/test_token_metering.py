"""
Sprint 1 (TOKEN_OVERAGE_BILLING_PLAN.md): token_metering.record_usage().

Django TestCase (SQLite): python manage.py test aitext.test_token_metering
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, Chat, Message, MessageTokenUsage, NeuralNetwork
from aitext.token_metering import record_usage

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
