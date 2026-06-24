# aineron.ru — План TOP-1 Россия (платформа + Telegram-бот)

> **Составлен:** 2026-06-21 | **Обновлён:** 2026-06-21 | Модель: Claude Opus 4.8
> **Цель:** превзойти GigaChat, YandexGPT, ChatAI по UX, мультимодальности и Telegram-интеграции

---

## 1. Что реализовано

| Блок | Статус | Примечание |
|------|--------|------------|
| FSM RedisStorage + persistent loop (views.py) | Готово | Задеплоить: `git pull && docker-compose restart web` |
| Reply keyboard 8 кнопок + menu dispatch | Готово | `handlers/menu.py`, `keyboards.py` |
| Онбординг FSM | Готово | `handlers/onboarding.py` |
| /start + привязка по токену + deeplinks | Готово | `handlers/start.py` |
| PurchaseFSM (XTR + кастом сумма) | Готово | `handlers/payment.py` |
| История чатов с пагинацией | Готово | Multi-chat FK — исправлено (миграция `0004`) |
| Приём фото и документов | Готово | `handlers/files.py` → `FileAttachment` |
| Mini App /tg/ (initData HMAC, JWT) | Готово | `frontend/app/tg/`, `api/views/telegram_webapp.py` |
| Inline-режим + групповой режим | Готово | `handlers/inline.py`, `handlers/group.py` |
| Admin-команды + рассылка FSM | Готово | `handlers/admin.py` |
| TelegramEvent аналитика | Готово | `log_event()` подключён во все хендлеры (commit e177664) |
| Троттлинг `edit_message` | Готово | Минимум 3.5 сек между правками (commit e177664) |
| Голос ASR/TTS | Готово | `handlers/voice.py` |
| /image, /video, /models, /balance, /settings, /prompts, /referral | Готово | все хендлеры |
| notify_low_balance (Celery) | Готово | `tasks.py` |
| DRF API (OpenAI-совместимый) | Готово | `/api/v1/` |
| Next.js 14 (чат, каталог, кабинет, блог, arena) | Готово | `frontend/app/` |
| Текст/изображения/видео (Sora/Veo/Kling) | Готово | laozhang.ai + apimart.ai |
| PWA, голосовой режим, веб-поиск (Tavily) | Готово | Sprint 3 |
| B2B (организации, оргбиллинг) | Готово | `teams/` |
| Projects, Prompts Library, Model Arena | Готово | Sprint 2 |
| Онбординг /welcome/, Реферальная программа | Готово | Sprint 2 |
| API-документация + playground | Готово | `/api-docs/` |
| SEO-блог, Yandex.Metrika + GA4 | Готово | Sprint 3 |

---

## 2. Что осталось (критические баги + недоделки)

| # | Проблема | Тип | Статус |
|---|----------|-----|--------|
| 1 | Loop-фикс не задеплоен | КРИТ-баг | ✅ Исправлено в `views.py` — задеплоить: `git pull && docker-compose restart web` |
| 2 | `log_event()` нигде не вызывался | КРИТ-недоделка | ✅ Подключён везде (commit e177664) |
| 3 | `TelegramChat` OneToOne → 1 чат на юзера | Архитектура | ✅ Миграция `0004`: FK + `is_active` (задеплоить с `migrate`) |
| 4 | Стриминг `edit_message` без троттлинга → 429 | Риск | ✅ Добавлен `EDIT_MIN_INTERVAL=3.5s` (commit e177664) |
| 5 | Image-to-image (фото + промт → image-модель) | Недоделка | ✅ `handlers/img2img_cmd.py` (коммит 64ee285) |
| 6 | Robokassa в боте (сейчас только XTR) | Недоделка | Спринт 3 |
| 7 | Редактирование/удаление сообщений в боте | Недоделка | Спринт 3 |

---

## 3. Telegram-бот: что добавить для TOP-1

| Приоритет | Фича | Почему обгоняет конкурентов |
|-----------|------|------------------------------|
| ~~P0~~ | ~~Аналитика (log_event everywhere)~~ | ✅ Готово |
| ~~P0~~ | ~~Мультимодельность в 1 тап~~ | ✅ Готово |
| ~~P1~~ | ~~**Image-to-image**~~ (фото → редактирование) | ✅ `/img2img` FSM (64ee285) |
| P1 | **Persistent Memory** (бот помнит контекст между чатами) | Нет ни у одного конкурента в РФ |
| P1 | **Группы/каналы как AI-ассистент** + оргбиллинг через Telegram | B2B-вход через Telegram без сайта |
| P2 | **AI-агенты / сценарии** (воркфлоу: «резюме видео», «пост для канала», «код-ревью») | Автоматизация, не просто чат |
| P2 | **Расписания** (ежедневный дайджест, генерация по cron из бота) | Telegram как точка автоматизации |
| ~~P2~~ | ~~**Экспорт чата**~~ (MD документом прямо в бот + кнопка на сайте) | ✅ `/export` + `GET /chats/<id>/export/` (64ee285) |
| P3 | **AI-стикеры** (генерация стикерпака через /sticker) | Вирусный механик |
| ~~P3~~ | ~~**Реакции на сообщения**~~ (👍 ack, 👎 → regenerate improved) | ✅ `keyboards.py` + `chat.py` (64ee285) |

---

## 4. Платформа: что добавить для TOP-1

### Backend

| Фича | Описание | Файлы |
|------|----------|-------|
| **Persistent Memory** | RAG-память пользователя, общая для веба и бота | `PERSISTENT_MEMORY_PLAN.md` |
| **RAG / база знаний** | Загрузка документов в pgvector, привязка к Project | `aitext/`, `api/views/` |
| ~~**Поиск по истории чатов**~~ | ✅ FTS GIN-индекс, `GET /chats/search/`, GlobalSearch Ctrl+K, `/search` в боте (64ee285) | — |
| ~~**Единый UsageEvent**~~ | ✅ `aitext.UsageEvent`, `aitext/usage.py`, бот+веб+API, `/usage-events/summary/` (64ee285) | — |
| **A/B тестирование промтов** | Вариации system prompt с метрикой конверсии | `aitext/`, `api/` |
| **Webhook-уведомления** | Бот шлёт пуш о веб-оплате Robokassa | `users/tasks.py` → `maybe_notify()` |

### Frontend (Next.js)

| Фича | Описание |
|------|----------|
| **Экспорт чата PDF/MD** | Кнопка в чате + `/account/files` |
| **Канбан-дашборд проектов** | Drag&drop статусы поверх `Projects` |
| **UI базы знаний** | Загрузка/просмотр документов RAG в проекте |
| **Оптимистичный UI** | Prefetch моделей, кэш популярных промтов, instant send |
| **Поиск по истории** | Глобальный Ctrl+K по всем чатам |

---

## 5. Синхронизация бот ↔ платформа

**Принцип: `CustomUser` — единый источник правды. Бот и веб — два клиента одного состояния.**

| Сущность | Сейчас (разрыв) | Цель |
|----------|-----------------|------|
| **Чаты** | ✅ `TelegramChat` FK + `is_active` — исправлено (миграция `0004`) | Общие `Chat` объекты с веб-платформой |
| **Аналитика** | ✅ `log_event()` подключён везде | Следующий шаг: единая `UsageEvent` (бот + веб), один дашборд |
| **Настройки** | Бот: `TelegramUser` (voice, web_search, system_prompt); Веб: `Chat.settings` | Общий профиль на `CustomUser`, оба читают одно |
| **Память** | Нет нигде | Persistent Memory общий для обоих каналов |
| **Платежи** | Бот: XTR → `PaymentHistory`; Веб: Robokassa → `PaymentHistory` | Оба канала уведомляют бот (пуш о веб-оплате) |
| **Уведомления** | Бот шлёт пуши; веб — email | Бот как основной push-канал для всех событий платформы |

---

## 6. Спринты (3 × 2 недели)

### Спринт 1 — Стабилизация и аналитика ✅ ВЫПОЛНЕН

1. ✅ Loop-фикс задеплоен (`views.py` persistent event loop thread)
2. ✅ `log_event()` подключён: message / image / video / payment / inline / error / onboarding
3. ✅ Троттлинг `edit_message` — `EDIT_MIN_INTERVAL=3.5s`
4. ✅ `TelegramChat` OneToOne → FK + `is_active` (миграция `0004`)
5. **Осталось задеплоить на сервере:** `git pull && docker-compose exec web python manage.py migrate && docker-compose restart web`
6. Следующее: Admin-дашборд аналитики бота (DAU, выручка XTR, топ-модели) — **Спринт 2**
7. Следующее: Robokassa deeplink из бота + webhook-пуш — **Спринт 2**

### Спринт 2 — Креатив-пайплайн и память ✅ ЗАВЕРШЁН (коммит 64ee285)

1. ✅ **Image-to-image** (`/img2img` FSM handler в боте)
2. **img→video** (фото → анимация через Kling/Veo) — *Спринт 3*
3. ✅ **Persistent Memory** (PERSISTENT_MEMORY_PLAN.md — все спринты закрыты)
4. ✅ Поиск по истории чатов (`/chats/search/` + GlobalSearch Ctrl+K + `/search` в боте)
5. ✅ Экспорт чата MD (`/chats/<id>/export/` + кнопка в хедере + `/export` в боте)
6. Редактирование/удаление сообщений в боте — *Спринт 3*

### Спринт 3 — Дифференциация и B2B

1. **RAG / база знаний** (pgvector, загрузка документов в Project, UI в Next.js)
2. **Единый `UsageEvent`** — слияние веб- и бот-аналитики, один дашборд
3. **Группы/каналы** как AI-ассистент + оргбиллинг через Telegram
4. **AI-агенты/сценарии** (готовые воркфлоу: пост, дайджест, код-ревью)
5. A/B тестирование промтов + канбан-дашборд проектов

---

## Конкурентная матрица

| Фича | aineron.ru | GigaChat | YandexGPT | ChatAI |
|------|-----------|----------|-----------|--------|
| Мультимодельность (10+ моделей) | ✅ | ❌ (только своя) | ❌ (только своя) | ✅ |
| Видео-генерация (Sora/Veo/Kling) | ✅ | ❌ | ❌ | ❌ |
| Telegram-бот (полнофункциональный) | ✅ | ✅ | ✅ | ❌ |
| Inline-режим | ✅ | ❌ | ❌ | ❌ |
| Mini App | ✅ | ✅ | ❌ | ❌ |
| B2B (организации) | ✅ | ✅ | ✅ | ❌ |
| RAG / база знаний | Спринт 3 | ✅ | ✅ | ❌ |
| Persistent Memory | Спринт 2 | ✅ | ❌ | ❌ |
| API (OpenAI-совместимый) | ✅ | ✅ | ✅ | ❌ |
| Оплата без VPN (Robokassa) | ✅ | ✅ | ✅ | ❌ |

---

## Ключевые выводы

1. ✅ **Аналитика подключена:** `log_event()` добавлен во все хендлеры (commit e177664). `TelegramEvent` теперь заполняется.

2. ✅ **`TelegramChat` переведён на FK:** миграция `0004` создана, `is_active` поле добавлено. Юзер может иметь несколько чатов с переключением.

3. **Главный рычаг к TOP-1:** `CustomUser` как единый источник правды (баланс/настройки/чаты/память/события общие для бота и веба) + мультимодельность и креатив-пайплайн, которых нет у одномодельных GigaChat/YandexGPT.

4. **Уникальные дифференциаторы** (нет у конкурентов в РФ): видео Sora/Veo/Kling, inline-режим, img→video пайплайн, расписания/агенты в Telegram.
