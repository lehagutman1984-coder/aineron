# PERSISTENT MEMORY — Технический аудит и production-grade план исправлений

> **Статус документа:** это аудит **уже реализованной** системы Persistent Memory (не greenfield-спецификация).
> Код существует и работает в проде: `src/aitext/memory.py`, задачи `extract_memory_facts` / `generate_chat_summary`
> в `src/aitext/tasks.py`, две точки интеграции (`tasks.py` — Celery, `api/views/chats.py` — SSE),
> модели `UserMemory` / `ChatSummary` в `src/aitext/models.py`.
>
> Документ содержит: (0) TL;DR со статусом, (1) все найденные баги с severity и фиксами,
> (2) что работает правильно, (3) архитектурные улучшения, (4) пошаговые коммиты, (5) Phase 2.

---

## 0. TL;DR / статус

**Вердикт:** система формально работает, но **ключевая функция (автоизвлечение фактов) фактически мертва для основного канала** (веб-чат через SSE), а механизм сжатия истории **почти никогда не запускается** на моделях с большим контекстом и при этом **молча теряет старые сообщения**. Плюс два бага класса «потеря данных» в дедупликации.

### Светофор найденного

| # | Проблема | Severity | Файл:строка |
|---|----------|----------|-------------|
| B1 | SSE-путь не вызывает `extract_memory_facts` — факты не извлекаются при обычном веб-использовании | **критический** | `api/views/chats.py:496` |
| B2 | Compression silent-drop: под порогом возвращаем `all_msgs[-RECENT_WINDOW:]`, теряя 1..N−20 сообщений без сжатия | **критический** | `aitext/memory.py:164–166` |
| B3 | `content_key` коллизии → молчаливая потеря НОВЫХ фактов (`continue`); пробелы вырезаются | **высокий** | `tasks.py:611–613`, `models.py:566` |
| B4 | `update_rolling_summary` — lost update при конкурентных сообщениях (read-modify-write не атомарен) | **высокий** | `memory.py:217–229`, `chats.py:391–397` |
| B5 | Синхронное сжатие через DeepSeek прямо в SSE-запросе — блокирует TTFB на несколько секунд | **высокий** | `chats.py:391`, `memory.py:197–208` |
| B6 | `generate_chat_summary` триггерится только при новом чате с **той же** нейросетью | **высокий** | `chats.py:142–149` |
| B7 | Два несогласованных суммаризатора пишут один `ChatSummary` (`rolling_summary` vs `summary_text`), читаются в разных местах, не сводятся | **высокий** | `memory.py:101`/`143`, `tasks.py:638–689` |
| B8 | `generate_chat_summary` режет `dialogue[:5000]` после сборки oldest-first → суммируется начало, свежак теряется | **средний** | `tasks.py:662–666,680` |
| B9 | HTML в `content` попадает в compression/summary input при пустом `plain_text` | **средний** | `memory.py:160,182`, `tasks.py:552,664` |
| B10 | `_CHARS_PER_TOKEN = 0.35` неточен для кириллицы (рус. токенизируется ~2–3 симв./токен) | **средний** | `memory.py:19,46–50` |
| B11 | `build_memory_context` бьёт в БД на КАЖДОМ сообщении (2 запроса), без кэша | **средний** | `memory.py:82–99` |
| B12 | `%-d` в `strftime` падает на Windows → теряются все past-summaries в dev/test | **низкий** | `memory.py:101` |
| B13 | Гонка дедупа в `extract_memory_facts` (existing_keys до LLM) — но `UniqueConstraint` спасает, только лишний LLM-вызов | **низкий** | `tasks.py:557–560,612` |
| B14 | rolling_summary растёт бесконечно, если пользователь не открывает новый чат (summary_text не триггерится) | **средний** | следствие B6+B7 |

### Что нужно сделать в первую очередь (минимальный набор для прод-стабильности)
1. **B1** — добавить `extract_memory_facts.delay()` в конец SSE-стрима.
2. **B2** — вернуть `all_msgs` вместо `all_msgs[-RECENT_WINDOW:]` в ветке «всё помещается».
3. **B3** — централизовать `normalize_fact()` (сохранять пробелы) и заменить `continue` на `update_or_create` либо суффикс-дизамбигуацию.
4. **B5 + B4** — вынести сжатие в Celery-задачу, убрать синхронный DeepSeek из запроса.

---

## 1. Найденные баги и проблемы

> Severity: **критический** (ломает функцию/теряет данные в дефолтном сценарии) → **высокий** → **средний** → **низкий**.
> Для критических/высоких приведён точный фикс-код. Для средних/низких — однострочное решение.

---

### B1 — SSE-путь НИКОГДА не извлекает факты `[критический]`

**Где:** `src/api/views/chats.py`, генератор `generate()` финализируется на строке **496**:

```python
                assistant_message.status = Message.Status.COMPLETED
                assistant_message.save()              # ← строка 496

                yield _sse({ "type": "done", ... })   # ← и всё, никакого .delay()
```

**Проблема.** Триггер `extract_memory_facts.delay(chat.id)` есть **только** в Celery-пути (`tasks.py:497–501`, по `completed_count % 3 == 0`). Но обычный веб-чат идёт через **SSE-стрим** (`StreamMessageView` в `chats.py`), который генерирует ответ сам, в потоке, и Celery `generate_ai_response` для текста **не вызывает**. Значит при нормальном веб-использовании факты **не извлекаются вообще никогда**. `UserMemory` наполняется только в каналах, идущих через Celery (Telegram-бот, Studio, фолбэки) — то есть ядро фичи мертво для главного канала.

**Фикс.** После успешного завершения стрима (после `assistant_message.save()` на 496) запустить фоновую задачу. Триггерить так же, как в Celery — каждые 3 ответа ассистента, чтобы не дёргать LLM на каждое сообщение:

```python
                assistant_message.status = Message.Status.COMPLETED
                assistant_message.save()

                # ── Persistent Memory: извлечение фактов (фон, каждые 3 ответа) ──
                try:
                    from aitext.tasks import extract_memory_facts
                    completed_count = chat.messages.filter(
                        role='assistant', status=Message.Status.COMPLETED
                    ).count()
                    if completed_count % 3 == 0:
                        extract_memory_facts.delay(chat.id)
                except Exception:
                    pass  # память не должна ронять стрим

                yield _sse({ "type": "done", ... })
```

> Примечание: `chat`, `request.user` доступны в замыкании? `chat` — да (захвачен выше). Если в замыкании виден только `chat` через closure — он есть (`chat.id` используется на 435). Если нет — захватить `chat_id = chat.id` рядом с `user_msg_id = user_message.id` (строка 449) и фильтровать по `chat_id`.

---

### B2 — Compression silent-drop: теряем 1..N−20 сообщений без сжатия `[критический]`

**Где:** `src/aitext/memory.py`, строки **164–166**:

```python
    if overhead + history_tokens <= token_threshold:
        # Всё помещается — берём последние RECENT_WINDOW
        return all_msgs[-RECENT_WINDOW:], rolling      # ← БАГ
```

**Проблема — посчитаем математику, это не edge-case, а дефолт.**
`token_threshold = context_window * 0.70`. Для `gpt-4o` / `claude` / `gemini`:
- gpt-4o: `0.70 × 128_000 = 89_600` токенов бюджета.
- claude: `0.70 × 200_000 = 140_000`.
- gemini: `0.70 × 1_000_000 = 700_000`.

Чат из 30–50 сообщений — это ~5–15k токенов. То есть `overhead + history_tokens <= token_threshold` истинно **практически для любого чата** на большой модели вплоть до сотен сообщений. В этой ветке мы возвращаем **только последние 20 сообщений** (`all_msgs[-RECENT_WINDOW:]`), а `rolling` при этом **пустой** (сжатие не запускалось). Сообщения `1 .. N−20` просто **выкидываются из контекста и нигде не сохранены**. Пользователь, написавший 25 сообщений, теряет первые 5 — хотя они спокойно влезали в окно.

Двойной вред: (а) теряем то, что влезало; (б) на gpt-4o/claude/gemini ветка сжатия (строки 168+) **практически никогда не выполняется**, потому что порог не достигается.

**Фикс.** Если всё помещается — отдаём **всю** историю, она по определению влезает:

```python
    if overhead + history_tokens <= token_threshold:
        # Всё помещается в окно — отдаём ВСЮ историю, ничего не теряем.
        return all_msgs, rolling
```

> Это устраняет потерю данных немедленно. Полноценное решение «когда история реально не влезает» остаётся в ветке ниже (строки 168+), но теперь оно срабатывает по делу, а не «никогда». См. также архитектурный фикс в Section 3 (вынос сжатия в задачу + хранение покрытого диапазона по `last_message_id`).

---

### B3 — `content_key` коллизии: молчаливая потеря НОВЫХ фактов `[высокий]`

**Где (дублируется в двух местах):**
- `src/aitext/models.py:566` (в `UserMemory.save()`):
  ```python
  self.content_key = re.sub(r'[^а-яёa-z0-9]', '', self.content.lower())[:255]
  ```
- `src/aitext/tasks.py:611–613` (в `extract_memory_facts`):
  ```python
  content_key = re.sub(r'[^а-яёa-z0-9]', '', content.lower())[:255]
  if content_key in existing_keys:
      continue                       # ← НОВЫЙ факт молча отбрасывается
  ```

**Проблема — это потеря данных, а не «лишний дедуп».** Регекс вырезает **в том числе пробелы**. Значит «Работает в Python» и «Работаетвpython» дают одинаковый `content_key = 'работаетвpython'`. Хуже — РАЗНЫЕ по смыслу факты схлопываются:
- «Любит Go» → `любитgo`
- «Любит Гоа» (отпуск) → `любитгоа` (ок, отличается) — но
- «Имя Алексей» и «Имя: Алексей.» → `имяалексей` (ок), а вот
- «Стек: Python, Go» и «Стек Python Go» → `стекpythongo` = одинаковые (это норм),
- однако «3 кота» и «3 кита» различаются, а «работа в банке» / «работав банке» — нет.

Реальная боль: при коллизии в `extract_memory_facts` срабатывает `continue` (строка 613) — **новый факт просто не сохраняется**, без лога, без альтернативы. А т.к. пробелы вырезаны, частота коллизий искусственно завышена.

**Фикс — централизовать нормализацию и сохранять пробелы (collapse, не strip):**

1. В `src/aitext/memory.py` добавить единую функцию (источник истины):
```python
import re

def normalize_fact(text: str) -> str:
    """Ключ дедупа: lowercase, без пунктуации, пробелы СХЛОПНУТЫ (не вырезаны)."""
    t = (text or '').lower().strip()
    t = re.sub(r'[^\w\s]', '', t, flags=re.UNICODE)   # убрать пунктуацию, оставить буквы/цифры/пробелы
    t = re.sub(r'\s+', ' ', t).strip()                 # схлопнуть пробелы
    return t[:255]
```

2. В `src/aitext/models.py` `UserMemory.save()` (строки 563–567) — использовать её:
```python
    def save(self, *args, **kwargs):
        if not self.content_key and self.content:
            from aitext.memory import normalize_fact
            self.content_key = normalize_fact(self.content)
        super().save(*args, **kwargs)
```

3. В `src/aitext/tasks.py` `extract_memory_facts` (строки 610–631) — заменить `continue` на безопасный upsert, чтобы НОВЫЙ факт не терялся при близком ключе. Если ключ реально занят — обновляем содержимое (свежая формулировка точнее), а не выкидываем:
```python
        from aitext.memory import normalize_fact
        content_key = normalize_fact(content)
        if not content_key:
            continue

        valid_categories = {'profile', 'preference', 'project', 'fact', 'skill'}
        if category not in valid_categories:
            category = 'fact'

        # update_or_create вместо «continue»: не теряем факт, обновляем формулировку.
        _, was_created = UserMemory.objects.update_or_create(
            user=user, content_key=content_key,
            defaults={'content': content, 'category': category,
                      'source': 'auto', 'source_chat': chat},
        )
        if was_created:
            existing_keys.add(content_key)
            added += 1
```

> `existing_preview` (строки 562–566) по-прежнему отдаём в промпт LLM, чтобы модель сама не плодила почти-дубли — это первая линия дедупа, `content_key` — вторая.

---

### B4 — `update_rolling_summary`: lost update при конкурентных сообщениях `[высокий]`

**Где:** `src/aitext/memory.py:217–229` + вызов в `chats.py:391–397` / `tasks.py:304–310`.

**Уточнение механизма (важно — НЕ IntegrityError).** `get_or_create` сам по себе **не падает** под конкуренцией: Django оборачивает create в savepoint и при `IntegrityError` повторяет `get`. Так что строка не «теряется из-за проглоченного IntegrityError». Реальный баг — **lost update**:

```
Запрос A: get_history_with_compression → new_rolling_A   ┐
Запрос B: get_history_with_compression → new_rolling_B   ┘  (читают одинаковое состояние)
Запрос A: update_rolling_summary(new_rolling_A)  → save
Запрос B: update_rolling_summary(new_rolling_B)  → save  (перетирает A)
```

Read-modify-write растянут между `get_history_with_compression` (чтение + LLM-сжатие) и `update_rolling_summary` (запись) и **не атомарен**. При двух одновременных сообщениях в один чат побеждает последний писатель; результат сжатия одного из них теряется. Плюс `except Exception` (строка 228) маскирует любые реальные ошибки записи в `warning`.

**Фикс (тактический — атомарный upsert с блокировкой):**
```python
from django.db import transaction

def update_rolling_summary(chat, new_rolling: str) -> None:
    from aitext.models import ChatSummary
    if not new_rolling:
        return
    try:
        with transaction.atomic():
            cs, _ = ChatSummary.objects.select_for_update().get_or_create(
                chat=chat,
                defaults={'summary_text': '', 'rolling_summary': new_rolling},
            )
            if cs.rolling_summary != new_rolling:
                cs.rolling_summary = new_rolling
                cs.save(update_fields=['rolling_summary', 'updated_at'])
    except Exception as e:
        logger.warning(f'[memory] update_rolling_summary error for chat {chat.id}: {e}')
```

> `select_for_update()` сериализует конкурентные записи в один и тот же `ChatSummary`. **Стратегический фикс** (предпочтительный): вынести само сжатие в Celery-задачу (см. B5 и Section 3) — тогда сжатие идёт вне горячего пути и идемпотентно по `last_message_id`, гонка исчезает в корне.

---

### B5 — Синхронный DeepSeek-вызов в SSE-запросе блокирует TTFB `[высокий]`

**Где:** `src/api/views/chats.py:391` вызывает `get_history_with_compression(...)` **до** старта стрима; внутри (`memory.py:197–208`) — синхронный `client.chat.completions.create(model='deepseek-v3', ...)`.

**Проблема.** Когда история перешагивает порог, сжатие выполняется **синхронно прямо в HTTP-запросе**, до того как пользователь увидит первый токен. Это +несколько секунд к Time-To-First-Token на каждом сообщении длинного чата. Хуже — ветка не гейтится: при каждом сообщении выше порога DeepSeek дёргается **заново** (пересжатие тех же сообщений). На top-1 платформе с потоком запросов это и латентность, и лишние деньги, и нагрузка на провайдера.

**Фикс (архитектурный — единственно правильный):**
1. Из горячего пути убрать LLM-сжатие. `get_history_with_compression` должна быть **чистым чтением**: вернуть последние `RECENT_WINDOW` сообщений + уже сохранённый `rolling_summary`/`summary_text` из `ChatSummary`. Без сетевых вызовов.
2. Решение «пора сжать» принимать по дешёвому порогу (кол-во несжатых сообщений) и запускать **Celery-задачу** `compress_chat_history.delay(chat.id)` (или переиспользовать `generate_chat_summary`), которая считает токены, зовёт DeepSeek и пишет результат с `last_message_id` покрытия.
3. В запросе никогда не ждём LLM — показываем то, что уже сжато.

Скелет чистой версии (Section 3.2 содержит полный новый `memory.py`):
```python
def get_history_with_compression(chat, exclude_msg_id=None):
    from aitext.models import Message, ChatSummary
    qs = chat.messages.filter(status=Message.Status.COMPLETED)
    if exclude_msg_id:
        qs = qs.exclude(id=exclude_msg_id)
    recent = list(qs.order_by('-created_at')[:RECENT_WINDOW]); recent.reverse()
    summary = ''
    try:
        cs = ChatSummary.objects.get(chat=chat)
        summary = cs.rolling_summary or cs.summary_text or ''
    except ChatSummary.DoesNotExist:
        pass
    return recent, summary    # никаких сетевых вызовов
```

> Побочный бонус: устраняет B4 (гонку) — запись `rolling_summary` теперь только в одной фоновой задаче.

---

### B6 — `generate_chat_summary` триггерится только при новом чате с ТОЙ ЖЕ нейросетью `[высокий]`

**Где:** `src/api/views/chats.py:142–149`:
```python
            prev_chat = (
                Chat.objects.filter(user=request.user, network=network)   # ← фильтр по network
                .exclude(id=chat.id).order_by('-updated_at').first()
            )
            if prev_chat and prev_chat.messages.filter(...COMPLETED).count() >= 4:
                generate_chat_summary.delay(prev_chat.id)
```

**Проблема.** Суммаризация прошлого чата запускается **только** когда пользователь создаёт новый чат **с той же нейросетью**. Сценарии, в которых summary не создаётся НИКОГДА:
- открыл новый чат с **другой** моделью (gpt-4o → claude) — старый gpt-4o-чат не суммаризируется;
- вообще не создаёт новых чатов, сидит в одном — summary не появляется (а `rolling_summary` пухнет, см. B14);
- первый чат пользователя — `prev_chat` нет.

Итог: `ChatSummary.summary_text` у большинства чатов остаётся пустым, и блок «Прошлая сессия» в `build_memory_context` (memory.py:91–103) почти всегда пуст. Cross-session память не работает.

**Фикс.** Двойной триггер:
1. Убрать привязку к `network` — суммаризировать предыдущий **любой** активный чат:
```python
            prev_chat = (
                Chat.objects.filter(user=request.user)
                .exclude(id=chat.id).order_by('-updated_at').first()
            )
```
2. Добавить **периодический Celery-beat** для чатов без свежего summary и для «брошенных» (последнее сообщение > 24ч назад) — см. Section 3.3. Это закрывает сценарии «не создаёт новых чатов» и «сменил модель».

---

### B7 — Два несогласованных суммаризатора пишут один `ChatSummary` `[высокий]`

**Где:**
- `rolling_summary` пишет синхронный путь: `chats.py:397` / `tasks.py:310` → `update_rolling_summary` (memory.py:217).
- `summary_text` пишет фоновая `generate_chat_summary` (tasks.py:638–689, `cs.save()` в районе 689).
- Читают их **в разных местах и по-разному**: `build_memory_context` берёт `summary_text` прошлых чатов (memory.py:103: `s.summary_text[:500]`), а `get_history_with_compression` берёт `rolling_summary` текущего (memory.py:143–144).

**Проблема.** Это два независимых поля одной строки, никем не сводимых:
- `rolling_summary` — «сжатое начало текущей сессии», обновляется в горячем пути.
- `summary_text` — «финальное резюме», обновляется при открытии нового чата.

Они описывают пересекающийся контент, но никогда не согласуются. В `build_memory_context` для **прошлых** чатов читается `summary_text` — который из-за B6 почти всегда пуст. А `rolling_summary` текущего чата для cross-session не используется. Архитектурно это два полу-механизма вместо одного.

**Фикс (архитектурный, Section 3).** Свести к **одной** модели смысла: одно поле `content` + `last_message_id` (докуда покрыто) + `messages_count`. Одна фоновая задача его поддерживает (инкрементально дописывает по мере роста чата). Горячий путь только читает. `build_memory_context` для прошлых чатов и `get_history_with_compression` для текущего читают одно и то же поле. Это совмещает «rolling» и «final» в один непротиворечивый артефакт.

---

### B8 — `generate_chat_summary` режет не тот конец диалога `[средний]`

**Где:** `src/aitext/tasks.py:662–666` собирает `dialogue` oldest-first по **всем** сообщениям, затем 680: `dialogue[:5000]`.

**Проблема.** Сборка идёт от старых к новым (`order_by('created_at')`), потом берётся первые 5000 символов. На длинном чате это означает: суммаризируется **начало** диалога, а свежие (самые важные для контекста) сообщения **отрезаются**. Логика «сжать старое, сохранить свежее» инвертирована.

**Фикс.** Суммаризировать только то, что выпадает за окно (старое), а не весь чат, и не резать хвост: сжимать `completed[:-RECENT_WINDOW]` (как в Section 3.3 `generate_chat_summary`), а лимит применять по началу осознанно (или инкрементально к уже существующему summary). Если резать — резать **старое** начало при наличии прошлого summary, а не свежие сообщения.

---

### B9 — HTML из `content` попадает в LLM-вход `[средний]`

**Где:** `memory.py:160` (`(m.plain_text or m.content or '')`), `memory.py:182`, `tasks.py:552`, `tasks.py:664`.

**Проблема.** `msg.content` — это HTML после `CodeFormatter.format_ai_response()`. `msg.plain_text` — сырой текст. У ранних/легаси-сообщений `plain_text` бывает пустым, тогда фолбэк на `content` тащит в compression/summary/extraction вход `<pre>`, `<code class="...">`, `<span>` и пр. Это раздувает токены и сбивает LLM.

**Фикс.** Везде, где фолбэк на `content`, прогонять через strip HTML:
```python
import re
def _plain(msg) -> str:
    if msg.plain_text:
        return msg.plain_text
    return re.sub(r'<[^>]+>', ' ', msg.content or '')  # грубый, но достаточный strip
```
Применить в `memory.py` (compression input), `tasks.py` (`extract_memory_facts`, `generate_chat_summary`).

---

### B10 — `_CHARS_PER_TOKEN = 0.35` неточен для кириллицы `[средний]`

**Где:** `memory.py:19,46–50`.

**Проблема.** `0.35` означает «токенов = 0.35 × символов», т.е. ~2.86 символа на токен. Для **английского** реально ~4 симв./токен (т.е. коэффициент ~0.25). Для **русского** на токенайзерах OpenAI/DeepSeek кириллица дробится сильнее — часто ~2–3 символа на токен, иногда буква = токен. То есть `0.35` **завышает** оценку для англ. и **занижает** для рус. Это влияет на порог сжатия (B2) — оценка токенов кривая в обе стороны.

**Фикс (без tiktoken, дёшево).** Раздельный коэффициент по доле кириллицы, либо консервативный единый ~3 симв./токен:
```python
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cyr = sum('а' <= c.lower() <= 'я' or c.lower() == 'ё' for c in text)
    # кириллица ~2.5 симв/токен, латиница ~4 симв/токен
    cyr_frac = cyr / max(1, len(text))
    chars_per_token = 2.5 * cyr_frac + 4.0 * (1 - cyr_frac)
    return max(1, int(len(text) / chars_per_token))
```
> Для top-1 платформы корректнее подключить реальный токенайзер (`tiktoken` для GPT, фолбэк-эвристика для остальных) — см. Section 3.

---

### B11 — `build_memory_context` бьёт в БД на каждом сообщении `[средний]`

**Где:** `memory.py:82–99` — два запроса (`UserMemory` + `ChatSummary` past_summaries) **на каждый** запрос пользователя.

**Проблема.** При 40 фактах + 3 past-summaries это 2 запроса на каждое сообщение; контент почти не меняется между сообщениями. На потоке это лишняя нагрузка на Postgres в горячем пути.

**Фикс.** Кэш в Redis по пользователю, TTL ~5 мин, инвалидация при изменении фактов (см. Section 3.1):
```python
from django.core.cache import cache
def build_memory_context(user, chat):
    if not memory_enabled_for(user, chat):
        return ''
    cache_key = f'memctx:{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    ctx = _build_memory_context_uncached(user)   # текущая логика
    cache.set(cache_key, ctx, 300)
    return ctx
```
Инвалидация: в `extract_memory_facts` (после `update_or_create`) и в API мутациях `/memory/` — `cache.delete(f'memctx:{user.id}')`.

---

### B12 — `%-d` в `strftime` падает на Windows `[низкий]`

**Где:** `memory.py:101`: `s.updated_at.strftime('%-d %b %Y')`.

**Проблема.** `%-d` (без ведущего нуля) — **только Linux/glibc**. На Windows бросает `ValueError`. Прод на Linux/Docker, и вызов внутри `try/except` (92–105), так что в проде это деградация — но на **dev/test под Windows** исключение прерывает цикл и теряет **все** past-summaries, что искажает локальное тестирование.

**Фикс (кроссплатформенно, без strftime для дня):**
```python
            dt = s.updated_at
            date_str = f"{dt.day} {dt.strftime('%b %Y')}" if hasattr(dt, 'day') else ''
```

---

### B13 — Гонка дедупа в `extract_memory_facts` `[низкий]`

**Где:** `tasks.py:557–560` (existing_keys читается ДО LLM), `tasks.py:612`.

**Проблема.** Две одновременные `extract_memory_facts` (каждые 3 сообщения, Celery concurrency 200) видят одинаковый `existing_keys` и пытаются вставить одинаковые факты. **Но** `UniqueConstraint(user, content_key)` корректно отклоняет дубль — это **штатное** поведение, не баг данных. Единственная потеря — лишний LLM-вызов. После фикса B3 (`update_or_create`) даже исключения не будет.

**Фикс.** Достаточно B3. Опционально — Redis-лок `memextract:{chat_id}` на время задачи, чтобы не гонять LLM дважды. Не критично.

---

### B14 — rolling_summary растёт бесконечно `[средний]`

**Где:** следствие B6 + B7. Если пользователь не открывает новый чат, `generate_chat_summary` (создающая `summary_text`) не вызывается никогда, а `rolling_summary` накапливается через горячий путь.

**Фикс.** Закрывается периодическим beat-таском суммаризации (Section 3.3) + единой моделью summary (B7). После — rolling инкрементально пересжимается в фоне, не растёт неограниченно.

---

## 2. Что работает правильно (отдать должное)

1. **Модель данных в целом верная.** `UserMemory.user → CustomUser` (per-user, cross-channel) и `ChatSummary.chat → OneToOne(Chat)` — правильная декомпозиция. Cross-channel память (web/Telegram/Studio через один `CustomUser`) — архитектурно корректна.
2. **`UniqueConstraint(user, content_key)` с `condition=Q(content_key__gt='')`** — грамотно: уникальность дедупа только для непустых ключей, пустые не конфликтуют. Защищает БД от дублей даже при гонках (B13).
3. **Двойной тоггл памяти** — глобальный `CustomUser.memory_enabled` + per-chat `Chat.settings['memory_enabled']` (без миграции). Проверяется и в `build_memory_context`, и в `extract_memory_facts`. Чисто и без оверинжиниринга.
4. **Память бесплатна для пользователя** — фоновые задачи на дешёвом DeepSeek V3, звёзды не списываются. Сильное конкурентное преимущество.
5. **Грейсфул-деградация в фоновых задачах** — `extract_memory_facts` / `generate_chat_summary` обёрнуты в try/except и не роняют основной поток генерации (`tasks.py:502–503`, `chats.py:150–151`). Правильный приоритет: память не должна ломать ответ.
6. **Дедуп-промпт с `existing_preview`** (`tasks.py:562–566`) — отдаём LLM уже известные факты, чтобы она сама не плодила почти-дубли. Хорошая первая линия дедупа поверх `content_key`.
7. **Категоризация фактов** (profile/preference/project/fact/skill) и группировка в контексте — повышает читаемость system-промпта для модели.
8. **Сортировка `-is_pinned, -created_at`** при выборке фактов — закреплённые пользователем идут первыми. Разумный приоритет.
9. **`exclude_msg_id`** при сборке истории — корректно исключает текущее генерируемое сообщение из контекста.
10. **`max_tokens`/`temperature` низкие** в фоновых задачах (0.1–0.3, 400–600 токенов) — дёшево и детерминированно для извлечения/сжатия.

---

## 3. Архитектурные улучшения (план)

Цель — превратить «работает на бумаге» в production-grade для top-1 платформы.

### 3.1. Redis-кэш памяти пользователя (фикс B11)
- Ключ `memctx:{user.id}`, TTL 300с, хранит готовый текстовый блок памяти.
- Инвалидация при любой мутации `UserMemory` (extract-задача, API CRUD, toggle).
- Снимает 2 запроса/сообщение в горячем пути.

### 3.2. Чистый `get_history_with_compression` + асинхронное сжатие (фикс B2, B4, B5, B7)
- Горячий путь — **только чтение** (последние N сообщений + готовый summary). Никаких LLM-вызовов в запросе.
- Решение «сжать» — по дешёвому счётчику несжатых сообщений (`should_summarize`), запуск Celery-задачи.
- Единая модель summary: одно поле `content` + `last_message_id` + `messages_count` (свести `rolling_summary`/`summary_text`, B7). Миграция данных: при деплое заполнить `content := rolling_summary or summary_text`.
- Сжатие идемпотентно по `last_message_id`: задача сжимает только `(last_message_id .. конец−RECENT_WINDOW]`, инкрементально дописывая к существующему `content`. Гонки нет (одна точка записи + `select_for_update`).

### 3.3. Celery-beat периодическая суммаризация (фикс B6, B8, B14)
Новая задача в `celery.py` beat-расписании, раз в ~1–2 часа:
```python
@shared_task(ignore_result=True)
def summarize_stale_chats():
    from aitext.models import Chat, Message
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    # чаты с активностью, где summary отстаёт или чат «брошен»
    stale = Chat.objects.filter(
        messages__status=Message.Status.COMPLETED
    ).distinct()
    for chat in stale.iterator():
        if should_summarize(chat) or (chat.updated_at and chat.updated_at < cutoff):
            generate_chat_summary.delay(chat.id)
```
- Закрывает: смену модели (B6), «не создаёт новых чатов» (B14), брошенные чаты (>24ч).
- `generate_chat_summary` переписать: сжимать `completed[:-RECENT_WINDOW]`, не резать свежак (B8), инкрементально от существующего summary.

### 3.4. `extract_memory_facts` из SSE-пути (фикс B1)
- Добавить триггер в `chats.py` после стрима (см. B1).
- Унифицировать порог (каждые 3 ответа) в обоих путях — вынести в константу `EXTRACT_EVERY_N = 3` в `memory.py`.

### 3.5. Умная дедупликация (улучшение B3)
- **Phase 1:** централизованный `normalize_fact` (collapse пробелов), `update_or_create` вместо `continue`.
- **Phase 2 (pgvector):** при вставке считать косинусную близость нового факта к существующим; если > 0.92 — это дубль, обновлять, а не плодить. Фаззи-дедуп вместо точного `content_key`.

### 3.6. Relevance scoring памяти (Phase 2)
- Сейчас в контекст идут top-40 по recency/pin. На большом объёме это шум.
- Phase 2: эмбеддить текущее сообщение, выбирать top-K **семантически релевантных** фактов (`CosineDistance`). Резко повышает точность персонализации при сотнях фактов.

### 3.7. Точный подсчёт токенов (улучшение B10)
- Подключить `tiktoken` для GPT-моделей; для остальных — эвристика с раздельным коэффициентом кириллица/латиница. Кэшировать токенайзер.

### 3.8. HTML-strip как единая утилита (фикс B9)
- `_plain(msg)` в `memory.py`, использовать во всех LLM-входах (compression, extract, summary).

### 3.9. Автоочистка устаревших фактов
- Beat-таск `prune_stale_memories` (ночью): деактивировать `is_active=True, is_pinned=False`, не использованные > 90 дней. Требует поля `last_referenced_at` (или `times_referenced` + `updated_at`) — добавить миграцией.

### 3.10. Управление памятью пользователем (новый код — отсутствует)
- В репозитории **нет** DRF API `/api/v1/memory/` и страницы `/account/memory/` (проверено grep'ом — только `memory.py`, задачи и 2 точки интеграции). Это нужно построить: CRUD фактов, тоггл, очистка (спецификация — Section 4, коммиты 7–11 ниже). Без UI пользователь не видит и не контролирует, что о нём «помнят» — для top-1 это обязательно (приватность, доверие, паритет с ChatGPT Memory).

---

## 4. Пошаговые коммиты для исправлений

> Ветка: `fix/persistent-memory-audit` от текущей. Каждый коммит атомарен, проект собирается. После каждого — `git push`.

### Спринт A — критические фиксы (потеря данных и мёртвая фича)

| # | Коммит | Файлы | Severity закрывает |
|---|--------|-------|--------------------|
| A1 | `fix(memory): trigger extract_memory_facts from SSE stream` | `api/views/chats.py` (после :496) | B1 крит |
| A2 | `fix(memory): stop dropping in-window messages on under-threshold` | `aitext/memory.py:164–166` | B2 крит |
| A3 | `fix(memory): centralize normalize_fact, keep spaces, upsert facts` | `aitext/memory.py`, `aitext/models.py:566`, `aitext/tasks.py:611` | B3 высокий |
| A4 | `test(memory): regression tests for B1/B2/B3` | `aitext/test_memory.py` | — |

### Спринт B — устранение гонок и латентности (архитектура горячего пути)

| # | Коммит | Файлы |
|---|--------|-------|
| B1c | `refactor(memory): make get_history_with_compression read-only (no sync LLM)` | `aitext/memory.py`, `chats.py:391`, `tasks.py:304` |
| B2c | `feat(memory): async compress_chat_history celery task` | `aitext/tasks.py` |
| B3c | `fix(memory): select_for_update in summary upsert` | `aitext/memory.py:217` |
| B4c | `refactor(memory): unify rolling_summary+summary_text into single content+last_message_id` | `aitext/models.py` + миграция `aitext/00XX` + data-migration |

### Спринт C — покрытие суммаризации и качество

| # | Коммит | Файлы |
|---|--------|-------|
| C1 | `fix(memory): summarize prev chat of ANY network + beat task summarize_stale_chats` | `chats.py:142`, `aitext/tasks.py`, `config/celery.py` |
| C2 | `fix(memory): generate_chat_summary compresses old tail, not recent` | `aitext/tasks.py:662` |
| C3 | `fix(memory): strip HTML from content fallback in LLM inputs` | `aitext/memory.py`, `aitext/tasks.py` |
| C4 | `fix(memory): cross-platform date format (drop %-d)` | `aitext/memory.py:101` |
| C5 | `perf(memory): redis cache for build_memory_context + invalidation` | `aitext/memory.py`, `aitext/tasks.py` |
| C6 | `fix(memory): cyrillic-aware token estimation` | `aitext/memory.py:46` |

### Спринт D — управление памятью (новый функционал)

| # | Коммит | Файлы |
|---|--------|-------|
| D1 | `feat(memory): DRF API /api/v1/memory/ CRUD + settings + clear` | `api/views/memory.py` (новый), `api/urls.py` |
| D2 | `feat(memory): admin for UserMemory + ChatSummary` | `aitext/admin.py` |
| D3 | `feat(memory): /account/memory page + api client` | `frontend/app/account/memory/page.tsx`, `frontend/lib/api/memory.ts` |
| D4 | `feat(memory): chat memory indicator + per-chat toggle + nav` | `frontend/components/chat/*`, account nav, chat serializer |
| D5 | `feat(memory): prune_stale_memories beat task (90d, last_referenced)` | `aitext/models.py` + миграция, `aitext/tasks.py`, `config/celery.py` |

---

## 5. Улучшения Phase 2 (RAG / pgvector)

Включается **после** стабилизации Phase 1 (Спринты A–D зелёные).

### 5.1. Инфраструктура
- `pgvector` в `src/requirements.txt`; образ Postgres → `pgvector/pgvector:pg15` в `docker-compose.yml`.
- Миграция `VectorExtension()` (CREATE EXTENSION vector).
- Поле `UserMemory.embedding = VectorField(dimensions=1536, null=True)` + `HnswIndex` (cosine).

### 5.2. Заполнение эмбеддингов
- В `extract_memory_facts` при создании факта — `client.embeddings.create(model='text-embedding-3-small', input=content)` → `embedding`.
- Management-команда `backfill_memory_embeddings` для существующих.

### 5.3. Семантический поиск + relevance scoring (фикс шума при большом объёме)
- `POST /api/v1/memory/search/` — эмбеддит query, `order_by(CosineDistance('embedding', q))[:limit]`.
- `build_memory_context` RAG-режим: вместо top-N по recency — top-K по релевантности **текущему сообщению**. Это и есть Section 3.6.

### 5.4. Фаззи-дедуп (улучшение B3)
- При вставке: косинусная близость к существующим > 0.92 → дубль, обновлять `content`/`confidence`, не плодить. Дополняет точечный `content_key`.

### 5.5. Приватность и контроль (паритет с ChatGPT Memory)
- Экспорт памяти пользователем (GDPR-like), полная очистка одним действием.
- Аудит: какие факты использованы в каком ответе (для прозрачности) — поверх `times_referenced`/`last_referenced_at`.

---

## Приложение: карта файлов системы (текущее состояние)

| Компонент | Файл:строки | Состояние |
|-----------|-------------|-----------|
| Ядро памяти | `src/aitext/memory.py` | реализовано, содержит B2/B4/B5/B9/B10/B11/B12 |
| Модели | `src/aitext/models.py:509–592` | реализовано, B3 (save:566) |
| extract_memory_facts | `src/aitext/tasks.py:521–634` | реализовано, B3/B13 |
| generate_chat_summary | `src/aitext/tasks.py:637–689` | реализовано, B8 |
| Триггер extract (Celery) | `src/aitext/tasks.py:495–503` | есть |
| Интеграция Celery-путь | `src/aitext/tasks.py:280–311` | есть |
| Интеграция SSE-путь | `src/api/views/chats.py:366–404` | есть, **B1: нет триггера extract** |
| Триггер summary (новый чат) | `src/api/views/chats.py:139–151` | есть, B6 (фильтр network) |
| DRF API `/memory/` | — | **не существует** (построить, Спринт D) |
| Frontend `/account/memory/` | — | **не существует** (построить, Спринт D) |
| Тесты | `src/aitext/test_memory.py` | существует, дополнить регрессиями |
