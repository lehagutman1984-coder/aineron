# Studio Live Preview — Master Plan

> Единый источник правды по фиче **Studio Live Preview** (aineron.ru).
> Заменяет `STUDIO_PREVIEW_PLAN.md` (архитектура) и `STUDIO_PREVIEW_STATUS.md` (статус).
> Дата актуализации: **2026-06-25**. Состояние: **Sprint 0–7 code-complete**, перед первым продакшн-деплоем.

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

## 3. Что сделано (Sprint 0–7)

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

---

## 4. Что НЕ сделано и почему (с приоритетами)

| # | Не сделано | Причина / статус | Приоритет |
|---|---|---|---|
| 1 | **E2B billing для пользователя** | Превью бесплатно — расход E2B не биллится | **КРИТ** |
| 2 | **E2B warm pool / snapshot-restore** | Cold start 30–60 с (`npm install`/`pip install`). Шаблоны помогают, но не собраны | **КРИТ** |
| 3 | **WebSocket/SSE log streaming** | Логи через ручной poll (кнопка «Обновить»). UX отстаёт от реалтайма | Важно |
| 4 | **Timeweb провизия** | `TimewebProvider` есть, API = `NotImplementedError`. Нужна для 152-ФЗ клиентов | Важно |
| 5 | **Status page интеграция** | E2B uptime/метрики не выводятся на `/status/` | Важно |
| 6 | **Forward-only migrations runner** | `db/_migrate.py` (`__schema_version`) есть, в проде не используется | Опц. |
| 7 | **Bot templates (aiogram/telebot)** | Готовых стартовых шаблонов в Studio нет | Опц. |
| 8 | **PgBouncer** | Не нужен при текущей нагрузке (db-proxy достаточен) | Опц. |
| 9 | **FirecrackerRuntime (своя инфра)** | ABC-шов есть; смысл при расходах E2B > €80–100/мес | Опц. |
| 10 | **Neon partner OAuth** | Работаем через user API key (самообслуживание) — осознанный выбор | Опц. |
| 11 | **Cloudflare Tunnel** | Сознательно убран, заменён на `sbx.get_host(port)` | Не нужен |
| 12 | **README / docs preview-service** | Минимальные | Важно |

---

## 5. Следующие спринты (Sprint 8+)

### Sprint 8 — Монетизация E2B (highest ROI) — КРИТ
- [ ] Учёт минут сессии: в `preview_stop` (и при reaper-истечении) считать `duration = now − started_at`.
- [ ] Конвертация `минуты × $0.0022 → звёзды` и списание против существующего баланса.
- [ ] Предстарт-проверка баланса в `preview_start` → 402 при нуле.
- [ ] Хранить `started_at`, `user_id`, `cost_stars` в Redis + финальная запись в Django audit.
- [ ] UI: индикатор стоимости и текущего «расхода» сессии (см. §7).
- [ ] Жёсткий суточный лимит минут на пользователя + глобальный kill-switch (env-флаг).

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
- [ ] **E2B billing** (Sprint 8) — сейчас фича раздаёт платный ресурс бесплатно. Hook-точка: `preview_start`/`preview_stop` в `main.py`.
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

| Что добавить | Компонент/иконка | Зачем |
|---|---|---|
| **Кнопка «Остановить сессию»** (отсутствует!) | `StopCircle` в шапке рядом с Refresh | Пользователь не может явно освободить слот и прекратить биллинг |
| **Таймер до истечения** (countdown к `expires_at`) | текст `MM:SS` в шапке | Сессия живёт 15 мин — нужно видеть, сколько осталось |
| **Индикатор стоимости** (минуты × тариф) | `Coins` иконка | Прозрачность после Sprint 8 billing |
| **Realtime-логи (SSE)** | заменить ручной poll | Стрим даёт ощущение «живого» dev-сервера |
| **Авто-показ логов при `failed`** | раскрывать `<pre>` автоматически | При падении пользователь сразу видит traceback без лишнего клика |
| **Бейдж стека** (nextjs/python/django) | бейдж в шапке | Подтверждение, какой движок запущен |

### 7.2 `PreviewPanel.tsx` — оркестратор

| Что добавить | Зачем |
|---|---|
| **Единый бейдж движка** (sandpack / e2b) | Пользователь видит, где исполняется код |
| **Переключатель viewport (375/768/100%)** для E2B-ветки | Сейчас есть только в Sandpack-ветке |
| **Тост вместо `window.alert()`** | `alert()` ломает профессиональный UX |

### 7.3 `TelegramBotPanel.tsx` — живой бот

| Что добавить | Зачем |
|---|---|
| **Таймер до автостопа (15 мин)** | Бот автоматически завершается — нужен видимый обратный отсчёт |
| **Кнопка «Открыть бота в Telegram»** (deep-link `t.me/<botname>`) | Прямой путь к тесту запущенного бота |
| **Live-лог бота** (Terminal-кнопка как в E2BPreview) | При ошибке непонятно, что не так |

### 7.4 `DatabasePanel.tsx` — БД

| Что добавить | Зачем |
|---|---|
| **Кнопка «Проверить подключение»** (ping через db-proxy) | Убедиться, что DSN/Neon-ключ валиден до запуска превью |
| **Индикатор circuit breaker** (`ShieldAlert`) | Показать, когда proxy временно блокирует соединения |
| **Прогресс экспорта `pg_dump`** | Сейчас streaming без видимой индикации |
| **Бейдж юрисдикции** (RU/Timeweb vs внешняя) | Важно для 152-ФЗ клиентов |

### 7.5 Глобально (Studio)

- [ ] **Бейдж «Превью / N звёзд/мин»** в шапке панели — счётчик расходов.
- [ ] **Единый компонент `<SessionTimer expiresAt>`** — переиспользовать в E2BPreview и TelegramBotPanel.
- [ ] **Замена всех `window.alert/prompt`** на единый toast/modal.

---

## 8. Pre-deploy checklist (перед `bash deploy.sh`)

### 8.1 Секреты и окружение — блокеры
- [ ] **`PREVIEW_INTERNAL_TOKEN`** — заменить дефолт на сильный секрет (в `preview-service/settings.py` и Django `.env`).
- [ ] **`E2B_API_KEY`** — задан и валиден.
- [ ] **`PROJECT_CONNECTOR_FERNET_KEY`** — байт-в-байт совпадает между Django и preview-service.
- [ ] **`REDIS_URL`** — доступен из preview-service контейнера.
- [ ] **`AINERON_DB_HOST/NAME/USER/PASSWORD/PORT`** — корректны для режима aineron.

### 8.2 Миграции и сервисы
- [ ] Применить миграцию **`0018`**: `python manage.py migrate studio`.
- [ ] preview-service запущен на :8001; `GET /healthz` → `{"ok": true}`.
- [ ] Reaper-thread жив (проверить лог `slot-reaper`).

### 8.3 Производительность / лимиты
- [ ] **Собрать E2B-шаблоны** (`templates/build.sh`) и задать `E2B_TEMPLATE_NEXTJS/PYTHON/DJANGO` — иначе cold start 30–60 с.
- [ ] Проверить `PREVIEW_MAX_CONCURRENT` (деф. 10) и per-user лимит (= 5).

### 8.4 Безопасность
- [ ] Egress-allowlist для бот-стека активен.
- [ ] Bot token нигде не пишется в файлы/лог.
- [ ] db-proxy: DDL-block, semicolon-guard, circuit breaker включены.

### 8.5 Биллинг — предупреждение
- [ ] **До Sprint 8** каждое серверное превью = бесплатный расход E2B. Рекомендуется временно ограничить доступ feature-флагом или суточным лимитом.

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
`models.py` (ProjectDatabase, migration 0018) · `views/pipeline.py` (все preview/db views)
`urls.py` (/e2b/, /e2b/{sid}/, /e2b/{sid}/logs/, /db/, /db/export/, /bot-emulate/, /e2b-bot/)

**Frontend (`frontend/components/studio/`):**
`PreviewPanel.tsx` · `E2BPreview.tsx` · `SandpackPreview.tsx` · `DatabasePanel.tsx`
`BotEmulator.tsx` · `TelegramBotPanel.tsx`
`frontend/lib/api/studio.ts` · `frontend/lib/api/client.ts` (BASE_URL exported)

---

*При изменении состояния обновлять §3 (сделано), §4 (не сделано), §8 (checklist).*
