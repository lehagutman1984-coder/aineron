# SANDBOX_API_PLAN.md — Aineron Sandboxes (эксперимент)

> **СТАТУС (2026-07-06): SB-1…SB-4 CODE-COMPLETE.** Реализовано: runtime `/sandbox/*`
> в preview-service, Django-app `sandboxes` (биллинг/квоты/reconcile/abuse), DRF
> `/api/v1/sandboxes/`, Python SDK (`sdk/python`), доки+playground+лендинг, админка,
> метрики на /status/. Тесты: `python manage.py test sandboxes api.tests_sandboxes`.
> **Блокер запуска: E2B-аккаунт заблокирован** (нет платёжного метода) и
> `preview_service` спрятан за docker-профилем `studio` — см. чеклист §10.
> Флаг `SANDBOX_API_ENABLED=0` — API отключён до прохождения чеклиста.

> **Продукт:** публичный API исполнения недоверенного кода в изолированных microVM —
> «российский E2B». Первый и единственный sandbox-API в каталоге российских AI-платформ.
> **Формат:** бюджетный эксперимент поверх уже написанного `preview-service` (E2B под капотом),
> без покупки железа. Studio остаётся замороженной — она не нужна.
> **Ориентиры качества:** E2B (api-дизайн, DX), Modal (биллинг посекундно), Daytona (лайфцикл сессий).

---

## 0. TL;DR

| Что | Значение |
|---|---|
| Продукт | `POST /api/v1/sandboxes/` → изолированная microVM за 1–5 с → exec/files/logs/url |
| Аудитория | Разработчики AI-агентов, EdTech (проверка кода), интеграторы; РФ-компании без доступа к E2B/Modal |
| Инфра | Существующий `preview-service` + E2B (себестоимость ~0,20–0,25 ₽/мин за 2vCPU/2GiB) |
| Цена | 1 ₽/мин standard (2vCPU/2GiB), 0,5 ₽/мин small (1vCPU/1GiB), округление до минуты вверх |
| Объём работ | 3 спринта ≈ 2–3 недели (core → DX → hardening) |
| Kill-критерий | 60 дней после запуска: < 5 внешних ключей с реальным трафиком ≥ 30 мин → сворачиваем в maintenance |
| Studio | НЕ нужна, флаг `STUDIO_ENABLED` не трогаем. Нужен живой `preview-service` + `E2B_API_KEY` |

---

## 1. Продуктовая гипотеза и метрики эксперимента

**Гипотеза:** в РФ существует неудовлетворённый спрос на «исполнение кода как сервис»
(E2B/Modal недоступны: оплата картой, санкционные риски, 152-ФЗ), и aineron может
захватить эту нишу первым, потому что 80% инфраструктуры уже написано.

**Метрики успеха (60 дней после публичного запуска):**

| Метрика | Порог «продолжаем» | Порог «масштабируем» (своё железо) |
|---|---|---|
| Внешних API-ключей со скоупом `sandboxes` и ≥ 30 мин трафика | ≥ 5 | ≥ 30 |
| Оплаченных минут / месяц | ≥ 2 000 (≈ 2 000 ₽) | ≥ 40 000 (порог €80–100 E2B → FirecrackerRuntime) |
| Маржа (выручка − себестоимость E2B) | > 0 | > 60% |

**Kill-критерий:** ниже порога «продолжаем» → фича остаётся в API (кода мало, поддержка
дешёвая), но маркетинг и развитие останавливаются.

**Что НЕ делаем в эксперименте** (осознанно, до сигнала спроса):
- Своё железо (Kata/Firecracker) — только после порога «масштабируем».
- GPU-песочницы, кастомные Docker-образы пользователей, persistent volumes.
- Web-IDE / браузерный терминал (playground в `/api-docs/` достаточно).

---

## 2. Конкурентный ландшафт и позиционирование

| Сервис | Цена (2vCPU/2GiB) | Cold start | Доступен из РФ |
|---|---|---|---|
| E2B | ~$0.133/час | 1–5 с | Нет (карта, KYC) |
| Modal | ~$0.135/час CPU | 1–2 с | Нет |
| Daytona | ~$0.10/час | ~90 мс | Нет |
| Yandex Cloud Serverless | нет sandbox-SDK для агентов | — | Да, но не тот продукт |
| **Aineron Sandboxes** | **60 ₽/час (1 ₽/мин)** | 1–5 с (warm pool) | **Да, рубли, оферта РФ** |

Позиционирование: **«Песочницы для AI-агентов. Из России, за рубли, по одному API-ключу»**.
Ключевой сценарий в маркетинге — агентный цикл: LLM через `/chat/completions` пишет код →
`/sandboxes/{id}/exec/` его выполняет → результат возвращается в LLM. Обе половины цикла —
у нас, одним ключом. Ни один российский агрегатор нейросетей этого не даёт.

---

## 3. API-поверхность v1 (публичный контракт)

Все эндпоинты — под `/api/v1/`, авторизация `Authorization: Bearer <APIKey>`
(существующая `api.authentication`), скоуп `sandboxes`. Формат ошибок — единый с
остальным API (существующие `api.exceptions`). Все мутации принимают заголовок
`Idempotency-Key` (как у Stripe): повтор с тем же ключом возвращает первый результат.

### 3.1 Лайфцикл

```
POST   /api/v1/sandboxes/                     создать песочницу
GET    /api/v1/sandboxes/                     список активных (+ ?all=1 история)
GET    /api/v1/sandboxes/{sid}/               статус
POST   /api/v1/sandboxes/{sid}/timeout/       продлить/сократить TTL
DELETE /api/v1/sandboxes/{sid}/               остановить (kill) + финальный биллинг
```

**POST /sandboxes/** — запрос:
```json
{
  "template": "base",          // base | python | nodejs | nextjs | django
  "size": "standard",          // small (1vCPU/1GiB) | standard (2vCPU/2GiB)
  "timeout_seconds": 300,      // TTL, default 300, max 3600
  "env": {"MY_VAR": "..."},    // env-переменные внутри VM (не логируются)
  "metadata": {"run": "42"}    // произвольные теги клиента, вернутся в list
}
```
Ответ `201`:
```json
{
  "id": "sbx_9f3k2m...",
  "template": "base", "size": "standard",
  "state": "running",          // starting | running | stopped | expired | failed
  "public_host": "3000-sbx9f3k2m.e2b.dev",   // get_host, для веб-серверов
  "started_at": "2026-07-06T12:00:00Z",
  "expires_at": "2026-07-06T12:05:00Z",
  "price_kopecks_per_min": 100
}
```

### 3.2 Исполнение

```
POST /api/v1/sandboxes/{sid}/exec/
```
```json
{
  "command": "python -c \"print(2+2)\"",   // ЛИБО command, ЛИБО code+language
  "code": "print(2+2)",
  "language": "python",                     // python | bash | node
  "timeout_seconds": 60,                    // default 60, max 300
  "cwd": "/home/user"
}
```
Ответ:
```json
{
  "exit_code": 0,
  "stdout": "4\n",
  "stderr": "",
  "duration_ms": 312,
  "truncated": false            // stdout/stderr обрезаются на 256 KB
}
```
Синхронный вызов (держим HTTP до конца exec или таймаута). Для длинных процессов —
`"background": true` → возвращает `pid`, вывод забирается через `/logs/`.

### 3.3 Файлы

```
POST /api/v1/sandboxes/{sid}/files/         записать: [{"path": "...", "content": "..."}]
                                            (content utf-8; "encoding": "base64" для бинарных, ≤ 5 MB)
GET  /api/v1/sandboxes/{sid}/files/?path=   прочитать файл / листинг директории
```

### 3.4 Логи и наблюдаемость

```
GET /api/v1/sandboxes/{sid}/logs/           tail (?lines=100)
GET /api/v1/sandboxes/{sid}/logs/stream/    SSE (реюз паттерна E2BPreviewLogsStreamView)
```

### 3.5 Ограничения v1 (документируем честно)

- Egress: allowlist-политика preview-service (pypi, npm registry, api.telegram.org + расширения по запросу).
- Одновременно: 3 песочницы на ключ (small-тарифы), настраивается per-user.
- Без GPU, без снапшотов пользователю (pause/resume — внутренняя оптимизация), без кастомных образов.

---

## 4. Архитектура

```
Клиент (SDK / curl)
   │ Bearer APIKey (scope: sandboxes)
   ▼
Django DRF  /api/v1/sandboxes/*          ← новый тонкий слой (авторизация, биллинг, квоты, аудит)
   │ X-Internal-Token (существующий)
   ▼
preview-service (FastAPI)  /sandbox/*    ← НОВЫЙ namespace рядом с /preview/*
   │ e2b SDK
   ▼
E2B Firecracker microVM (warm pool L1–L7 реиспользуется)
```

**Ключевые решения:**

1. **Отдельный namespace `/sandbox/*` в preview-service**, а не реюз `/preview/start`.
   Причина: `/preview/start` заточен под «закинуть файлы проекта + поднять dev-сервер».
   Sandbox-режим — «голая VM из шаблона, ничего не запускать». Общий код (пул, клейм
   prewarm/paused/pool/cold, реапер, метрики) выносится в `E2BRuntime`, режимы различаются
   только bootstrap-шагом.
2. **Django-модель `SandboxSession`** (durable-запись) — источник истины для биллинга,
   истории и аудита. Redis — только оперативное состояние (как сейчас у превью).
3. **Биллинг по образцу превью**: `reserve()` на max-стоимость TTL при создании →
   `charge_from_reserve()` по факту при stop/expire → `release_reserve_amount()` остатка.
   Reference идемпотентности: `sandbox:{sid}` (паттерн `preview:{session_id}` из
   `src/studio/views/pipeline.py:922`). Reconcile-задача добивает зависшие сессии.
4. **Никакой зависимости от `studio.*`**: биллинг-хелперы, которые сейчас живут в
   `src/studio/billing.py`, для песочниц реализуются через `CustomUser.spend_kopecks`/
   `add_kopecks` напрямую (они уже идемпотентны по `(type, reference)`) — Studio-флаг
   выключен и импортировать её код не нужно.

### 4.1 Новые компоненты

| Файл | Что |
|---|---|
| `src/sandboxes/` (новое Django-app) | `models.py` (SandboxSession), `billing.py`, `quotas.py`, `tasks.py` (reconcile) |
| `src/api/views/sandboxes.py` | DRF-views: Create/List/Detail/Exec/Files/Logs/Delete |
| `src/api/serializers/sandboxes.py` | Сериализаторы + валидация (path traversal, размеры) |
| `preview-service/main.py` | `/sandbox/create`, `/sandbox/{sid}/exec`, `/sandbox/{sid}/files`, `/sandbox/{sid}/logs`, `/sandbox/{sid}` DELETE |
| `preview-service/runtime/e2b_runtime.py` | `create_bare()`, `exec()`, `write_files()`, `read_file()` — поверх готового `sbx.commands.run` |
| `frontend/app/api-docs/` | раздел Sandboxes + примеры + playground-вкладка |
| `frontend/app/sandbox/page.tsx` | SSG-лендинг (SEO: «песочница для кода API», «E2B аналог Россия») |
| `sdk/python/` | пакет `aineron` на PyPI (см. §6) |

### 4.2 Модель `SandboxSession`

```python
class SandboxSession(models.Model):
    id            = UUID (pk)                 # sbx_… наружу
    user          = FK(CustomUser)
    api_key       = FK(api.APIKey, null=True) # каким ключом создана
    template      = CharField                 # base/python/nodejs/nextjs/django
    size          = CharField                 # small/standard
    state         = CharField                 # starting/running/stopped/expired/failed
    e2b_sandbox_id= CharField                 # внутренний, наружу НЕ отдаём
    public_host   = CharField
    started_at / stopped_at / expires_at
    reserved_kopecks / charged_kopecks
    exec_count    = IntegerField(default=0)   # для аналитики и abuse-детекта
    metadata      = JSONField
```

---

## 5. Биллинг и тарифы

Себестоимость E2B: $0.0504/vCPU-час + $0.0162/GiB-час.

| Тариф | Конфиг | Себестоимость | Цена | Маржа |
|---|---|---|---|---|
| small | 1vCPU / 1GiB | ≈ 0,10–0,12 ₽/мин | **0,5 ₽/мин** (50 коп.) | ~75% |
| standard | 2vCPU / 2GiB | ≈ 0,20–0,25 ₽/мин | **1 ₽/мин** (100 коп.) | ~75% |

- Тарификация: округление до полной минуты **вверх**, минимум 1 минута за сессию.
  (Посекундный биллинг — маркетинг-обещание фазы 2; для v1 минута проще и честна при TTL ≥ 5 мин.)
- Хранение цен: `settings.SANDBOX_PRICE_KOPECKS = {'small': 50, 'standard': 100}` (env-переопределяемо).
- Резерв при создании: `ceil(timeout/60) * price` копеек; недостаточно баланса → `402` с
  телом в формате остального API. Продление TTL — доп. резерв.
- Дневной кап минут на пользователя — реюз механики `preview:daily_min:{uid}:{date}`
  (`_check_and_reserve_daily_cap`), отдельный env `SANDBOX_DAILY_CAP_MIN=240`, ответ `429`.
- Бесплатный старт: стартовые 10 ₽ нового пользователя = 10 минут standard — достаточно
  для «hello world» из документации без ввода карты. Отдельный free-tier НЕ вводим (abuse).
- Все списания — через `spend_kopecks/add_kopecks` с `reference` (идемпотентность к ретраям).
- `reconcile_sandbox_billing` (Celery beat, каждые 5 мин): сессии с `state=running` и
  истёкшим `expires_at` → опросить preview-service → дочислить/вернуть → закрыть.
  Паттерн уже отработан на `reconcile_preview_billing`.

---

## 6. DX — то, что отличает топ-1 от «просто эндпоинта»

Стандарт качества: разработчик от регистрации до первого `4` в stdout — **< 5 минут**.

### 6.1 Python SDK (`pip install aineron`)

```python
from aineron import Sandbox

with Sandbox(template="python") as sbx:          # ключ из env AINERON_API_KEY
    result = sbx.exec(code="print(2+2)")
    print(result.stdout)                          # "4"
    sbx.write_file("data.csv", csv_bytes)
```

- Контекст-менеджер (гарантированный kill → нет утечки минут), ретраи с backoff,
  типизация, `sbx.url(port)` для веб-серверов.
- JS/TS SDK — фаза 2 (после первых пользователей); до этого — curl/fetch-примеры в доках.

### 6.2 Документация (`/api-docs/`, раздел Sandboxes)

- Quickstart: 3 шага, curl + Python, копируемые блоки.
- **Главный туториал: «AI-агент, который пишет и выполняет код»** — полный цикл
  `/chat/completions` (tool use) + `/sandboxes/exec` на нашем же API. Это одновременно
  документация, демо синергии и SEO-статья.
- Референс каждого эндпоинта: запрос/ответ/ошибки/лимиты. Честная страница ограничений (§3.5).
- Playground: вкладка в существующем `/api-docs/playground/` — создать sandbox → выполнить
  сниппет → увидеть stdout (работает на своём ключе пользователя, тратит его баланс).

### 6.3 Контент-запуск

- Лендинг `/sandbox/` (SSG): hero с живым примером кода, таблица цен, сравнение с E2B
  («из России, за рубли»), FAQ + JSON-LD.
- 2–3 статьи в блог через существующую контент-машину: «Как безопасно выполнять код,
  который пишет LLM», «Песочницы для AI-агентов: обзор и пример на Python».
- Хабр-пост после стабилизации (ручной, не AI — аудитория чувствительна).

---

## 7. Безопасность и анти-abuse (критично: дешёвый compute притягивает майнеров)

| Угроза | Мера |
|---|---|
| Побег из песочницы | Уже решено: E2B Firecracker microVM, отдельное ядро; наш Django-процесс изолирован (preview-service — отдельный сервис, паттерн сохраняем) |
| Майнинг | TTL max 3600 c жёстким reaper'ом; small/standard без GPU невыгодны майнеру; метрика: сессии с CPU-bound exec > 10 мин подряд → флаг в админку |
| Прокси/спам через egress | Egress-allowlist preview-service остаётся по умолчанию; расширение доменов — по заявке (поле в форме поддержки), лог исходящих доменов |
| Абьюз бесплатных 10 ₽ | Существующий ShadowBan по IP + скоуп `sandboxes` НЕ входит в дефолтные скоупы нового ключа — включается явно в `/account/keys/` |
| Утечка секретов | `env` клиента не пишется в логи; `e2b_sandbox_id` наружу не отдаём; `Idempotency-Key` ответы храним без тел env |
| Path traversal в files | Валидация: абсолютные пути только под `/home/user`, `..` запрещён |
| Флуд exec | Rate limit: 30 exec/мин на песочницу, 10 создания/мин на ключ (существующий `api.throttling`) |
| Финансовые дыры | Резерв ДО создания VM; reconcile каждые 5 мин; дневной кап; alert при `sum(running) * rate > X ₽/час` |

Аудит: каждое создание/удаление песочницы — запись в существующий audit log (`/api/v1/audit`).

---

## 8. План работ по спринтам (детально, «бери и делай»)

Порядок жёсткий: каждый спринт заканчивается работающим, проверенным руками результатом.
Внутри спринта задачи идут в порядке зависимостей — можно выполнять последовательно сверху вниз.

---

### Sprint SB-1 — Runtime-ядро в preview-service (2–3 дня) — ✅ CODE-COMPLETE 2026-07-06

**Результат:** `curl` с внутренним токеном может создать голую VM, записать файл,
выполнить код, прочитать логи и убить сессию. Django ещё не тронут.

#### SB-1.1 Методы в `preview-service/runtime/e2b_runtime.py`

- [ ] `create_bare(template: str, size: str, ttl: int, env: dict) -> tuple[str, str]`
      — возвращает `(sandbox_id, public_host)`. Внутри: реюз существующего клейма
      prewarm/pool/cold (тот же порядок, что в `start()`), но **без** вызова `_bg_start`
      — VM остаётся «пустой». `size` мапится на `Sandbox.create(..., cpu_count, memory_mb)`
      (small=1/1024, standard=2/2048). `template` → существующие `E2B_TEMPLATE_*`,
      `base` → дефолтный образ e2b.
- [ ] `exec(sandbox_id, command: str, timeout: int, cwd: str, background: bool) -> ExecResult`
      — обёртка над `sbx.commands.run(cmd, timeout=timeout, cwd=cwd)`; уже используется
      в 6 местах файла, риск нулевой. `ExecResult = {exit_code, stdout, stderr, duration_ms,
      truncated}`. Trancate stdout/stderr на `OUTPUT_LIMIT_KB` (по умолчанию 256).
      `background=True` → паттерн `setsid bash -c '... >> /tmp/sandbox.log 2>&1' &`
      (готовый шаблон — `_bg_start_python`, строка 181).
- [ ] `write_files(sandbox_id, files: list[{path, content, encoding}])` — реюз
      `sbx.files.write` (см. строку 141). base64-decode при `encoding=base64`.
      Валидация пути здесь НЕ нужна (делается в Django-слое), но пути нормализуем.
- [ ] `read_file(sandbox_id, path) -> {content, encoding}` / `list_dir(sandbox_id, path)` —
      `sbx.files.read` + `sbx.commands.run("ls -la ...")`.
- [ ] `kill(sandbox_id)` — `Sandbox.connect(...).kill()`; идемпотентно (уже мёртвая VM → ok).

#### SB-1.2 Namespace `/sandbox/*` в `preview-service/main.py`

Все — под `Depends(verify_token)` (существующий). Redis-ключи по образцу превью:

```
sandbox:session:{sid}   → JSON {e2b_id, template, size, expires_at, user_id}  TTL = ttl+120
sandbox:user:{uid}      → счётчик активных (INCR-first паттерн, функция _try_acquire_user_slot уже есть)
```

- [ ] `POST /sandbox/create` — body `{template, size, ttl, env, user_id}` →
      `create_bare()` → записать сессию в Redis → `{sid, e2b_id, public_host, expires_at}`.
      Латентность писать в существующий `_record_latency` (общие метрики p95).
- [ ] `POST /sandbox/{sid}/exec` — прочитать сессию из Redis (404 если нет) → `exec()`.
- [ ] `POST /sandbox/{sid}/files` / `GET /sandbox/{sid}/files?path=` — write/read/list.
- [ ] `GET /sandbox/{sid}/logs?lines=` — `tail /tmp/sandbox.log` (паттерн строки 283).
- [ ] `DELETE /sandbox/{sid}` — `kill()` + удалить Redis-ключ + декремент слота →
      `{ok, duration_seconds, started_at}` (как `StopResponse`) — Django посчитает деньги.
- [ ] Реапер: расширить существующий реапер превью — сканировать и `sandbox:session:*`
      с истёкшим `expires_at` → kill. (Не отдельный процесс — та же петля.)

#### SB-1.3 Критерии приёмки SB-1

- [ ] Скрипт `preview-service/spikes/sandbox_smoke.py`: create(base) → write(main.py) →
      exec(`python main.py`) → stdout == ожидаемому → logs → delete. Проходит < 15 с.
- [ ] exec с `timeout=2` на `sleep 10` → корректная ошибка таймаута, VM жива.
- [ ] DELETE дважды подряд → оба раза 200 (идемпотентность).
- [ ] `/metrics` показывает латентность sandbox-стартов.

---

### Sprint SB-2 — Django-слой: биллинг, квоты, публичный API (2–3 дня) — ✅ CODE-COMPLETE 2026-07-06 (36 тестов OK)

**Результат:** внешний запрос с Bearer APIKey проходит весь путь; деньги списываются
корректно во всех сценариях. Флаг `SANDBOX_API_ENABLED` ещё = 0 (тестим на стейдже/локально).

#### SB-2.1 Django-app `src/sandboxes/`

- [ ] `models.py` — `SandboxSession` (поля из §4.2) + миграция.
- [ ] `client.py` — HTTP-клиент к preview-service (base URL + `X-Internal-Token`,
      таймауты, 3 ретрая на сетевые ошибки; паттерн взять из существующего вызова
      preview-service в `src/studio/views/pipeline.py`).
- [ ] `billing.py` — три функции на `CustomUser.spend_kopecks/add_kopecks`
      (БЕЗ импорта `studio.billing` — Studio заморожена):
      ```python
      reserve(user, session) -> bool        # spend_kopecks(ceil(ttl/60)*price, 'sandbox_reserve', f'sandbox:{sid}:reserve')
      settle(session, duration_sec)         # факт: charged = ceil(dur/60)*price; вернуть разницу add_kopecks(..., 'refund', f'sandbox:{sid}:settle')
      refund_full(session)                  # ошибка старта → вернуть весь резерв
      ```
      Все reference — идемпотентны (повтор Celery не задвоит).
- [ ] `quotas.py` — `check_daily_cap(user, ttl_min)` (копия `_check_and_reserve_daily_cap`
      из `pipeline.py:42` с ключом `sandbox:daily_min:{uid}:{date}`) +
      `check_concurrent(user)` (COUNT активных `SandboxSession`).
- [ ] `tasks.py` — `reconcile_sandbox_billing()` (beat, */5 мин): `state=running` и
      `expires_at < now` → спросить preview-service → `settle()` → `state=expired`.
      Регистрация — как у существующих beat-задач.

#### SB-2.2 DRF-слой `src/api/`

- [ ] `serializers/sandboxes.py` — Create/Exec/Files сериализаторы. Валидация:
      `path` начинается с `/home/user` или относительный без `..`; `content` ≤ 5 MB;
      `ttl` ∈ [60, SANDBOX_MAX_TTL]; `env`-ключи `^[A-Z_][A-Z0-9_]*$`.
- [ ] `views/sandboxes.py` — семь view (§3), общий базовый класс:
      auth (существующие JWT+APIKey классы) → проверка скоупа `sandboxes` → флаг
      `SANDBOX_API_ENABLED` (иначе 404) → shadow_banned → квоты. Порядок в Create:
      **квоты → reserve → preview-service create → SandboxSession(running)**;
      при ошибке create — `refund_full` (паттерн `release_reserve_amount` в
      `pipeline.py:859-878`). В Delete: preview-service DELETE → `settle(duration)`.
- [ ] Idempotency-Key: Redis `idem:{key_hash}:{user_id}` → сохранённый ответ, TTL 24 ч.
      Только POST create / DELETE (exec не идемпотентен по природе — документируем).
- [ ] `urls.py` — блок `v1/sandboxes/` (7 маршрутов из §3).
- [ ] Throttling: `SandboxCreateThrottle` (10/мин), `SandboxExecThrottle` (30/мин на sid)
      в существующем `api/throttling.py`.
- [ ] Скоуп: добавить `sandboxes` в список скоупов APIKey; НЕ включать в дефолтные.
- [ ] Audit: записи `sandbox.create` / `sandbox.delete` в существующий audit log.

#### SB-2.3 Тесты `src/sandboxes/tests.py` + `src/api/tests_sandboxes.py`

- [ ] Биллинг: резерв → settle меньшей длительности → разница вернулась; повтор settle —
      без двойного возврата; refund_full после падения create.
- [ ] 402 при нехватке баланса, 429 при капе/конкурrenci, 403 без скоупа, 404 при флаге=0.
- [ ] Path traversal (`../../etc/passwd`) → 400. env-инъекция (`FOO=x; rm`) → 400.
- [ ] Reconcile закрывает подвешенную сессию и дочисляет верно.
- [ ] Mock preview-service (responses/requests-mock) — весь happy path create→exec→delete.

#### SB-2.4 Критерии приёмки SB-2

- [ ] `python manage.py test sandboxes api` — зелёный.
- [ ] Ручной curl-прогон с реальным APIKey на стейдже: create → files → exec → logs →
      delete; в админке `BalanceTransaction` ровно 2 записи (reserve, settle-refund) с
      правильными суммами.
- [ ] Убить preview-service между create и delete → reconcile возвращает деньги.

---

### Sprint SB-3 — DX: SDK, доки, playground, лендинг (3–4 дня) — ✅ CODE-COMPLETE 2026-07-06 (PyPI-публикация — при запуске)

**Результат:** незнакомый разработчик проходит путь «регистрация → первый stdout» за < 5 минут.

- [ ] **Python SDK** `sdk/python/` — пакет `aineron`: класс `Sandbox` (контекст-менеджер
      с гарантированным kill в `__exit__`), `exec/write_file/read_file/url`, ретраи с
      backoff на 5xx, ключ из `AINERON_API_KEY`. `pyproject.toml`, README с примерами,
      публикация на PyPI. Тесты SDK — на responses-mock, без сети.
- [ ] **Docs** `/api-docs/`: раздел Sandboxes — quickstart (curl + Python, 3 шага),
      референс всех эндпоинтов (взять структуру существующих разделов chat/images),
      страница лимитов и ошибок (§3.5, §7).
- [ ] **Туториал** «AI-агент, который пишет и выполняет код»: полный цикл
      `/chat/completions` (tool use) + `/sandboxes/exec` — отдельная страница в доках,
      код целиком копируемый.
- [ ] **Playground**: вкладка Sandboxes в `/api-docs/playground/` — textarea кода →
      create(small, ttl=120) → exec → stdout → авто-delete. Работает на ключе пользователя.
- [ ] **Лендинг** `/sandbox/` (SSG): hero с живым сниппетом, таблица цен (§5), сравнение
      с E2B, FAQ + JSON-LD (FAQPage), в sitemap. Иконки — только Lucide, без эмодзи.
- [ ] **UI ключей** `/account/keys/`: чекбокс скоупа `sandboxes` (выкл. по умолчанию) + подсказка.
- [ ] Строка «Sandboxes» в каталог возможностей API (там, где перечислены chat/images/audio).

**Приёмка:** попросить человека, не видевшего проект, пройти quickstart с таймером.

---

### Sprint SB-4 — Hardening и запуск (2–3 дня) — ✅ CODE-COMPLETE 2026-07-06 (сам запуск — по чеклисту §10 после разблокировки E2B)

**Результат:** `SANDBOX_API_ENABLED=1` в проде, метрики и алерты живые.

- [ ] SSE-стрим логов `GET /sandboxes/{sid}/logs/stream/` — реюз паттерна
      `E2BPreviewLogsStreamView` + `/preview/{id}/logs/stream` (уже написаны).
- [ ] Админка: список `SandboxSession` (фильтр по state/user), action «Kill»
      (зовёт preview-service DELETE + settle).
- [ ] Abuse: колонка `exec_count`; Celery-проверка «running > 20 мин и exec_count > 50»
      → пометка + письмо админу. Egress-лог доменов в лог-файл.
- [ ] `/status/`: блок Sandboxes — p95 старта, активные сессии (данные из `/metrics`
      preview-service — эндпоинт готов).
- [ ] `/account/analytics/`: траты `sandbox_*` отдельной категорией (тип транзакции уже
      различим по `type`).
- [ ] Алерт: beat-задача — если `COUNT(running) * price > SANDBOX_RUNRATE_ALERT_RUB/час`
      → email админу.
- [ ] Прогнать чеклист §10 целиком → `SANDBOX_API_ENABLED=1` → анонс (блог ×2 через
      контент-машину, телеграм-канал).

---

### Sprint SB-5 — условный (только при пороге «масштабируем», см. §1)

- [ ] JS/TS SDK (`@aineron/sdk`).
- [ ] Посекундный биллинг + pause/resume наружу (внутри уже есть — L5).
- [ ] Выделенный сервер (bare-metal, KVM) + Kata Containers → реализация
      `FirecrackerRuntime`-шва из `preview-service/runtime/base.py`; E2B остаётся
      fallback'ом (двойной runtime = наш SLA-аргумент).
- [ ] B2B: выделенные лимиты, договор, 152-ФЗ (данные и логи в РФ на своём железе).

---

### Сводка объёма

| Спринт | Дней | Новых файлов | Изменяемых файлов | Риск |
|---|---|---|---|---|
| SB-1 runtime | 2–3 | 1 (smoke) | 2 (`e2b_runtime.py`, `main.py`) | низкий — все примитивы e2b уже используются |
| SB-2 Django | 2–3 | ~7 (`src/sandboxes/*`, views, serializers, тесты) | 3 (`urls.py`, `throttling.py`, settings) | средний — биллинг, покрыть тестами |
| SB-3 DX | 3–4 | ~6 (SDK, доки, лендинг) | 2 (playground, keys UI) | низкий |
| SB-4 запуск | 2–3 | 0–2 | ~5 | низкий |
| **Итого до прода** | **≈ 10–13 дней** | | | |

---

## 9. Конфигурация (`.env` — новые переменные)

```
SANDBOX_API_ENABLED=0            # мастер-флаг: 404 на /api/v1/sandboxes/ пока 0
SANDBOX_PRICE_SMALL_KOPECKS=50
SANDBOX_PRICE_STANDARD_KOPECKS=100
SANDBOX_DAILY_CAP_MIN=240        # минут/день на пользователя
SANDBOX_MAX_CONCURRENT_PER_USER=3
SANDBOX_DEFAULT_TTL=300
SANDBOX_MAX_TTL=3600
SANDBOX_EXEC_TIMEOUT_MAX=300
SANDBOX_OUTPUT_LIMIT_KB=256
```

Существующие обязательные: `E2B_API_KEY`, `PREVIEW_INTERNAL_TOKEN`, `E2B_TEMPLATE_*`
(собрать шаблоны — иначе cold start 30–60 с и продукт мёртв на старте).

---

## 10. Чеклист перед публичным запуском

- [ ] **Разблокировать E2B-аккаунт** (добавить платёжный метод — сейчас 403
      «team is blocked») и поднять сервис: `docker-compose --profile studio up -d preview_service`.
- [ ] `E2B_API_KEY` активен, шаблоны собраны, warm pool греется (`/pool/stats`).
- [ ] Smoke-прогон: `python preview-service/spikes/sandbox_smoke.py` — зелёный, < 15 с.
- [ ] Прогнать миграции: `0001_initial` (sandboxes), `0006` (api), users (тип sandbox).
- [ ] Опубликовать SDK: `cd sdk/python && python -m build && twine upload dist/*`.
- [ ] p95 create→running < 5 с на standard (замер через `/metrics`).
- [ ] Биллинг сверен вручную: 3 сценария (нормальный stop, expire, kill во время exec) —
      списания совпадают с минутами в `BalanceTransaction`.
- [ ] Reconcile добивает искусственно подвешенную сессию.
- [ ] Дневной кап и 402 при нуле баланса срабатывают.
- [ ] ShadowBan-пользователь не может создать песочницу.
- [ ] Docs quickstart проходится «с чистого листа» за < 5 минут (проверить руками).
- [ ] Алерт на run-rate настроен.
- [ ] `SANDBOX_API_ENABLED=1` — последним шагом.

---

## 11. Риски

| Риск | Вероятность | Митигация |
|---|---|---|
| Спроса в РФ нет | Средняя–высокая | Формат эксперимента: kill-критерий §1, вложения ≈ 2–3 недели, код остаётся полезным (Studio-превью использует то же ядро) |
| E2B заблокирует/поднимет цены | Средняя | ABC-шов `Runtime` уже в коде; Kata/Firecracker-план готов (§8 SB-4); маржа 75% выдерживает ×2 рост себестоимости |
| Майнеры/абьюз | Высокая при росте | §7: капы, TTL, скоуп не по умолчанию, ShadowBan, метрики CPU-bound |
| Расход E2B без выручки | Низкая | Резерв до старта VM + дневной кап + алерт run-rate: платим только за оплаченные минуты |
| Latency из РФ до E2B (US/EU) | Средняя | Честный ETA в ответе create (паттерн `eta_seconds` уже есть); при жалобах — аргумент за SB-4 (железо в РФ) |
