# aineron.ru — CLAUDE.md

## Что это за проект

SaaS-платформа для доступа к AI-нейросетям без VPN. Пользователи пополняют **рублёвый баланс** (в копейках, `balance_kopecks`) и тратят его на каждое сообщение к нейросети. Поддерживает текстовые LLM, генерацию изображений и видео — текст и изображения через **api.laozhang.ai**, видео через **api.apimart.ai**.

«Звёзды» — legacy-термин: старое название внутренней валюты до перехода на рублёвый биллинг (см. раздел «Биллинг» ниже). Сейчас это (а) устаревшее dual-write поле `pages_count` в БД, сохранённое только для обратной совместимости API, и (б) отдельное, никак не связанное понятие — **Telegram Stars (XTR)**, нативная платёжная система Telegram, один из способов пополнения баланса в боте. Если видите «звёзды» в интерфейсе бота — это либо legacy-текст, который надо поправить, либо про Telegram Stars как способ оплаты; в остальном коде это не текущая валюта проекта.

Поверх базового доступа к моделям построены продукты:
- **Веб-платформа** (Next.js 14) — чат, каталог, кабинет, блог, Model Arena, Projects, Prompts.
- **Telegram-бот** (aiogram 3) — полноценный AI-ассистент в мессенджере + Mini App.
- **Vibe-Coding Studio** — AI-конструктор приложений (многоагентный пайплайн генерации кода в Docker-песочнице с git-хостингом Gitea и деплоем). **Заморожена** на обоих инстансах — на aineron.ru выключена флагом (`STUDIO_ENABLED=false`), на aineron.net сервисы Studio/Gitea вообще отсутствуют в `docker-compose.intl.yml` (не просто выключены — структурно не задеплоены). Код остаётся в репозитории для будущего возобновления, но фичу сейчас не развиваем и не чиним.

Архитектура — разделённый стек: **Django (DRF API + Admin)** на бэкенде и **Next.js 14 (App Router)** на фронтенде. Фронтенд полностью развёрнут в папке `frontend/`, Django работает в режиме API-сервера (`/api/v1/`).

---

## Два инстанса, один репозиторий — не перепутать

Этот код обслуживает **два отдельных живых продакшн-инстанса** из **одного git-репозитория и одной ветки `main`** (отдельной ветки под intl нет):

| | **aineron.ru** | **aineron.net** |
|---|---|---|
| Рынок | Россия, русский язык | Международный: en/fa/tr/id/ar (next-intl) |
| Сервер | Beget (Россия) | Отдельный VPS (NL) |
| Деплой | `docker-compose.yml` + `deploy.sh` | `docker-compose.intl.yml` + `deploy_intl.sh` |
| Флаг | `INTL_MODE=0` (по умолчанию) | `INTL_MODE=1` |
| Платежи | Robokassa | + Crypto Pay (USDT/TON), Telegram Stars (XTR) |
| Studio/Gitea | Выключены флагом | Сервисов нет в compose вообще |

**Оба сервера независимо друг от друга делают `git pull origin main`** и разворачивают только свой `docker-compose*.yml`. Автодеплоя между ними нет — если задеплоить только один, второй может неделями сидеть на старом коммите. Разделение — **не по репозиториям и не по веткам**, а по env-флагу `INTL_MODE` внутри одного и того же кода, плюс два параллельных docker-compose/deploy-скрипта.

**Почему это не разделяют на два репозитория** (сознательное решение, не забытая задача): ~95% кода общее — модели, миграции, биллинговый движок, чат/медиа-пайплайн. Разделение репо означает два PR на каждый общий баг-фикс и, главное, **риск разъехавшейся истории миграций Django** — у обоих инстансов одна и та же схема БД, и рассинхронизация `django_migrations` на живых базах — тяжёлый инцидент. Один репозиторий с дисциплиной по флагам — безопаснее, чем два репозитория без неё.

**Практические правила, которые реально защищают один инстанс от изменений для другого:**
1. **Любое различающееся поведение — только через `settings.INTL_MODE`**, с безопасным дефолтом (`INTL_MODE=0` по умолчанию — то есть если забыть добавить проверку флага для новой intl-фичи, она включится и на aineron.ru; для платных/рискованных путей всегда явно проверяйте флаг и по умолчанию выключайте).
2. **Data-миграции (`RunPython`) должны быть instance-agnostic** — идемпотентны, не завязаны на валюту/локаль/наличие конкретных сервисов. Если миграция обязана вести себя по-разному — ветвление внутри неё на `settings.INTL_MODE`, а не предположение, что «сейчас точно такой-то инстанс».
3. Новые модели/поля — только additive и обратно совместимые с безопасным дефолтом (пример: `Post.language` из блога — новое поле с `default='ru'`, безвредно приземляется на aineron.ru даже неиспользуемым).
4. После любого изменения общего кода или миграции — по возможности деплоить оба инстанса близко по времени, не оставлять один надолго на старом коммите с непроверенным изменением.

**Локальная работа с двумя инстансами:** этот чек-аут (`C:\Users\user\Desktop\aineron.ru`) — рабочая копия для aineron.ru. Для aineron.net рекомендуется отдельный `git clone` того же `origin` в другую папку (например `C:\Users\user\Desktop\aineron.net`) — не `git worktree` (обе ветки — `main`, worktree не даст завести две копии одной ветки), и открывать его отдельной сессией Claude Code, чтобы не путать контекст «какой инстанс сейчас обсуждается». Разделы ниже помечены `[.ru]` / `[.net]` / без пометки = общее для обоих, где расхождение существенно.

---

## Стек технологий

### Backend

| Слой | Технология |
|------|-----------|
| Backend | Django 4.2, Python 3.11 |
| API | Django REST Framework (`/api/v1/`, OpenAI-совместимые эндпоинты) |
| Task queue | Celery 5.6 + Redis 7 |
| Database | PostgreSQL 15 (SQLite только для тестов) |
| Auth (web) | django-allauth 65 (Google, Yandex, VK, Mail.ru, GitHub + email/password) |
| Auth (API) | JWT (djangorestframework-simplejwt) + APIKey (для внешних запросов) |
| CORS | django-cors-headers |
| AI — текст | laozhang.ai (openai SDK, base_url: api.laozhang.ai/v1) |
| AI — изображения | laozhang.ai (openai SDK, images.generate API) |
| AI — видео | apimart.ai (Sora / Veo / Kling, `/v1/videos/generations`) |
| Telegram-бот | aiogram 3 (FSM на Redis, webhook) |
| Studio (codegen) | OpenAI SDK через laozhang.ai, Docker SDK (песочницы), Gitea, Playwright (скриншоты) |
| Веб-поиск | Tavily API |
| Платежи | Robokassa (recurring через POST /Merchant/Recurring); Telegram Stars (XTR) в боте |
| WSGI | Gunicorn (8 workers, 2 threads) |
| Celery pool | gevent, concurrency 200 (общая очередь); отдельные воркеры для Studio |

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
| SSE | EventSource (real-time streaming текстовых ответов и событий Studio) |
| Расположение | `frontend/` в корне репозитория |

### Деплой

| Слой | Технология |
|------|-----------|
| Деплой | Docker Compose (11 сервисов) |
| Reverse proxy | Nginx (SSL termination, роутинг Next.js / Django / Gitea / Studio-песочницы) |
| Git-хостинг | Gitea 1.22 (репозитории проектов Studio) |

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
│   ├── studio/                 # Vibe-Coding Studio: агенты, пайплайн, песочницы
│   ├── telegram_bot/           # Telegram-бот (aiogram 3) + Mini App API
│   ├── landing/                # Старый лендинг (legacy), 404-обработчик
│   ├── static/ , staticfiles/  # Legacy/собранная статика
│   ├── templates/neuro/        # Legacy HTML-шаблоны + admin/API-docs
│   ├── media/                  # Загруженные и сгенерированные файлы
│   ├── logs/                   # Логи приложения
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
│   │   ├── studio/             # Vibe-Coding Studio UI (+ [id]/interview, /review)
│   │   ├── tg/                 # Telegram Mini App
│   │   ├── ide/                # IDE-страница (генерация ключей / интеграции)
│   │   ├── welcome/            # Онбординг-wizard
│   │   ├── blog/               # Блог (SSR + ISR)
│   │   ├── api-docs/           # Документация API + playground
│   │   ├── status/             # Статус-страница
│   │   ├── blocked/            # Страница блокировки (shadow ban)
│   │   ├── payment-success/ , payment-fail/   # Результат оплаты
│   │   ├── privacy-policy/ , terms/           # Юридические страницы
│   │   ├── (auth)/             # Группа авторизации
│   │   ├── (dashboard)/        # Группа дашборда (B2B)
│   │   ├── manifest.ts         # PWA manifest
│   │   ├── sitemap.ts          # Sitemap
│   │   ├── robots.ts           # robots.txt
│   │   ├── providers.tsx       # React Query / Zustand провайдеры
│   │   └── layout.tsx          # Корневой layout
│   ├── components/             # analytics, chat, docs, landing, layout, studio, ui, PWAProvider
│   ├── lib/                    # api (клиент), stores (Zustand), studio, utils.ts
│   ├── middleware.ts           # Next.js middleware (auth-редиректы)
│   ├── public/                 # Статика, manifest.json, иконки
│   ├── next.config.mjs
│   ├── tailwind / postcss config
│   └── package.json
├── docker-compose.yml          # 11 сервисов (см. раздел Docker Compose)
├── Dockerfile                  # Backend: FROM python:3.11-slim
├── Dockerfile.frontend         # Frontend: Next.js build
├── Dockerfile.playwright       # Celery-воркер со скриншотами (Playwright)
├── Dockerfile.sandbox          # Образ песочницы Studio (Node + dev-сервер)
├── nginx.conf                  # SSL termination, роутинг Next.js / Django / Gitea / sandbox
├── deploy.sh / pull.sh         # Скрипты деплоя
├── TOP1_PLAN.md                # Актуальный стратегический план (платформа + бот)
├── PERSISTENT_MEMORY_PLAN.md   # План Persistent Memory (НЕ реализован)
└── .env                        # Секреты (не коммитить)
```

---

## Nginx-роутинг (production)

```
/                    → Next.js (frontend:3000)   — лендинг, каталог, чат, кабинет, studio, tg и т.д.
/_next/              → Next.js (frontend:3000)   — статика Next.js
/api/                → Django  (web:8000)        — DRF API
/admin/              → Django  (web:8000)        — Django Admin (НЕ мигрируется)
/users/ , /accounts/ , /aitext/ , /telegram/ → Django (web:8000)
/git/                → Gitea   (gitea:3000)      — git-хостинг репозиториев Studio
/studio/preview/<cid>/<rest> → sandbox-контейнер — превью генерируемого приложения
/media/              → static files напрямую     — загруженные и сгенерированные файлы
/static/             → static files напрямую     — collectstatic Django (admin, legacy)
```

Nginx делает SSL termination, сертификаты: `./ssl/fullchain.pem` и `./ssl/privkey.pem`.
Превью Studio проксируется напрямую в контейнер-песочницу по его имени (`http://<cid>:3000/`) через сеть `aineron_sandbox_net`.

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
| `/studio/` | Client | Vibe-Coding Studio: список проектов, шаблоны, hero |
| `/studio/[id]/` | Client | Рабочее пространство проекта (файлы, превью, пайплайн, чат) |
| `/studio/[id]/interview/` | Client | Интервью-онбординг проекта (карточки вопросов) |
| `/studio/[id]/review/` | Client | Режим ревью / просмотра результата |
| `/tg/` | Client | Telegram Mini App (auth по initData + JWT) |
| `/ide/` | Client | IDE-интеграции / генерация ключей |
| `/welcome/` | Client | Онбординг (3-шаговый wizard после регистрации) |
| `/blog/` | SSR + ISR | Блог |
| `/api-docs/` | SSG | Документация API + интерактивный playground |
| `/status/` | Client | Статус-страница сервиса |
| `/blocked/` | Client | Страница блокировки (shadow ban) |
| `/payment-success/`, `/payment-fail/` | Client | Результат оплаты |
| `/privacy-policy/`, `/terms/` | Client/SSR | Юридические документы |
| `(auth)/` | Client | Группа авторизации (вход / регистрация / восстановление) |
| `(dashboard)/` | Client | Группа B2B-дашборда (organization, usage) |

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

**Middleware:**
- `ShadowBanMiddleware` — при регистрации с IP уже использованного пользователя автоматически ставит `shadow_banned=True`, редиректит на страницу блокировки
- `EmailVerificationMiddleware` — редиректит на верификацию если email не подтверждён
- `UserActivityMiddleware` — логирует IP и дневную активность

**Celery-задачи:**
- `process_pending_renewals()` — каждые 12 ч: находит подписки, истекающие в течение 3 дней, делает recurring-платёж через Robokassa
- `notify_upcoming_expiration()` — уведомляет email за 3 дня до конца подписки (один раз)

### `aitext` — нейросети, чаты, медиа

**Модели:**
- `Category` — категории нейросетей (Фото, Видео, Аудио и т.д.)
- `NeuralNetwork` — нейросеть: `provider` (`openrouter` = текст laozhang.ai / `fal-ai` = изображения и видео), `model_name`, `cost_per_message`, `unlimited` + `tariffs` (M2M безлимит для тарифов), `messages_limit` (дневной лимит бесплатных), `config_json` (для медиа-моделей), `handle_photo/video/archive/text_files`, `translate_to_english`, SEO-поля
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
- **Видео** (provider=fal-ai, видео-модели apimart): маршрутизация через `config_json.metadata.video_api == 'apimart'`, см. раздел «Видео модели»
- При ошибке генерации медиа — звёзды возвращаются пользователю через `user.add_pages(total_cost)`
- 3 retry с задержкой 60 сек

**Translate to English**: если у нейросети `translate_to_english=True`, промт переводится через DeepSeek V3 (laozhang.ai) перед отправкой в модель изображений/видео.

### `api` — DRF API-слой (`/api/v1/`)

OpenAI-совместимый API для внешних клиентов, IDE-интеграций и фронтенда Next.js.

**Структура:**
- `authentication.py` — JWT + APIKey аутентификация
- `throttling.py` — rate limiting
- `exceptions.py` — кастомные обработчики ошибок
- `serializers/`, `services/`, `views/` — разбиты по доменам (views: chat, chats, images, audio, embeddings, batch, keys, webhooks, audit, billing, invoices, usage, referral, teams, catalog, projects, prompts, files, uploads, compare, blog, legal, anthropic, api_status, auth, models_list, telegram_link, telegram_webapp)
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
- `/teams` — B2B
- `/studio/` — Vibe-Coding Studio (включён через `include('studio.urls')`)
- `/telegram/link-token/`, `/telegram/webapp-auth/` — привязка аккаунта и авторизация Mini App
- `/webhooks` — управление вебхуками (HMAC-подпись исходящих событий)
- `/audit` — audit log
- `/blog`, `/legal` — контент
- `/anthropic` — Anthropic-совместимый endpoint
- `/status` — статус сервиса

### `teams` — B2B (организации)

**Модели:** `Organization`, `Member`, `OrgInvite`, `OrgInvoice`.
**Функционал:** орг-биллинг (общий баланс/счета), usage по членам организации. Frontend — группа `(dashboard)/`: `/dashboard/organization/`, `/dashboard/usage/`.

### `blog` — блог

- `Category`, `Post` — статьи с SEO-полями, привязка к нейросетям (M2M), `show_in_notification`, `show_on_main`
- Management-команда `create_seo_posts` — генерация SEO-статей (контент-машина через DeepSeek/Celery)
- Раздаётся через DRF (`/api/v1/blog`) и рендерится на Next.js (`/blog/`, SSR + ISR)

### `telegram_bot` — Telegram-бот (aiogram 3) + Mini App

Полноценный AI-ассистент в Telegram. Webhook монтируется в `config/urls.py` при `TELEGRAM_BOT_ENABLED=1` на `/telegram/webhook/`.

**Модели:**
- `TelegramUser` — привязка к `CustomUser`, дефолтные модели (текст/изображение/видео), настройки (голос, веб-поиск, system_prompt, streaming), дневные счётчики
- `TelegramChat` — FK на `aitext.Chat` (несколько чатов на пользователя, `is_active`)
- `TelegramLinkToken` — одноразовый токен привязки аккаунта (TTL 15 мин)
- `TelegramEvent` — аналитика событий (message/image/video/payment/inline/error/onboarding/task_run/research/business_reply/subscription/affiliate_join)
- `AITask` — проактивные AI-задачи по расписанию (S2, общие для веба и бота, лимиты по тарифам, идемпотентный биллинг `aitask:{id}:{run_iso}`)
- `StarsSubscription` — подписка на тариф через Telegram Stars (S4)
- `BusinessConnection` / `BusinessDraft` — AI-секретарь для Telegram Business (S5, черновики с TTL 7 дней)
- `TelegramTopic` — топик в личке ↔ проект (S7), `GroupMessageLog` — лог для /summary (TTL 48 ч)
- `ManagedBot` — персональные AI-боты пользователей (S8, webhook-мультиплексор `/telegram/managed/<id>/webhook/`)

**Хендлеры (`handlers/`):** start, onboarding, menu, chat, images, video_cmd, voice, files, history, balance, payment (вкл. Stars-подписки /subscribe), models_cmd, settings_cmd, prompts_cmd, referral, inline, group, group2 (/summary, /quiz, /stat), admin (вкл. /paidpost, /affstats), tasks_cmd (/task, /tasks), research_cmd (/research), business (/secretary), topics (/topics), mybot_cmd (/mybot).

**TELEGRAM_SUPREMACY_PLAN (S0–S8 реализованы):** фиче-флаги Bot API 9.3+/10.1 в env (`TG_NATIVE_STREAMING`, `TG_RICH_MESSAGES`, `TG_STARS_SUBSCRIPTIONS`, `TG_BUSINESS`, `TG_AFFILIATE`, `TG_GIFTS`, `TG_TOPICS`, `TG_MANAGED_BOTS` — все по умолчанию 0); `capabilities.py` (детект поддержки aiogram), `rich.py` (md→Rich-блоки, юнит-тесты `test_rich.py`), `notify.py` (`DraftStreamer` — нативный стриминг с edit-fallback, `send_rich_or_markdown`, реакции-статусы). AI-задачи: Celery `run_due_ai_tasks`/`execute_ai_task`, веб-зеркало `/api/v1/tasks/` + `/account/tasks/`. Deep Research в боте реюзает `deep_research_task` (цена `RESEARCH_PRICE_KOPECKS`). Mini App 2.0 (`/tg/`): экраны Баланс/Галерея/Чат, `lib/telegram-webapp.ts`, JWT добавлен в DRF-аутентификацию, эндпоинты `/telegram/webapp/files/` и `/telegram/webapp/prepare-share/`. Тариф «Бизнес» в `setup_tariffs`, лендинг `/business-bot/`.

**Особенности:**
- FSM на отдельной Redis-БД (`TELEGRAM_FSM_REDIS_URL`, db=2)
- Reply-клавиатура с меню, онбординг-FSM, deeplinks
- Платежи через Telegram Stars (XTR) + кастомная сумма
- Стриминг ответов через `edit_message` с троттлингом (мин. 3.5 сек)
- Приём фото/документов → `FileAttachment`; голос ASR/TTS
- Inline-режим и групповой режим
- Admin-команды + рассылка (FSM)
- Mini App `/tg/` — авторизация по `initData` (HMAC) с выдачей JWT (`api/views/telegram_webapp.py`)

**Celery-задачи:** `notify_low_balance()`, `broadcast_message()`.
**Management-команды:** `run_bot` (polling-режим для разработки), `setup_webhook`.

### `studio` — Vibe-Coding Studio (AI-конструктор приложений)

AI-конструктор, который по описанию или клонированию URL генерирует фронтенд-приложение через многоагентный пайплайн в Docker-песочнице, версионирует код в Gitea и деплоит. Эндпоинты под `/api/v1/studio/`, UI — `frontend/app/studio/`.

**Модели (`studio/models.py`):**
- `StudioProject` — проект: `status` (draft/interview/planning/ready/coding/paused/completed/failed), `mode` (auto/semi/manual), `entry_mode` (description/clone_url), `target_stack` (nextjs/react/vue/html/tma), `deploy_target` (none/vercel/timeweb/selectel/tma), `interview_data`, `project_md_content` / `commits_md_content` / `design_md_content`, `sandbox_container_id`, `repo_url`, `stars_reserved` / `stars_spent`, `ai_model`, `agent_models` (per-agent override), `max_iterations`, `max_stars_budget`, `forked_from`, `github_repo_url`, `screenshot`
- `StudioFile` — файл проекта (path, content, language)
- `StudioPipelineState` — состояние пайплайна (status, step_index, iteration_count, отчёты review/test, fix_plan, флаги паузы, счётчики автофиксов и повторных ошибок)
- `StudioVersion` — версия (git_sha, шаг, потраченные звёзды) для отката/ветвления
- `StudioCollaborator` — соавторы проекта (viewer/editor)
- `StudioTemplate` — публичные шаблоны (slug, stack, seed_prompt, features, usage_count)

**Пайплайн (`studio/tasks.py` → `run_pipeline`, очередь `studio_queue`):**
- Текущая рабочая версия — 3-ролевой пайплайн: **architect** (Opus, один раз — PROJECT.md + COMMITS.md), **coder** (Qwen3 Coder Plus, на каждый шаг), **guardian** (Sonnet/Gemini, review+test+fixplan на каждый шаг)
- В `studio/agents/` есть и legacy-агенты (interviewer, analyst, planner, reviewer, tester, fixer, explainer, deviation, screenshot, assistant) — сохранены для совместимости и вспомогательных задач
- Структурные гейты (валидация FILE_BLOCKS/EDIT-блоков), проверка зависимостей, детект зацикливания (одинаковый diff / повторяющиеся ошибки), автофикс
- SSE-события пайплайна через `studio/events.py` (фронт читает `/projects/<id>/events/`)
- Каждый шаг коммитится; превью поднимается в песочнице и проксируется через nginx

**Инфраструктура Studio:**
- `sandbox.py` — управление Docker-песочницами (создание/реап контейнеров, лимиты памяти/CPU, сеть `aineron_sandbox_net`)
- `gitea_client.py` — работа с Gitea (создание репозиториев, коммиты)
- `crawler.py` — клонирование сайта по URL (entry_mode=clone_url)
- `scaffold.py` — стартовые скелеты проектов по стеку
- `billing.py` — биллинг по токенам/тиру моделей (см. ниже)
- `security.py`, `validators.py`, `deviation.py`, `screenshot.py` (Playwright) — безопасность, валидация, скриншоты
- `models_catalog.py` — единый каталог LLM-моделей Studio с тирами и картой эскалации
- Management-команда `seed_templates` — посев шаблонов

**Биллинг Studio (`billing.py`):**
- Тиры: `STAR_RATE = {'fast': 1, 'coder': 1.7, 'smart': 3}` (звёзд на 1000 токенов)
- `AGENT_BUDGET` задаёт тир и бюджет токенов на агента; стоимость резервируется до запуска и списывается из резерва
- При ошибке шага звёзды возвращаются; `max_stars_budget` ограничивает проект

**Флаги STUDIO_V4 (по умолчанию ВЫКЛЮЧЕНЫ, в разработке):** `STUDIO_V4_TOKEN_BILLING`, `STUDIO_V4_COMMITS_CACHE`, `STUDIO_V4_PROVIDER_FALLBACK`, `STUDIO_V4_AUTOFIX`, `STUDIO_V4_STREAMING`, `STUDIO_V4_GUARDIAN_CONTEXT`, `STUDIO_V4_RU_STACK` (GigaChat), `STUDIO_V4_TMA`. Текущее поведение по умолчанию = пайплайн V3 (`STUDIO_V3`).

### `sandboxes` — Sandbox API (публичные песочницы)

Публичный продукт `/api/v1/sandboxes/` (план: `SANDBOX_API_PLAN.md`) — изолированные
E2B microVM для исполнения недоверенного кода (AI-агенты, EdTech). Работает через
`preview-service` (namespace `/sandbox/*`), Studio не нужна.

- **Модель** `SandboxSession` — durable-источник биллинга (reserve → settle, идемпотентно по reference `sandbox:{id}:…`)
- **Биллинг**: `billing.py` поверх `spend_kopecks/add_kopecks`; цены `SANDBOX_PRICE_KOPECKS` (small 50, standard 100 коп./мин)
- **Квоты**: `quotas.py` — дневной кап минут (Redis) + одновременные сессии (БД)
- **Celery**: `reconcile_sandbox_billing` (*/5 мин), `check_sandbox_abuse` (*/10), `check_sandbox_runrate` (*/15)
- **DRF**: `api/views/sandboxes.py`, скоуп ключа `sandboxes` (не выдаётся по умолчанию), Idempotency-Key, троттлинг 10 create/мин, 30 exec/мин
- **SDK**: `sdk/python` — пакет `aineron` (PyPI)
- **Флаг**: `SANDBOX_API_ENABLED=0` — выключен до разблокировки E2B-аккаунта (чеклист в плане §10)

### `landing` — legacy лендинг

- Старый Django-лендинг (legacy, основной лендинг теперь на Next.js)
- Кастомный обработчик 404: `landing.views.custom_404_view`

---

## Видео модели — ТЕКУЩЕЕ СОСТОЯНИЕ

5 видео-моделей через management-команду `add_video_models`, провайдер: **apimart.ai**.

| Модель | `model_name` (apimart) | Стоимость |
|--------|------------------------|-----------|
| Sora 2 | `sora-2` | 60 звёзд |
| Sora 2 Pro | `sora-2-pro` | 100 звёзд |
| Veo 3.1 Fast | `veo3.1-fast` | 50 звёзд |
| Veo 3.1 | `veo3.1-quality` | 100 звёзд |
| Kling v2.6 | `kling-v2-6` | 40 звёзд |

Видео-генерация реализована в `src/aitext/fal_utils.py` → `generate_video_apimart()`.

**Все модели через единый apimart.ai endpoint:**
- Создание задачи: `POST https://api.apimart.ai/v1/videos/generations` — JSON body
- Проверка статуса: `GET https://api.apimart.ai/v1/tasks/{task_id}`
- Результат: `status_response.result.videos[].url` (url может быть строкой или массивом)
- Роутинг в коде: `config_json.metadata.video_api == 'apimart'`
- Ключ: `APIMART_API_KEY` в `.env`

**Параметры по моделям:**
- **Sora 2 / Sora 2 Pro**: `duration` (5/10/20 сек), `aspect_ratio` (16:9 / 9:16)
- **Veo 3.1 Fast / Quality**: `duration=8` (фиксировано), `aspect_ratio`, `resolution` (720p/1080p/4k)
- **Kling v2.6**: `mode` (std=720p / pro=1080p), `duration` (5/10 сек), `aspect_ratio` (16:9/9:16/1:1), **`audio`** (bool, только в pro mode), `negative_prompt`

**Особенности:**
- Polling до 15 минут — 60 попыток × 15 секунд
- При любой ошибке генерации звёзды возвращаются пользователю
- Ссылки на видео действительны 24 часа (скачиваем и сохраняем локально)

---

## Веб-поиск (Tavily)

Чат поддерживает режим веб-поиска для текстовых моделей.

- Провайдер: **Tavily API** (1000 запросов/месяц бесплатно, tavily.com)
- Ключ: `TAVILY_API_KEY` в `.env`
- Реализация: `call_web_search()` в `src/aitext/tasks.py`
- UI: toggle «Интернет» в поле ввода чата (frontend) и тоггл `web_search` у `TelegramUser`
- Flow: при включённом тоггле перед вызовом LLM выполняется поиск, результаты подмешиваются в контекст сообщения
- Тест: `docker-compose exec web python manage.py test_search "запрос"`

---

## Биллинг: рублёвый баланс в копейках (миграция со «звёзд»)

Инвариант: **1 звезда (legacy) = 1 рубль = 100 копеек**. Полный план миграции — `BILLING_MIGRATION_PLAN.md`.

- **Источник истины** — `CustomUser.balance_kopecks` (BigInteger). `pages_count` — legacy dual-write поле (звёзды), синхронизируется автоматически при каждой операции, будет удалено в фазе R2 (cleanup).
- **Money-утилиты**: `src/core/money.py` (`format_rub`, `rub_to_kopecks`, `kopecks_to_rub`, `apply_min_charge`, `get_min_charge_kopecks`) и `frontend/lib/money.ts` (`formatRub`, `kopecksToRub`, `rubToKopecks`) — единственное место форматирования сумм.
- **Атомарные операции баланса** (`CustomUser`, `src/users/models.py`): `spend_kopecks(amount, type, reference)`, `add_kopecks(...)`, `set_kopecks(...)`, `has_enough_kopecks(...)`. Все — через condition `UPDATE ... WHERE balance_kopecks >= amount` (без TOCTOU-гонки) и пишут запись в `BalanceTransaction` (ledger). Если `reference` непустой — операция идемпотентна по `(type, reference)`: повтор (ретрай Celery/вебхука) не спишет/не начислит дважды.
- **Legacy-обёртки** `spend_pages`/`add_pages`/`set_pages`/`has_enough_pages` — тонкие обёртки ×100 над kopecks-методами, оставлены для необновлённых call sites.
- **Цена сообщения**: `NeuralNetwork.cost_kopecks` — авторитетное поле (поддерживает дробные ₽, например 50 = 0,50 ₽). `cost_per_message` (legacy, целые звёзды) выводится из него один раз при создании записи, дальше поля независимы — редактируйте любое.
- **Минимальное списание**: `settings.MIN_CHARGE_KOPECKS` (env, дефолт 10 = 0,10 ₽) — защита от списаний в доли копейки при токенном биллинге.
- Новый пользователь получает `free_tariff.balance_grant_kopecks` (обычно 1000 коп. = 10 ₽)
- При ошибке генерации — средства возвращаются через `add_kopecks(..., type='refund', reference=...)`
- Покупка тарифа/пополнение — через `add_kopecks(..., type='subscription'|'topup', reference=invoice_id)`, идемпотентно к повтору вебхука Robokassa
- Telegram Stars (XTR) — только способ оплаты, начисляет рубли на единый баланс (`type='xtr'`, `reference=telegram_payment_charge_id`)
- Промокоды: `PromoCode.kopecks` (авто-синхронизировано с `stars` ×100)
- Безлимит: если `network.unlimited=True` и у пользователя тариф из `network.tariffs`, то сообщения бесплатны до `messages_limit` в день
- Studio резервирует и списывает копейки по тирам моделей (`src/studio/billing.py`, `KOPECK_RATE`) — та же идемпотентная схема через `reference=f'studio:{project_id}:{agent}:{step}'`
- Организационный биллинг (Telegram-группы, `teams.Organization.balance_rub`) унифицирован с личным тарифом: `settings.ORG_KOPECKS_PER_STAR` (дефолт 100 — то есть 1:1)
- **API-совместимость** (`/api/v1`): старые поля (`pages_count`, `cost_per_message`, `new_balance`, `stars_charged`) сохранены как алиасы; новые поля с суффиксом `_kopecks` — авторитетные

---

## Платежи

**Robokassa (веб) `[.ru]`:**
- Подпись MD5: `MerchantLogin:OutSum:InvId:Receipt(JSON):Password1` кодируется в UTF-8 или CP1251 в зависимости от типа платежа
- Result URL (POST): `/users/api/payment/success/` — верифицирует подпись `OutSum:InvId:Password2`, активирует тариф
- Recurring платежи: POST на `https://auth.robokassa.ru/Merchant/Recurring` с `PreviousInvoiceID`
- Тестовый режим: `ROBOKASSA_TEST_MODE=0` (production)

**Telegram Stars (XTR, в боте) — оба инстанса:** пополнение баланса через нативные платежи Telegram (`handlers/payment.py`), поддержка кастомной суммы. Это нативная платёжная система Telegram, не связана с legacy-полем `pages_count` («звёздами» из старого биллинга).

**Криптовалюта (Crypto Pay / @CryptoBot) `[.net]`:** пополнение баланса в USDT/TON, фиатный инвойс в RUB (`src/users/crypto_payments.py`, views `src/api/views/crypto.py`). Включается `CRYPTO_PAY_ENABLED=1` — при 0 фронт скрывает блок оплаты (флаг отдаётся через `GET /api/v1/billing/crypto/`). На aineron.ru этот флаг выключен, платёжный код в репозитории общий, но путь неактивен. Зачисление идемпотентно (`reference='crypto:{invoice_id}'`) и работает двумя путями: вебхук `/users/api/payment/crypto/webhook/` (HMAC-подпись) и поллинг статуса фронтом (сам опрашивает Crypto Pay — вебхук не обязателен). Тесты: `api/tests_crypto.py`.

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
  "metadata": { "requires_input_images": false, "video_api": "apimart" }
}
```
`extra_cost` в поле — дополнительные звёзды за настройку.

---

## Переменные окружения (`.env`)

Ниже — общий пример на базе `.env` для aineron.ru. На aineron.net (`.env` на intl-сервере) главное отличие — `INTL_MODE=1` (переключает язык инстанса, биллинг-режим и часть UI, см. «Два инстанса, один репозиторий»); остальные `[.net]`-пометки ниже — по конкретным флагам.

```
SECRET_KEY=
DEBUG=0
DJANGO_ALLOWED_HOSTS=aineron.ru www.aineron.ru localhost 127.0.0.1

# Инстанс: 0 = aineron.ru (по умолчанию), 1 = aineron.net
INTL_MODE=0

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

# Платежи (Robokassa)
ROBOKASSA_LOGIN=
ROBOKASSA_PASS1=
ROBOKASSA_PASS2=
ROBOKASSA_TEST_MODE=0

# Платежи (криптовалюта, Crypto Pay / @CryptoBot) — [.net], на aineron.ru выключено (CRYPTO_PAY_ENABLED=0)
CRYPTO_PAY_ENABLED=0           # 1 = включить оплату криптой (фронт показывает блок по флагу из API)
CRYPTO_PAY_TOKEN=              # токен приложения из @CryptoBot → Crypto Pay
CRYPTO_PAY_ASSETS=USDT,TON     # принимаемые активы
# CRYPTO_PAY_API_URL=https://pay.crypt.bot/api  (testnet: https://testnet-pay.crypt.bot/api)

# AI провайдер (laozhang.ai) — текст и изображения
LAOZHANG_API_KEY=
LAOZHANG_API_URL_FALLBACK=     # резервный base_url (Studio V4 provider fallback)
SEEDANCE_API_KEY=              # legacy, больше не используется

# APIMart — видео генерация (Sora, Veo, Kling)
APIMART_API_KEY=               # apimart.ai — https://apimart.ai/

# Автофолбэк между сервисами: текст/изображения laozhang→apimart, видео apimart→laozhang
AI_PROVIDER_FALLBACK=1         # 1 = включён (по умолчанию), 0 = выключить

# Веб-поиск
TAVILY_API_KEY=                # tavily.com — 1000 req/month free

# Telegram-бот
TELEGRAM_BOT_ENABLED=0         # 1 = монтировать webhook
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_BOT_USERNAME=aineron_bot
TELEGRAM_ADMIN_IDS=            # через запятую

# Vibe-Coding Studio
STUDIO_SANDBOX_IMAGE=aineron-sandbox:latest
STUDIO_SANDBOX_NET=aineron_sandbox_net
STUDIO_SANDBOX_MEM=512m
STUDIO_SANDBOX_CPUS=1
STUDIO_GITEA_URL=http://gitea:3000
STUDIO_GITEA_ADMIN_USER=studio_admin
STUDIO_GITEA_ADMIN_TOKEN=
STUDIO_MAX_ITERATIONS=3
STUDIO_MAX_SANDBOXES_PER_USER=5
STUDIO_VERCEL_TOKEN=
STUDIO_PROMPT_LANG=en          # en | ru
STUDIO_V3=0                    # 1 = пайплайн V3
# STUDIO_V4_* флаги (все по умолчанию 0): TOKEN_BILLING, COMMITS_CACHE,
# PROVIDER_FALLBACK, AUTOFIX, STREAMING, GUARDIAN_CONTEXT, RU_STACK, TMA
TIMEWEB_API_TOKEN=             # деплой Timeweb Cloud
SELECTEL_ACCOUNT_ID=
SELECTEL_API_KEY=
STUDIO_TMA_BOT_TOKEN=

# Sandbox API (SANDBOX_API_PLAN.md)
SANDBOX_API_ENABLED=0          # 1 = включить /api/v1/sandboxes/ (нужен живой preview_service + E2B)
SANDBOX_PRICE_SMALL_KOPECKS=50
SANDBOX_PRICE_STANDARD_KOPECKS=100
SANDBOX_DAILY_CAP_MIN=240
SANDBOX_MAX_CONCURRENT_PER_USER=3

# Gitea
GITEA_DB_PASSWORD=

# Сайт
SITE_URL=https://aineron.ru
SITE_NAME=aineron.ru

# Frontend (Next.js)
NEXT_PUBLIC_API_URL=           # базовый URL Django API для фронтенда
NEXT_PUBLIC_SITE_URL=
```

---

## Docker Compose

Два отдельных compose-файла — по одному на инстанс (см. «Два инстанса, один репозиторий» выше), не смешивать.

### `docker-compose.yml` `[.ru]` — 11 сервисов

| Сервис | Образ/build | Описание |
|--------|-------------|----------|
| `redis` | redis:7-alpine | Брокер Celery, кэш сессий, FSM бота |
| `db` | postgres:15-alpine | PostgreSQL (основная БД) |
| `web` | build (Dockerfile) | Django + Gunicorn, :8000 (makemigrations+migrate при старте) |
| `celery_worker` | build (Dockerfile) | Celery gevent, concurrency 200 (общая очередь) |
| `celery_beat` | build (Dockerfile) | Периодические задачи (DatabaseScheduler) |
| `celery_studio` | build (Dockerfile) | Celery для Studio (`studio_queue`), доступ к `docker.sock` |
| `celery_studio_playwright` | build (Dockerfile.playwright) | Скриншоты/проверки Studio (`studio_playwright_queue`, prefork) |
| `gitea_db` | postgres:15-alpine | БД для Gitea |
| `gitea` | gitea/gitea:1.22 | Git-хостинг репозиториев Studio, ROOT_URL `/git/` |
| `frontend` | build (Dockerfile.frontend) | Next.js 14, :3000 |
| `nginx` | nginx:1.25-alpine | SSL termination, роутинг, :80/:443 |

Volumes: `postgres_data`, `redis_data`, `static_volume`, `gitea_data`, `gitea_db_data` (медиа — bind-mount `./src/media`).
Сети: `default` + `aineron_sandbox_net` (internal) — для песочниц Studio.

### `docker-compose.intl.yml` `[.net]` — 8 сервисов

Отдельный сервер, отдельная БД, свой `.env`. Без `celery_studio`/`celery_studio_playwright`/`gitea`/`gitea_db` — Studio на этом инстансе структурно не задеплоена (не просто выключена флагом). Сервисы: `redis`, `db`, `web`, `daphne` (SSE/WebSocket), `celery_worker`, `celery_beat`, `frontend`, `nginx`. Запуск: `docker compose -f docker-compose.intl.yml up -d --build` (см. `deploy_intl.sh`).

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
docker-compose exec web python manage.py seed_templates          # шаблоны Studio
docker-compose exec web python manage.py setup_webhook           # webhook Telegram-бота
```

---

## Аутентификация

**Web / Next.js:**
- Кастомная модель `CustomUser` (email как логин, username генерируется из email)
- django-allauth для социальных провайдеров: Google, Yandex, VK, Mail.ru, GitHub
- JWT (simplejwt) для запросов фронтенда к API
- Email верификация: 6-значный код в поле `email_verification_code`
- Shadow ban: автоматически при регистрации с уже использованного IP

**Telegram:**
- Привязка аккаунта по одноразовому токену (`TelegramLinkToken`, deeplink в бота)
- Mini App: авторизация по `initData` (HMAC) с выдачей JWT

**API (внешние клиенты):**
- `APIKey` модель — аутентификация внешних запросов к `/api/v1/`
- OpenAI-совместимый формат (Bearer token), throttling по ключу

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

**Проверка баланса перед запросом** (актуальный паттерн — копейки, не legacy `pages_count`):
```python
if not request.user.has_enough_kopecks(cost_kopecks):
    return JsonResponse({'success': False, 'message': 'Недостаточно средств на балансе...'})
```

**Celery retry при ошибке API:**
```python
raise self.retry(exc=e, countdown=60)  # max_retries=3
```

**Безопасность медиа-генерации**: при любой ошибке генерации изображений/видео звёзды возвращаются через `user.add_pages(total_cost)`. В Studio — возврат из резерва при ошибке шага.

**Singleton-настройки**: `SiteSettings.get_settings()`, `PageSaleSettings.get_settings()` — `get_or_create(id=1)`.

**SSE streaming**: текстовые ответы стримятся через EventSource на фронте; Celery-задача пишет токены, фронт отображает с адаптивным дренажём токенов. Studio использует SSE для событий пайплайна (`studio/events.py`).

---

## Реферальная программа

- Каждый пользователь имеет уникальный `referral_code` (8 символов)
- При регистрации через `/?ref=CODE` — устанавливается `user.referrer`
- При покупке тарифа — рефереру начисляется `tariff.referral_bonus` руб. или `tariff.referral_bonus_stars` звёзд
- Пользователи с `can_convert_to_rub=True` получают рублёвый баланс и могут заказать вывод на карту
- Frontend: `/account/referral/`; в боте — `handlers/referral.py`

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
- Скрипт проверки: `scripts/check_no_emoji.py`

---

## Статус проекта (ROADMAP)

Базовые 6 фаз платформы (SEO → DRF API → Next.js инфраструктура → миграция страниц → B2B → SEO-блог/Analytics → Embeddings/Audio/Batch/Webhooks/Audit/Status) — **завершены**.

Дополнительно реализованы крупные продукты сверх первоначального ROADMAP:
- **Telegram-бот** — ЗАВЕРШЁН (aiogram 3: FSM, меню, онбординг, чат, изображения, видео, голос, файлы, история, платежи Stars, inline/групповой режим, admin/рассылка, аналитика, Mini App `/tg/`).
- **Vibe-Coding Studio** — **заморожена** (была РАБОТАЕТ: V3-пайплайн architect/coder/guardian, песочницы, Gitea, биллинг по тирам, шаблоны, экспорт в GitHub, деплой — код рабочий и остаётся в репозитории). На aineron.ru выключена флагом `STUDIO_ENABLED=false`, на aineron.net сервисов Studio/Gitea нет в `docker-compose.intl.yml` вообще. Не развиваем и не чиним, пока не будет решения возобновить. Набор флагов `STUDIO_V4_*` заморожен вместе с остальным.

Актуальный стратегический план развития — `TOP1_PLAN.md` (цель: TOP-1 Россия, фокус на UX, мультимодальности и Telegram-интеграции).

### НЕ реализовано
- **Persistent Memory** (RAG-память пользователя, общая для веба и бота) — план в `PERSISTENT_MEMORY_PLAN.md`

---

## Файлы: ключевые пути

### Backend

| Что | Где |
|-----|-----|
| Настройки Django | `src/config/settings.py` |
| Celery конфиг | `src/config/celery.py` |
| Корневые URL | `src/config/urls.py` |
| Money-утилиты (биллинг, копейки) | `src/core/money.py` |
| Модели пользователей | `src/users/models.py` |
| Модели нейросетей/чатов | `src/aitext/models.py` |
| AI-генерация (Celery task) | `src/aitext/tasks.py` |
| Веб-поиск (Tavily) | `src/aitext/tasks.py` → `call_web_search()` |
| Медиа/видео утилиты (apimart) | `src/aitext/fal_utils.py` → `generate_video_apimart()` |
| Файловые утилиты | `src/aitext/file_utils.py` |
| Форматирование кода | `src/aitext/code_formatter.py` |
| Команда видео-моделей | `src/aitext/management/commands/add_video_models.py` |
| Команда SEO-статей | `src/blog/management/commands/create_seo_posts.py` |
| DRF API URLs | `src/api/urls.py` |
| DRF API views | `src/api/views/` |
| API аутентификация | `src/api/authentication.py` |
| Модели API (APIKey, audit, webhooks) | `src/api/models.py` |
| Модели B2B | `src/teams/models.py` |
| Платежи (views) | `src/users/views.py` |
| Celery-задачи подписок | `src/users/tasks.py` |
| Middleware | `src/users/middleware.py` |
| Telegram-бот (модели) | `src/telegram_bot/models.py` |
| Telegram-бот (точка входа, хендлеры) | `src/telegram_bot/bot.py`, `src/telegram_bot/handlers/` |
| Telegram webhook view | `src/telegram_bot/views.py` |
| Studio модели | `src/studio/models.py` |
| Studio пайплайн (Celery) | `src/studio/tasks.py` → `run_pipeline()` |
| Studio агенты | `src/studio/agents/` (architect, coder, guardian + legacy) |
| Studio песочницы / Gitea / биллинг | `src/studio/sandbox.py`, `gitea_client.py`, `billing.py` |
| Studio каталог моделей | `src/studio/models_catalog.py` |
| Studio URLs / views | `src/studio/urls.py`, `src/studio/views/` |

### Frontend (Next.js)

| Что | Где |
|-----|-----|
| Корневой layout / провайдеры | `frontend/app/layout.tsx`, `frontend/app/providers.tsx` |
| Лендинг | `frontend/app/page.tsx` |
| Каталог моделей / чат | `frontend/app/models/`, `frontend/app/chat/` |
| Кабинет | `frontend/app/account/` (keys, analytics, billing, referral, files) |
| Model Arena / Projects / Prompts | `frontend/app/compare/`, `projects/`, `prompts/` |
| Studio UI | `frontend/app/studio/`, `frontend/components/studio/`, `frontend/lib/studio/` |
| Studio API-клиент | `frontend/lib/api/studio.ts` |
| Telegram Mini App | `frontend/app/tg/` |
| IDE-интеграции | `frontend/app/ide/` |
| Блог / API-docs / статус | `frontend/app/blog/`, `api-docs/`, `status/` |
| Группа авторизации / дашборда | `frontend/app/(auth)/`, `frontend/app/(dashboard)/` |
| API-клиент / сторы | `frontend/lib/api/` (client.ts, server.ts, types.ts), `frontend/lib/stores/` (auth.ts, ui.ts) |
| Money-утилиты (форматирование ₽) | `frontend/lib/money.ts` |
| Next.js middleware | `frontend/middleware.ts` |
| PWA / sitemap / robots | `frontend/app/manifest.ts`, `sitemap.ts`, `robots.ts` |

### Инфраструктура

| Что | Где |
|-----|-----|
| Docker Compose | `docker-compose.yml` |
| Backend / Frontend Dockerfile | `Dockerfile`, `Dockerfile.frontend` |
| Studio Dockerfile (Playwright / sandbox) | `Dockerfile.playwright`, `Dockerfile.sandbox` |
| Nginx | `nginx.conf` |
| Скрипты деплоя | `deploy.sh`, `pull.sh` |
| Стратегический план | `TOP1_PLAN.md` |
| План Persistent Memory (не реализован) | `PERSISTENT_MEMORY_PLAN.md` |
| Скрипт проверки эмодзи | `scripts/check_no_emoji.py` |
