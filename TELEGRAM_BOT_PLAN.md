# aineron.ru — Telegram-бот: план TOP-1 Россия

> **Обновлён:** 2026-06-21 | Ветка: `studio-v3`
> **Цель:** лучший AI-бот в российском Telegram — полноценное приложение в TG

---

## Текущее состояние (реализовано)

- `/start` — привязка аккаунта через токен (переход на сайт)
- `/models` — выбор модели (3 вкладки: Текст / Изображения / Видео)
- `/image <промт>` — генерация изображения (polling 90 сек)
- `/video <промт>` — fire-and-forget видео (уведомление когда готово)
- `/balance` — баланс + кнопки пополнения
- `/settings` — настройки (голос, веб-поиск, системный промт)
- `/prompts` — библиотека промтов
- `/referral` — реферальная программа
- `/newchat` — новый чат
- `/help` — справка
- Голосовые сообщения (ASR + TTS)
- Текстовый чат с LLM
- Оплата через Telegram Stars (XTR)
- Уведомления через `maybe_notify()`, `send_media_to_telegram()`

---

## Критический архитектурный факт

**FSM сейчас сломан в production.**
`asyncio.run()` per-request + `MemoryStorage` = состояния умирают между webhook-запросами.
Все многошаговые сценарии нерабочие. **Сессия 1 — обязательный фундамент для всего остального.**

---

## Сессия 1 — Фундамент: RedisStorage FSM + главное меню + онбординг

**Цель**: Превратить бота из «консоли с командами» в интуитивный интерфейс

### Фичи

- **Персистентный FSM на RedisStorage**
  Подключить `RedisStorage.from_url()` к `Dispatcher` в `bot.py`. Состояния FSM переживают отдельные webhook-запросы. Ключ строится по `chat_id+user_id` — не зависит от пересоздаваемого `Bot`-инстанса. Разблокирует все FSM-флоу следующих сессий.

- **Главное меню (Reply Keyboard, 8 кнопок)**
  Постоянное, отправляется после `/start` и онбординга:
  - Ряд 1: «Чат», «Изображение»
  - Ряд 2: «Видео», «Баланс»
  - Ряд 3: «Модели», «Настройки»
  - Ряд 4: «История», «Помощь»
  Плейсхолдер: «Напиши вопрос или выбери раздел»

- **Menu-dispatch роутер**
  Заменить строковый матчинг кнопок в `handle_text_message` на единый словарь `{текст_кнопки: handler}`. Кнопки больше никогда не уходят в LLM как вопросы.

- **Онбординг новых пользователей (FSM, 3 шага)**
  После первой привязки аккаунта:
  1. Приветствие + что умеет бот с примерами
  2. Выбор основной текстовой модели через inline-кнопки
  3. Предложение задать первый вопрос или сгенерировать картинку

- **Команды в меню Telegram**
  `set_my_commands` с локализацией ru — синяя кнопка «Меню» рядом с полем ввода

### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/bot.py` | RedisStorage + `TELEGRAM_FSM_REDIS_URL` |
| `src/config/settings.py` | Добавить `TELEGRAM_FSM_REDIS_URL` (Redis DB=2) |
| `src/telegram_bot/keyboards.py` | `main_reply_kb()` — 8 кнопок |
| `src/telegram_bot/handlers/menu.py` | НОВЫЙ: menu-dispatch роутер |
| `src/telegram_bot/handlers/onboarding.py` | НОВЫЙ: `OnboardingFSM` |
| `src/telegram_bot/handlers/chat.py` | Убрать строковый матчинг кнопок |
| `src/telegram_bot/handlers/start.py` | После привязки → онбординг + `main_reply_kb()` |
| `src/telegram_bot/management/commands/setup_webhook.py` | `set_my_commands` |

### Результат
Пользователь всегда видит понятное меню. Новичок проходит онбординг и сразу делает первый запрос. Многошаговые сценарии технически работают.

---

## Сессия 2 — Монетизация и удержание: покупка FSM + проактивные уведомления

**Цель**: Гладкий флоу пополнения баланса + возврат пользователей через проактивные сигналы

### Фичи

- **FSM-флоу покупки звёзд**
  Способ оплаты (XTR / Robokassa) → пакет → подтверждение → инвойс.
  Для Robokassa — deeplink на `/account/billing/` с предзаполненным пакетом.

- **Кастомная сумма звёзд**
  Шаг «Своя сумма» — FSM просит число, валидирует по `PageSaleSettings`, считает XTR, выставляет инвойс.

- **Уведомление о низком балансе**
  Celery-задача `notify_low_balance`: при балансе < стоимости одного сообщения шлёт уведомление с inline-кнопкой «Пополнить». Дедупликация в Redis — не спамить.

- **Реферальные уведомления**
  При начислении реферального бонуса → `maybe_notify` рефереру.

- **Кнопки «Ещё / Поделиться»** при уведомлении о готовом видео

### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/handlers/payment.py` | `PurchaseFSM`: 3 шага + кастомная сумма |
| `src/telegram_bot/keyboards.py` | Клавиатуры выбора способа/пакета/подтверждения |
| `src/telegram_bot/tasks.py` | НОВЫЙ Celery: `notify_low_balance` |
| `src/users/tasks.py` | Хук реферального начисления → `maybe_notify` |
| `src/config/settings.py` / beat | Расписание `notify_low_balance` |

### Результат
Пополнение — плавный диалог, не одна кнопка. Пользователь не «отваливается» молча.

---

## Сессия 3 — Контент-паритет: история чатов + файлы и фото

**Цель**: Дать пользователю историю диалогов и приём файлов — паритет с сайтом

### Фичи

- **История чатов**
  Кнопка «История» → список последних чатов (из модели `Chat`), inline-пагинация.
  Тап → загружает сообщения, делает чат активным (`TelegramChat.chat`).

- **Возобновление контекста**
  При выборе старого чата — история как контекст для LLM (последние 20 сообщений).

- **Приём фото для анализа**
  Handler на `F.photo` → `FileAttachment` → мультимодальная модель (если `handle_photo`).

- **Приём документов**
  Handler на `F.document` (pdf/txt/docx) → `file_utils.py` → текст в контекст.

- **Image-to-image**
  Фото + подпись-промт → image-модель с `requires_input_images`.

### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/handlers/history.py` | НОВЫЙ: список, пагинация FSM, активация чата |
| `src/telegram_bot/handlers/files.py` | НОВЫЙ: handlers `F.photo` и `F.document` |
| `src/telegram_bot/handlers/chat.py` | Учёт `extracted_content` вложений |
| `src/telegram_bot/keyboards.py` | Клавиатуры истории и пагинации |

### Результат
Продолжение прошлых диалогов в боте, анализ фото и документов.

---

## Сессия 4 — Telegram Mini App + глубокая интеграция с сайтом

**Цель**: Встроенный интерфейс биллинга/аналитики/настроек внутри Telegram, синхронный с сайтом

### Фичи

- **WebApp на Next.js** (`/tg/`)
  Лёгкий интерфейс под Telegram WebApp SDK: баланс, графики трат, покупка, настройки, реферал.
  Тема из `Telegram.WebApp.themeParams` (dark mode поддержан).

- **Валидация `initData`**
  DRF-эндпоинт принимает `initData`, валидирует HMAC по `TELEGRAM_BOT_TOKEN`, выдаёт существующий JWT simplejwt. Без нового механизма авторизации.

- **Кнопка «Открыть приложение»**
  `set_chat_menu_button` с `WebAppInfo` — кнопка рядом с полем ввода.

- **Синхронизация настроек**
  Изменения в Mini App пишутся в `TelegramUser` через DRF, мгновенно отражаются в боте.

- **Deeplinks**
  - `?start=model_<slug>` — открывает чат с конкретной моделью
  - `?start=prompt_<id>` — открывает промт
  - `?start=ref_<code>` — реферал (уже частично есть)
  - «Открыть в Telegram» на страницах моделей и промтов сайта

### Файлы

| Файл | Действие |
|------|----------|
| `frontend/app/tg/` | НОВЫЙ маршрут: WebApp UI |
| `frontend/lib/telegram-webapp.ts` | НОВЫЙ: обёртка Telegram WebApp SDK |
| `src/api/views/` | НОВЫЙ: `telegram_webapp_auth` (initData → JWT) |
| `src/api/urls.py` | `/api/v1/telegram/webapp-auth` |
| `src/telegram_bot/keyboards.py` | `WebAppInfo` кнопки |
| `src/telegram_bot/management/commands/setup_webhook.py` | `set_chat_menu_button` |
| `src/telegram_bot/handlers/start.py` | Парсинг `model_`, `prompt_` deeplinks |
| `frontend/app/models/[slug]/` | Кнопка «Открыть в Telegram» |

### Результат
Биллинг, аналитика и настройки в богатом интерфейсе внутри Telegram. Шаринг моделей и промтов через нативные ссылки.

---

## Сессия 5 — Inline-режим и групповой режим

**Цель**: AI из любого чата Telegram + работа в группах

### Фичи

- **Inline-режим** (`@bot <запрос>` из любого чата)
  Ответ через `inline_message_id` + дозапись результата по завершении Celery-задачи.
  Неавторизованным — результат с приглашением привязать аккаунт.

- **Групповой режим**
  Ответ только на reply на свои сообщения или @упоминание.
  Плательщик — `from_user.id` (тот кто упомянул).
  Rate-limit для групп.

- **Операционные шаги BotFather**
  `/setinline`, `/setjoingroups`, решение по `/setprivacy`.

### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/handlers/inline.py` | НОВЫЙ: inline_query + chosen_inline_result |
| `src/telegram_bot/handlers/group.py` | НОВЫЙ: фильтры mention/reply, rate-limit |
| `src/telegram_bot/middlewares.py` | Групповой rate-limit |
| `src/telegram_bot/notify.py` | `edit_message_text` по `inline_message_id` |

### Результат
AI одним @упоминанием из любого диалога. Бот в группах без спама.

---

## Сессия 6 — Admin-команды и аналитика

**Цель**: Управление ботом из Telegram + метрики использования

### Фичи

- **Admin-команды** (доступ по `TELEGRAM_ADMIN_IDS`)
  `/stats` — DAU/WAU, сообщения, выручка XTR
  `/broadcast` — FSM-рассылка (Celery, 30 msg/s, прогресс)
  `/userinfo <email|tg_id>` — карточка пользователя
  `/grant <tg_id> <stars>` — начисление звёзд
  `/ban <tg_id>` — shadow-ban

- **Аналитика использования**
  Модель `TelegramEvent`: тип, пользователь, модель, стоимость, время.
  `log_event()` во всех handlers.

- **Дашборд в Django Admin**
  Метрики бота: DAU/WAU, конверсия привязки, топ-модели.

- **Алёрты владельцу** при росте ошибок генерации.

### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/handlers/admin.py` | НОВЫЙ: admin-роутер + FSM рассылки |
| `src/telegram_bot/models.py` | НОВАЯ модель `TelegramEvent` |
| `src/telegram_bot/migrations/` | Миграция `TelegramEvent` |
| `src/telegram_bot/analytics.py` | НОВЫЙ: `log_event()` |
| `src/telegram_bot/tasks.py` | Celery `broadcast_message` |
| `src/telegram_bot/admin.py` | Дашборд в Django Admin |
| `src/config/settings.py` | `TELEGRAM_ADMIN_IDS` |

### Результат
Владелец управляет ботом из Telegram. Все действия пользователей измеряются.

---

## Порядок реализации и зависимости

| Сессия | Зависит от | Можно параллелить |
|--------|-----------|-------------------|
| C1 — FSM + меню + онбординг | — | **Обязательно первым** |
| C2 — покупка + уведомления | C1 (FSM) | — |
| C3 — история + файлы | C1 | Параллельно с C2 |
| C4 — Mini App | C1, C2 | — |
| C5 — inline + группы | C1 | Параллельно с C4 |
| C6 — admin + аналитика | C1 | В последнюю очередь |

> **Ключевой риск**: без RedisStorage в C1 любые FSM-фичи (покупка, онбординг, рассылка, пагинация) не работают в webhook-per-request модели. Это не опция — это блокер.
