# Studio Preview — Текущий статус (2026-06-25)

## Что сделано (все 7 спринтов + bugfix)

### Sprint 0-1: Фундамент
- `preview-service/` — отдельный FastAPI микросервис (порт 8001)
- E2B SPIKE: sandbox создаётся за ~150ms, port forwarding через `sbx.get_host(port)`
- Egress SPIKE: `network=` kwarg работает, egress deny-all + allowlist подтверждён
- Sandpack для React/Vue/HTML/TMA — браузер, $0, нулевые Docker-баги

### Sprint 2: E2B Runtime для Next.js/Python
- `E2BRuntime(Runtime ABC)` с Redis session store
- Slot semaphore (`preview:slots`, MAX_CONCURRENT)
- Port forwarding без cloudflared — `sbx.get_host(port)` → HTTPS
- Frontend: `E2BPreview.tsx` (poll/iframe), `PreviewPanel.tsx` (auto-select)
- Django: `E2BPreviewView`, `E2BPreviewStatusView`

### Sprint 3: Database Providers
- `AineronSchemaProvider`: `CREATE SCHEMA proj_{uuid}` + scoped PG role
- `NeonProvider`: Fernet-шифрование user API key, POST к Neon API
- `ExternalProvider`: Fernet-шифрование DSN
- `db-proxy`: circuit breaker (3 fails → 60s pause), statement_timeout=5s
- Django: `ProjectDatabase` model + migration 0018
- Frontend: `DatabasePanel.tsx`

### Sprint 4: Python/Django stack + Timeweb
- Django стек: `manage.py migrate` → uvicorn fallback на runserver
- Custom E2B templates: `python.Dockerfile`, `django.Dockerfile`, `nextjs.Dockerfile`
- `TimewebProvider`: Timeweb Cloud DB API (152-ФЗ)

### Sprint 5: Telegram Bot Preview
- **Tier 1 (AI-симулятор)**: `BotEmulator.tsx` — чат UI, LLM читает .py файлы, стоит 1 звезда
- **Tier 2 (E2B live)**: `TelegramBotPanel.tsx` — токен → E2B env only (никогда в БД)
- Security: Redis SETNX lock sha256(token), delete_webhook обязателен, egress allowlist
- `sprint5_bot.py` — все security helpers

### Sprint 6: Hardening
- Per-user rate limit: max 3 сессии/user через Redis INCR-first (без TOCTOU)
- `GET /metrics` — p50/p95/p99 latency, последние 1000 запусков
- `STUDIO_DEPRECATE_DOCKER_FRONTEND=1` — SandboxStatusView возвращает `sandpack:true`
- `DbExportView` — pg_dump для aineron-mode schemas, streaming download
- "Экспортировать данные" кнопка в `DatabasePanel.tsx`

### Sprint 7: DB wire-up + Log tail + Cleanup (2026-06-25) ✅
- **INTEGRATION GAP CLOSED**: db-proxy теперь получает `db_credentials_enc` в Redis-сессии
  - `_build_db_credentials_enc()`: для aineron mode — admin-creds + schema; для external — decrypt DSN
  - `ProjectDatabaseView.post()` aineron: `CREATE SCHEMA` + `ROLE` → `credentials_enc` → `provisioned=True`
  - `E2BPreviewView.post()` → `StartRequest.db_credentials_enc` → `E2BRuntime.start()` → Redis
- **Live log tail**: `E2BRuntime.get_logs()` → `/preview/{sid}/logs` → Django proxy → frontend
  - Terminal-кнопка в E2BPreview.tsx, `<pre>` панель до 40% высоты, обновление вручную
- **Bug/debt cleanup**:
  - 21× `StudioProject.objects.get()` → `get_object_or_404()` (replace_all, весь pipeline.py)
  - Удалён мёртвый `showIframe` код в PreviewPanel.tsx
  - `BASE_URL` экспортирован из client.ts; 3× `process.env.NEXT_PUBLIC_API_URL` → `BASE_URL` в studio.ts

### Bugfix audit (Opus 4.8 × 3 агента, 20 находок, все исправлено):
- Double-DECR SLOTS_KEY → счётчик уходил в минус
- Bot-lock race → SETNX fail удалял замок ДРУГОЙ сессии
- Non-atomic SETNX+EXPIRE → `SET nx=True ex=` (атомарно)
- Slot leak на TTL expiry → reaper thread (scan_iter каждые 60s)
- DDL blocklist bypass via semicolons → запрет `;` в SQL
- Circuit breaker на user query errors → только OperationalError
- Role name 12-char truncation → full UUID (35 chars)
- TOCTOU race в rate limit → INCR-first
- Bare `settings` NameError в PreviewProxyView → 500 на каждом HTML preview
- Missing get_object_or_404 в Sprint 5-6 views
- KeyError `data['session_id']` → `.get()` + 502 guard
- setInterval leak в TelegramBotPanel → useRef + clearPoll()
- showIframe мёртвый код → удалён
- `process.env.NEXT_PUBLIC_API_URL` без fallback → `BASE_URL` из client.ts

## Что осталось / следующие шаги

### Обязательно перед деплоем
1. **Интеграционный тест E2B** — запустить `preview-service/spikes/e2b_basic.py` с реальным ключом
2. **Деплой**: `bash deploy.sh` после проверки .env (E2B_API_KEY, PREVIEW_INTERNAL_TOKEN, FERNET_KEY)
3. **Миграция 0018**: `python manage.py migrate studio` на проде
4. **E2B templates build**: `cd preview-service/templates && bash build.sh`
5. **Env vars для aineron mode**: `AINERON_DB_HOST`, `AINERON_DB_PORT`, `AINERON_DB_NAME`, `AINERON_DB_USER`, `AINERON_DB_PASSWORD`

### Архитектурные улучшения (Sprint 8+)
- **Neon partner OAuth**: отправить заявку — user API key работает как временное решение
- **E2B billing**: показывать пользователю стоимость E2B превью (сейчас не биллится)
- **Status page интеграция**: показывать E2B uptime на /status/
- **Bot templates**: готовые шаблоны бота (aiogram 3, telebot, pyrogram) в Studio
- **WebSocket log streaming**: SSE или WebSocket для real-time логов вместо poll

## Файловая карта

```
preview-service/
  main.py               FastAPI app, /preview/ + /metrics + /db-proxy/ + logs endpoint
  settings.py           E2B_API_KEY, REDIS_URL, MAX_CONCURRENT, FERNET_KEY, ...
  runtime/
    base.py             Runtime ABC, Stack/SessionState/PreviewSession dataclasses
    e2b_runtime.py      E2BRuntime, slot semaphore, reaper thread, bot lock, get_logs()
    sprint5_bot.py      bot_lock_key, bot_egress_network, _BOT_STARTUP_CMD
  db/
    base.py             DatabaseProvider ABC, DBCredentials dataclass
    proxy.py            /db-proxy/query — circuit breaker, DDL block, semicolon guard
    aineron_provider.py CREATE SCHEMA + scoped PG role (full UUID naming)
    neon_provider.py    Neon Management API + Fernet-enc key
    external_provider.py DSN Fernet-enc, validate postgresql:// scheme
    timeweb_provider.py Timeweb Cloud DB API (152-ФЗ)
    crypto.py           Fernet encrypt/decrypt helpers
    _migrate.py         Forward-only migration runner
  templates/
    python.Dockerfile   E2B custom template: python 3.11, pip, common libs
    django.Dockerfile   E2B custom template: django, uvicorn, psycopg2
    nextjs.Dockerfile   E2B custom template: node 20, npm
    build.sh            e2b template build script
  spikes/
    e2b_basic.py        SPIKE-2: sandbox create + exec (passed)
    e2b_egress.py       SPIKE-3: network= egress deny-all (passed)

src/studio/
  models.py             StudioProject, ProjectDatabase (mode/neon_project_id/...)
  views/pipeline.py     100% get_object_or_404, _build_db_credentials_enc(),
                        E2BPreviewView, E2BPreviewStatusView, E2BPreviewLogsView,
                        ProjectDatabaseView (with aineron provision), DbExportView,
                        BotEmulateView, E2BBotPreviewView, SandboxStatusView
  urls.py               /e2b/, /e2b/<session_id>/, /e2b/<session_id>/logs/,
                        /db/, /db/export/, /bot-emulate/, /e2b-bot/
  migrations/0018_projectdatabase.py

frontend/components/studio/
  SandpackPreview.tsx   React/Vue/HTML/TMA браузерный превью
  E2BPreview.tsx        E2B превью: poll/iframe + Terminal-кнопка + log panel
  PreviewPanel.tsx      Auto-select: Sandpack vs E2B (showIframe мёртвый код удалён)
  DatabasePanel.tsx     Aineron/Neon/External UI + "Экспортировать данные"
  BotEmulator.tsx       Tier 1 AI chat simulator
  TelegramBotPanel.tsx  Tier 2 E2B live bot + Tier 1 tab (fixed interval leak)

frontend/lib/api/
  client.ts             BASE_URL экспортирован
  studio.ts             все API: e2bPreviewStart/Status/Stop/Logs, db*, botEmulate, e2bBotStart
```
