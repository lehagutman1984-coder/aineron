"""
Sprint 3 (TOKEN_OVERAGE_BILLING_PLAN.md), веб-SSE-путь: StreamMessageView.

Единственные тесты, которые реально прогоняют перестроенный генератор
`generate()` целиком, а не функции token_metering по отдельности. Спринт 3
поднял два первых `yield` внутрь существующего `try` и добавил ветку
`finally` — риск, из-за которого Спринт 1 откладывал эту правку, закрывается
именно здесь:

- штатное завершение: usage получен → доплата списана ДО события `done`;
- обрыв клиента (`response.close()` посреди стрима) → `GeneratorExit` →
  `finally`: сообщение не висит `PENDING`, строка usage пишется с
  `source=MISSING`, доплата НЕ списывается (§1.1(а)).

Django TestCase (SQLite): python manage.py test api.test_stream_settle
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, Chat, Message, MessageTokenUsage, NeuralNetwork
from users.models import BalanceTransaction, UserSpending

User = get_user_model()

# Реальный инцидент из §2.4 плана: Opus 5, 1850/10428 → доплата 1256 коп.
PROMPT_TOKENS = 1850
COMPLETION_TOKENS = 10428
OVERAGE_KOPECKS = 1256
FLAT_KOPECKS = 2200


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    """Минимальный дубль чанка OpenAI SDK: либо контент, либо финальный usage."""

    def __init__(self, content=None, usage=None):
        self.choices = [_Choice(content)] if content is not None else []
        self.usage = usage


class _Usage:
    prompt_tokens = PROMPT_TOKENS
    completion_tokens = COMPLETION_TOKENS


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks

    def create(self, **kwargs):
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks):
        self.chat = type('_Chat', (), {'completions': _FakeCompletions(chunks)})()


@override_settings(
    TOKEN_METERING_ENABLED=True,
    TOKEN_METERING_STREAM_USAGE_MODELS=['claude-opus-5'],
    TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False,
    TOKEN_OVERAGE_USD_RUB=80, TOKEN_OVERAGE_MARKUP=1.6,
    TOKEN_OVERAGE_MIN_FRACTION=0.25, TOKEN_OVERAGE_MIN_KOPECKS=100,
    TOKEN_OVERAGE_CAP_MULTIPLE=2.0, TOKEN_OVERAGE_ABS_CAP_KOPECKS=4000,
    TOKEN_OVERAGE_MODELS=[],
    # build_memory_context/get_history_with_compression ходят в кэш — на
    # локальном прогоне Redis нет, подменяем на locmem (иначе падают и
    # предсуществующие aitext.test_memory).
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class StreamMessageSettleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sse', email='sse@t.ru', password='x')
        User.objects.filter(pk=self.user.pk).update(balance_kopecks=100000)
        self.user.refresh_from_db()
        cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
        self.network = NeuralNetwork.objects.create(
            name='Opus 5', slug='sse-opus5', model_name='claude-opus-5', category=cat,
            cost_per_message=22, cost_kopecks=FLAT_KOPECKS, provider='openrouter',
        )
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = f'/api/v1/chats/{self.chat.id}/messages/stream/'

    def _post(self, chunks):
        with patch('api.views.chats.get_client_for_network', return_value=_FakeClient(chunks)):
            resp = self.client.post(self.url, {'message': 'привет', 'web_search': False}, format='json')
            self.assertEqual(resp.status_code, 200)
            yield resp

    def _assistant(self):
        return Message.objects.filter(chat=self.chat, role='assistant').latest('id')

    def test_full_stream_settles_overage_before_done_event(self):
        chunks = [_Chunk('раз'), _Chunk('два'), _Chunk(usage=_Usage())]
        for resp in self._post(chunks):
            body = b''.join(resp.streaming_content).decode('utf-8')

        self.assertIn('"type": "done"', body)
        msg = self._assistant()
        self.assertEqual(msg.status, Message.Status.COMPLETED)

        row = MessageTokenUsage.objects.get(message=msg)
        self.assertEqual(row.source, MessageTokenUsage.Source.PROVIDER)
        self.assertEqual(row.completion_tokens, COMPLETION_TOKENS)
        self.assertTrue(row.flat_was_charged)
        self.assertEqual(row.overage_kopecks, OVERAGE_KOPECKS)
        self.assertEqual(row.settled_kopecks, OVERAGE_KOPECKS)
        self.assertIsNotNone(row.settled_at)

        self.assertEqual(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.OVERAGE,
                reference=f'overage:{msg.id}',
            ).count(), 1,
        )
        self.assertEqual(
            User.objects.get(pk=self.user.pk).balance_kopecks,
            100000 - FLAT_KOPECKS - OVERAGE_KOPECKS,
        )
        self.assertTrue(UserSpending.objects.filter(
            user=self.user, amount_kopecks=OVERAGE_KOPECKS).exists())

    def test_client_abort_marks_failed_and_settles_nothing(self):
        # Много контент-чанков, usage — последним: рвём соединение до него,
        # ровно как реальный обрыв вкладки.
        chunks = [_Chunk(f'ток{i}') for i in range(20)] + [_Chunk(usage=_Usage())]
        for resp in self._post(chunks):
            stream = resp.streaming_content
            next(stream)  # init
            next(stream)  # первый токен
            resp.close()  # → GeneratorExit внутри generate() → finally

        msg = self._assistant()
        self.assertEqual(msg.status, Message.Status.FAILED)

        row = MessageTokenUsage.objects.get(message=msg)
        self.assertEqual(row.source, MessageTokenUsage.Source.MISSING)
        self.assertEqual(row.overage_kopecks, 0)
        self.assertEqual(row.settled_kopecks, 0)
        self.assertIsNone(row.settled_at)

        self.assertFalse(BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.OVERAGE).exists())
        # Плоское списание при обрыве не возвращается — предсуществующее
        # поведение, вне скоупа плана (§6). Фиксируем как есть, чтобы правка
        # этого поведения была осознанной, а не случайной.
        self.assertEqual(
            User.objects.get(pk=self.user.pk).balance_kopecks, 100000 - FLAT_KOPECKS)

    def test_provider_error_refunds_flat_and_settles_nothing(self):
        class _RaisingCompletions:
            def create(self, **kwargs):
                raise RuntimeError('upstream down')

        fake = _FakeClient([])
        fake.chat.completions = _RaisingCompletions()
        with patch('api.views.chats.get_client_for_network', return_value=fake):
            resp = self.client.post(self.url, {'message': 'привет', 'web_search': False}, format='json')
            body = b''.join(resp.streaming_content).decode('utf-8')

        self.assertIn('"type": "error"', body)
        msg = self._assistant()
        self.assertEqual(msg.status, Message.Status.FAILED)
        row = MessageTokenUsage.objects.get(message=msg)
        self.assertFalse(row.flat_was_charged)  # деньги возвращены
        self.assertEqual(row.settled_kopecks, 0)
        self.assertFalse(BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.OVERAGE).exists())
        self.assertEqual(User.objects.get(pk=self.user.pk).balance_kopecks, 100000)
