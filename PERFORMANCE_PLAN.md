# PERFORMANCE_PLAN.md — скорость и стабильность продакшена

Цель: стабильная работа при 500+ одновременных пользователях.
Сервер (Beget): 2 ядра CPU / 4 ГБ RAM / 80 ГБ NVMe. **Подана заявка на апгрейд до 8 ядер.**

---

## ЧТО СДЕЛАНО (июль 2026)

### 1. Чат-SSE переведён на Daphne (коммит `341aa8e`)
**Проблема:** стриминг чата (`/api/v1/chats/{id}/messages/stream/`) шёл через общий
`location /api/` на Gunicorn. Каждый активный стрим держал один из 16 sync-слотов
до конца генерации → при ~16 параллельных чатах ВСЁ API зависало (Проекты, Арена,
`/status` показывал «Неизвестно»).
**Решение:** отдельный location в nginx → Daphne (тот же паттерн, что Studio events),
`proxy_read_timeout 3600s`, буферизация выключена.

### 2. Gunicorn пересобран под железо (2 ядра / 4 ГБ)
Было: `--workers 8 --threads 2` (16 слотов, ~1.5–2 ГБ RAM, таймаут 30с дефолтный).
Стало: `--workers 3 --threads 12 --timeout 300 --max-requests 500 --max-requests-jitter 50`:
- 36 слотов при ~3× меньшей памяти (I/O-bound нагрузка → потоки эффективнее процессов);
- `--timeout 300` выровнен с nginx `proxy_read_timeout 300s` (раньше воркеры убивались на 30с);
- `--max-requests 500` — перезапуск воркера, утечки памяти не накапливаются.
**После апгрейда до 8 ядер:** поднять до `--workers 5 --threads 12`.

### 3. Celery concurrency 200 → 50
200 gevent-гринлетов могли разом открыть 200 соединений к Postgres при лимите
`max_connections=100` → «FATAL: too many connections» и падение всего.
50 параллельных задач для текущей нагрузки достаточно.

### 4. gzip в nginx
Не был включён вообще — JSON API и JS-бандлы летели несжатыми.
Включён `gzip_comp_level 5` для JSON/JS/CSS/SVG (3–5× меньше трафика).

### 5. Redis-кэш тяжёлых публичных GET (TTL 60 сек)
- `/api/v1/catalog/networks/` (ключ учитывает фильтры category/provider/is_popular/is_free)
- `/api/v1/catalog/categories/`
- `/api/v1/arena/leaderboard/` (+ сброс кэша при голосовании)
Каталог дёргается каждым юзером на каждой странице чата/сравнения — теперь 1 запрос
к БД в минуту вместо сотен.

### 6. Studio-сервисы отключены (заморозка Studio, коммит `12e4203`)
`preview_service` (спамил E2B 403 «team is blocked») и `celery_studio` спрятаны за
`profiles: ["studio"]` — освобождена RAM. Вернуть: `docker-compose --profile studio up -d`.
Gitea оставлена (нужна для синхронизации Проектов).

---

## ЧТО НУЖНО СДЕЛАТЬ

### Срочно (до/сразу после запуска платежей)
- [ ] **Пополнить баланс Beget** (оставалось 9 дней на 2026-07-06!)
- [ ] **Апгрейд сервера** — заявка на 8 ядер подана; RAM тоже критична: 4 ГБ уже
      занято на ~75% в простое. Минимум 8 ГБ RAM.
- [ ] После апгрейда: gunicorn `--workers 5 --threads 12` (docker-compose.yml)
- [ ] **Бэкапы БД** — критично с платежами (потеря БД = потеря балансов юзеров):
      cron с `docker-compose exec -T db pg_dump -U neiro_user neiro_db | gzip` +
      выгрузка в объектное хранилище Beget (S3). Хранить 7–14 дней.
- [ ] **Мониторинг аптайма**: бесплатный UptimeRobot на
      `https://aineron.ru/api/v1/status/` (алерт в Telegram при падении) +
      правило мониторинга в панели Beget (CPU/RAM/диск).

### Средний приоритет (при росте нагрузки)
- [ ] Долгие sync-эндпоинты увести с Gunicorn (сейчас блокируют слоты на секунды–минуты):
      - `/api/v1/images/compare/` — ждёт генерацию картинок синхронно
      - `/api/v1/audio/speech` и `/api/v1/audio/transcriptions` — ждут ответ провайдера
      Паттерн: Celery-задача + polling статуса (как в чате) или перевод на Daphne.
- [ ] `CONN_MAX_AGE` для web (60 сек) — переиспользование соединений к Postgres
      (сейчас новое соединение на каждый запрос). Только для web, НЕ для celery-gevent.
- [ ] Swap-файл 2–4 ГБ на сервере как страховка от OOM:
      `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`
- [ ] Кэш `/api/v1/blog/posts/` (60–300 сек) — если блог начнёт получать трафик из SEO.
- [ ] `docker-compose logs` ротация: добавить `logging: {driver: json-file, options: {max-size: "50m", max-file: "3"}}`
      сервисам web/celery/frontend — иначе логи съедят диск.

### При масштабировании (1000+ юзеров)
- [ ] Postgres → управляемая «Облачная БД» Beget (снимет RAM-давление и вопрос бэкапов)
- [ ] PgBouncer перед Postgres (пулинг соединений)
- [ ] CDN Beget для `/media/` (сгенерированные картинки/видео — самый тяжёлый трафик)
- [ ] Реплика: второй app-сервер за балансировщиком (Postgres/Redis выносятся первыми)
- [ ] Тюнинг Postgres под RAM: `shared_buffers=25% RAM`, `effective_cache_size=50% RAM`

---

## Диагностика при проблемах

| Симптом | Что смотреть |
|---|---|
| API виснет | `docker-compose logs --tail=50 web` — ищи `WORKER TIMEOUT`; `docker stats` — RAM |
| Всё «Неизвестно» на /status | фронт не дождался API → слоты Gunicorn забиты или web упал |
| «too many connections» в логах | Postgres достиг max_connections → снизить celery concurrency / добавить PgBouncer |
| Контейнер внезапно перезапустился | `dmesg | grep -i oom` — OOM-killer, не хватает RAM |
| Стриминг чата оборвался | `docker-compose logs --tail=50 daphne` (SSE чата живёт на Daphne с 341aa8e) |

## Архитектурный принцип
Django остаётся синхронным — это нормально. Правило: **быстрые запросы — Gunicorn,
долгоживущие (SSE/стримы) — Daphne, тяжёлая работа — Celery + polling.**
Новый долгий эндпоинт НЕ должен попадать в общий `location /api/` без Celery.
