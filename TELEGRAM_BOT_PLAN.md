# aineron.ru — Telegram-бот: Полный план

> Цель: лучший AI-бот в российском Telegram — уровень выше RUGPT, Syntx, VLEX.  
> Аудитория: 30–40% пользователей предпочитают Telegram браузеру.

---

## 1. Позиционирование

**Слоган:** «Весь GPT-4o, Claude, Midjourney — прямо в Telegram»

Что отличает нас от конкурентов:
- Единственный бот с полноценным контекстом и историей чатов
- Генерация изображений без отдельного бота
- Голосовой режим: говоришь → AI отвечает голосом
- Streaming-эффект через edit_message (как пишет живой AI)
- Telegram Stars — оплата прямо в мессенджере без перехода на сайт
- Inline-режим: `@aineron_bot напиши код` — ответ в любом чате

---

## 2. Стек

| Компонент       | Технология                                     |
|-----------------|------------------------------------------------|
| Фреймворк       | aiogram 3.x (asyncio)                         |
| Вебхук          | Django endpoint `/telegram/webhook/`           |
| Состояния FSM   | Redis (уже в docker-compose)                   |
| AI-генерация    | Переиспользуем `generate_ai_response` + прямые вызовы laozhang.ai |
| TTS / ASR       | `/api/v1/audio/` эндпоинты (уже есть)         |
| Изображения     | fal.ai через существующий pipeline             |
| БД              | Та же PostgreSQL, новые таблицы в `telegram_bot` app |
| Деплой          | Новый сервис `telegram_bot` в docker-compose   |

---

## 3. Структура приложения

```
src/telegram_bot/
├── __init__.py
├── apps.py
├── models.py          # TelegramUser, TelegramChat, BotSettings
├── bot.py             # Точка входа, регистрация роутеров
├── views.py           # Вебхук-эндпоинт для Django
├── middlewares.py     # Авторизация, логирование, антиспам
├── keyboards.py       # Inline- и Reply-клавиатуры
├── utils.py           # Форматирование, конвертация
├── management/
│   └── commands/
│       └── run_bot.py # Для polling (dev-режим)
└── handlers/
    ├── __init__.py
    ├── start.py       # /start, онбординг, привязка аккаунта
    ├── chat.py        # Основной чат с AI (текст, контекст)
    ├── images.py      # Генерация изображений
    ├── voice.py       # Голосовые сообщения (STT + TTS)
    ├── files.py       # Обработка фото и документов
    ├── models.py      # /models — смена модели
    ├── balance.py     # /balance, пополнение, Telegram Stars
    ├── prompts.py     # /prompts — шаблоны
    ├── settings.py    # /settings — настройки бота
    ├── referral.py    # /referral — реферальная программа
    ├── inline.py      # Inline-режим (@aineron_bot)
    └── groups.py      # Работа в групповых чатах
```

---

## 4. Модели БД

### `TelegramUser`
```python
class TelegramUser(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='telegram')
    telegram_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    telegram_first_name = models.CharField(max_length=100, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    
    # Настройки бота
    default_network = models.ForeignKey(NeuralNetwork, null=True, blank=True, on_delete=models.SET_NULL)
    voice_responses = models.BooleanField(default=False)  # Отвечать голосом
    web_search = models.BooleanField(default=False)
    system_prompt = models.TextField(blank=True)          # Персональный system prompt
    language = models.CharField(max_length=5, default='ru')
    streaming = models.BooleanField(default=True)         # Edit-streaming эффект
    
    # Антиспам
    last_message_at = models.DateTimeField(null=True)
    messages_today = models.PositiveIntegerField(default=0)
    messages_today_date = models.DateField(null=True)
```

### `TelegramChat`
```python
class TelegramChat(models.Model):
    """Текущий активный чат пользователя в боте"""
    tg_user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE)
    chat = models.ForeignKey(Chat, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### `TelegramLinkToken`
```python
class TelegramLinkToken(models.Model):
    """Одноразовый токен для привязки бота к аккаунту"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
```

---

## 5. Авторизация и онбординг

### Сценарий 1 — привязка из кабинета (основной)
```
aineron.ru → Настройки → «Подключить Telegram»
  → Генерируется ссылка: t.me/aineron_bot?start=TOKEN_abc123
  → Пользователь переходит → /start TOKEN_abc123
  → Токен проверяется → аккаунты привязываются
  → «Готово! Твой баланс: 100 звёзд»
```

### Сценарий 2 — регистрация прямо в боте
```
/start (без токена)
  → «Войти через aineron.ru» (кнопка-ссылка)
  ИЛИ
  → «Зарегистрироваться» → запрашиваем email → отправляем код → создаём аккаунт
  (Упрощённая регистрация без пароля — только email + 6-значный код)
```

### Онбординг-визард (показывается один раз)
```
Шаг 1: «Выбери, что будешь делать чаще всего»
  [Писать код] [Переводить] [Генерировать изображения] [Просто общаться]

Шаг 2: «Выбери дефолтную модель»
  [GPT-4o mini — быстро и дёшево]
  [GPT-4o — для сложных задач]
  [Claude Sonnet — для текстов]
  [DeepSeek — для кода]

Шаг 3: «Отлично! Пришли первый запрос»
  Примеры: «Объясни квантовую физику», «Напиши питон-скрипт...»
```

---

## 6. Основной чат (killer-feature)

### Streaming через edit_message
Имитация живого набора текста — главный WOW-эффект:
```
Пользователь → «Расскажи о квантовой физике»
Бот → «⌛ Генерирую...»

  Через 0.5 сек edit: «Квантовая физика —»
  Через 1 сек edit:   «Квантовая физика — это раздел»
  Через 1.5 сек edit: «Квантовая физика — это раздел физики, изучающий...»
  (обновление каждые 500–800мс, не чаще — иначе flood от Telegram)

Финал: полный ответ + кнопки [Regenerate] [Copy] [New chat] [Voice]
```

### Контекст (важно!)
- Сохраняется история последних 20 сообщений (как на сайте)
- `/newchat` — сбросить контекст, начать с нуля
- «Продолжить чат с сайта» — подхватывает тот же чат из web-интерфейса

### Форматирование
- Telegram поддерживает `**bold**`, `_italic_`, `` `code` ``, ` ```code block``` `
- Конвертируем markdown из AI → telegram markdown (parse_mode=MarkdownV2)
- Длинные ответы (> 4096 символов) разбиваются на части автоматически
- Таблицы → преобразуем в читаемый текст (Telegram не поддерживает HTML-таблицы)

### Кнопки под каждым ответом
```
[↻ Regenerate] [📋 Копировать] [🔊 Озвучить]
[🆕 Новый чат] [⚙️ Настройки]
```
*(иконки будут заменены Lucide-совместимыми символами в тексте кнопок)*

---

## 7. Генерация изображений

### Команды
- `/image <промт>` — сгенерировать изображение текущей image-моделью
- `/imagine <промт>` — алиас (как у Midjourney в Discord)

### Флоу
```
/image нарисуй закат над океаном в стиле аниме
  → «Генерирую... обычно занимает 10–30 сек»
  → [progress bar через dots: •••○○]
  → Фото + подпись: «Flux Pro · 50 звёзд · 18 сек»
  
Кнопки:
  [↻ Ещё вариант]  [⬆ Улучшить (upscale)]
  [📝 Изменить промт]  [⚙️ Настройки генерации]
```

### Настройки генерации (FSM-диалог)
```
/image_settings
  ├── Модель: [Flux Pro] [Flux Schnell] [DALL-E 3] [SDXL]
  ├── Разрешение: [1:1] [16:9] [9:16 (Stories)] [4:3]
  ├── Стиль: [Реализм] [Аниме] [Цифровое искусство] [Фото]
  └── Количество: [1] [2] [4]
```

### Image-to-Image
- Пользователь присылает фото + подпись с промтом → img2img через fal.ai
- «Перерисуй в стиле ван Гога», «Убери фон», «Сделай аниме-версию»

---

## 8. Голосовой режим

### STT (речь → текст)
```
Пользователь присылает голосовое или кружок (video_note)
  → Бот скачивает .ogg
  → POST /api/v1/audio/transcriptions (Whisper — уже есть!)
  → Транскрипция → отправляется в AI как обычный текст
  → Показываем: «[🎤 Транскрипция]: {текст}»
```

### TTS (текст → голос)
```
Пользователь нажимает [🔊 Озвучить] под ответом
  → POST /api/v1/audio/speech (TTS — уже есть!)
  → Бот присылает voice message с ответом AI

Или: в /settings включить «Всегда отвечать голосом»
  → Каждый ответ приходит одновременно текстом + голосом
```

### Hands-free режим
- `/voice_mode on` — режим только голоса
- Пользователь говорит → AI отвечает голосом → снова ждёт голоса
- Хорошо для мобильного использования на ходу

---

## 9. Работа с файлами и фотографиями

### Фото (vision)
```
Пользователь присылает фото [без подписи]
  → «Что на фото? Или напиши вопрос об изображении»
  
Пользователь присылает фото + «Что это за блюдо?»
  → Файл → base64 → GPT-4o Vision / Claude Vision
  → Ответ с описанием
```

### Документы и PDF
```
Пользователь присылает PDF / DOCX / TXT
  → Извлекаем текст через file_utils.py (уже есть!)
  → «Файл получен: доклад.pdf (12 стр., 8500 слов)»
  → «Задай вопрос по документу»
  
Пользователь: «Какие выводы в документе?»
  → Контекст = извлечённый текст + вопрос → AI
```

### Ограничения
- Размер файла: до 20 МБ (лимит Telegram Bot API)
- Поддерживаемые форматы: jpg, png, webp, gif, pdf, txt, docx, xlsx, csv, py, js, ts

---

## 10. Команды

### Полный список команд (для BotFather `/setcommands`)
```
start      - Начало работы и привязка аккаунта
help       - Справка по командам
newchat    - Начать новый чат (сбросить контекст)
models     - Список моделей и смена текущей
image      - Генерация изображения: /image закат на море
imagine    - Алиас для /image
balance    - Баланс звёзд и пополнение
buy        - Купить звёзды через Telegram Stars
prompts    - Библиотека готовых промтов
settings   - Настройки бота
voice      - Включить/выключить голосовые ответы
search     - Включить/выключить веб-поиск
referral   - Реферальная программа и заработок
history    - Последние 5 чатов, переключение между ними
stats      - Моя статистика (звёзды по моделям)
feedback   - Оставить отзыв
```

---

## 11. Inline-режим

Пользователь пишет `@aineron_bot <запрос>` в любом чате Telegram:

```
@aineron_bot переведи "I love programming" на русский

Результат в выпадающем списке:
┌─────────────────────────────────────────┐
│ Перевод (GPT-4o)                        │
│ «Я люблю программирование»              │
├─────────────────────────────────────────┤
│ Перевод (DeepSeek)                      │
│ «Мне нравится программировать»          │
└─────────────────────────────────────────┘
```

Применения:
- Быстрый перевод
- Объяснение терминов
- Улучшение текста
- Генерация изображений (`@aineron_bot image закат` → ссылка на картинку)

---

## 12. Групповые чаты

Бот может работать в группах/супергруппах:

```
Активация: добавить бота в группу → /start
Режимы:
  1. Отвечает на @aineron_bot: «@aineron_bot объясни этот код»
  2. Отвечает на Reply на его сообщения
  3. /ai <запрос> — команда внутри группы
  
Администратор группы:
  - Может задать system prompt для всей группы
  - Может ограничить разрешённые модели
  - Может назначить, кто оплачивает (владелец или каждый сам)
```

---

## 13. Баланс и платежи

### /balance
```
⭐ Ваш баланс: 247 звёзд

Дефолтная модель: GPT-4o (5 зв./сообщение)
Хватит примерно на: ~49 сообщений

[Пополнить через сайт] [Купить через Telegram Stars]
```

### Telegram Stars (нативная оплата)
- Telegram с 2024 поддерживает приём Telegram Stars (XTR)
- Курс: 1 Telegram Star ≈ 1–2 звезды aineron
- Оплата без перехода на сайт, без карты — 2 тапа в приложении
- Отличный инструмент для монетизации без комиссий платёжных систем

```python
# aiogram 3.x — отправка инвойса
await bot.send_invoice(
    chat_id=user_id,
    title="100 звёзд aineron",
    description="Для использования AI-нейросетей",
    payload="stars_100",
    currency="XTR",
    prices=[LabeledPrice(label="100 звёзд", amount=50)],  # 50 Telegram Stars
)
```

### Уведомления о балансе
- При остатке < 20 звёзд: «Осталось мало звёзд, пополни баланс»
- При успешном пополнении: «Начислено 100 звёзд! Текущий баланс: 347»

---

## 14. Промпт-библиотека в боте

```
/prompts

Категории:
[💻 Код]  [✍️ Тексты]  [📚 Учёба]
[🌐 Перевод]  [📊 Анализ]  [🎨 Изображения]

→ Пользователь выбирает категорию
→ Список промтов (по 5 штук, пагинация)
→ Нажимает → промт вставляется в чат и отправляется
→ Или «Редактировать» → FSM для изменения перед отправкой

Мои промты:
[Сохранить текущий промт] [Мои сохранённые]
```

---

## 15. Настройки (/settings)

```
⚙️ Настройки aineron-бота

🤖 Модель: GPT-4o mini [Изменить]
🔊 Голосовые ответы: Выкл [Включить]
🌐 Веб-поиск: Выкл [Включить]
📝 Системный промт: Не задан [Задать]
💬 Стриминг (живой набор): Вкл [Выключить]
🌍 Язык ответов: Русский [Изменить]
🎨 Модель изображений: Flux Pro [Изменить]

[Сбросить настройки]  [Отвязать аккаунт]
```

---

## 16. Реферальная программа в боте

```
/referral

👥 Реферальная программа

Твоя ссылка: t.me/aineron_bot?start=ref_abc123
Также работает: aineron.ru/?ref=abc123

📊 Статистика:
  Приглашено: 7 человек
  Из них оплатили: 3
  Заработано: 150 звёзд / 45 ₽

[Поделиться ссылкой]  [Вывести рубли]
```

---

## 17. Антиспам и защита

### Rate limiting (Redis)
- Не более 30 сообщений в минуту на пользователя
- Не более 200 сообщений в день (бесплатный тариф)
- При превышении: «Слишком много запросов, подожди минуту»

### Shadow ban
- Если пользователь в `shadow_banned` — ответы приходят с задержкой 5–10 сек
- Без уведомления о блокировке (стандартное поведение shadow ban)

### Middleware в aiogram
```python
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        telegram_id = event.from_user.id
        tg_user = await TelegramUser.objects.select_related('user').aget(telegram_id=telegram_id)
        if not tg_user:
            await event.answer("Сначала привяжи аккаунт: /start")
            return
        if tg_user.user.shadow_banned:
            await asyncio.sleep(random.uniform(5, 10))
        data['tg_user'] = tg_user
        return await handler(event, data)
```

---

## 18. Уведомления (push от сервера к пользователю)

Бот используется и для отправки уведомлений пользователям:

| Событие | Уведомление |
|---------|-------------|
| Баланс заканчивается | «Осталось 10 звёзд» |
| Пополнение баланса | «Начислено 100 звёзд» |
| Подписка истекает через 3 дня | «Твоя подписка истекает 17 июня» |
| Batch-задача готова | «Пакетная задача #5 выполнена, 48 ответов» |
| Реферальный бонус | «Твой реферал пополнил баланс, тебе +50 звёзд» |
| Новая статья в блоге | Опционально, по подписке |

```python
# Функция отправки уведомления (вызывается из Celery)
async def notify_user(telegram_id: int, text: str, reply_markup=None):
    await bot.send_message(chat_id=telegram_id, text=text, reply_markup=reply_markup)
```

---

## 19. Аналитика и метрики бота

### Для нас (внутренняя аналитика)
- DAU/MAU бота
- Топ-команды по использованию
- Конверсия `/start` → привязка аккаунта
- Конверсия бесплатные пользователи → платящие через бота
- Среднее число сообщений на пользователя в день

### Для пользователя (/stats)
```
📊 Твоя статистика за 30 дней

Сообщений отправлено: 342
Звёзд потрачено: 1247
Изображений сгенерировано: 23
Голосовых сообщений: 15

Топ моделей:
  GPT-4o mini — 67%
  Flux Pro — 18%
  Claude Sonnet — 15%
```

---

## 20. Деплой

### docker-compose.yml (дополнение)
```yaml
telegram_bot:
  build: .
  command: python manage.py run_bot
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - TELEGRAM_WEBHOOK_URL=${SITE_URL}/telegram/webhook/
  depends_on:
    - redis
    - db
  restart: unless-stopped
  volumes:
    - media_volume:/app/src/media
```

### Два режима работы
- **Production**: вебхук (Django endpoint принимает updates)
- **Development**: polling (`python manage.py run_bot --polling`)

### Переменные окружения (.env)
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=   # X-Telegram-Bot-Api-Secret-Token для безопасности
TELEGRAM_BOT_USERNAME=aineron_bot
```

---

## 21. Поэтапная реализация (план коммитов)

### Этап 1 — MVP (1 неделя): базовый чат
- [ ] Django-app `telegram_bot`, модели, вебхук
- [ ] `/start` — привязка через токен
- [ ] Текстовый чат с дефолтной моделью (без streaming)
- [ ] `/balance`, `/newchat`, `/help`
- [ ] docker-compose сервис
- [ ] Уведомления о балансе

### Этап 2 — Core UX (3–5 дней): стриминг + модели
- [ ] Streaming через edit_message
- [ ] `/models` — смена модели + inline-кнопки
- [ ] Голосовые сообщения (STT через Whisper)
- [ ] Фотографии → vision
- [ ] Кнопки Regenerate / Copy под ответом

### Этап 3 — Изображения (2–3 дня)
- [ ] `/image` — генерация через fal.ai
- [ ] Настройки (модель, размер, стиль) через FSM
- [ ] image-to-image (фото + промт)
- [ ] `/imagine` — алиас

### Этап 4 — Платежи и монетизация (2–3 дня)
- [ ] Telegram Stars — инвойсы, обработка successful_payment
- [ ] TTS — голосовые ответы
- [ ] `/prompts` — библиотека промтов
- [ ] Реферальная программа в боте

### Этап 5 — Продвинутые фичи (1 неделя)
- [ ] Inline-режим (@aineron_bot)
- [ ] Работа в групповых чатах
- [ ] PDF и документы
- [ ] Voice mode (hands-free)
- [ ] `/settings` полноценные настройки
- [ ] Регистрация прямо в боте (без сайта)

### Этап 6 — Полировка
- [ ] Онбординг-визард
- [ ] /stats для пользователя
- [ ] Уведомления (истечение подписки, batch, рефералы)
- [ ] Антиспам middleware
- [ ] Аналитика (счётчики в Redis)

---

## 22. Конкурентное сравнение (целевое состояние)

| Фича                    | RUGPT | Syntx | VLEX | aineron (цель) |
|-------------------------|-------|-------|------|----------------|
| Текстовый чат           | ✓     | ✓     | ✓    | ✓              |
| Выбор модели            | ✓     | ✓     | ✗    | ✓              |
| Streaming (edit_msg)    | ✗     | ✓     | ✗    | ✓              |
| Генерация изображений   | ✗     | ✓     | ✓    | ✓              |
| image-to-image          | ✗     | ✗     | ✗    | ✓              |
| Голосовые сообщения STT | ✓     | ✓     | ✗    | ✓              |
| TTS (ответ голосом)     | ✗     | ✗     | ✗    | ✓              |
| Анализ фото (vision)    | ✗     | ✓     | ✗    | ✓              |
| PDF и документы         | ✗     | ✗     | ✗    | ✓              |
| Контекст чата           | ✓     | ✓     | ✓    | ✓              |
| Промпт-библиотека       | ✗     | ✗     | ✗    | ✓              |
| Inline-режим            | ✗     | ✗     | ✗    | ✓              |
| Групповые чаты          | ✗     | ✓     | ✗    | ✓              |
| Telegram Stars оплата   | ✗     | ✗     | ✗    | ✓              |
| Веб-поиск               | ✗     | ✗     | ✗    | ✓              |
| Реферальная программа   | ✓     | ✗     | ✓    | ✓              |
| Уведомления             | ✓     | ✓     | ✓    | ✓              |
| Онбординг               | ✗     | ✓     | ✗    | ✓              |
| Статистика пользователя | ✗     | ✗     | ✗    | ✓              |
| Привязка к web-кабинету | ✗     | ✓     | ✗    | ✓              |
| Hands-free voice mode   | ✗     | ✗     | ✗    | ✓              |

**Итог: мы закрываем каждую фичу конкурентов + добавляем 8 уникальных.**

---

*Файл: `TELEGRAM_BOT_PLAN.md` | Обновлён: 2026-06-14*
