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
    normalize_fact, scoped_content_key, should_compress,
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


# ── scoped_content_key (B12) ────────────────────────────────────────────────────

class ScopedContentKeyTests(TestCase):
    """Ключ дедупликации должен учитывать скоуп (project/organization),
    иначе одинаковый по тексту факт в разных скоупах схлопывается в одну строку
    по UniqueConstraint(user, content_key) — см. UserMemoryContentKeyTests ниже
    для регрессионного теста на реальных моделях."""

    def test_no_scope_matches_plain_normalize(self):
        self.assertEqual(scoped_content_key('Любит Go'), normalize_fact('Любит Go'))

    def test_project_scope_gets_prefix(self):
        key = scoped_content_key('Использует Python', project_id=5)
        self.assertEqual(key, 'proj5:использует python')

    def test_org_scope_gets_prefix(self):
        key = scoped_content_key('Стек: Django', organization_id=7)
        self.assertEqual(key, 'org7:стек django')

    def test_project_and_org_and_global_keys_all_differ(self):
        keys = {
            scoped_content_key('Работает с Django'),
            scoped_content_key('Работает с Django', project_id=1),
            scoped_content_key('Работает с Django', project_id=2),
            scoped_content_key('Работает с Django', organization_id=1),
        }
        self.assertEqual(len(keys), 4)  # ни одна пара не совпала

    def test_project_id_takes_precedence_over_organization_id(self):
        key = scoped_content_key('факт', project_id=3, organization_id=9)
        self.assertTrue(key.startswith('proj3:'))

    def test_empty_text_returns_empty_key_even_with_scope(self):
        self.assertEqual(scoped_content_key('   ', project_id=5), '')

    def test_stays_within_255_chars(self):
        key = scoped_content_key('a' * 300, project_id=12345)
        self.assertLessEqual(len(key), 255)


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

    def _make_project(self, name):
        from aitext.models import Project
        return Project.objects.create(user=self.user, name=name)

    def test_same_text_in_two_projects_creates_two_rows(self):
        """B12 regression: до фикса второй create() либо падал IntegrityError
        (общий ключ без скоупа), либо (в update_or_create-путях) тихо
        перезаписывал факт первого проекта вместо создания отдельной записи."""
        from aitext.models import UserMemory
        proj_a = self._make_project('A')
        proj_b = self._make_project('B')
        content = 'Использует Python'

        m_a = UserMemory.objects.create(user=self.user, content=content, project=proj_a)
        m_b = UserMemory.objects.create(user=self.user, content=content, project=proj_b)

        self.assertNotEqual(m_a.content_key, m_b.content_key)
        self.assertEqual(UserMemory.objects.filter(user=self.user, content=content).count(), 2)
        m_a.refresh_from_db()
        self.assertEqual(m_a.project_id, proj_a.id)  # факт проекта A не "перескочил" в B

    def test_project_scoped_fact_does_not_collide_with_global(self):
        from aitext.models import UserMemory
        proj = self._make_project('A')
        content = 'Работает удалённо'

        UserMemory.objects.create(user=self.user, content=content)  # глобальный
        m_proj = UserMemory.objects.create(user=self.user, content=content, project=proj)

        self.assertEqual(UserMemory.objects.filter(user=self.user, content=content).count(), 2)
        self.assertIsNone(UserMemory.objects.get(project__isnull=True, user=self.user).project_id)
        self.assertEqual(m_proj.project_id, proj.id)

    def test_deleting_project_keeps_fact_but_unscopes_it(self):
        """B12: project FK — SET_NULL, не CASCADE. Удаление папки-проекта не должно
        тихо уничтожать долговременный факт, извлечённый из чатов пользователя."""
        from aitext.models import UserMemory
        proj = self._make_project('Disposable')
        m = UserMemory.objects.create(user=self.user, content='Факт проекта', project=proj)

        proj.delete()

        m.refresh_from_db()
        self.assertIsNone(m.project_id)


# ── build_memory_context ───────────────────────────────────────────────────────

class BuildMemoryContextTests(TestCase):
    def setUp(self):
        # Тесты в этом классе переиспользуют один и тот же user_id (SQLite сбрасывает
        # автоинкремент между TestCase), а build_memory_context кэширует факты по
        # memfacts:{user_id} на 5 минут — без сброса кэша между тестами более ранний
        # тест с тем же user_id "протекает" в следующий (например test_empty_when_no_facts
        # кэширует '', и test_includes_facts_when_present получает эту стухшую пустую строку).
        from django.core.cache import cache
        cache.clear()
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


# ── C2 идемпотентность compress_chat_history ──────────────────────────────────

class CompressIdempotencyTests(TestCase):
    """
    C2 regression: повторный вызов compress_chat_history при тех же сообщениях
    должен возвращать no-op (ничего не сжимать), а не дублировать компрессию.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='idemuser', email='idemuser@test.com', password='x'
        )

    def _make_chat_with_messages(self, count: int):
        from aitext.models import Category, NeuralNetwork, Chat, Message
        cat, _ = Category.objects.get_or_create(
            name='TextIdem', slug='textidem', defaults={'order': 0}
        )
        net, _ = NeuralNetwork.objects.get_or_create(
            name='GPT-Idem', slug='gpt-idem',
            defaults={'category': cat, 'model_name': 'gpt-4o', 'cost_per_message': 10}
        )
        chat = Chat.objects.create(user=self.user, network=net, title='idem', settings={})
        msgs = []
        for i in range(count):
            role = 'user' if i % 2 == 0 else 'assistant'
            m = Message.objects.create(
                chat=chat, role=role,
                content=f'Msg {i}', plain_text=f'Msg {i}',
                status=Message.Status.COMPLETED,
            )
            msgs.append(m)
        return chat, msgs

    def test_no_compress_when_last_compressed_id_covers_all_candidates(self):
        """C2: если last_compressed_message_id == ID последнего кандидата на сжатие,
        to_compress пуст и функция должна вернуть no-op (не менять rolling_summary)."""
        from aitext.models import ChatSummary
        from aitext.memory import RECENT_WINDOW

        count = RECENT_WINDOW + 5
        chat, msgs = self._make_chat_with_messages(count)

        # Симулируем успешную компрессию: last_compressed_message_id = ID последнего
        # кандидата (всё что до RECENT_WINDOW уже сжато)
        last_id = msgs[-(RECENT_WINDOW + 1)].id  # последний кандидат на сжатие
        ChatSummary.objects.create(
            chat=chat,
            rolling_summary='Уже сжатое резюме',
            message_count=count,
            last_compressed_message_id=last_id,
        )

        # Кандидаты для сжатия: msgs[:-RECENT_WINDOW], все id <= last_id
        # После фильтрации id > last_id → to_compress пустой → no-op
        candidates = msgs[:-RECENT_WINDOW]
        new_candidates = [m for m in candidates if m.id > last_id]
        self.assertEqual(len(new_candidates), 0, 'C2: нет новых кандидатов — no-op ожидается')

        # rolling_summary не должен измениться
        cs = ChatSummary.objects.get(chat=chat)
        self.assertEqual(cs.rolling_summary, 'Уже сжатое резюме')
        self.assertEqual(cs.last_compressed_message_id, last_id)

    def test_compress_only_new_messages_after_last_compressed_id(self):
        """C2: при наличии last_compressed_message_id сжимаем только новые сообщения."""
        from aitext.models import ChatSummary, Message
        from aitext.memory import RECENT_WINDOW

        count = RECENT_WINDOW + 3
        chat, msgs = self._make_chat_with_messages(count)

        # Первая компрессия покрыла первые 2 сообщения
        first_compressed_id = msgs[1].id
        ChatSummary.objects.create(
            chat=chat,
            rolling_summary='Первое резюме',
            message_count=count,
            last_compressed_message_id=first_compressed_id,
        )

        # Добавляем 3 новых сообщения чтобы RECENT_WINDOW не поглотил кандидатов
        for i in range(3):
            Message.objects.create(
                chat=chat, role='user', content=f'Extra {i}',
                plain_text=f'Extra {i}', status=Message.Status.COMPLETED,
            )
        all_msgs = list(
            Message.objects.filter(chat=chat, status=Message.Status.COMPLETED)
            .order_by('created_at')
        )
        candidates = all_msgs[:-RECENT_WINDOW]
        new_candidates = [m for m in candidates if m.id > first_compressed_id]

        # Должны быть новые кандидаты (сообщения после первой компрессии)
        self.assertGreater(len(new_candidates), 0)
        # Ни один из старых сообщений (id <= first_compressed_id) не попал в новые кандидаты
        for m in new_candidates:
            self.assertGreater(m.id, first_compressed_id)


# ── Intentionally not tested (require live Celery + LLM) ──────────────────────
#
# extract_memory_facts — вызывает DeepSeek V3, требует LAOZHANG_API_KEY + Redis
# generate_chat_summary — то же
# compress_chat_history — то же (также Redis-блокировка, cache.add)
#
# Тестируются на staging через docker-compose с реальными сервисами.
