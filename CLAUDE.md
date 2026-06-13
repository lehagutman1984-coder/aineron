# aineron.ru — CLAUDE.md

## Что это за проект

SaaS-платформа для доступа к AI-нейросетям без VPN. Пользователи покупают «звёзды» (внутреннюю валюту) и тратят их на каждое сообщение к нейросети. Поддерживает как текстовые LLM, так и генерацию изображений/видео — всё через единый провайдер api.laozhang.ai.

Домен: **aineron.ru** | Язык интерфейса: **русский**

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| Backend | Django 4.2, Python 3.11 |
| Task queue | Celery 5.6 + Redis 7 |
| Database | PostgreSQL 15 (SQLite только для тестов) |
| Auth | django-allauth 65 (Google, Yandex, VK, Mail.ru + email/password) |
| AI — текст | laozhang.ai (openai SDK, base_url: api.laozhang.ai/v1) |
| AI — медиа | laozhang.ai (openai SDK, images.generate API) |
| Платежи | Robokassa (recurring через POST /Merchant/Recurring) |
| Frontend | Vanilla JS + CSS, без фреймворков |
| Деплой | Docker Compose (6 сервисов) + Nginx reverse proxy |
| WSGI | Gunicorn (8 workers, 2 threads) |
| Celery pool | gevent, concurrency 200 |

---

## Структура папок

```
aineron.ru/
├── src/                        # Весь Python-код
│   ├── config/                 # Настройки Django, Celery, URLs
│   │   ├── settings.py         # Все настройки (из env-переменных)
│   │   ├── celery.py
│   │   └── urls.py             # Корневые URLs
│   ├── users/                  # Пользователи, тарифы, платежи, рефералы
│   ├── aitext/                 # Нейросети, чаты, сообщения, файлы
│   ├── blog/                   # Статьи и категории блога
│   ├── landing/                # Главная страница, 404
│   ├── static/neuro/           # JS и CSS файлы
│   ├── templates/neuro/        # HTML-шаблоны
│   ├── media/                  # Загруженные и сгенерированные файлы
│   └── requirements.txt
├── docker-compose.yml          # 6 сервисов: redis, db, web, celery_worker, celery_beat, nginx
├── Dockerfile                  # FROM python:3.11-slim
├── nginx.conf                  # SSL termination, static/media, proxy_pass → web:8000
├── deploy.sh                   # Скрипт деплоя (down → build → up → migrate → collectstatic)
└── .env                        # Секреты (не коммитить)
```

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
- `users/urls_api.py` → prefix `users/api/` — все AJAX-эндпоинты
- `users/urls_pages.py` → prefix `users/pages/` — HTML-страницы

**Middleware (в settings.py):**
- `ShadowBanMiddleware` — при регистрации с IP уже использованного пользователя автоматически ставит `shadow_banned=True`, редиректит на `/users/pages/blocked/`
- `EmailVerificationMiddleware` — редиректит на верификацию если email не подтверждён
- `UserActivityMiddleware` — логирует IP и дневную активность

**Celery-задачи:**
- `process_pending_renewals()` — каждые 12 ч: находит подписки, истекающие в течение 3 дней, делает recurring-платёж через Robokassa
- `notify_upcoming_expiration()` — уведомляет email за 3 дня до конца подписки (один раз)

### `aitext` — нейросети и чаты

**Модели:**
- `Category` — категории нейросетей (Фото, Видео, Аудио и т.д.)
- `NeuralNetwork` — нейросеть: `provider` (openrouter / fal-ai), `model_name`, `cost_per_message`, `unlimited` + `tariffs` (M2M безлимит для тарифов), `messages_limit` (дневной лимит бесплатных), `config_json` (для fal.ai), `handle_photo/video/archive/text_files`, SEO-поля
- `Chat` — чат пользователя с нейросетью, хранит `settings` (JSON с параметрами генерации)
- `Message` — сообщение (role: user/assistant), статусы pending/completed/failed, `plain_text` (без HTML), `extracted_content` (текст из вложений)
- `FileAttachment` — загруженный пользователем файл (image/video/audio/pdf/other), с извлечённым текстом
- `GeneratedImage` — сгенерированный AI файл (image или video), хранится в `media/generated_images/` или `media/generated_videos/`
- `NeuralNetworkDailyUsage` — счётчик бесплатных сообщений в день (per user+network+date)
- `FAQ` — вопросы-ответы, привязываются к нейросети или показываются глобально

**Ключевой flow чата:**
1. Пользователь POST → `create_chat` или `send_message`
2. Проверка баланса / бесплатного лимита
3. Создаётся `Message(role='assistant', status='pending')`
4. Для текстовых моделей — звёзды списываются сразу; для изображений/видео — в Celery-задаче
5. `generate_ai_response.delay(assistant_message.id)` — задача Celery
6. Frontend polling `message_status/{id}` пока status != completed/failed

**Celery-задача `generate_ai_response`:**
- **Текст** (provider=openrouter): собирает историю (последние 20 сообщений), вызывает `chat.completions.create`, форматирует ответ через `CodeFormatter`, обрабатывает base64-изображения в ответе
- **Изображения** (provider=fal-ai): валидирует настройки через `validate_and_merge_settings`, вызывает `client.images.generate`, скачивает и сохраняет медиа через `save_media_from_url`
- При ошибке генерации изображений — возвращает звёзды пользователю
- 3 retry с задержкой 60 сек

**Translate to English**: если у нейросети `translate_to_english=True`, промт переводится через DeepSeek V3 (laozhang.ai) перед отправкой в модель изображений

### `blog` — блог

- `Category`, `Post` — статьи с SEO-полями, привязка к нейросетям (M2M), `show_in_notification`, `show_on_main`

### `landing` — главная страница

- Пустая модель, только views и URLs
- Кастомный обработчик 404: `landing.views.custom_404_view`

---

## Валюта: «Звёзды» (pages_count)

- Новый пользователь получает `free_tariff.pages_count` звёзд (обычно 10)
- Каждое сообщение списывает `network.cost_per_message` звёзд
- При ошибке генерации изображений — звёзды возвращаются
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

## Конфигурация моделей изображений (`config_json`)

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

# Сайт
SITE_URL=https://aineron.ru
SITE_NAME=aineron.ru
```

---

## Docker Compose (сервисы)

| Сервис | Образ/build | Описание |
|--------|-------------|----------|
| `redis` | redis:7-alpine | Брокер Celery, кэш сессий |
| `db` | postgres:15-alpine | PostgreSQL |
| `web` | build . | Django + Gunicorn, :8000 |
| `celery_worker` | build . | Celery gevent, concurrency 200 |
| `celery_beat` | build . | Периодические задачи (DatabaseScheduler) |
| `nginx` | nginx:1.25-alpine | SSL termination, :80/:443 |

Volumes: `postgres_data`, `redis_data`, `static_volume`, `media_volume`
SSL сертификаты: `./ssl/fullchain.pem` и `./ssl/privkey.pem`

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

**Для тестов** (SQLite, без Docker):
```bash
cd src
python manage.py test
```

---

## Аутентификация

- Кастомная модель `CustomUser` (email как логин, username генерируется из email)
- django-allauth для социальных провайдеров: Google, Yandex, VK, Mail.ru
- AJAX-эндпоинты для регистрации/входа/восстановления пароля (не стандартные формы allauth)
- Email верификация: 6-значный код в поле `email_verification_code`
- Shadow ban: автоматически при регистрации с уже использованного IP

---

## SEO

- Sitemap: `/sitemap.xml` — NeuralNetworkSitemap, PostSitemap, StaticViewSitemap
- robots.txt: `/robots.txt` (из `src/static/robots.txt`)
- Каждая нейросеть, пост и категория блога имеют `seo_title`, `seo_description`, `seo_keywords`
- `SiteSettings` хранит глобальные SEO-мета и отдельные для блога и каталога

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

**Безопасность fal.ai**: при любой ошибке генерации звёзды возвращаются через `user.add_pages(total_cost)`.

**Singleton-настройки**: `SiteSettings.get_settings()`, `PageSaleSettings.get_settings()` — `get_or_create(id=1)`.

**Контекст-процессоры**: `user_balance`, `site_settings`, `current_site`, `site_counter`, `notification_posts`, `footer_networks` — доступны во всех шаблонах.

---

## Реферальная программа

- Каждый пользователь имеет уникальный `referral_code` (8 символов)
- При регистрации через `/?ref=CODE` — устанавливается `user.referrer`
- При покупке тарифа — рефереру начисляется `tariff.referral_bonus` руб. или `tariff.referral_bonus_stars` звёзд
- Пользователи с `can_convert_to_rub=True` получают рублёвый баланс и могут заказать вывод на карту

---

## Файлы: ключевые пути

| Что | Где |
|-----|-----|
| Настройки Django | `src/config/settings.py` |
| Celery конфиг | `src/config/celery.py` |
| Корневые URL | `src/config/urls.py` |
| Модели пользователей | `src/users/models.py` |
| Модели нейросетей/чатов | `src/aitext/models.py` |
| AI-генерация (Celery task) | `src/aitext/tasks.py` |
| fal.ai утилиты | `src/aitext/fal_utils.py` |
| Файловые утилиты | `src/aitext/file_utils.py` |
| Форматирование кода | `src/aitext/code_formatter.py` |
| Платежи (views) | `src/users/views.py` (payment_success, create_robokassa_payment, buy_pages) |
| Celery-задачи подписок | `src/users/tasks.py` |
| Middleware | `src/users/middleware.py` |
| Email-сервис | `src/users/email_service.py` |
| Адаптеры allauth | `src/users/adapters.py` |
| Шаблоны | `src/templates/neuro/` |
| JS | `src/static/neuro/js/` |
| CSS | `src/static/neuro/css/` |
