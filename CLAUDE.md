# aineron.ru — CLAUDE.md

## Что это за проект

SaaS-платформа для доступа к AI-нейросетям без VPN. Пользователи покупают «звёзды» (внутреннюю валюту) и тратят их на каждое сообщение к нейросети. Поддерживает текстовые LLM, генерацию изображений и видео — всё через единый провайдер **api.laozhang.ai**.

Домен: **aineron.ru** | Язык интерфейса: **русский**

Архитектура — это разделённый стек: **Django (DRF API + Admin)** на бэкенде и **Next.js 14 (App Router)** на фронтенде. Это уже не план миграции, а текущая рабочая реальность: фронтенд полностью развёрнут в папке `frontend/`, Django переведён в режим API-сервера (`/api/v1/`).

---

## Стек технологий

### Backend

| Слой | Технология |
|------|-----------|
| Backend | Django 4.2, Python 3.11 |
| API | Django REST Framework (`/api/v1/`, OpenAI-совместимые эндпоинты) |
| Task queue | Celery 5.6 + Redis 7 |
| Database | PostgreSQL 15 (SQLite только для тестов) |
| Auth (web) | django-allauth 65 (Google, Yandex, VK, Mail.ru + email/password) |
| Auth (API) | JWT (djangorestframework-simplejwt) + APIKey (для внешних запросов) |
| CORS | django-cors-headers |
| AI — текст | laozhang.ai (openai SDK, base_url: api.laozhang.ai/v1) |
| AI — изображения | laozhang.ai (openai SDK, images.generate API) |
| AI — видео | laozhang.ai (Veo/Sora `/v1/videos`, Seedance отдельный endpoint) |
| Веб-поиск | Tavily API |
| Платежи | Robokassa (recurring через POST /Merchant/Recurring) |
| WSGI | Gunicorn (8 workers, 2 threads) |
| Celery pool | gevent, concurrency 200 |

### Frontend

| Слой | Технология |
|------|-----------|
| Framework | Next.js 14 App Router |
| Язык | TypeScript |
| Стейт | Zustand |
| Запросы | TanStack Query (React Query v5) |
| Стили | Tailwind CSS v4 |
| Иконки | **Lucide React** (только этот набор, без эмодзи) |
| Markdown | react-markdown + rehype-highlight + remark-gfm |
| PWA | next-pwa (manifest + service worker) |
| Голос | Web Speech API + Whisper ASR / TTS через `/api/v1/audio/*` |
| SSE | EventSource (real-time streaming текстовых ответов) |
| Расположение | `frontend/` в корне репозитория |

### Деплой

| Слой | Технология |
|------|-----------|
| Деплой | Docker Compose (7 сервисов) |
| Reverse proxy | Nginx (SSL termination, роутинг между Next.js и Django) |

---

## Структура папок

```
aineron.ru/
├── src/                        # Весь Python/Django-код
│   ├── config/                 # Настройки Django, Celery, URLs
│   │   ├── settings.py         # Все настройки (из env-переменных)
│   │   ├── celery.py
│   │   └── urls.py             # Корневые URLs
│   ├── users/                  # Пользователи, тарифы, платежи, рефералы
│   ├── aitext/                 # Нейросети, чаты, сообщения, файлы, видео
│   ├── api/                    # DRF API-слой (/api/v1/), OpenAI-совместимый
│   ├── teams/                  # B2B: организации, члены, оргбиллинг
│   ├── blog/                   # Статьи и категории блога
│   ├── landing/                # Старый лендинг (legacy), 404-обработчик
│   ├── static/neuro/           # Legacy JS и CSS (до Next.js)
│   ├── templates/neuro/        # Legacy HTML-шаблоны + admin/API-docs
│   ├── media/                  # Загруженные и сгенерированные файлы
│   └── requirements.txt
├── frontend/                   # Next.js 14 App Router (основной фронт)
│   ├── app/                    # Маршруты (App Router)
│   │   ├── page.tsx            # Лендинг (/)
│   │   ├── models/             # Каталог нейросетей + [slug]
│   │   ├── chat/               # Чат [networkSlug]
│   │   ├── account/            # Кабинет: keys, analytics, billing, referral, files
│   │   ├── compare/            # Model Arena (сравнение моделей)
│   │   ├── projects/           # Projects (папки чатов)
│   │   ├── prompts/            # Библиотека промтов
│   │   ├── welcome/            # Онбординг-wizard
│   │   ├── blog/               # Блог (SSR + ISR)
│   │   ├── api-docs/           # Документация API + playground
│   │   ├── status/             # Статус-страница
│   │   ├── (auth)/             # Группа авторизации
│   │   ├── (dashboard)/        # Группа дашборда (B2B)
│   │   ├── manifest.ts         # PWA manifest
│   │   ├── sitemap.ts          # Sitemap
│   │   ├── robots.ts           # robots.txt
│   │   ├── providers.tsx       # React Query / Zustand провайдеры
│   │   └── layout.tsx          # Корневой layout
│   ├── components/             # analytics, chat, docs, landing, layout, ui, PWAProvider
│   ├── lib/                    # api (клиент), stores (Zustand), utils.ts
│   ├── middleware.ts           # Next.js middleware (auth-редиректы)
│   ├── public/                 # Статика, manifest.json, иконки
│   ├── next.config.mjs
│   ├── tailwind / postcss config
│   └── package.json
├── docker-compose.yml          # 7 сервисов: redis, db, web, celery_worker, celery_beat, frontend, nginx
├── Dockerfile                  # Backend: FROM python:3.11-slim
├── Dockerfile.frontend         # Frontend: Next.js build
├── nginx.conf                  # SSL termination, роутинг Next.js / Django / media
├── deploy.sh                   # Скрипт деплоя
├── COMPETITIVE_PLAN.md         # Конкурентная стратегия (Sprint 1/2/3)
├── TELEGRAM_BOT_PLAN.md        # План Telegram-бота (НЕ реализован)
├── PERSISTENT_MEMORY_PLAN.md   # План Persistent Memory (НЕ реализован)
└── .env                        # Секреты (не коммитить)
```

---

## Nginx-роутинг (production)

```
/        → Next.js   (frontend:3000)   — лендинг, каталог, чат, кабинет и т.д.
/api/    → Django    (web:8000)        — DRF API
/admin/  → Django    (web:8000)        — Django Admin (НЕ мигрируется)
/media/  → static files напрямую       — загруженные и сгенерированные файлы
/static/ → static files напрямую       — collectstatic Django (admin, legacy)
```

Nginx делает SSL termination, сертификаты: `./ssl/fullchain.pem` и `./ssl/privkey.pem`.

---

## Маршруты Next.js (frontend/app)

| Путь | Тип рендеринга | Назначение |
|------|----------------|------------|
| `/` | SSG | Лендинг 2.0 (hero, social proof, comparison, use cases, pricing) |
| `/models/` | SSR | Каталог нейросетей (SEO) |
| `/models/[slug]/` | SSR | Детальная страница модели + JSON-LD |
| `/chat/[networkSlug]/` | Client | Чат (polling статуса + SSE streaming) |
| `/account/` | Client | Кабинет: баланс, тарифы, история |
| `/account/keys/` | Client | API-ключи |
| `/account/analytics/` | Client | Аналитика трат (bar charts, топ моделей) |
| `/account/billing/` | Client | Биллинг / покупка |
| `/account/referral/` | Client | Реферальная программа |
| `/account/files/` | Client | Файлы пользователя |
| `/compare/` | Client | Model Arena (сравнение 2-3 моделей side-by-side, SSE) |
| `/projects/` | Client | Projects (папки чатов с system prompt, цветом, иконкой) |
| `/prompts/` | Client | Библиотека промтов (встроенные + пользовательские) |
| `/welcome/` | Client | Онбординг (3-шаговый wizard после регистрации) |
| `/blog/` | SSR + ISR | Блог |
| `/api-docs/` | SSG | Документация API + интерактивный playground |
| `/status/` | Client | Статус-страница сервиса |
| `(auth)/` | Client | Группа авторизации (вход / регистрация / восстановление) |
| `(dashboard)/` | Client | Группа B2B-дашборда (organization, usage) |

Примечание: в спецификациях ROADMAP каталог иногда называется `/catalog/`, а документация `/docs/` — фактические директории называются `models/` и `api-docs/`.

---

## Django-приложения

### `users` — пользователи и монетизация

**Модели:**
- `CustomUser` (AbstractUser) — email как логин, поле `pages_count` (звёзды), `tariff`, `active_subscription`, `shadow_banned`, `referral_code`, `referrer`, `rub_balance`
- `Tariff` — тарифные планы: `pages_count`, `price`, `is_free`, `is_trial`, `duration_days`, `next_tariff` (для перехода после пробного), реферальные бонусы
- `UserSubscription` — активная подписка пользователя, `expires_at`, `auto_renew`, `renewal_attempts`
- `PaymentHistory` — история платежей (subscription / pages / promo), статусы pending/success/failed/refunded
- `PageSaleSettings` — настройки продажи звёзд поштучно
- `PromoCode` / `UsedPromoCode` — промокоды на звёзды
- `LegalDocument` — политика конфиденциальности и пользовательское соглашение (управляется через админку)
- `SiteSettings` — глобальные SEO-настройки, ссылки соцсетей, email поддержки (singleton, id=1)
- `ReferralEarning` / `WithdrawalRequest` — реферальная программа
- `UserIPAddress`, `UserActivityLog`, `UserSpending` — аналитика

**URL-файлы:**
- `users/urls_api.py` → prefix `users/api/` — AJAX-эндпоинты (legacy + платежи)
- `users/urls_pages.py` → prefix `users/pages/` — legacy HTML-страницы

**Middleware (в settings.py):**
- `ShadowBanMiddleware` — при регистрации с IP уже использованного пользователя автоматически ставит `shadow_banned=True`, редиректит на `/users/pages/blocked/`
- `EmailVerificationMiddleware` — редиректит на верификацию если email не подтверждён
- `UserActivityMiddleware` — логирует IP и дневную активность

**Celery-задачи:**
- `process_pending_renewals()` — каждые 12 ч: находит подписки, истекающие в течение 3 дней, делает recurring-платёж через Robokassa
- `notify_upcoming_expiration()` — уведомляет email за 3 дня до конца подписки (один раз)

### `aitext` — нейросети, чаты, медиа

**Модели:**
- `Category` — категории нейросетей (Фото, Видео, Аудио и т.д.)
- `NeuralNetwork` — нейросеть: `provider` (openrouter / fal-ai), `model_name`, `cost_per_message`, `unlimited` + `tariffs` (M2M безлимит для тарифов), `messages_limit` (дневной лимит бесплатных), `config_json` (для медиа-моделей), `handle_photo/video/archive/text_files`, `translate_to_english`, SEO-поля
- `Chat` — чат пользователя с нейросетью, хранит `settings` (JSON с параметрами генерации)
- `Message` — сообщение (role: user/assistant), статусы pending/completed/failed, `plain_text` (без HTML), `extracted_content` (текст из вложений)
- `FileAttachment` — загруженный пользователем файл (image/video/audio/pdf/other), с извлечённым текстом
- `GeneratedImage` — сгенерированный AI файл (image или video), хранится в `media/generated_images/` или `media/generated_videos/`
- `NeuralNetworkDailyUsage` — счётчик бесплатных сообщений в день (per user+network+date)
- `FAQ` — вопросы-ответы, привязываются к нейросети или показываются глобально

**Management-команды:**
- `add_laozhang_models` — добавление текстовых/медиа моделей laozhang.ai
- `add_video_models` — добавление 5 видео-моделей (см. раздел «Видео модели»)
- `cleanup_old_models` — очистка устаревших моделей
- `download_avatars` — загрузка аватаров моделей
- `test_search "запрос"` — тест веб-поиска через Tavily

**Ключевой flow чата:**
1. Пользователь POST → `create_chat` или `send_message` (через `/api/v1/`)
2. Проверка баланса / бесплатного лимита
3. Создаётся `Message(role='assistant', status='pending')`
4. Для текстовых моделей — звёзды списываются сразу; для изображений/видео — в Celery-задаче
5. `generate_ai_response.delay(assistant_message.id)` — задача Celery
6. Frontend: для текста — SSE streaming; в остальных случаях polling `message_status/{id}` пока status != completed/failed

**Celery-задача `generate_ai_response`:**
- **Текст** (provider=openrouter): собирает историю (последние 20 сообщений), при включённом веб-поиске вызывает `call_web_search()` (Tavily) и подмешивает результаты в контекст, вызывает `chat.completions.create` (стримингом для SSE), форматирует ответ через `CodeFormatter`, обрабатывает base64-изображения в ответе
- **Изображения** (provider=fal-ai): валидирует настройки через `validate_and_merge_settings`, вызывает `client.images.generate`, скачивает и сохраняет медиа через `save_media_from_url`
- **Видео**: маршрутизация по `model_name` (Veo/Sora vs Seedance), см. раздел «Видео модели»
- При ошибке генерации медиа — звёзды возвращаются пользователю через `user.add_pages(total_cost)`
- 3 retry с задержкой 60 сек

**Translate to English**: если у нейросети `translate_to_english=True`, промт переводится через DeepSeek V3 (laozhang.ai) перед отправкой в модель изображений/видео.

### `api` — DRF API-слой (`/api/v1/`)

OpenAI-совместимый API для внешних клиентов, IDE-интеграций и фронтенда Next.js.

**Структура:**
- `authentication.py` — JWT + APIKey аутентификация
- `throttling.py` — rate limiting
- `exceptions.py` — кастомные обработчики ошибок
- `serializers/`, `services/`, `views/` — разбиты по доменам
- `models.py` — `APIKey` (хэш ключа, scopes, лимиты), audit-модели, webhook-модели

**Эндпоинты (`/api/v1/`):**
- `POST /chat/completions` — текстовые чаты (OpenAI-совместимый, поддержка stream)
- `POST /images/generations` — генерация изображений
- `POST /embeddings` — эмбеддинги
- `POST /audio/speech` — TTS (текст → аудио)
- `POST /audio/transcriptions` — ASR / Whisper (аудио → текст)
- `POST /batches/` — batch API (асинхронная пакетная обработка через Celery)
- `/keys/` — управление API-ключами
- `/models` — список доступных моделей
- `/catalog`, `/chats`, `/projects`, `/prompts`, `/files`, `/uploads` — ресурсы фронтенда
- `/compare` — Model Arena
- `/billing`, `/invoices`, `/usage`, `/referral` — монетизация
- `/teams` — B2B (см. ниже)
- `/webhooks` — управление вебхуками (HMAC-подпись исходящих событий)
- `/audit` — audit log
- `/blog`, `/legal` — контент
- `/anthropic` — Anthropic-совместимый endpoint
- `/status` — статус сервиса

**Особенности:**
- Webhooks подписываются HMAC
- Audit log фиксирует значимые действия
- Throttling по ключу/пользователю

### `teams` — B2B (организации)

**Модели:**
- `Organization` — организация (владелец, баланс, настройки)
- `Member` — член организации (роль, доступ)
- `OrgInvite` — приглашения в организацию
- `OrgInvoice` — счета оргбиллинга

**Функционал:**
- Орг-биллинг (общий баланс/счета организации)
- Usage по членам организации
- Frontend: `(dashboard)/` группа маршрутов — `/dashboard/organization/`, `/dashboard/usage/`

### `blog` — блог

- `Category`, `Post` — статьи с SEO-полями, привязка к нейросетям (M2M), `show_in_notification`, `show_on_main`
- Management-команда `create_seo_posts` — генерация SEO-статей (контент-машина через DeepSeek/Celery)
- Раздаётся через DRF (`/api/v1/blog`) и рендерится на Next.js (`/blog/`, SSR + ISR)

### `landing` — legacy лендинг

- Старый Django-лендинг (legacy, основной лендинг теперь на Next.js)
- Кастомный обработчик 404: `landing.views.custom_404_view`

---

## Видео модели — ТЕКУЩЕЕ СОСТОЯНИЕ И ПРОБЛЕМЫ

Добавлены 5 видео-моделей через management-команду `add_video_models`:

| Модель | `model_name` | Стоимость |
|--------|--------------|-----------|
| Sora | `sora-2` | 60 звёзд |
| Sora Pro | `sora-2-pro` | 100 звёзд |
| Veo 3.1 Fast | `veo-3.1-fast-generate-preview` | 50 звёзд |
| Veo 3.1 | `veo-3.1-generate-preview` | 100 звёзд |
| Seedance Fast | `doubao-seedance-2-0-fast-260128` | 40 звёзд |

Видео-генерация реализована в `src/aitext/fal_utils.py`.

**Veo / Sora** (через laozhang.ai `/v1/...`):
- Создание задачи: `POST /v1/videos` — **multipart/form-data** (не JSON!)
- Проверка статуса: `GET /v1/videos/{id}`
- Скачивание результата: `GET /v1/videos/{id}/content`

**Seedance** (отдельный endpoint и ключ):
- Создание задачи: `POST https://api.laozhang.ai/seedance/api/v3/contents/generations/tasks` (JSON)
- Требует **отдельный API-ключ** группы SeeDance2 на laozhang.ai → переменная `SEEDANCE_API_KEY`

**Известные ограничения / проблемы:**
- laozhang.ai ставит жёсткий **rate limit на видео** — при частых запросах подряд возвращает **429**
- **Seedance** требует отдельный `SEEDANCE_API_KEY` с группой SeeDance2; без него Seedance не работает
- **Veo 3.1 Fast** работает корректно (протестировано, задача создаётся примерно за $0.30)
- **Polling до 15 минут** — 60 попыток с интервалом 15 секунд
- При любой ошибке генерации звёзды возвращаются пользователю

---

## Веб-поиск (Tavily)

Чат поддерживает режим веб-поиска для текстовых моделей.

- Провайдер: **Tavily API** (1000 запросов/месяц бесплатно, tavily.com)
- Ключ: `TAVILY_API_KEY` в `.env`
- Реализация: `call_web_search()` в `src/aitext/tasks.py`
- UI: toggle «Интернет» в поле ввода чата (frontend)
- Flow: при включённом тоггле перед вызовом LLM выполняется поиск, результаты подмешиваются в контекст сообщения
- Тест: `docker-compose exec web python manage.py test_search "запрос"`

---

## Валюта: «Звёзды» (pages_count)

- Новый пользователь получает `free_tariff.pages_count` звёзд (обычно 10)
- Каждое сообщение списывает `network.cost_per_message` звёзд
- При ошибке генерации изображений/видео — звёзды возвращаются
- Покупка тарифа **добавляет** звёзды к существующим (`pages_count += tariff.pages_count`)
- Покупка звёзд поштучно: через `PageSaleSettings` (цена за звезду, мин/макс)
- Промокоды: начисляют звёзды напрямую
- Безлимит: если `network.unlimited=True` и у пользователя тариф из `network.tariffs`, то сообщения бесплатны до `messages_limit` в день

---

## Платежи (Robokassa)

- Подпись MD5: `MerchantLogin:OutSum:InvId:Receipt(JSON):Password1` кодируется в UTF-8 или CP1251 в зависимости от типа платежа
- Result URL (POST): `/users/api/payment/success/` — верифицирует подпись `OutSum:InvId:Password2`, активирует тариф
- Recurring платежи: POST на `https://auth.robokassa.ru/Merchant/Recurring` с `PreviousInvoiceID`
- Тестовый режим: `ROBOKASSA_TEST_MODE=0` (production)

---

## Конфигурация моделей изображений/видео (`config_json`)

Поле `NeuralNetwork.config_json` — JSON-объект со структурой:
```json
{
  "name": "Название модели",
  "api_defaults": { "param": "value" },
  "ui_settings": {
    "sections": [
      {
        "title": "Секция",
        "fields": [
          { "name": "param", "type": "slider|select|checkbox|number|text", "label": "...", "min": 0, "max": 100, "extra_cost": 5 }
        ]
      }
    ]
  },
  "constraints": { "max_colors": 10, "min_seed": 0 },
  "metadata": { "requires_input_images": false }
}
```
`extra_cost` в поле — дополнительные звёзды за настройку.

---

## Переменные окружения (`.env`)

```
SECRET_KEY=
DEBUG=0
DJANGO_ALLOWED_HOSTS=aineron.ru www.aineron.ru localhost 127.0.0.1

# PostgreSQL
POSTGRES_DB=neiro_db
POSTGRES_USER=neiro_user
POSTGRES_PASSWORD=
DB_HOST=db
DB_NAME=neiro_db
DB_USER=neiro_user
DB_PASSWORD=
DB_PORT=5432

# Redis / Celery
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Email (Gmail SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Платежи
ROBOKASSA_LOGIN=
ROBOKASSA_PASS1=
ROBOKASSA_PASS2=
ROBOKASSA_TEST_MODE=0

# AI провайдер (laozhang.ai)
LAOZHANG_API_KEY=
SEEDANCE_API_KEY=         # laozhang.ai SeeDance2 group token (optional, для Seedance видео)

# Веб-поиск
TAVILY_API_KEY=           # tavily.com — 1000 req/month free

# Сайт
SITE_URL=https://aineron.ru
SITE_NAME=aineron.ru

# Frontend (Next.js)
NEXT_PUBLIC_API_URL=      # базовый URL Django API для фронтенда
```

---

## Docker Compose (7 сервисов)

| Сервис | Образ/build | Описание |
|--------|-------------|----------|
| `redis` | redis:7-alpine | Брокер Celery, кэш сессий |
| `db` | postgres:15-alpine | PostgreSQL |
| `web` | build (Dockerfile) | Django + Gunicorn, :8000 |
| `celery_worker` | build (Dockerfile) | Celery gevent, concurrency 200 |
| `celery_beat` | build (Dockerfile) | Периодические задачи (DatabaseScheduler) |
| `frontend` | build (Dockerfile.frontend) | Next.js 14, :3000 |
| `nginx` | nginx:1.25-alpine | SSL termination, роутинг, :80/:443 |

Volumes: `postgres_data`, `redis_data`, `static_volume`, `media_volume`

---

## Запуск локально

```bash
# Создать .env из примера, заполнить секреты
cp .env.example .env

# Деплой
bash deploy.sh

# Или вручную
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
docker-compose exec web python manage.py createsuperuser
```

**Backend-тесты** (SQLite, без Docker):
```bash
cd src
python manage.py test
```

**Frontend (Next.js) локально:**
```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build    # production-сборка
npm run lint
```

**Полезные management-команды:**
```bash
docker-compose exec web python manage.py add_video_models
docker-compose exec web python manage.py add_laozhang_models
docker-compose exec web python manage.py test_search "запрос"
docker-compose exec web python manage.py create_seo_posts
```

---

## Аутентификация

**Web / Next.js:**
- Кастомная модель `CustomUser` (email как логин, username генерируется из email)
- django-allauth для социальных провайдеров: Google, Yandex, VK, Mail.ru
- JWT (simplejwt) для запросов фронтенда к API
- Email верификация: 6-значный код в поле `email_verification_code`
- Shadow ban: автоматически при регистрации с уже использованного IP

**API (внешние клиенты):**
- `APIKey` модель — аутентификация внешних запросов к `/api/v1/`
- OpenAI-совместимый формат (Bearer token)
- Throttling по ключу

---

## SEO

- Sitemap: `frontend/app/sitemap.ts` (Next.js) + Django `/sitemap.xml` (legacy)
- robots.txt: `frontend/app/robots.ts`
- Каждая нейросеть, пост и категория блога имеют `seo_title`, `seo_description`, `seo_keywords`
- JSON-LD: на страницах моделей (`/models/[slug]/`), FAQPage, BreadcrumbList
- `SiteSettings` хранит глобальные SEO-мета и отдельные для блога и каталога
- Аналитика: Yandex.Metrika + Google Analytics 4 (frontend)
- SEO-контент машина: команда `create_seo_posts` + Celery-генерация статей через DeepSeek

---

## Важные паттерны

**Проверка баланса перед запросом:**
```python
if deduct_stars and request.user.pages_count < cost:
    return JsonResponse({'success': False, 'message': f'Недостаточно звёзд...'})
```

**Celery retry при ошибке API:**
```python
raise self.retry(exc=e, countdown=60)  # max_retries=3
```

**Безопасность медиа-генерации**: при любой ошибке генерации изображений/видео звёзды возвращаются через `user.add_pages(total_cost)`.

**Singleton-настройки**: `SiteSettings.get_settings()`, `PageSaleSettings.get_settings()` — `get_or_create(id=1)`.

**Контекст-процессоры** (legacy-шаблоны): `user_balance`, `site_settings`, `current_site`, `site_counter`, `notification_posts`, `footer_networks`.

**SSE streaming**: текстовые ответы стримятся через EventSource на фронте; Celery-задача пишет токены, фронт отображает с адаптивным дренажём токенов (плавная анимация).

---

## Реферальная программа

- Каждый пользователь имеет уникальный `referral_code` (8 символов)
- При регистрации через `/?ref=CODE` — устанавливается `user.referrer`
- При покупке тарифа — рефереру начисляется `tariff.referral_bonus` руб. или `tariff.referral_bonus_stars` звёзд
- Пользователи с `can_convert_to_rub=True` получают рублёвый баланс и могут заказать вывод на карту
- Frontend: `/account/referral/`

---

## Дизайн-система и UI-правила (ОБЯЗАТЕЛЬНО соблюдать)

### Иконки
- Использовать **только** Lucide React: `import { IconName } from 'lucide-react'`
- Запрещены эмодзи в любом месте интерфейса — ни в JSX, ни в шаблонах Django, ни в тексте кнопок, ни в плейсхолдерах
- Запрещены другие иконочные шрифты (Font Awesome, Material Icons и т.п.)
- Размеры иконок: `size={16}` (inline), `size={20}` (кнопки), `size={24}` (заголовки/навигация)
- Цвет иконок наследуется от `currentColor` — не задавать явно без необходимости

### Стиль интерфейса
- Строгий, минималистичный, профессиональный — ориентир: Linear, Vercel Dashboard, Stripe
- Никаких декоративных эмодзи в заголовках, CTA, списках, письмах
- Тексты кнопок: короткие глаголы без спецсимволов («Войти», «Купить», «Скопировать»)
- Типографика: системный стек или Inter (Google Fonts / bunny.net)

### Dark Mode
- Реализован через CSS-переменные и `data-theme="dark"`
- Учитывает system preference, состояние сохраняется в localStorage

### Legacy фронт (Django-шаблоны)
- Новые шаблоны `.html` и legacy JS-файлы создавать без эмодзи
- В существующих файлах при редактировании убирать эмодзи на текст или SVG-иконки
- Скрипт проверки: `scripts/check_no_emoji.py`

---

## Стратегический план (ROADMAP)

Все 6 фаз ROADMAP **завершены**. Актуальный план развития — конкурентная стратегия выхода в топ-3 России — в файле `COMPETITIVE_PLAN.md`.

### Статус фаз
- **ФАЗА 0** — SEO и zero-emoji — ЗАВЕРШЕНА
- **ФАЗА 1** — DRF API-слой + OpenAI-совместимые эндпоинты + API-ключи — ЗАВЕРШЕНА
- **ФАЗА 2** — Инфраструктура Next.js — ЗАВЕРШЕНА
- **ФАЗА 3** — Миграция страниц на Next.js — ЗАВЕРШЕНА
- **ФАЗА 4** — B2B (команды, оргбиллинг, usage) — ЗАВЕРШЕНА
- **ФАЗА 5** — SEO-блог, Analytics — ЗАВЕРШЕНА (~70%, нужен контент статей)
- **ФАЗА 6** — Embeddings, Audio, Batch, Webhooks, Audit, Status — ЗАВЕРШЕНА

### Спринты конкурентного плана

**Sprint 1 — ВЫПОЛНЕН:**
- Chat sidebar с историей (группировка по дате, переименование, удаление, Ctrl+K поиск)
- Markdown рендеринг (react-markdown + rehype-highlight + remark-gfm)
- Copy / Regenerate / Like кнопки на каждом сообщении ассистента
- Dark Mode (CSS-переменные, `data-theme="dark"`, system preference, localStorage)
- Starter prompts на пустом экране чата (4-6 карточек, специфичных для модели)

**Sprint 2 — ВЫПОЛНЕН:**
- Загрузка файлов в чат (FileUpload, drag&drop, jpg/png/pdf/txt/docx)
- Model Arena (`/compare/`) — сравнение 2-3 моделей side-by-side с SSE streaming
- Промпт-библиотека (`/prompts/`) — встроенные + пользовательские промты
- Веб-поиск в чате (Tavily API, toggle «Интернет»)
- Аналитика пользователя (`/account/analytics/`) — bar charts, топ моделей
- Онбординг `/welcome/` — 3-шаговый wizard после регистрации
- Лендинг 2.0 — hero-анимация, social proof, comparison-таблица, use cases, pricing
- Projects (`/projects/`) — папки чатов с system prompt, цветом, иконкой

**Sprint 3 — ВЫПОЛНЕН (кроме Telegram и Persistent Memory):**
- PWA (`frontend/public/manifest.json` / `app/manifest.ts`, service worker, next-pwa)
- Голосовой режим — VoiceInput (Web Speech API → Whisper ASR `/api/v1/audio/transcriptions`), VoiceOutput (TTS `/api/v1/audio/speech`)
- SEO-контент машина — команда генерации статей + Celery-задача через DeepSeek
- API Playground в документации (`/api-docs/playground/`) — интерактивный тестер с copy curl/Python/JS

### НЕ реализовано
- **Telegram-бот** — план в `TELEGRAM_BOT_PLAN.md`
- **Persistent Memory** — план в `PERSISTENT_MEMORY_PLAN.md`

---

## Файлы: ключевые пути

### Backend

| Что | Где |
|-----|-----|
| Настройки Django | `src/config/settings.py` |
| Celery конфиг | `src/config/celery.py` |
| Корневые URL | `src/config/urls.py` |
| Модели пользователей | `src/users/models.py` |
| Модели нейросетей/чатов | `src/aitext/models.py` |
| AI-генерация (Celery task) | `src/aitext/tasks.py` |
| Веб-поиск (Tavily) | `src/aitext/tasks.py` → `call_web_search()` |
| Медиа/видео утилиты (Veo/Sora/Seedance) | `src/aitext/fal_utils.py` |
| Файловые утилиты | `src/aitext/file_utils.py` |
| Форматирование кода | `src/aitext/code_formatter.py` |
| Команда видео-моделей | `src/aitext/management/commands/add_video_models.py` |
| Команда тест поиска | `src/aitext/management/commands/test_search.py` |
| Команда SEO-статей | `src/blog/management/commands/create_seo_posts.py` |
| DRF API URLs | `src/api/urls.py` |
| DRF API views | `src/api/views/` (chat, images, audio, embeddings, batch, keys, webhooks, ...) |
| API аутентификация | `src/api/authentication.py` |
| API throttling | `src/api/throttling.py` |
| Модели API (APIKey, audit, webhooks) | `src/api/models.py` |
| Модели B2B | `src/teams/models.py` |
| Платежи (views) | `src/users/views.py` (payment_success, create_robokassa_payment, buy_pages) |
| Celery-задачи подписок | `src/users/tasks.py` |
| Middleware | `src/users/middleware.py` |
| Email-сервис | `src/users/email_service.py` |
| Адаптеры allauth | `src/users/adapters.py` |
| Legacy шаблоны | `src/templates/neuro/` |

### Frontend (Next.js)

| Что | Где |
|-----|-----|
| Корневой layout | `frontend/app/layout.tsx` |
| Провайдеры (React Query, Zustand) | `frontend/app/providers.tsx` |
| Лендинг | `frontend/app/page.tsx` |
| Каталог моделей | `frontend/app/models/` |
| Чат | `frontend/app/chat/` |
| Кабинет | `frontend/app/account/` (keys, analytics, billing, referral, files) |
| Model Arena | `frontend/app/compare/` |
| Projects | `frontend/app/projects/` |
| Промпт-библиотека | `frontend/app/prompts/` |
| Онбординг | `frontend/app/welcome/` |
| Блог | `frontend/app/blog/` |
| API-документация + playground | `frontend/app/api-docs/` |
| Статус | `frontend/app/status/` |
| Группа авторизации | `frontend/app/(auth)/` |
| Группа дашборда (B2B) | `frontend/app/(dashboard)/` |
| Компоненты | `frontend/components/` (chat, landing, docs, analytics, layout, ui) |
| API-клиент | `frontend/lib/api/` |
| Zustand-сторы | `frontend/lib/stores/` |
| Next.js middleware | `frontend/middleware.ts` |
| PWA manifest | `frontend/app/manifest.ts` + `frontend/public/manifest.json` |
| sitemap / robots | `frontend/app/sitemap.ts` / `frontend/app/robots.ts` |
| Next config | `frontend/next.config.mjs` |

### Инфраструктура

| Что | Где |
|-----|-----|
| Docker Compose | `docker-compose.yml` |
| Backend Dockerfile | `Dockerfile` |
| Frontend Dockerfile | `Dockerfile.frontend` |
| Nginx | `nginx.conf` |
| Скрипт деплоя | `deploy.sh` |
| Конкурентный план | `COMPETITIVE_PLAN.md` |
| План Telegram-бота (не реализован) | `TELEGRAM_BOT_PLAN.md` |
| План Persistent Memory (не реализован) | `PERSISTENT_MEMORY_PLAN.md` |
| Скрипт проверки эмодзи | `scripts/check_no_emoji.py` |
