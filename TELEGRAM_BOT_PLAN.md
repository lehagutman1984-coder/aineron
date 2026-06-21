# aineron.ru — Telegram-бот: Обновлённый план

> **Обновлён:** 2026-06-21 | Ветка: `feature/telegram-bot`  
> **Цель:** лучший AI-бот в российском Telegram — уровень выше RUGPT, Syntx, VLEX.

---

## Что изменилось по сравнению со старым планом

| Было (план 2026-06-14) | Стало (актуально) |
|---|---|
| Провайдер изображений: fal.ai | laozhang.ai — через существующую `generate_ai_response` задачу |
| Видео: fal.ai | apimart.ai (уже в `fal_utils.py`) — тот же путь через задачу |
| Модели: «GPT-4o mini, Flux Pro» (имена) | Реальные `model_name` из БД NeuralNetwork по id/slug |
| Asyncio мост: не описан | `asgiref.sync.async_to_sync` + `sync_to_async` — явное решение |
| aiogram в requirements: отсутствует | Добавить `aiogram>=3.17,<4.0` |
| nginx: нет `/telegram/` роута | Добавить `location /telegram/` → Django web:8000 |
| 22 раздела → 6+ этапов | 10 сессий / 13 коммитов — чёткая граница |

---

## Что убрали из плана (и почему)

| Убрано | Причина |
|---|---|
| Inline-режим (`@aineron_bot`) | Сложная реализация, низкий приоритет для MVP |
| Групповые чаты | Усложняет биллинг, модерацию — отдельный product |
| Руки-без-рук голосовой режим | Edge case, сложно без Web Audio |
| Регистрация прямо в боте (без сайта) | Привязка через сайт — надёжнее и проще |
| /stats пользователя | Уже есть в web-кабинете `/account/analytics/` |
| image-to-image | Фаза 2+ после запуска MVP |
| PDF и документы | Фаза 2+ после запуска MVP |
| Vision / анализ фото | Фаза 2+ после запуска MVP |
| `/imagine` алиас | Не нужен без inline-режима |

---

## Связь с STUDIO_V4 (TMA)

Два независимых Telegram-продукта в одном проекте:

| | Продуктовый бот (этот план) | TMA Studio (уже в V4) |
|---|---|---|
| Переменная | `TELEGRAM_BOT_TOKEN` | `STUDIO_TMA_BOT_TOKEN` |
| Назначение | AI-чат для всех пользователей aineron.ru | Бот-лаунчер для Mini App, сгенерированного Studio |
| Целевая аудитория | Конечные пользователи | Разработчики / клиенты Studio |
| Связь | `TelegramUser` → `CustomUser` | Отдельная TMA-сборка |

**Точка синергии в будущем:** продуктовый бот может открывать Studio-TMA через кнопку `web_app`. `TelegramUser.telegram_id` понадобится обоим — поэтому модель общая.

---

## Стек (актуальный)

| Компонент | Технология |
|---|---|
| Фреймворк бота | aiogram 3.x (asyncio) |
| Asyncio мост | `asgiref.sync.async_to_sync` (уже в Django deps) |
| ORM в async-хендлерах | `asgiref.sync.sync_to_async` |
| Webhook endpoint | Sync Django view → `async_to_sync(dp.feed_update)(bot, update)` |
| Состояния FSM | Redis (уже в docker-compose) |
| AI-текст | `generate_ai_response.delay(message_id)` — переиспользуем как есть |
| AI-изображения | Та же задача — указываем image-нейросеть (provider='fal-ai') |
| TTS / ASR | Прямой вызов laozhang.ai API (минуя `/api/v1/audio/` — избегаем auth complexity) |
| БД | PostgreSQL — новые таблицы в `src/telegram_bot/` |
| Деплой | Вебхук через Django `web` сервис; polling dev-mode через management command |

### Asyncio мост — конкретная реализация

```python
# src/telegram_bot/views.py
from asgiref.sync import async_to_sync
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .bot import bot, dp
import json
from aiogram import types

@csrf_exempt
def telegram_webhook(request):
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        return HttpResponse(status=403)
    data = json.loads(request.body)
    update = types.Update.model_validate(data)
    async_to_sync(dp.feed_update)(bot, update)
    return HttpResponse('ok')
```

```python
# В хендлерах — ORM только через sync_to_async
from asgiref.sync import sync_to_async
get_tg_user = sync_to_async(TelegramUser.objects.select_related('user').get)
```

---

## Структура приложения

```
src/telegram_bot/
├── __init__.py
├── apps.py
├── models.py             # TelegramUser, TelegramChat, TelegramLinkToken
├── bot.py                # bot instance, dp (Dispatcher)
├── views.py              # Sync Django webhook view
├── notify.py             # send_notification() — sync wrapper для Celery
├── middlewares.py        # AuthMiddleware (sync_to_async ORM), antispam
├── keyboards.py          # Inline клавиатуры
├── utils.py              # markdown → MarkdownV2 конвертер, split_message
├── admin.py
├── migrations/
│   └── 0001_initial.py
├── management/commands/
│   └── run_bot.py        # dev polling mode
└── handlers/
    ├── __init__.py
    ├── start.py          # /start, привязка аккаунта
    ├── chat.py           # Текстовый чат с AI + polling + edit streaming
    ├── balance.py        # /balance, /buy
    ├── payment.py        # successful_payment обработчик
    ├── models_cmd.py     # /models — смена модели
    ├── voice.py          # STT (голосовые → Whisper) + TTS кнопка
    ├── images.py         # /image генерация
    ├── prompts_cmd.py    # /prompts библиотека
    ├── settings_cmd.py   # /settings FSM
    └── referral.py       # /referral
```

---

## Модели БД

```python
class TelegramUser(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='telegram')
    telegram_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    telegram_first_name = models.CharField(max_length=100, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    # Настройки
    default_network = models.ForeignKey('aitext.NeuralNetwork', null=True, blank=True, on_delete=models.SET_NULL)
    voice_responses = models.BooleanField(default=False)
    web_search = models.BooleanField(default=False)
    system_prompt = models.TextField(blank=True)
    streaming = models.BooleanField(default=True)   # edit_message эффект
    # Антиспам
    last_message_at = models.DateTimeField(null=True)
    messages_today = models.PositiveIntegerField(default=0)
    messages_today_date = models.DateField(null=True)

class TelegramChat(models.Model):
    tg_user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE)
    chat = models.ForeignKey('aitext.Chat', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

class TelegramLinkToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
```

---

## Конкурентное позиционирование (MVP)

| Фича | RUGPT | Syntx | VLEX | aineron (MVP) |
|---|---|---|---|---|
| Текстовый чат | + | + | + | + |
| Выбор модели | + | + | - | + |
| Streaming (edit_msg) | - | + | - | + |
| Генерация изображений | - | + | + | + |
| Голосовые STT | + | + | - | + |
| TTS (ответ голосом) | - | - | - | + |
| Telegram Stars оплата | - | - | - | + |
| Веб-поиск | - | - | - | + |
| Промпт-библиотека | - | - | - | + |
| Уведомления | + | + | + | + |
| Реферальная программа | + | - | + | + |
| Единый аккаунт с сайтом | - | + | - | + |

**Уникальные фичи aineron:** TTS-ответы, Telegram Stars, веб-поиск, промпт-библиотека, единый аккаунт с web-кабинетом.

---

---

# ПЛАН ПО СЕССИЯМ И КОММИТАМ

## Как читать

Правила те же, что в STUDIO_V4_COMMITS.md:
- 1 сессия = 1 рабочий контекст Sonnet (1 коммит, максимум 3 связанных)
- Фича-флаг `TELEGRAM_BOT_ENABLED` (default=0) — весь бот выключен пока не готов к запуску
- Миграции — вручную, без `makemigrations` (Docker не запущен локально)
- FE и BE в разных сессиях

---

## ФАЗА 0 — Инфраструктура (2 сессии)

---

### Сессия 0.1 — App + модели + миграция

**Цель:** создать Django-приложение с моделями. Чисто аддитивно — ничего не сломает.  
**Флаг:** нет (миграция не требует флага)  
**Файлы:** `src/telegram_bot/` (новая папка), `src/config/settings.py`

#### Коммит 0.1.1 — django app telegram_bot + models

Что делать точно:

1. Создать `src/telegram_bot/__init__.py`, `apps.py` (AppConfig name='telegram_bot'), `admin.py`

2. `src/telegram_bot/models.py` — три модели (код выше в разделе «Модели БД»)

3. `src/telegram_bot/migrations/0001_initial.py` — написать вручную (не запускать makemigrations)

4. `src/config/settings.py` — в блок после `STUDIO_V4_*` добавить:
   ```python
   # ── Telegram Bot ──────────────────────────────────────────────────────────
   TELEGRAM_BOT_ENABLED       = os.getenv('TELEGRAM_BOT_ENABLED',    '0') == '1'
   TELEGRAM_BOT_TOKEN         = os.getenv('TELEGRAM_BOT_TOKEN',      '')
   TELEGRAM_WEBHOOK_SECRET    = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
   TELEGRAM_BOT_USERNAME      = os.getenv('TELEGRAM_BOT_USERNAME',   'aineron_bot')
   ```
   Добавить `'telegram_bot'` в `INSTALLED_APPS`.

5. `src/telegram_bot/admin.py` — зарегистрировать `TelegramUser`, `TelegramChat`, `TelegramLinkToken`

Что НЕ делать: не трогать `urls.py`, не создавать `bot.py`, не устанавливать aiogram.

**Верификация:** `python -c "import sys; sys.path.insert(0, 'src'); from telegram_bot import models; print('ok')"` не падает.

---

### Сессия 0.2 — Bot core + webhook + docker

**Цель:** бот принимает updates через вебхук Django; локально запускается через polling.  
**Флаг:** `TELEGRAM_BOT_ENABLED` — URL добавляется только если True  
**Файлы:** `src/requirements.txt`, `src/telegram_bot/bot.py`, `src/telegram_bot/views.py`, management command, `src/config/urls.py`, `nginx.conf`, `docker-compose.yml`

#### Коммит 0.2.1 — aiogram dep + bot core + webhook view + nginx + docker

1. `src/requirements.txt`: добавить строку `aiogram>=3.17,<4.0`

2. `src/telegram_bot/bot.py`:
   ```python
   from aiogram import Bot, Dispatcher
   from django.conf import settings

   bot = Bot(token=settings.TELEGRAM_BOT_TOKEN or 'placeholder:placeholder')
   dp = Dispatcher()
   ```

3. `src/telegram_bot/views.py` — sync webhook view (код из раздела «Asyncio мост» выше)

4. `src/telegram_bot/management/__init__.py`, `commands/__init__.py`, `commands/run_bot.py`:
   ```python
   import asyncio
   from django.core.management.base import BaseCommand
   from telegram_bot.bot import bot, dp

   class Command(BaseCommand):
       help = 'Telegram bot polling (dev only)'
       def handle(self, *args, **options):
           asyncio.run(dp.start_polling(bot))
   ```

5. `src/config/urls.py` — в конец добавить:
   ```python
   from django.conf import settings
   if settings.TELEGRAM_BOT_ENABLED:
       from telegram_bot import views as tg_views
       urlpatterns += [path('telegram/webhook/', tg_views.telegram_webhook)]
   ```

6. `nginx.conf` — добавить перед блоком `location /api/`:
   ```nginx
   location /telegram/ {
       proxy_pass http://web:8000;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

7. `docker-compose.yml` — добавить сервис (для polling dev-mode):
   ```yaml
   telegram_bot:
     build: .
     command: python manage.py run_bot
     env_file: .env
     depends_on: [redis, db]
     restart: unless-stopped
     volumes:
       - media_volume:/app/src/media
     profiles: [bot]  # docker-compose --profile bot up
   ```
   Профиль `bot` — сервис не стартует по умолчанию, только явным запуском.

**Верификация:** `python -c "from telegram_bot.bot import bot, dp; print('ok')"` не падает.

---

## ФАЗА 1 — MVP чат (3 сессии)

---

### Сессия 1.1 — /start + link flow

**Цель:** пользователь привязывает Telegram к аккаунту aineron.ru.  
**Файлы:** `src/telegram_bot/handlers/start.py`, `src/api/views/telegram_link.py`, `src/api/urls.py`

#### Коммит 1.1.1 — /start handler + TelegramLinkTokenView API

**Backend API** — `src/api/views/telegram_link.py`:
- `POST /api/v1/telegram/link-token/` — создаёт `TelegramLinkToken(expires_at=now+15min, token=secrets.token_urlsafe(32))`
- Возвращает: `{"link": "https://t.me/{BOT_USERNAME}?start={token}", "expires_in": 900}`
- Auth: JWT required (как все остальные API)
- Добавить в `src/api/urls.py`: `path('v1/telegram/link-token/', TelegramLinkTokenView.as_view())`

**Bot handler** — `src/telegram_bot/handlers/start.py`:
```python
@dp.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)[1] if ' ' in message.text else ''
    
    if args and not args.startswith('ref_'):
        # Попытка привязки по токену
        link_token = await get_link_token(args)  # sync_to_async
        if link_token and not link_token.used and link_token.expires_at > now():
            tg_user, _ = await create_tg_user(link_token.user, message.from_user)
            link_token.used = True
            await save(link_token)
            await message.answer(
                f"Аккаунт привязан! Баланс: {link_token.user.pages_count} звёзд.\n"
                "Напиши любой вопрос — отвечу мгновенно."
            )
            return
        else:
            await message.answer("Ссылка недействительна или устарела. Зайди на aineron.ru и получи новую.")
            return
    
    # args пустой или ref_ реферал
    await message.answer(
        "Привет! Я AI-ассистент aineron.ru.\n\n"
        "Чтобы начать, привяжи аккаунт:\n"
        "1. Зайди на aineron.ru\n"
        "2. Кабинет → Telegram\n"
        "3. Нажми «Подключить» и перейди по ссылке"
    )
```

Зарегистрировать router в `bot.py` через `dp.include_router(start_router)`.

**Верификация:** POST `/api/v1/telegram/link-token/` возвращает 200 с ссылкой; /start без токена — инструкция.

---

### Сессия 1.2 — AuthMiddleware + текстовый чат

**Цель:** пользователь пишет тексто боту → AI отвечает с эффектом streaming.  
**Файлы:** `src/telegram_bot/middlewares.py`, `src/telegram_bot/utils.py`, `src/telegram_bot/handlers/chat.py`

#### Коммит 1.2.1 — AuthMiddleware + antispam

`src/telegram_bot/middlewares.py`:

```python
from aiogram import BaseMiddleware
from asgiref.sync import sync_to_async
import asyncio, random

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        from_user = getattr(event, 'from_user', None) or data.get('event_from_user')
        if not from_user:
            return await handler(event, data)
        
        try:
            get_tg = sync_to_async(TelegramUser.objects.select_related('user').get)
            tg_user = await get_tg(telegram_id=from_user.id)
        except TelegramUser.DoesNotExist:
            if hasattr(event, 'answer'):
                await event.answer("Сначала привяжи аккаунт: /start")
            return
        
        if tg_user.user.shadow_banned:
            await asyncio.sleep(random.uniform(5, 10))
        
        # Antispam: max 30 msg/min (Redis counter)
        # ключ: f"tg_rate:{tg_user.telegram_id}"  TTL=60, INCR > 30 → reject
        
        data['tg_user'] = tg_user
        return await handler(event, data)
```

Зарегистрировать: `dp.message.middleware(AuthMiddleware())` в `bot.py`.

#### Коммит 1.2.2 — chat handler + edit streaming

`src/telegram_bot/handlers/chat.py`:

Flow:
1. Получить текст, `tg_user` из `data['tg_user']`
2. Определить `network = tg_user.default_network` (или дефолтную текстовую)
3. Проверить баланс: `tg_user.user.pages_count < network.cost_per_message` → "Нужно X звёзд. /buy"
4. `sync_to_async` — найти или создать `Chat` через `TelegramChat`
5. Создать `Message(role='user', content=text)` и `Message(role='assistant', status='pending')`
6. `generate_ai_response.delay(assistant_msg.id, web_search=tg_user.web_search)`
7. Отправить placeholder: "Генерирую..."
8. Polling loop (45 итераций × 2 сек = 90 сек):
   - Каждые 4 итерации (8 сек) если есть `msg.plain_text` — `edit_text(partial)` (streaming эффект)
   - При `status='completed'` — финальный edit + кнопки [Повторить] [Новый чат] [Озвучить]
   - При `status='failed'` — "Ошибка генерации. Попробуй ещё раз."
9. `/newchat` → удалить `TelegramChat.chat`, ответить "Начинаю новый чат"

`src/telegram_bot/utils.py`:
- `telegram_format(md_text: str) -> str` — markdown → MarkdownV2 (escape `._*[]()~>#+-=|{}.!`, таблицы → текст, `` ``` `` блоки сохранить)
- `split_message(text: str, limit: int = 4096) -> list[str]` — разбивка по границам абзацев

---

### Сессия 1.3 — /balance /help /models + keyboards

**Цель:** базовые команды и навигация.  
**Файлы:** `src/telegram_bot/handlers/balance.py`, `handlers/models_cmd.py`, `keyboards.py`

#### Коммит 1.3.1 — /balance /help /models + keyboards

`src/telegram_bot/keyboards.py`:
- `main_reply_kb()` — ReplyKeyboardMarkup: «Новый чат», «Баланс», «Модели», «Настройки»
- `after_answer_kb(msg_id)` — InlineKeyboardMarkup: [Повторить] [Новый чат] [Озвучить]
- `models_kb(networks, current_id)` — InlineKeyboard для выбора модели

`handlers/balance.py` — /balance:
```
Ваш баланс: 247 звёзд

Текущая модель: GPT-4o mini (3 зв./сообщение)
Изображения: Flux Schnell (30 зв./запрос)
Хватит примерно на: ~82 текстовых сообщения

[Пополнить на сайте] [Купить через Telegram Stars]
```

`handlers/models_cmd.py` — /models:
- Запрос к БД: `NeuralNetwork.objects.filter(is_active=True, provider='openrouter')` (текстовые)
- InlineKeyboard: по 2 кнопки в ряд
- Callback: обновить `tg_user.default_network` → "Модель изменена: {name}"

Прикрепить `main_reply_kb()` к финальному ответу в `/start` и `/newchat`.

---

## ФАЗА 2 — Монетизация и медиа (3 сессии)

---

### Сессия 2.1 — Telegram Stars оплата

**Цель:** пользователь покупает aineron-звёзды прямо в Telegram без перехода на сайт.  
**Файлы:** `src/telegram_bot/handlers/payment.py`, extend `handlers/balance.py`

#### Коммит 2.1.1 — invoice + successful_payment

Пакеты звёзд:
- 50 XTR → 100 aineron-звёзд
- 100 XTR → 220 aineron-звёзд (+10% бонус)
- 250 XTR → 600 aineron-звёзд (+20% бонус)

```python
# handlers/payment.py

STAR_PACKS = {
    'stars_100':  {'xtr': 50,  'stars': 100},
    'stars_220':  {'xtr': 100, 'stars': 220},
    'stars_600':  {'xtr': 250, 'stars': 600},
}

@router.callback_query(F.data == 'buy_stars')
async def show_packs(query: CallbackQuery):
    # Показать InlineKeyboard с тремя пакетами

@router.callback_query(F.data.startswith('pack:'))
async def send_invoice(query: CallbackQuery):
    pack_key = query.data.split(':')[1]
    pack = STAR_PACKS[pack_key]
    await query.message.answer_invoice(
        title=f"{pack['stars']} звёзд aineron",
        description="Для AI-чата, генерации изображений и видео",
        payload=pack_key,
        currency="XTR",
        prices=[LabeledPrice(label=f"{pack['stars']} звёзд", amount=pack['xtr'])],
    )

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def on_payment(message: Message, tg_user: TelegramUser):
    payload = message.successful_payment.invoice_payload
    pack = STAR_PACKS.get(payload)
    if pack:
        add_stars = sync_to_async(tg_user.user.add_pages)
        await add_stars(pack['stars'])
        new_balance = tg_user.user.pages_count + pack['stars']
        await message.answer(f"Начислено {pack['stars']} звёзд!\nБаланс: {new_balance} звёзд.")
```

---

### Сессия 2.2 — Голосовые STT + TTS

**Цель:** голосовые сообщения → транскрипция → AI; кнопка «Озвучить».  
**Файлы:** `src/telegram_bot/handlers/voice.py`

#### Коммит 2.2.1 — STT Whisper + TTS reply button

STT (минуя внутренний API — прямой вызов laozhang.ai):
```python
@router.message(F.voice | F.video_note)
async def handle_voice(message: Message, tg_user: TelegramUser, bot: Bot):
    file_id = message.voice.file_id if message.voice else message.video_note.file_id
    file = await bot.get_file(file_id)
    ogg_bytes = await bot.download_file(file.file_path)
    
    get_client = sync_to_async(get_laozhang_client)
    client = await get_client()
    transcribe = sync_to_async(client.audio.transcriptions.create)
    result = await transcribe(model='whisper-1', file=('audio.ogg', ogg_bytes.read(), 'audio/ogg'))
    
    text = result.text
    await message.reply(f"[Голосовое]: {text}")
    # Передать в чат-хендлер как обычный текст
    await process_text(message, tg_user, text)
```

TTS через callback-кнопку «Озвучить»:
```python
@router.callback_query(F.data.startswith('tts:'))
async def speak_answer(query: CallbackQuery, tg_user: TelegramUser):
    msg_id = int(query.data.split(':')[1])
    get_msg = sync_to_async(Message.objects.get)
    msg = await get_msg(id=msg_id)
    
    client = await sync_to_async(get_laozhang_client)()
    create_speech = sync_to_async(client.audio.speech.create)
    audio = await create_speech(model='tts-1', voice='alloy', input=msg.plain_text[:4096])
    
    await query.message.answer_voice(audio.content)
    await query.answer()
```

---

### Сессия 2.3 — Генерация изображений

**Цель:** /image промт → изображение через существующий pipeline.  
**Файлы:** `src/telegram_bot/handlers/images.py`

#### Коммит 2.3.1 — /image command

```python
@router.message(Command('image'))
async def generate_image(message: Message, tg_user: TelegramUser):
    prompt = message.text.removeprefix('/image').strip()
    if not prompt:
        await message.answer("Напиши промт: /image закат на море")
        return
    
    # Найти дефолтную image-нейросеть (provider='fal-ai', first active)
    get_net = sync_to_async(NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).first)
    network = tg_user.default_image_network or await get_net()
    
    if tg_user.user.pages_count < network.cost_per_message:
        await message.answer(f"Нужно {network.cost_per_message} звёзд. /balance")
        return
    
    sent = await message.answer("Генерирую изображение... (15-30 сек)")
    
    # Создать Chat + Message через sync_to_async — стандартный путь
    assistant_msg = await create_image_messages(tg_user, network, prompt)
    generate_ai_response.delay(assistant_msg.id)
    
    # Polling до 90 сек
    for i in range(30):
        await asyncio.sleep(3)
        get_state = sync_to_async(Message.objects.get)
        msg = await get_state(id=assistant_msg.id)
        if msg.status == 'completed':
            get_img = sync_to_async(msg.generated_images.first)
            image = await get_img()
            if image:
                await sent.delete()
                await message.answer_photo(
                    f"{settings.SITE_URL}{image.file.url}",
                    caption=f"{network.name} · {network.cost_per_message} зв."
                )
            break
        elif msg.status == 'failed':
            await sent.edit_text("Ошибка генерации. Попробуй позже — звёзды возвращены.")
            break
```

---

## ФАЗА 3 — Интеграция с сайтом + финальные команды (2 сессии)

---

### Сессия 3.1 — Frontend: страница «Telegram» в кабинете

**Цель:** пользователь привязывает бота из web-интерфейса.  
**Файлы:** `frontend/app/account/telegram/page.tsx`, `frontend/lib/api/telegram.ts`, `frontend/components/layout/AccountNav.tsx`

#### Коммит 3.1.1 — account/telegram page

`/account/telegram/`:
- Если НЕ привязан: кнопка «Подключить Telegram» → POST `/api/v1/telegram/link-token/` → показывает ссылку + таймер 15 мин + QR через `qrcode.react`
- Если привязан: имя бота + telegram_username + дата привязки; кнопка «Отвязать» (DELETE `/api/v1/telegram/link-token/`)
- Добавить пункт «Telegram» в `frontend/components/layout/AccountNav.tsx`

---

### Сессия 3.2 — Push-уведомления + /settings /prompts /referral

**Цель:** бот уведомляет о событиях; все команды MVP реализованы.  
**Файлы:** `src/telegram_bot/notify.py`, `src/users/tasks.py`, `src/aitext/tasks.py`, handlers

#### Коммит 3.2.1 — notify util + Celery hooks

`src/telegram_bot/notify.py`:
```python
import asyncio
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

def send_notification(telegram_id: int, text: str) -> None:
    """Синхронная обёртка — вызывается из Celery tasks и Django views."""
    from .bot import bot
    async def _send():
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode=None)
        except (TelegramForbiddenError, TelegramBadRequest):
            pass
    try:
        asyncio.run(_send())
    except RuntimeError:
        # Already in event loop — use thread executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _send()).result()
```

Подключить в:
- `src/users/tasks.py` `notify_upcoming_expiration()` — если `user.telegram` → `send_notification(user.telegram.telegram_id, "Подписка истекает через 3 дня...")`
- `src/users/views.py` `payment_success` — после пополнения → уведомить
- `src/aitext/tasks.py` `generate_ai_response` on_failure — если изображение/видео и есть telegram → уведомить

#### Коммит 3.2.2 — /settings /prompts /referral

`handlers/settings_cmd.py` (FSM):
- /settings → меню с текущими значениями и кнопками переключения
- Голосовые ответы вкл/выкл → `tg_user.voice_responses = not tg_user.voice_responses`
- Веб-поиск вкл/выкл → `tg_user.web_search`
- Системный промт → FSM: запросить текст → сохранить в `tg_user.system_prompt`

`handlers/prompts_cmd.py`:
- /prompts → список категорий из `aitext.Prompt` (встроенные)
- Нажал → промт → отправить в chat handler как обычное сообщение

`handlers/referral.py`:
- /referral → `t.me/{BOT_USERNAME}?start=ref_{user.referral_code}`
- + статистика: приглашено N, оплатили M, заработано K звёзд

---

## Итоговая карта сессий

| # | Сессия | Коммитов | Что даёт |
|---|---|---|---|
| 0.1 | App + модели | 1 | Django app, 3 модели, миграция |
| 0.2 | Bot core + webhook | 1 | aiogram, webhook view, nginx, docker |
| 1.1 | /start + link flow | 1 | Привязка аккаунта, API endpoint |
| 1.2 | AuthMiddleware + чат | 2 | Middleware, текстовый чат с polling |
| 1.3 | /balance /help /models | 1 | Базовые команды, keyboards |
| 2.1 | Telegram Stars | 1 | Нативная оплата |
| 2.2 | Voice STT + TTS | 1 | Голосовые сообщения |
| 2.3 | /image генерация | 1 | Изображения |
| 3.1 | Frontend telegram page | 1 | Web-привязка из кабинета |
| 3.2 | Notify + /settings /prompts | 2 | Push-уведомления, финальные команды |

**Итого: 10 сессий / 13 коммитов**

---

## Переменные окружения

Добавить в `.env` (пока всё выключено):

```bash
# ── Telegram Bot ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_ENABLED=0         # 1 = включить вебхук и функционал бота
TELEGRAM_BOT_TOKEN=            # Токен продуктового бота от @BotFather
TELEGRAM_WEBHOOK_SECRET=       # Случайная строка — защита вебхука (openssl rand -hex 32)
TELEGRAM_BOT_USERNAME=aineron_bot  # Username без @
```

**Различие токенов:**
- `TELEGRAM_BOT_TOKEN` — продуктовый бот aineron.ru (этот план)
- `STUDIO_TMA_BOT_TOKEN` (уже в .env) — бот для Studio-генерируемых TMA-проектов
- Это разные боты с разными токенами

---

## Фаза 2+ (после запуска MVP)

Реализовать по мере спроса:
- Vision (анализ фото + img2img)
- PDF и документы через `file_utils.py`
- Inline-режим (`@aineron_bot`)
- Групповые чаты
- /stats пользователя
- Регистрация прямо в боте (без сайта)
- Интеграция TMA Studio → кнопка `web_app` для запуска сгенерированного приложения

---

*Обновлён: 2026-06-21 | Версия: 2.0 | Заменяет: TELEGRAM_BOT_PLAN.md v1.0 (2026-06-14)*
