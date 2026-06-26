# preview-service

FastAPI микросервис, обеспечивающий Live Preview Studio на базе E2B Firecracker-сэндбоксов.

## Архитектура

```
Django (studio/views/pipeline.py)
    │
    │  X-Internal-Token (shared secret)
    ▼
preview-service (FastAPI, порт 8001)
    ├── /preview/start         — запустить сэндбокс (warm pool → pause/resume → cold create)
    ├── /preview/{id}/status   — статус сэндбокса
    ├── /preview/{id}          — DELETE: остановить и выставить финальный биллинг
    ├── /preview/{id}/logs     — последние N строк логов
    ├── /preview/{id}/logs/stream  — SSE-стрим логов
    ├── /db-proxy/query        — SQL-прокси к БД проекта (из сэндбокса)
    ├── /pool/warm             — принудительно добавить сэндбокс в warm pool
    ├── /pool/stats            — глубина warm pool по стекам
    └── /metrics               — p50/p95/p99 cold-start + hit_rate
```

## Переменные окружения

| Переменная | Обязательная | Описание | Пример |
|---|---|---|---|
| `REDIS_URL` | Да | URL Redis (тот же что у Celery) | `redis://localhost:6379/0` |
| `E2B_API_KEY` | Да | API-ключ E2B Firecracker | `e2b_...` |
| `INTERNAL_TOKEN` | Да | Shared secret для X-Internal-Token | `changeme-secret` |
| `MAX_CONCURRENT` | Нет (=10) | Максимум одновременных сэндбоксов | `10` |
| `POOL_TARGET_DEFAULT` | Нет (=2) | Цель warm pool на каждый стек | `2` |
| `DEFAULT_TTL` | Нет (=900) | TTL сэндбокса в секундах (15 мин) | `900` |
| `FERNET_KEY` | Если есть БД | Ключ шифрования учётных данных БД | `base64url...` |
| `NEON_API_KEY` | Если режим neon | API-ключ Neon | `napi_...` |
| `TIMEWEB_API_KEY` | Если режим timeweb | API-ключ Timeweb Cloud | `...` |
| `DB_PROXY_HOST` | Нет | Хост прокси-БД внутри сэндбокса | `db-proxy.internal` |

## Шаблоны E2B

| Стек | Template ID | Что prebake |
|---|---|---|
| `nextjs` | `khytik8ssbjahj8v943m` | Node 20, `node_modules` общих зависимостей, Next.js 14 |
| `python` | `jibema1fid8nzyw01p95` | Python 3.13, flask, fastapi, uvicorn, redis, python-dotenv |
| `django` | `x1mi9kdn8kzj7wca18pi` | Python 3.13, django, djangorestframework, gunicorn |

## Путь холодного старта (L1–L7)

1. **L1 Prebake** — шаблон уже содержит deps, npm install пропускается при совпадении хэша
2. **L2 Warm pool** — горячие сэндбоксы в Redis-очереди `preview:pool:{stack}`
3. **L3 Prewarm** — генерация проекта триггерит Celery-задачу `prewarm_preview`
4. **L4 Dep-delta skip** — хэш package.json сравнивается с кэшем, npm install пропускается
5. **L5 Pause/Resume** — `sbx.pause()` при STOP, `Sandbox.connect()` при последующем старте
6. **L6 Progressive UI** — фронтенд показывает ETA-прогрессбар и source badge (warm/paused/cold)
7. **L7 Hit-rate metrics** — Redis-счётчики + `/metrics` эндпоинт

Цель: **p95 < 5s** для warm/paused хитов, **p95 < 20s** для cold start.

## Запуск (локально)

```bash
cd preview-service
pip install -e ".[dev]"      # или: pip install fastapi uvicorn e2b redis psycopg2-binary requests

# Скопируйте и заполните переменные:
cp ../.env.example .env

uvicorn main:app --port 8001 --reload
```

Проверка:
```bash
curl -H "X-Internal-Token: changeme-secret" http://localhost:8001/metrics
```

## Запуск (Docker)

```bash
docker build -t preview-service -f Dockerfile .
docker run -p 8001:8001 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e E2B_API_KEY=e2b_... \
  -e INTERNAL_TOKEN=changeme-secret \
  preview-service
```

## Безопасность

- **X-Internal-Token** — сервис НЕ публичный, требует shared secret header на всех эндпоинтах
- **Bot token** — никогда не записывается в файлы или логи, передаётся только через `envs=` E2B SDK
- **Redis bot lock** — `SET bot_preview:{sha256(token)} "locked" nx=True ex=ttl+60` перед polling
- **Telegram webhook** — `delete_webhook(drop_pending_updates=True)` обязателен перед polling
- **DB credentials** — Fernet-шифрование в Redis, расшифровка только в момент подключения
- **Circuit breaker** — 3 ошибки подключения к БД → 60-секундная пауза (Redis key `cb:{provider}:{project_id}:fails`)
- **DDL blocklist** — DROP/ALTER/TRUNCATE и multi-statement (`;`) запрещены в db-proxy

## Runbook

### Сэндбокс завис / не отвечает
```bash
# Посмотреть активные сессии в Redis
redis-cli keys "preview:sess:*"
# Принудительно завершить через API
curl -X DELETE -H "X-Internal-Token: $TOKEN" http://localhost:8001/preview/{session_id}
```

### Warm pool пустой
```bash
# Проверить глубину
curl -H "X-Internal-Token: $TOKEN" http://localhost:8001/pool/stats
# Добавить вручную
curl -X POST -H "X-Internal-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stack":"nextjs","count":2}' \
  http://localhost:8001/pool/warm
```

### Hit-rate низкий (< 50%)
```bash
curl -H "X-Internal-Token: $TOKEN" http://localhost:8001/metrics
# prewarm_hits + paused_hits + pool_hits / total — если низко, увеличить POOL_TARGET_DEFAULT
```

### Превышен лимит слотов (429 Too Many Requests)
Увеличьте `MAX_CONCURRENT` или дождитесь завершения текущих сессий.
Reconciler (`reconcile_preview_billing` Celery-задача) force-kills сессии старше `DEFAULT_TTL + 60s`.

## Migrations (preview-service DB)

Скрипт `db/_migrate.py` содержит forward-only DDL миграции. В проде запускается вручную:
```bash
python db/_migrate.py
```
Автозапуск при старте сервиса намеренно **отключён** — команда принимает решение о каждой миграции.
