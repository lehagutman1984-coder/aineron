# aineron.ru — MASTER PLAN (единый план продукта и разработки)

> Обновлён: 2026-06-24 | Модель: Claude Opus 4.8
> Этот документ заменяет `TOP1_PLAN.md` и `IMPLEMENTATION_PLAN_STAGE2.md`.
> Читают два адресата: ИИ-ассистент (чтобы продолжить разработку) и владелец продукта (чтобы понимать состояние).

**Цель продукта:** позиция #1 среди AI-платформ РФ (обойти GigaChat, YandexGPT, ChatAI) и функциональный паритет с ChatGPT / Claude.ai / Perplexity по ключевым возможностям (Canvas, Code Interpreter, Voice, Agents, Personas). Платформа — это OpenAI-совместимый API, веб-кабинет, Telegram-бот и B2B-инструменты.

Легенда статусов: ✅ Готово и задеплоено | ⚡ Code-complete (не тестировалось на проде) | 🔧 В процессе | 🚫 Не реализовано | ⚠️ Проблема провайдера

---

## 1. Текущий статус

### Telegram-бот
| Фича | Статус | Примечание |
|------|--------|-----------|
| FSM RedisStorage, меню 8 кнопок, онбординг, deeplinks, /start | ✅ | `src/telegram_bot/` |
| Покупка звёзд (Telegram Stars XTR + Robokassa), выбор пакета | ✅ | `handlers/payment.py` |
| История чатов с пагинацией, приём фото/документов | ✅ | `handlers/history.py`, `handlers/files.py` |
| Telegram Mini App (/tg/, initData HMAC, JWT) | ✅ | `api/views/telegram_webapp.py` |
| Inline-режим, групповой режим с оргбиллингом | ✅ | |
| Admin-команды, рассылка FSM | ✅ | `handlers/admin.py` |
| Голос ASR (Whisper) + TTS, кружочки (video_note) | ✅ | |
| /image /video /models /balance /settings /prompts /referral | ✅ | |
| Уведомления о низком балансе (Celery) | ✅ | |
| /img2video FSM (фото → Kling/Veo), /sticker FSM (512×512) | ✅ | |
| /ai (пост/email/бриф/код-ревью/summary/перевод) | ✅ | |
| /digest (дайджест по расписанию), /search, /export (MD) | ✅ | |
| Редактирование/удаление сообщений (EditMsgFSM) | ✅ | |
| /reggroup, /memory, Persistent Memory (UserMemory + RAG) | ✅ | |
| Реакции 👍/👎 → regenerate | ✅ | |
| BUG-2: per-user изоляция групп (TelegramGroupChat) | ✅ | |
| Stars/Robokassa кнопки при нехватке баланса, 7-дн. сводка в /balance | ✅ | |
| /translate по reply (EN/RU/DE/ES/FR/ZH), /persona | ✅ | |
| /remind + /reminders FSM (напоминания) | ✅ | Sprint 7 |
| /poll FSM (опросы → AI-анализ) | ✅ | Sprint 7 |
| /img2img FSM | ⚡ | нужна модель в каталоге |

### Платформа (веб + Django)
| Фича | Статус | Примечание |
|------|--------|-----------|
| DRF API OpenAI-совместимый (/api/v1/) | ✅ | `src/api/views/` |
| B2B: Organization, Member, Invite, оргбиллинг | ✅ | `src/teams/` |
| Projects (Gitea, AI-коммиты, KB pgvector) | ✅ | |
| Kanban-дашборд проектов (drag&drop) | ✅ | |
| Глобальный поиск Ctrl+K, экспорт PDF/MD | ✅ | |
| A/B тестирование промтов | ✅ | |
| Blog + SEO (JSON-LD, sitemap), Yandex.Metrika + GA4 | ✅ | |
| Batch API (Celery) | ✅ | `api/views/batch.py` |
| Webhooks (HMAC) через Celery с retry 10/60/300с | ✅ | Stage2, `aitext/tasks.py` |
| Embeddings API + Audio TTS/ASR API, /status/ page | ✅ | |
| Реферальная программа | ✅ | |
| EDIT Blocks (патч-коммиты любого размера) | ✅ | |
| Studio (AI app-builder в Docker-sandbox) | ✅ | |
| Collaborative Spaces (роли viewer/editor) | ✅ | |
| Model Arena / Compare (6 моделей) | ✅ | |
| Аудит-лог проектов | ✅ | |
| AI Personas (модель, API, UI /personas/, бот) | ✅ | `api/views/personas.py` |
| PromptTemplate.variables (smart templates, JSONField) | ✅ | |
| Model Arena Elo-рейтинг (ModelMatch, ArenaVoteView, /arena) | ✅ | Sprint 7 |
| Billing Seats (seats_count, seat_monthly_stars, Celery reset) | ✅ | Sprint 7 |
| Knowledge Graph (pgvector cosine, /projects/[id]/graph/) | ✅ | Sprint 7 |
| ASGI: daphne, nginx /ws/, CHANNEL_LAYERS (Redis DB 4) | ✅ | Stage2, `config/routing.py`, `config/asgi.py` |
| ModerationLog модель (0032) + check_moderation() | ✅ | код есть; см. §7 (флаг выкл.) |
| OrganizationBranding (subdomain, custom_domain, logo, colors) | ✅ | Stage2, `teams/models.py` |
| OrganizationBrandingMiddleware (Redis TTL 300s) + /v1/branding/ | ✅ | `teams/middleware.py`, `api/views/branding.py` |
| django-oauth-toolkit (PKCE), /oauth/ + TelegramOAuthBackend | ✅ | Stage2, `telegram_bot/oauth.py` |
| OAuth Apps UI (/account/oauth-apps/) | ✅ | |
| YjsConsumer (broadcast + snapshot в Project.yjs_state) | ✅ | `aitext/consumers.py` |
| VoiceConsumer (ASR → LLM → TTS, half-duplex) | ✅ | `aitext/voice_consumers.py` |
| Hooks useYjsProject.ts + useVoiceChat.ts, yjs/y-websocket | ✅ | frontend |
| ArtifactPanel (React/HTML/SVG/Mermaid preview в чате) | ⚡ | `frontend/components/chat/ArtifactPanel.tsx` |
| AI-модерация (/v1/moderations) | ⚠️ | формат провайдера неверный, флаг выкл. — см. §7 |
| White-label Этап A (субдомены *.aineron.ru) | 🔧 | код готов, нужен wildcard SSL + DNS |
| White-label Этап B (кастомные домены клиентов) | 🚫 | нужен Caddy on-demand TLS / certbot-хук |
| Canvas mode (CanvasEditor.tsx + тип canvas в Message) | 🚫 | Sprint 8 |
| Code Interpreter (Python в sandbox) | 🚫 | python-runtime в Dockerfile.sandbox |
| No-code Agent builder (AgentDefinition) | 🚫 | модели нет |
| BUG-1: TEXT_BILLING_ENABLED | 🚫 | флаг=0 намеренно, см. §3 |

---

## 2. Критические P0-задачи

1. **BUG-1 — включить TEXT_BILLING_ENABLED (ежедневная потеря выручки).**
   Флаг написан, стоит `0`. Списание звёзд за текст не идёт. Порядок включения: рассылка в боте → бонус активным пользователям → включить флаг. Это P0 — каждый день без него = недополученная выручка.
2. **White-label wildcard cert.** Этап A полностью готов в коде (middleware, branding API, frontend). Блокер чисто инфраструктурный: нужен wildcard SSL-сертификат `*.aineron.ru` + DNS wildcard A-запись. DevOps-задача.
3. **AI-модерация (провайдер).** Код готов, флаг `MODERATION_ENABLED=0`, провайдер laozhang.ai возвращает неверный формат. Детали и пути решения — §7.

---

## 3. BUG-1 (TEXT_BILLING_ENABLED) — подробно

- Текущее: `TEXT_BILLING_ENABLED=0`. Текстовые ответы не тарифицируются.
- Почему отключено намеренно: до включения нужно предупредить пользователей рассылкой и выдать бонус активным, иначе резкий отток.
- План: (1) подготовить рассылку в боте, (2) начислить бонус активным за последние N дней, (3) включить флаг, (4) мониторить отток/выручку первые сутки.
- Приоритет: **P0**, это прямая ежедневная потеря выручки.

---

## 4. Дорожная карта

### Sprint 8 (ближайший)
- Включить BUG-1 (рассылка + бонус + флаг). **P0**
- Canvas mode: `CanvasEditor.tsx` + тип `canvas` в `Message.settings`.
- Протестировать на проде ArtifactPanel и /img2img (добавить модель в каталог).
- White-label Этап A: оформить DevOps-тикет на wildcard SSL + DNS, после — прод-проверка субдоменов.

### Sprint 9
- Code Interpreter: python-runtime в `Dockerfile.sandbox`, `code_exec.py`, `CodeRunOutput.tsx`.
- White-label Этап B: Caddy on-demand TLS или certbot-хук для кастомных доменов клиентов.
- No-code Agent builder: модель `AgentDefinition` в `studio/models.py`, UI, рантайм.
- Telegram-бот: Smart templates FSM (/prompts с заполнением `{var}`) — M.

### Long-term
- Мультиагентный чат (веб и бот).
- /workflow в боте (модель Workflow + DatabaseScheduler).
- Inline 2.0 (несколько InlineQueryResultArticle).
- Авто-рассылка release notes, групповой /stat для B2B.

### Заморожено — высокая стоимость эксплуатации (не реализовывать без решения по монетизации)

Эти фичи намеренно пропущены: расходы на API растут с каждым пользователем, а цена их включения выше пользы на текущем масштабе.

| Фича | Почему отложено |
|------|----------------|
| §C1 Voice mode (real-time, голосовая комната) | ASR/TTS за каждую минуту разговора — прямые расходы на провайдера |
| §C2 Image editor / inpainting | API-вызовы к laozhang на каждую правку — дорого при активном использовании |
| §C3 Video analysis (транскрипция загружаемых видео) | FFmpeg + ASR + vision — расходы на каждый видеофайл |
| §C4 AI moderation (pre-check каждого сообщения) | Провайдер laozhang.ai возвращает неверный формат (⚠️ §7); даже если починить — расход на каждое сообщение |
| §C5 Fine-tuning UI | Дорого + сложно; рекомендовано заменить улучшенным RAG+Persona (уже реализовано) |

**Условие разморозки:** выбрать одно из двух — (а) перевести фичу на тарифный план (пользователь платит за каждый вызов), или (б) объём пользователей вырос до уровня, когда расход укладывается в unit economics.

---

## 5. Технический долг

| Приоритет | Долг |
|-----------|------|
| P0 | BUG-1 не включён — потеря выручки |
| P1 | Модерация не работает из-за провайдера (флаг выкл., код в except → flagged:False) |
| P1 | White-label A заблокирован инфраструктурой (wildcard cert/DNS) |
| P2 | ArtifactPanel и /img2img code-complete, но не проверены на проде |
| P2 | White-label B требует динамического TLS |
| P3 | Bot: Smart templates FSM, мультиагент, групповой /stat, release notes, Inline 2.0 |

---

## 6. Для разработки (ИИ-ассистент)

**Стек:** Django + DRF (OpenAI-совместимый API), Celery (Redis broker), ASGI через daphne (WebSockets), Next.js frontend, PostgreSQL + pgvector, Telegram-бот на aiogram (FSM RedisStorage). Деплой: `bash deploy.sh`. После коммита — сразу `git push origin main`.

**Провайдеры AI (актуальные):**
- `api.laozhang.ai` — текст (chat completions, streaming) + изображения + ASR/TTS + embeddings
- `api.apimart.ai` — видео: Sora 2, Veo 3.1, Kling 1.6/2.1, Wan 2.1, Hunyuan, Seedance 1.5 Pro/2.0. Ключ: `APIMART_API_KEY` в `.env`, URL: `settings.APIMART_API_URL`. Роутинг: `NeuralNetwork.config_json.metadata.video_api == 'apimart'` → `fal_utils.generate_video_apimart()` → POST `https://api.apimart.ai/v1/videos/generations`
- `fal.ai` и `openrouter` — НЕ подключены и НЕ используются. Строка `provider='fal-ai'` в модели `NeuralNetwork` — это устаревший DB-ключ ветвления (legacy), реальные запросы к fal.ai/openrouter не идут. Рефактор этого поля — отдельный PR с data-migration (P3, не горит).
- Telegram-бот (`/video`, `/img2video`) — тот же путь: `fal_utils.generate_video_apimart()` → `api.apimart.ai`. Бот и веб используют одну функцию.

**Ключевые директории/файлы:**
- API: `src/api/views/` (chat.py, batch.py, webhooks.py, embeddings.py, audio.py, personas.py, branding.py, compare.py, referral.py, telegram_webapp.py, api_status.py).
- Текст/AI ядро: `src/aitext/models.py`, `tasks.py` (Celery: webhooks с retry, reset_monthly_seats), `moderation.py`, `consumers.py` (YjsConsumer), `voice_consumers.py` (VoiceConsumer).
- B2B: `src/teams/models.py` (Organization, Member, Invite, OrganizationBranding, seats), `teams/middleware.py` (OrganizationBrandingMiddleware).
- ASGI/Channels: `src/config/asgi.py`, `config/routing.py`, `config/channel_auth.py`, `config/settings.py` (CHANNEL_LAYERS → Redis DB 4), `nginx.conf` (/ws/).
- OAuth: `src/telegram_bot/oauth.py` (TelegramOAuthBackend, HMAC + auth_date freshness), django-oauth-toolkit (PKCE required, /oauth/).
- Бот: `src/telegram_bot/views.py`, `handlers/*` (menu, onboarding, start, payment, history, files, admin, balance, chat, digest_cmd, export_cmd).
- Frontend: `frontend/app/` (arena, compare, layout, sitemap), `frontend/components/chat/ArtifactPanel.tsx`, хуки `useYjsProject.ts`, `useVoiceChat.ts`.

**Архитектурные решения:**
- ASGI-миграция была блокером для Voice (§7.1) и Yjs (§7.10) — теперь снята: daphne-контейнер, WS через nginx `/ws/`, CHANNEL_LAYERS на Redis DB 4.
- Webhooks переведены с прямой доставки на Celery-задачи (retry 10/60/300с) для надёжности.
- Branding-резолвинг кэшируется в Redis (TTL 300s) в middleware, чтобы не бить БД на каждый запрос субдомена.
- Модерация вставлена в `generate_ai_response`, но завязана на флаг `MODERATION_ENABLED` (см. §7); при ошибке возвращает `flagged:False` (fail-open).
- Дизайн UI: ноль эмодзи, только Lucide React, строгий профессиональный стиль (эмодзи в этом документе — только статусные иконки).

---

## 7. Проблема с провайдером laozhang.ai

**Что работает:** чат-комплешны, стриминг, embeddings, audio TTS/ASR, генерация изображений — через api.laozhang.ai. Видеогенерация — через api.apimart.ai (Sora, Veo, Kling, Wan, Seedance, Hunyuan).

**Что не работает — AI-модерация (§7.9, ⚠️):**
- Эндпоинт `/v1/moderations` у провайдера существует, но отдаёт неверный формат.
- Ожидалось: `{"results": [{"flagged": false, "categories": {...}}]}`.
- Пришло: `{"choices": null, "usage": {...}}` — структура чат-комплешна вместо модерации.
- Итог: `MODERATION_ENABLED=0`. Код в `src/aitext/moderation.py` написан, но падает в `except` и возвращает `flagged: False` (fail-open, ничего не блокирует).

**Как решить (варианты):**
1. Подключить прямой OpenAI API key для бесплатного эндпоинта `/v1/moderations` (только для модерации) и включить флаг.
2. Дождаться корректной поддержки модерации у laozhang.ai.

До решения модерация фактически выключена — это осознанный временный компромисс, а не баг кода.

---

## 8. Для пользователей и бизнеса (простым языком)

Aineron — это AI-платформа: общение с лучшими нейросетями, генерация текста, картинок и видео, голосовой режим, плюс инструменты для команд и разработчиков. Доступ через сайт, Telegram-бот и API.

### Что может пользователь
- Общаться с разными AI-моделями в одном месте, сравнивать их ответы и выбирать лучшую.
- Генерировать тексты, изображения и видео; превращать фото в видео; делать стикеры.
- Использовать голосовой режим: говорить — и получать голосовой ответ.
- Хранить историю переписок, искать по ней, экспортировать в PDF или Markdown.
- Создавать «персон» (AI с заданным характером и ролью) и шаблоны запросов.
- Платить удобно — звёздами (пополнение через Telegram Stars или Robokassa), видеть баланс и недельную сводку расходов.
- Приглашать друзей по реферальной программе и получать бонусы.

### Что может бизнес / B2B
- Заводить организацию, приглашать сотрудников, управлять ролями и доступами.
- Единый счёт и биллинг на команду: оплата по «местам» (seats) с месячным лимитом.
- Получать OpenAI-совместимый API — подключать AI в свои продукты и IDE (Cursor, VS Code, Continue).
- White-label: своя витрина на поддомене с логотипом и цветами компании (запуск после настройки сертификата).
- Совместная работа над проектами: общий доступ, роли «просмотр/редактирование», совместное редактирование в реальном времени.
- Управление проектами с Kanban-доской, база знаний с умным поиском, граф знаний.
- Контроль и прозрачность: журнал действий (аудит), вебхуки для интеграций, пакетная обработка запросов.

### Что умеет Telegram-бот
- Полноценный AI-чат прямо в Telegram, с историей и поиском по ней.
- Генерация картинок, видео и стикеров; распознавание присланных фото и документов.
- Голосовые сообщения и видео-кружочки: бот понимает голос и отвечает голосом.
- Готовые команды-помощники: написать пост или письмо, сделать бриф, код-ревью, краткую выжимку, перевод.
- Напоминания с таймером и опросы с автоматическим разбором результатов.
- Ежедневный персональный дайджест, экспорт переписки.
- Персональная память: бот запоминает важное о вас и учитывает в ответах.
- Покупка звёзд внутри бота, оповещения о низком балансе.
- Работа в группах с раздельным контекстом и биллингом для команд.
- Мини-приложение (Mini App) с расширенным интерфейсом внутри Telegram.

---

## 9. Telegram-бот: UX/UI редизайн (фронт уровня топов)

> Цель: из «текстового терминала» — в профессиональный продукт с визуальным языком, брендингом и интуитивной навигацией. Без внешних зависимостей — только HTML-разметка aiogram + эмодзи.

### 9.1 Визуальная система

**Цветовые маркеры раздела (константы в `utils.py`):**
```python
MARK = {
    'chat':    '🔵',  # Чат / AI-ответы
    'image':   '🟣',  # Изображения
    'video':   '🔴',  # Видео
    'balance': '⭐',  # Баланс / платежи
    'models':  '🤖',  # Модели
    'settings':'⚙️',  # Настройки
    'history': '🕑',  # История
    'projects':'📁',  # Проекты
    'help':    '❓',  # Помощь
    'success': '🟢',  # Успех
    'warning': '🟡',  # Предупреждение
    'error':   '🔴',  # Ошибка (= video; ОК — раздел из контекста)
    'neutral': '⚪',  # Нейтральный
}
DIVIDER = '─' * 20   # ────────────────────
```

**Шаблоны карточек (helpers в `utils.py`):**
```python
def card(icon: str, title: str, body: str, footer: str = '') -> str:
    parts = [f'{icon} <b>{title}</b>', DIVIDER, body]
    if footer:
        parts += [DIVIDER, f'<i>{footer}</i>']
    return '\n'.join(parts)

def success_card(title: str, body: str) -> str:
    return card('🟢', title, body)

def error_card(title: str, body: str) -> str:
    return card('🔴', title, body)

def warning_card(title: str, body: str) -> str:
    return card('🟡', title, body)
```

**Индикатор прогресса (для длинных операций):**
```python
PROGRESS = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
# usage: await msg.edit_text(f'{PROGRESS[i % 10]} Генерирую видео...')
```

---

### 9.2 Новая клавиатура 3×3

**Файл:** `src/telegram_bot/keyboards.py` — заменить `main_reply_kb()`:

```python
def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🔵 Чат'),     KeyboardButton(text='🟣 Картинка'), KeyboardButton(text='🔴 Видео')],
            [KeyboardButton(text='⭐ Баланс'),  KeyboardButton(text='🤖 Модели'),   KeyboardButton(text='⚙️ Настройки')],
            [KeyboardButton(text='📁 Проекты'), KeyboardButton(text='🕑 История'),  KeyboardButton(text='❓ Помощь')],
        ],
        resize_keyboard=True,
        input_field_placeholder='Напиши вопрос или выбери раздел...',
    )
```

**Нормализация кнопок в `menu.py`** (чтобы `F.text.in_()` работал с эмодзи-префиксами):

```python
import re

# Новый список с эмодзи
MENU_BUTTONS = {
    '🔵 Чат', '🟣 Картинка', '🔴 Видео',
    '⭐ Баланс', '🤖 Модели', '⚙️ Настройки',
    '📁 Проекты', '🕑 История', '❓ Помощь',
}

# Нормализатор: '🔵 Чат' → 'чат'
def _btn_key(text: str) -> str:
    return re.sub(r'^[^\w]+', '', text or '').strip().lower()

KEY_MAP = {_btn_key(b): b for b in MENU_BUTTONS}
# 'чат' → '🔵 Чат', 'картинка' → '🟣 Картинка', ...
```

Маппинг в хэндлере: `key = _btn_key(message.text)` вместо `message.text == 'Чат'`.

---

### 9.3 Экраны — готовые HTML-строки

**Welcome / /start (новый пользователь):**
```html
🤖 <b>Добро пожаловать в aineron.ru</b>
────────────────────
Я — AI-ассистент с доступом к лучшим нейросетям мира.

<b>Что умею:</b>
• 🔵 Чат с GPT-4o, Claude, Gemini и другими
• 🟣 Генерация изображений (DALL·E, Stable Diffusion)
• 🔴 Генерация видео (Sora, Veo 3, Kling)
• 🎤 Голосовые сообщения и видео-кружочки
• 📁 Проекты с базой знаний

<b>Для начала:</b> привяжи аккаунт на aineron.ru
Кабинет → Telegram → «Подключить»
```

**Dashboard (авторизованный /start):**
```html
🔵 <b>Привет, {first_name}!</b>
────────────────────
⭐ Баланс: <b>{balance} звёзд</b>
🤖 Модель: <b>{model_name}</b>
────────────────────
Выбери действие в меню ниже или просто напиши вопрос.
```

**Balance экран (`send_balance`):**
```html
⭐ <b>Баланс</b>
────────────────────
Звёзды: <b>{balance}</b>
7 дней: потрачено <b>{week_spent}</b> зв.

<b>Пополнить:</b>
```
→ inline-кнопки пакетов звёзд + кнопка «🌐 Открыть кабинет»

**Low-balance предупреждение (автоматически при < 20 зв.):**
```html
🟡 <b>Заканчиваются звёзды</b>
────────────────────
Остаток: <b>{balance} зв.</b> — хватит примерно на {estimate}.
Пополни, чтобы продолжить без перерывов.
```

**Settings экран:**
```html
⚙️ <b>Настройки</b>
────────────────────
🔊 Голосовые ответы: <b>{voice}</b>
🔍 Веб-поиск: <b>{search}</b>
⚡ Стриминг: <b>{streaming}</b>
🤖 Модель: <b>{model_name}</b>
```

**Models экран (заголовок таба):**
```html
🤖 <b>Выбор модели</b>   •   [ Текст ] | Изображения | Видео
────────────────────
Текущая: <b>{model_name}</b>
```

**Help экран:**
```html
❓ <b>Помощь</b>
────────────────────
<b>Чат:</b> просто напиши вопрос
<b>Медиа:</b>
  /image &lt;описание&gt; — картинка
  /video &lt;описание&gt; — видео (5-15 мин)
  /img2video — фото → анимация
  /sticker &lt;описание&gt; — стикер

<b>Инструменты:</b>
  /ai — агенты (пост, письмо, код-ревью, перевод)
  /digest — дайджест, /export — скачать чат
  /remind — напоминания, /poll — опросы
  /memory — что бот помнит о вас
  /search &lt;запрос&gt; — поиск по истории

<b>Аккаунт:</b>
  /balance — баланс и пополнение
  /referral — реферальная программа

🌐 aineron.ru — полный кабинет
```

**Ошибка (унифицированная, через `error_card()`):**
```html
🔴 <b>Ошибка</b>
────────────────────
{описание — краткое, без stack trace}
────────────────────
<i>Если ошибка повторяется — напиши /start</i>
```

---

### 9.4 Mini App промо (после первого успешного ответа чата)

```python
# В chat.py, после отправки AI-ответа, раз в 10 сообщений:
if tg_user.message_count % 10 == 0:
    from telegram_bot.keyboards import webapp_kb
    await message.answer(
        '📱 <b>Совет:</b> в Mini App удобнее — история, файлы, полноэкранный чат.',
        parse_mode='HTML',
        reply_markup=webapp_kb(settings.SITE_URL),
    )
```

---

### 9.5 Этапы внедрения

#### Этап 1 — S (≈ ½ дня): визуальный язык + клавиатура

1. `utils.py` — добавить `MARK`, `DIVIDER`, `card()`, `success_card()`, `error_card()`, `warning_card()`, `PROGRESS`
2. `keyboards.py` — новая `main_reply_kb()` (3×3 с эмодзи)
3. `menu.py` — обновить `MENU_BUTTONS`, добавить `_btn_key()`, переписать `handle_menu_button` на нормализованный маппинг
4. `start.py` — новый welcome HTML + dashboard HTML (использовать `card()`)
5. Деплой + ручной тест /start, всех кнопок меню

#### Этап 2 — M (≈ ½–1 день): экраны разделов

6. `balance.py` — новый `send_balance` с карточкой + inline пополнения
7. `handlers/settings_cmd.py` — `send_settings` с HTML-карточкой настроек
8. `handlers/models_cmd.py` — заголовок табов с текущей моделью
9. `menu.py` — контекстные подсказки для 🔵 Чат / 🟣 Картинка / 🔴 Видео с примерами команд
10. Унифицировать обработку ошибок: `error_card()` везде (chat.py, images.py, video_cmd.py, img2video_cmd.py)

#### Этап 3 — M (≈ 1 день): онбординг + полировка

11. `handlers/onboarding.py` — переработать шаги онбординга с карточками, прогресс-индикатором
12. `handlers/balance.py` — low-balance предупреждение (`warning_card()`) в Celery-задаче
13. `chat.py` — Mini App промо каждые 10 сообщений (§9.4)
14. `keyboards.py` — `settings_kb()` с эмодзи-метками toggle-кнопок
15. `handlers/help.py` (или `menu.py`) — финальный help-экран из §9.3
16. Финальный тест всех FSM: /image, /video, /img2video, /remind, /poll, /ai, /persona

---

### 9.6 Критические требования при внедрении

- Все экраны — `parse_mode='HTML'`. Никакого Markdown (он ломается на спецсимволах).
- `F.text.in_(MENU_BUTTONS)` должен матчить **точный текст кнопки с эмодзи** — обновить `MENU_BUTTONS` синхронно с `main_reply_kb()`.
- Не трогать FSM-состояния и callback_data — только текстовые ответы и клавиатуры.
- `DIVIDER = '─' * 20` — U+2500, не тире и не минус.
- Деплой через `bash deploy.sh` (с пересборкой) или `docker-compose restart web` (только Python-файлы).
