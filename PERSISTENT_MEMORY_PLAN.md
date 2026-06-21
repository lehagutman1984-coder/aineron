# PERSISTENT MEMORY — Технический аудит (post-fix) и план развития

> **Статус документа:** аудит **уже реализованной и трижды пропатченной** системы Persistent Memory.
> Round 1: B1, B2, B6, B8, B9, B10, B12. Round 2: B3, B4, B5, B10+, B11, B13, B14.
> Round 3 (2026-06-21, коммит `d841d55`): R1, R1b, R2, R4, R5.
> R3 снят автоматически (summaries не кэшируются после R2-fix).
>
> **Решение 2026-06-21:** Sprint B2 ОТЛОЖЕН (HARD_MSG_CAP=80 достаточен, Redis-аккумулятор несёт риск корректности).
> Sprint C ОТЛОЖЕН (требует миграции живой БД — отдельный релиз). Sprint D = Phase 2.
>
> Дата последнего обновления: 2026-06-21. Ветка: `main`.

---

## 1. Executive Summary

Система долговременной памяти **реализована полностью по контуру**: модели, ядро, фоновые задачи, DRF API, UI личного кабинета, beat-расписание. Оба критических бага исходного аудита (B1 — мёртвое извлечение фактов в SSE; B2 — потеря сообщений «в окне») **закрыты**. Память работает в двух каналах через единый `CustomUser`: веб (SSE + Celery) и Telegram-бот (через `generate_ai_response`).

> **Studio вне периметра памяти (проверено grep'ом):** Vibe-Coding Studio использует собственный многоагентный пайплайн (`studio/tasks.py`, architect/coder/guardian), работает с `StudioProject`, а не с `aitext.Chat`, и **не вызывает** `build_memory_context` / `generate_ai_response` / `UserMemory`. Долговременная память на Studio не распространяется — это отдельный продукт со своим контекстом.

**Вердикт:** система production-ready по функционалу, но содержит **несколько остаточных дефектов класса «производительность/корректность»**, которые не ломают фичу визуально, но дорого стоят на потоке и портят качество cross-session памяти. Главные из них — **избыточные перезапуски компрессии практически на каждом сообщении** (off-by-`RECENT_WINDOW` в `should_compress`), **некорректный ключ Redis-кэша** (per-user, хотя контент зависит от чата) и **отсутствие инвалидации кэша при обновлении summary**. Плюс набор тестов частично сломан после фиксов.

Архитектурный долг из исходного плана (B7 — слияние `rolling_summary`/`summary_text` в единую модель `content + last_message_id`) **не выполнен**: Round 2 добавил только read-fallback'и, два поля по-прежнему живут раздельно.

### Светофор текущего состояния

| Область | Статус |
|--------|--------|
| Извлечение фактов (auto) — все каналы | Работает (B1 закрыт) |
| Сохранение истории «в окне» без потерь | Работает (B2 закрыт) |
| Дедупликация фактов | Работает (B3 закрыт, `update_or_create`) |
| Гонки записи summary | Снято `select_for_update` (B4 закрыт) |
| Горячий путь без sync-LLM | Работает (B5 закрыт, async `compress_chat_history`) |
| Cross-session summary (любая модель + beat) | Работает (B6/B14 закрыты) |
| Redis-кэш контекста | Исправлен: факты — per-user (`memfacts:{user_id}`), summaries — всегда свежо (R2 закрыт) |
| Триггер компрессии | Исправлен: TOTAL msg_count + Redis-лок (R1/R1b закрыты) |
| Производительность чтения истории | Закрыт достаточно: HARD_MSG_CAP=80 (R4 закрыт). Инкр. токен-кэш — ОТЛОЖЕН (Sprint B2, риск корректности > выгода) |
| Тесты | Исправлены: сломанный патч удалён, R1-регрессия и normalize_fact покрыты (R5 закрыт) |
| Единая модель summary (B7/R6) | Mitigated (read-fallback), не resolved. Sprint C — ОТЛОЖЕН (требует миграции живой БД) |
| generate_chat_summary инкрементальность (R7) | Тех. долг — не критично, Sprint C — ОТЛОЖЕН |
| DRF API `/memory/` + UI `/account/memory/` | Реализовано полностью |

---

## 2. Архитектура (что есть сейчас)

### 2.1. Модель данных — `src/aitext/models.py:509–592`

- **`UserMemory`** (`models.py:509`) — факт о пользователе, общий для всех каналов. Поля: `user` (FK), `category` (profile/preference/project/fact/skill), `content`, `content_key` (ключ дедупа, `db_index`), `source` (auto/user), `source_chat` (FK, SET_NULL), `is_active`, `is_pinned`, timestamps.
  - `UniqueConstraint(user, content_key)` c `condition=Q(content_key__gt='')` (`models.py:552`) — дедуп только непустых ключей.
  - `save()` (`models.py:563`) — генерирует `content_key` через единый `normalize_fact()`.
- **`ChatSummary`** (`models.py:570`) — `OneToOne(Chat)`, поля `summary_text` (финальное резюме), `rolling_summary` (сжатое начало текущей сессии), `message_count`, timestamps. **Два независимых текстовых поля** (см. R6).
- **`CustomUser.memory_enabled`** (`users/models.py:488`) — глобальный тоггл, `default=True`.

### 2.2. Ядро — `src/aitext/memory.py`

| Функция | Назначение | Строки |
|---------|-----------|--------|
| `normalize_fact()` | Нормализация ключа дедупа: lowercase, без пунктуации, пробелы **схлопнуты** (не вырезаны) | `52–61` |
| `estimate_tokens()` | Language-aware оценка токенов (кириллица ~2.5, латиница ~4.0 симв/токен) | `64–74` |
| `_get_context_window()` | Контекстное окно по `model_name` (таблица `_CONTEXT_WINDOWS`) | `77–84` |
| `build_memory_context()` | Блок памяти для system-prompt, Redis-кэш `memctx:{user_id}` TTL 300с | `100–156` |
| `should_compress()` | Дешёвая проверка «пора сжать» (только счётчики БД) | `159–177` |
| `get_history_with_compression()` | Read-only: история + готовый summary, без LLM | `180–241` |
| `update_rolling_summary()` | Атомарный upsert с `select_for_update` | `244–269` |
| `invalidate_memory_cache()` | Сброс Redis-кэша | `91–97` |

Константы: `RECENT_WINDOW=20`, `COMPRESS_TRIGGER=30`, `COMPRESS_THRESHOLD=0.70`, `MAX_MEMORY_FACTS=40`, `EXTRACT_EVERY_N=3`, `MEMORY_CACHE_TTL=300`.

### 2.3. Фоновые задачи — `src/aitext/tasks.py`

- **`extract_memory_facts(chat_id)`** (`tasks.py:534–654`) — DeepSeek V3, анализ последних 10 сообщений, `update_or_create` по `content_key`, инвалидация кэша. HTML стрипается через `_strip_html` (`tasks.py:23`).
- **`generate_chat_summary(chat_id)`** (`tasks.py:657–723`) — финальное `summary_text`, DeepSeek V3, последние 40 сообщений → последние 5000 символов.
- **`compress_chat_history(chat_id)`** (`tasks.py:726–810`) — async-компрессия в `rolling_summary`, сжимает `msgs[:-RECENT_WINDOW]`, идемпотентный гард по `message_count` (`tasks.py:764`).
- **`summarize_stale_chats()`** (`tasks.py:813–858`) — beat, раз в 2 часа, до 30 «брошенных» (>24ч) чатов без актуального summary.

### 2.4. Точки интеграции

- **Celery-путь** (`tasks.py:289–323`) — текст и Telegram-бот (`telegram_bot/handlers/chat.py:95` → `generate_ai_response.delay`). Триггер extract: `tasks.py:508–514` (каждые 3 ответа).
- **SSE-путь** (`api/views/chats.py:366–412`) — основной веб-чат. Триггер extract: `chats.py:506–515` (каждые 3 ответа) — **B1 закрыт**.
- **Триггер summary** при новом сообщении: `chats.py:139–151` — любой предыдущий чат (B6 закрыт).
- **Beat:** `config/celery.py:36–39` — `summarize_stale_chats` каждые 2 часа.

### 2.5. API и UI

- DRF: `api/views/memory.py` + `api/serializers/memory.py`, роуты `api/urls.py:148–153` (`/memory/`, `/<pk>/`, `/clear/`, `/summaries/`, `/settings/`).
  - Порядок роутов **безопасен**: `<int:pk>` не матчит строки `clear`/`summaries`.
  - Инвалидация кэша на всех мутациях (create/update/destroy/clear/settings).
- UI: `frontend/app/account/memory/page.tsx` — глобальный тоггл, CRUD фактов, фильтры (категория/источник), pin/active toggle, история сессий, очистка авто-фактов. API-клиент `frontend/lib/api/memory.ts`.

---

## 3. Подтверждённые исправления (Round 1 + Round 2)

| # | Баг | Как закрыт | Подтверждение в коде |
|---|-----|-----------|----------------------|
| B1 | SSE не извлекал факты | Триггер `extract_memory_facts.delay()` добавлен в конец стрима | `chats.py:506–515` |
| B2 | Silent-drop сообщений «в окне» | Ветка «всё помещается» возвращает `all_msgs`, не `[-RECENT_WINDOW:]` | `memory.py:234–236` |
| B3 | Коллизии `content_key`, `continue` терял факты | Единый `normalize_fact` (пробелы схлопнуты) + `update_or_create` | `memory.py:52`, `models.py:563`, `tasks.py:625–648` |
| B4 | Lost update в summary | `select_for_update()` в `update_rolling_summary` | `memory.py:251–267` |
| B5 | Sync DeepSeek в SSE-запросе | `get_history_with_compression` read-only; компрессия в Celery | `memory.py:180`, `tasks.py:726` |
| B6 | Summary только при той же модели | Триггер по любому prev-чату + beat-таск | `chats.py:142–149`, `tasks.py:813` |
| B8 | Резался не тот конец диалога | `msgs[-40:]` + `dialogue[-5000:]` (свежий хвост) | `tasks.py:683`, `tasks.py:702` |
| B9 | HTML в LLM-входе | `_strip_html()` во всех входах | `tasks.py:565`, `tasks.py:686`, `memory.py:230` |
| B10 | Неточный токен-каунт | Language-aware (кириллица/латиница) | `memory.py:64–74` |
| B11 | БД на каждом сообщении | Redis-кэш `memctx:{user_id}` TTL 300с | `memory.py:116–155` |
| B12 | `%-d` падал на Windows | `f"{dt.day} {dt.strftime('%b %Y')}"` | `memory.py:147–148` |
| B13 | Гонка дедупа | Снята `update_or_create` + `UniqueConstraint` | `tasks.py:635` |
| B14 | rolling_summary рос бесконечно | beat `summarize_stale_chats` | `tasks.py:813`, `celery.py:36` |

---

## 4. Остаточные проблемы (после фиксов)

> Эти дефекты **пережили** оба раунда фиксов либо были **внесены** ими. Severity: высокий = заметно влияет на стоимость/корректность на потоке; средний = деградация качества/перформанса; низкий = тех. долг.

### R1 — `should_compress` перезапускает компрессию почти на каждом сообщении `[ЗАКРЫТ — Round 3, d841d55]`

**Где:** `memory.py:174–175` (чтение) против `tasks.py:806` (запись).

**Механика.** `compress_chat_history` пишет `message_count = msg_count - RECENT_WINDOW` (`tasks.py:806`). А `should_compress` считает `unsummarized = msg_count - cs.message_count` и триггерит при `>= RECENT_WINDOW` (`memory.py:174–175`).

Подставим числа. Чат вырос до 30 сообщений, компрессия отработала → `message_count = 30 − 20 = 10`. Следующее сообщение: `msg_count = 31`, `unsummarized = 31 − 10 = 21 ≥ 20` → **True снова**. То есть условие «накопилось `RECENT_WINDOW` новых» удовлетворяется уже сразу после компрессии и **остаётся истинным на каждом последующем сообщении**.

Гард в задаче (`tasks.py:764`: `if cs.message_count >= msg_count - RECENT_WINDOW: return`) ловит **только** случай нулевого прироста. При любом новом сообщении `msg_count - RECENT_WINDOW` растёт на 1 и условие не срабатывает — задача каждый раз **заново сжимает растущий префикс через DeepSeek**.

**Последствия:** лишний вызов DeepSeek V3 на каждое сообщение длинного чата (после 30+), рост латентности фоновой очереди, деньги провайдеру. Фича не «ломается», но это off-by-`RECENT_WINDOW` в семантике счётчика.

**Фикс (правильная семантика счётчика):** хранить в `message_count` **общее число сообщений на момент сжатия** (`msg_count`), а не `msg_count - RECENT_WINDOW`. Тогда:
- запись: `update_rolling_summary(chat, new_rolling, msg_count=msg_count)` (`tasks.py:806`);
- чтение: `unsummarized = msg_count - cs.message_count`, триггер `>= RECENT_WINDOW` — корректно (после сжатия `unsummarized = 0`, копится до 20).
- гард в задаче: `if cs.message_count >= msg_count: return`.

Альтернатива (надёжнее) — хранить `last_compressed_message_id` и сжимать только `(last_id .. конец−RECENT_WINDOW]` (см. R6 / Future).

**R1b ЗАКРЫТ (Round 3): конкурентные `compress_chat_history` для одного чата blind-overwrite.** `update_rolling_summary` сериализует **запись** через `select_for_update` (B4), но цепочка чтение→DeepSeek→запись **не атомарна на уровне задачи**. Два одновременных запуска компрессии одного чата (вероятность которых R1 как раз многократно повышает) прочитают одинаковое состояние, оба сожмут через DeepSeek и затем перетрут результат друг друга — побеждает последний писатель. Это не падение, но потеря работы и лишние вызовы. **Корень снимается** идемпотентностью по `last_compressed_message_id` (§5.1) + опциональным Redis-локом `memcompress:{chat_id}` на время задачи.

---

### R2 — Redis-кэш `build_memory_context` per-user, хотя контент зависит от чата `[ЗАКРЫТ — Round 3, d841d55]`

**Где:** ключ `memctx:{user_id}` (`memory.py:88, 116`), но контент содержит `past_summaries` с `.exclude(chat=chat)` (`memory.py:138`).

**Механика.** Блок памяти включает «резюме последних 3 чатов, **кроме текущего**». Кэш-ключ зависит только от `user_id`. В пределах TTL (5 мин) пользователь переключается между чатами A и B:
- открыл A → закэширован блок, исключающий A;
- открыл B (тот же user, ключ тот же) → вернётся **кэш от A**, в котором summary чата A присутствует как «прошлая сессия», а summary чата B (которое нужно показать в A-исключённом виде) — может отсутствовать.

Итог: чат видит собственное summary как «прошлую сессию» и/или не видит summary параллельного чата. Корректность cross-session-блока нарушена — **регрессия, внесённая фиксом B11**.

**Фикс (один из):**
1. Ключ с учётом чата: `memctx:{user_id}:{chat_id}` — простейший, но снижает hit-rate.
2. Разделить кэш: факты (per-user, `memctx:{user_id}`) кэшируем, past-summaries (chat-dependent) — либо не кэшируем, либо отдельным ключом `memsum:{user_id}:{chat_id}` с коротким TTL.
3. Кэшировать только факты (стабильны per-user), а past-summaries собирать без кэша (это 1 лёгкий запрос с `select_related`).

Рекомендация — вариант 3: основной объём (до 40 фактов) кэшируется, а дешёвый chat-зависимый запрос идёт всегда корректно.

---

### R3 — Кэш памяти не инвалидируется при обновлении summary `[СНЯТ автоматически — Round 3]`

**Где:** `compress_chat_history` (`tasks.py:806`) и `generate_chat_summary` (`tasks.py:712–721`) пишут summary, но **не вызывают** `invalidate_memory_cache`.

**Механика.** Past-summaries входят в кэшированный блок (R2). При появлении/обновлении summary кэш не сбрасывается → пользователь до 5 минут получает старый блок памяти без свежего резюме. `extract_memory_facts` кэш сбрасывает (`tasks.py:654`), а суммаризаторы — нет.

**Фикс:** вызвать `invalidate_memory_cache(chat.user_id)` в конце `compress_chat_history` и `generate_chat_summary` после успешной записи. (После исправления R2 по варианту 3 этот пункт частично снимается — past-summaries перестанут кэшироваться.)

---

### R4 — `get_history_with_compression` читает ВСЮ историю и токенизирует каждое сообщение каждый запрос `[ЗАКРЫТ достаточно — Round 3, d841d55]`

**Где:** `memory.py:208` (`all_msgs = list(qs.order_by('created_at'))`), `memory.py:229–232` (token-count по всем).

**Механика.** После фикса B2 модели с большим окном (gpt-4o 89.6k, claude 140k, gemini 700k бюджет) почти всегда попадают в ветку «всё помещается» и получают **всю** историю. Каждый запрос:
- грузит из БД **все** completed-сообщения чата;
- прогоняет `estimate_tokens` + regex-strip HTML по каждому (`memory.py:229–232`).

Это O(N) на сообщение и O(N²) на жизнь чата. Плюс **вся** история уходит провайдеру на каждом ходу (нет верхнего кэпа сообщений, только токен-порог в 70% окна) — на gemini это сотни сообщений в каждом запросе. Корректно по смыслу, дорого по ресурсам.

**Закрыто (Round 3):** добавлен `HARD_MSG_CAP=80` (`memory.py:231–233`) — чаты >80 сообщений сразу идут в ветку recent+summary без полного перебора.

**Инкрементальный токен-кэш (Sprint B2) — ОТЛОЖЕН:** HARD_MSG_CAP+RECENT_WINDOW сводит token-loop к ≤80 дешёвых итераций. Redis-аккумулятор при дрейфе вверх даст false-truncation (потеря середины диалога). Профилинг не показывает проблемы на текущей нагрузке — вернуться только если появится реальный bottleneck.

---

### R5 — Тесты частично сломаны после фиксов `[ЗАКРЫТ — Round 3, d841d55]`

**Где:** `src/aitext/test_memory.py`.

**Установлено статически** (Django в этом окружении не установлен, прогнать suite нельзя; дефекты подтверждены чтением кода):

1. `test_large_history_returns_recent_window` (`test_memory.py:169–179`) патчит `aitext.memory.get_laozhang_client` (строка 173). После фикса B5 функция стала read-only и **`get_laozhang_client` в `memory.py` больше не импортируется и не существует** (подтверждено grep). `with patch('aitext.memory.get_laozhang_client')` бросит `AttributeError` → **тест падает на setup патча**.
2. Тот же тест ассертит `len(result) <= RECENT_WINDOW` (`test_memory.py:179`). Это **противоречит фиксу B2**: 25 сообщений на gpt-4o теперь возвращаются целиком (влезают в 89.6k бюджет) → ассерт ложен даже без ошибки патча.

**Не покрыто тестами вообще:**
- `should_compress` (особенно баг R1 — регрессионный тест на «не триггерить каждое сообщение»).
- `normalize_fact` (схлопывание пробелов, отсутствие ложных коллизий «Любит Go» vs «Любитgo») — критично для B3.
- `update_rolling_summary` (upsert/блокировка).
- Кэш `build_memory_context` (попадание/инвалидация, баг R2 — переключение чатов).
- Триггеры extract в обоих путях (хотя бы мок `.delay`).
- `compress_chat_history` / `generate_chat_summary` (явно объявлены untested, `test_memory.py:197–204`).

**Фикс:** переписать `test_large_history_returns_recent_window` (убрать несуществующий патч, разделить на два кейса: «влезает → all»; «не влезает → recent+summary» через малое окно модели типа `mistral` 32k или мок `_get_context_window`). Добавить юнит-тесты на `should_compress` (регрессия R1), `normalize_fact`, инвалидацию кэша.

---

### R6 — B7 не выполнен: `rolling_summary` и `summary_text` по-прежнему раздельны `[низкий — тех. долг]`

**Где:** `models.py:577–582`; чтение «лучшего из двух» в `memory.py:144`, `memory.py:214`, сериализатор `serializers/memory.py:40`.

**Механика.** Исходный план предписывал свести два поля в единую модель `content + last_message_id + messages_count`. Round 2 этого **не сделал** — добавил только read-fallback `(summary_text or rolling_summary)` в нескольких местах. Два суммаризатора (`compress_chat_history` → `rolling_summary`, `generate_chat_summary` → `summary_text`) по-прежнему пишут **разные поля одной строки**, описывая пересекающийся контент, никем не сводимый. Это работает (read-fallback маскирует), но остаётся источником рассинхрона: после длинной сессии `rolling_summary` и `summary_text` могут расходиться, а в контекст идёт «что попалось первым».

**Статус: mitigated, не resolved.** Не критично для работы, но блокирует чистое решение R1 (идемпотентность по `last_message_id`).

---

### R7 — `generate_chat_summary` не инкрементален, сжимает заново `[низкий]`

**Где:** `tasks.py:683` — берёт `msgs[-40:]` и пересоздаёт summary целиком каждый раз. Не дописывает к существующему, теряет контекст начала длинного чата (>40 сообщений середина выпадает). Для big-picture cross-session это терпимо, но не идеально.

**Фикс:** инкрементальная суммаризация поверх существующего summary (как в `compress_chat_history`), либо явное «summary начала + последние N».

---

## 5. Будущие улучшения (Phase 2)

Включается **после** стабилизации Phase 1 (R1–R5 закрыты).

### 5.1. Единая модель summary (закрывает R6, разблокирует R1)
- Свести к одному полю `content` + `last_compressed_message_id` + `messages_count`.
- Миграция данных: `content := rolling_summary or summary_text`.
- Одна фоновая задача, идемпотентная по `last_compressed_message_id` — сжимает только новый хвост, дописывает к существующему. Гонка и R1 исчезают в корне.

### 5.2. RAG-память на pgvector (relevance scoring)
- `pgvector/pgvector:pg15`, `UserMemory.embedding = VectorField(1536)` + HNSW (cosine).
- Эмбеддинг факта при создании в `extract_memory_facts` (`text-embedding-3-small`).
- `build_memory_context` в RAG-режиме: top-K **семантически релевантных** текущему сообщению фактов вместо top-40 по recency. Резко снижает шум при сотнях фактов.
- `POST /api/v1/memory/search/`.

### 5.3. Фаззи-дедуп
- При вставке: косинус > 0.92 к существующему → обновить, не плодить. Дополняет точечный `content_key`.

### 5.4. Точный токен-каунт
- `tiktoken` для GPT, кэш токенайзера; эвристика-фолбэк для остальных. Делает порог сжатия точным.

### 5.5. Автоочистка устаревших фактов
- beat `prune_stale_memories` (ночью): деактивировать `is_active, not is_pinned`, не используемые > 90 дней. Требует поля `last_referenced_at` (миграция).

### 5.6. Приватность / контроль (паритет с ChatGPT Memory)
- Экспорт памяти (GDPR-like), полная очистка одним действием (частично есть — `/memory/clear/` чистит только auto).
- Аудит: какой факт использован в каком ответе (`times_referenced` / `last_referenced_at`).

### 5.7. Telegram: UI управления памятью
- В боте память **работает** (через `generate_ai_response`), но нет хендлера управления фактами. Mini App `/tg/` может переиспользовать `/account/memory/`-контур.

---

## 6. Спринт-план

> Ветка: `fix/persistent-memory-r3` от `studio-v3`. Каждый коммит атомарен, проект собирается.

### Спринт A — остаточные баги стоимости/корректности `[DONE — d841d55]`

| # | Статус | Закрывает |
|---|--------|-----------|
| A1 | DONE: `tasks.py:806` → `msg_count=msg_count`; гард `>= msg_count` | R1 |
| A1b | DONE: Redis-лок `memcompress:{chat_id}` + `finally: cache.delete` в compress | R1b |
| A2 | DONE: `_facts_cache_key` → `memfacts:{user_id}`; summaries свежо каждый раз | R2 |
| A3 | DISSOLVED: summaries больше не кэшируются после R2 | R3 |
| A4 | DONE: тесты переписаны — R1-регрессия, normalize_fact, исправлен сломанный патч | R5 |

### Спринт B — производительность горячего пути

| # | Статус | Описание | Файлы | Закрывает |
|---|--------|----------|-------|-----------|
| B1 | **DONE** (d841d55) | HARD_MSG_CAP=80 в `get_history_with_compression` | `aitext/memory.py` | R4 достаточно |
| B2 | **ОТЛОЖЕН** | Инкр. токен-кэш (Redis/ChatSummary). HARD_MSG_CAP уже ограничивает loop ≤80 итераций. Вернуться при реальном bottleneck на profiler. | `aitext/memory.py`, `aitext/models.py` + миграция | R4 полностью |

### Спринт C — единая модель summary `[ОТЛОЖЕН — требует миграции живой БД]`

> Текущее состояние: два поля (`rolling_summary` + `summary_text`) сосуществуют через read-fallback. Система работает корректно. Унификация — архитектурный долг, не критичный баг.
>
> Выполнять только как отдельный продуманный релиз: additive migration (новые поля + backfill) → переключить код → удалить старые поля в следующем релизе.

| # | Статус | Коммит | Файлы | Закрывает |
|---|--------|--------|-------|-----------|
| C1 | ОТЛОЖЕН | `refactor(memory): unify summary into content + last_compressed_message_id` | `aitext/models.py` + миграция + data-migration | R6 |
| C2 | ОТЛОЖЕН (зависит от C1) | `refactor(memory): idempotent compress by last_compressed_message_id` | `aitext/tasks.py`, `aitext/memory.py` | R1 (root), R7 |
| C3 | ОТЛОЖЕН (зависит от C1) | `fix(memory): incremental generate_chat_summary` | `aitext/tasks.py:657` | R7 |

### Спринт D — Phase 2 (RAG) `[БУДУЩЕЕ — отдельная фаза]`

> Требует: pgvector в docker-compose, новый образ postgres, миграция + backfill эмбеддингов. Отдельная задача после стабилизации Phase 1.

| # | Статус | Коммит | Файлы |
|---|--------|--------|-------|
| D1 | БУДУЩЕЕ | `feat(memory): pgvector infra + UserMemory.embedding + HNSW` | `requirements.txt`, `docker-compose.yml`, миграция |
| D2 | БУДУЩЕЕ | `feat(memory): embed facts on extract + backfill command` | `aitext/tasks.py`, management-команда |
| D3 | БУДУЩЕЕ | `feat(memory): relevance-scored build_memory_context + /memory/search/` | `aitext/memory.py`, `api/views/memory.py` |
| D4 | БУДУЩЕЕ | `feat(memory): prune_stale_memories beat (90d, last_referenced)` | `aitext/models.py` + миграция, `aitext/tasks.py`, `config/celery.py` |

---

## 7. Что работает правильно (зафиксировать)

1. **Cross-channel память** — единый `CustomUser` для web и Telegram. Telegram-бот получает память автоматически через `generate_ai_response` (`telegram_bot/handlers/chat.py:95`). (Studio — отдельный пайплайн, память не использует, см. Executive Summary.)
2. **Грейсфул-деградация** — все интеграции в `try/except`, память не роняет генерацию (`chats.py:514`, `tasks.py:515`).
3. **Память бесплатна** — фоновые задачи на дешёвом DeepSeek V3, звёзды не списываются.
4. **Двойной тоггл** — глобальный `memory_enabled` + per-chat `Chat.settings['memory_enabled']`, проверяется в `build_memory_context`.
5. **Дедуп в два эшелона** — `existing_preview` в промпте LLM (первая линия) + `content_key` UniqueConstraint (вторая).
6. **Полный UI** — `/account/memory/` с CRUD, фильтрами, pin/active, историей сессий, очисткой. Без эмодзи, Lucide-иконки, соответствует дизайн-системе.
7. **Безопасный порядок DRF-роутов** — `<int:pk>` не перехватывает `clear`/`summaries`.
8. **Инвалидация кэша на мутациях API** — все CRUD-операции вызывают `invalidate_memory_cache` (`api/views/memory.py`).

---

## Приложение: карта файлов (текущее состояние)

| Компонент | Файл:строки | Состояние |
|-----------|-------------|-----------|
| Ядро памяти | `src/aitext/memory.py` | реализовано; R1/R2/R4/R5 закрыты; Sprint B2 ОТЛОЖЕН; Sprint C ОТЛОЖЕН |
| Модели | `src/aitext/models.py:509–592` | реализовано; R6 (два поля summary) mitigated — Sprint C ОТЛОЖЕН |
| `extract_memory_facts` | `src/aitext/tasks.py:534–654` | реализовано, B3/B13/R3 закрыты |
| `generate_chat_summary` | `src/aitext/tasks.py:657–723` | реализовано; R7 (не инкрементально) — тех. долг, Sprint C ОТЛОЖЕН |
| `compress_chat_history` | `src/aitext/tasks.py:726–810` | реализовано; R1/R1b ЗАКРЫТЫ (Round 3) |
| `summarize_stale_chats` (beat) | `src/aitext/tasks.py:813–858` | реализовано (B14) |
| Триггер extract (Celery) | `src/aitext/tasks.py:508–514` | есть |
| Триггер extract (SSE) | `src/api/views/chats.py:506–515` | есть (B1 закрыт) |
| Триггер summary (новое сообщение) | `src/api/views/chats.py:139–151` | есть (B6 закрыт) |
| Интеграция Celery-путь | `src/aitext/tasks.py:289–323` | есть |
| Интеграция SSE-путь | `src/api/views/chats.py:366–412` | есть |
| Beat-расписание | `src/config/celery.py:36–39` | есть |
| DRF API `/memory/` | `src/api/views/memory.py`, `src/api/urls.py:148–153` | реализовано |
| Сериализаторы | `src/api/serializers/memory.py` | реализовано |
| Frontend `/account/memory/` | `frontend/app/account/memory/page.tsx` | реализовано |
| API-клиент | `frontend/lib/api/memory.ts` | реализовано |
| `memory_enabled` | `src/users/models.py:488` | есть |
| Тесты | `src/aitext/test_memory.py` | R5 закрыт — R1-регрессия, normalize_fact, fix patch |
