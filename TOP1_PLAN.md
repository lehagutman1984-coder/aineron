# aineron.ru — TOP-1 Россия + Конкурентоспособность Global

> Составлен: 2026-06-24 | Обновлён: 2026-06-24 | Модель: Claude Opus 4.8 / Claude Sonnet 4.6

> Цель: позиция #1 среди AI-платформ РФ (обойти GigaChat, YandexGPT, ChatAI) и достичь функционального паритета с ChatGPT / Claude.ai / Perplexity по ключевым возможностям (Canvas, Code Interpreter, Voice mode, Agents, Personas).

---

## 1. Что реализовано (полный чеклист)

### 1.1 Telegram-бот (`src/telegram_bot/`)
| Фича | Статус | Файл |
|------|--------|------|
| FSM RedisStorage + persistent event loop | Готово | `views.py` |
| Reply-keyboard 8 кнопок + menu dispatch | Готово | `handlers/menu.py`, `keyboards.py` |
| Онбординг FSM (3 шага) | Готово | `handlers/onboarding.py` |
| /start + deeplinks + привязка по токену | Готово | `handlers/start.py` |
| PurchaseFSM (XTR + Robokassa, выбор пакета) | Готово | `handlers/payment.py` |
| История чатов с пагинацией (FK + is_active) | Готово | `handlers/history.py`, миграция `0004` |
| Приём фото/документов → FileAttachment | Готово | `handlers/files.py` |
| Mini App /tg/ (initData HMAC, JWT) | Готово | `frontend/app/tg/`, `api/views/telegram_webapp.py` |
| Inline-режим + групповой режим (оргбиллинг) | Готово | `handlers/inline.py`, `handlers/group.py` |
| Admin-команды + рассылка FSM | Готово | `handlers/admin.py` |
| TelegramEvent аналитика (log_event везде) | Готово | `analytics.py` |
| Троттлинг edit_message (3.5s) | Готово | `handlers/chat.py:24` |
| Голос ASR (Whisper) + TTS | Готово | `handlers/voice.py` |
| Кружочки (video_note) → ASR + AI-ответ | Готово | `handlers/voice.py` (F.video_note) |
| /image /video /models /balance /settings /prompts /referral | Готово | соответствующие хендлеры |
| notify_low_balance (Celery) | Готово | `tasks.py` |
| /img2video FSM (фото + промт → Kling/Veo) | Готово | `handlers/img2video_cmd.py` |
| /sticker FSM (стикерпак 512×512) | Готово | `handlers/sticker_cmd.py` |
| /ai (пост/email/бриф/код-ревью/summary/перевод) | Готово | `handlers/scenarios_cmd.py` |
| /digest (ежедневный дайджест по расписанию) | Готово | `handlers/digest_cmd.py` |
| /search (поиск по истории) | Готово | `handlers/search_cmd.py` |
| /export (экспорт чата MD) | Готово | `handlers/export_cmd.py` |
| Редактирование/удаление сообщений (✏️🗑️) | Готово | `handlers/chat.py` (EditMsgFSM) |
| /img2img FSM | Code-complete | `handlers/img2img_cmd.py` (нужна модель в каталоге) |
| /reggroup (привязка группы к организации) | Готово | `handlers/reggroup_cmd.py`, миграция `0007` |
| /memory (управление памятью) | Готово | `handlers/memory_cmd.py` |
| Persistent Memory (UserMemory + RAG) | Готово | `aitext.UserMemory` |
| Реакции 👍/👎 → regenerate | Готово | `keyboards.py` + `chat.py` |
| UsageEvent аналитика (бот+веб) | Готово | `aitext.UsageEvent` |
| **[Sprint 4]** BUG-1 fix: TEXT_BILLING_ENABLED гейт в text-ветке generate_ai_response | Code-complete (флаг off by default) | `aitext/tasks.py` ~992 |
| **[Sprint 4]** BUG-2 fix: TelegramGroupChat per-user group isolation | Готово | `telegram_bot/models.py`, `handlers/group.py`, миграция `0008` |
| **[Sprint 4]** _get_default_network: fallback на любую активную модель | Готово | `handlers/chat.py:27` |
| **[Sprint 4]** Stars/Robokassa кнопки при нехватке баланса | Готово | `handlers/chat.py:108–124` |
| **[Sprint 4]** 7-дневная сводка списаний в /balance | Готово | `handlers/balance.py` |
| **[Sprint 6]** /translate по reply с выбором языка (EN/RU/DE/ES/FR/ZH) | Готово | `handlers/scenarios_cmd.py` |
| **[Sprint 6]** /persona — выбор AI-персоны из каталога | Готово | `handlers/persona_cmd.py` |

### 1.2 Платформа (Next.js + Django)
| Фича | Статус | Файл |
|------|--------|------|
| DRF API OpenAI-совместимый | Готово | `api/views/chat.py`, `anthropic.py` |
| B2B (Organization, Member, Invite, оргбиллинг) | Готово | `teams/` |
| Projects (Gitea, AI-коммиты, KB pgvector) | Готово | `aitext.Project`, `ProjectChunk` |
| Kanban-дашборд проектов (drag&drop) | Готово | `aitext.Project.status` (миграция `0029`) |
| Глобальный поиск Ctrl+K | Готово | `api/views/chat_search.py` |
| Экспорт PDF/MD | Готово | `api/views/chat_export.py` |
| A/B тестирование промтов | Готово | `aitext.PromptABTest` (`0028`) |
| Blog + SEO (JSON-LD, sitemap) | Готово | `blog/`, `frontend/app/sitemap.ts` |
| Yandex.Metrika + GA4 | Готово | `frontend/app/layout.tsx` |
| Batch API (Celery) + Webhooks (HMAC) | Готово | `api/views/batch.py`, `webhooks.py` |
| Embeddings API + Audio TTS/ASR API | Готово | `api/views/embeddings.py`, `audio.py` |
| /status/ page | Готово | `frontend/app/status/`, `api/views/api_status.py` |
| Реферальная программа | Готово | `api/views/referral.py` |
| EDIT Blocks (патч-коммиты) | Готово | `frontend/app/chat/[chatId]/` (EditBlock) |
| **Studio — AI app-builder в Docker-sandbox** | Готово (база) | `studio/` (sandbox.py, agents/, gitea_client.py, scaffold.py, pipeline.py), `frontend/app/studio/[id]/`, `frontend/app/ide/` |
| **Collaborative Spaces (роли в проекте)** | Готово (база) | `api/views/collaborators.py`, `aitext.ProjectCollaborator` |
| **Model Arena / Compare** | Готово (6 моделей) | `api/views/compare.py`, `frontend/app/compare/` |
| Аудит-лог проектов | Готово | `aitext.ProjectAuditEntry` (`0022`) |
| **[Sprint 4]** setup_webhook в deploy.sh | Готово | `deploy.sh` |
| **[Sprint 5]** ArtifactPanel: React/HTML/SVG/Mermaid previe в чате | Code-complete (не тестировалось на проде) | `frontend/components/chat/ArtifactPanel.tsx`, `frontend/app/chat/[chatId]/page.tsx` |
| **[Sprint 5]** PDF chat: загрузка PDF + вопросы по тексту | Готово (было) | `api/views/uploads.py` (extract_text_from_file) |
| **[Sprint 6]** AI Personas: модель, API, bot команда, UI-страница | Code-complete | `aitext.Persona`, `api/views/personas.py`, `/v1/personas/`, `frontend/app/personas/`, `/persona` в боте |
| **[Sprint 6]** PromptTemplate.variables JSONField (smart templates) | Code-complete | `aitext.PromptTemplate`, миграция `0030` |

> **Важно:** в репозитории уже есть фундамент для трёх «премиальных» фич, которые принято считать greenfield: **Studio** (sandbox-исполнение кода/приложений в Docker — фактически Code Interpreter + v0-style builder), **Collaborative Spaces** (роли/доступы), **Arena**. План ниже их **достраивает**, а не создаёт с нуля.

---

## 2. Критические баги (P0) — исправить ПЕРВЫМ

### BUG-1 (P0, revenue leak) — текстовый чат в боте бесплатен
**Подтверждено в коде.** Биллинг звёзд (`spend_pages` + `UserSpending`) в `src/aitext/tasks.py` находится **только внутри ветки `if network.provider == 'fal-ai':`** (строки 681–694) — то есть списываются лишь изображения/видео. Текстовая ветка начинается со строки 748 (`# laozhang.ai текст провайдер`) и **не содержит ни одного вызова `spend_pages`**. В боте `process_text()` (`handlers/chat.py:105–114`) только *проверяет* баланс (`check_balance`) и никогда не списывает. Веб списывает upfront (`api/views/chats.py:123`). Итог: любой пользователь бота получает бесплатный текстовый чат.

**Fix (исполнимый):** в `generate_ai_response`, в **текстовой** ветке, после успешного сохранения ответа (`message.status = COMPLETED; message.save()` — найти точку сохранения текстового ответа в блоке 748–1030 и закрепить fix сразу после неё), вставить блок биллинга, идентичный по структуре уже существующему в fal-ai-ветке:

```python
skip_billing = (message.settings or {}).get('skip_star_billing', False)
if not skip_billing:
    cost = network.cost_per_message
    if user.pages_count >= cost:
        user.spend_pages(cost)              # метод уже есть в CustomUser
        UserSpending.objects.create(
            user=user,
            amount=cost,                      # ВАЖНО: реальные поля модели
            description=f"Сообщение в чате с {network.name} (Telegram)",
        )
```

> **Поправка к предложенному в задаче сниппету:** он использовал несуществующие поля `UserSpending(network=, cost=, source=)`. Реальная модель `users.UserSpending` имеет поля `user`, `amount`, `description` (см. `users/models.py:909`). Используем уже существующий метод `CustomUser.spend_pages()` (`users/models.py:551`). Списание делаем **после** успешной генерации (а не upfront), чтобы при ошибке модели звёзды не сгорали.

> **Конкурентность (рекомендация):** `spend_pages()` — это read-modify-write (`pages_count -= cost; save()`), он не атомарен — два параллельных Celery-таска могут прочитать устаревший баланс и увести его в минус. Тот же race уже существует в fal-ai-ветке (стр. 687), так что вариант выше регрессию не вносит. Concurrency-safe вариант (рекомендуется заодно применить и к медиа-ветке): `updated = CustomUser.objects.filter(id=user.id, pages_count__gte=cost).update(pages_count=F('pages_count') - cost)` внутри `transaction.atomic()`, и создавать `UserSpending` только если `updated`.

**Процедура запуска (обязательно!):** изменение начнёт списывать звёзды у реальных пользователей, сейчас получающих бесплатный чат.
1. Рассылка в боте за 24ч: «с DD.MM текстовые ответы стоят N звёзд, как и на сайте».
2. Начислить разовый бонус активным пользователям (мягкий переход).
3. Включить за фиче-флагом `TEXT_BILLING_ENABLED` (env), чтобы откатить без деплоя.
- Сложность: **M** (1 день код + 1 день коммуникация/раскатка).

### BUG-2 (P0, context bleeding) — групповые чаты смешиваются
**Проблема:** анонимные участники группы роутятся через `TelegramUser` владельца. `_ensure_chat(owner_tg, network)` (`handlers/chat.py:37`) находит/создаёт чат по `tg_user=owner`. Все участники группы **и** личные сообщения владельца пишут в ОДИН `Chat` → контексты разных людей перемешиваются.

**Fix:** ввести изоляцию per-(group, user):
1. Новая модель `telegram_bot.TelegramGroupChat`: `group (FK TelegramGroup)`, `from_user_id (BigInteger)`, `network (FK)`, `chat (FK aitext.Chat)`, `is_active`, `unique_together=(group, from_user_id, network)`. Миграция `telegram_bot/0008`.
2. В `handlers/group.py` заменить `ensure_chat(owner_tg, …)` на `ensure_group_chat(group, from_user_id, network)` — находит/создаёт `Chat`, привязанный к (группе, отправителю). Биллинг остаётся через организацию владельца (skip_star_billing на сообщении).
3. Личный DM владельца продолжает идти через `_ensure_chat` (по `tg_user`) — не смешивается с группой.
- Файлы: `src/telegram_bot/models.py`, `src/telegram_bot/handlers/group.py`, новая миграция.
- Сложность: **M** (1–2 дня).

---

## 3. Технический долг

| # | Долг | Действие | Приоритет |
|---|------|----------|-----------|
| 1 | Непримённые миграции на проде: `aitext/0029`, `teams/0002`, `telegram_bot/0007` | `docker-compose exec web python manage.py migrate` в рамках `deploy.sh` | **P0** (блокирует фичи статусов проектов, org-meta, групп) |
| 2 | `setup_webhook` не запускался на проде → старый список команд в Telegram | Добавить `python manage.py setup_webhook` (или `set_my_commands`) в `deploy.sh` после миграций | **P1** |
| 3 | `provider='openrouter'` / `provider='fal-ai'` — устаревшие имена | **НЕ find-replace.** Это live-ключи ветвления (`if network.provider == 'fal-ai'`, `tasks.py:654`; default-провайдер `_get_default_network`, `chat.py:34`). Рефактор = миграция данных + кода в одном PR: (а) добавить новые значения `provider`, (б) data-migration перезаписать строки в БД, (в) обновить все `==`-проверки. Риск высокий, поведение рабочее → **P3**, делать отдельным изолированным PR с тестами | **P3** |
| 4 | `_get_default_network` падает на `provider='openrouter'` фильтре | Сделать дефолт устойчивым: если фильтр пуст — брать первую активную text-модель по `order` | **P1** |
| 5 | Отсутствует фиче-флаг для биллинга текста | env `TEXT_BILLING_ENABLED` (см. BUG-1) | **P0** |

---

## 4. Спринт 4 — [2 недели] — «Деньги, изоляция, чистка» (стабилизация)

Цель: закрыть revenue leak, изоляцию групп, привести прод в актуальное состояние. Без этого любая новая фича копит долг.

| Пункт | Зачем | Файлы | Сложн. |
|-------|-------|-------|--------|
| Fix BUG-1 (биллинг текста бота) + фиче-флаг | Прямая потеря выручки на всех текстовых запросах | `aitext/tasks.py` (текст-ветка ~748–1030), `telegram_bot/handlers/chat.py`, env | M |
| Fix BUG-2 (`TelegramGroupChat`, per-user isolation) | Утечка контекста = неюзабельные группы для B2B | `telegram_bot/models.py`, `handlers/group.py`, миграция `0008` | M |
| Раскатать миграции `0029/0002/0007` + встроить `migrate` в `deploy.sh` | Прод отстаёт от кода → фичи не работают | `deploy.sh` | S |
| `setup_webhook` в деплой + обновить `set_my_commands` | Пользователи видят устаревшее меню команд | `deploy.sh`, `telegram_bot/management/` | S |
| Устойчивый `_get_default_network` | Бот падает если нет модели с provider='openrouter' | `telegram_bot/handlers/chat.py:27` | S |
| Telegram-native Stars invoice в один тап (без FSM-переходов) | Снизить трение оплаты — оплата прямо из сообщения о нехватке баланса | `handlers/payment.py`, `handlers/chat.py` (кнопка под «недостаточно звёзд») | M |
| Сводка по списаниям в `/balance` (звёзд за период, топ-модель) | Прозрачность после включения биллинга — снижает отток | `handlers/balance.py`, `api/views/usage_events.py` | S |

---

## 5. Спринт 5 — [2 недели] — «Артефакты и Canvas» (паритет с ChatGPT/Claude)

Цель: вынести aineron в один ряд с Claude.ai Artifacts и ChatGPT Canvas. Это самый заметный для пользователя скачок UX и сильнейший SEO-инфоповод.

| Пункт | Зачем | Файлы | Сложн. |
|-------|-------|-------|--------|
| **Artifact system** — превью React/HTML/SVG/Mermaid прямо в чате | Ни у GigaChat/YandexGPT/ChatAI нет. Парсер уже есть (EditBlock) — переиспользовать | `frontend/app/chat/[chatId]/ArtifactPanel.tsx`, детект код-блоков в рендерере сообщений; sandbox-iframe (`sandbox="allow-scripts"`) | M |
| **Canvas mode** — боковая панель редактирования длинного документа/кода с инлайн-правками AI | Прямой паритет с ChatGPT Canvas | `frontend/app/chat/[chatId]/CanvasEditor.tsx`, новый тип сообщения `canvas` в `aitext.Message.settings`, API `POST /chats/<id>/canvas/edit` (точечная правка диапазона) | L |
| **Code Interpreter (Python в sandbox)** — достроить на базе `studio/sandbox.py` | Sandbox-инфра уже есть (Docker, `spawn_sandbox`). Не хватает: python-runtime в образе + endpoint выполнения + рендер stdout/plots в чате | `studio/sandbox.py` (добавить python exec), `api/views/` новый `code_exec.py`, `Dockerfile.sandbox` (matplotlib/pandas), `frontend/.../CodeRunOutput.tsx` | L |
| **Document understanding (чат с PDF)** — загрузил PDF → вопросы по нему | KB/pgvector (`ProjectChunk`) уже есть; нужен per-chat ad-hoc индекс | `api/views/files.py` (extract+chunk), `aitext/tasks.py` (embed), привязка чанков к `Chat` | M |
| Bot: video notes (кружочки) → транскрипция + AI-ответ | Уникум в РФ; ASR уже есть | `telegram_bot/handlers/voice.py` (handler на `F.video_note`) | S |

---

## 6. Спринт 6 — [2 недели] — «Агенты, Персоны, Мультиагент» (дифференциация)

Цель: то, чего нет ни у одного конкурента РФ и что приближает к Character.ai / Custom GPTs. Часть базируется на готовом `studio/agents/`.

| Пункт | Зачем | Файлы | Сложн. |
|-------|-------|-------|--------|
| **AI Personas** (сохранённые персонажи: «Деловой партнёр», «Python-ментор», «Редактор») | Аналог Character.ai/Custom GPTs; ноль конкурентов в РФ | модель `aitext.Persona` (name, system_prompt, avatar, model, is_public), `api/views/personas.py`, `frontend/app/personas/`, выбор персоны в чате; в боте `/persona` | M |
| **No-code Agent builder** (визуальный конструктор) — поверх `studio/agents/` | Уникальная B2B-фича; инфра агентов готова | `studio/models.py` (AgentDefinition: tools[], steps[]), `studio/views/`, `frontend/app/studio/[id]/agent-builder` | L |
| **Мультиагентный чат** (несколько моделей отвечают параллельно → выбор лучшего) | Расширение Arena (`compare.py` готов) в основной чат | `frontend/app/chat/[chatId]/` (multi-column), `compare.py` (batch-fanout + parallel `generate_ai_response`) | M |
| **Workflow / цепочки в боте** («каждый вечер: дайджест → перевод → пост в канал») | Telegram как no-code automation-хаб; `/digest` и Celery-beat готовы | `telegram_bot/models.py` (Workflow: trigger_cron, steps), Celery-beat dynamic schedule, `handlers/workflow_cmd.py` | L |
| **Smart templates** (шаблоны с переменными: нажал → заполнил → отправил) | Быстрый ROI для бизнес-пользователей; `PromptTemplate` готов | расширить `aitext.PromptTemplate` (variables JSON), `frontend/app/prompts/` форма заполнения, `/prompts` в боте | S |
| Bot: /translate по reply (перевод сообщения нажатием) | Вирусная фича в группах | `telegram_bot/handlers/scenarios_cmd.py` (reply-handler) | S |

---

## 7. Долгосрочные фичи (6+ месяцев)

Сильные, но требуют больше времени/ресурсов — после паритета по §5–6.

> **Условные обозначения:** `БЕСПЛАТНО` = только время разработки, новых денежных расходов нет. `ПЛАТНО` = требуются дополнительные API-расходы или инфраструктура.

| Фича | Суть | Затраты | Оценка |
|------|------|---------|--------|
| **AI Voice mode (real-time)** | Дуплексный голос как ChatGPT Voice; streaming ASR↔TTS + WebRTC в браузере | **ПЛАТНО** — ASR ~$0.006/мин + TTS ~$15/1М символов (laozhang.ai). Инфра: WebSocket-процесс на том же сервере (бесплатно). Dev: 2–3 нед. | L |
| **AI Image editor (inpainting)** | Выделил область на фото → промт → замена. Поверх загруженных фото | **ПЛАТНО** — API за каждую генерацию (~$0.04–0.08 за изображение). Зависит от наличия inpaint-моделей у laozhang.ai (уточнить). Dev: 1 нед. | M |
| **Video analysis (чат с видео)** | Загрузил видео → FFmpeg нарезал кадры → GPT-4V отвечает на вопросы по содержанию + ASR для аудио | **ПЛАТНО** — Vision-запросы ~$2.5/1М токенов + ASR. Кадры хранятся временно (бесплатно). Dev: 1–2 нед. | M |
| **Knowledge graph** | Граф связей между файлами/чанками в KB проекта. D3.js/vis-network визуализация | **БЕСПЛАТНО** — pgvector уже есть, библиотеки MIT. Нужен endpoint извлечения связей и фронтенд. Dev: 1 нед. | M |
| **Model Arena с Elo-рейтингом** | Публичный лидерборд: пользователи голосуют за лучший ответ → Elo обновляется. SEO-магнит | **БЕСПЛАТНО** — extend `compare.py`, таблица голосований в PG. Dev: 3–5 дней | S |
| **White-label для B2B** | Клиент приносит свой домен → Nginx vhost + кастомный логотип/цвет/название | **БЕСПЛАТНО** — wildcard SSL через Let's Encrypt, nginx config auto-gen. Dev: 1 нед. | M |
| **Billing seats (посадочные места)** | Орг покупает N мест → каждый участник получает месячный лимит звёзд | **БЕСПЛАТНО** — расширение `teams/` моделей. Dev: 3–5 дней | S |
| **Zapier / Make интеграция** | Zapier/Make триггер на новое AI-сообщение или webhook. Поверх готовых Webhooks (HMAC) | **БЕСПЛАТНО** — webhooks уже готовы. Нужен JSON-схема + примеры шаблонов. Dev: 2–3 дня | S |
| **AI-модерация контента** | Автопроверка пользовательских запросов через Moderation API для корп. тенантов | **ПЛАТНО** но дёшево — ~$0.0001/запрос (практически бесплатно). Dev: 2–3 дня | S |
| **Real-time collaboration (как Figma)** | Несколько пользователей видят и редактируют один чат/документ в реальном времени через CRDT/Yjs | **БЕСПЛАТНО** — Yjs MIT, y-websocket сервер (+50 MB RAM). Dev: 2–3 нед. Сложно | L |
| **Fine-tuning UI** | Разметка датасета в интерфейсе → отправка на дообучение через провайдера | **ПЛАТНО и дорого** — fine-tuning у OpenAI от $8/1М токенов + хранение модели. Зависит от поддержки laozhang.ai. Пока нецелесообразно | L |
| **Bot as OAuth provider** | «Войти через Telegram» для внешних сервисов через наш бот | **БЕСПЛАТНО** — Django OAuth Toolkit + aiogram. Dev: 1 нед. | M |
| **Telegram polls → AI-анализ** | Запустил опрос в группе → бот агрегирует ответы и строит AI-саммари | **БЕСПЛАТНО** — Telegram poll API + laozhang.ai (пользователь платит звёздами). Dev: 2–3 дня | S |
| **Scheduled AI reminders** | Подписка на напоминание с AI-контекстом («каждое утро: прогресс по задачам») | **БЕСПЛАТНО** — Celery-beat уже есть. Dev: 2–3 дня | S |

### Резюме по деньгам

**Не требуют новых расходов (только разработка):**
Knowledge Graph, Model Arena с Elo, White-label, Billing seats, Zapier/Make, Real-time collaboration, Bot OAuth, Telegram polls, Scheduled reminders — итого **9 из 14 фич бесплатны**.

**Требуют API-расходов (платятся из маржи, покрываются ценой пользователя):**
Voice mode (ASR+TTS за звёзды), Image editor (звёзды), Video analysis (звёзды), AI-модерация (копейки).

**Требуют отдельных вложений:**
Fine-tuning — дорого ($100+/модель) и зависит от провайдера. Рекомендуется отложить.

> **Вывод:** большинство фич §7 реализуемы без дополнительных денег — только время. Voice mode и Video analysis монетизируются через звёзды пользователей, так что окупаются сразу при запуске.

---

## 8. Синхронизация бот ↔ платформа

**Принцип: `CustomUser` — единый источник правды. Бот и веб — два клиента одного состояния.**

| Сущность | Текущее состояние | Цель | Действие |
|----------|-------------------|------|----------|
| Баланс/списания | `CustomUser.pages_count`, `UserSpending` — общие | ✅ единый | **Закрыть BUG-1**, чтобы бот списывал так же, как веб |
| Чаты | `Chat` общий; бот через `TelegramChat` (FK) | ✅ почти | **BUG-2:** добавить `TelegramGroupChat` для изоляции групп |
| Аналитика | `UsageEvent` (бот+веб) | ✅ единый | Один дашборд `/dashboard/usage/` уже агрегирует оба источника |
| Настройки | Бот: `TelegramUser` (voice/web_search/system_prompt); Веб: `Chat.settings` | Общий профиль на `CustomUser` | Вынести дефолты (модель, voice, system_prompt) на `CustomUser`, оба клиента читают одно |
| Память | `UserMemory` (RAG) — общая | ✅ единый | Persona/Memory доступны и в `/memory` бота, и в вебе |
| Платежи | XTR + Robokassa → `PaymentHistory` | Оба уведомляют бот | Веб-оплата Robokassa шлёт пуш в бот (Celery `maybe_notify`) |
| Персоны/шаблоны (Спринт 6) | — | Общие | `Persona`/`PromptTemplate` на `CustomUser`, выбор и в боте, и в вебе |

---

## 9. Конкурентная матрица (обновлённая)

| Фича | aineron.ru | GigaChat | YandexGPT | ChatAI | RouterAI | ChatGPT | Claude.ai | Perplexity |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Мультимодельность (10+) | ✅ | ❌ | ❌ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Видео (Sora/Veo/Kling/Seedance) | ✅ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| Полнофункц. Telegram-бот | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Inline + групповой режим | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Mini App | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| API (OpenAI-совместимый) | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| B2B (организации/оргбиллинг) | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ⚠️ |
| RAG / база знаний | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Persistent Memory | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Sandbox-builder приложений (Studio) | ✅ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ | ❌ |
| Code Interpreter (Python) | ⚠️ строим | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Artifacts / Canvas | ⚠️ Спринт 5 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| AI Personas | ⚠️ Спринт 6 | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ | ❌ |
| Мультиагентный чат | ⚠️ Спринт 6 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Voice mode (real-time) | ⚠️ долгосрок | ❌ | ⚠️ (Alice) | ❌ | ❌ | ✅ | ❌ | ❌ |
| Оплата без VPN (Robokassa/XTR) | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ |

Легенда: ✅ есть · ⚠️ частично/в плане/ограничено · ❌ нет.

**Вывод:** относительно РФ-конкурентов aineron уже впереди по мультимодельности, видео и Telegram-интеграции. Разрыв с глобальными лидерами — в трёх местах: **Artifacts/Canvas (Спринт 5)**, **Code Interpreter (Спринт 5, база готова в Studio)**, **Personas/Agents (Спринт 6)**. Закрыв их, получаем функциональный паритет с ChatGPT/Claude.ai при уникальных РФ-преимуществах (видео, Telegram, оплата без VPN).

---

## 10. Ключевые принципы

1. **Деньги вперёд фич.** BUG-1 (бесплатный текст в боте) — прямая ежедневная потеря выручки. Спринт 4 — деньги и стабильность, потом всё остальное.
2. **`CustomUser` — единый источник правды.** Любая новая фича (Persona, Memory, настройки) живёт на пользователе, а не дублируется в боте и вебе.
3. **Достраивать, а не переписывать.** Studio (sandbox), EditBlock-парсер, Compare/Arena, ProjectCollaborator, KB/pgvector уже есть — Artifacts/Canvas/CodeInterpreter/Personas строятся поверх них за 1–2 дня каждая, а не с нуля.
4. **Каждая фича — 1–2 дня.** Если задача больше — она декомпозируется. Сложность L = разбить на под-PR.
5. **Фиче-флаги для рискованного.** Биллинг текста, новые провайдеры, мультиагент — за env-флагом с возможностью отката без деплоя.
6. **Уважать live-ключи.** `provider='fal-ai'/'openrouter'` — рабочие ветвления, а не косметика. Рефактор только отдельным PR с миграцией данных.
7. **Telegram — точка автоматизации, не просто чат.** Workflow, расписания, video notes, native-оплата — то, что физически невозможно у GigaChat/YandexGPT и недоступно ChatGPT/Claude в РФ.
8. **Деплой = `bash deploy.sh`** (с обязательными `migrate` + `setup_webhook` внутри). Не предлагать ручные docker-compose команды.
9. **Zero-emoji в продуктовом UI.** Только Lucide-иконки, строгий профессиональный стиль (распространяется на новые компоненты Artifact/Canvas/Persona).
