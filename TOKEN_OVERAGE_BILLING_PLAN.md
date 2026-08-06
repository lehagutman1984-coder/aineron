# TOKEN_OVERAGE_BILLING_PLAN.md

Гибридный биллинг: плоская цена как включённый лимит + прозрачная доплата (overage)
за реальные токены только на моделях, где выходной токен кратно дороже входного.

Статус: **план, к реализации не приступали.** Дата составления: 2026-08-05.
Все ссылки вида `файл:строка` проверены по рабочей копии на момент составления.

---

## 0. Блокирующее решение по скоупу — прочитать первым

Задача была поставлена как «веб-чат **и Telegram-бот** списывают плоскую цену».
**Это верно только для веба.** Проверено по коду:

| Канал | Списание базовой плоской цены | Где |
|---|---|---|
| Веб, SSE-стриминг | **Да**, ДО генерации | `src/api/views/chats.py:402-407` — `spend_kopecks(cost_kopecks, type='spend', reference=f'chat:{assistant_message.id}')` |
| Веб, polling (не-стрим) | **Да**, ДО генерации | `src/api/views/chats.py:138`, `:281`, `:787` + `record_message_billing` |
| Telegram-бот, текст 1:1 | **НЕТ** | `src/telegram_bot/handlers/chat.py:176-177` — только `has_enough_kopecks()`, проверка без списания. `_create_messages` пишет `settings={}` (`chat.py:136`), т.е. без `billing_reference` |
| Telegram-бот, медиа | Да | `src/aitext/tasks.py:754` (fal-ветка) |
| Telegram-бот, ASR/TTS/research/группы | Да | `voice.py:121,201`, `research_cmd.py:76`, `group2.py:66` |

Единственное списание за текст в Celery-задаче — `src/aitext/tasks.py:1186-1202`,
и оно **мертво**: `getattr(settings, 'TEXT_BILLING_ENABLED', False)`, а
`src/config/settings.py` эту переменную **не определяет вообще** (grep по всему
`settings.py` — ноль совпадений). `.env:113` содержит `TEXT_BILLING_ENABLED=0`, но
Django её не читает — сам `.env:12` это и фиксирует: «МИНА двойного списания, НЕ
включать (и код её не читает)». Значит флаг постоянно False независимо от env.

**Следствие: текстовые сообщения в боте бесплатны.** Это соответствует известной,
но не закрытой задаче «BUG-1 revenue leak текст бота» из истории проекта.

**Почему это блокирует дизайн:** overage определён как «доплата сверх плоской
цены». Если плоская цена = 0, overage становится *единственным* списанием — это
другой продукт (чистый токенный биллинг в боте), другая коммуникация с
пользователем и другое решение по ценообразованию, а не техническая деталь.

### Принятое в этом плане разделение

- **Списание overage в v1 — только веб-путь**, где база фактически существует.
- **Метрирование (сбор токенов) — оба пути с первого спринта.** Бот дешевле
  инструментировать: `generate_ai_response` вызывает провайдера **без стриминга**
  (`src/aitext/tasks.py:1058`), `completion.usage` доступен сразу, `stream_options`
  не нужен.
- **Закрытие базового списания в боте вынесено в Спринт 0 как предусловие**
  с явной развилкой для основателя. Пока оно не принято — бот остаётся в режиме
  «меряем, не списываем», и это не блокирует Спринты 1-4 по вебу.

---

## 1. Проверенные факты, на которых стоит дизайн

### 1.1. Веб-SSE: генерация идёт до конца независимо от клиента

`StreamMessageView.post()` — `src/api/views/chats.py:317-745`.

Апстрим-стрим потребляется **внутри** генератора HTTP-ответа:

```python
# chats.py:593-598
stream = client.chat.completions.create(**kwargs)
for chunk in stream:
    delta = chunk.choices[0].delta if chunk.choices else None
    if delta and delta.content:
        full_text += delta.content
        yield _sse({"type": "token", "text": delta.content})
```

В файле **нет** ни `finally`, ни `GeneratorExit`, ни `close()` — проверено grep'ом
по всему `chats.py`. Единственный обработчик — `except Exception` на `:717`, а
`GeneratorExit` наследуется от `BaseException` и туда не попадает. Контраст:
dev-API в `src/api/views/chat.py:74` использует
`with client.chat.completions.create(stream=True, ...) as stream:` — контекст-менеджер,
закрывающий апстрим. В `chats.py:593` его нет.

**Ответ на ключевой вопрос задачи, из которого всё следует:**

1. Себестоимость у провайдера возникает вне зависимости от того, жив ли клиент —
   ничто не отменяет апстрим-вызов.
2. **При обрыве клиента usage-чанк не будет получен никогда** — он приходит
   последним, после того как итерация уже прервалась на `yield` (`:598`).
3. При обрыве `assistant_message.save()` (`:661`) не выполняется — сообщение
   остаётся `PENDING`, а плоское списание с `:403` не возвращается (оба пути
   возврата закрыты: inline-refund на `:726-727` под `except Exception`,
   а `refund_message_billing` бесполезен, т.к. `StreamMessageView` **не вызывает**
   `record_message_billing` — её вызовы только на `chats.py:143`, `:286`, `:792`).

**Правило, вытекающее отсюда (обязательное к соблюдению во всех спринтах).**
Важно различать два подслучая обрыва — они ведут себя по-разному:

> **(а) Обрыв до конца стрима** (не получен usage-чанк) → `source=MISSING` →
> **overage не начисляется**, плоская цена остаётся, факт логируется в мониторинг.
> Худший случай ограничен уже задеплоенным потолком `core/model_limits.py`.
>
> **(б) Обрыв после последнего чанка, но до того как клиент прочитал `done`**
> → usage получен, `status=COMPLETED` → **overage начисляется штатно**, но
> receipt-событие до клиента не доходит. Резервная поверхность прозрачности —
> строка `UserSpending` с отличимым описанием, которая автоматически видна в
> `/account/analytics/` (Спринт 3, задача 2). Отдельного UI не требуется.

Это снимает риск двойного/недосписания, о котором предупреждала постановка
задачи: settle никогда не пытается угадать стоимость незавершённой генерации.

### 1.1.1. Где settle выполняться НЕ должен

Соблазнительный вариант «settle в `finally` генератора» **отвергнут**, хотя
`finally` и срабатывает на `GeneratorExit`:

1. `done` отправляется на `chats.py:707-715` — **внутри `try`**, то есть до
   `finally`. Settle в `finally` означал бы, что receipt в `done` сообщает сумму,
   которая ещё не списана. Это ровно тот провал, от которого страхует
   требование «показывать фактически списанное».
2. SSE-путь на этом деплое обслуживается Daphne за nginx (см. `PERFORMANCE_PLAN.md`
   и историю перф-тюнинга). Своевременность доставки `GeneratorExit` до
   синхронного генератора под ASGI + буферизацией nginx не гарантирована —
   обнаружение обрыва может задержаться до таймаута, и settle в `finally` тихо не
   выполнится вовсе.

**Правильная точка — внутри `try`, сразу после `assistant_message.save()`
(`chats.py:661`), до `yield` события `done`.** Это корректно, потому что
usage-чанк приходит **последним** чанком стрима: к моменту выхода из цикла на
`:599` переменная `_usage` уже заполнена. `finally` остаётся только страховкой
(запись `source=MISSING` и перевод зависшего `PENDING` в `FAILED`).

### 1.2. Существующие примитивы и прецеденты

| Что | Где | Что берём |
|---|---|---|
| `spend_kopecks` / `add_kopecks` | `src/users/models.py:650-712` | Атомарный condition-UPDATE, ledger, идемпотентность по `unique(type, reference)` (`:1347-1353`) |
| **Ловушка**: дубликат reference | `src/users/models.py:680-683` | `IntegrityError` глотается, метод возвращает **`True`** — «уже списано» неотличимо от «списано сейчас» |
| Идиома «проверить, списывали ли уже» | `src/studio/billing.py:106-116` | Явный `BalanceTransaction.objects.filter(user, type, reference).exists()` **перед** неидемпотентными side-эффектами |
| reserve → settle | `src/sandboxes/billing.py:30-74` | Резерв максимума → возврат разницы. Нам нужно наоборот (доплата), но идиома reference'ов та же |
| Токенный расчёт + tiktoken | `src/studio/billing.py:24-29, 60-65` | `count_tokens()` с фолбэком на `cl100k_base` |
| Оценка токенов без tiktoken | `src/aitext/memory.py:87` | `estimate_tokens()`, language-aware |
| Конвенция фиче-флагов | `src/config/settings.py:394, 459, 535-542` | `X = os.getenv('X', '0') == '1'` |
| Мониторинг «списано без результата» | `src/aitext/tasks.py:2337-2424` | Паттерн скана `BalanceTransaction` + `notify_admins` |

### 1.3. Уже отгруженный потолок `max_tokens`

`src/core/model_limits.py` — подтверждено, живой модуль. Применён в:
`src/api/views/chat.py:187-192`, `src/api/views/anthropic.py:97-98` (внешний dev-API,
фикс от 2026-08-04), `src/aitext/tasks.py:513-514, 1052-1054` (Celery),
`src/api/views/chats.py:557-560` (веб-SSE, через ре-экспорт из `aitext.tasks`).
Для `claude*` потолок 16384, дефолт для неперечисленных семейств — 16384
(`model_limits.py:26, 31`).

**Это даёт дизайну важное свойство: худший случай overage вычислим заранее**
(потолок выходных токенов известен до вызова) — см. §4.3.

### 1.4. Существующая сломанная попытка — чего не повторять

`src/api/services/billing.py` (dev-API, НЕ основной чат):

- `NeuralNetwork.kopecks_per_1k_tokens` (`src/aitext/models.py:191-196`) — **единая
  смешанная ставка** input+output, раздельных цен нет.
- `get_kopecks_per_1k()` (`billing.py:19-25`) при незаданной ставке делит
  `cost_kopecks` на константу `_DEFAULT_TOKENS_PER_MESSAGE = 500` (`:16`) — это не
  токенная экономика, это та же плоская цена в маскировке.
- Дополнительно: `src/api/views/chat.py:96-98` читает `chunk.usage`, но вызов на
  `:74` **не задаёт `stream_options`** → usage всегда `None` → `charge_for_tokens`
  на `:108` получает нули.

**Решение: `src/api/services/billing.py` в этом плане не трогаем и не переиспользуем.**
Новый код — отдельный модуль. Ставки — **не в поле БД**, а в dict-модуле по
префиксу имени модели, по конвенции `core/model_limits.py:15-26` и
`studio/models_catalog.py:MODEL_TIER`. Отсутствие модели в таблице = чистая плоская
цена, overage невозможен. Это даёт per-model opt-in бесплатно и исключает
воспроизведение провала «поле = 0 у 127 моделей + тихий фейковый фолбэк».

---

## 2. Экономическая модель

### 2.1. Формула провайдера (подтверждена по реальным транзакциям)

```
Списание $ = (вход + выход × коэфф_завершения) × коэфф_модели / 500000
           ≡ (in_tok × in_$/1M + out_tok × out_$/1M) / 1e6
```

### 2.2. Курс USD→RUB, зашитый в приведённые числа

Реальная транзакция: Opus 5, ~1850 in / 10428 out, себестоимость ~21,60 ₽.

```
(1850 × 5 + 10428 × 25) / 1e6 = $0.26995   →   21.60 / 0.26995 = 80.0 ₽/$
```

Перепроверено на всех четырёх точках безубыточности из постановки — сходится
точно при **80 ₽/$**:

| Модель | in $/1M | out $/1M | Розница | Расчётный breakeven out-токенов @1850 in | Заявлено |
|---|---|---|---|---|---|
| Claude Fable 5 | 10 | 50 | 9 ₽ | (112500 − 18500)/50 = **1880** | ~1880 ✓ |
| Claude Opus 4.8 | 5 | 25 | 20 ₽ | (250000 − 9250)/25 = **9630** | ~9630 ✓ |
| Claude Opus 5 | 5 | 25 | 22 ₽ | (275000 − 9250)/25 = **10630** | ~10630 ✓ |
| GPT-5 Pro | 15 | 120 | 60 ₽ | (750000 − 27750)/120 = **6019** | ~6020 ✓ |

Курс выносится в настройку `TOKEN_OVERAGE_USD_RUB` (дефолт `80`), а не хардкодится:
при движении курса вся таблица пересчитывается одной переменной.

### 2.3. Расчёт доплаты

```python
cost_kopecks   = (in_tok × in_usd_per_1m + out_tok × out_usd_per_1m) / 1e6 × USD_RUB × 100
target_kopecks = round(cost_kopecks × TOKEN_OVERAGE_MARKUP)
overage_raw    = target_kopecks − flat_charged_kopecks
overage        = overage_raw if overage_raw >= threshold else 0
overage        = min(overage, cap)

threshold = max(TOKEN_OVERAGE_MIN_KOPECKS, flat_charged_kopecks × TOKEN_OVERAGE_MIN_FRACTION)
cap       = max(flat_charged_kopecks × TOKEN_OVERAGE_CAP_MULTIPLE,
                TOKEN_OVERAGE_ABS_CAP_KOPECKS)
```

### 2.3.1. Ловушка: `flat_charged_kopecks == 0`

`src/api/views/chats.py:352-374` в двух случаях выставляет `deduct_stars = False`,
и тогда плоское списание на `:403` **не происходит вовсе**:

1. `network.unlimited == True` **и** тариф пользователя входит в `network.tariffs`
   **и** дневной счётчик `NeuralNetworkDailyUsage.count < network.messages_limit`;
2. `network.is_free == True` (вкладка «Бесплатные», OpenRouter `:free`).

Наивный cap `flat × CAP_MULTIPLE` при `flat = 0` даёт `cap = 0`, то есть overage
структурно всегда ноль — пользователь на безлимитном тарифе мог бы вытянуть
16 384 выходных токена из Opus 5 (~67 ₽ себестоимости) бесплатно, и механизм
этого не заметил бы. Отсюда слагаемое `TOKEN_OVERAGE_ABS_CAP_KOPECKS` в формуле.

**Поправка (найдена при ревью, критична): абсолютный cap сам по себе НЕ
закрывает дыру — он открывает другую.** При `flat = 0` формула §2.3 даёт
`threshold = max(100, 0×0.25) = 100` (порог схлопывается до 1 ₽) и
`cap = max(0×2.0, 4000) = 4000`. Для безлимитного/бесплатного пользователя на
Opus 5 у потолка 16384 токена это означает `target ≈ 5362` коп. → **overage
40 ₽ спишется с пользователя, которому явно обещано «бесплатно» или
«безлимитно» на этой модели.** Это не утечка маржи, а обратная и более
плохая ошибка — тихое платное списание на объявленно-бесплатном пути.

**Правильное решение: `compute_overage` обязан возвращать `0`, если плоское
списание не происходило, а не пытаться прикрыть это через cap.** Источник
истины — не `flat_kopecks == 0` (это могло бы быть и легитимным нулём по
другой причине), а явный флаг того, выполнялось ли списание вообще:
добавить в `MessageTokenUsage` булево поле `flat_was_charged` (`True` только
если `chats.py:352-374` реально дошёл до `spend_kopecks` на `:403`, `False`
на путях `deduct_stars=False`/`is_free`). `compute_overage` в Спринте 2
проверяет `if not usage_row.flat_was_charged: return 0` первым шагом, до
всей остальной формулы. Тогда безлимитные/бесплатные модели остаются
защищены исключительно потолком `max_tokens` (что и является правильным для
них ответом), а `TOKEN_OVERAGE_ABS_CAP_KOPECKS` остаётся just-in-case
подстраховкой для случаев, не покрытых этим флагом, а не основным механизмом.

**Обязательная проверка перед Спринтом 3** — попадает ли хоть одна из семи
аудированных моделей в безлимитный тариф:

```sql
SELECT n.name, n.model_name, n.unlimited, n.is_free, n.messages_limit, t.name AS tariff
FROM aitext_neuralnetwork n
LEFT JOIN aitext_neuralnetwork_tariffs nt ON nt.neuralnetwork_id = n.id
LEFT JOIN users_tariff t ON t.id = nt.tariff_id
WHERE (n.unlimited = true AND n.messages_limit > 0) OR n.is_free = true
ORDER BY n.name;
```

- Если **ни одной из семи** там нет — зафиксировать этот факт в плане письменно,
  дыра закрыта фактически, `TOKEN_OVERAGE_ABS_CAP_KOPECKS` остаётся страховкой
  на случай будущего изменения каталога.
- Если какая-то есть — принять решение явно: либо вывести её из безлимита, либо
  положиться на абсолютный cap (тогда overage на безлимите станет единственным
  списанием — по сути та же развилка, что в §0 для бота, и её надо озвучить
  пользователям).

Бесплатные модели (`is_free`) в таблицу ставок **не входят по определению** —
`wholesale_rates()` вернёт `None`, overage невозможен. Отдельного действия не
требуется, но проверить это тестом.

**Порог, а не пол.** Нельзя использовать `core.money.apply_min_charge` —
`tokens_to_kopecks` (`api/services/billing.py:34`) поднимает **любое** списание до
`MIN_CHARGE_KOPECKS`. Применённое к overage, это выставило бы 0,10 ₽ практически на
каждое сообщение и уничтожило бы обещание «большинство не заметит разницы». Нужен
именно порог отсечения снизу — обратная операция.

### 2.4. Рекомендуемые стартовые значения (калибруются в Спринте 2)

| Параметр | Дефолт | Обоснование |
|---|---|---|
| `TOKEN_OVERAGE_USD_RUB` | `80` | Выведен из реальной транзакции, §2.2 |
| `TOKEN_OVERAGE_MARKUP` | `1.6` | Удерживает ~60 % маржи в хвосте, не 8× как на типичном сообщении |
| `TOKEN_OVERAGE_MIN_FRACTION` | `0.25` | Доплата меньше четверти плоской цены не начисляется |
| `TOKEN_OVERAGE_MIN_KOPECKS` | `100` (1 ₽) | Абсолютный порог — нет копеечных доплат |
| `TOKEN_OVERAGE_CAP_MULTIPLE` | `2.0` | Максимум за сообщение = 3× плоской цены суммарно; защита от шок-счёта |
| `TOKEN_OVERAGE_ABS_CAP_KOPECKS` | `4000` (40 ₽) | Абсолютный потолок доплаты; спасает случай `flat = 0` (§2.3.1) |

Проверка на реальных сценариях Opus 5 (flat 22 ₽ = 2200 коп.):

| Сценарий | in / out | Себестоимость | target ×1.6 | overage | Итог пользователю |
|---|---|---|---|---|---|
| Типичное сообщение | 1850 / 600 | 1,94 ₽ | 3,10 ₽ | 0 (< flat) | **22 ₽ — без изменений** |
| Средне-длинный | 1850 / 3000 | 6,74 ₽ | 10,78 ₽ | 0 (< flat) | **22 ₽ — без изменений** |
| Реальный инцидент | 1850 / 10428 | 21,60 ₽ | 34,56 ₽ | 12,56 ₽ (порог 5,50 ₽ пройден) | 34,56 ₽, маржа ×1.6 |
| Худший случай при потолке 16384 | 1850 / 16384 | 33,51 ₽ | 53,62 ₽ | 31,62 ₽ (cap 44 ₽ не сработал — 31,62 < 44) | 53,62 ₽, маржа ×1.6 |

**Поправка (найдена при реализации Спринта 2, `core/test_model_pricing.py` +
`aitext/test_token_metering.py::ComputeOverageTests`): строка «Худший случай»
выше и Fable-5-строка «Потолок 16384» ниже изначально считали `cap` как
`flat × CAP_MULTIPLE` (44 ₽ и 18 ₽ соответственно), не по формуле §2.3
`max(flat × CAP_MULTIPLE, ABS_CAP_KOPECKS)` — код в этом же документе (§2.3)
всегда использовал правильную формулу, разошлась только эта иллюстративная
таблица. Обе строки исправлены на числа, которые реально выдаёт код
(закреплено регрессионными тестами).**

Fable 5 (flat 9 ₽ = 900 коп.) — самая уязвимая модель, breakeven при 1880 out:

| Сценарий | in / out | Себестоимость | target ×1.6 | overage | Итог |
|---|---|---|---|---|---|
| Типичное | 1850 / 600 | 3,88 ₽ | 6,21 ₽ | 0 | **9 ₽ — без изменений** |
| 4000 out | 1850 / 4000 | 17,48 ₽ | 27,97 ₽ | 18,97 ₽ | 27,97 ₽ |
| Потолок 16384 | 1850 / 16384 | 67,02 ₽ | 107,23 ₽ | 40 ₽ (cap `max(1800, 4000)`=4000 сработал — 98,23 > 40) | 49 ₽ (cap), **убыток** |

Fable 5 в потолке всё ещё убыточна даже с overage из-за абсолютного cap. Это осознанный
размен «не выставлять шок-счёт» против «не потерять деньги на редком хвосте».
Решение: для Fable 5 в Спринте 2 отдельно оценить (а) снижение
`model_limits.MODEL_MAX_TOKENS_CAP['claude']` для этого семейства, либо
(б) per-model `cap_multiple` в таблице ставок. Данные для решения даст dry-run.

### 2.5. Таблица ставок v1 (только аудированные модели)

Семь моделей из постановки. Остальные ~120 — **без записи в таблице, значит без
overage вообще**, схему бэкфиллить не требуется.

| Ключ-префикс | in $/1M | out $/1M | Розница сегодня | Комментарий |
|---|---|---|---|---|
| `claude-fable-5` | 10 | 50 | 9 ₽ | Самый узкий запас; цена поднята 2026-08-04 с 6,5 ₽ |
| `claude-opus-4-8` | 5 | 25 | 20 ₽ | Ключ с дефисом — под реальный `model_name` в БД, не `claude-opus-4.8` |
| `claude-opus-5` | 5 | 25 | 22 ₽ | Триггер расследования |
| `gpt-5-pro` | 15 | 120 | 60 ₽ | |
| `gpt-5.4-pro` | 30 | 180 | — | Здоров (×3.47), метрируем ради данных |
| `gpt-5.3` | 60 | 60 | 30 ₽ | Аномальный плоский тариф провайдера, подтверждён 3 скриншотами; цена поднята 2026-08-04 с 14 ₽ |
| `gpt-5.6-terra` | 2 | 12 | — | Здоров (×15.2), метрируем ради данных |

**Точные ключи обязательно сверить с `NeuralNetwork.model_name` в проде** перед
кодированием — сопоставление префиксное (как `model_limits.py:36-38`), опечатка в
префиксе означает молчаливое отсутствие overage, а не ошибку.

---

## 3. Фиче-флаги и kill-switch

Двухуровневый выключатель по конвенции `settings.py:394, 459, 535-542`.

```python
# src/config/settings.py, рядом с MIN_CHARGE_KOPECKS (:628)
TOKEN_METERING_ENABLED   = os.getenv('TOKEN_METERING_ENABLED',   '0') == '1'
TOKEN_OVERAGE_ENABLED    = os.getenv('TOKEN_OVERAGE_ENABLED',    '0') == '1'
TOKEN_OVERAGE_DRY_RUN    = os.getenv('TOKEN_OVERAGE_DRY_RUN',    '1') == '1'
TOKEN_OVERAGE_USD_RUB    = float(os.getenv('TOKEN_OVERAGE_USD_RUB', '80'))
TOKEN_OVERAGE_MARKUP     = float(os.getenv('TOKEN_OVERAGE_MARKUP', '1.6'))
TOKEN_OVERAGE_MIN_FRACTION = float(os.getenv('TOKEN_OVERAGE_MIN_FRACTION', '0.25'))
TOKEN_OVERAGE_MIN_KOPECKS  = int(os.getenv('TOKEN_OVERAGE_MIN_KOPECKS', '100'))
TOKEN_OVERAGE_CAP_MULTIPLE = float(os.getenv('TOKEN_OVERAGE_CAP_MULTIPLE', '2.0'))
TOKEN_OVERAGE_ABS_CAP_KOPECKS = int(os.getenv('TOKEN_OVERAGE_ABS_CAP_KOPECKS', '4000'))
TOKEN_OVERAGE_MODELS     = os.getenv('TOKEN_OVERAGE_MODELS', '')  # CSV-allowlist, пусто = вся таблица
```

Уровни отключения, от мягкого к жёсткому:

1. Убрать модель из `TOKEN_OVERAGE_MODELS` — точечно, без редеплоя кода.
2. `TOKEN_OVERAGE_DRY_RUN=1` — считаем и пишем в БД, не списываем.
3. `TOKEN_OVERAGE_ENABLED=0` — расчёт не выполняется, метрирование продолжается.
4. `TOKEN_METERING_ENABLED=0` — полный откат к текущему поведению, включая
   отключение `stream_options` в SSE.

`TOKEN_OVERAGE_DRY_RUN` намеренно **дефолтится в `1`**: даже если кто-то включит
`TOKEN_OVERAGE_ENABLED` без чтения этого документа, деньги не спишутся.

Совместимость инстансов (CLAUDE.md «Два инстанса, один репозиторий»): все дефолты
безопасны и одинаковы, ветвления по `INTL_MODE` не требуется. Миграции —
additive и instance-agnostic.

---

## Спринт 0 — Предусловие: базовое списание в боте (решение основателя)

**Цель:** снять неопределённость §0. Кода в этом спринте может не быть вовсе.

### Задачи

1. Подтвердить масштаб утечки запросом на проде:
   ```sql
   SELECT n.name, COUNT(*) AS msgs, SUM(n.cost_kopecks) AS would_have_charged_kopecks
   FROM aitext_message m
   JOIN aitext_chat c ON c.id = m.chat_id
   JOIN aitext_neuralnetwork n ON n.id = c.neural_network_id
   WHERE m.role = 'assistant' AND m.status = 'completed'
     AND c.id IN (SELECT chat_id FROM telegram_bot_telegramchat)
     AND m.created_at >= NOW() - INTERVAL '30 days'
   GROUP BY n.name ORDER BY would_have_charged_kopecks DESC;
   ```
2. Развилка для основателя — три варианта, выбрать один:
   - **A. Включить базовое списание в боте** (рекомендуется). Реализация: в
     `telegram_bot/handlers/chat.py` после `_create_messages` вызвать
     `record_message_billing(assistant_msg, f'tg:{assistant_msg.id}', network.cost_kopecks)`
     и `user.spend_kopecks(...)` тем же reference, по образцу `chats.py:402-407`.
     Возврат при провале уже работает: `tasks.py:1250-1259` вызывает
     `refund_message_billing`, который читает ровно этот `billing_reference`.
     Требует коммуникации пользователям бота.
   - **B. Оставить бот бесплатным как маркетинговый канал** — тогда overage в боте
     не включается никогда, Спринты 1-4 остаются веб-only.
   - **C. Ввести в боте отдельную модель оплаты** — за рамками этого плана.
3. Удалить мёртвый код `TEXT_BILLING_ENABLED` (`tasks.py:1186-1202`) либо
   определить переменную в `settings.py`. Сейчас это ловушка: строки в `.env`
   создают ложное впечатление работающего переключателя.

### Готово, когда
Решение зафиксировано письменно; если выбран вариант A — базовое списание в боте
задеплоено и проверено живьём **до** Спринта 3.

### Риски
Включение списания в боте без предупреждения пользователей — репутационный риск
выше денежного. Это не техническая задача.

### Реализовано (2026-08-05) — вариант A, код-комплит, тесты зелёные, НЕ задеплоено

Решение основателя: включить базовое списание в боте.

При реализации выяснилось, что фактическая архитектура отличается от
черновика выше (написан до код-ревью, здесь — по факту прочтения кода):

- **`telegram_bot/handlers/chat.py::process_text` уже делал `has_enough_kopecks`
  ДО генерации** (не просто отсутствовавшая проверка, как предполагал черновик) —
  показывал пользователю красивый пейволл с кнопками Stars/Robokassa/сайт. Но
  это была только ПРОВЕРКА, не СПИСАНИЕ: реальное списание зависело от
  `TEXT_BILLING_ENABLED`-блока в `tasks.py:1186-1202`, который срабатывал
  (а) только если флаг вообще определён (не был), и (б) уже ПОСЛЕ успешной
  генерации, не блокируя её. Итог до фикса: пользователь с балансом ≥
  `cost_kopecks` мог писать в бот бесконечно бесплатно — баланс проходил
  проверку, но никогда не списывался.
- Использован **тот же pre-charge паттерн, что уже стоит на вебе**
  (`api/views/chats.py:136-143`, `compare.py:105-111`) — списание ДО постановки
  задачи в очередь, с `record_message_billing`, а не reference `tg:{id}` из
  черновика — взят **тот же `chat:{id}`**, что и у веба, специально ради
  единообразия и переиспользования уже написанного `refund_message_billing`
  без дополнительных веток.
- Новая функция `_charge_text_message` в `chat.py` (+ `charge_text_message` —
  `sync_to_async`-обёртка): `spend_kopecks` → `UserSpending` → `record_message_billing`,
  вызывается после создания сообщений, до `generate_ai_response.delay(...)`.
  При провале (гонка балансов между проверкой и списанием — user прислал два
  сообщения подряд) — сообщение помечается `FAILED`, пользователю показывается
  тот же пейволл, задача в очередь не ставится (бесплатной генерации не бывает).
- `TEXT_BILLING_ENABLED` определена в `settings.py` (дефолт `1`) — теперь это
  **safety-net post-charge**, а не основной механизм: для веба/бота она no-op
  (у сообщения уже есть `billing_reference`, `_skip=True`), но защищает пути
  без pre-charge (найден минимум один — `api/views/files.py` регенерация
  текстовой подписи, cost_kopecks проверяется, но не списывается явно).
- Попутно исправлен baг в самом `tasks.py`-фолбэке: `spend_kopecks` возвращает
  `False` при нехватке средств, но возврат не проверялся — `UserSpending`
  создавался как «успешный» даже когда денег фактически не сняли. Теперь
  создаётся только при реальном списании, иначе — `logger.warning`.
- Тесты: `src/telegram_bot/test_billing.py` (4/4 зелёных) — списание +
  `billing_reference`, блокировка при нехватке средств (баланс не двигается,
  `UserSpending` не создаётся), отсутствие двойного списания при retry
  (идемпотентность `spend_kopecks` по `(type, reference)`), возврат средств
  через `refund_message_billing` для бот-сообщения (подтверждено: функция
  канало-агностична, работает для бота без доп. кода).
- **НЕ выполнено**: деплой на прод. Это первый спринт плана, где включение в
  проде меняет реальное финансовое поведение для реальных пользователей бота
  (те, кто раньше писал бесплатно, начнут списываться) — требует отдельного
  подтверждения перед деплоем, не покрывается общим «работай автономно» по
  плану, см. чат с фаундером 2026-08-05.

---

## Спринт 1 — Только метрирование, ноль изменений в деньгах

**Цель:** получить достоверные данные о реальных токенах на всех путях. Ни одна
копейка не меняет владельца.

### Задачи

1. **Новая модель `MessageTokenUsage`** — `src/aitext/models.py` + миграция
   `aitext/00XX_message_token_usage.py` (последняя сейчас `0057_deactivate_deepseek_v3.py`).

   Почему новая модель, а не `api.models.TokenUsage` (`src/api/models.py:76-118`):
   у неё нет FK на `Message` (только `request_id: CharField`), и она отдаётся в
   `/account/usage/` как статистика dev-API — смешивание веб-чата туда исказит
   существующий отчёт. Почему не `Message.settings` (JSON): нужен именно
   запрашиваемый набор для маржинального анализа Спринта 2 и для реконсилера
   Спринта 3, а JSON-поле по этим полям не индексируется.

   ```python
   class MessageTokenUsage(models.Model):
       class Source(models.TextChoices):
           PROVIDER = 'provider', 'Ответ провайдера'
           ESTIMATE = 'estimate', 'Локальная оценка (tiktoken)'
           MISSING  = 'missing',  'Недоступно (обрыв клиента)'

       message = models.OneToOneField('aitext.Message', on_delete=models.CASCADE,
                                      related_name='token_usage')
       network = models.ForeignKey('aitext.NeuralNetwork', on_delete=models.SET_NULL,
                                   null=True, blank=True)
       model_name       = models.CharField(max_length=200, blank=True, default='')
       channel          = models.CharField(max_length=16, default='web')  # web | telegram
       prompt_tokens    = models.PositiveIntegerField(default=0)
       completion_tokens= models.PositiveIntegerField(default=0)
       source           = models.CharField(max_length=16, choices=Source.choices,
                                           default=Source.MISSING)
       flat_kopecks     = models.BigIntegerField(default=0)   # что списано плоско
       cost_kopecks     = models.BigIntegerField(default=0)   # себестоимость (Спринт 2)
       overage_kopecks  = models.BigIntegerField(default=0)   # рассчитанная доплата
       settled_kopecks  = models.BigIntegerField(default=0)   # фактически списано (Спринт 3)
       settled_at       = models.DateTimeField(null=True, blank=True)
       created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

       class Meta:
           indexes = [models.Index(fields=['-created_at', 'model_name'])]
   ```
   `OneToOneField` даёт защиту от дублей на уровне БД: повторный settle физически
   не создаст вторую строку.

2. **Новый модуль `src/aitext/token_metering.py`** — единственная точка записи:
   `record_usage(message, network, channel, prompt_tokens, completion_tokens, source, flat_kopecks)`,
   всё под `if not settings.TOKEN_METERING_ENABLED: return`, весь код в
   `try/except` с `logger.warning` — метрирование **никогда** не должно ронять
   генерацию.

3. **Celery-путь (бот + веб-polling)** — `src/aitext/tasks.py`.
   После `completion = client.chat.completions.create(**completion_kwargs)`
   (`:1058`), рядом с `message.save()` (`:1151`):
   ```python
   _u = getattr(completion, 'usage', None)
   record_usage(message, network, channel,
                getattr(_u, 'prompt_tokens', 0) or 0,
                getattr(_u, 'completion_tokens', 0) or 0,
                source=Source.PROVIDER if _u else Source.ESTIMATE, ...)
   ```
   Вызов не стриминговый — `usage` должен присутствовать без доп. параметров.
   `channel` определять по наличию `TelegramChat` на `chat` (или пробросить в
   `settings` сообщения из `telegram_bot/handlers/chat.py:204`).

4. **Верификационная задача — идёт ПЕРВОЙ, до правки `chats.py` (порядок
   изменён при ревью: изначально стояла после кодовой правки, что означало
   включение `stream_options` глобально ещё до того, как известно, держит ли
   его laozhang; при `400` от провайдера `chats.py` не оборачивает `create()`
   в `try` вокруг самого вызова стрима так, чтобы не уронить уже открытый SSE
   — итог был бы сломанный чат на проде под флагом, который считается
   «выключенным»).** Проверить, отдаёт ли laozhang.ai `usage` на стриме для
   всех 7 аудированных моделей. Это реселлер, соблюдение OpenAI-контракта
   **нельзя предполагать**. Тест — management-команда
   `src/aitext/management/commands/probe_stream_usage.py`, гоняющая короткий
   промпт по каждой модели и печатающая таблицу «модель / usage получен / значения».
   Учесть обёртку фолбэка: `src/aitext/providers.py` подменяет провайдера
   (`_PeekedStream:218`, `_CompletionsProxy.create:286`), kwargs проходят насквозь,
   но фактический провайдер может отличаться от primary — печатать и его.

   **План Б, если провайдер usage не отдаёт:** для высокорисковых моделей
   маршрутизировать веб-запросы на существующий не-стриминговый путь
   (`chats.py:154`/`:297` → Celery), где `usage` гарантирован. **Не** начислять
   overage по локальным оценкам tiktoken — расхождение токенизаторов у Claude и
   OpenAI слишком велико, чтобы выставлять по нему счета.

5. **Веб-SSE-путь** — `src/api/views/chats.py`. `stream_options` включается
   **не глобальным флагом, а allowlist'ом моделей, подтверждённых задачей 4**
   (`TOKEN_METERING_STREAM_USAGE_MODELS` — список `model_name`, пусто до
   прогона probe; модели вне списка продолжают работать как раньше, без
   `stream_options`, и просто не метрируются на SSE-пути до своей проверки).
   - Добавить в `kwargs` (`:585-591`), только если `network.model_name` в
     allowlist: `"stream_options": {"include_usage": True}`.
     Строка `:595` уже безопасна для usage-чанка (`chunk.choices[0].delta if chunk.choices else None`)
     — финальный чанк с пустым `choices` не уронит цикл.
   - Копить `usage` из чанков: `if getattr(chunk, 'usage', None): _usage = chunk.usage`.
     Usage-чанк приходит **последним**, поэтому после выхода из цикла на `:599`
     он уже доступен.
   - **Основной вызов `record_usage` — внутри `try`, сразу после
     `assistant_message.save()` (`:661`), до `yield` события `done`** (обоснование
     в §1.1.1; в Спринте 3 сюда же встанет settle).
   - **Дополнительно обернуть тело `generate()` в `try/finally`** — как страховку,
     не как основную точку. `GeneratorExit` на подвешенном `yield` запускает
     `finally` и **не** ловится `except Exception` на `:717`. В `finally`: если
     строка usage ещё не создана → записать `source=MISSING`.
   - `record_usage` реализовать через `update_or_create` по `message`, а не
     `create`: `OneToOneField` иначе бросит `IntegrityError`, когда сработают и
     основной путь, и страховочный `finally`.
   - Заодно закрыть смежный баг: в `finally` при `_usage is None` и
     `assistant_message.status == PENDING` пометить сообщение `FAILED` — сейчас
     оборванные сообщения висят `PENDING` навсегда (`chats.py:661` не достигается).

6. **Django-admin** для `MessageTokenUsage` (read-only, фильтры по `model_name`,
   `source`, дате) — чтобы Спринт 2 можно было анализировать без SQL-доступа.

### Готово, когда
`TOKEN_METERING_ENABLED=1` на проде минимум 5-7 дней; в `MessageTokenUsage` есть
строки со всех трёх каналов; доля `source='provider'` по аудированным моделям
известна и задокументирована; ноль изменений в `BalanceTransaction`.

### Что может пойти не так / что тестировать
- `stream_options` может вызвать `400` у части моделей → добавить per-model
  отключение и убедиться, что `except` вокруг `create()` не превращает это в
  сломанный чат. Тест: прогнать `probe_stream_usage` на всех 7 до включения на проде.
- `record_usage` внутри `finally` при обрыве выполняется в контексте закрывающегося
  генератора — запрещено делать `yield`, разрешён только DB-write. Проверить
  вручную: начать стрим, закрыть вкладку, убедиться что строка `source='missing'`
  создалась и исключений в логе нет.
- Рост нагрузки на БД: +1 INSERT на сообщение. Незначительно, но замерить.

### Реализовано (2026-08-05) — код-комплит, тесты зелёные, НЕ задеплоено

- `MessageTokenUsage` + миграция `aitext/0058_message_token_usage.py` (включая
  `flat_was_charged` — заложен сразу по фиксу §2.3.1, не как доп. миграция).
- `src/aitext/token_metering.py`: `record_usage()` (`update_or_create` по
  `message`, идемпотентно) + `channel_for_chat()`.
- Celery-путь (`tasks.py`): usage записывается **после** блока
  `TEXT_BILLING_ENABLED`, а не сразу после `completion = client....create()`,
  как в черновике плана — иначе `flat_was_charged` для post-charge фолбэк-пути
  (`files.py`) записался бы `False`, хотя секундами позже деньги всё-таки
  спишутся. Источник для `flat_was_charged`/`flat_kopecks`: `billing_reference`
  в `message.settings` (pre-charge) ИЛИ локальный флаг фактического списания
  из фолбэк-блока (тот не пишет `billing_reference`, только реально списывает).
- `probe_stream_usage` (management-команда) написана и готова к прогону на
  проде для 7 аудированных моделей — **ещё не запускалась** (нужен доступ к
  живым `LAOZHANG_API_KEY`, требует явного окна на реальные, хоть и копеечные,
  вызовы провайдера).
- Веб-SSE-путь (`api/views/chats.py`, `StreamMessageView`): **важная находка
  при чтении реального кода — этот путь НЕ вызывает `record_message_billing`**
  (в отличие от `TariffPayView`/`compare.py`), списывает `spend_kopecks`
  напрямую и возвращает деньги через прямой `add_kopecks(..., type='refund')`
  в except-ветке без использования `billing.py`. Значит для этого пути
  `flat_was_charged` берётся из локальной переменной `deduct_stars`, а не из
  `message.settings['billing_reference']`, как предполагал черновик плана.
  `stream_options` добавляется в kwargs **только** если модель есть в
  `TOKEN_METERING_STREAM_USAGE_MODELS` (allowlist из .env, пусто по
  умолчанию) — глобального переключателя нет, ничего не может сломаться,
  пока конкретная модель не подтверждена `probe_stream_usage`.
- **Сознательно НЕ реализовано: `finally`-перехват `GeneratorExit`** (клиент
  закрыл вкладку посреди стрима). Оригинальный черновик предполагал обернуть
  весь `generate()` (~160 строк с уже существующим `try/except`) в
  дополнительный `try/finally` — это требует переотступа всего существующего
  блока на один уровень в live revenue-критичном SSE-хендлере. Риск случайно
  сломать синтаксис/логику существующего платного пути ради страховки
  metering-only спринта (Спринт 1 не трогает деньги) признан неоправданным.
  Вместо этого `record_usage` вызывается в двух уже существующих точках
  выхода (успех — после `assistant_message.save()` до `yield done`; провал —
  в `except`, после возврата денег). Практическое следствие: при обрыве
  соединения ДО достижения одной из этих двух точек не будет ни строки
  `MessageTokenUsage`, ни исправления зависшего `PENDING`-сообщения — тот же
  предсуществующий пробел, что был и до Спринта 1, просто не расширенный на
  metering. Это нужно закрыть по-настоящему в **Спринте 3** (там `finally`
  вокруг settle обязателен по другой причине — риск не откатить/не подтвердить
  реальные деньги при обрыве, а не только пропустить строку аналитики — тогда
  переотступ оправдан и его стоит делать вместе с этим risk-акцептом, не раньше).
- Django admin (read-only) — `MessageTokenUsageAdmin`.
- Тесты: `aitext/test_token_metering.py` (5/5) + регрессия `telegram_bot/test_billing.py` (4/4).

---

## Спринт 2 — Таблица ставок, расчёт стоимости, dry-run

**Цель:** узнать точно, сколько сообщений и на какую сумму получили бы доплату,
**не списав ничего**. Это самый ценный этап де-рискинга — не сливать его в Спринт 3.

### Задачи

1. **`src/core/model_pricing.py`** — новый модуль, по образцу `core/model_limits.py:15-39`.
   **Поправка при ревью: ключи должны совпадать с реальным `model_name` в БД —
   он использует дефисы, не точки** (`claude-opus-4-8`, не `claude-opus-4.8`;
   проверено запросом к БД в этой же сессии). С точкой префиксный матч не
   находит модель вообще, и Спринт 2 молча не метрирует Opus 4.8. Дополнительно:
   `wholesale_rates` матчит по вхождению подстроки, а не по точному имени — при
   появлении варианта вроде `claude-opus-5-thinking` префикс `claude-opus-5`
   совпадёт с ним тоже и подставит неверные ставки (ровно так завёлся баг
   `$60/$60` у gpt-5.3-варианта, который разбирали в этом же аудите). Функция
   обязана возвращать **ставки самого длинного совпавшего префикса**, а не
   первого попавшегося в порядке словаря:
   ```python
   # (input_usd_per_1m, output_usd_per_1m)
   MODEL_WHOLESALE = {
       'claude-fable-5':  (10.0,  50.0),
       'claude-opus-4-8': ( 5.0,  25.0),
       'claude-opus-5':   ( 5.0,  25.0),
       'gpt-5-pro':       (15.0, 120.0),
       'gpt-5.4-pro':     (30.0, 180.0),
       'gpt-5.3':         (60.0,  60.0),
       'gpt-5.6-terra':   ( 2.0,  12.0),
   }

   def wholesale_rates(model_name):
       """None — модель не аудирована, overage невозможен.
       Возвращает ставки самого длинного совпавшего префикса (longest-prefix-wins),
       иначе будущий вариант модели (например claude-opus-5-thinking) молча
       унаследует ставки claude-opus-5, что может быть неверно.
       """
       m = (model_name or '').lower()
       matches = [(prefix, rates) for prefix, rates in MODEL_WHOLESALE.items() if prefix in m]
       if not matches:
           return None
       return max(matches, key=lambda pr: len(pr[0]))[1]

   def cost_kopecks(model_name, prompt_tokens, completion_tokens): ...
   def worst_case_cost_kopecks(model_name, prompt_tokens): ...  # использует model_limits.model_max_tokens_cap
   ```
   Юнит-тесты `src/core/test_model_pricing.py` — обязательно закрепить реальный
   инцидент как регрессионный тест: Opus 5, 1850/10428 → 2160 коп. ± 1. Плюс
   тест на longest-prefix-wins: `wholesale_rates('claude-opus-5-thinking')` не
   должен молча вернуть ставки `claude-opus-5`, если такого ключа нет explicitly
   — тест должен падать до тех пор, пока это не решено осознанно.

2. **`src/aitext/token_metering.py`: `compute_overage(usage_row) -> int`** —
   формула §2.3. Порог, cap, allowlist. Возвращает 0, если
   `wholesale_rates()` вернул `None`, если `source != 'provider'`, если модель
   не в `TOKEN_OVERAGE_MODELS`, **или если `usage_row.flat_was_charged` is
   `False`** (см. поправку в §2.3.1 — это первая проверка в функции, до всей
   остальной формулы, иначе безлимитный/бесплатный путь при `flat=0` уезжает в
   overage через cap вместо честного нуля).

3. Вызывать `compute_overage` сразу после `record_usage`, писать результат в
   `cost_kopecks` / `overage_kopecks`. При `TOKEN_OVERAGE_DRY_RUN=1`
   `settled_kopecks` остаётся `0`.

4. **Management-команда `src/aitext/management/commands/overage_report.py`** —
   за период печатает по каждой модели: всего сообщений, сколько получили бы
   overage, %, суммарная доплата, средняя доплата, макс. доплата, суммарная
   себестоимость vs суммарная выручка, итоговая маржа. Это артефакт, по которому
   основатель принимает решение включать или нет.

5. **Калибровка** `MARKUP` / `MIN_FRACTION` / `CAP_MULTIPLE` по фактическому
   распределению. Целевой ориентир: доля сообщений с ненулевым overage
   **не более 2-5 %** на аудированных моделях. Если получилось больше — плоская
   цена занижена и правильный ответ — поднять `cost_kopecks`, а не облагать
   доплатой каждое второе сообщение.

6. Отдельно проанализировать Fable 5 (§2.4) — решить по данным: снижать потолок
   `max_tokens` или вводить per-model `cap_multiple`.

7. **Выполнить проверку `deduct_stars = False` из §2.3.1** (SQL-запрос по
   безлимитным и бесплатным моделям) и зафиксировать результат письменно в этом
   документе. Это предусловие Спринта 3 — без него дыра «flat = 0 → overage = 0»
   остаётся необнаруженной.

### Готово, когда
Отчёт за 7+ дней реального трафика на руках; параметры откалиброваны; расчётный
overage на реальной транзакции Opus 5 (10428 out) сходится с ручным расчётом
21,60 ₽ себестоимости; ноль записей в `BalanceTransaction` с `type='overage'`.

### Что может пойти не так / что тестировать
- Оптовые цены у реселлера меняются без уведомления → добавить в
  `overage_report` предупреждение при отклонении расчётной себестоимости от
  факта из кабинета провайдера; поставить квартальную сверку в календарь.
- Курс USD/RUB уплыл → `TOKEN_OVERAGE_USD_RUB` меняется без редеплоя кода.
- Порог настроен слишком агрессивно → видно в отчёте до того, как кто-то заплатит.

### Реализовано (2026-08-05) — код-комплит, тесты зелёные, калибровка ЗАБЛОКИРОВАНА

- `src/core/model_pricing.py` — `MODEL_WHOLESALE` (7 моделей), `wholesale_rates()`
  (longest-prefix-wins), `cost_kopecks()` (округление до int здесь же — важно
  для сходимости с рабочим примером, см. ниже), `worst_case_cost_kopecks()`.
- `src/aitext/token_metering.py`: `compute_overage(usage_row) -> (cost, overage)`
  — первый guard `flat_was_charged` (§2.3.1), затем `source`, затем allowlist
  `TOKEN_OVERAGE_MODELS`. `apply_overage(usage_row)` — считает и сохраняет
  `cost_kopecks`/`overage_kopecks` на уже записанную строку, `settled_kopecks`
  не трогает (Спринт 3). Вызывается сразу после `record_usage` на всех путях
  (Celery, веб-SSE успех/провал).
- `overage_report` (management-команда) — по модели: сообщений, % с overage,
  Σ/среднюю/макс. доплату, Σ себестоимость vs Σ выручка, маржу, за период.
- Настройки: `TOKEN_OVERAGE_ENABLED`/`_DRY_RUN`/`_USD_RUB`/`_MARKUP`/
  `_MIN_FRACTION`/`_MIN_KOPECKS`/`_CAP_MULTIPLE`/`_ABS_CAP_KOPECKS`/`_MODELS`
  в `settings.py` — все с дефолтами из §2.4, `TOKEN_OVERAGE_ENABLED=0`.
- При реализации найдена и исправлена арифметическая нестыковка в
  иллюстративной таблице §2.4 (см. поправку там) — формула в коде (§2.3)
  была верна с самого начала, разошлась только ручная прикидка в тексте.
- Тесты: `core/test_model_pricing.py` (8/8) + `aitext/test_token_metering.py::ComputeOverageTests`
  (8/8, включая точное совпадение с «реальным инцидентом» — 21,60 ₽ → 34,56 ₽
  → 12,56 ₽) + регрессия Sprint 0/1.
- **Задачи 5-7 (калибровка параметров, решение по Fable 5, SQL-проверка
  `deduct_stars=False` на реальных данных) — БЛОКИРОВАНЫ:** требуют 7+ дней
  реального трафика с `TOKEN_METERING_ENABLED=1` на проде, а Спринт 0/1/2 ещё
  не задеплоены (см. риск-акцепт в Спринте 0). Это не техническая
  недоделка — данных физически не существует до деплоя.

### Задеплоено на aineron.ru (2026-08-06)

Founder-решение получено явно (чат 2026-08-06): деплоить Спринты 0-2, работать
дальше по плану автономно. Выполнено:

- `git pull` на проде до `2d58dcd`, `bash deploy.sh` — миграция
  `aitext.0058_message_token_usage` применена, все 11 контейнеров живы, ошибок
  в логах web/celery после рестарта нет.
- Смоук-тест бот-биллинга на реальном пользователе намеренно пропущен —
  единственный зарегистрированный `TelegramUser` на проде оказался настоящим
  платящим клиентом (~14 989 ₽ баланс), не QA-аккаунтом; гонять по нему тестовые
  списания не стали. Верификация — по прошедшему локально тест-сьюту
  (`telegram_bot/test_billing.py` 4/4) + чистым логам; первое органическое
  взаимодействие будет первым живым подтверждением.
- `TOKEN_METERING_ENABLED=1` выставлен в `.env`, контейнеры (`web`,
  `celery_worker`, `celery_beat`, `daphne`) пересозданы через `docker-compose
  up -d` (`restart` НЕ подхватывает новые переменные `.env` — только полное
  пересоздание контейнера). Побочный эффект: `docker-compose up -d` также
  пересоздал `db`-контейнер (все сервисы шарят `env_file`, хэш конфигурации
  изменился) — том `postgres_data` не тронут, данные целы (проверено `SELECT
  count(*) FROM users_customuser` — 89, до и после).
- `probe_stream_usage` прогнан на проде. Результат:

  | Модель | Usage в стриме | Комментарий |
  |---|---|---|
  | `claude-fable-5` | OK (8/8) | |
  | `claude-opus-4-8` | OK (8/8) | |
  | `claude-opus-5` | OK (8/8) | |
  | `gpt-5-pro` | OK (7/134) | Ушёл через фолбэк apimart (laozhang: 404 "only supported in v1/responses") — в проде реальный трафик пойдёт тем же путём через `FallbackClient`, поэтому валидно добавлять в allowlist |
  | `gpt-5.4-pro` | НЕ ПРОВЕРЕНО | `400 Invalid 'max_output...'` — параметр самого probe-запроса (`max_tokens=8`) несовместим с моделью, это не факт об отсутствии usage. Требует отдельного probe-запроса с другим именем параметра |
  | `gpt-5.3` | НЕ ПРОВЕРЕНО | `503 model_not_found` — модель недоступна у обоих провайдеров в момент прогона (транзиентно?), не проверено по usage |
  | `gpt-5.6-terra` | НЕ ПРОВЕРЕНО | `400 Invalid 'max_completion...'` — та же причина, что у gpt-5.4-pro |

  `TOKEN_METERING_STREAM_USAGE_MODELS=claude-fable-5,claude-opus-4-8,claude-opus-5,gpt-5-pro`
  выставлен в `.env` — веб-SSE метрирование активно только для этих четырёх.
  Три непроверенные модели остаются вне SSE-метрирования (Celery-путь их всё
  равно метрирует, там usage гарантирован) до отдельного повторного прогона
  probe с корректным параметром под каждую модель.
- Деньги нигде не тронуты: `TOKEN_OVERAGE_ENABLED=0`, `TOKEN_OVERAGE_DRY_RUN=1`
  (дефолты) — расчёт overage в проде уже идёт (записывается в
  `MessageTokenUsage.cost_kopecks`/`overage_kopecks`), но не списывается.
- **Следующее:** копить 7+ дней трафика, затем `overage_report` за период →
  калибровка (задачи 5-7 этого спринта) → Спринт 3.

### Цена Fable 5 поднята 9 ₽ → 15 ₽ на aineron.ru (2026-08-06)

Прямое решение §2.4 «проблемы Fable 5» — не снижать потолок `max_tokens` и не
вводить per-model `cap_multiple`, а поднять саму розничную цену. `cost_kopecks`
обновлён напрямую в БД прод (900→1500), плюс исходник
`add_laozhang_models.py` (иначе ручной перезапуск команды откатил бы цену
обратно к устаревшим 650 коп.) — `add_laozhang_models` не входит в
`deploy.sh`, поэтому прямое изменение в БД безопасно и не требует полного
редеплоя.

Пересчёт §2.4 с новой ценой (себестоимость не изменилась, курс/наценка те же):
breakeven-точка сдвигается с ~1880 до **~3380 output-токенов** — типичный и
средне-длинный диапазон ответов теперь целиком укладывается в плоскую цену.
На потолке 16384 токена (себестоимость ~67 ₽) `ABS_CAP_KOPECKS=4000` (40 ₽)
по-прежнему доминирует над `flat×CAP_MULTIPLE` (1500×2=3000), поэтому крайний
хвост остаётся при том же принятом трейд-оффе «не пугать шок-счётом» ценой
убытка на редких экстремальных ответах — цена сама по себе эту часть не
чинит, только сдвигает точку, где overage вообще начинает начисляться.

### Спринт 3 задеплоен на aineron.ru (2026-08-06)

`git pull` до `a1ea06d`, `bash deploy.sh` — миграция `users.0014_balancetransaction_overage_type`
применена, все 11 контейнеров живы, ошибок в логах нет. Флаги после полного
`docker-compose down/up` подтверждены: `TOKEN_METERING_ENABLED=1`, allowlist
из 4 моделей на месте, `TOKEN_OVERAGE_ENABLED=0`, `TOKEN_OVERAGE_DRY_RUN=1`,
`TOKEN_OVERAGE_SETTLE_FROM` пуст — settle-код живёт в проде, но неактивен,
деньги не трогает. Копим трафик дальше к 7-дневной отметке.

### Задеплоено на aineron.net — паритет с aineron.ru (2026-08-06)

Founder-решение (чат 2026-08-06): тот же план применим к `.net` без изменений
— overage-механизм работает поверх `balance_kopecks` независимо от способа
пополнения (крипта на `.net` выставляет фиатный инвойс в RUB, см. CLAUDE.md),
`INTL_MODE` этот код нигде не ветвит (заложено дизайном ещё в §3, «Совместимость
инстансов»). Перед деплоем проверено: `.net` был на `62733f1` (та же точка,
что `.ru` до этой сессии), 4 пользователя всего/1 в Telegram — низкий риск;
все 7 аудированных моделей уже в каталоге `.net` с независимыми от `.ru`
розничными ценами (Fable 5 на `.net` НЕ поднимали — отдельный вопрос
ценообразования, вне этого плана); тот же баг Спринта 0 (`TEXT_BILLING_ENABLED`
не определена) подтверждён живым на `.net`-версии кода до деплоя.

Выполнено: `bash deploy_intl.sh` (git pull до `c0a3843`, build, migrate) — обе
миграции (`aitext.0058`, `users.0014`) применены, все 7 контейнеров
`docker-compose.intl.yml` живы, `db` не пересоздавался (в отличие от `.ru`,
данные не потревожены вообще). `TOKEN_METERING_ENABLED=1` выставлен.
`probe_stream_usage` на `.net` подтвердил usage в стриме для 3 моделей
(`claude-fable-5`, `claude-opus-4-8`, `claude-opus-5` — `gpt-5-pro` в этом
прогоне упал на параметрах пробного запроса, отличие от прогона на `.ru`,
не факт об отсутствии usage), allowlist выставлен по этим трём. Ошибок в
логах web/celery/daphne/frontend/nginx после обоих пересозданий нет.

Оба инстанса теперь на `c0a3843`, метрирование идёт на обоих, overage
остаётся в dry-run на обоих. Калибровка (задачи 5-7 Спринта 2) будет
опираться в основном на трафик `.ru` — на `.net` слишком мало живых
пользователей для статистически значимых данных, но метрирование включено
для паритета инстансов и на случай будущего роста аудитории.

### Пересмотр подхода к калибровке (2026-08-06) — контролируемое тестирование вместо ожидания органики

Изначальный план (ждать 7+ дней реального трафика) оказался нежизнеспособен:
проверка по `.ru` за 30 дней дала всего 7 сообщений суммарно по всем 7
аудированным моделям (4 модели — 0 сообщений). Трафик к тому же не органический
— идёт платная кампания Яндекс.Директ, ждать «естественного» паттерна
бессмысленно. Решение основателя (чат 2026-08-06): не ждать, а самим
протестировать каждую модель контролируемым набором запросов, чтобы задать
правильную плоскую цену — по образцу того, как уже поднята цена Fable 5.

**Что можно не тестировать вызовами (уже есть точно, из формулы):**
себестоимость в худшем случае (`worst_case_cost_kopecks`, на потолке
`max_tokens`) — чистая арифметика по `core/model_pricing.py`, подтверждена
реальным инцидентом Opus 5. Не нужно провоцировать модель отвечать максимально
длинно, чтобы узнать эту цифру — она уже известна для каждой модели без единого
вызова.

**Что нужно измерить вызовом — нельзя вычислить:** сколько токенов модель
ФАКТИЧЕСКИ генерирует на реалистичный запрос данного типа — это поведенческая
характеристика (многословность), не арифметика.

**План: 3 контролируемых запроса на каждую из 7 моделей** (21 вызов), через
QA-аккаунт (`admin@example.com`, `persistent-qa-key`, см. память
`reference_qa_credentials`), через `POST /v1/chats/` — тот же Celery-путь
(`generate_ai_response` → `record_usage`/`apply_overage`/`settle_overage`
dry-run), что и у реальных пользователей, а не через dev-API
(`/v1/chat/completions`), который на другом, неинструментированном пути
(`api/services/billing.py`, сознательно не используется этим планом, см. §1.4).

| Тип | Пример промта | Что показывает |
|---|---|---|
| Короткий | «Сколько будет 137×289? Только число.» | Минимальная себестоимость — почти всегда в рамках плоской цены |
| Средний | «Объясни, как работает TCP handshake» | Типичный кейс — то, под что рассчитана плоская цена |
| Длинный/детальный | «Напиши статью 1500+ слов о влиянии AI на рынок труда РФ до 2030, с разделами и статистикой» | Тот же класс запроса, что вызвал реальный инцидент Opus 5 |

После прогона — читаем `MessageTokenUsage` по этим 21 сообщению
(`prompt_tokens`/`completion_tokens`/`cost_kopecks`/`overage_kopecks`),
сравниваем с текущей плоской ценой по каждой модели, предлагаем корректировки
там, где «средний» кейс уже вплотную подходит к плоской цене без запаса.

### Результаты прогона (2026-08-06)

21 вызов через QA-аккаунт, 6 из 7 моделей отработали (`gpt-5.3` недоступна у
провайдера — `model_not_found`, 503, подтверждено повторно уже после пополнения
баланса laozhang, это не про деньги, отдельная операционная проблема).

| Модель | Флаг цена | Короткий | Средний | Длинный (реалистичная статья) |
|---|---|---|---|---|
| claude-fable-5 | 15 ₽ | 0,18 ₽ | 2,90 ₽ (717 ток.) | не поймали чисто (баг парсинга, см. ниже), по счёту провайдера ~6000 ток. → ~24 ₽ — уже выше флага, overage корректно подхватит |
| claude-opus-4-8 | 20 ₽ | 0,02 ₽ | 1,79 ₽ | 9,14 ₽ (4549 ток.) — весь диапазон с запасом |
| claude-opus-5 | 22 ₽ | 0,13 ₽ | 2,13 ₽ | не поймали чисто, по формуле на ~8000 ток. ~16 ₽ — всё ещё в рамках флага |
| gpt-5-pro | 60 ₽ | 1,40 ₽ | — | не поймали; по формуле на потолке (16384 ток.) ~157 ₽ — сильно выше флага |
| gpt-5.4-pro | 55 ₽ | 0,62 ₽ | 12,54 ₽ (867 ток.) | не поймали; по формуле на ~13000 ток. ~187 ₽ — сильно выше флага |
| gpt-5.6-terra | 16 ₽ | 0,03 ₽ | 0,48 ₽ | 5,34 ₽ (5552 ток.) — весь диапазон с запасом |

**Вывод: кроме уже поднятой Fable 5, срочных изменений плоской цены не
требуется.** Типичный кейс (короткий/средний запрос) везде укладывается в цену
с большим запасом. `gpt-5-pro` и `gpt-5.4-pro` проваливаются на длинных
ответах в разы — но это ровно тот случай, под который спроектирован overage
(Спринт 3), а не повод поднимать базовую цену: поднимать её ради редкого
длинного ответа означало бы переплату большинством пользователей за типичные
короткие сообщения.

**Побочные находки, не про цены:**
- `gpt-5.3` недоступна у провайдера целиком — требует отдельного решения
  (деактивировать модель или разбираться с провайдером), вне этого плана.
- Оба провайдерских баланса (laozhang, apimart) были на нуле в момент теста —
  это и было первопричиной масштабного фолбэка/ретраев в прогоне, не разовый
  сбой конкретной модели. Пополнены пользователем по ходу сессии.
- Единицы в дашборде apimart — «кредиты» ($20 = 200 кредитов, курс $0.1/кредит),
  не доллары напрямую — при пересчёте с этим курсом apimart оказался **дешевле**
  laozhang (~×0.80 на тех же токенах на 4 моделях), а не в разы дороже, как
  показалось при первом (ошибочном) прочтении дашборда без пересчёта единиц.
- Найден и исправлен баг парсинга ответа при фолбэке (`'str' object has no
  attribute 'choices'`) — см. отдельную запись ниже.

### Исправлен баг: фолбэк не ловил «успешный», но нечитаемый ответ провайдера (2026-08-06)

Обнаружено при прогоне: часть длинных ответов (через фолбэк на apimart) падала
с `'str' object has no attribute 'choices'` в `aitext/tasks.py:1100`, каждый
раз запуская полный (платный) ретрай Celery-задачи с нуля — генерация
повторялась заново на том же проблемном провайдере, а не переключалась на
следующего в цепочке.

**Причина**: `FallbackClient._run()` (`aitext/providers.py`) считал вызов
успешным, если `client.chat.completions.create()` не бросил исключение. Но
openai-python при HTTP 200 с телом, которое не парсится как `ChatCompletion`
(например, апстрим вернул голую JSON-строку вместо объекта), не бросает
исключение — просто возвращает эти сырые данные как есть. Ошибка проявлялась
только в вызывающем коде (`completion.choices[0]`), уже вне зоны видимости
фолбэк-механизма — переключиться на следующего провайдера было некому.

**Фикс**: `_run()` теперь проверяет для `kind == 'chat'`, что результат имеет
атрибут `.choices`; если нет — поднимает `_MalformedResponseError` и обрабатывает
его наравне с ошибками доступности (тот же цикл переключения на следующего
провайдера в цепочке, что и для 5xx/429/таймаутов). Если «сломанный» ответ
пришёл от ВСЕХ провайдеров в цепочке — ошибка уходит наверх как раньше
(легитимный последний рубеж, ретрай на уровне Celery-задачи).

Файлы: `src/aitext/providers.py` (`_MalformedResponseError`, `_run`),
`src/aitext/test_providers.py` (+2 теста на сценарий, существующие тесты
переведены с голых строк на фейковый объект с `.choices` — иначе они сами
стали бы «сломанным ответом» по новой проверке). 15/15 тестов зелёные,
полная регрессия `aitext core telegram_bot` (171 тест) — 5 ошибок, все
предсуществующие (нужен Redis, не запущен локально), не связаны с правкой.

---

## Спринт 3 — Включение списания за флагом

**Цель:** реально списывать overage, идемпотентно и без возможности задвоить.

### 3.1. Где выполняется settle

| Путь | Точка settle | Гарантия выполнения |
|---|---|---|
| Celery (бот + веб-polling) | `src/aitext/tasks.py`, сразу после `message.save()` (`:1151`) | Задача всегда доходит до конца при успехе; при провале сообщение `FAILED` → overage не считается |
| Веб-SSE | Внутри `try`, после `assistant_message.save()` (`chats.py:661`), **до** `yield` события `done` (`:707`); **только** если `_usage` получен и `status == COMPLETED` | Usage-чанк приходит последним → на `:661` уже доступен. При обрыве `_usage is None` → overage = 0 по правилу §1.1(а). **Не в `finally`** — обоснование в §1.1.1 |
| Реконсилер | Новая Celery-задача, см. 3.4 | Подбирает всё, что упало между записью usage и settle |

### 3.2. Идемпотентность

```python
reference = f'overage:{message.id}'
```

- `unique(type, reference)` на `BalanceTransaction` (`users/models.py:1347-1353`)
  делает повторное списание физически невозможным.
- `MessageTokenUsage.message` — `OneToOneField`, вторая строка не создастся.
- **Ловушка**: `spend_kopecks` возвращает `True` и при дубликате
  (`users/models.py:680-683`). Поэтому перед неидемпотентными side-эффектами
  (`UserSpending.objects.create`, отправка receipt в SSE/бот) — явная проба по
  идиоме `studio/billing.py:106-116`:
  ```python
  already = BalanceTransaction.objects.filter(
      user=user, type=BalanceTransaction.Type.OVERAGE, reference=reference
  ).exists()
  ```
- Обновление `settled_kopecks` / `settled_at` — только внутри той же
  `transaction.atomic()`, что и списание.

### 3.3. Политика при нехватке баланса на момент settle

Списание происходит **после** генерации, баланс мог обнулиться. `spend_kopecks`
вернёт `False`. Три варианта:

| Вариант | Плюсы | Минусы |
|---|---|---|
| A. Списать сколько есть, остаток записать как долг, блокировать следующее сообщение | Деньги не теряются | Нужна модель долга, новый UX-путь, риск «залипшего» пользователя |
| B. Списать сколько есть, остаток простить, залогировать | Просто, без нового UX | Управляемая утечка |
| **C. Preflight-клэмп (рекомендуется)** | Ситуация нехватки почти не возникает | Требует расчёта worst-case до вызова |

**Рекомендуется C**, и это возможно именно потому, что потолок `max_tokens` уже
отгружен (`core/model_limits.py`) — худший случай вычислим до вызова:

```python
# в chats.py перед формированием kwargs и в tasks.py перед create()
worst = worst_case_cost_kopecks(model_name, prompt_tokens_estimate)
head  = user.balance_kopecks - flat_kopecks           # что осталось после базы
if worst_overage(worst, flat_kopecks) > head:
    max_tokens = min(max_tokens, affordable_max_tokens(model_name, head, flat_kopecks))
```

То есть при нехватке средств мы **не отказываем в запросе**, а сужаем ответ до
того, что пользователь может оплатить — с нижней границей (например 1024 токена),
ниже которой ответ бессмыслен и лучше показать «пополните баланс». `C` дополняется
`B` как страховкой: если settle всё же не прошёл (гонка с параллельным запросом),
остаток прощается и уходит в `notify_admins`.

Оценку `prompt_tokens_estimate` брать из уже собранного `messages_for_api` через
`studio.billing.count_tokens` / `aitext.memory.estimate_tokens` — точность здесь
не критична, это защитная граница, а не счёт.

### 3.4. Реконсилер

**Новая** Celery-задача `aitext.tasks.reconcile_unsettled_overage`, `*/15` мин.

**Не расширять `reconcile_stuck_spends`** (`tasks.py:2337-2424`): её семантика —
«списано без результата», и она явно пропускает `COMPLETED` (`:2407`). У overage
сообщение всегда `COMPLETED`, поэтому там она была бы no-op.

Логика: `MessageTokenUsage.objects.filter(overage_kopecks__gt=0, settled_at__isnull=True,
created_at__lt=now-20min, created_at__gte=now-6h)` → для каждой попытаться
досписать тем же `reference` (идемпотентно), при неудаче — накопить в алерт
`notify_admins`, по образцу `:2418-2424`, с антиспам-кэшем как на `:2411`.

### 3.5. Прочие задачи спринта

1. Добавить `OVERAGE = 'overage', 'Доплата за токены'` в `BalanceTransaction.Type`
   (`users/models.py:1302-1311`) + миграция `users/00XX_...` (последняя сейчас
   `0013_customuser_acquisition_utm.py`). Additive, instance-agnostic — безопасно
   приземляется на оба инстанса.
2. Писать `UserSpending` с отличимым описанием («Доплата за длинный ответ,
   {model}») — тогда строки автоматически появятся в `/account/analytics/`
   без изменений фронта.
3. **Определить взаимодействие с надбавкой за варианты** (`chats.py:649-657`,
   `reference=f'chat-variants:{id}'`, ×0.5). Решение: **overage считается только
   по основному вызову**; токены вариантов (`_gen_variant`, `:622-628`) в usage не
   входят, надбавка ×0.5 покрывает их отдельно. Зафиксировать это в комментарии
   кода, иначе следующий разработчик сложит их дважды. Попутно: спенд на `:653`
   стоит внутри `except Exception: pass` (`:658-659`) и не проверяет
   возвращаемое значение — отдельный существующий баг, чинить не в этом плане, но
   не копировать паттерн.
4. Метрика в логах: доля сообщений с overage, суммарная сумма за сутки.

### Готово, когда
`TOKEN_OVERAGE_DRY_RUN=0` на одной модели (рекомендуется начать с **Opus 5** —
самый дорогой хвост, самая понятная история); первые реальные списания
`type='overage'` в ledger; реконсилер не находит зависших; ручной тест «оборвать
соединение на середине» подтверждает overage = 0.

### Что может пойти не так / что тестировать
- **Двойное списание** — главный риск. Тест: вызвать settle дважды подряд с одним
  `message.id`, убедиться что `BalanceTransaction` одна и `UserSpending` одна.
- **Retry Celery** — `generate_ai_response` имеет `max_retries=3`; при ретрае
  после частичного успеха settle должен быть no-op. Тест: искусственно бросить
  исключение после settle.
- Гонка «два сообщения параллельно + низкий баланс» — settle одного проходит,
  второго нет. Покрывается 3.3.
- Отрицательный баланс невозможен по конструкции `spend_kopecks`
  (`WHERE balance_kopecks >= amount`, `users/models.py:664-668`) — проверить, что
  новый код нигде не мутирует баланс в обход этих методов.

### Реализовано (2026-08-06) — код-комплит, тесты зелёные, НЕ задеплоено

Деньги на проде не двигаются: `TOKEN_OVERAGE_ENABLED=0` и `TOKEN_OVERAGE_DRY_RUN=1`
(дефолты не менялись). Весь Спринт 3 приземляется как no-op до явного флага.

- `token_metering.settle_overage(usage_row) -> int` — единственная точка списания.
  Возвращает списанное **в этом вызове** (0 при любом no-op). Гейтинг: сначала
  `overage_kopecks > 0` и `settled_at is None`, затем `TOKEN_OVERAGE_ENABLED`,
  затем `TOKEN_OVERAGE_DRY_RUN` (считает и логирует, не списывает). Явная проба
  `BalanceTransaction.objects.filter(type=OVERAGE, reference=...).exists()` по
  идиоме `studio/billing.py:106-116` — до `UserSpending.objects.create`.
  `settled_kopecks`/`settled_at` обновляются condition-UPDATE'ом
  (`settled_at__isnull=True`) в той же `transaction.atomic()`, что и списание,
  причём **первым шагом транзакции — как блокировка**: сама `.exists()`-проба
  это check-then-act, и два одновременных settle (инлайн + реконсилер, когда
  его заведут в Beat) оба увидели бы `already=False`; второй получил бы от
  `spend_kopecks` `True` по проглоченному `IntegrityError` и создал бы вторую
  `UserSpending` при одной строке в ledger. Кто выиграл UPDATE — тот списывает;
  при нехватке средств `transaction.set_rollback(True)` снимает и отметку.
- `BalanceTransaction.Type.OVERAGE` + миграция
  `users/0014_balancetransaction_overage_type.py` (additive, instance-agnostic).
- Celery-путь (`tasks.py`) — `settle_overage` сразу после существующего
  `apply_overage`. Веб-SSE (`chats.py`) — там же, внутри `try`, после
  `assistant_message.save()` и **строго до `yield done`** (§1.1.1), под условием
  `_usage is not None` (§1.1(а)).
- **Отложенный из Спринта 1 `try/finally` сделан без переотступа 160 строк:**
  вместо вложенного `try` вокруг всего тела `generate()` к УЖЕ существующему
  `try/except` добавлена ветка `finally`, а внутрь `try` подняты только два
  первых `yield` (`init`, `search_done`) — 12 строк вместо 160. Риск, из-за
  которого Спринт 1 это отложил, тем самым снят, а не принят. В `finally`
  только DB-запись (никаких `yield` и никакого `return` — `return` при
  `GeneratorExit` даёт `RuntimeError: generator ignored GeneratorExit` и рвёт
  SSE-ответ на платном пути): при обрыве пишется `MessageTokenUsage` с
  `source=MISSING` (если строки ещё нет) и зависший `PENDING` переводится в
  `FAILED`. Локальный флаг `_finalized` ставится **до** `yield done` / `yield
  error` — после последнего `yield` на обрыве код не выполняется вовсе, — и
  делает `finally` дешёвым no-op на штатных путях.
- Preflight-клэмп (§3.3, вариант C) — `token_metering.preflight_max_tokens()` +
  `estimate_prompt_tokens()`, применён в обоих местах расчёта `max_tokens`
  (`chats.py` перед генератором, `tasks.py` перед `create()`). Пол —
  **1024 токена** (`PREFLIGHT_MIN_MAX_TOKENS`), отказа в запросе нет: ниже пола
  не опускаемся и всё равно генерируем, остаточный риск нехватки закрывает
  реконсилер. Клэмп — единственная user-visible часть спринта (короче ответ),
  поэтому он **полный no-op при `DRY_RUN=1`/`ENABLED=0`**, а не «считаем всегда»:
  иначе на текущем состоянии флагов пользователи с низким балансом получили бы
  обрезанные ответы, не получив взамен никакой доплаты. Закреплено тестами.
- Реконсилер `aitext.tasks.reconcile_unsettled_overage` (§3.4) — новая задача,
  `reconcile_stuck_spends` не тронута. **В Celery Beat НЕ заведён** — оставлено
  follow-up'ом вместе с включением доплаты.
- §3.5(3): комментарий у надбавки за варианты (`chats.py`, `chat-variants:`) —
  overage считается только по основному вызову, токены вариантов в usage не
  входят, надбавку ×0.5 с ними складывать нельзя. Предсуществующий баг там
  (спенд под `except: pass` без проверки возврата) намеренно не тронут.
- Тесты: `aitext/test_token_metering.py` 33/33 (было 13) — двойной settle,
  «ledger есть, строка не отмечена» (падение между списанием и UPDATE),
  нехватка баланса, `source=MISSING`, dry-run, клэмп (срабатывает / не трогает
  при здоровом балансе / no-op под dry-run и при выключенном флаге / пол 1024 /
  неаудированная модель / бесплатный путь), реконсилер (окно, отсечка, уже
  списанное, dry-run). Плюс **новый `api/test_stream_settle.py` (3/3)** —
  единственные тесты, прогоняющие перестроенный генератор `StreamMessageView`
  целиком через `APIClient` с подменённым провайдером: штатное завершение
  (доплата списана до `done`), **обрыв клиента через `response.close()`**
  (`GeneratorExit` → `finally`: `PENDING`→`FAILED`, строка `source=MISSING`,
  доплата 0) и ошибка провайдера (возврат плоской цены, доплаты нет). Без них
  риск переотступа/перестройки генератора был бы проверен только `ast.parse`.
  Итого по Спринтам 0-3: 49/49. Локально требуется `SECRET_KEY` в окружении —
  без него messages-middleware роняет ЛЮБОЙ view-тест проекта (предсуществующее).

#### Расхождения с §3 (осознанные)

1. **Нехватка баланса на settle: all-or-nothing вместо «списать сколько есть»**
   (§3.3, вариант B как страховка к C). Частичное списание сожгло бы
   `unique(type, reference)` — досписать остаток тем же reference потом уже
   невозможно, понадобился бы второй ключ и модель долга (это вариант A,
   явно отклонённый). Поэтому: не списываем ничего, `settled_at` остаётся
   пустым, строку ретраит реконсилер, после окна 6 ч остаток прощается и
   уходит в `notify_admins` — ровно тот исход, что §3.3 и предписывает, но
   с одной дополнительной попыткой собрать деньги целиком.
2. **Новая настройка `TOKEN_OVERAGE_SETTLE_FROM`** (в §3 не предусмотрена,
   дефолт пусто = реконсилер не делает ничего). Без неё в момент выключения
   `TOKEN_OVERAGE_DRY_RUN` реконсилер поймал бы в своё окно 20 мин–6 ч строки
   dry-run-периода (`overage_kopecks > 0`, `settled_at IS NULL`) и **списал бы
   деньги задним числом** за сообщения, по которым пользователю ничего не
   показывали. Реконсилер — ретрай пропущенного инлайн-settle, не бэкфилл.
   **Операционное правило:** `TOKEN_OVERAGE_DRY_RUN=0` и
   `TOKEN_OVERAGE_SETTLE_FROM=<текущее время>` выставляются одной правкой
   `.env`; тот, кто будет заводить реконсилер в Beat, обязан это учесть.
3. `TOKEN_OVERAGE_ENABLED` до этого спринта не гейтил ничего (Спринт 2 считал
   overage независимо от него) — семантика сохранена: флаг гейтит **settle и
   клэмп**, расчёт для dry-run-отчёта продолжает идти при любом его значении.
4. Клэмп считает худший случай через `model_pricing.cost_kopecks(model, prompt,
   max_tokens)`, а НЕ через `worst_case_cost_kopecks()` (§3.3 подразумевал её):
   вторая берёт потолок семейства из `model_limits`, а к моменту клэмпа
   `max_tokens` уже сужен значением из БД — считать надо по фактически
   запрашиваемому потолку, иначе клэмп срабатывает раньше, чем нужно.
   `worst_case_cost_kopecks()` остаётся без вызывающих (только тесты) — она
   писалась в Спринте 2 под отчёт, который её в итоге не использует.

---

## Спринт 4 — Прозрачность для пользователя и раскатка

**Цель:** пользователь видит, за что доплатил, а не молча обнаруженное списание.

Текущее состояние фронта проверено: **в чате нет ни одного отображения токенов
или стоимости**. Есть только плумбинг баланса — `new_balance_kopecks` приходит в
SSE-событии `init` и уходит в Zustand: `frontend/app/[locale]/chat/[chatId]/page.tsx:380-382`
→ `useAuthStore.setBalance`. Значит новых экранов не нужно, только расширение
существующих поверхностей.

### Задачи

1. **Backend, SSE.** Расширить событие `done` (`chats.py:707-715`). Settle
   выполняется на `:661`, то есть **до** этого `yield` (§1.1.1), поэтому суммы
   уже финальные. Брать **`usage_row.settled_kopecks`** (фактически списанное),
   а не расчётную переменную `overage` — при частичном/непрошедшем списании они
   расходятся:
   ```python
   **({"billing": {
        "flat_kopecks": flat_kopecks,
        "overage_kopecks": usage_row.settled_kopecks,
        "prompt_tokens": pt, "completion_tokens": ct,
        "new_balance_kopecks": user.balance_kopecks,
      }} if usage_row.settled_kopecks > 0 else {}),
   ```
   Ключ добавляется **только при ненулевой доплате** — обычные сообщения идут
   байт-в-байт как сейчас.

2. **Frontend, типы.** Добавить `billing?` в union `SSEEvent` варианта `done`
   (`frontend/lib/api/client.ts:316`) и в сигнатуру `onDone` (`:335`).

3. **Frontend, UI.** В `onDone` (`page.tsx`, рядом с существующим `setBalance`
   на `:382`): при наличии `billing` — вызвать `setBalance(billing.new_balance_kopecks)`
   и отрисовать под пузырём ответа компактную строку-чек:
   `Длинный ответ · 10 428 токенов · доплата 12,56 ₽`.
   Требования CLAUDE.md: только Lucide-иконка (`Receipt` или `Info`, `size={16}`),
   **ноль эмодзи**, строки через `t()` (путь `[locale]/`, next-intl), а не
   хардкод русского. Ключи локали добавить во все языки инстанса `.net`
   (en/fa/tr/id/ar) — иначе на intl-инстансе будет пустая строка.

4. **Telegram-бот** (только если Спринт 0 выбрал вариант A): в
   `telegram_bot/handlers/chat.py` при финализации ответа (`:245`) добавить
   строку-чек через существующий `DIVIDER`/`card()` из `telegram_bot/utils.py`.
   Без эмодзи — по конвенции редизайна бота.

5. **Документация для пользователя.** Абзац в `TARIFFS.md` и на странице тарифов:
   «плоская цена включает ответ до N токенов; сверх — доплата по себестоимости
   с фиксированной наценкой». Без этого overage выглядит как скрытая комиссия и
   ломает ровно тот дифференциатор, ради которого делалась плоская цена.

6. **Раскатка по моделям**, по одной, с интервалом 2-3 дня, в порядке
   убывания риска: `claude-opus-5` → `claude-opus-4-8` → `gpt-5-pro` →
   `claude-fable-5` → `gpt-5.3`. `gpt-5.4-pro` и `gpt-5.6-terra` — здоровые,
   держать в dry-run как контрольную группу.
   **Осознанная оговорка (не упущение):** Opus 5 в очереди первым ради
   наглядности инцидента, который и запустил эту работу, но именно
   `claude-fable-5` — модель с самым узким запасом (порог безубыточности
   ~1880 токенов, §2 и TARIFFS.md item 11) и уже отмечена как «lossy у потолка
   даже после cap». Она остаётся полностью не защищена от длинных ответов
   до своей очереди в этом списке — если до неё далеко, стоит рассмотреть
   внеочередной перенос выше `gpt-5-pro`.

7. **Деплой обоих инстансов близко по времени** (CLAUDE.md, правило 4). Миграции
   `MessageTokenUsage` и `BalanceTransaction.Type.OVERAGE` — additive, но
   `django_migrations` общий по схеме, расхождение недопустимо.

### Готово, когда
Пользователь после overage-сообщения видит чек; тикеты «почему списалось больше»
не растут; отчёт `overage_report` показывает положительную маржу на всех
аудированных моделях.

### Что может пойти не так / что тестировать
- Чек показан, но settle не прошёл (нехватка баланса) → UI обязан показывать
  **фактически списанное**, а не расчётное. Брать значения из `settled_kopecks`
  (учтено в задаче 1).
- Отток пользователей на дорогих моделях. Метрика для отслеживания: недельное
  число сообщений на `claude-opus-*` до и после.
- Обрыв соединения — два подслучая, см. §1.1:
  **(а)** обрыв до конца стрима → usage не получен → overage не списан, чека нет.
  Консистентно.
  **(б)** обрыв после последнего чанка, но до чтения `done` → overage **списан**,
  а чек до клиента не дошёл. Это реальный сценарий, а не теоретический.
  Компенсирующая поверхность — строка `UserSpending` в `/account/analytics/`
  (Спринт 3, задача 2). Проверить вручную: убить соединение сразу после
  последнего токена и убедиться, что трата видна в аналитике с понятным описанием.

### Реализовано (2026-08-06) — задачи 1-5, код-комплит, тесты зелёные, НЕ задеплоено

Задачи 6 (раскатка по моделям) и 7 (деплой) — операционные, кодом не
закрываются; флаги не тронуты, `TOKEN_OVERAGE_ENABLED=0`/`DRY_RUN=1` остаются
как были, поэтому ключ `billing` в проде сейчас не появится ни разу.

- **SSE (`api/views/chats.py`).** Ключ `billing` в событии `done`, только при
  `settled_kopecks > 0`. Собирается НЕ выражением над `_usage_row` прямо в
  payload, как в сниппете задачи 1, а в отдельную переменную `_billing`,
  объявленную рядом с `_usage`: `_usage_row` живёт внутри вложенного `try`, при
  `TOKEN_METERING_ENABLED=0` равен `None` (`record_usage` так и возвращает), а
  при исключении в `record_usage` вообще не связан — обращение к нему из payload
  уронило бы штатный платный путь в `except` с возвратом плоской цены. Результат
  на выходе байт-в-байт тот же.
- **`flat_kopecks` в этом view локальной переменной НЕ существует** (сниппет
  задачи 1 её подразумевал): плоская цена там — выражение
  `cost_kopecks if deduct_stars else 0`. Берём `_usage_row.flat_kopecks` — то же
  значение, но уже сохранённое и потому честное.
- `new_balance_kopecks` (`:410`) посчитан ДО генерации, а `settle_overage`
  списывает со своего instance (`usage_row.message.chat.user`) — перед сборкой
  чека делается `user.refresh_from_db(fields=['balance_kopecks'])`.
- **Фронт.** `OverageBilling` в `lib/api/client.ts` (вариант `done` + сигнатура
  `onDone`), клиентское поле `WebMessage.overage_billing` в `lib/api/types.ts`,
  строка-чек под пузырём ответа в `[locale]/chat/[chatId]/page.tsx` — рядом с
  индикатором `used_memory` и по его же визуальному образцу (Lucide `Receipt`
  `size={16}`, без эмодзи). `setBalance(billing.new_balance_kopecks)` в `onDone`
  добавлен: раньше его там не было вовсе (баланс обновлялся только в `onInit`).
  Сумма форматируется `lib/money.ts::formatMoney` (не `formatRub`) — на .net это
  кредиты; число токенов уходит в ICU числом (`{tokens, number}`).
- **Персистентность чека сознательно не делалась.** Поле приходит только в
  SSE-событии живой сессии, сериализатор списка сообщений его не отдаёт — после
  перезагрузки чата чек не восстанавливается. Это тот же исход, что и §1.1(б)
  (обрыв соединения), и компенсируется той же поверхностью — строкой траты в
  `/account/analytics/`. Расширять `ChatDetailView` ради этого не стали.
- **Локали.** `chat.overageReceipt` во все 6 файлов `frontend/messages/*.json`
  (ICU) и во все 6 `telegram_bot/locales/*.json` (`str.format`, у бота свой
  формат плейсхолдеров — не смешивать).
- **Бот (`telegram_bot/handlers/chat.py`).** Чек дописывается в `full_text`
  ПЕРЕД доставкой, тем же способом, что и блок источников KB выше, — а НЕ через
  `card()`: `card()` отдаёт готовый HTML (`<b>`), а `full_text` уходит либо в
  `telegram_format()`, либо в `send_rich_or_markdown()`, и сырой HTML на
  rich-пути даёт мангленную разметку. `DIVIDER` (просто «─»×21) переиспользован.
  Данные тянет новый `get_overage_receipt` (`sync_to_async`, фильтр
  `settled_kopecks__gt=0`), любая ошибка — только лог, доставка ответа не
  блокируется. Запрос гейтится `overage_settle_active()` — пока доплата
  выключена/в dry-run, строк с `settled_kopecks > 0` не бывает в принципе, и
  лишний запрос на каждый ответ бота не делается (тот же приём, что у
  preflight-клэмпа в Спринте 3).
  **Известная гонка, принята осознанно:** `tasks.py` сохраняет `COMPLETED` ДО
  `settle_overage`, поллер бота просыпается раз в 2 с — если он успеет между
  этими двумя точками, строки ещё нет и чек не покажется. Деньги при этом
  списаны корректно и видны в аналитике; цена промаха — отсутствие
  информационной строки, поэтому ретраев/ожидания здесь нет.
- **Тесты:** `api/test_stream_settle.py` 3 → 6. Новые: чек в `done` совпадает с
  `settled_kopecks`; **под `TOKEN_OVERAGE_DRY_RUN=1`** (текущая прод-конфигурация,
  `overage_kopecks > 0` при `settled_kopecks == 0`) в теле SSE нет подстроки
  `"billing"` вовсе; при `TOKEN_METERING_ENABLED=0` (`_usage_row is None`) событие
  `done` не ломается и деньги не возвращаются. Итого по Спринтам 0-4: 52/52.

---

### Спринт 4 задеплоен на оба инстанса (2026-08-06)

`git pull` до `933ce85`, полный `deploy.sh`/`deploy_intl.sh` на `.ru` и
`.net` (фронтенд требует пересборки образа — bind mount тут не спасает, в
отличие от чисто-Python правок ранее в этой сессии). Оба чисто: миграций не
было, все контейнеры живы, ошибок в логах web/celery/daphne/frontend нет,
`db` на `.net` не пересоздавался (данные не тронуты), оба сайта отвечают
200. Чек по доплате в проде сейчас невидим ни для одного пользователя —
`billing`-ключ появляется только при `settled_kopecks > 0`, а settle
неактивен (`TOKEN_OVERAGE_ENABLED=0`), так что это чисто латентный код,
ничего не меняет до отдельного включения флага.

---

## 5. Сводная матрица выключателей

| Ситуация | Действие | Время реакции |
|---|---|---|
| Overage на одной модели считается неверно | Убрать модель из `TOKEN_OVERAGE_MODELS` | Рестарт web+celery |
| Массовые жалобы, причина неясна | `TOKEN_OVERAGE_DRY_RUN=1` — считаем, не списываем | Рестарт |
| Подозрение на двойное списание | `TOKEN_OVERAGE_ENABLED=0` | Рестарт |
| `stream_options` ломает генерацию | `TOKEN_METERING_ENABLED=0` — полный откат | Рестарт |
| Нужно вернуть деньги задним числом | `add_kopecks(type='refund', reference=f'overage:{msg_id}')` — идемпотентно, безопасно к повтору | Скрипт |

Откат кода не требуется ни в одном сценарии: всё поведение за флагами, дефолты
безопасны, миграции additive.

---

## 6. Что этот план сознательно НЕ делает

- Не трогает `src/api/services/billing.py` и dev-API — там своя (сломанная)
  токенная схема, её починка — отдельная задача.
- Не бэкфиллит `NeuralNetwork.kopecks_per_1k_tokens` — поле остаётся
  неиспользуемым, ставки живут в `core/model_pricing.py`.
- Не аудирует остальные ~120 моделей — они не попадают в таблицу и продолжают
  работать по чистой плоской цене без изменений.
- Не чинит смежные найденные баги (незакрытый апстрим-стрим при обрыве,
  невозвращаемое списание при обрыве, `chat-variants` спенд без проверки
  результата, зависшие `PENDING`-сообщения) — кроме тех, что попутно закрываются
  добавлением `try/finally` в Спринте 1. Их стоит завести отдельными задачами.
- Не решает вопрос ценообразования бота — это Спринт 0, решение основателя.

---

## Резюме для основателя

Плоская цена за сообщение ломается ровно на семи моделях, где провайдер берёт за
выходной токен в 5-8 раз больше, чем за входной: Opus 5 при 10 428 токенах ответа
обошёлся в 21,60 ₽ при цене 22 ₽ — нулевая маржа, и это не редкий выброс, а
предсказуемое следствие формулы. Предлагаемое решение — гибрид: плоская цена
остаётся включённым лимитом, а доплата начисляется **после** генерации и только
когда реальная себестоимость с наценкой ×1,6 превышает плоскую цену более чем на
четверть; по расчёту на реальных цифрах типичное сообщение (600 токенов ответа)
не затрагивается вообще, а доплату получают примерно 2-5 % сообщений на этих семи
моделях. Ставки живут в отдельном dict-модуле по образцу уже отгруженного
`core/model_limits.py`, поэтому остальные ~120 моделей не требуют ни аудита, ни
миграции и работают как раньше. Ключевое техническое ограничение выяснено по коду:
при обрыве соединения клиента генерация на сервере всё равно идёт до конца, но
данные о токенах теряются — поэтому в таком случае доплата просто не начисляется,
что убирает риск двойного или ошибочного списания. Работа разбита на пять
спринтов, из которых деньги затрагивает только третий, а второй — **обязательный
режим сухого прогона**, дающий точный ответ «сколько сообщений и на какую сумму
получили бы доплату» до того, как хоть один пользователь заплатит рубль. И
отдельно, до начала работ, требуется ваше решение по вопросу за рамками техники:
**текстовые сообщения в Telegram-боте сегодня не списывают деньги вообще** —
проверено по коду, флаг `TEXT_BILLING_ENABLED` в `.env` Django не читает, — и
пока это не закрыто, доплата в боте не имеет базы, к которой могла бы
добавляться.
