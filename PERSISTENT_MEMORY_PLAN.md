# PERSISTENT MEMORY — Технический аудит и план развития

> **Статус документа:** аудит **реализованной и четырежды пропатченной** системы Persistent Memory.
> Round 1: B1, B2, B6, B8, B9, B10, B12. Round 2: B3, B4, B5, B10+, B11, B13, B14.
> Round 3 (2026-06-21, коммит `d841d55`): R1, R1b, R2, R4, R5.
> Sprint C (2026-06-21, коммит `1750ea7`): C1 — `last_compressed_message_id`, C2 — идемпотентная компрессия, C3 — инкрементальный summary.
>
> Дата последнего обновления: 2026-06-21. Ветка: `main`.

---

## 1. Executive Summary

Система долговременной памяти **реализована полностью и стабилизирована**. Модели, ядро, фоновые задачи, DRF API, UI личного кабинета, beat-расписание — всё работает. Все критические и производительностные баги (R1–R5) закрыты. Sprint C закрыл оставшийся техдолг по корректности: компрессия идемпотентна по ID сообщения, `generate_chat_summary` инкрементален.

> **Studio вне периметра памяти (проверено grep'ом):** Vibe-Coding Studio использует собственный многоагентный пайплайн (`studio/tasks.py`, architect/coder/guardian), работает с `StudioProject`, а не с `aitext.Chat`, и **не вызывает** `build_memory_context` / `generate_ai_response` / `UserMemory`. Долговременная память на Studio не распространяется — это отдельный продукт со своим контекстом.

**Вердикт:** система production-ready. Оставшийся архитектурный долг (слияние двух текстовых полей summary в одно `content`) — косметический, не влияет на корректность и откладывается на Future.

### Светофор текущего состояния

| Область | Статус |
|--------|--------|
| Извлечение фактов (auto) — все каналы | Работает (B1 закрыт) |
| Сохранение истории «в окне» без потерь | Работает (B2 закрыт) |
| Дедупликация фактов | Работает (B3 закрыт, `update_or_create`) |
| Гонки записи summary | Снято `select_for_update` (B4 закрыт) |
| Горячий путь без sync-LLM | Работает (B5 закрыт, async `compress_chat_history`) |
| Cross-session summary (любая модель + beat) | Работает (B6/B14 закрыты) |
| Redis-кэш контекста | Исправлен: факты per-user (`memfacts:{user_id}`), summaries свежо (R2 закрыт) |
| Триггер компрессии | Исправлен: TOTAL msg_count + Redis-лок (R1/R1b закрыты) |
| Производительность чтения истории | HARD_MSG_CAP=80 (R4 закрыт). Инкр. токен-кэш — ОТЛОЖЕН (Sprint B2) |
| Тесты | R1-регрессия, normalize_fact, C2-идемпотентность покрыты (R5/C2 закрыты) |
| Идемпотентность компрессии по ID | ЗАКРЫТ — Sprint C (C2, `last_compressed_message_id`) |
| `generate_chat_summary` инкрементальность | ЗАКРЫТ — Sprint C (C3) |
| Единое поле summary (слияние rolling+final) | Mitigated. Поле `last_compressed_message_id` добавлено. Слияние полей — Future |
| DRF API `/memory/` + UI `/account/memory/` | Реализовано полностью |

---

## 2. Архитектура (что есть сейчас)

### 2.1. Модель данных — `src/aitext/models.py:509–595`

- **`UserMemory`** (`models.py:509`) — факт о пользователе, общий для всех каналов. Поля: `user` (FK), `category` (profile/preference/project/fact/skill), `content`, `content_key` (ключ дедупа, `db_index`), `source` (auto/user), `source_chat` (FK, SET_NULL), `is_active`, `is_pinned`, timestamps.
  - `UniqueConstraint(user, content_key)` c `condition=Q(content_key__gt='')` — дедуп только непустых ключей.
  - `save()` — генерирует `content_key` через `normalize_fact()`.
- **`ChatSummary`** (`models.py:570`) — `OneToOne(Chat)`, поля:
  - `summary_text` — финальное резюме сессии (пишет `generate_chat_summary`)
  - `rolling_summary` — сжатое начало текущей сессии (пишет `compress_chat_history`)
  - `message_count` — total сообщений на момент последнего сжатия
  - `last_compressed_message_id` (**Sprint C, миграция 0011**) — ID последнего сжатого сообщения; основа идемпотентности C2
  - timestamps
- **`CustomUser.memory_enabled`** — глобальный тоггл, `default=True`.

### 2.2. Ядро — `src/aitext/memory.py`

| Функция | Назначение |
|---------|-----------|
| `normalize_fact()` | Нормализация ключа дедупа: lowercase, без пунктуации, пробелы схлопнуты |
| `estimate_tokens()` | Language-aware оценка токенов (кириллица ~2.5, латиница ~4.0 симв/токен) |
| `_get_context_window()` | Контекстное окно по `model_name` |
| `build_memory_context()` | Блок памяти для system-prompt, Redis-кэш `memfacts:{user_id}` TTL 300с |
| `should_compress()` | Дешёвая проверка «пора сжать» (только счётчики БД) |
| `get_history_with_compression()` | Read-only: история + готовый summary, без LLM, HARD_MSG_CAP=80 |
| `update_rolling_summary()` | Атомарный upsert с `select_for_update`; принимает `last_compressed_message_id` (C2) |
| `invalidate_memory_cache()` | Сброс Redis-кэша |

Константы: `RECENT_WINDOW=20`, `COMPRESS_TRIGGER=30`, `COMPRESS_THRESHOLD=0.70`, `MAX_MEMORY_FACTS=40`, `EXTRACT_EVERY_N=3`, `MEMORY_CACHE_TTL=300`, `HARD_MSG_CAP=80`.

### 2.3. Фоновые задачи — `src/aitext/tasks.py`

- **`extract_memory_facts(chat_id)`** — DeepSeek V3, анализ последних 10 сообщений, `update_or_create` по `content_key`, инвалидация кэша.
- **`generate_chat_summary(chat_id)`** — финальный `summary_text`. **Инкрементален (C3):** если есть `rolling_summary` + `last_compressed_message_id`, обрабатывает только новые сообщения после последней компрессии и дополняет существующее резюме. Иначе — стандартный путь (последние 40 сообщений).
- **`compress_chat_history(chat_id)`** — async-компрессия в `rolling_summary`. **Идемпотентна (C2):** фильтрует кандидатов по `id > last_compressed_message_id`; при пустом результате — немедленный no-op return. Redis-лок `memcompress:{chat_id}` (R1b).
- **`summarize_stale_chats()`** — beat, раз в 2 часа, до 30 «брошенных» (>24ч) чатов без актуального summary.

### 2.4. Точки интеграции

- **Celery-путь** — текст и Telegram-бот (`telegram_bot/handlers/chat.py`). Триггер extract: каждые 3 ответа.
- **SSE-путь** (`api/views/chats.py`) — основной веб-чат. Триггер extract: каждые 3 ответа (B1 закрыт).
- **Триггер summary** при новом сообщении: `chats.py:139–151` — любой предыдущий чат (B6 закрыт).
- **Beat:** `config/celery.py` — `summarize_stale_chats` каждые 2 часа.

### 2.5. API и UI

- DRF: `api/views/memory.py` + `api/serializers/memory.py`, роуты `api/urls.py:148–153` (`/memory/`, `/<pk>/`, `/clear/`, `/summaries/`, `/settings/`).
  - Сериализатор `ChatSummarySerializer` включает `last_compressed_message_id` (Sprint C).
- UI: `frontend/app/account/memory/page.tsx` — глобальный тоггл, CRUD фактов, фильтры, pin/active toggle, история сессий, очистка авто-фактов.

---

## 3. Все исправления (Round 1 + Round 2 + Round 3 + Sprint C)

| # | Баг | Как закрыт |
|---|-----|-----------|
| B1 | SSE не извлекал факты | Триггер `extract_memory_facts.delay()` добавлен в конец стрима |
| B2 | Silent-drop сообщений «в окне» | Ветка «всё помещается» возвращает `all_msgs` целиком |
| B3 | Коллизии `content_key`, `continue` терял факты | Единый `normalize_fact` + `update_or_create` |
| B4 | Lost update в summary | `select_for_update()` в `update_rolling_summary` |
| B5 | Sync DeepSeek в SSE-запросе | `get_history_with_compression` read-only; компрессия в Celery |
| B6 | Summary только при той же модели | Триггер по любому prev-чату + beat-таск |
| B8 | Резался не тот конец диалога | `msgs[-40:]` + `dialogue[-5000:]` (свежий хвост) |
| B9 | HTML в LLM-входе | `_strip_html()` во всех входах |
| B10 | Неточный токен-каунт | Language-aware (кириллица/латиница) |
| B11 | БД на каждом сообщении | Redis-кэш `memfacts:{user_id}` TTL 300с |
| B12 | `%-d` падал на Windows | `f"{dt.day} {dt.strftime('%b %Y')}"` |
| B13 | Гонка дедупа | `update_or_create` + `UniqueConstraint` |
| B14 | rolling_summary рос бесконечно | beat `summarize_stale_chats` |
| R1 | `should_compress` триггерил на каждом сообщении | Хранить TOTAL `msg_count`, гард `>= msg_count` |
| R1b | Конкурентные компрессии перетирали друг друга | Redis-лок `memcompress:{chat_id}` |
| R2 | Redis-кэш per-user, контент зависит от чата | Факты кэшируем per-user, summaries — всегда свежо |
| R4 | O(N) чтение истории на каждый запрос | `HARD_MSG_CAP=80` — cap без полного перебора |
| R5 | Тесты сломаны после фиксов | Полная перезапись тестового файла |
| **C1** | Нет якоря для идемпотентности | `last_compressed_message_id` (BigIntegerField, nullable) в `ChatSummary`, миграция 0011 |
| **C2** | `compress_chat_history` перекомпрессировала сообщения повторно | Фильтр `id > last_compressed_message_id`; пустой результат → no-op |
| **C3** | `generate_chat_summary` пересоздавала summary с нуля | Инкрементальный режим: новые сообщения + rolling как контекст |

---

## 4. Остаточный технический долг

### Единое поле summary (архитектурный долг, не баг)

**Где:** `models.py:577–582` — два текстовых поля `summary_text` и `rolling_summary`.

**Что есть:** read-fallback `(summary_text or rolling_summary)` в нескольких местах, `best_summary` в сериализаторе. `last_compressed_message_id` (Sprint C) добавил якорь — компрессия теперь идемпотентна. Система работает корректно.

**Что не сделано:** слияние двух полей в одно `content` (исходный план B7). Два суммаризатора пишут разные поля одной строки — в контекст идёт «что попалось первым».

**Статус: mitigated, не resolved. Не критично.** Откладывается в Future — требует data-migration живой БД (backfill `content := rolling_summary or summary_text`), затем удаление старых колонок в отдельном релизе.

### Производительность (Sprint B2 — отложен)

Инкрементальный токен-кэш в Redis/ChatSummary. `HARD_MSG_CAP=80` уже достаточен для текущей нагрузки — вернуться только при реальном bottleneck на profiler.

---

## 5. Будущие улучшения (Phase 2)

### 5.1. Единая модель summary (архитектурная очистка)
- Свести к одному полю `content` + `last_compressed_message_id` (уже есть) + `messages_count`.
- Data-migration: `content := rolling_summary or summary_text`, затем удалить старые поля.
- Только после этого убрать read-fallback из code-base.

### 5.2. RAG-память на pgvector (relevance scoring)
- `pgvector/pgvector:pg15`, `UserMemory.embedding = VectorField(1536)` + HNSW (cosine).
- Эмбеддинг факта при создании в `extract_memory_facts` (`text-embedding-3-small`).
- `build_memory_context` в RAG-режиме: top-K семантически релевантных фактов вместо top-40 по recency.
- `POST /api/v1/memory/search/`.

### 5.3. Фаззи-дедуп
- При вставке: косинус > 0.92 к существующему → обновить, не плодить.

### 5.4. Точный токен-каунт
- `tiktoken` для GPT, кэш токенайзера; эвристика-фолбэк для остальных.

### 5.5. Автоочистка устаревших фактов
- beat `prune_stale_memories` (ночью): деактивировать `is_active, not is_pinned`, не используемые > 90 дней. Требует поля `last_referenced_at`.

### 5.6. Приватность / контроль
- Экспорт памяти (GDPR-like). Аудит: какой факт использован в каком ответе (`times_referenced`).

### 5.7. Telegram: UI управления памятью
- Память в боте **работает**, но нет хендлера управления фактами. Mini App `/tg/` может переиспользовать `/account/memory/`-контур.

---

## 6. Спринт-план (итоговый)

### Спринт A — остаточные баги стоимости/корректности `[DONE — d841d55]`

| # | Статус | Закрывает |
|---|--------|-----------|
| A1 | DONE | R1: `msg_count=msg_count` в compress; гард `>= msg_count` |
| A1b | DONE | R1b: Redis-лок `memcompress:{chat_id}` |
| A2 | DONE | R2: `_facts_cache_key` → `memfacts:{user_id}`; summaries всегда свежо |
| A3 | DISSOLVED | R3: summaries больше не кэшируются после A2 |
| A4 | DONE | R5: тесты переписаны |

### Спринт B — производительность горячего пути

| # | Статус | Описание |
|---|--------|----------|
| B1 | **DONE** (d841d55) | HARD_MSG_CAP=80 в `get_history_with_compression` |
| B2 | **ОТЛОЖЕН** | Инкр. токен-кэш. HARD_MSG_CAP достаточен — вернуться при bottleneck |

### Спринт C — идемпотентность и инкрементальность `[DONE — 1750ea7]`

| # | Статус | Закрывает |
|---|--------|-----------|
| C1 | **DONE** | `last_compressed_message_id` в `ChatSummary`, миграция `0011` |
| C2 | **DONE** | Идемпотентный `compress_chat_history` по `id > last_compressed_message_id` |
| C3 | **DONE** | Инкрементальный `generate_chat_summary` (rolling как контекст + новые сообщения) |

### Спринт D — Phase 2 (RAG) `[БУДУЩЕЕ — отдельная фаза]`

| # | Статус | Описание |
|---|--------|----------|
| D1 | БУДУЩЕЕ | pgvector infra + `UserMemory.embedding` + HNSW |
| D2 | БУДУЩЕЕ | Embed facts on extract + backfill command |
| D3 | БУДУЩЕЕ | Relevance-scored `build_memory_context` + `/memory/search/` |
| D4 | БУДУЩЕЕ | `prune_stale_memories` beat (90d, `last_referenced_at`) |

---

## 7. Что работает правильно (зафиксировать)

1. **Cross-channel память** — единый `CustomUser` для web и Telegram. Studio — отдельный пайплайн, память не использует.
2. **Грейсфул-деградация** — все интеграции в `try/except`, память не роняет генерацию.
3. **Память бесплатна** — фоновые задачи на DeepSeek V3, звёзды не списываются.
4. **Двойной тоггл** — глобальный `memory_enabled` + per-chat `Chat.settings['memory_enabled']`.
5. **Дедуп в два эшелона** — `existing_preview` в промпте LLM + `content_key` UniqueConstraint.
6. **Идемпотентная компрессия** — повторный запуск `compress_chat_history` при тех же данных — no-op (C2).
7. **Инкрементальный summary** — `generate_chat_summary` дополняет существующее резюме, не пересоздаёт (C3).
8. **Полный UI** — `/account/memory/` с CRUD, фильтрами, pin/active, историей сессий, очисткой.
9. **Безопасный порядок DRF-роутов** — `<int:pk>` не перехватывает `clear`/`summaries`.
10. **Инвалидация кэша на мутациях API** — все CRUD-операции вызывают `invalidate_memory_cache`.

---

## Приложение: карта файлов (текущее состояние)

| Компонент | Файл | Состояние |
|-----------|------|-----------|
| Ядро памяти | `src/aitext/memory.py` | Готово. `update_rolling_summary` принимает `last_compressed_message_id` (C2) |
| Модели | `src/aitext/models.py:509–595` | Готово. `ChatSummary` + `last_compressed_message_id` (C1) |
| Миграция C1 | `src/aitext/migrations/0011_chatsummary_last_compressed_message_id.py` | Готово |
| `extract_memory_facts` | `src/aitext/tasks.py:534–654` | Готово |
| `generate_chat_summary` | `src/aitext/tasks.py:657–770` | Готово. Инкрементален (C3) |
| `compress_chat_history` | `src/aitext/tasks.py:773–870` | Готово. Идемпотентен по ID (C2) |
| `summarize_stale_chats` (beat) | `src/aitext/tasks.py:871+` | Готово |
| Триггер extract (SSE) | `src/api/views/chats.py:506–515` | Готово (B1) |
| Триггер summary | `src/api/views/chats.py:139–151` | Готово (B6) |
| Beat-расписание | `src/config/celery.py` | Готово |
| DRF API `/memory/` | `src/api/views/memory.py` | Готово |
| Сериализаторы | `src/api/serializers/memory.py` | Готово. `last_compressed_message_id` в `ChatSummarySerializer` (C1) |
| Frontend `/account/memory/` | `frontend/app/account/memory/page.tsx` | Готово |
| API-клиент | `frontend/lib/api/memory.ts` | Готово |
| Тесты | `src/aitext/test_memory.py` | R5 + C2-идемпотентность (2 новых теста) |
