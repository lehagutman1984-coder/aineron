# STUDIO_PREVIEW_PLAN.md

Финальный исполнимый sprint-план: live-preview серверных стеков (Telegram Bot + Django/Python) внутри vibe-coding Studio на aineron.ru.

**Цель:** топ-1 в России по живому превью серверных стеков. Первые в СНГ с live Telegram Bot preview и Django-превью на реальной БД.

**Статус решений:** все архитектурные решения приняты (Runtime = E2B/Вариант A с ABC-швом под собственный Firecracker; БД = 4 провайдера через ABC; preview-service как отдельный микросервис; порядок Sandpack → E2B → Next.js → Python/Django → Telegram Bot → cleanup). Этот документ — реализация, не пересмотр.

---

## Обзор архитектуры (1 страница)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ПОЛЬЗОВАТЕЛЬ (браузер)                              │
│   Next.js Studio UI  ──  <SandpackPreview>  |  <E2BPreview src=tunnel_url>      │
└───────────┬───────────────────────────────────────────────┬────────────────────┘
            │ (фронт-стеки: HTML/React/Vue/TMA)              │ (серверные стеки)
            │  Sandpack — В БРАУЗЕРЕ, без бэкенда            │  HTTPS на tunnel URL
            ▼                                                ▼
   ┌──────────────────┐                          ┌────────────────────────────────┐
   │  Sandpack (CDN)  │                          │   Cloudflare Tunnel (бесплатно) │
   │  мгновенно,      │                          │   *.trycloudflare.com           │
   │  $0, изолировано │                          └───────────────┬─────────────────┘
   └──────────────────┘                                          │
                                                                 ▼
  ┌──────────────────────────┐   POST /preview/start   ┌─────────────────────────────┐
  │   src/studio (Django)    │ ──────────────────────► │   preview-service (FastAPI) │
  │   PreviewProxyView       │ ◄────────────────────── │   ОТДЕЛЬНЫЙ микросервис      │
  │   SandboxStatusView      │   session_id, url       │   Runtime ABC + DB ABC      │
  │   tasks.py (Celery)      │                         │   Redis: slot semaphore,    │
  │   models.StudioProject   │                         │   TTL watchdog, circuit br. │
  └──────────────────────────┘                         └──────────────┬──────────────┘
                                                                       │ e2b SDK
                                                                       ▼
                                              ┌─────────────────────────────────────────┐
                                              │   E2B (Firecracker microVM, ~150ms)       │
                                              │   • Node/Next.js | Python/Django | Bot    │
                                              │   • cloudflared tunnel --url              │
                                              │   • EGRESS DENY-ALL + allowlist           │
                                              │     (api.telegram.org, pip, db-proxy)     │
                                              │   • Bot token ТОЛЬКО в памяти sandbox      │
                                              └──────────────────┬────────────────────────┘
                                                                 │ db-proxy (connect_timeout=3,
                                                                 │ statement_timeout=5s, circuit breaker)
                                                                 ▼
                                       ┌──────────────────────────────────────────────────┐
                                       │            DatabaseProvider (ABC)                  │
                                       ├──────────────────────────────────────────────────┤
                                       │ Mode 1 AineronSchemaProvider  CREATE SCHEMA + PgB │
                                       │ Mode 2 NeonProvider           OAuth, USER платит  │
                                       │ Mode 3 ExternalProvider       paste conn (Fernet)  │
                                       │ Mode 4 TimewebProvider        РФ-юрисдикция        │
                                       └──────────────────────────────────────────────────┘
```

### DatabaseProvider flow (Mode-by-Mode)

```
Mode 1 (aineron):  UI "Создать базу" → provision() → CREATE SCHEMA proj_<id>
                   → role + GRANT → PgBouncer pool → DBCredentials (мгновенно).
                   Биллинг: aineron. Изоляция: schema-per-project.

Mode 2 (Neon):     UI "Вставить Neon API Key" (10 сек: Neon Console → Settings → API Keys)
                   → aineron вызывает POST /api/v2/projects с Bearer {user_key}
                   → project создаётся В АККАУНТЕ ПОЛЬЗОВАТЕЛЯ, ключ Fernet-шифруется.
                   OAuth недоступен без commercial partnership с Neon (только для партнёров).
                   Биллинг: ПОЛЬЗОВАТЕЛЬ (Neon free tier: 100 проектов, 0.5GB, 100 CU-h/мес).

Mode 3 (External): UI "Вставить connection string" → Fernet-encrypt → store
                   → db-proxy подключается. Биллинг: пользователь у своего провайдера.

Mode 4 (Timeweb):  UI "База в РФ (Timeweb)" → Timeweb Cloud DB API provision
                   → DBCredentials. Биллинг: aineron или пользователь (152-ФЗ).
```

---

## Runtime Interface (код)

`preview-service/runtime/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class Stack(str, Enum):
    NEXTJS = "nextjs"
    PYTHON = "python"
    DJANGO = "django"
    TELEGRAM_BOT = "telegram_bot"

class SessionState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class PreviewSession:
    session_id: str
    project_id: str
    public_url: str          # Cloudflare Tunnel URL
    internal_sandbox_id: str # e2b sandbox id — наружу не отдаём
    expires_at: float        # epoch, TTL watchdog

@dataclass
class SessionStatus:
    session_id: str
    state: SessionState
    public_url: str | None
    logs_tail: list[str]

class Runtime(ABC):
    @abstractmethod
    def start(self, project_id: str, code_files: dict[str, str],
              stack: Stack, ttl: int,
              env: dict[str, str] | None = None) -> PreviewSession: ...
    @abstractmethod
    def stop(self, session_id: str) -> None: ...
    @abstractmethod
    def status(self, session_id: str) -> SessionStatus: ...

class E2BRuntime(Runtime): ...        # Sprint 2 — реализация через e2b SDK
class FirecrackerRuntime(Runtime): ... # Будущее (Вариант B) — тот же интерфейс
```

---

## DatabaseProvider Interface (код)

`preview-service/db/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class DBCredentials:
    host: str
    port: int
    dbname: str
    user: str
    password: str          # в transit; в покое — Fernet
    schema: str | None     # для schema-per-project (Mode 1)
    provider: str          # "aineron" | "neon" | "external" | "timeweb"

class DatabaseProvider(ABC):
    @abstractmethod
    def provision(self, project_id: str) -> DBCredentials: ...
    @abstractmethod
    def sync_schema(self, credentials: DBCredentials,
                    migrations: list[str]) -> None: ...   # forward-only
    @abstractmethod
    def deprovision(self, project_id: str) -> None: ...

class AineronSchemaProvider(DatabaseProvider): ...  # Sprint 3 — CREATE SCHEMA + PgBouncer
class NeonProvider(DatabaseProvider): ...           # Sprint 3 — OAuth (SPIKE OK, см. ниже)
class ExternalProvider(DatabaseProvider): ...       # Sprint 3 — paste conn string + Fernet
class TimewebProvider(DatabaseProvider): ...        # Sprint 4 — РФ-юрисдикция
```

---

## Спринты

### Sprint 0 (3 дня) — Foundation & Spikes

**Цель:** скелет микросервиса + закрытые SPIKE-вопросы.

Файлы:
- `preview-service/` — отдельный Python-пакет **в корне репо**, НЕ в `src/` (untrusted code изолирован от основного Django).
- `preview-service/runtime/base.py` — `Runtime` ABC (см. выше).
- `preview-service/db/base.py` — `DatabaseProvider` ABC (см. выше).
- `preview-service/main.py` — FastAPI: заглушки `POST /preview/start`, `DELETE /preview/{id}`, `GET /preview/{id}/status`, `GET /healthz`.
- `preview-service/pyproject.toml` — зависимости: `fastapi`, `uvicorn`, `e2b`, `redis`, `cryptography`, `psycopg2-binary`, `httpx`.
- `preview-service/settings.py` — `MAX_CONCURRENT`, `DEFAULT_TTL`, `EGRESS_ALLOWLIST`, `E2B_API_KEY`.

Задачи:
- Скелет FastAPI + healthcheck + Redis-подключение.
- Внутренняя авторизация: shared-secret заголовок `X-Internal-Token` между `src/studio` и preview-service (preview-service НЕ публичный).

**SPIKE-1 (ЗАКРЫТ) — Neon механика: OAuth недоступен, используем Management API с user key.**
- Neon OAuth (`docs/guides/oauth-integration`): *«We only provide OAuth integrations for partners we have active commercial relationships with»* — недоступен без коммерческого соглашения с Neon. Заявку не подаём — это длинный и неопределённый процесс.
- **Решение (самообслуживание, без блокеров):** Neon Management API (`console.neon.tech/api/v2`) полностью self-serve: пользователь создаёт аккаунт Neon бесплатно → в Neon Console → Settings → API Keys копирует ключ → вставляет в aineron. aineron вызывает `POST /api/v2/projects` с `Authorization: Bearer {user_neon_api_key}` → проект создаётся В АККАУНТЕ ПОЛЬЗОВАТЕЛЯ, он владелец, он платит.
- UX: не OAuth-кнопка, а поле «Neon API Key» + ссылка на инструкцию (10 секунд для пользователя).
- Результат идентичен OAuth: база в аккаунте пользователя, aineron ничего не платит, Scale-to-zero.
- Free tier: 100 проектов/аккаунт, 0.5 GB storage/проект, 100 CU-hours/мес.
- В будущем: если Neon сам предложит партнёрство при росте трафика → добавим OAuth как апгрейд UX. `NeonProvider` менять не нужно, только добавить OAuth path рядом с API-key path.

**SPIKE-2 (design-confirmed по docs; sandbox ещё НЕ запускался — выполнить в Sprint 0) — E2B Python SDK + первый sandbox.**
```python
from e2b import Sandbox
sbx = Sandbox.create(template="base", timeout=600)  # подтвердить актуальный template id эмпирически
sbx.commands.run("echo hello")
sbx.kill()
```

**SPIKE-3 (design-confirmed по docs; deny-all эмпирически НЕ проверен — выполнить в Sprint 0) — E2B egress firewall (deny-all + allowlist).**
E2B поддерживает network policies (по docs, 2026). Allow-правила имеют приоритет над deny.
Ниже — форма API по docs (через WebFetch-резюме страницы); **точную сигнатуру `network=` подтвердить против актуального SDK при первом запуске**.
```python
from e2b import Sandbox
sbx = Sandbox.create(
    network={
        "deny_out": lambda ctx: [ctx.all_traffic],   # 0.0.0.0/0 — запрет всего
        "allow_out": [
            "api.telegram.org",
            "pypi.org", "files.pythonhosted.org",
            "<db-proxy-host>",
        ],
    },
)
# Рантайм-обновление allowlist (заменяет правила целиком):
sbx.update_network(...)
```
Также: `Sandbox.create(allow_internet_access=False)` для полностью offline-стадии сборки.

**Deliverable Sprint 0:** preview-service поднимается локально (`uvicorn preview-service.main:app`), `GET /healthz` отвечает; ABC-интерфейсы закоммичены; первый E2B sandbox создаётся из скрипта и egress deny-all с allowlist подтверждён эмпирически; дизайн Mode 2 зафиксирован (OAuth = user платит).

---

### Sprint 1 (2-3 дня) — Sandpack для HTML/React/Vue (немедленный выигрыш)

**Цель:** убрать целый класс Docker-багов для фронт-стеков; мгновенный preview без бэкенда.

Frontend (Next.js):
- Компонент `frontend/components/studio/SandpackPreview.tsx` (`@codesandbox/sandpack-react`):
  `<SandpackPreview files={files} stack={stack} />` — рендерит **в браузере**, изолированно, $0.
  (Подключить через существующий `frontend/components/studio/PreviewPanel.tsx`; статус — `SandboxStatusBadge.tsx`.)
- Условный рендер в Studio-плеере: `if stack in ['react','vue','html'] → <SandpackPreview> вместо iframe→Docker`.
- Источник файлов — уже существующий `GET /studio/projects/{id}/files/`.

Backend (`src/studio`):
- `SandboxStatusView` — добавить поле `engine: 'sandpack' | 'e2b' | 'docker'`. Для фронт-стеков возвращать `sandpack` (бэкенд-контейнер не нужен).
- В `tasks.py`: для Sandpack-стеков **не запускать** `restart_preview`/`deploy` Celery-таски (preview целиком на клиенте).

TMA (Telegram Mini App):
- Sandpack + инжект мок-SDK `window.Telegram.WebApp` (заглушки `ready()`, `expand()`, `initDataUnsafe`, `MainButton`, `themeParams`) → предпросмотр TMA без реального Telegram.

**Deliverable Sprint 1:** HTML/React/Vue/TMA-проекты показывают мгновенный preview через Sandpack; Docker-путь для этих стеков не задействуется; класс «контейнер не поднялся / порт 3000 не отвечает» багов для фронта устранён.

---

### Sprint 2 (5-7 дней) — E2B Runtime + Next.js preview

**Цель:** живой preview для Next.js (и базис для Python/Django/Bot) через изолированный E2B.

`preview-service`:
- `preview-service/runtime/e2b_runtime.py` — `E2BRuntime(Runtime)` через `e2b` SDK:
  - `start()`: создать sandbox с network policy (deny-all + allowlist), залить `code_files`, поднять dev-сервер (Next.js: `npm install && npm run dev -p 3000`), запустить `cloudflared tunnel --url http://localhost:3000`, распарсить `*.trycloudflare.com` URL → вернуть `PreviewSession`.
  - `stop()`: `sbx.kill()` + снять Redis slot.
  - `status()`: состояние sandbox + хвост логов.
- `preview-service/main.py`: реализовать `POST /preview/start`, `DELETE /preview/{id}`, `GET /preview/{id}/status`.
- **Redis slot semaphore:** `MAX_CONCURRENT` через `INCR preview:slots` / `DECR`; при превышении → `429`.
- **TTL watchdog:** фоновый таск (или Redis keyspace TTL + reaper-loop) убивает sandbox по `expires_at`; «N минут» настраивается.

`src/studio` (Django):
- `POST /studio/preview/start` → HTTP-вызов preview-service (`httpx`, заголовок `X-Internal-Token`) → отдаёт фронту `public_url`.
- Фронт `frontend/components/studio/E2BPreview.tsx`: `<iframe src={public_url}>` для серверных стеков (рендерится в `PreviewPanel.tsx`).
- `PreviewProxyView` оставляем для legacy Docker; новый путь не проксирует HTTP сами — отдаём прямой tunnel URL.

**Deliverable Sprint 2:** Next.js-проект получает живой публичный preview (Cloudflare Tunnel) через изолированный E2B; конкурентный доступ ограничен слотами; протухшие сессии автоматически убиваются.

---

### Sprint 3 (5-7 дней) — Database Provisioning

**Цель:** пользователь видит приложение на реальных данных; 3 режима БД.

`preview-service/db/`:
- `aineron_schema.py` — `AineronSchemaProvider`:
  - `provision()`: `CREATE SCHEMA proj_<id>`, создать role + `GRANT ... ON SCHEMA`, `search_path=proj_<id>` → `DBCredentials(schema=...)`.
  - **PgBouncer** (transaction pooling) перед общим Postgres для schema-per-project пулинга.
  - `deprovision()`: `DROP SCHEMA proj_<id> CASCADE`.
- `neon.py` — `NeonProvider` (SPIKE ЗАКРЫТ, без блокеров): принять `neon_api_key` от пользователя (Fernet-encrypt при хранении) → `POST https://console.neon.tech/api/v2/projects` с `Authorization: Bearer {key}` → project создаётся **в аккаунте пользователя** → `DBCredentials`.
- `external.py` — `ExternalProvider`: принять connection string, **Fernet-encrypt** (`cryptography`) перед хранением; расшифровка только в момент подключения db-proxy.
- `proxy.py` — **db-proxy endpoint** в preview-service: единая точка коннектов из sandbox в БД с
  `connect_timeout=3`, `statement_timeout='5s'`, **circuit breaker** (3 failures → 60s pause) через Redis-счётчик `cb:<provider>:fails`.

Миграции (forward-only):
- Таблица `__schema_version` в каждой БД; применяем только `ADD COLUMN`/`CREATE TABLE`/`CREATE INDEX`. Никаких DROP/ALTER-разрушающих — превью не должно терять данные.

UI (`frontend/`):
- Кнопка «Создать базу»: Mode 1 — мгновенно; Mode 2 — OAuth redirect на Neon; Mode 3 — поле «вставьте connection string».
- Показ статуса БД и выбранного провайдера в Studio.

**Deliverable Sprint 3:** пользователь одной кнопкой получает БД (3 режима), приложение в превью работает на реальных данных; db-proxy устойчив (таймауты + circuit breaker); миграции безопасны (forward-only).

---

### Sprint 4 (7-10 дней) — Python/Django Preview

**Цель:** Django-приложение с реальной БД в превью за секунды.

E2B base image / snapshot:
- Кастомный E2B template: Python + Django + DRF + psycopg2 + top-30 зависимостей **pre-built**.
- **Snapshot/restore:** прогреть sandbox → снять snapshot → restore за ~150ms (без `pip install` на старте).

`E2BRuntime` (расширение):
- Stack `python`/`django`: mount user code → `python manage.py migrate` (через `sync_schema`) → запустить ASGI-воркер (`uvicorn`/`daphne`) на :8000 → tunnel.
- Подключение к реальной БД через **db-proxy** (Sprint 3), egress allowlist включает db-proxy host.

`TimewebProvider` (Mode 4):
- `preview-service/db/timeweb.py` — адаптер к Timeweb Cloud Databases API (provision/deprovision Postgres) для **российской юрисдикции** (152-ФЗ). UI: «База в РФ (Timeweb)».

**Deliverable Sprint 4:** Django-проект поднимается в превью за секунды (warm snapshot), мигрирует и работает на реальной БД; доступна РФ-юрисдикция через Timeweb.

---

### Sprint 5 (5-7 дней) — Telegram Bot Preview (первые в СНГ)

**Цель:** живой preview Telegram-ботов. Два уровня.

**Tier 1 — in-browser эмулятор (по умолчанию, $0, без токена):**
- React-компонент fake-чат `frontend/components/studio/BotEmulator.tsx`: парсим handlers из кода (aiogram: `@dp.message`, `@router.callback_query`, команды), рендерим виртуальный диалог. Реальный Telegram не нужен.

**Tier 2 — E2B serverless polling (реальный бот, по запросу):**
- `E2BRuntime` stack `telegram_bot`: поднять aiogram-процесс в sandbox с polling.
- **ОБЯЗАТЕЛЬНО перед стартом polling:** `await bot.delete_webhook(drop_pending_updates=True)` — иначе 409 Conflict.
- **Один токен — одна сессия:** Redis-lock `SETNX bot_preview:{sha256(token)} <session_id> EX 900`. Если занято → отказ «бот уже в превью в другой сессии». Снимаем lock при stop.
- **Bot token НИКОГДА не персистим:** передаётся в `env` E2B sandbox, живёт только в памяти microVM; в БД aineron не пишется (ни в `StudioProject`, ни в логах). Хэш токена — только для Redis-lock.
- **Egress:** allowlist строго `api.telegram.org` (+ db-proxy, если бот ходит в БД).
- **Watchdog TTL 10-15 мин** → автоматический kill + `delete_webhook` cleanup + снятие lock.
- **Предупреждение в UI:** «На время preview-сессии (до 15 мин) бот будет перехвачен этим окном и не будет отвечать в других местах. Токен нигде не сохраняется.»

**Deliverable Sprint 5:** Tier 1 эмулятор работает для любого бота без токена; Tier 2 даёт реальный живой бот в Telegram на 10-15 мин с гарантией «один токен — одна сессия», без 409 и без утечки токена. **Первые в СНГ с live Telegram Bot preview.**

---

### Sprint 6 (3-5 дней) — Hardening & Cleanup

**Цель:** надёжность, наблюдаемость, миграция с Docker.

- `src/studio/sandbox.py`: **deprecate Docker preview для фронт-стеков** (флаг `ENGINE_DEPRECATE_DOCKER_FRONTEND`); серверные стеки уже на E2B.
- **Мониторинг:** p95/p99 restore-time (snapshot→ready), алерты по E2B quota и активным слотам; экспорт метрик из preview-service.
- **Rate limiting** на `POST /preview/start` per-user (Redis token bucket).
- **Экспорт данных:** кнопка «Экспортировать данные» → `pg_dump --schema=proj_<id> | psql $USER_DB` (вывод дампа пользователю / в его БД).
- Документация preview-service (README + OpenAPI) и changelog.

**Deliverable Sprint 6:** Docker-путь для фронта выключен; есть метрики и алерты; защита от абуза; пользователь может забрать свои данные; всё задокументировано.

---

## Швы для перехода A → B (Firecracker)

- **Когда переключаться:** когда расходы на E2B стабильно > €80-100/мес — это сигнал реальной нагрузки, при которой собственный Firecracker экономически оправдан.
- **Что делать:** реализовать `FirecrackerRuntime(Runtime)` с тем же интерфейсом `start/stop/status`. Своя orchestration-нода с Firecracker microVM + cloudflared + та же egress-модель.
- **Что НЕ меняется:** контракт `Runtime` ABC; HTTP-API preview-service (`/preview/*`); вызовы из `src/studio`; `DatabaseProvider` и db-proxy; весь UI. Переключение — через конфиг/фабрику Runtime.

---

## Unit Economics (с пометками estimate)

| Статья | Значение | Источник |
|---|---|---|
| E2B CPU | $0.0504 / vCPU-hr | проверено (e2b.dev/pricing, 2026) |
| E2B RAM | $0.0162 / GiB-hr | проверено |
| Активная сессия 2vCPU / 2GiB | (2·0.0504 + 2·0.0162) ≈ **$0.133/час** ≈ **$0.0022/мин** | проверено |
| Cloudflare Tunnel | **$0** | trycloudflare.com |
| Neon (Mode 2) | **$0 для aineron** — платит пользователь (free tier: 100 проектов, 0.5GB, 100 CU-h/мес) | проверено, docs |
| Storage E2B | бесплатно до 10 GiB (Hobby) / 20 GiB (Pro) | проверено |
| E2B Pro plan | $150/мес — 24h-сессии, до 100 concurrent (расш. до 1100), кастом CPU/RAM | проверено |
| Warm pool 3 VM (idle, 2vCPU/2GiB) | ~$0.133·3·730 ≈ **$291/мес** | estimate (idle, без scale-to-zero) |

**Break-even (estimate).** При $0.0022/мин активной сессии: 1000 сессий × 10 мин = ~$22/мес чистого compute. Платный «звёздный» тариф за preview-минуты с маржой ×3-4 покрывает E2B и warm-pool уже при сотнях активных сессий/день. Warm pool держать минимальным (1-3 VM) и масштабировать по очереди слотов, чтобы idle-расходы не съедали маржу. Точные цифры подтвердить после Sprint 2 на реальных p95-длительностях.

---

## Риски (по приоритету, с митигациями)

1. **Утечка bot token / untrusted code из основного приложения.** Митигация: preview-service — отдельный микросервис, не в `src/`; код исполняется ТОЛЬКО в E2B (Firecracker), не в Docker; токен только в памяти microVM, никогда в БД aineron; egress deny-all + allowlist с первого дня.
2. **409 Conflict Telegram Bot.** Митигация: `delete_webhook(drop_pending_updates=True)` перед polling + Redis-lock «один токен — одна сессия» (`SETNX ... EX 900`).
3. **db-proxy нестабильность под нагрузкой.** Митигация: `connect_timeout=3`, `statement_timeout='5s'`, circuit breaker (3 fails → 60s pause), PgBouncer перед Postgres.
4. **Neon OAuth недоступен без партнёрства.** Решено: Mode 2 реализован через Neon Management API с user-provided API key — самообслуживание, без блокеров. OAuth добавим позже как UX-апгрейд если Neon сам предложит партнёрство.
5. **E2B расходы выходят из-под контроля.** Митигация: Redis slot semaphore (`MAX_CONCURRENT`), TTL watchdog, per-user rate limiting, quota-алерты; warm pool минимальный; шов на собственный Firecracker готов.
6. **Egress allow-rule приоритет над deny.** В E2B allow имеет приоритет — митигация: allowlist держать строго минимальным и ревьюить при каждом добавлении хоста; разные allowlist на стадии build (offline где можно) и runtime.
7. **РФ-юрисдикция / 152-ФЗ для данных пользователей.** Митигация: Mode 4 TimewebProvider (БД в РФ); preview-service compute (E2B) — отдельный вопрос, для чувствительных данных предлагать Mode 4 + минимизировать persist.
8. **Forward-only миграции ломают данные.** Митигация: `__schema_version`, только ADD/CREATE, запрет разрушающих ALTER/DROP в авто-миграциях превью.

---

## Следующий шаг (что делать сегодня)

1. Создать каталог `preview-service/` в корне репо (НЕ в `src/`) с `pyproject.toml`, `main.py` (FastAPI + `/healthz`), `runtime/base.py` и `db/base.py` (ABC-интерфейсы из этого документа).
2. Получить `E2B_API_KEY`, прогнать SPIKE-2/3: создать первый sandbox и **эмпирически** подтвердить deny-all + allowlist (`network={"deny_out": lambda ctx: [ctx.all_traffic], "allow_out": [...]}`).
3. Для Mode 2 (Neon) — OAuth партнёрство не нужно. Neon Management API self-serve: `POST /api/v2/projects` с user API key. Реализуется в Sprint 3 без блокеров.
4. Закоммитить скелет (`feat(preview-service): scaffold + Runtime/DatabaseProvider ABC + spikes`) и сразу `git push origin main`.

---

### Источники (research)
- Neon OAuth (user владеет аккаунтом и платит): https://neon.com/docs/guides/oauth-integration
- Neon integration models (OAuth vs embedded project-per-user / кто платит): https://neon.com/docs/guides/platform-integration-overview
- Neon free tier 2026 (100 проектов, 0.5GB, 100 CU-h, scale-to-zero): https://neon.com/docs/introduction/plans
- E2B network policy / egress allowlist (Python `allow_out`/`deny_out`, `update_network`): https://e2b.dev/docs/sandbox/internet-access
- E2B pricing 2026 ($0.0504/vCPU-hr, $0.0162/GiB-hr): https://e2b.dev/pricing
