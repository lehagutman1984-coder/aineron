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

#### Telegram-бот — предстоит реализовать (обновлён 2026-06-24)

> Только новые задачи. Реализованное выше не дублируется. Приоритет: P0 (срочно) → S/M/L (сложность).

| Фича | Зачем | Приоритет | Сложн. |
|------|-------|:---:|:---:|
| Включить BUG-1 `TEXT_BILLING_ENABLED=1` после рассылки | Код биллинга текста уже написан (флаг off, `aitext/tasks.py:996–1009`). Каждый текстовый ответ в боте сейчас бесплатен = ежедневная потеря выручки. Включать после release-рассылки + бонус-перехода | **P0** | S |
| `/workflow` — цепочки команд (no-code automation) | Telegram как automation-хаб; `DatabaseScheduler` (`django_celery_beat`) уже активен (`settings.py:285`) — динамические расписания через `PeriodicTask`/`CrontabSchedule`, не нужен костыль «раз в минуту + фильтр» как в `/digest`. Модель `Workflow(trigger_cron, steps[])` + `handlers/workflow_cmd.py` | L | L |
| No-code Agent в боте — запуск через `/agent` | Дифференциация от всех РФ-конкурентов. Поверх `studio/agents/BaseAgent` (готовы 13 агентов), но `AgentDefinition`-модели НЕТ — нужно сначала её ввести (см. §8.2 Sprint 8), бот станет вторым клиентом запуска | L | L |
| Smart templates в боте — `/prompts` с заполнением переменных | `PromptTemplate.variables` (JSONField, `models.py:776`) уже есть; сейчас `/prompts` шлёт `content` как есть без подстановки (`prompts_cmd.py:109`). Добавить FSM-шаги заполнения `{var}` → готовый ROI для бизнеса | M | M |
| Мультиагентный чат в боте — несколько моделей параллельно | Перенос Arena (`api/views/compare.py` fanout) в бот; отправка одного запроса в 2–4 модели, ответы в одном треде с пометкой модели | M | M |
| Elo-рейтинг моделей по голосам пользователей | Реакции 👍/👎 уже есть; добавить парное голосование «A vs B» → таблица `ModelVote` + Elo. SEO-магнит и сигнал доверия. База — `compare.py` | M | M |
| Групповой `/stat` для B2B (статистика группы) | `UsageEvent(channel='bot')` уже логирует всё (`aitext/models.py:939`); агрегировать по `TelegramGroup.organization` — топ-пользователи, расход звёзд, модели. Продаёт B2B-ценность групп | S | S |
| Авто-рассылка release notes при выкатке фич | `handlers/admin.py` рассылка FSM готова; добавить команду публикации changelog активным пользователям. Повышает adoption новых фич (напр. перед включением BUG-1) | S | S |
| Inline-режим 2.0 — выбор модели в inline query | `handle_inline` (`handlers/inline.py:53`) сейчас один результат-заглушка; добавить несколько `InlineQueryResultArticle` = выбор модели прямо из строки `@bot ...`. Также: `setup_webhook` регистрирует лишь 16 команд (нет `/persona`, `/search`, `/export`, `/translate`) — расширить меню для discoverability | M | M |

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

## 7. Долгосрочные фичи (6+ месяцев) — детальные планы реализации

Сильные фичи, требующие больше времени/ресурсов — выполняются после паритета §5–6. Для каждой: конкретные файлы, нетривиальные архитектурные решения, что переиспользуем из текущей кодовой базы, риски и реальная оценка.

> **Условные обозначения:** `БЕСПЛАТНО` = только время разработки, новых денежных расходов нет. `ПЛАТНО` = требуются дополнительные API-расходы или инфраструктура.

> **Два сквозных архитектурных факта, влияющих на несколько фич ниже:**
> 1. **WebSocket-инфраструктура НЕ поднята.** `channels==4.3.2`, `channels_redis==4.3.0`, `daphne==4.2.1` есть в `requirements.txt`, но `INSTALLED_APPS` их не содержит, `ASGI_APPLICATION`/`CHANNEL_LAYERS` не заданы, `config/asgi.py` — голый `get_asgi_application()`, прод работает на **WSGI** (`settings.py:105`). Реалтайм сегодня = SSE-стриминг (`StreamMessageView`) + HTTP-поллинг (`MessageStatusView`). Любая дуплексная фича (Voice, Yjs-collab) сначала требует разовой миграции на ASGI — это общий блокер, его делаем **один раз** и распределяем стоимость на обе фичи.
> 2. **`DatabaseScheduler` уже активен** (`django_celery_beat==2.8.1`, `CELERY_BEAT_SCHEDULER` задан в `settings.py:285`). Динамические расписания (reminders, workflow) делаются через DB-модели `PeriodicTask`/`CrontabSchedule`, без перезапуска beat. Долг: два конкурирующих определения расписания — `config/celery.py:18` (`app.conf.beat_schedule`) и `settings.py:289` (`CELERY_BEAT_SCHEDULE`) — свести к одному источнику.

---

### 7.1 AI Voice mode (real-time) — `ПЛАТНО` — оценка: 3–4 нед — L

**Суть.** Дуплексный голосовой режим уровня ChatGPT Voice: пользователь говорит, поток ASR транскрибирует, текст уходит в LLM-стрим, ответ синтезируется TTS и проигрывается с минимальной задержкой; прерывание (barge-in) останавливает воспроизведение.

**Что переиспользуем.** ASR/TTS уже работают синхронно: `api/views/audio.py` — `AudioTranscriptionsView` (`client.audio.transcriptions.create`, line 68) и `AudioSpeechView` (`client.audio.speech.create`, line 127), оба через `get_laozhang_client()`. В боте голос уже есть (`telegram_bot/handlers/voice.py`). LLM-стрим уже есть (`StreamMessageView`).

**Архитектура (нетривиальная часть).**
- **Разовая миграция на ASGI** (общий блокер, см. врезку): добавить `channels` в `INSTALLED_APPS`, `ASGI_APPLICATION='config.asgi.application'`, `CHANNEL_LAYERS` на существующем Redis (`channels_redis`, `REDIS_URL` уже есть). `config/asgi.py` → `ProtocolTypeRouter({'http': django_asgi, 'websocket': AuthMiddlewareStack(URLRouter(ws_routes))})`. Запуск: **daphne рядом с gunicorn** (отдельный процесс под `/ws`), nginx проксирует `/ws/` на daphne, остальное на WSGI. Не переводить весь сайт на ASGI — снизить риск.
- **Новый consumer** `src/api/consumers/voice.py: VoiceConsumer(AsyncWebsocketConsumer)`. Протокол: клиент шлёт PCM/opus-чанки → consumer держит rolling-буфер. Поскольку laozhang ASR — это REST `transcriptions.create` (не WS-стрим), реализуем **VAD-сегментацию на стороне сервера** (webrtcvad: детект тишины → закрываем сегмент → отправляем чанк на ASR). Это убирает зависимость от наличия у провайдера streaming-ASR.
- **Пайплайн интервалов:** segment→ASR (текст) → `generate_ai_response`-подобный стрим LLM → по предложениям (sentence-boundary) синтез TTS чанками → стрим аудио обратно в WS. Barge-in: входящий голос при активном TTS → отмена текущей TTS-задачи.
- **Биллинг:** списывать звёзды за минуты ASR + символы TTS через тот же `UsageEvent(channel='web', event_type='voice')` и `spend_pages`. Фиче-флаг `VOICE_MODE_ENABLED`.
- **Frontend:** `frontend/components/voice/VoiceSession.tsx` — `getUserMedia` → `AudioWorklet` энкодер → WS; воспроизведение через `AudioContext` очередь. Кнопка в чате рядом с `VoiceButton.tsx`.

**Риски.** Латентность (цель < 1.5 с round-trip; узкое место — REST-ASR, смягчается VAD-нарезкой и параллельным TTS по предложениям). Стоимость WS-соединений на одном сервере (limit + reconnect). Качество русского TTS у laozhang — протестировать заранее.

---

### 7.2 AI Image editor (inpainting) — `ПЛАТНО` — оценка: 1–1.5 нед — M

**Суть.** Загрузил фото → выделил область маской → промт → модель заменяет выделенное.

**Что переиспользуем.** Весь медиа-пайплайн готов: `aitext/fal_utils.py:generate_with_falai` (line 855) маршрутизирует по `NeuralNetwork.config_json.metadata`; `NeuralNetwork(provider='fal-ai')` с `config_json` (`api_defaults/constraints/metadata`) — каталог уже умеет описывать медиа-модели; биллинг медиа в `tasks.py:682–694`. Загрузка/хранение файлов — `FileAttachment`, `api/views/uploads.py`.

**Архитектура.**
- **ПРЕДУСЛОВИЕ (уточнить):** есть ли у laozhang.ai inpaint/edit-эндпоинт (тип `images.edit` с `image`+`mask`). Если нет — фича блокируется или нужен альтернативный провайдер. Отметить как gate перед стартом.
- Добавить inpaint-модель в каталог через `add_laozhang_models.py` с `config_json.metadata.mode='inpaint'`. В `generate_with_falai` ветка: при `mode='inpaint'` слать `image`+`mask`+`prompt` на edit-эндпоинт.
- **Маска:** генерируется на фронте. `frontend/components/image/InpaintCanvas.tsx` — canvas поверх изображения, кисть рисует альфа-маску → экспорт PNG (белое = заменить). Отправка multipart на новый `api/views/images.py:ImageEditView`.
- **Frontend-вход:** кнопка «Редактировать» на сгенерированном/загруженном изображении в чате.

**Риски.** Зависимость от провайдера (главный). UX рисования маски на мобильных. Биллинг — как обычная генерация изображения (звёзды).

---

### 7.3 Video analysis (чат с видео) — `ПЛАТНО` — оценка: 1.5–2 нед — M

**Суть.** Загрузил видео → задаёшь вопросы по содержанию (визуал + речь).

**Что переиспользуем.** **`BaseAgent.run_vision`** (`studio/agents/base.py:288`) — уже умеет слать изображения в vision-модель; переиспользуем механизм для кадров. ASR — `api/views/audio.py`. Хранение — `FileAttachment`/media. KB/pgvector (`ProjectChunk`) — для индексации транскрипта длинных видео.

**Архитектура.**
- **Загрузка → Celery-таск** `aitext/tasks.py:analyze_video`. FFmpeg (добавить в Docker-образ web/worker): (а) извлечь аудиодорожку → ASR → транскрипт с таймкодами; (б) извлечь кадры — не равномерно, а по **scene-detection** (`ffmpeg select='gt(scene,0.4)'`) чтобы не слать 1000 одинаковых кадров в vision (экономия токенов и денег).
- **Индекс:** транскрипт чанкуется и эмбеддится (переиспользовать `embed_project_file`-логику и `ProjectChunk`); кадры хранятся как `FileAttachment` с таймкодом.
- **Ответ на вопрос:** RAG по транскрипту (`build_project_knowledge_context`) + топ-N релевантных кадров в `run_vision`. Vision-вызов через существующий laozhang-клиент.
- **Биллинг:** дорогая фича — vision + ASR; ценообразование per-минута видео, фиче-флаг.

**Риски.** Стоимость vision (главный → scene-detection обязателен). Размер файлов/диск (временное хранение + cleanup-таск). Длительность обработки → прогресс через тот же поллинг, что у медиа.

---

### 7.4 Knowledge graph — `БЕСПЛАТНО` — оценка: 1–1.5 нед — M — **CODE-COMPLETE 2026-06-24**

**Суть.** Граф связей между файлами/чанками в KB проекта; визуализация и навигация.

**Что переиспользуем.** `ProjectChunk` с pgvector-эмбеддингами (`aitext/models.py:453`, vector через raw SQL) — связи строятся из cosine-близости чанков; уже есть весь embed-пайплайн.

**Архитектура.**
- **Endpoint** `api/views/projects.py:ProjectGraphView` — строит рёбра: для каждой пары чанков с cosine-similarity > порога создаёт ребро (раздельный SQL по pgvector `<=>`); узлы = файлы (агрегация чанков) или чанки. Кэш результата (граф меняется только при изменении KB) — поле `Project` или Redis.
- **Извлечение сущностей (опц., нетривиально):** LLM-проход по чанкам → JSON `{entities, relations}` (через `BaseAgent.run_json`, base.py:235) → семантический граф, а не только similarity. Дороже, но качественнее.
- **Frontend:** `frontend/app/projects/[id]/graph/page.tsx` с `vis-network` или `react-force-graph` (MIT). Клик по узлу → открыть файл/чанк.

**Риски.** O(n²) по парам чанков — для больших KB строить только top-K соседей на узел (kNN через pgvector), не полный граф.

---

### 7.5 Model Arena с Elo-рейтингом — `БЕСПЛАТНО` — оценка: 3–5 дней — S — **CODE-COMPLETE 2026-06-24**

**Суть.** Публичный лидерборд: пользователи голосуют за лучший из двух ответов → Elo обновляется. SEO-магнит и сигнал доверия.

**Что переиспользуем.** **`api/views/compare.py`** уже делает fanout одного запроса в 2–6 моделей (отдельные `Chat`+`Message` на модель, поллинг). Реакции 👍/👎 в боте. Нужно только добавить голосование + рейтинг.

**Архитектура.**
- **Модели** в `aitext/models.py`: `ModelMatch(prompt, network_a, network_b, winner)` и расширить `NeuralNetwork` полями `elo_rating` (default 1500), `elo_matches`. Обновление Elo стандартной формулой в транзакции при голосовании.
- **Anti-abuse (нетривиально):** голос засчитывается только за свой `CompareView`-результат (привязка к `chat_id` пары из `compare.py`), один голос на матч на пользователя, rate-limit. Без этого лидерборд накручивается.
- **Endpoint** `api/views/compare.py:ArenaVoteView` + публичный `ArenaLeaderboardView`.
- **Frontend:** кнопки «A лучше / B лучше / ничья» в `frontend/app/compare/page.tsx`; публичная страница `frontend/app/arena/page.tsx` (индексируемая, для SEO).
- **Бот:** парное голосование как расширение реакций (см. §1.1 Elo-задача).

**Риски.** Накрутка (решается привязкой к реальному матчу + rate-limit). Холодный старт рейтинга — стартовать с 1500 и calibration-периода.

---

### 7.6 White-label для B2B — `БЕСПЛАТНО` — оценка: 1–1.5 нед — M

**Суть.** Корп-клиент приносит свой домен → своя тема/логотип/название, шильдик aineron убран.

**Что переиспользуем.** `teams/` (Organization). Next.js рендерит по `Host`-заголовку.

**Архитектура.**
- **Модель** `teams.OrganizationBranding(organization, custom_domain, logo_url, primary_color, brand_name, hide_powered_by)`.
- **Резолв домена:** middleware (Django + Next.js) определяет org по `Host` → подменяет брендинг. Next.js: чтение домена в `layout.tsx`/middleware, CSS-переменная `--brand-primary`, динамические `metadata`.
- **SSL/Nginx (нетривиально):** автоген vhost при добавлении домена + Let's Encrypt. Реализовать через **on-demand TLS** (Caddy как фронт-прокси перед nginx — автоматически выпускает серты для разрешённых доменов из allowlist) ИЛИ certbot-хук, дёргаемый при сохранении `custom_domain`. Caddy проще и безопаснее массового certbot.
- **Изоляция:** проверка, что домен принадлежит верифицированной org (DNS TXT-верификация перед активацией).

**Риски.** Управление сертификатами в проде (Caddy снимает основную боль). Верификация владения доменом обязательна (иначе фишинг).

---

### 7.7 Billing seats (посадочные места) — `БЕСПЛАТНО` — оценка: 3–5 дней — S — **CODE-COMPLETE 2026-06-24**

**Суть.** Орг покупает N мест → каждый участник получает месячный лимит звёзд из общего пула.

**Что переиспользуем.** `teams/` (Organization, Member, оргбиллинг, Invoice). `UsageEvent` для учёта расхода.

**Архитектура.**
- Расширить `teams.models`: `Organization.seats_count`, `seat_monthly_quota`; на `Member` — `monthly_used`, `period_start`. Биллинг участника: сначала тратится личная квота места, при исчерпании — общий оргпул (или блок, по настройке).
- **Сброс периода:** Celery-beat таск `reset_seat_quotas` (DatabaseScheduler, ежемесячно).
- **UI:** `frontend/app/(dashboard)/dashboard/organization/` — управление местами, графики расхода по участникам (данные из `UsageEvent`).

**Риски.** Гонки при списании из общего пула — `F()`-update + `transaction.atomic()` (та же дисциплина, что в BUG-1).

---

### 7.8 Zapier / Make интеграция — `БЕСПЛАТНО` — оценка: 2–4 дня — S — **CODE-COMPLETE 2026-06-24**

**Суть.** Триггеры Zapier/Make на события aineron (новое сообщение, готовая генерация) + действия (отправить промт).

**Что переиспользуем.** **Webhooks с HMAC уже готовы:** `api/services/webhooks.py:_deliver` (line 20, `X-Aineron-Signature: sha256=<hex>`, ретраи `[10,60,300]s`), `dispatch_event` (48), CRUD в `api/views/webhooks.py`. OpenAI-совместимый API для действий.

**Архитектура.**
- **Долг к исправлению (нетривиально):** `dispatch_event` доставляет в **daemon-потоке** (`threading.Thread`, webhooks.py:64), а не через Celery — при рестарте процесса доставки теряются. Перед публичной Zapier-интеграцией перенести доставку в **Celery-таск** (`deliver_webhook.delay`) с ретраями через Celery — надёжность критична для внешней интеграции.
- **Zapier app:** определить триггеры (subscribe/unsubscribe через наш Webhook CRUD = REST hooks pattern) и actions (POST в `/v1/chat/completions`). Опубликовать в Zapier (private → public review).
- **Make:** аналогично, custom app по тому же REST hooks.
- Документация + примеры сценариев в `frontend/app/api-docs/`.

**Риски.** Надёжность доставки (решается переносом на Celery). Ревью Zapier/Make (недели на стороне платформ — закладывать в срок).

---

### 7.9 AI-модерация контента — `ПЛАТНО` (копейки) — оценка: 2–3 дня — S

**Суть.** Автопроверка запросов/ответов через moderation-эндпоинт для корп-тенантов (compliance).

**Что переиспользуем.** Точка входа генерации `aitext/tasks.py:generate_ai_response`; `Organization` для пер-оргных политик.

**Архитектура.**
- Pre-check в начале `generate_ai_response` (за фиче-флагом `MODERATION_ENABLED` на уровне org): вызов moderation-эндпоинта laozhang (если есть; иначе классификация дешёвой моделью). При флаге → блок + лог в `UsageEvent(event_type='error', meta={'moderation':...})` и в аудит (`ProjectAuditEntry` паттерн).
- Настройка порогов на `Organization` (категории, действие block/flag).

**Риски.** Ложные срабатывания на русском (тюнинг порогов). Латентность pre-check — кэшировать вердикты по хэшу промта.

---

### 7.10 Real-time collaboration (Yjs) — `БЕСПЛАТНО` — оценка: 2–3 нед — L

**Суть.** Несколько пользователей одновременно видят/редактируют один чат или Canvas-документ (как Figma/Google Docs).

**Что переиспользуем.** `ProjectCollaborator` (роли viewer/editor, `aitext/models.py:248`) — модель доступа готова. Canvas-редактор (§5) — целевой документ для совместного редактирования.

**Архитектура (нетривиально — общий блокер с Voice).**
- **CRDT через Yjs.** Два варианта транспорта:
  - (а) **Отдельный `y-websocket` Node-процесс** (npm, MIT) рядом с Next.js — проще всего, состояние в его памяти/Redis. Аутентификация через JWT в query при connect, проверка `ProjectCollaborator`-роли через внутренний вызов к Django.
  - (б) Свой consumer на Django Channels (если уже мигрировали на ASGI ради Voice §7.1 — переиспользовать ту же инфру; `y-py` на питоне).
- **Рекомендация:** если §7.1 уже подняла ASGI — идти путём (б) и не плодить процессы; иначе (а) изолированно. **Сиквенсить §7.1 и §7.10 вместе.**
- **Persistence:** Yjs-документ периодически сериализуется в `Message.settings`/Canvas-хранилище; presence-курсоры — ephemeral (не персистим).
- **Frontend:** `y-prosemirror`/`y-codemirror` поверх Canvas-редактора, awareness для курсоров.

**Риски.** Самый сложный пункт §7. Конфликты CRDT решаются библиотекой, но интеграция с AI-правками (AI пишет в тот же документ) требует, чтобы AI-патчи применялись как Yjs-транзакции, а не перезапись. Память y-websocket на много документов.

---

### 7.11 Fine-tuning UI — `ПЛАТНО и дорого` — оценка: L — **отложить**

**Суть.** Разметка датасета в UI → запуск дообучения у провайдера → использование своей модели.

**Оценка целесообразности.** Fine-tuning дорог ($100+/модель + хранение), и **зависит от поддержки laozhang.ai** (нужен fine-tuning-эндпоинт — уточнить, скорее всего отсутствует у реселлера). Без провайдерской поддержки — нереализуемо.

**Альтернатива сейчас (рекомендуется вместо fine-tuning):** «псевдо-fine-tuning» через уже имеющиеся **Persona (system_prompt)** + **RAG (`ProjectChunk`)** + **few-shot из `PromptTemplate`**. Покрывает 80% запросов «обучи под нас» без реального дообучения и денежных затрат. Fine-tuning UI вернуть только при появлении провайдера с поддержкой.

**Риски.** Деньги, зависимость от провайдера, длительность обучения. → Не делать в горизонте плана.

---

### 7.12 Bot as OAuth provider — `БЕСПЛАТНО` — оценка: 1–1.5 нед — M

**Суть.** «Войти через Telegram/aineron» для внешних сервисов; aineron — identity provider.

**Что переиспользуем.** Привязка Telegram уже есть (`TelegramLinkToken`, `api/views/telegram_link.py`, Mini App initData HMAC в `telegram_webapp.py`). **`scaffold.validate_init_data`** (`studio/scaffold.py:230`) — готовая проверка подписи Telegram initData, переиспользуема для верификации входа.

**Архитектура.**
- **`django-oauth-toolkit`** (OAuth2 provider): эндпоинты `/o/authorize/`, `/o/token/`. Регистрация внешних приложений (client_id/secret) в кабинете.
- **Telegram-вход:** Telegram Login Widget / Mini App → initData → `validate_init_data` → выдача OAuth-кода → токен. `CustomUser` как identity.
- **UI:** `frontend/app/(dashboard)/dashboard/oauth-apps/` — управление приложениями; страница согласия (consent screen).

**Риски.** Безопасность OAuth (использовать проверенный toolkit, не самопис). Scope-модель.

---

### 7.13 Telegram polls → AI-анализ — `БЕСПЛАТНО` — оценка: 2–3 дня — S — **CODE-COMPLETE 2026-06-24**

**Суть.** Бот запускает опрос в группе → собирает ответы → строит AI-саммари/аналитику.

**Что переиспользуем.** Групповой режим (`TelegramGroup`, `handlers/group.py`), биллинг через оргу, LLM-пайплайн.

**Архитектура.**
- Команда `/poll` (FSM: вопрос + варианты) → `bot.send_poll`. Хендлер `poll_answer`/`poll`-update (aiogram) копит ответы в новой модели `telegram_bot.PollSession(group, poll_id, results)`.
- По `/poll close` или таймеру → агрегат → `generate_ai_response` (анализ распределения, инсайты) → пост в группу.
- Биллинг саммари — звёзды инициатора/оргпул.

**Риски.** Минимальны. Учёт анонимных опросов (Telegram не отдаёт авторов анонимных голосов — только агрегаты).

---

### 7.14 Scheduled AI reminders — `БЕСПЛАТНО` — оценка: 2–3 дня — S — **CODE-COMPLETE 2026-06-24**

**Суть.** Подписка на напоминание с AI-контекстом («каждое утро: сводка задач», «по пятницам: дайджест»).

**Что переиспользуем.** **`DatabaseScheduler` уже активен** (см. врезку) → динамические per-user расписания через `PeriodicTask`/`CrontabSchedule` без перезапуска beat. `/digest` (`handlers/digest_cmd.py`, `tasks.py:send_daily_digests`) — готовый паттерн доставки в бот. `_DIGEST_PROMPT` — образец AI-генерации по расписанию.

**Архитектура.**
- Команда `/remind` (FSM: текст/AI-промт + cron/время). На сохранение создаём `django_celery_beat.PeriodicTask` + `CrontabSchedule` (DB), указывающий на `telegram_bot.tasks.run_reminder(reminder_id)`. **Это идеологически чище текущего `/digest`** (который крутится «раз в минуту + фильтр по `digest_hour`») — для reminders сразу делаем нативные DB-расписания.
- Модель `telegram_bot.Reminder(user, prompt, schedule_ref, is_active)`.
- При срабатывании: `generate_ai_response`-стиль → доставка через `_bot_send` (паттерн из `tasks.py`).

**Риски.** Рост числа `PeriodicTask` (cleanup неактивных). Часовые пояса (`CELERY_TIMEZONE='Europe/Moscow'` — учитывать TZ пользователя).

> **Опциональная унификация:** §7.14 (reminders) и `/workflow` (§1.1) используют один механизм DatabaseScheduler — имеет смысл сделать общий слой `ScheduledTask(user, kind, schedule, payload)` и не плодить три похожие модели (digest/reminder/workflow). При рефакторе перевести и `/digest` на DB-расписания, убрав «раз в минуту».

### Резюме по деньгам

**Не требуют новых расходов (только разработка):**
Knowledge Graph, Model Arena с Elo, White-label, Billing seats, Zapier/Make, Real-time collaboration, Bot OAuth, Telegram polls, Scheduled reminders — итого **9 из 14 фич бесплатны**.

**Требуют API-расходов (платятся из маржи, покрываются ценой пользователя):**
Voice mode (ASR+TTS за звёзды), Image editor (звёзды), Video analysis (звёзды), AI-модерация (копейки).

**Требуют отдельных вложений:**
Fine-tuning — дорого ($100+/модель) и зависит от провайдера. Рекомендуется отложить.

> **Вывод:** большинство фич §7 реализуемы без дополнительных денег — только время. Voice mode и Video analysis монетизируются через звёзды пользователей, так что окупаются сразу при запуске.

---

## 8. Конкурентная матрица и дорожная карта синхронизации

### 8.1 Конкурентная матрица

Значения для aineron.ru — **реальное состояние кодовой базы** (не цель): `✓` готово в проде, `~` частично / code-complete / база есть / без оркестрации, `✗` нет. Для конкурентов — публично известные факты; где состояние неоднозначно, ставится консервативное `~`.

| Фича | aineron.ru | GigaChat | YandexGPT | ChatAI (chatai.ru) | ChatGPT | Claude.ai | Character.ai |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Canvas mode | ✗ (Sprint 7) | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| Code Interpreter (Python) | ~ (база Studio) | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| Voice mode (real-time) | ✗ (Sprint 9) | ✗ | ~ (Alice) | ✗ | ✓ | ✗ | ✓ |
| AI Personas | ~ (code-complete) | ✗ | ✗ | ✗ | ✓ | ~ | ✓ |
| No-code Agent builder | ✗ (Sprint 8) | ✗ | ✗ | ✗ | ~ (GPTs) | ✗ | ✗ |
| Artifacts | ~ (code-complete) | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| Мультиагентный чат | ~ (compare, без оркестрации) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Telegram-нативность (бот+группы+Stars) | ✓ | ~ | ~ | ✗ | ✗ | ✗ | ✗ |
| White-label B2B | ✗ (Sprint 9) | ~ | ~ | ✗ | ~ | ~ | ✗ |
| Knowledge base (RAG) | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| Model Arena | ~ (без Elo) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Batch API | ✓ | ~ | ~ | ✗ | ✓ | ✓ | ✗ |
| Webhooks | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

Легенда: `✓` есть · `~` частично / в плане / ограничено · `✗` нет.

**Чтение матрицы.** Против РФ-конкурентов aineron уже уникален по Telegram-нативности, Webhooks, Model Arena, Мультиагенту. Разрыв с ChatGPT/Claude — три заметные UX-фичи: Canvas, Code Interpreter (доводка), Voice. Это и задаёт порядок спринтов ниже.

### 8.2 Приоритеты синхронизации (Sprint 7–9)

> **Важно:** Canvas и Agent builder фигурировали как цели Sprint 5–6, но это были L-задачи, которые **не уместились** в те спринты (в 5–6 закрыты Artifacts/Personas/Smart-templates — code-complete). Sprint 7–9 — это вынесенные L-задачи плюс глобальный уровень. Противоречия с §5–6 нет.

**Sprint 7 — «Паритет с ChatGPT/Claude»: Canvas mode + Code Interpreter**
- **Цель:** закрыть два самых заметных пользователю UX-разрыва с глобальными лидерами.
- **Ключевые задачи:** `CanvasEditor.tsx` + тип сообщения `canvas` в `Message.settings` + `POST /chats/<id>/canvas/edit` (точечная правка диапазона AI); Code Interpreter — добавить python-runtime (matplotlib/pandas) в `Dockerfile.sandbox`, endpoint выполнения поверх `studio/sandbox.py:exec_command` (он уже выполняет произвольный shell, но образ Node-центричный — Python3 только как static-fallback), рендер stdout/plots в чате.
- **Эффект:** функциональный паритет с ChatGPT Canvas и Code Interpreter; сильнейший SEO-инфоповод.
- **Риски:** sandbox-безопасность исполнения Python (изоляция сети, лимиты — частично есть: `cap_drop`, `pids_limit`, `mem_limit`); Canvas-диффы AI должны быть инкрементальными, а не перезаписью (переиспользовать EditBlock-парсер из `MarkdownContent.tsx:391`).

**Sprint 8 — «Дифференциация от всех РФ-конкурентов»: No-code Agent builder + Workflow в боте**
- **Цель:** то, чего нет ни у одного РФ-конкурента; превратить Studio-агентов и Telegram в automation-платформу.
- **Ключевые задачи:** ввести **`AgentDefinition`** (tools[], steps[]) в `studio/models.py` — её **нет**, агенты сейчас code-defined (`BaseAgent`-подклассы, 13 шт.); UI drag-drop `frontend/app/studio/[id]/agent-builder`; мост code→DB (рантайм собирает пайплайн из `AgentDefinition`). `/workflow` в боте: модель `Workflow(trigger_cron, steps)` на нативном `DatabaseScheduler` (уже активен).
- **Эффект:** уникальная B2B-фича; Telegram как no-code automation-хаб.
- **Риски:** проектирование DSL шагов агента (не переусложнить); безопасность пользовательских tools.

**Sprint 9 — «Глобальный уровень»: Voice mode + White-label + Elo Arena**
- **Цель:** догнать ChatGPT по Voice, открыть enterprise-канал (White-label), запустить SEO-магнит (Elo).
- **Ключевые задачи:** разовая миграция на ASGI + `VoiceConsumer` (см. §7.1); `OrganizationBranding` + on-demand TLS (Caddy, §7.6); `ModelMatch`+Elo поверх `compare.py` (§7.5).
- **Эффект:** глобальный паритет по голосу, enterprise-продажи, публичный лидерборд.
- **Риски:** ASGI-миграция — главный (изолировать `/ws` на daphne, не трогать WSGI); латентность голоса; управление TLS-сертами (снимается Caddy).

### 8.3 Уникальные преимущества aineron (не копируются быстро)

1. **Telegram-нативность.** Полный бот + inline + групповой режим с оргбиллингом + Stars-оплата + Mini App + per-user изоляция групп. Это годы продуктовой работы; ChatGPT/Claude в РФ недоступны, GigaChat/YandexGPT имеют лишь базовых ботов.
2. **Открытый OpenAI-совместимый API + Webhooks (HMAC) + Batch.** Платформа как инфраструктура, а не только UI. РФ-конкуренты (ChatAI) этого не дают; Webhooks нет даже у ChatGPT/Claude в коробке.
3. **Personas + RAG + Studio в одной платформе.** Persistent Memory (`UserMemory`), KB на pgvector, sandbox-builder приложений и AI-персоны под одной крышей — комбинация, которой нет ни у кого из конкурентов целиком.
4. **Российская платёжная система (Robokassa) + локальный хостинг + оплата звёздами.** Оплата без VPN и зарубежных карт, данные в РФ — структурное преимущество перед ChatGPT/Claude и паритет с GigaChat/YandexGPT при кратно более широкой функциональности.

---

## 9. Синхронизация бот ↔ платформа

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
