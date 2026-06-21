# PERSISTENT MEMORY — План реализации (production-grade)

> **Статус:** НЕ реализовано. Этот документ — полная, самодостаточная спецификация.
> Разработчик может реализовать всё по порядку коммитов, **не принимая ни одного архитектурного решения** — все решения приняты здесь.
>
> **Цель:** дать aineron.ru долговременную память пользователя уровня ChatGPT Memory и Claude Projects — но лучше: **единая память, общая для веб-чата, Telegram-бота и Studio**, без списания дополнительных звёзд.

---

## 0. TL;DR для занятого разработчика

1. Две новые модели в `aitext`: `UserMemory` (привязана к **пользователю**, общая на все каналы) и `ChatSummary` (привязана к **чату**). Миграция `aitext/0010`.
2. Один новый флаг `memory_enabled` на `CustomUser`. Отдельная миграция `users/00XX`.
3. Per-chat тоггл хранится в существующем `Chat.settings` JSON (`settings['memory_enabled']`) — **без миграции**.
4. Новый модуль `src/aitext/memory.py`: `build_memory_context()`, `get_history_with_compression()`, `estimate_tokens()`.
5. Две Celery-задачи в `src/aitext/tasks_memory.py`: `extract_memory_facts()` (с дедупликацией) и `generate_chat_summary()`.
6. **Ровно 2 точки интеграции** в backend:
   - `src/aitext/tasks.py:281` (Celery `generate_ai_response` — текстовый путь)
   - `src/api/views/chats.py:355` (SSE `StreamMessageView`)
7. **Telegram-бот и Studio получают память бесплатно**: бот вызывает ту же задачу `generate_ai_response.delay(...)` (подтверждено: `telegram_bot/handlers/chat.py:95`), поэтому правка `tasks.py:281` автоматически включает память в боте. Отдельного кода в `telegram_bot/` не требуется.
8. DRF API: новый `src/api/views/memory.py` + роуты `/api/v1/memory/...`.
9. Frontend: страница `/account/memory/`, индикатор памяти в чате, тоггл в настройках чата.
10. **Phase 2 (RAG):** pgvector + семантический поиск по фактам, переиспользует существующую инфраструктуру эмбеддингов (`src/api/views/embeddings.py`).

### Что такое «память» (без магии)

Память — это **три механизма поверх обычного LLM API**:

1. **Дискретные факты** (`UserMemory`) — атомарные записи о пользователе, извлечённые автоматически или добавленные вручную. Инжектируются в system-prompt каждого запроса.
2. **In-session compression** (`ChatSummary`) — когда диалог длинный, старые сообщения сжимаются в текстовое резюме. Именно это создаёт ощущение, что ИИ «помнит» начало длинного разговора. Сейчас стоит жёсткое отсечение `[:20]` в **двух местах** — его и заменяем.
3. **Cross-channel facts** — факты привязаны к пользователю, а не к чату/каналу, поэтому работают одинаково в web, Telegram и Studio.

DeepSeek V3 через laozhang.ai — единственная модель для всех фоновых задач памяти (дёшево, быстро, достаточно умно).

---

## 1. Архитектура

### 1.1. Слои памяти

| Слой | Что хранит | Привязка | Время жизни | Кто пишет |
|------|-----------|----------|-------------|-----------|
| **Working memory** | последние N сообщений | чат | до сжатия | существующий код |
| **Chat summary** (`ChatSummary`) | сжатое резюме старых сообщений чата | **чат** | пока жив чат | `generate_chat_summary` |
| **User memory** (`UserMemory`) | устойчивые факты о пользователе (имя, проекты, предпочтения, стиль) | **пользователь** | бессрочно (пока не удалит) | `extract_memory_facts` |
| **Semantic memory** (Phase 2) | эмбеддинги фактов для RAG-поиска | пользователь | бессрочно | `extract_memory_facts` + embeddings |

**Ключевой принцип общей памяти:**
`UserMemory.user → CustomUser`. Память **не** привязана к чату или каналу. Один и тот же пользователь в веб-чате, в Telegram-боте и в Studio видит одни и те же факты о себе — потому что `TelegramChat.chat → aitext.Chat → Chat.user`, и все каналы в конечном счёте резолвятся в один `CustomUser`.

`ChatSummary.chat → Chat` — резюме всегда про конкретный чат.

### 1.2. Диаграмма потоков данных (ASCII)

```
                         ┌──────────────────────────────────────────────┐
   ВХОДНЫЕ КАНАЛЫ        │                                              │
                         │                                              │
  ┌─────────────┐        │   ┌────────────────────────────────────┐    │
  │  WEB CHAT   │───SSE──┼──▶│  api/views/chats.py                 │    │
  │ (Next.js)   │        │   │  StreamMessageView  (стр. 355)      │    │
  └─────────────┘        │   └─────────────┬──────────────────────┘    │
                         │                 │                            │
  ┌─────────────┐        │   ┌─────────────▼──────────────────────┐    │
  │ TELEGRAM    │─delay─▶│   │  aitext/tasks.py                    │    │
  │ BOT(aiogram)│        │   │  generate_ai_response (стр. 281)    │    │
  └─────────────┘        │   └─────────────┬──────────────────────┘    │
        │                │                 │                            │
  ┌─────────────┐        │                 │  обе точки вызывают:       │
  │   STUDIO    │─delay─▶│                 ▼                            │
  └─────────────┘        │   ┌────────────────────────────────────┐    │
                         │   │  aitext/memory.py                   │    │
                         │   │  build_memory_context(user, chat)   │    │
                         │   │  get_history_with_compression(chat) │    │
                         │   └──────┬───────────────────┬─────────┘    │
                         │          │                   │              │
                         │   ┌──────▼──────┐     ┌──────▼──────┐       │
                         │   │ UserMemory  │     │ ChatSummary │       │
                         │   │ (per USER)  │     │ (per CHAT)  │       │
                         │   └─────────────┘     └─────────────┘       │
                         │          ▲                   ▲              │
                         │          │                   │              │
                         │   ┌──────┴───────────────────┴─────────┐    │
   ФОНОВЫЕ ЗАДАЧИ        │   │  aitext/tasks_memory.py             │    │
   (Celery+DeepSeek V3)  │   │  extract_memory_facts  (после ответа)│   │
                         │   │  generate_chat_summary (по триггеру) │   │
                         │   └────────────────────────────────────┘    │
                         │                                              │
                         └──────────────────────────────────────────────┘

  Сборка контекста перед вызовом LLM (порядок messages_for_api):
    [system: network.prompt / project.system_prompt]
    [system: USER MEMORY block]      ← из UserMemory (build_memory_context)
    [system: CHAT SUMMARY block]     ← из ChatSummary (get_history_with_compression)
    [... последние N несжатых сообщений ...]
    [user: текущее сообщение]
```

### 1.3. Жизненный цикл

```
Пользователь пишет сообщение
        │
        ▼
Создаётся Message(assistant, pending) ──▶ generate_ai_response.delay(...)
        │
        ▼
build_memory_context(user, chat)  +  get_history_with_compression(chat)
  → собирается messages_for_api с блоками памяти
        │
        ▼
LLM генерирует ответ (стриминг)
        │
        ▼
После завершения ответа:
  ├─ extract_memory_facts.delay(chat_id, user_msg_id, assistant_msg_id)
  │     → DeepSeek V3 извлекает факты → дедуп → UserMemory.get_or_create
  └─ generate_chat_summary.delay(chat_id)
        → внутри проверяет should_summarize(); если порог достигнут — сжимает
```

---

## 2. Конкурентное сравнение

| Возможность | ChatGPT Memory | Claude Projects | **aineron.ru (этот план)** |
|-------------|----------------|-----------------|----------------------------|
| Автоизвлечение фактов | да | нет (ручной контекст) | **да (DeepSeek V3, фон)** |
| Общая память между чатами | да | в рамках проекта | **да (per-user)** |
| Память в мессенджере | приложение | приложение | **да, в Telegram-боте (уникально)** |
| Сжатие длинных диалогов | частично | да (context window) | **да (ChatSummary)** |
| Управление фактами пользователем | да (просмотр/удаление) | — | **да (/account/memory/, категории)** |
| Per-chat отключение | нет | — | **да (Chat.settings)** |
| Семантический поиск по памяти | нет (публично) | — | **да (Phase 2, pgvector)** |
| Доплата за память | входит в подписку | входит | **0 звёзд (фон на дешёвом DeepSeek)** |

---

## 3. Django-модели

### 3.1. `aitext/models.py` — добавить в конец файла

```python
from django.db.models import F  # добавить к импортам, если ещё нет


class UserMemory(models.Model):
    """
    Долговременный факт о пользователе. Общий для всех каналов
    (веб-чат, Telegram-бот, Studio) — привязан к пользователю, не к чату.
    """
    class Category(models.TextChoices):
        PROFILE = 'profile', 'Профиль'             # имя, профессия, язык
        PREFERENCE = 'preference', 'Предпочтения'  # стиль ответов, формат
        PROJECT = 'project', 'Проекты'             # над чем работает
        FACT = 'fact', 'Факты'                     # прочие устойчивые факты
        SKILL = 'skill', 'Навыки/уровень'          # экспертиза, стек

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memories',
        verbose_name='Пользователь',
    )
    category = models.CharField(
        max_length=20, choices=Category.choices,
        default=Category.FACT, verbose_name='Категория',
    )
    content = models.TextField(verbose_name='Факт')
    # Нормализованный ключ для дедупликации (lowercase, без пунктуации).
    content_key = models.CharField(
        max_length=255, db_index=True, blank=True,
        verbose_name='Ключ дедупликации',
    )
    source_chat = models.ForeignKey(
        'Chat', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='extracted_memories', verbose_name='Чат-источник',
    )
    confidence = models.FloatField(default=1.0, verbose_name='Уверенность')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    # Закреплён пользователем вручную — не удаляется автоочисткой.
    is_pinned = models.BooleanField(default=False, verbose_name='Закреплён')
    times_referenced = models.PositiveIntegerField(default=0, verbose_name='Раз использован')
    # Phase 2: эмбеддинг для семантического поиска (заполняется позже).
    # embedding = VectorField(dimensions=1536, null=True, blank=True)  # см. Phase 2
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Память пользователя'
        verbose_name_plural = 'Память пользователей'
        ordering = ['-is_pinned', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content_key'],
                name='uniq_user_memory_key',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'is_active'], name='um_user_active_idx'),
            models.Index(fields=['user', 'category'], name='um_user_cat_idx'),
        ]

    def __str__(self):
        return f'{self.user_id}: {self.content[:50]}'


class ChatSummary(models.Model):
    """
    Сжатое резюме старых сообщений конкретного чата.
    Заменяет «выпавшие» из окна сообщения, экономит токены.
    """
    chat = models.OneToOneField(
        'Chat', on_delete=models.CASCADE,
        related_name='summary', verbose_name='Чат',
    )
    content = models.TextField(verbose_name='Резюме диалога')
    # До какого сообщения (включительно) учтено в резюме.
    last_message_id = models.PositiveIntegerField(
        default=0, verbose_name='ID последнего учтённого сообщения',
    )
    messages_count = models.PositiveIntegerField(
        default=0, verbose_name='Сколько сообщений сжато',
    )
    token_estimate = models.PositiveIntegerField(
        default=0, verbose_name='Оценка токенов резюме',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Резюме чата'
        verbose_name_plural = 'Резюме чатов'

    def __str__(self):
        return f'Резюме чата #{self.chat_id} ({self.messages_count} сообщ.)'
```

### 3.2. `users/models.py` — добавить поле в `CustomUser`

(вставить рядом с прочими полями `CustomUser`, например после блока «Безопасность»)

```python
    # Persistent Memory — глобальный тоггл памяти (по умолчанию включена)
    memory_enabled = models.BooleanField(
        default=True,
        verbose_name='Долговременная память включена',
    )
```

### 3.3. Per-chat тоггл — БЕЗ миграции

Используем существующее поле `Chat.settings` (JSONField). Память для чата включена, если:

```python
user.memory_enabled and chat.settings.get('memory_enabled', True)
```

Пользователь может выключить память глобально либо точечно для конкретного чата.

### 3.4. Миграции

**Миграция `aitext/migrations/0010_user_memory_chat_summary.py`** (после `0009_message_search_context`).
Сгенерировать: `python manage.py makemigrations aitext`. Проверить, что номер = `0010` и зависимость = `0009_message_search_context`.

**Миграция `users/migrations/00XX_customuser_memory_enabled.py`** (отдельная, в приложении `users`):

```python
class Migration(migrations.Migration):
    dependencies = [('users', '<последняя миграция users>')]
    operations = [
        migrations.AddField(
            model_name='customuser',
            name='memory_enabled',
            field=models.BooleanField(default=True, verbose_name='Долговременная память включена'),
        ),
    ]
```

Сгенерировать: `python manage.py makemigrations users`.

> Итого ровно 2 новые миграции. Это намеренно: модели памяти живут в `aitext`, флаг пользователя — в `users`.

---

## 4. `src/aitext/memory.py` (новый файл)

```python
"""
Persistent Memory — сборка контекста памяти и сжатие истории.

Используется из двух точек интеграции:
  - aitext/tasks.py (Celery generate_ai_response)
  - api/views/chats.py (SSE StreamMessageView)
"""
import logging
import re

from django.db.models import F

from .models import Message, UserMemory, ChatSummary

logger = logging.getLogger(__name__)

# Сколько последних сообщений держим «как есть» (несжатыми).
RECENT_WINDOW = 20
# Если несжатых сообщений больше этого порога — запускаем суммаризацию.
SUMMARY_TRIGGER = 30
# Сколько фактов максимум вставляем в контекст.
MAX_MEMORY_FACTS = 40
# Грубая оценка: ~4 символа на токен (англ./рус. смешанный).
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Грубая оценка количества токенов по длине строки."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def normalize_fact(text: str) -> str:
    """Нормализация факта для дедупликации: lowercase, без пунктуации, схлоп пробелов."""
    t = text.lower().strip()
    t = re.sub(r'[^\w\s]', '', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t)
    return t[:255]


def memory_enabled_for(user, chat) -> bool:
    """Память включена, если включена и глобально, и для этого чата."""
    if not getattr(user, 'memory_enabled', True):
        return False
    try:
        return bool(chat.settings.get('memory_enabled', True))
    except Exception:
        return True


def build_memory_context(user, chat, max_facts: int = MAX_MEMORY_FACTS):
    """
    Возвращает system-сообщение с фактами о пользователе, либо None.
    Формат: {"role": "system", "content": "..."}.
    """
    if not memory_enabled_for(user, chat):
        return None

    facts = list(
        UserMemory.objects
        .filter(user=user, is_active=True)
        .order_by('-is_pinned', '-times_referenced', '-updated_at')[:max_facts]
    )
    if not facts:
        return None

    # Группируем по категориям для читаемости.
    by_cat = {}
    for f in facts:
        by_cat.setdefault(f.get_category_display(), []).append(f.content)

    lines = ["Ниже — то, что ты знаешь о пользователе из прошлых диалогов. "
             "Используй это, чтобы отвечать персонализированно. "
             "Не упоминай явно, что у тебя есть «память», если пользователь не спрашивает."]
    for cat, items in by_cat.items():
        lines.append(f"\n[{cat}]")
        for it in items:
            lines.append(f"- {it}")

    # Отметим, что факты использованы (для приоритезации).
    UserMemory.objects.filter(id__in=[f.id for f in facts]).update(
        times_referenced=F('times_referenced') + 1
    )

    return {"role": "system", "content": "\n".join(lines)}


def get_history_with_compression(chat, exclude_message_id=None):
    """
    Возвращает (summary_system_message_or_None, recent_messages_list).

    recent_messages — последние RECENT_WINDOW завершённых сообщений (хронологически).
    summary — system-сообщение из ChatSummary, если оно покрывает более старые сообщения.
    """
    qs = chat.messages.filter(status=Message.Status.COMPLETED)
    if exclude_message_id:
        qs = qs.exclude(id=exclude_message_id)

    recent = list(qs.order_by('-created_at')[:RECENT_WINDOW])
    recent.reverse()

    summary_msg = None
    summary = getattr(chat, 'summary', None)
    if summary and summary.content:
        oldest_recent_id = recent[0].id if recent else None
        # Резюме показываем только если есть сообщения старше окна.
        if oldest_recent_id and summary.last_message_id < oldest_recent_id:
            summary_msg = {
                "role": "system",
                "content": f"Краткое содержание более ранней части диалога:\n{summary.content}",
            }

    return summary_msg, recent


def should_summarize(chat) -> bool:
    """Нужно ли запускать суммаризацию для чата."""
    completed = chat.messages.filter(status=Message.Status.COMPLETED).count()
    summary = getattr(chat, 'summary', None)
    covered = summary.messages_count if summary else 0
    return (completed - covered) > SUMMARY_TRIGGER
```

---

## 5. Celery-задачи: `src/aitext/tasks_memory.py` (новый файл)

```python
"""
Фоновые задачи Persistent Memory. Все вызовы LLM — DeepSeek V3 через laozhang.ai
(дёшево, быстро). Пользователю звёзды НЕ списываются.
"""
import json
import logging

from celery import shared_task

from .models import Message, UserMemory, ChatSummary, Chat
from .memory import normalize_fact, estimate_tokens, should_summarize, RECENT_WINDOW
from .tasks import get_laozhang_client

logger = logging.getLogger(__name__)

MEMORY_MODEL = 'deepseek-v3'

EXTRACT_SYSTEM_PROMPT = """Ты — система извлечения долговременных фактов о пользователе.
Из диалога извлеки УСТОЙЧИВЫЕ факты, полезные в будущих беседах: имя, профессия, язык,
проекты, предпочтения по стилю ответов, уровень экспертизы, инструменты/стек.
НЕ извлекай: разовые вопросы, эфемерный контекст, чувствительные данные
(пароли, номера карт, паспорта).
Верни СТРОГО JSON-массив объектов вида:
[{"category": "profile|preference|project|fact|skill", "content": "<краткий факт на русском>"}]
Если устойчивых фактов нет — верни []."""


def _parse_facts(raw: str):
    """Безопасный парсинг JSON-массива фактов из ответа LLM."""
    try:
        start = raw.find('[')
        end = raw.rfind(']')
        if start == -1 or end == -1:
            return []
        return json.loads(raw[start:end + 1])
    except Exception:
        return []


@shared_task(bind=True, max_retries=2)
def extract_memory_facts(self, chat_id, user_message_id, assistant_message_id):
    """Извлекает факты из последней пары сообщений и сохраняет в UserMemory (с дедупом)."""
    try:
        chat = Chat.objects.select_related('user').get(id=chat_id)
    except Chat.DoesNotExist:
        return
    user = chat.user
    if not getattr(user, 'memory_enabled', True):
        return
    if not chat.settings.get('memory_enabled', True):
        return

    try:
        user_msg = Message.objects.get(id=user_message_id)
        assistant_msg = Message.objects.get(id=assistant_message_id)
    except Message.DoesNotExist:
        return

    dialogue = (
        f"Пользователь: {user_msg.content}\n"
        f"Ассистент: {assistant_msg.plain_text or assistant_msg.content}"
    )

    client = get_laozhang_client()
    try:
        resp = client.chat.completions.create(
            model=MEMORY_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": dialogue[:6000]},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f'[memory] extract LLM error chat={chat_id}: {e}')
        raise self.retry(exc=e, countdown=30)

    facts = _parse_facts(raw)
    if not facts:
        return

    created = 0
    for fact in facts:
        content = (fact.get('content') or '').strip()
        category = fact.get('category', 'fact')
        if not content or len(content) < 3:
            continue
        if category not in dict(UserMemory.Category.choices):
            category = 'fact'
        key = normalize_fact(content)
        if not key:
            continue
        # Дедуп Phase 1: уникальность по (user, content_key) на уровне БД.
        _, was_created = UserMemory.objects.get_or_create(
            user=user, content_key=key,
            defaults={'content': content, 'category': category, 'source_chat': chat},
        )
        if was_created:
            created += 1
    logger.info(f'[memory] chat={chat_id}: +{created} фактов (из {len(facts)})')


SUMMARY_SYSTEM_PROMPT = """Ты сжимаешь диалог в краткое содержание для дальнейшего контекста.
Сохрани: ключевые темы, решения, факты, незавершённые задачи, договорённости.
Пиши на русском, до 250 слов, без воды. Не выдумывай."""


@shared_task(bind=True, max_retries=2)
def generate_chat_summary(self, chat_id):
    """Сжимает старые сообщения чата в ChatSummary, если достигнут порог."""
    try:
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist:
        return
    if not should_summarize(chat):
        return

    completed = list(
        chat.messages.filter(status=Message.Status.COMPLETED).order_by('created_at')
    )
    if len(completed) <= RECENT_WINDOW:
        return

    to_compress = completed[:-RECENT_WINDOW]  # всё, кроме окна последних
    last_id = to_compress[-1].id
    existing = getattr(chat, 'summary', None)

    parts = []
    if existing and existing.content:
        parts.append(f"Предыдущее резюме:\n{existing.content}\n")
    for m in to_compress:
        text = m.plain_text or m.content
        if text:
            role = 'Пользователь' if m.role == 'user' else 'Ассистент'
            parts.append(f"{role}: {text}")
    dialogue = "\n".join(parts)[:20000]

    client = get_laozhang_client()
    try:
        resp = client.chat.completions.create(
            model=MEMORY_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": dialogue},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        summary_text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f'[memory] summary LLM error chat={chat_id}: {e}')
        raise self.retry(exc=e, countdown=60)

    ChatSummary.objects.update_or_create(
        chat=chat,
        defaults={
            'content': summary_text,
            'last_message_id': last_id,
            'messages_count': len(to_compress),
            'token_estimate': estimate_tokens(summary_text),
        },
    )
    logger.info(f'[memory] chat={chat_id}: резюме обновлено ({len(to_compress)} сообщ.)')
```

### 5.1. Расписание / триггеры

- `extract_memory_facts` — **по событию** (не cron): `.delay(...)` сразу после успешной генерации ответа в обеих точках интеграции.
- `generate_chat_summary` — **по событию + проверка порога**: `.delay(chat_id)` после ответа; внутри проверяет `should_summarize()` и тихо выходит, если порог не достигнут.
- (Phase 1.5, опционально) `prune_stale_memories` — ночной cron beat: удаляет `is_active=True, is_pinned=False, times_referenced=0`, старше 180 дней.

---

## 6. Точки интеграции (ТОЧНЫЕ номера строк)

> **Важно:** Telegram-бот и Studio вызывают `aitext.tasks.generate_ai_response.delay(...)`
> (подтверждено: `telegram_bot/handlers/chat.py:95`, `images.py:97`, `video_cmd.py:78`, `inline.py:107`).
> Правка точки №1 (`tasks.py`) автоматически даёт память **во всех трёх каналах** для текстового пути.
> Отдельного кода в `telegram_bot/` или `studio/` НЕ требуется.

### 6.1. Точка №1 — `src/aitext/tasks.py`, строка 281

**Было** (строки 280-282):
```python
        # Получаем последние 20 сообщений из истории
        history_qs = chat.messages.filter(status=Message.Status.COMPLETED).order_by('-created_at')[:20]
        history = list(reversed(history_qs))
```

**Стало:**
```python
        from .memory import build_memory_context, get_history_with_compression

        user = chat.user
        summary_msg, history = get_history_with_compression(chat, exclude_message_id=message.id)
```

Затем, **после** блока, где добавляются system-промты проекта/сети (после строки ~295, сразу за `network.prompt`-блоком) — вставить:
```python
        # ── Persistent Memory ──────────────────────────────────────────
        mem_msg = build_memory_context(user, chat)
        if mem_msg:
            messages_for_api.append(mem_msg)
        if summary_msg:
            messages_for_api.append(summary_msg)
        # ───────────────────────────────────────────────────────────────
```

Существующий цикл `for msg in history:` (строки 298+) остаётся без изменений — `history` теперь уже без сжатых сообщений.

**После завершения генерации** (где `message.status = Message.Status.COMPLETED` и `message.save()` в конце текстового пути) добавить:
```python
        from .tasks_memory import extract_memory_facts, generate_chat_summary
        if user_msg:
            extract_memory_facts.delay(chat.id, user_msg.id, message.id)
        generate_chat_summary.delay(chat.id)
```

### 6.2. Точка №2 — `src/api/views/chats.py`, строка 355

**Было** (строки 350-357):
```python
        max_input_tokens = network.max_input_tokens
        history_qs = (
            chat.messages
            .filter(status=Message.Status.COMPLETED)
            .exclude(id=user_message.id)
            .order_by('-created_at')[:20]
        )
        history = list(reversed(history_qs))
```

**Стало:**
```python
        from aitext.memory import build_memory_context, get_history_with_compression

        max_input_tokens = network.max_input_tokens
        summary_msg, history = get_history_with_compression(
            chat, exclude_message_id=user_message.id
        )
```

Затем, **после** блока system-промтов (после строки ~369, за `network.prompt`-блоком) — вставить:
```python
        # ── Persistent Memory ──────────────────────────────────────────
        mem_msg = build_memory_context(request.user, chat)
        if mem_msg:
            messages_for_api.append(mem_msg)
        if summary_msg:
            messages_for_api.append(summary_msg)
        # ───────────────────────────────────────────────────────────────
```

**После завершения SSE-стрима** (где `assistant_message` финализируется как COMPLETED) добавить:
```python
        from aitext.tasks_memory import extract_memory_facts, generate_chat_summary
        extract_memory_facts.delay(chat.id, user_message.id, assistant_message.id)
        generate_chat_summary.delay(chat.id)
```

> Обе точки переходят от хардкода `[:20]` к `get_history_with_compression`, где окно = `RECENT_WINDOW` (тоже 20, но теперь конфигурируемо и дополнено резюме).

---

## 7. Telegram-бот: интеграция (нулевой код)

Telegram-бот **не требует отдельной реализации памяти**:

1. `telegram_bot/handlers/chat.py:95` вызывает `generate_ai_response.delay(assistant_msg.id, ...)` — ту же Celery-задачу, что и веб.
2. `TelegramChat.chat` → `aitext.Chat` → `Chat.user` → `CustomUser`. Память (`UserMemory.user`) уже привязана к тому же `CustomUser`.
3. Факты из веб-чата автоматически видны в боте, и наоборот — **единая память между web и Telegram из коробки**.

Опциональные улучшения бота (Phase 1.5, не обязательны для MVP):
- Команда `/memory` — показать список фактов (тот же сервис, что и API).
- В `/settings` бота — тоггл памяти (пишет в `user.memory_enabled`).

Studio (`src/studio/`) — аналогично: текстовая генерация через `generate_ai_response` получает память без изменений.

---

## 8. DRF API: `src/api/views/memory.py` (новый файл) + роуты

### 8.1. Эндпоинты

| Метод | Путь | Назначение |
|-------|------|-----------|
| `GET` | `/api/v1/memory/` | список фактов пользователя (фильтр `?category=`) |
| `POST` | `/api/v1/memory/` | создать факт вручную |
| `PATCH` | `/api/v1/memory/<id>/` | редактировать факт / pin / активность |
| `DELETE` | `/api/v1/memory/<id>/` | удалить факт |
| `DELETE` | `/api/v1/memory/clear/` | очистить всю память пользователя |
| `GET` | `/api/v1/memory/settings/` | `{memory_enabled: bool}` (глобальный) |
| `PATCH` | `/api/v1/memory/settings/` | `{memory_enabled: bool}` |
| `POST` | `/api/v1/memory/search/` | **Phase 2:** семантический поиск `{query}` |

### 8.2. Схемы запросов/ответов

**`GET /api/v1/memory/`**
```json
{
  "memory_enabled": true,
  "count": 12,
  "items": [
    {
      "id": 5, "category": "profile", "category_display": "Профиль",
      "content": "Зовут Алексей, frontend-разработчик",
      "is_pinned": true, "is_active": true, "times_referenced": 7,
      "source_chat": 41,
      "created_at": "2026-06-21T10:00:00Z", "updated_at": "2026-06-21T12:00:00Z"
    }
  ]
}
```

**`POST /api/v1/memory/`**
```json
// request
{ "category": "preference", "content": "Предпочитает краткие ответы с примерами кода" }
// 201 → объект факта
```

**`PATCH /api/v1/memory/<id>/`**
```json
// request (любое подмножество)
{ "content": "...", "category": "fact", "is_pinned": true, "is_active": false }
// 200 → обновлённый объект
```

**`PATCH /api/v1/memory/settings/`**
```json
{ "memory_enabled": false }   // → { "memory_enabled": false }
```

**`POST /api/v1/memory/search/` (Phase 2)**
```json
// request
{ "query": "какой у меня стек", "limit": 5 }
// 200
{ "items": [ { "id": 5, "content": "...", "score": 0.83 } ] }
```

### 8.3. Реализация view (Phase 1)

```python
"""Persistent Memory API."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from aitext.models import UserMemory


def _serialize(m):
    return {
        'id': m.id, 'category': m.category,
        'category_display': m.get_category_display(),
        'content': m.content, 'is_pinned': m.is_pinned,
        'is_active': m.is_active, 'times_referenced': m.times_referenced,
        'source_chat': m.source_chat_id,
        'created_at': m.created_at, 'updated_at': m.updated_at,
    }


class MemoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = UserMemory.objects.filter(user=request.user)
        cat = request.query_params.get('category')
        if cat:
            qs = qs.filter(category=cat)
        items = [_serialize(m) for m in qs]
        return Response({
            'memory_enabled': request.user.memory_enabled,
            'count': len(items), 'items': items,
        })

    def post(self, request):
        from aitext.memory import normalize_fact
        content = (request.data.get('content') or '').strip()
        if not content:
            return Response({'error': 'content required'}, status=400)
        category = request.data.get('category', 'fact')
        if category not in dict(UserMemory.Category.choices):
            category = 'fact'
        m, _ = UserMemory.objects.update_or_create(
            user=request.user, content_key=normalize_fact(content),
            defaults={'content': content, 'category': category, 'is_pinned': True},
        )
        return Response(_serialize(m), status=status.HTTP_201_CREATED)


class MemoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        return UserMemory.objects.filter(user=request.user, id=pk).first()

    def patch(self, request, pk):
        m = self._get(request, pk)
        if not m:
            return Response(status=404)
        for f in ('content', 'category', 'is_pinned', 'is_active'):
            if f in request.data:
                setattr(m, f, request.data[f])
        m.save()
        return Response(_serialize(m))

    def delete(self, request, pk):
        m = self._get(request, pk)
        if not m:
            return Response(status=404)
        m.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemoryClearView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        n, _ = UserMemory.objects.filter(user=request.user).delete()
        return Response({'deleted': n})


class MemorySettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'memory_enabled': request.user.memory_enabled})

    def patch(self, request):
        val = bool(request.data.get('memory_enabled', request.user.memory_enabled))
        request.user.memory_enabled = val
        request.user.save(update_fields=['memory_enabled'])
        return Response({'memory_enabled': val})
```

### 8.4. Роуты — добавить в `src/api/urls.py`

```python
from api.views.memory import (
    MemoryListCreateView, MemoryDetailView, MemoryClearView, MemorySettingsView,
)

# в urlpatterns, рядом с прочими /v1/ (clear/ и settings/ — ДО <int:pk>/):
    path('v1/memory/', MemoryListCreateView.as_view(), name='memory_list_create'),
    path('v1/memory/clear/', MemoryClearView.as_view(), name='memory_clear'),
    path('v1/memory/settings/', MemorySettingsView.as_view(), name='memory_settings'),
    path('v1/memory/<int:pk>/', MemoryDetailView.as_view(), name='memory_detail'),
```

---

## 9. Frontend (Next.js)

### 9.1. Страница `/account/memory/` — `frontend/app/account/memory/page.tsx`

Client component, React Query. Спецификация:
- **Заголовок:** «Память» + toggle «Долговременная память» → `PATCH /memory/settings/`. Иконка `Brain` (Lucide).
- **Описание:** «ИИ запоминает важные факты о вас и использует их во всех чатах и в Telegram-боте.»
- **Фильтр по категориям:** chips (Профиль / Предпочтения / Проекты / Факты / Навыки) → `GET /memory/?category=`.
- **Список фактов:** карточки. У каждой: текст, бейдж категории, кнопки `Pin` (`Pin`), `Edit` (`Pencil`), `Delete` (`Trash2`).
- **Добавить факт вручную:** поле ввода + select категории + кнопка «Добавить» → `POST /memory/`.
- **Очистить всё:** кнопка «Очистить память» с подтверждением → `DELETE /memory/clear/`.
- **Empty state:** «Память пока пуста. Факты появятся автоматически по мере общения.»
- Только Lucide-иконки, без эмодзи, строгий стиль (Linear/Vercel). Dark mode через CSS-переменные.

### 9.2. API-клиент — `frontend/lib/api/memory.ts` (новый)

Функции: `getMemory(category?)`, `createMemory(data)`, `updateMemory(id, data)`, `deleteMemory(id)`, `clearMemory()`, `getMemorySettings()`, `updateMemorySettings(enabled)`. Реиспользовать существующий клиент из `frontend/lib/api/`.

### 9.3. Индикатор памяти в чате

- В `frontend/components/chat/` (шапка чата или возле поля ввода) — индикатор: иконка `Brain` + tooltip «Память активна — ИИ помнит вас». Кликабелен → `/account/memory/`.
- Скрыт, если `memory_enabled=false`.

### 9.4. Per-chat тоггл

- В меню настроек чата — переключатель «Память в этом чате». Пишет в `Chat.settings.memory_enabled` через `PATCH /chats/<id>/`. Если сериализатор чата не пропускает `settings.memory_enabled` — добавить поддержку (мелкая правка сериализатора).

### 9.5. Навигация

- Пункт «Память» в навигации аккаунта (`frontend/app/account/` layout/sidebar), рядом с keys/analytics/billing/referral/files. Иконка `Brain`.

---

## 10. Phase 2 — RAG с pgvector (Advanced)

Включается **после** стабильной работы Phase 1. Переиспользует инфраструктуру эмбеддингов (`src/api/views/embeddings.py`, `text-embedding-3-small` через laozhang.ai).

### 10.1. Инфраструктура

1. **Расширение pgvector** — миграция `aitext/0011_pgvector.py`:
```python
from pgvector.django import VectorExtension
class Migration(migrations.Migration):
    dependencies = [('aitext', '0010_user_memory_chat_summary')]
    operations = [VectorExtension()]  # CREATE EXTENSION IF NOT EXISTS vector
```
   - Добавить `pgvector` в `src/requirements.txt`.
   - Образ Postgres должен поддерживать pgvector: заменить `postgres:15-alpine` на `pgvector/pgvector:pg15` в `docker-compose.yml`.

2. **Поле эмбеддинга** — миграция `aitext/0012_usermemory_embedding.py`:
```python
from pgvector.django import VectorField, HnswIndex
migrations.AddField(
    model_name='usermemory',
    name='embedding',
    field=VectorField(dimensions=1536, null=True, blank=True),
)
migrations.AddIndex(
    model_name='usermemory',
    index=HnswIndex(name='um_embedding_hnsw', fields=['embedding'],
                    m=16, ef_construction=64, opclasses=['vector_cosine_ops']),
)
```
   Раскомментировать поле `embedding` в `UserMemory` (см. 3.1).

### 10.2. Заполнение эмбеддингов

- В `extract_memory_facts` при создании нового факта дополнительно: `client.embeddings.create(model='text-embedding-3-small', input=content)` → сохранить в `UserMemory.embedding`.
- Бэкофилл существующих — management-команда `backfill_memory_embeddings`.

### 10.3. Семантический поиск

- `POST /api/v1/memory/search/`: эмбеддит `query`, `UserMemory.objects.filter(user=...).order_by(CosineDistance('embedding', q))[:limit]`.
- `build_memory_context` (RAG-режим): вместо «топ-N по recency» — top-K фактов, **семантически релевантных текущему сообщению**. Радикально повышает точность при большом объёме памяти.

### 10.4. Дедупликация Phase 2

- При вставке: если косинусная близость к существующему факту > 0.92 — дубликат, не вставлять (или обновлять `confidence`). Дополняет точечный дедуп Phase 1 (`content_key`).

### 10.5. Категории UI (Phase 2)

- На `/account/memory/` — группировка по категориям со сворачиванием, счётчики, поиск по фактам (`/memory/search/`).

---

## 11. Разбивка по коммитам

> Ветка: `feature/persistent-memory` от `main`. Каждый коммит атомарен, проект собирается. После каждого коммита — `git push`.

### Phase 1 — MVP

| # | Коммит | Файлы | Часы |
|---|--------|-------|------|
| 1 | `feat(memory): models UserMemory + ChatSummary` | `aitext/models.py`, миграция `aitext/0010` | 2 |
| 2 | `feat(memory): memory_enabled flag on CustomUser` | `users/models.py`, миграция `users/00XX` | 1 |
| 3 | `feat(memory): memory.py — context build + history compression` | `aitext/memory.py` (новый) | 4 |
| 4 | `feat(memory): celery tasks extract + summary` | `aitext/tasks_memory.py` (новый) | 5 |
| 5 | `feat(memory): wire into generate_ai_response` | `aitext/tasks.py` (стр. 281 + хвост) | 3 |
| 6 | `feat(memory): wire into SSE StreamMessageView` | `api/views/chats.py` (стр. 355 + хвост) | 3 |
| 7 | `feat(memory): DRF API endpoints` | `api/views/memory.py` (новый), `api/urls.py` | 4 |
| 8 | `feat(memory): admin for UserMemory + ChatSummary` | `aitext/admin.py` | 1 |
| 9 | `feat(memory): frontend /account/memory page` | `frontend/app/account/memory/page.tsx`, `frontend/lib/api/memory.ts` | 6 |
| 10 | `feat(memory): chat memory indicator + nav link` | `frontend/components/chat/*`, account nav | 3 |
| 11 | `feat(memory): per-chat toggle (Chat.settings)` | chat serializer, chat settings UI | 2 |
| 12 | `test(memory): unit tests for memory.py + dedup` | `aitext/tests/test_memory.py` | 4 |
| 13 | `docs(memory): update CLAUDE.md` | `CLAUDE.md` | 1 |

**Итого Phase 1: ~39 часов.**

### Phase 1.5 — опционально

| # | Коммит | Файлы | Часы |
|---|--------|-------|------|
| 14 | `feat(memory): /memory command in telegram bot` | `telegram_bot/handlers/` | 3 |
| 15 | `feat(memory): prune_stale_memories beat task` | `tasks_memory.py`, celery beat | 2 |

### Phase 2 — RAG

| # | Коммит | Файлы | Часы |
|---|--------|-------|------|
| 16 | `chore(memory): add pgvector (req + docker + extension migration)` | `requirements.txt`, `docker-compose.yml`, `aitext/0011` | 3 |
| 17 | `feat(memory): embedding field + HNSW index` | `aitext/models.py`, `aitext/0012` | 2 |
| 18 | `feat(memory): embed facts on extraction + backfill cmd` | `tasks_memory.py`, management command | 4 |
| 19 | `feat(memory): semantic search endpoint + RAG context` | `api/views/memory.py`, `memory.py`, `api/urls.py` | 5 |
| 20 | `feat(memory): semantic dedup (cosine > 0.92)` | `tasks_memory.py` | 2 |
| 21 | `feat(memory): categories UI + fact search` | `frontend/app/account/memory/` | 4 |

**Итого Phase 2: ~20 часов.**

---

## 12. Анализ стоимости

### 12.1. Накладные расходы на токены (на сообщение, входной контекст)

| Компонент | Доп. входные токены (оценка) |
|-----------|------------------------------|
| Блок UserMemory (до 40 фактов × ~15 ток. + заголовок) | ~600–650 |
| Блок ChatSummary (≤ 250 слов) | ~350–400 |
| **Итого добавочный вход** | **~1000 входных токенов / сообщение** |

При этом **ChatSummary экономит** входные токены на длинных диалогах: вместо 30+ старых сообщений (легко 5000–15000 токенов) отправляется одно резюме (~400 токенов). На длинных чатах память **снижает** суммарный расход.

### 12.2. Фоновые задачи (DeepSeek V3, laozhang.ai)

- `extract_memory_facts`: вход ~1.5k токенов, выход ~0.3k. Один вызов на сообщение пользователя.
- `generate_chat_summary`: вход до ~20k токенов, выход ~0.5k. Запускается **редко** — только при превышении `SUMMARY_TRIGGER` (≈ раз в 30 сообщений).

### 12.3. Денежная оценка

> **Цены laozhang.ai/DeepSeek V3 в репозитории не зафиксированы** — `settings.py` содержит только `LAOZHANG_API_KEY` и `LAOZHANG_API_URL`, без тарифов. Ниже — **формула**; подставить реальные ставки из биллинг-кабинета laozhang.ai.
>
> `P_in` = цена за 1M входных токенов, `P_out` = за 1M выходных (для DeepSeek V3 — обычно очень низкая).

```
Стоимость памяти на 1 сообщение ≈
    (1500/1e6)*P_in + (300/1e6)*P_out
    + (1/30)*((20000/1e6)*P_in + (500/1e6)*P_out)
```

При типичных ставках DeepSeek V3 это **доли копейки на сообщение** — пренебрежимо мало относительно стоимости ответа основной модели.

### 12.4. Влияние на баланс звёзд пользователя

**Нулевое.** Принципиальное решение: **за память звёзды НЕ списываются**.
- Фоновые задачи не вызывают `user.spend_pages()`.
- Добавочные входные токены основного запроса не увеличивают `cost_per_message` — стоимость сообщения остаётся фиксированной (`network.cost_per_message`). Расход токенов — операционная стоимость платформы, не пользователя.
- Конкурентное преимущество: память «бесплатна» для пользователя (как в ChatGPT/Claude по подписке), но у нас работает ещё и в Telegram.

---

## 13. Чеклист готовности (Definition of Done, Phase 1)

- [ ] `makemigrations` создаёт ровно 2 миграции (`aitext/0010`, `users/00XX`), `migrate` проходит.
- [ ] Факты извлекаются после ответа (лог `[memory] chat=...: +N фактов`).
- [ ] Один и тот же факт не дублируется (uniqueness по `content_key`).
- [ ] Память видна в веб-чате И в Telegram-боте для одного пользователя.
- [ ] Длинный чат (>30 сообщений) получает ChatSummary, старые сообщения не шлются целиком.
- [ ] `/account/memory/` показывает, добавляет, редактирует, пинит, удаляет факты.
- [ ] Глобальный и per-chat тогглы отключают память.
- [ ] За память не списываются звёзды (проверить `pages_count` до/после).
- [ ] Нет эмодзи в UI, только Lucide-иконки (`scripts/check_no_emoji.py`).
- [ ] Тесты `aitext/tests/test_memory.py` зелёные.

---

## 14. Решения, зафиксированные в этом плане

1. `UserMemory` → FK на **пользователя** (общая память). `ChatSummary` → OneToOne на **чат**.
2. Глобальный тоггл — поле `memory_enabled` на `CustomUser` (миграция `users`). Per-chat — `Chat.settings['memory_enabled']` (без миграции).
3. Дедуп Phase 1 — нормализованный `content_key` + `UniqueConstraint(user, content_key)`. Phase 2 — косинусная близость > 0.92.
4. Фоновые LLM-вызовы — `deepseek-v3` через `get_laozhang_client()`.
5. Триггеры событийные (`.delay` после ответа), порог суммаризации проверяется внутри задачи.
6. Telegram/Studio — нулевой код, наследуют через `generate_ai_response`.
7. `RECENT_WINDOW = 20`, `SUMMARY_TRIGGER = 30`, `MAX_MEMORY_FACTS = 40`.
8. За память звёзды не списываются.
9. RAG (pgvector) — отдельная Phase 2, образ Postgres → `pgvector/pgvector:pg15`.
