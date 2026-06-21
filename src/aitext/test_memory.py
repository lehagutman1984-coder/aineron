"""
Unit-тесты для Persistent Memory (детерминированная логика).

Что тестируем:
- estimate_tokens()
- normalize_fact()
- build_memory_context() — структура вывода, тоггл
- should_compress() — включая R1-регрессию
- get_history_with_compression() — сортировка, RECENT_WINDOW, exclude_msg_id
- UserMemory.save() — content_key генерация и дедупликация

Запуск: python manage.py test aitext.test_memory --keepdb
"""
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from aitext.memory import (
    estimate_tokens, build_memory_context,
    normalize_fact, should_compress,
    RECENT_WINDOW, COMPRESS_TRIGGER,
)

User = get_user_model()


# ── estimate_tokens ────────────────────────────────────────────────────────────

class EstimateTokensTests(TestCase):
    def test_empty_string(self):
        self.assertEqual(estimate_tokens(''), 0)

    def test_none_like(self):
        self.assertEqual(estimate_tokens(None), 0)  # type: ignore

    def test_short_text(self):
        result = estimate_tokens('hello word')
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 20)

    def test_proportional(self):
        short = estimate_tokens('a' * 100)
        long_ = estimate_tokens('a' * 1000)
        self.assertGreater(long_, short)


# ── normalize_fact ─────────────────────────────────────────────────────────────

class NormalizeFactTests(TestCase):
    """Чистые unit-тесты — БД не нужна."""

    def test_lowercases(self):
        self.assertEqual(normalize_fact('РАБОТАЕТ В МОСКВЕ'), 'работает в москве')

    def test_collapses_inner_spaces(self):
        self.assertEqual(normalize_fact('Любит  Go'), 'любит go')

    def test_no_false_collision_missing_space(self):
        self.assertNotEqual(normalize_fact('Любит Go'), normalize_fact('Любитgo'))

    def test_removes_punctuation(self):
        self.assertEqual(normalize_fact('Python-разработчик!'), 'pythonразработчик')

    def test_truncates_to_255(self):
        result = normalize_fact('a' * 300)
        self.assertEqual(len(result), 255)

    def test_empty_string(self):
        self.assertEqual(normalize_fact(''), '')

    def test_none_safe(self):
        self.assertEqual(normalize_fact(None), '')  # type: ignore


# ── UserMemory content_key ─────────────────────────────────────────────────────

class UserMemoryContentKeyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='memtest', email='memtest@test.com', password='x'
        )

    def test_content_key_generated_on_save(self):
        from aitext.models import UserMemory
        m = UserMemory.objects.create(
            user=self.user, content='Python разработчик', category='skill'
        )
        self.assertTrue(len(m.content_key) > 0)
        self.assertEqual(m.content_key, normalize_fact('Python разработчик'))

    def test_content_key_lowercase(self):
        from aitext.models import UserMemory
        m = UserMemory.objects.create(
            user=self.user, content='РАБОТАЕТ В МОСКВЕ', category='profile'
        )
        self.assertEqual(m.content_key, m.content_key.lower())

    def test_duplicate_prevented_by_constraint(self):
        from aitext.models import UserMemory
        content = 'Python разработчик Senior'
        m1 = UserMemory.objects.create(user=self.user, content=content, category='skill')
        with self.assertRaises(Exception):
            UserMemory.objects.create(
                user=self.user, content=content,
                content_key=m1.content_key, category='skill'
            )


# ── build_memory_context ───────────────────────────────────────────────────────

class BuildMemoryContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ctxuser', email='ctxuser@test.com', password='x'
        )

    def _make_chat(self):
        from aitext.models import Category, NeuralNetwork, Chat
        cat, _ = Category.objects.get_or_create(
            name='Текст', slug='text', defaults={'order': 0}
        )
        net, _ = NeuralNetwork.objects.get_or_create(
            name='Test GPT', slug='test-gpt',
            defaults={'category': cat, 'model_name': 'gpt-4o', 'cost_per_message': 10}
        )
        return Chat.objects.create(user=self.user, network=net, title='test', settings={})

    def test_returns_empty_when_memory_disabled(self):
        self.user.memory_enabled = False
        self.user.save()
        chat = self._make_chat()
        result = build_memory_context(self.user, chat)
        self.assertEqual(result, '')

    def test_returns_empty_when_per_chat_disabled(self):
        chat = self._make_chat()
        chat.settings = {'memory_enabled': False}
        chat.save()
        result = build_memory_context(self.user, chat)
        self.assertEqual(result, '')

    def test_includes_facts_when_present(self):
        from aitext.models import UserMemory
        chat = self._make_chat()
        UserMemory.objects.create(
            user=self.user,
            content='Работает с Django',
            category='skill',
        )
        result = build_memory_context(self.user, chat)
        self.assertIn('Django', result)
        self.assertIn('Долговременная память', result)

    def test_empty_when_no_facts(self):
        chat = self._make_chat()
        result = build_memory_context(self.user, chat)
        self.assertEqual(result, '')

    def test_excludes_inactive_facts(self):
        from aitext.models import UserMemory
        chat = self._make_chat()
        UserMemory.objects.create(
            user=self.user, content='Старый факт',
            category='fact', is_active=False
        )
        result = build_memory_context(self.user, chat)
        self.assertEqual(result, '')


# ── should_compress ────────────────────────────────────────────────────────────

class ShouldCompressTests(TestCase):
    """
    Тесты для should_compress() — включая R1-регрессию.

    R1: после компрессии ONE новое сообщение НЕ должно ретриггерить компрессию.
    Bug: старый код хранил message_count = msg_count - RECENT_WINDOW (30-20=10),
         затем 31-10=21 ≥ RECENT_WINDOW=20 → ретриггер на каждое сообщение.
    Fix: храним total msg_count (30), затем 31-30=1 < 20 → нет ретриггера.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='compuser', email='compuser@test.com', password='x'
        )

    def _make_chat_with_messages(self, count: int):
        from aitext.models import Category, NeuralNetwork, Chat, Message
        cat, _ = Category.objects.get_or_create(
            name='ТекстC', slug='textc', defaults={'order': 0}
        )
        net, _ = NeuralNetwork.objects.get_or_create(
            name='GPT-C', slug='gpt-c',
            defaults={'category': cat, 'model_name': 'gpt-4o', 'cost_per_message': 10}
        )
        chat = Chat.objects.create(user=self.user, network=net, title='c', settings={})
        for i in range(count):
            role = 'user' if i % 2 == 0 else 'assistant'
            Message.objects.create(
                chat=chat, role=role,
                content=f'Msg {i}', plain_text=f'Msg {i}',
                status=Message.Status.COMPLETED,
            )
        return chat

    def test_no_compress_below_trigger(self):
        chat = self._make_chat_with_messages(COMPRESS_TRIGGER - 1)
        self.assertFalse(should_compress(chat))

    def test_compress_triggered_at_threshold(self):
        chat = self._make_chat_with_messages(COMPRESS_TRIGGER)
        self.assertTrue(should_compress(chat))

    def test_r1_regression_no_repeat_after_first_compression(self):
        """R1 regression: one new message after compression must NOT retrigger."""
        from aitext.models import ChatSummary, Message
        msg_count = COMPRESS_TRIGGER
        chat = self._make_chat_with_messages(msg_count)

        # Симулируем compress_chat_history с R1-исправлением (хранит total)
        ChatSummary.objects.create(
            chat=chat,
            rolling_summary='Сжатое резюме',
            message_count=msg_count,  # TOTAL — правильное поведение после R1-fix
        )

        # Добавляем ОДНО новое сообщение
        Message.objects.create(
            chat=chat, role='user', content='Новое сообщение',
            plain_text='Новое сообщение', status=Message.Status.COMPLETED,
        )

        # НЕ должно тригерить: накопилось только 1 новое сообщение (< RECENT_WINDOW)
        self.assertFalse(should_compress(chat))

    def test_compress_retriggers_after_full_window(self):
        """После RECENT_WINDOW новых сообщений с момента компрессии — ретриггер."""
        from aitext.models import ChatSummary, Message
        msg_count = COMPRESS_TRIGGER
        chat = self._make_chat_with_messages(msg_count)
        ChatSummary.objects.create(
            chat=chat, rolling_summary='Резюме', message_count=msg_count,
        )
        for i in range(RECENT_WINDOW):
            Message.objects.create(
                chat=chat, role='user', content=f'New {i}',
                plain_text=f'New {i}', status=Message.Status.COMPLETED,
            )
        self.assertTrue(should_compress(chat))


# ── get_history_with_compression ──────────────────────────────────────────────

class GetHistoryWithCompressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='histuser', email='histuser@test.com', password='x'
        )

    def _make_chat_with_messages(self, count: int):
        from aitext.models import Category, NeuralNetwork, Chat, Message
        cat, _ = Category.objects.get_or_create(
            name='Текст2', slug='text2', defaults={'order': 0}
        )
        net, _ = NeuralNetwork.objects.get_or_create(
            name='GPT2', slug='gpt-2',
            defaults={'category': cat, 'model_name': 'gpt-4o', 'cost_per_message': 10}
        )
        chat = Chat.objects.create(user=self.user, network=net, title='t', settings={})
        msgs = []
        for i in range(count):
            role = 'user' if i % 2 == 0 else 'assistant'
            m = Message.objects.create(
                chat=chat, role=role,
                content=f'Message {i}', plain_text=f'Message {i}',
                status=Message.Status.COMPLETED,
            )
            msgs.append(m)
        return chat, msgs

    def test_small_history_returns_all(self):
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(5)
        result, rolling = get_history_with_compression(chat)
        self.assertEqual(len(result), 5)

    def test_large_history_truncated_to_recent_window(self):
        """Ветка token-overflow: при маленьком контекстном окне возвращаем RECENT_WINDOW."""
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(RECENT_WINDOW + 5)
        # Форсируем крошечное контекстное окно чтобы сработал token-overflow
        with patch('aitext.memory._get_context_window', return_value=1):
            result, rolling = get_history_with_compression(chat)
        self.assertLessEqual(len(result), RECENT_WINDOW)

    def test_exclude_msg_id_works(self):
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(5)
        excluded_id = msgs[-1].id
        result, _ = get_history_with_compression(chat, exclude_msg_id=excluded_id)
        result_ids = [m.id for m in result]
        self.assertNotIn(excluded_id, result_ids)

    def test_messages_ordered_chronologically(self):
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(5)
        result, _ = get_history_with_compression(chat)
        created_ats = [m.created_at for m in result]
        self.assertEqual(created_ats, sorted(created_ats))


# ── Intentionally not tested (require live Celery + LLM) ──────────────────────
#
# extract_memory_facts — вызывает DeepSeek V3, требует LAOZHANG_API_KEY + Redis
# generate_chat_summary — то же
# compress_chat_history — то же (также Redis-блокировка, cache.add)
#
# Тестируются на staging через docker-compose с реальными сервисами.
