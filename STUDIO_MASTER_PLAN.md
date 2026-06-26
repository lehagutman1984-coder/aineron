# Studio Live Preview — Master Plan

> Единый источник правды по фиче **Studio Live Preview** (aineron.ru).
> Заменяет `STUDIO_PREVIEW_PLAN.md` (архитектура) и `STUDIO_PREVIEW_STATUS.md` (статус).
> Дата актуализации: **2026-06-26**. Состояние: **Sprint 0–8 code-complete**, перед первым продакшн-деплоем.
>
> **Дополняющий план:** [STUDIO_V5_PLAN.md](STUDIO_V5_PLAN.md) — надёжность AI-генерации (build gate, per-stack prompts, quality gate). Оба плана про Studio, но разные слои: этот = среда запуска; V5 = качество кода на выходе.

---

## 1. Назначение

Studio — AI-конструктор приложений внутри aineron.ru. Live Preview даёт пользователю **запускаемое** превью сгенерированного проекта прямо в браузере:

- **Фронтенд-стеки** (react/vue/html/tma) — рендер в браузере через Sandpack, $0 инфраструктуры.
- **Серверные стеки** (nextjs/python/django) — запуск в изолированной E2B Firecracker microVM с публичным URL.
- **Telegram-боты** — два режима: AI-эмулятор (Tier 1, дёшево) и живой бот в E2B (Tier 2, токен только в памяти).
- **База данных** — опциональная привязка БД к превью (aineron-схема / Neon / внешний DSN / Timeweb).

Принцип безопасности: **untrusted-код всегда исполняется вне Django-процесса** (отдельный FastAPI-сервис + E2B microVM), секреты (bot token, DSN) **никогда не пишутся в файлы sandbox или в общий лог**.

---

## 2. Архитектура (реальная, не плановая)

```
┌─────────────┐   HTTPS    ┌──────────────────────┐  X-Internal-Token  ┌────────────────────────┐
│  Next.js 14 │──────────▶ │  Django + DRF        │ ─────────────────▶ │ preview-service        │
│  (Studio UI)│            │  /studio/... proxy   │                    │ FastAPI :8001          │
└─────────────┘            │  ProjectDatabase     │                    │  ├─ E2BRuntime         │
       │                   │  db_credentials_enc  │                    │  ├─ db-proxy (router)  │
       │ Sandpack          │  DbExportView        │                    │  └─ /metrics /healthz  │
       │ (в браузере)      └──────────────────────┘                    └───────────┬────────────┘
       ▼                                                                            │
   [ браузерный iframe ]                                            E2B SDK         ▼
                                                              ┌───────────────────────────────┐
                                                              │ E2B Firecracker microVM       │
                                                              │  /app + npm/pip + dev server  │
                                                              │  sbx.get_host(port) → public  │
                                                              └───────────────┬───────────────┘
                                                                              │ psycopg2 (через db-proxy)
                                                                              ▼
                                          ┌────────────── Database providers ──────────────┐
                                          │ aineron schema │ Neon │ External DSN │ Timeweb │
                                          └─────────────────────────────────────────────────┘
                  Redis (session store, slot semaphore, per-user limit, bot lock, latency samples)
```

### 2.1 Ключевые архитектурные решения

| Решение | Реализовано как | Отличие от исходного плана |
|---|---|---|
| Runtime для серверных стеков | **E2B Firecracker** (`Sandbox.create`) | по плану; FirecrackerRuntime ABC оставлен как шов, без реализации |
| Публичный доступ к sandbox | **`sbx.get_host(port)`** (E2B native) | **заменил Cloudflare Tunnel** — не нужен отдельный binary, проще и надёжнее |
| Фронтенд-превью | **Sandpack** в браузере | по плану, $0 |
| Изоляция доступа к БД | **db-proxy** (FastAPI router): circuit breaker + DDL-block + semicolon-guard | по плану; **PgBouncer не используется** (db-proxy достаточен) |
| Хранилище сессий/слотов | **Redis** (session store, `preview:slots`, per-user, bot-lock) | по плану |
| Лимит конкурентности | глобальный `MAX_CONCURRENT=10` + reaper-thread | по плану |
| Лимит на пользователя | `MAX_SESSIONS_PER_USER = MAX_CONCURRENT // 2` = **5** (INCR-first, без TOCTOU) | по плану |
| Bot token | передаётся только через `envs=`, sha256 в Redis для lock; **в БД не пишется** | по плану |
| Шифрование DSN/ключей | **Fernet** (`PROJECT_CONNECTOR_FERNET_KEY`), byte-for-byte общий с Django | по плану |

### 2.2 preview-service — endpoints (`preview-service/main.py`)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/healthz` | health-check (без авторизации) |
| GET | `/metrics` | p50/p95/p99 latency старта, slots_used, max_concurrent |
| POST | `/preview/start` | старт sandbox (slot-лимит + per-user-лимит + db_credentials_enc) |
| DELETE | `/preview/{session_id}` | стоп sandbox, релиз слота и bot-lock |
| GET | `/preview/{session_id}/status` | состояние (starting/running/failed/expired/stopped) |
| GET | `/preview/{session_id}/logs` | tail `/tmp/preview.log` (до 500 строк) |
| (router) | `/db-proxy/query` | прокси SQL sandbox→БД с circuit breaker |

Все, кроме `/healthz`, защищены `X-Internal-Token` (`verify_token`).

---

## 3. Что сделано (Sprint 0–8)

### Sprint 0–1 — Каркас и SPIKE
- [x] `preview-service` (FastAPI, порт 8001), отдельный процесс от Django.
- [x] E2B SPIKE OK (`spikes/e2b_basic.py`, `spikes/e2b_egress.py`) — старт microVM, egress-проверка.
- [x] Sandpack для фронт-стеков (`SandpackPreview.tsx`).
- [x] Runtime ABC и Stack enum (`runtime/base.py`).

### Sprint 2 — E2B Runtime
- [x] `E2BRuntime` (`runtime/e2b_runtime.py`) с Redis session store.
- [x] Slot semaphore (`preview:slots`, `MAX_CONCURRENT`).
- [x] Port forwarding через `sbx.get_host(port)` (без cloudflared).
- [x] `E2BPreview.tsx`, `PreviewPanel.tsx` (auto-select engine по стеку).
- [x] Фоновый `_poll_until_up` → перевод сессии в RUNNING.

### Sprint 3 — Database Providers + db-proxy
- [x] `AineronSchemaProvider`, `NeonProvider`, `ExternalProvider` (`db/*.py`).
- [x] `db-proxy` (`db/proxy.py`): circuit breaker + DDL-block + semicolon-guard.
- [x] Django-модель `ProjectDatabase` (migration **0018**), режимы aineron/neon/external/none.
- [x] Fernet-шифрование секретов (`db/crypto.py`, ключ общий с Django).
- [x] `DatabasePanel.tsx` (выбор режима, write-only секреты: `has_neon_key`/`has_external_conn`).

### Sprint 4 — Django/Python стек + кастомные образы
- [x] Стек **django** в E2B: `pip install → migrate → uvicorn` (fallback `runserver`).
- [x] Стек **python**: `pip install → python main.py`.
- [x] Custom E2B templates через `E2B_TEMPLATE_*` (pre-installed deps).
- [x] `TimewebProvider` (класс есть; API-интеграция — `NotImplementedError`, см. §4).

### Sprint 5 — Telegram-боты (2 уровня)
- [x] Tier 1: `BotEmulator.tsx` — AI-симулятор диалога (`botEmulate`), 1 звезда.
- [x] Tier 2: `TelegramBotPanel.tsx` — табы AI-эмулятор / живой бот в E2B.
- [x] `sprint5_bot.py`: Redis `SET nx` lock (атомарный), egress-allowlist (`api.telegram.org`), `delete_webhook` перед polling.
- [x] Токен — только `envs=`, в Redis хранится `sha256`, TTL бота ≤ 15 мин (`BOT_MAX_TTL`).

### Sprint 6 — Лимиты, метрики, экспорт
- [x] Per-user rate limit (`MAX_SESSIONS_PER_USER`, INCR-first, без TOCTOU).
- [x] `GET /metrics` — p50/p95/p99.
- [x] `STUDIO_DEPRECATE_DOCKER_FRONTEND=1` (флаг отказа от Docker-фронтенда).
- [x] `DbExportView` — streaming `pg_dump`, кнопка «Экспортировать данные» в `DatabasePanel.tsx`.

### Sprint 7 — Закрытие integration-gap + log tail (2026-06-25)
- [x] `db_credentials_enc` проходит всю цепочку Django → preview-service → Redis → db-proxy.
- [x] Режим **aineron** теперь при провизии делает `CREATE SCHEMA + CREATE ROLE`.
- [x] Live log tail: `GET /preview/{id}/logs` + кнопка Terminal + `<pre>`-панель в `E2BPreview.tsx`.
- [x] `get_object_or_404` везде (replace_all 21 вхождение), удалён мёртвый код `showIframe`.
- [x] `BASE_URL` экспортирован из `client.ts`.

### Bugfix-волна (Opus 4.8 × 3 агента, 2026-06-25)
- [x] Double-DECR слотов (единственный owner — внешний `except`).
- [x] Bot-lock race (`acquired_bot_lock` флаг — не трогаем чужой lock).
- [x] Non-atomic SETNX+EXPIRE → одиночный `SET nx=True ex=`.
- [x] Slot leak при TTL-истечении → reaper-thread (reconcile каждые 60 с).
- [x] DDL bypass через `;` → semicolon-guard.
- [x] Circuit breaker реагирует только на `OperationalError`.
- [x] Role name 12-char truncation → full UUID (35 chars).
- [x] TOCTOU в rate limit → INCR-first.
- [x] `settings` NameError в PreviewProxyView.
- [x] `setInterval` leak в `TelegramBotPanel` (cleanup на unmount).

### Sprint 8 — Монетизация E2B — ✅ CODE-COMPLETE 2026-06-25
- [x] `PreviewSession` модель + migration **0019**, `reserve`/`charge_from_reserve`, Celery `reconcile_preview_billing`.
- [x] UI: `SessionTimer.tsx` (shared countdown, красный < 2 мин), переиспользован в `TelegramBotPanel`.
- [x] UI: `StopCircle` кнопка явной остановки, `Coins` индикатор стоимости, stack badge в шапке.
- [x] UI: авто-показ логов при `failed`; тосты вместо `window.alert()` в `PreviewPanel.tsx`.
- [x] UI: `TelegramBotPanel.tsx` — countdown + Terminal кнопка + live-логи бота.
- (подробности — §5 Sprint 8)

---

## 4. Что НЕ сделано и почему (с приоритетами)

| # | Не сделано | Причина / статус | Приоритет |
|---|---|---|---|
| 1 | **E2B warm pool / snapshot-restore** | Cold start 30–60 с (`npm install`/`pip install`). Шаблоны помогают, но не собраны | **КРИТ** |
| 2 | **WebSocket/SSE log streaming** | Логи через ручной poll (кнопка «Обновить»). UX отстаёт от реалтайма | Важно |
| 3 | **Timeweb провизия** | `TimewebProvider` есть, API = `NotImplementedError`. Нужна для 152-ФЗ клиентов | Важно |
| 4 | **Status page интеграция** | E2B uptime/метрики не выводятся на `/status/` | Важно |
| 5 | **Forward-only migrations runner** | `db/_migrate.py` (`__schema_version`) есть, в проде не используется | Опц. |
| 6 | **Bot templates (aiogram/telebot)** | Готовых стартовых шаблонов в Studio нет | Опц. |
| 7 | **PgBouncer** | Не нужен при текущей нагрузке (db-proxy достаточен) | Опц. |
| 8 | **FirecrackerRuntime (своя инфра)** | ABC-шов есть; смысл при расходах E2B > €80–100/мес | Опц. |
| 9 | **Neon partner OAuth** | Работаем через user API key (самообслуживание) — осознанный выбор | Опц. |
| 10 | **Cloudflare Tunnel** | Сознательно убран, заменён на `sbx.get_host(port)` | Не нужен |
| 11 | **README / docs preview-service** | Минимальные | Важно |

> **E2B billing (Sprint 8)** — ✅ DONE (см. §5 Sprint 8).

---

## 5. Sprint 8 (done) + Sprint 9–11 (план)

### Sprint 8 — Монетизация E2B — ✅ CODE-COMPLETE 2026-06-25
- [x] `started_at` в Redis-сессии (e2b_runtime.py), `duration_seconds` в stop-ответе.
- [x] `PreviewSession` модель + migration **0019** (`reserved_stars`, `settled` idempotency guard).
- [x] `E2BPreviewView.post()`: `reserve(user, 15 × rate, project)` → 402 при нуле баланса.
- [x] `E2BPreviewView.delete()` + `E2BPreviewStatusView.delete()`: `charge_from_reserve(actual)` + `settled=True`.
- [x] Celery task `reconcile_preview_billing` каждые 5 мин — settlement по TTL/expiry (Django-side reconciler).
- [x] `E2B_PREVIEW_STARS_PER_MIN=1` env-var — тариф без деплоя. **Пересчитать под курс звезда/рубль!**
- [x] UI: `SessionTimer.tsx` — shared countdown (красный < 2 мин), переиспользован в Bot.
- [x] UI: `StopCircle` кнопка, `Coins` стоимость, stack badge, авто-логи на failed.
- [x] UI: `TelegramBotPanel.tsx` — countdown + Terminal кнопка + live-логи бота.
- [x] UI: тосты вместо `window.alert()` в `PreviewPanel.tsx`.

### Sprint 9 — Холодный старт (UX скорости) — КРИТ
- [ ] Собрать кастомные образы (`templates/build.sh`) и прописать `E2B_TEMPLATE_NEXTJS/PYTHON/DJANGO`.
- [ ] Опционально warm-pool: 1–2 прогретых sandbox на популярный стек.
- [ ] Замерить p50/p95 старта до/после (через `/metrics`).

### Sprint 10 — Realtime логи и наблюдаемость — Важно
- [ ] SSE-эндпоинт `/preview/{id}/logs/stream` (заменить ручной poll в `E2BPreview.tsx`).
- [ ] Вывод E2B uptime + p95-старта на `/status/`.
- [ ] Алерты при срабатывании circuit breaker в db-proxy.

### Sprint 11 — БД и юрисдикция — Важно
- [ ] Завершить `TimewebProvider` (152-ФЗ).
- [ ] Включить forward-only migrations runner (`__schema_version`) в проде.
- [ ] Bot templates aiogram/telebot как стартовые проекты Studio.

---

## 6. Предлагаемые улучшения

### 6.1 Критические (монетизация / надёжность)
- [x] **E2B billing** (Sprint 8) — DONE. `reserve`/`charge_from_reserve`, `reconcile_preview_billing` Celery task, `SessionTimer.tsx`.
- [ ] **Жёсткий потолок расходов** — суточный лимит минут на пользователя и глобальный kill-switch.
- [ ] **Гарантированный teardown** — серверный watchdog, убивающий sandbox по `expires_at` независимо от фронта.

### 6.2 Важные (UX / конкурентное преимущество)
- [ ] **Realtime-логи (SSE)** вместо кнопки «Обновить».
- [ ] **Видимая стоимость превью** до и во время запуска — прозрачность биллинга.
- [ ] **Status-page интеграция** — публичный аптайм превью повышает доверие B2B.
- [ ] **Документация preview-service** (env-таблица, схема деплоя, runbook).

### 6.3 Опциональные (nice-to-have)
- [ ] Bot-шаблоны aiogram/telebot.
- [ ] Snapshot-restore для мгновенного рестарта.
- [ ] Forward-only migrations в проде.
- [ ] FirecrackerRuntime при росте расходов.

---

## 7. Frontend UX — конкретные задачи

Дизайн: **ноль эмодзи**, только **Lucide React** иконки, строгий профессиональный стиль.

### 7.1 `E2BPreview.tsx` — серверное превью

| Что добавить | Компонент/иконка | Статус |
|---|---|---|
| ~~**Кнопка «Остановить сессию»**~~ | `StopCircle` в шапке | ✅ Sprint 8 |
| ~~**Таймер до истечения** (countdown к `expires_at`)~~ | `SessionTimer.tsx` `MM:SS` | ✅ Sprint 8 |
| ~~**Индикатор стоимости** (минуты × тариф)~~ | `Coins` иконка | ✅ Sprint 8 |
| **Realtime-логи (SSE)** | заменить ручной poll | ⏳ Sprint 10 |
| ~~**Авто-показ логов при `failed`**~~ | раскрывать `<pre>` автоматически | ✅ Sprint 8 |
| ~~**Бейдж стека** (nextjs/python/django)~~ | бейдж в шапке | ✅ Sprint 8 |

### 7.2 `PreviewPanel.tsx` — оркестратор

| Что добавить | Статус |
|---|---|
| **Единый бейдж движка** (sandpack / e2b) | ⏳ TODO |
| **Переключатель viewport (375/768/100%)** для E2B-ветки | ⏳ TODO |
| ~~**Тост вместо `window.alert()`**~~ | ✅ Sprint 8 |

### 7.3 `TelegramBotPanel.tsx` — живой бот

| Что добавить | Статус |
|---|---|
| ~~**Таймер до автостопа (15 мин)**~~ | ✅ Sprint 8 (`SessionTimer.tsx`) |
| **Кнопка «Открыть бота в Telegram»** (deep-link `t.me/<botname>`) | ⏳ TODO |
| ~~**Live-лог бота** (Terminal-кнопка как в E2BPreview)~~ | ✅ Sprint 8 |

### 7.4 `DatabasePanel.tsx` — БД

| Что добавить | Зачем |
|---|---|
| **Кнопка «Проверить подключение»** (ping через db-proxy) | Убедиться, что DSN/Neon-ключ валиден до запуска превью |
| **Индикатор circuit breaker** (`ShieldAlert`) | Показать, когда proxy временно блокирует соединения |
| **Прогресс экспорта `pg_dump`** | Сейчас streaming без видимой индикации |
| **Бейдж юрисдикции** (RU/Timeweb vs внешняя) | Важно для 152-ФЗ клиентов |

### 7.5 Глобально (Studio)

- [ ] **Бейдж «Превью / N звёзд/мин»** в шапке панели — глобальный счётчик расходов.
- [x] ~~**Единый компонент `<SessionTimer expiresAt>`**~~ — ✅ Sprint 8 (переиспользован в E2BPreview и TelegramBotPanel).
- [x] ~~**Замена `window.alert/prompt`**~~ — ✅ Sprint 8 (тосты в `PreviewPanel.tsx`; проверить остальные компоненты).

---

## 8. Pre-deploy checklist (перед `bash deploy.sh`)

### 8.1 Секреты и окружение — блокеры
- [ ] **`PREVIEW_INTERNAL_TOKEN`** — заменить дефолт на сильный секрет (в `preview-service/settings.py` и Django `.env`).
- [ ] **`E2B_API_KEY`** — задан и валиден.
- [ ] **`PROJECT_CONNECTOR_FERNET_KEY`** — байт-в-байт совпадает между Django и preview-service.
- [ ] **`REDIS_URL`** — доступен из preview-service контейнера.
- [ ] **`AINERON_DB_HOST/NAME/USER/PASSWORD/PORT`** — корректны для режима aineron.

### 8.2 Миграции и сервисы
- [ ] Применить миграции:
  - **`0018`** — `ProjectDatabase` (db provider model)
  - **`0019`** — `PreviewSession` (billing reserve/settle)
  - **`0020`** — `target_stack`/`stack` max_length=20 (python/django/telegram_bot стеки)
  - Команда: `python manage.py migrate studio`
- [ ] preview-service запущен на :8001; `GET /healthz` → `{"ok": true}`.
- [ ] Reaper-thread жив (проверить лог `slot-reaper`).

### 8.3 Производительность / лимиты
- [ ] **Собрать E2B-шаблоны** (`templates/build.sh`) и задать `E2B_TEMPLATE_NEXTJS/PYTHON/DJANGO` — иначе cold start 30–60 с.
- [ ] Проверить `PREVIEW_MAX_CONCURRENT` (деф. 10) и per-user лимит (= 5).

### 8.4 Безопасность
- [ ] Egress-allowlist для бот-стека активен.
- [ ] Bot token нигде не пишется в файлы/лог.
- [ ] db-proxy: DDL-block, semicolon-guard, circuit breaker включены.

### 8.5 Биллинг
- [x] Sprint 8 billing реализован — `reserve`/`charge_from_reserve`, `reconcile_preview_billing`.
- [ ] Проверить тариф `E2B_PREVIEW_STARS_PER_MIN=1` (сейчас ≈$0.0022/мин при 2vCPU/2GiB) — пересчитать под курс звезда/рубль до продакшн-деплоя.

### 8.6 Уборка после деплоя
- [ ] `git rm STUDIO_PREVIEW_PLAN.md STUDIO_PREVIEW_STATUS.md` — заменены этим документом.

---

## 9. Unit economics

| Статья | Значение |
|---|---|
| E2B CPU | $0.0504 / vCPU-hr |
| E2B RAM | $0.0162 / GiB-hr |
| Активная сессия (2vCPU/2GiB) | ≈ **$0.0022/мин** |
| Cloudflare Tunnel | $0 (не используется, заменён `sbx.get_host`) |
| Neon (Mode 2) | $0 для aineron — платит пользователь |
| Break-even | 1000 сессий × 10 мин ≈ $22/мес; при тарифе ×3–4 окупается при сотнях активных сессий/день |

---

## 10. Файлы фичи (быстрый индекс)

**preview-service:**
`main.py` · `settings.py` · `runtime/base.py` · `runtime/e2b_runtime.py` · `runtime/sprint5_bot.py`
`db/proxy.py` · `db/crypto.py` · `db/aineron_provider.py` · `db/neon_provider.py`
`db/external_provider.py` · `db/timeweb_provider.py` · `db/_migrate.py`
`templates/python.Dockerfile` · `templates/django.Dockerfile` · `templates/nextjs.Dockerfile` · `templates/build.sh`
`spikes/e2b_basic.py` · `spikes/e2b_egress.py`

**Django (`src/studio/`):**
`models.py` (ProjectDatabase migration 0018, PreviewSession migration 0019, stack max_length migration 0020) · `views/pipeline.py` (все preview/db views)
`urls.py` (/e2b/, /e2b/{sid}/, /e2b/{sid}/logs/, /db/, /db/export/, /bot-emulate/, /e2b-bot/)

**Frontend (`frontend/components/studio/`):**
`PreviewPanel.tsx` · `E2BPreview.tsx` · `SandpackPreview.tsx` · `DatabasePanel.tsx`
`BotEmulator.tsx` · `TelegramBotPanel.tsx`
`frontend/lib/api/studio.ts` · `frontend/lib/api/client.ts` (BASE_URL exported)

---

*При изменении состояния обновлять §3 (сделано), §4 (не сделано), §8 (checklist).*

---

## 12. World-Class Cold Start — полный план (Sprint 9 expansion)

> Цель: **p50 < 3s, p95 < 5s** — лучше Replit (2-5s), CodeSandbox (2-4s), GitHub Codespaces (20-60s).
> Составлен Opus 4.8, 2026-06-26. Реализовывать слоями в порядке L1 → L3 → L2 → L5/L4 → L6 → L7.

### 12.1 Конкурентный анализ

| Конкурент | Cold start | Техника | Как мы их бьём |
|---|---|---|---|
| **StackBlitz** | <1s | WebContainers (Wasm Node, браузер) | Не запускает Python/Django/real servers/DB — мы можем |
| **Replit** | 2-5s | Persistent Nix VM + snapshot, always-on (paid) | Мы греем с **точными deps проекта** до клика (L3) — они греют generic |
| **CodeSandbox** | 2-4s | microVM project checkpoint после 1st build | То же через E2B pause/resume (L5), но "1st build" уже выполнен нами заранее |
| **Vercel v0** | 10-30s | serverless deploy | Другая модель; мы live-editable |
| **GitHub Codespaces** | 20-60s | полный rebuild контейнера | Мы никогда не делаем rebuild per-session |
| **E2B base (сейчас)** | 30-60s | base image без шаблонов | Custom template (L1) |
| **Aineron (цель)** | **p50 <3s / p95 <5s** | L1+L2+L3+L4+L5 | **Мы авторы кода → project-exact prewarm — наш ров** |

**Ключевой инсайт:** Replit/CodeSandbox не знают deps до клика. Aineron пишет `package.json`/`requirements.txt` в процессе генерации (30-120s) — к моменту клика «Превью» мы можем уже закончить `npm install`. Это структурное преимущество, которое конкуренты не могут скопировать.

### 12.2 Архитектурная схема

```
        DJANGO (Celery pipeline)               PREVIEW-SERVICE (FastAPI :8001)
 ┌────────────────────────────────┐       ┌──────────────────────────────────────────────┐
 │ commit_to_gitea                │       │  /preview/start   ◄── E2BPreviewView (Django) │
 │   └── prewarm_e2b.delay(pid) ──┼─HTTP─►│  /preview/prewarm ◄── prewarm_e2b Celery task │
 └────────────────────────────────┘  POST  │  /pool/stats      ◄── мониторинг              │
                                           │                                               │
                                           │   ┌─── CLAIM ORDER в start() ────────┐       │
                                           │   │ 1. preview:prewarm:{project_id}  │       │
                                           │   │ 2. preview:paused:{project_id}   │       │
                                           │   │ 3. preview:pool:{stack}  (LPOP)  │       │
                                           │   │ 4. Sandbox.create() — cold       │       │
                                           │   └──────────────────────────────────┘       │
                                           └──────────────┬────────────────────────────────┘
                                                          │ e2b SDK
                                    ┌─────────────────────┴──────────────────────────────┐
                                    │  POOL WARMER (singleton thread, Redis leader lock)  │
                                    │  держит N тёплых sandbox/stack, dev-server запущен  │
                                    └────────────────────────────────────────────────────┘

  REDIS — единый источник истины для pool/paused/prewarm/slots/latency
```

Каждый быстрый путь обязательно fallback-ает на следующий → в конечном счёте на `Sandbox.create()`. Нет пути, который не создаёт sandbox при сбое.

### 12.3 Слой L1 — Пребейк deps в шаблоне (1 день → 5-8s)

**Критическая находка:** `nextjs.Dockerfile` делает `npm install -g next@14 react@18 …` — глобальная установка НЕ удовлетворяет локальный `./node_modules` проекта. `_bg_start_nextjs` по-прежнему запускает полный `npm install` (30-60s) в каждой сессии. Простое выставление `E2B_TEMPLATE_NEXTJS` без фикса Dockerfile убирает только ~8s создания sandbox, но не 30-60s установки.

**Что сделать:**

**1a. Переписать `nextjs.Dockerfile`** — пребейковать проектный `node_modules`, а не глобальные пакеты:

```dockerfile
# preview-service/templates/nextjs.Dockerfile
FROM e2bdev/code-interpreter:latest

WORKDIR /opt/base
COPY base-package.json /opt/base/package.json
RUN npm install --legacy-peer-deps
# Сохраняем manifest для delta-check
RUN node -e "const p=require('./package.json'); const fs=require('fs'); \
    fs.writeFileSync('/opt/base/deps.json', JSON.stringify(p.dependencies||{}))"

WORKDIR /app
```

Добавить `preview-service/templates/base-package.json`:
```json
{
  "dependencies": {
    "next": "14",
    "react": "^18",
    "react-dom": "^18",
    "typescript": "^5",
    "tailwindcss": "^3",
    "autoprefixer": "^10",
    "postcss": "^8",
    "@types/react": "^18",
    "@types/node": "^20"
  }
}
```

**1b. Обновить `_bg_start_nextjs` в `e2b_runtime.py`** — симлинк-мерж вместо полного install:

```python
def _bg_start_nextjs(sbx: Sandbox, port: int):
    cmd = (
        "setsid bash -c '"
        "cd /app && "
        # Symlink base node_modules; only install project delta on top
        "ln -sfn /opt/base/node_modules /app/node_modules 2>/dev/null || true; "
        "if [ -f package.json ] && "
        "! diff -q <(node -p \"JSON.stringify(require('./package.json').dependencies||{})\") "
        "/opt/base/deps.json >/dev/null 2>&1; then "
        "  npm install --legacy-peer-deps --prefer-offline >> /tmp/preview.log 2>&1; "
        "fi; "
        f"npm run dev -- -p {port} >> /tmp/preview.log 2>&1"
        "' </dev/null >/dev/null 2>&1 &"
    )
    sbx.commands.run(cmd, timeout=30)
```

Для проектов, deps которых ⊆ base set (типовой scaffolded проект), `npm install` пропускается полностью → только `next dev` первая компиляция (~3-5s).

**1c. Выставить env vars** в `.env`:
```
E2B_TEMPLATE_NEXTJS=<id-после-build>
E2B_TEMPLATE_PYTHON=<id-после-build>
E2B_TEMPLATE_DJANGO=<id-после-build>
```

**Файлы:** `templates/nextjs.Dockerfile`, новый `templates/base-package.json`, `e2b_runtime.py`, `.env`.
**Результат:** nextjs **5-8s**, python/django **4-6s**.

---

### 12.4 Слой L3 — 🔥 UNIQUE: Generation-triggered project-exact pre-warming (1 день → 1.5-3s)

> Самый высокий impact/effort. Конкуренты не могут это реализовать — они не знают deps до клика.

**Идея:** Celery таска `commit_to_gitea` в `tasks.py` создаёт `package.json` за 30-120s ДО того как пользователь кликает «Превью». В этот момент мы запускаем прогрев с точными deps проекта. Когда пользователь кликает — sandbox уже готов.

**Django/Celery (`src/studio/tasks.py`)**:
```python
# В commit_to_gitea, после успешного коммита:
if project.target_stack in ('nextjs', 'python', 'django'):
    prewarm_e2b.delay(str(project.id))

@shared_task(bind=True, max_retries=1, queue=QUEUE)
def prewarm_e2b(self, project_id: str):
    from .models import StudioProject
    import hashlib, requests
    p = StudioProject.objects.get(id=project_id)
    files = {f.path: f.content for f in p.files.all()}
    dep_file = files.get('package.json') or files.get('requirements.txt') or ''
    dep_hash = hashlib.sha256(dep_file.encode()).hexdigest()[:16]
    preview_url = settings.STUDIO_PREVIEW_SERVICE_URL
    token = settings.STUDIO_PREVIEW_INTERNAL_TOKEN
    try:
        requests.post(
            f'{preview_url}/preview/prewarm',
            json={'project_id': project_id, 'stack': p.target_stack,
                  'dep_manifest': dep_file, 'dep_hash': dep_hash},
            headers={'X-Internal-Token': token},
            timeout=5,
        )
    except Exception:
        pass  # fire-and-forget: сбой прогрева не блокирует генерацию
```

**Preview-service (`main.py`)** — новый эндпоинт:
```python
class PrewarmRequest(BaseModel):
    project_id: str
    stack: str
    dep_manifest: str = ''
    dep_hash: str = ''

@app.post("/preview/prewarm", dependencies=[Depends(verify_token)])
async def prewarm_start(req: PrewarmRequest):
    # Идемпотентность: пропускаем если прогрев с тем же dep_hash уже есть
    existing_hash = _r.get(f"preview:prewarmhash:{req.project_id}")
    if _r.get(f"preview:prewarm:{req.project_id}") and existing_hash == req.dep_hash:
        return {"status": "already_warm"}
    asyncio.get_event_loop().run_in_executor(
        None, partial(_runtime.prewarm, req.project_id, req.stack,
                      req.dep_manifest, req.dep_hash))
    return {"status": "warming"}
```

**`e2b_runtime.py`** — новый метод `prewarm()`:
```python
def prewarm(self, project_id: str, stack: Stack, dep_manifest: str, dep_hash: str):
    # Claim pool sandbox or create new one
    pool_key = f"preview:pool:{stack.value}"
    sid = _r.lpop(pool_key)
    try:
        sbx = Sandbox.connect(sid, api_key=settings.E2B_API_KEY) if sid else \
              self._create_sandbox(Stack(stack), settings.DEFAULT_TTL, {})
        # Write only the dep manifest; start dev server with exact deps
        if dep_manifest:
            fname = 'package.json' if 'next' in stack or 'react' in stack else 'requirements.txt'
            sbx.files.write(f'/app/{fname}', dep_manifest)
            # Run install (this is the slow step — but happens during generation, not on click)
            _install_deps_for_stack(sbx, Stack(stack))
        sandbox_id = sbx.sandbox_id
        _r.setex(f"preview:prewarm:{project_id}", 600, sandbox_id)
        _r.setex(f"preview:prewarmhash:{project_id}", 600, dep_hash)
        _r.setex(f"preview:dephash:{project_id}", 3600, dep_hash)
        _r.incr("preview:claims:prewarm_created")
        logger.info("Prewarm done: project=%s sandbox=%s", project_id, sandbox_id)
    except Exception as exc:
        logger.warning("Prewarm failed project=%s: %s", project_id, exc)
```

**Claim в `start()`** (приоритет #1):
```python
prewarm_sid = _r.get(f"preview:prewarm:{project_id}")
if prewarm_sid:
    try:
        sbx = Sandbox.connect(prewarm_sid, api_key=settings.E2B_API_KEY)
        _r.delete(f"preview:prewarm:{project_id}")
        claim_source = "prewarm"
    except Exception:
        sbx = None  # fall through to next claim
```

**Файлы:** `tasks.py`, `main.py`, `e2b_runtime.py`.
**Результат:** **1.5-3s** для preview сразу после генерации (основной реальный flow).

---

### 12.5 Слой L2 — Warm pool (2-3 дня → 3-5s cold-click)

Generic warm pool — backstop для превью без предшествующей генерации.

**Redis структуры:**
```
preview:pool:{stack}            LIST    sandbox_ids (LPOP claim / RPUSH return)
preview:pool:meta:{sandbox_id}  HASH    stack, created_at, dev_ready
preview:pool:target:{stack}     STRING  желаемый размер (default 2, автоскейлинг L7)
preview:warmer:leader           STRING  SET NX EX 30 — singleton warmer
```

**Pool warmer** (singleton thread с leader lock в Redis):
```python
WORKER_ID = str(uuid.uuid4())

def _pool_warmer():
    while True:
        if _r.set("preview:warmer:leader", WORKER_ID, nx=True, ex=30):
            for stack in (Stack.NEXTJS, Stack.PYTHON, Stack.DJANGO):
                target = int(_r.get(f"preview:pool:target:{stack.value}") or 2)
                have = _r.llen(f"preview:pool:{stack.value}")
                slots_used = int(_r.get(SLOTS_KEY) or 0)
                budget = settings.MAX_CONCURRENT - slots_used
                for _ in range(min(target - have, max(0, budget))):
                    try:
                        _spawn_warm_sandbox(stack)
                    except Exception as exc:
                        logger.warning("Pool warm failed stack=%s: %s", stack, exc)
        time.sleep(10)

def _spawn_warm_sandbox(stack: Stack):
    sbx = self._create_sandbox(stack, 1800, {})  # 30 min pool TTL
    # start dev server on empty /app
    if stack == Stack.NEXTJS:
        sbx.commands.run("mkdir -p /app && cd /app && echo '{}' > package.json", timeout=5)
        _bg_start_nextjs(sbx, 3000)
    # ...
    _r.rpush(f"preview:pool:{stack.value}", sbx.sandbox_id)
    _r.hset(f"preview:pool:meta:{sbx.sandbox_id}", mapping={
        "stack": stack.value, "created_at": time.time(), "dev_ready": 0})
    _r.incr(SLOTS_KEY)
```

**stop() → return vs kill:**
```python
pool_key = f"preview:pool:{data['stack']}"
target = int(_r.get(f"preview:pool:target:{data['stack']}") or 2)
if _r.llen(pool_key) < target and (time.time() - data.get('created_at', 0)) < 1200:
    # Wipe user files, keep node_modules
    sbx.commands.run("find /app -mindepth 1 -not -path '*/node_modules*' -delete", timeout=10)
    _r.rpush(pool_key, sandbox_id)
else:
    sbx.kill()
    _r.decr(SLOTS_KEY)
```

**Pool-aware reaper** (расширяет `_reaper_loop`):
```python
# preview:slots = COUNT(sess:*) + SUM(LLEN(pool:*)) + COUNT(paused:*)
running = sum(1 for _ in _r.scan_iter(f"{SESSION_PREFIX}*"))
pooled  = sum(_r.llen(f"preview:pool:{s.value}") for s in Stack)
paused  = sum(1 for _ in _r.scan_iter("preview:paused:*"))
_r.set(SLOTS_KEY, max(0, running + pooled + paused))
```

---

### 12.6 Слой L5 — Pause/Resume: персистентность сессии (1-2 дня → 1-2s re-preview)

При остановке — **пауза** sandbox вместо kill. При следующем превью того же проекта — `Sandbox.resume()` (~1-2s) с сохранённым filesystem (incl. `node_modules`).

**Redis:**
```
preview:paused:{project_id}     STRING EX PAUSE_GRACE   sandbox_id
preview:paused:meta:{sid}       HASH   project_id, paused_at, stack
```

**stop() — добавить pause-path:**
```python
PAUSE_GRACE = int(os.getenv("PREVIEW_PAUSE_GRACE", "1800"))  # 30 min
PAUSE_ENABLED = os.getenv("PREVIEW_PAUSE_ENABLED", "1") == "1"

if PAUSE_ENABLED and not data.get("bot_sha"):  # боты не паузим
    try:
        sbx.pause()
        _r.setex(f"preview:paused:{project_id}", PAUSE_GRACE, sandbox_id)
        _r.hset(f"preview:paused:meta:{sandbox_id}", mapping={
            "project_id": project_id, "paused_at": time.time(), "stack": data["stack"]})
        _r.delete(_sess_key(session_id))  # не decr SLOTS_KEY — paused sandbox в пуле
        return  # НЕ убиваем
    except Exception as exc:
        logger.warning("Pause failed, killing: %s", exc)
sbx.kill()
_r.decr(SLOTS_KEY)
```

**Claim в `start()`** (приоритет #2 после prewarm):
```python
paused_sid = _r.get(f"preview:paused:{project_id}")
if paused_sid:
    try:
        sbx = Sandbox.resume(paused_sid, api_key=settings.E2B_API_KEY)
        _r.delete(f"preview:paused:{project_id}")
        claim_source = "resume"
        # L4: если dep_hash не изменился — skip install полностью
        old_hash = _r.get(f"preview:dephash:{project_id}")
        new_hash = _compute_dep_hash(code_files)
        if old_hash == new_hash:
            skip_install = True  # только upload source files + HMR reload
    except Exception:
        sbx = None  # GC'd → fall through
```

**Stale cleanup:** расширить `reconcile_preview_billing` в `src/studio/tasks.py`:
```python
# Удалить expired paused sandboxes
for key in r.scan_iter("preview:paused:*"):
    if r.ttl(key) < 0:
        sid = r.get(key)
        try:
            sbx = Sandbox.connect(sid, ...)
            sbx.kill()
        except: pass
        r.delete(key)
```

**Ограничение для Python/Django:** нет HMR, нужен restart процесса + `migrate` → floor ~2-4s даже на resume. Отражать в UI copy.

---

### 12.7 Слой L4 — 🔥 UNIQUE: Dependency-delta hash skip (встроен в L5)

При resume сравниваем hash `package.json`/`requirements.txt`:

```python
def _compute_dep_hash(code_files: dict) -> str:
    manifest = code_files.get('package.json') or code_files.get('requirements.txt') or ''
    return hashlib.sha256(manifest.encode()).hexdigest()[:16]

# В start() после resume:
old_hash = _r.get(f"preview:dephash:{project_id}")
new_hash = _compute_dep_hash(code_files)
if old_hash == new_hash:
    skip_install = True  # пропустить npm install полностью
_r.setex(f"preview:dephash:{project_id}", 3600, new_hash)
```

Для изменившихся deps — delta install (`npm install --prefer-offline` + `--legacy-peer-deps` добавляет только новое поверх `node_modules` из L1 symlink).

---

### 12.8 Слой L6 — Progressive UI: мгновенный первый пиксель (1-2 дня)

Показываем что-нибудь в <300ms пока E2B греется.

**`StartResponse`** в `main.py` — добавить поля:
```python
class StartResponse(BaseModel):
    session_id: str
    public_url: str
    expires_at: float
    started_at: float = 0.0
    state: str = "starting"
    claim_source: str = "cold"       # "prewarm" | "resume" | "pool" | "cold"
    eta_seconds: int = 8             # честная оценка по claim_source
```

**`E2BPreview.tsx`** — двухфазный рендер:
- На `state === 'starting'`: показываем Sandpack-shell (статическая версия кода) + прогресс-бар с `eta_seconds`
- Copy зависит от `claim_source`: `"prewarm"` → "Восстанавливаю готовый сеанс…", `"resume"` → "Возобновляю сессию…", `"pool"` → "Запускаю…", `"cold"` → "Запускаю (первый раз, ~{eta}s)…"
- Когда `state === 'running'`: crossfade E2B iframe поверх Sandpack-shell

---

### 12.9 Слой L7 — Метрики и автомасштабирование

**Расширить `/metrics`:**
```python
claim_prewarm = int(_r.get("preview:claims:prewarm") or 0)
claim_pool    = int(_r.get("preview:claims:pool")    or 0)
claim_resume  = int(_r.get("preview:claims:resume")  or 0)
claim_cold    = int(_r.get("preview:claims:cold")    or 0)
total = claim_prewarm + claim_pool + claim_resume + claim_cold or 1
return {
    ...,
    "hit_rate": (claim_prewarm + claim_pool + claim_resume) / total,
    "prewarm_hits": claim_prewarm,
    "pool_hits": claim_pool,
    "resume_hits": claim_resume,
    "cold_starts": claim_cold,
}
```

**Новый `/pool/stats`:**
```python
@app.get("/pool/stats", dependencies=[Depends(verify_token)])
def pool_stats():
    result = {}
    for stack in Stack:
        k = f"preview:pool:{stack.value}"
        result[stack.value] = {
            "warm": _r.llen(k),
            "target": int(_r.get(f"preview:pool:target:{stack.value}") or 2),
        }
    return result
```

**Автоскейлинг в warmer:**
```python
# Если p95 > 8s → увеличить target
raw = _r.lrange("preview:latency", 0, -1)
p95 = _percentile([float(x) for x in raw], 95) if raw else 0
target_key = f"preview:pool:target:{stack.value}"
current_target = int(_r.get(target_key) or 2)
if p95 > 8 and current_target < MAX_POOL_SIZE:
    _r.set(target_key, current_target + 1)
elif p95 < 3 and current_target > 1:
    _r.set(target_key, current_target - 1)
```

**🔥 UNIQUE — Predictive prewarm из pipeline state:** если проект в статусе `coding` >60s → стадировать pool sandbox под его стек заранее:
```python
# В _pool_warmer — predictive boost
for key in _r.scan_iter("studio:project:coding:*"):
    project_id = key.split(":")[-1]
    stack_str = _r.hget(f"studio:project:{project_id}", "stack")
    # Если ещё нет prewarm и нет resume — стадировать extra pool slot
    if not _r.get(f"preview:prewarm:{project_id}") and stack_str:
        _spawn_warm_sandbox(Stack(stack_str))
```

### 12.10 Полная карта Redis ключей

```
# Существующие (не менять семантику):
preview:sess:{session_id}          running session (hash)
preview:slots                      running + pool + paused (атомарный счётчик)
preview:latency                    LIST float для p50/p95/p99

# L2 — Pool:
preview:pool:{stack}               LIST  sandbox_ids  (LPOP claim, RPUSH return)
preview:pool:meta:{sandbox_id}     HASH  stack, created_at, dev_ready
preview:pool:target:{stack}        STRING желаемый размер (autoscaled)
preview:warmer:leader              STRING SET NX EX 30 (singleton)

# L3 — Generation prewarm:
preview:prewarm:{project_id}       STRING EX 600   sandbox_id
preview:prewarmhash:{project_id}   STRING EX 600   dep_hash

# L4/L5 — Pause/resume:
preview:paused:{project_id}        STRING EX 1800  sandbox_id
preview:paused:meta:{sandbox_id}   HASH  project_id, paused_at, stack
preview:dephash:{project_id}       STRING EX 3600  sha256[:16] package.json

# L7 — Metrics:
preview:claims:{source}            STRING INCR (prewarm|pool|resume|cold)
```

### 12.11 Файлы для изменения

| Файл | Слой | Что изменить |
|---|---|---|
| `templates/nextjs.Dockerfile` | L1 | `npm install -g` → project-local `/opt/base/node_modules` |
| `templates/base-package.json` | L1 | Новый файл: next@14 + deps |
| `preview-service/runtime/e2b_runtime.py` | L1-L5,L7 | `_bg_start_nextjs` symlink-merge, pool warmer, claim order, prewarm/pause/resume, reaper, delta-hash |
| `preview-service/main.py` | L3,L6,L7 | `/preview/prewarm`, `/pool/stats`, `StartResponse.claim_source/eta_seconds`, `/metrics` hit-rates |
| `preview-service/settings.py` | L2,L5,L7 | `POOL_TARGET_DEFAULT`, `POOL_MAX_AGE`, `PAUSE_ENABLED`, `PAUSE_GRACE`, `MAX_PAUSED`, `MAX_POOL_SIZE` |
| `src/studio/tasks.py` | L3,L5 | `prewarm_e2b` task, hook в `commit_to_gitea`, paused-cleanup в `reconcile_preview_billing` |
| `src/studio/views/pipeline.py` | L6 | Pass `claim_source` / `eta_seconds` в ответ фронтенда |
| `frontend/components/studio/E2BPreview.tsx` | L6 | Progressive render: Sandpack-bridge + crossfade + честный ETA |
| `frontend/components/studio/PreviewPanel.tsx` | L6 | claim_source-aware copy |

### 12.12 Plan порядка реализации (impact/effort)

| # | Слой | Усилие | Cold start после | Почему сначала |
|---|---|---|---|---|
| 1 | **L1 пребейк** (npm symlink fix + template build) | 1 день | 5-8s | Разблокирует всё; самое большое единичное падение |
| 2 | **L3 generation-prewarm** | 1 день | **1.5-3s** на hot path | Высший impact/effort; наш ров; нужен только Redis для prewarm ключей |
| 3 | **L2 warm pool** | 2-3 дня | 3-5s cold-click | Backstop для превью без предшествующей генерации |
| 4 | **L5 pause/resume + L4 delta** | 1-2 дня | **1-2s** re-preview | Убирает cost re-preview; реиспользует Redis pool |
| 5 | **L6 progressive UI** | 1-2 дня | <0.5s perceived | Воспринимаемая latency; независим от backend |
| 6 | **L7 autoscale + predictive** | 1 день | sustains p95<5s | Тюнинг; нужны L2 метрики |

### 12.13 Мониторинг и алерты

| Метрика | Алерт | Действие |
|---|---|---|
| `p95_s > 8` 5 мин подряд | page | warmer авто-увеличивает targets |
| `hit_rate < 50%` | warn | pool undersized или warmer leader мёртв |
| `slots_used == max_concurrent` sustained | warn | raise MAX_CONCURRENT или evict paused |
| warmer leader не обновляется >60s | critical | нет active warmer (crash или split-brain) |
| `paused_cost_estimate` > бюджет | warn | уменьшить PAUSE_GRACE или MAX_PAUSED |
