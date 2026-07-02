# Миграция биллинга: звёзды → рублёвый баланс в копейках

> **Статус: R1 (dual-write) реализован в коде.** Фазы 1-9 (money-утилиты, схема БД,
> backfill-миграция, атомарный баланс+ledger, точки списания, платежи Robokassa/XTR,
> API-алиасы, фронтенд, тесты) — code complete и покрыты тестами (`core`, `users`, `api`,
> частично `studio`). **На прод НЕ выкачено** — миграции не применялись к боевой БД,
> `deploy.sh` не запускался. См. раздел «Чек-лист выката R1» в конце файла перед деплоем.
> aineron.ru — топ-1 в России, конкурирует с европейскими сервисами.

## Context

Переход с внутренней валюты «звёзды» (`CustomUser.pages_count`) на профессиональный рублёвый биллинг. Подтверждённые решения владельца:

- **Курс миграции: 1 звезда = 1 ₽ = 100 копеек**
- **Дробные цены** за сообщение (например 0,50 ₽) — включаем
- **Рубли везде** — веб и Telegram-бот; Telegram Stars (XTR) остаётся только способом оплаты, начисляет рубли на единый баланс
- Robokassa остаётся платёжным провайдером на вебе

## Базовый инвариант

```
1 звезда = 1 ₽ = 100 копеек
```

| Что | Было | Стало |
|---|---|---|
| Баланс | `pages_count` (int звёзды) | `balance_kopecks` (BigInteger) |
| Цена сообщения | `cost_per_message` | `cost_kopecks` (×100) |
| Токен-ставка | `stars_per_1k_tokens` | `kopecks_per_1k_tokens` (×100) |
| Studio | `STAR_RATE {1, 1.7, 3}` | `KOPECK_RATE {100, 170, 300}` |
| Тариф | `tariff.pages_count` | `tariff.balance_grant_kopecks` |

**НЕ трогаем:** `CustomUser.rub_balance` (выводимый реферальный баланс, Decimal ₽) и `Organization.balance_rub` (уже рубли).

## Принятые дефолты (флагируем владельцу при выкате, менять легко)

1. **`MIN_CHARGE_KOPECKS = 10`** (0,10 ₽) — минимальное списание, env-настройка; округление списаний — ceil. Защита от 100× удешевления мелких запросов (сейчас floor = 1 звезда).
2. **Орг-биллинг унифицируется к 1 ₽/звезда** — устраняется расхождение `STAR_TO_RUB=0.10` (`telegram_bot/handlers/group.py:37`) vs `ORG_RUB_PER_STAR=1.0` (`api/services/billing.py`). Для организаций, шедших по 0.10 — подорожание 10×; предупредить владельца.
3. **XTR-пакеты — relabel:** «100 звёзд за 50 XTR» → «100 ₽ за 50 XTR», формула custom `xtr = max(1, rubles // 2)` не меняется численно.
4. **Ledger включаем:** новая модель `BalanceTransaction` (signed amount_kopecks, balance_after, type, reference, unique(type, reference)) — запись при каждом spend/refund/credit. Реконсиляция «баланс = SUM(ledger)» — отложена, источник истины `balance_kopecks`.

## Стратегия выката: dual-write, два релиза

- **R1**: новые поля + backfill ×100 + весь код пишет и `balance_kopecks`, и `pages_count` (синхронно). Чтение — с копеек. API отдаёт старые поля как алиасы + новые поля. Безопасный откат.
- **R2** (через 1–3 дня наблюдения): удаление dual-write, `pages_count`, старых `stars_*` полей.
- Backup БД перед миграцией обязателен. Без рантайм-фичефлага на деньгах (избыточно и рискованно).

## Фазы реализации

### Фаза 1 — Money-утилиты
- **`src/core/money.py`** (новый): `KOPECKS_PER_RUB=100`, `rub_to_kopecks()`, `kopecks_to_rub()`, `format_rub(kopecks)` → «125 ₽» / «1,50 ₽» (никогда «125,00 ₽», разделитель — запятая). `MIN_CHARGE_KOPECKS` из env.
- **`frontend/lib/utils/money.ts`** (новый): `formatRub(kopecks)` с теми же правилами.

### Фаза 2 — Схема БД (новые поля, ещё не читаем)
`src/users/models.py`:
- `CustomUser.balance_kopecks = BigIntegerField(default=0)` (BigInteger обязателен — ×100 приближает к потолку int32)
- `Tariff.balance_grant_kopecks`, `Tariff.referral_bonus_kopecks`
- `PaymentHistory.amount_kopecks` (nullable — только новые записи, историю НЕ конвертируем: аудит)
- Новая модель `BalanceTransaction` (см. дефолт №4)
- `PromoCode.kopecks`

`src/aitext/models.py`: `NeuralNetwork.cost_kopecks`, `kopecks_per_1k_tokens`; `UsageEvent.cost` → BigInteger.
`src/studio/models.py`: `stars_reserved_kopecks`, `stars_spent_kopecks`, `max_kopecks_budget` (новые поля, не реинтерпретация).
`src/api/models.py`: `TokenUsage.cost_kopecks`; `users` `UserSpending.amount` → BigInteger.

### Фаза 3 — Data-миграция (RunPython, обратимая, идемпотентная)
- **Категория А (балансы/справочники)**: `update(balance_kopecks=F('pages_count')*100)` — users, tariffs, networks, studio projects, promo.
- **Категория Б (аналитика)**: `UsageEvent.cost`, `TokenUsage.stars_charged`, `UserSpending.amount` — ×100 ВСЕ строки (иначе обрыв ×100 на графиках).
- **Категория В (финансы)**: `PaymentHistory` — историю не трогаем.
- reverse — зануляет новые поля.

### Фаза 4 — Атомарные методы баланса + ledger
`src/users/models.py` — новые методы по образцу атомарного `group.py:39-42`:
- `spend_kopecks(amount, type, reference)` — `filter(pk, balance_kopecks__gte=amount).update(F()-amount)` + rowcount + dual-write `pages_count` + запись `BalanceTransaction` (закрывает текущую TOCTOU-гонку в `spend_pages`)
- `add_kopecks(...)`, `has_enough_kopecks(...)`
- Старые `spend_pages/add_pages` на время dual-write — обёртки ×100
- Исправить хардкоды: `CustomUser.save()` (:534, бесплатные звёзды при регистрации), `activate_paid_tariff` (:568)
- Идемпотентность платежей: запись ledger внутри существующего guard `payment_success` + unique(type, reference)
- **Refund возвращает записанную сумму, не пересчёт** (иначе дрейф при ceil)

### Фаза 5 — Точки списания (~34 call sites)
- `src/api/services/billing.py`: `tokens_to_kopecks()` = `max(MIN_CHARGE_KOPECKS, ceil(rate*tokens/1000))`; орг-списание копейками атомарно; убрать `ORG_RUB_PER_STAR`
- `src/aitext/views.py` (:167, :274), `src/aitext/tasks.py` (:702 pre-charge, :753 refund, :1037, :1108/:1151 upscale)
- `src/api/views/`: chats.py (:123,:250,:357,:716,:596,:670), chat.py (:108,:221,:117), images.py (:76,:101,:128), audio.py (:78,:143 — flat 1 звезда → 100 копеек), embeddings.py (:93), compare.py (:104), billing.py (:240 promo)
- `src/studio/billing.py`: `KOPECK_RATE`, все 5 функций (charge/refund/reserve/charge_from_reserve/release_reserve) → копейки + `src/studio/tasks.py` синхронно
- `src/telegram_bot/handlers/`: chat.py/images.py/video_cmd.py — проверки баланса в копейках; group.py — унификация орг-ставки; admin.py — гранты

### Фаза 6 — Платежи
- Robokassa (`src/users/views.py`): подпись/суммы в ₽ без изменений; `payment_success` (:628) начисляет `add_kopecks(...)` с reference=invoice_id; реферальная ветка (:693-700) — `rub_balance` не трогаем, звёздная ветка → `referral_bonus_kopecks`
- `src/users/tasks.py` рекурренты → `add_kopecks(reference=invoice_id)`
- XTR (`src/telegram_bot/handlers/payment.py`): `RUB_PACKS` (relabel: 100 ₽/50 XTR, 220 ₽/100 XTR, 600 ₽/250 XTR), `on_successful_payment` → `add_kopecks(rubles*100, type='xtr', reference=telegram_charge_id)`
- Бот `handlers/balance.py`: карточка «Баланс: 125 ₽», «5 ₽/сообщ.», «~199 ответов» через `format_rub`

### Фаза 7 — API-контракт (публичный /api/v1 — не ломать)
Старые поля как `SerializerMethodField`-алиасы + новые авторитетные поля, deprecation ≥ 1 релиз:

| Старое (алиас) | Новое |
|---|---|
| `pages_count` | `balance_kopecks`, `balance_rub` (string) |
| `new_balance` | `new_balance_kopecks` |
| `cost_per_message` | `cost_kopecks`, `cost_rub` |
| `stars_charged` | `kopecks_charged` / `cost_kopecks` |
| Tariff `pages_count` | `balance_grant_kopecks` |

### Фаза 8 — Frontend (25+ файлов, ~40 мест)
- `frontend/lib/api/types.ts`: новые поля, старые — `@deprecated`
- `frontend/lib/stores/auth.ts`: **persist version=2 + migrate()** (сброс устаревшего localStorage "aineron-auth" — иначе неверный баланс после деплоя); `stars/setStars` → `balanceKopecks/setBalance`
- Все дисплеи через `formatRub()`: Navbar, account/* (billing, analytics «зв.»→«₽», referral), models/CatalogClient, **models/[slug] JSON-LD → `priceCurrency: "RUB"` (SEO!)**, chat (setBalance(new_balance_kopecks)), compare, AnimateImageModal, studio (5 файлов), register («Дарим 10 ₽ за регистрацию»), welcome, landing + FaqAccordion (переписать FAQ про звёзды → рубли), tg/ Mini App, dashboard/usage, ide, api-docs

### Фаза 9 — Тесты
- `test_money.py`: round-trip, format_rub, ceil, MIN_CHARGE floor
- `test_balance.py`: атомарность spend (гонка, не в минус), ledger balance_after, идемпотентность unique(type, reference)
- миграционный тест backfill ×100; API tokens_to_kopecks границы; XTR идемпотентность; studio reserve/release сходимость

### Фаза 10 — Rollout R1
1. Backup БД (pg_dump)
2. `migrate` → код R1 (dual-write)
3. Контроль: `COUNT(*) WHERE balance_kopecks <> pages_count*100` = 0
4. Smoke: списание web/бот/studio, покупка Robokassa, покупка XTR, persist v2 в инкогнито
5. Наблюдение 1–3 дня → R2 (cleanup: удалить pages_count, dual-write, алиасы после уведомления API-клиентов)

### Фаза 11 — Документация
Лендинг/FAQ/оферта («рублёвый баланс», XTR — способ оплаты), api-docs deprecation, CLAUDE.md (раздел биллинга: копейки, инвариант, money-утилита, ledger).

## Ключевые риски (учтены в плане)
- Переполнение int32 при ×100 → BigIntegerField
- TOCTOU-гонки → атомарный UPDATE с F()
- Двойное начисление на ретрае вебхука → unique(type, reference) + guard
- Устаревший localStorage → persist v2
- JSON-LD цена → RUB (SEO Rich Results)
- Обрыв аналитики → конвертация ВСЕХ исторических строк
- Скрытое 10× подорожание орг-биллинга → явно флагируем владельцу

## Verification

Выполнено в ходе реализации (локально, SQLite, вне Docker):
1. `manage.py check` — 0 issues по всем приложениям.
2. `manage.py makemigrations` + `manage.py migrate` (SQLite test DB) — все миграции применяются чисто, включая backfill. По пути исправлены 3 **несвязанные, предсуществующие** миграции с чистым Postgres SQL без guard для SQLite (`aitext/migrations/0015_pgvector_chunks.py`, `0026_message_fts_index.py`) — блокировали любой локальный `manage.py test` до этой сессии; исправлены добавлением `schema_editor.connection.vendor == 'postgresql'` guard, поведение на проде не меняется.
3. `manage.py test core users api aitext studio` — 184 теста, все новые биллинговые тесты (core money, users balance/ledger/tariff-sync/Robokassa-идемпотентность, api tokens_to_kopecks/charge_for_tokens, studio StarReservationTest) зелёные. Оставшиеся ~60 ошибок в studio/aitext — **предсуществующий технический долг**, не связанный с этой миграцией (отсутствие `username` в `create_user()` в ~55 старых тестах studio; 3 теста зависят от недоступного в этой среде Redis; 2 теста — таймингово-чувствительный мок сэндбокса).
4. `cd frontend && npx tsc --noEmit` — 0 ошибок по всему проекту после правок 5 параллельных фронтенд-агентов.

## Аудит после реализации (2026-07-02) — найдено и исправлено

Полный аудит биллинга выявил и закрыл 13 багов (детали в истории коммитов):

**Критические:**
1. **Studio «чеканка денег»**: `reserve()` с фиксированным reference при цикле Run→Pause→Run инкрементировал фантомный резерв, который `release_reserve` реально начислял. Фикс: уникальный reference на запуск + guard на дубликат в `reserve()`.
2. **Бесплатные регенерации**: reference `chat-regen:{id}` переиспользовался — повторные списания схлопывались в no-op. Фикс: uuid на попытку.
3. **Бесплатный повторный upscale + фантомный refund**: reference `upscale:{generation_id}` не различал попытки. Фикс: `upscale:{generation_id}:{placeholder_id}`.
4. **Нет возврата при провале текстовой генерации (polling)**: pre-charge в view, возврата в Celery-задаче не было. Фикс: `aitext/billing.py` — `record_message_billing`/`refund_message_billing` (метаданные в settings сообщения), возврат при `MaxRetriesExceededError`.
5. **Мина двойного списания TEXT_BILLING_ENABLED**: при включении флага задача списала бы второй раз поверх pre-charge веба. Фикс: skip при `billing_reference`.

**Высокие/средние:** Studio `cost=1` (копейка вместо 1 ₽, 3 view) → 100; орг-списание в группах до валидации текста → валидация до списания; утечка превью-резерва → `release_reserve_amount()` (частичный возврат) во всех 3 settle-точках; audio ASR/TTS гейт `balance>0` при цене 1 ₽ → `has_enough_kopecks(100)` + проверка результата spend; legacy-промокод → идемпотентный `add_kopecks(type='promo')` + `UsedPromoCode` до начисления; рублёвый реферальный бонус → атомарный гейт статуса платежа + `F()`; дрейф `pages_count` при дробных ценах → пересчёт от фактического баланса; дубль `PaymentHistory` при recurring-переходе тарифа → guard по invoice_id; `teams/admin.mark_paid` → атомарный статус-гейт + `F()`; завышение legacy-аналитики `max(1, …)` → честный floor.

**Известное ограничение** (не критично, отложено): при провале асинхронной генерации в Telegram-группах с орг-биллингом возврат на орг-баланс не выполняется (требует прокидывания контекста организации в Celery-задачу).

Ещё предстоит перед реальным деплоем:
1. `cd frontend && npm run build && npm run lint`
2. Прогон миграций на реальной копии продовой Postgres-БД (staging) + контрольный SQL: `SELECT COUNT(*) FROM users_customuser WHERE balance_kopecks <> pages_count*100` = 0
3. Ручной smoke: регистрация → 10 ₽ на балансе; отправка сообщения → списание; отказ генерации → возврат ровно списанной суммы; ledger (`BalanceTransaction`) содержит обе записи
4. Smoke бота (polling `run_bot`): /balance показывает ₽, покупка XTR начисляет ₽, повтор вебхука Robokassa не задваивает баланс (уже покрыто автотестом `RobokassaWebhookIdempotencyTests`, но стоит перепроверить вручную на staging)
5. Реальный деплой (`bash deploy.sh`) — **не выполнялся в рамках этой сессии**, требует отдельного подтверждения владельца перед прогоном на боевой БД
