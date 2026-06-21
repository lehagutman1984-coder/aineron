"""
Unit-тесты для Persistent Memory (детерминированная логика).

Что тестируем:
- estimate_tokens()
- build_memory_context() — структура вывода, тоггл
- get_history_with_compression() — сортировка, RECENT_WINDOW, exclude_msg_id
- UserMemory.save() — content_key генерация и дедупликация
- extract_memory_facts / generate_chat_summary — декларируем как not-tested (требуют Celery+LLM)

Запуск: python manage.py test aitext.test_memory --keepdb
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from aitext.memory import estimate_tokens, build_memory_context, RECENT_WINDOW

User = get_user_model()


class EstimateTokensTests(TestCase):
    def test_empty_string(self):
        self.assertEqual(estimate_tokens(''), 0)

    def test_none_like(self):
        self.assertEqual(estimate_tokens(None), 0)  # type: ignore

    def test_short_text(self):
        # 10 символов → примерно 1–4 токена
        result = estimate_tokens('hello word')
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 20)

    def test_proportional(self):
        short = estimate_tokens('a' * 100)
        long_ = estimate_tokens('a' * 1000)
        self.assertGreater(long_, short)


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
        self.assertNotIn(' ', m.content_key)

    def test_content_key_lowercase(self):
        from aitext.models import UserMemory
        m = UserMemory.objects.create(
            user=self.user, content='РАБОТАЕТ В МОСКВЕ', category='profile'
        )
        self.assertEqual(m.content_key, m.content_key.lower())

    def test_duplicate_prevented_by_constraint(self):
        from aitext.models import UserMemory
        from django.db import IntegrityError
        content = 'Python разработчик Senior'
        m1 = UserMemory.objects.create(user=self.user, content=content, category='skill')
        # Второй с тем же content_key должен выбросить IntegrityError
        with self.assertRaises(Exception):
            UserMemory.objects.create(
                user=self.user, content=content,
                content_key=m1.content_key, category='skill'
            )


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
        from aitext.models import Chat
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
                content=f'Message {i}',
                plain_text=f'Message {i}',
                status=Message.Status.COMPLETED,
            )
            msgs.append(m)
        return chat, msgs

    def test_small_history_returns_all(self):
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(5)
        result, rolling = get_history_with_compression(chat)
        self.assertEqual(len(result), 5)

    def test_large_history_returns_recent_window(self):
        from aitext.memory import get_history_with_compression
        chat, msgs = self._make_chat_with_messages(RECENT_WINDOW + 5)
        # Мокаем клиент чтобы не делать реальных вызовов
        with patch('aitext.memory.get_laozhang_client') as mock_client:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = 'Сжатое резюме'
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            result, rolling = get_history_with_compression(chat)
        # Должны получить не более RECENT_WINDOW сообщений
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
# get_history_with_compression (compression path) — проверяем только мок выше
#
# Эти задачи тестируются на staging через docker-compose с реальными сервисами.
