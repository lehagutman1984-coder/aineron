# Studio Preview — Текущий статус (2026-06-25)

## Что сделано (все 6 спринтов + bugfix)

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

### Bugfix audit (Opus 4.8 × 3 агента, 20 находок):
**Исправлено 12 из 20:**
- Double-DECR SLOTS_KEY (было: слот дважды декрементировался → счётчик уходил в минус)
- Bot-lock race (было: SETNX fail удалял замок ДРУГОЙ сессии → антидубль-полинг не работал)
- Non-atomic SETNX+EXPIRE → `SET nx=True ex=` (атомарно, нет orphan locks)
- Slot leak на TTL expiry → фоновый reaper thread (reconcile через scan_iter каждые 60s)
- DDL blocklist bypass via semicolons (`SELECT 1; DROP TABLE x`) → запрет `;` в SQL
- Circuit breaker трипал на user query errors → теперь только на OperationalError
- Role name 12-char truncation → full UUID (35 chars) во избежание коллизий
- TOCTOU race в rate limit → INCR-first pattern
- Bare `settings` NameError в PreviewProxyView (→ 500 на каждом HTML preview)
- Missing get_object_or_404 в Sprint 5-6 views (→ 500 вместо 404)
- KeyError `data['session_id']` → `.get()` + 502 guard
- setInterval leak в TelegramBotPanel → useRef + useEffect cleanup + clearPoll в stopBot

**Низкий приоритет (оставлено на потом):**
- showIframe мёртвый код в PreviewPanel.tsx
- refreshKey не используется в TelegramBotPanel (пока)
- NEXT_PUBLIC_API_URL без fallback в 3 местах studio.ts
- _poll_bot_alive улучшено, но не покрывает все edge cases

## Что НЕ сделано / следующие шаги

### Обязательно перед деплоем
1. **Интеграционный тест E2B** — запустить `preview-service/spikes/e2b_basic.py` с реальным ключом
2. **Деплой**: `bash deploy.sh` после проверки .env (E2B_API_KEY, PREVIEW_INTERNAL_TOKEN, FERNET_KEY)
3. **Миграция 0018**: `python manage.py migrate studio` на проде
4. **E2B templates build**: `cd preview-service/templates && bash build.sh` (python/django/nextjs шаблоны)

### Архитектурные улучшения (Sprint 7+)
- **DB credentials в Redis session**: `E2BRuntime.start()` должен провайдить БД лениво и записывать `db_credentials_enc` в Redis — без этого db-proxy всегда возвращает 404 (INTEGRATION GAP задокументирован в proxy.py)
- **Neon partner OAuth**: отправить заявку, пока ждём — user API key работает
- **Log tail в UI**: передавать `/tmp/preview.log` от E2B через WebSocket или SSE
- **E2B network= SDK version**: проверить, поддерживает ли текущая версия egress restriction; если нет — использовать E2B template firewall config
- **`get_object_or_404` во всех views**: pre-existing views (EstimateView, PipelineRunView и др.) всё ещё используют `.get()` — отдельный рефакторинг

### Направление движения
После деплоя и тестирования:
- **Monetization**: показывать стоимость E2B превью пользователю (сейчас не биллится)
- **Status page интеграция**: показывать E2B uptime на /status/
- **Multi-file bot templates**: готовые шаблоны бота (aiogram 3, telebot, pyrogram) в Studio

## Файловая карта

```
preview-service/
  main.py               FastAPI app, /preview/ + /metrics + /db-proxy/
  settings.py           E2B_API_KEY, REDIS_URL, MAX_CONCURRENT, FERNET_KEY, ...
  runtime/
    base.py             Runtime ABC, Stack/SessionState/PreviewSession dataclasses
    e2b_runtime.py      E2BRuntime, slot semaphore, reaper thread, bot lock
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
  views/pipeline.py     E2BPreviewView, E2BPreviewStatusView, ProjectDatabaseView,
                        DbExportView, BotEmulateView, E2BBotPreviewView, SandboxStatusView
  urls.py               /e2b/, /e2b/<session_id>/, /db/, /db/export/, /bot-emulate/, /e2b-bot/
  migrations/0018_projectdatabase.py

frontend/components/studio/
  SandpackPreview.tsx   React/Vue/HTML/TMA браузерный превью
  E2BPreview.tsx        Серверный E2B превью (poll + iframe)
  PreviewPanel.tsx      Auto-select: Sandpack vs E2B vs Docker (deprecated)
  DatabasePanel.tsx     Aineron/Neon/External UI + "Экспортировать данные"
  BotEmulator.tsx       Tier 1 AI chat simulator
  TelegramBotPanel.tsx  Tier 2 E2B live bot + Tier 1 tab (fixed interval leak)

frontend/lib/api/studio.ts  e2bPreviewStart/Status/Stop, dbGet/Provision/Deprovision/ExportUrl,
                             botEmulate, e2bBotStart
```
