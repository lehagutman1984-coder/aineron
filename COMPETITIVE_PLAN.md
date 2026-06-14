# aineron.ru — Конкурентный анализ и план развития
> Цель: топ-3 AI-сервисов России. Дата составления: 2026-06-14

---

## 1. Анализ конкурента — RouterAI (routerai.ru)

### Позиционирование
«Единый API-шлюз к 200+ нейросетям» — developer-first платформа. Целевая аудитория: разработчики, интеграторы, B2B-команды.

### Ценообразование
- Pay-as-you-go: 61–2769 ₽ за 1М токенов (в зависимости от модели)
- Нет фиксированных подписок, нет минимального платежа
- Корпоративные договоры, счета-фактуры для юридических лиц

### Ключевые фичи RouterAI
| Фича | Описание |
|---|---|
| 200+ моделей | OpenAI, Anthropic, Google, DeepSeek, Mistral и др. |
| OpenAI-совместимый API | Один ключ, один эндпоинт, смена модели через model ID |
| Failover | Автоматическое переключение при отказе провайдера |
| Командный баланс | Аналитика трат по сотрудникам в реальном времени |
| Серверы РФ | Хостинг на российских ДЦ для ФЗ-152-compliance |
| Веб-чат | Инструмент тестирования промтов, не основной продукт |
| Документация | Подробные гайды по интеграции |

### Слабые места RouterAI (наши возможности)
1. **Нет мобильного приложения** — только веб
2. **Нет Telegram-бота**
3. **Веб-чат — минимальный** — только для тестирования, не для ежедневного использования
4. **Нет генерации изображений в UI**
5. **Нет end-user UX** — продукт только для разработчиков, обычные пользователи теряются
6. **Нет промпт-библиотеки**, шаблонов, примеров
7. **Нет голосового режима**
8. **Нет Projects / постоянной памяти**
9. **Нет сравнения моделей side-by-side**
10. **Нет SEO-блога** с контентом

---

## 2. Конкурентное поле России (топ-10)

| # | Сервис | URL | Тариф от | Ключевое отличие |
|---|---|---|---|---|
| 1 | STUDY24 | study24.ai | 199₽/нед | Учёба, широкая аудитория |
| 2 | Syntx AI | syntx.ai | 890₽ | 90+ инструментов, Telegram-бот |
| 3 | VLEX | vlex-ai.io | 499₽/мес | Шаблоны, Telegram-бот |
| 4 | MashaGPT | mashagpt.ru | 990₽/мес | iOS/Android, Canvas, Projects |
| 5 | RUGPT | rugpt.io | 200₽ | 13к+ отзывов, Telegram |
| 6 | **BOTHUB** | bothub.ru | 250₽/1М | Несгораемые токены, приложения |
| 7 | GPT Tunnel | gptunnel.ru | pay-as-u-go | MCP, корп. доступ |
| 8 | ChadGPT | chadgpt.ru | 290₽/мес | Голос, веб-поиск, Минцифры |
| 9 | **RouterAI** | routerai.ru | ~61₽/1М | API-first, команды, failover |
| 10 | EpicAI | epicai.ru | 899₽ | Бонусные токены |

### Тренды рынка
- **Pay-as-you-go vs. подписки** — разделение аудиторий: BOTHUB/RouterAI развивают pay-as-you-go, MashaGPT/ChadGPT — подписки
- **Несгораемые токены** (BOTHUB) — сильный маркетинговый аргумент, наши "звёзды" несгораемы — нужно доносить
- **Telegram** — присутствует у большинства ТОП-конкурентов
- **Мобильные приложения** — у 60% конкурентов есть iOS/Android

---

## 3. Эталоны мирового уровня (Perplexity / ChatGPT / Poe)

### Perplexity — что делает их лидером
- **Минимализм** — один input в центре экрана, никакого шума
- **Источники inline** — каждый факт ссылается на источник, доверие к ответам
- **Model Council** — один запрос → 3 модели одновременно → сравнение
- **Web search по умолчанию** — не нужно переключаться, AI всегда знает актуальное
- **Spaces** — коллекции чатов с тематикой
- **Perplexity Computer** — AI-агент выполняет задачи автономно

### ChatGPT — что делает их №1
- **Projects** — папки чатов с общим system prompt и файлами
- **Persistent Memory** — AI помнит о тебе между сессиями
- **Canvas** — совместное редактирование документа прямо в чате
- **File interpreter** — загрузка PDF/CSV/Excel, анализ в чате
- **Voice Mode** — полноценный голосовой разговор с AI
- **GPTs Store** — маркетплейс кастомных ботов
- **Боковая панель с историей** — все чаты всегда видны, поиск по ним

### Poe — что делает их выбором молодой аудитории
- **Один subscription** — все модели за одну подписку
- **Bot marketplace** — создавай и продавай кастомных ботов
- **Multi-bot comparison** — сравнение моделей в одном диалоге
- **Instant switching** — переключение модели в середине разговора
- **Cross-platform** — iOS, Android, macOS, Windows, Web

---

## 4. Где aineron.ru слабее — честное сравнение

### Критические пробелы (блокируют рост)
| Пробел | Кто имеет | Влияние |
|---|---|---|
| Нет sidebar с историей чатов | ChatGPT, Poe, все | Пользователи теряют диалоги, не возвращаются |
| Markdown рендеринг — хак через detectHTML | Все | Плохое отображение кода и форматирования |
| Нет загрузки файлов в chat UI | ChatGPT, большинство | Модели не используются на полную |
| Нет кнопки "Регенерировать" | ChatGPT, Poe, Claude | Раздражает при плохом ответе |
| Нет Copy кнопки на каждом сообщении | Все | Базовая UX-функция |
| Нет веб-поиска | Perplexity, ChadGPT | Пользователи идут к Perplexity |
| Нет голосового ввода | ChatGPT, ChadGPT | Большая аудитория мобильных |

### Важные пробелы (ограничивают масштаб)
| Пробел | Кто имеет | Влияние |
|---|---|---|
| Нет Telegram-бота | RUGPT, Syntx, VLEX | Потеря 30–40% рос. аудитории |
| Нет мобильного приложения | MashaGPT, BOTHUB | Мобильный трафик растёт |
| Нет сравнения моделей | Perplexity Model Council | Нет инструмента для выбора |
| Нет промпт-библиотеки | Poe, многие | Низкий engagement новых пользователей |
| Нет Projects | ChatGPT, MashaGPT | B2B-пользователи уходят |
| Нет Persistent Memory | ChatGPT | Retention страдает |
| Нет Dark Mode | Все | 40% пользователей ожидают |
| Нет аналитики для юзера | RouterAI (teams) | Непонятно, на что тратятся звёзды |

### Конкурентные преимущества aineron.ru (сохранять и усиливать)
1. OpenAI-совместимый API (Фаза 1) — паритет с RouterAI
2. Команды и организации (Фаза 4) — паритет с RouterAI  
3. Embeddings, Audio, Batch API (Фаза 6) — превосходим большинство конкурентов
4. Webhooks + Audit Log — enterprise-ready, RouterAI этого нет
5. SEO-блог (Фаза 5) — контентный маховик
6. Status page — прозрачность, доверие

---

## 5. Детальный план по коммитам

### SPRINT 1 — Быстрые победы (1–2 дня)

---

#### 1.1 — Sidebar с историей чатов (КРИТИЧНО)
**Файлы:**
- `frontend/app/chat/layout.tsx` — добавить sidebar компонент
- `frontend/components/chat/ChatSidebar.tsx` — новый компонент
- `frontend/lib/api/client.ts` — добавить `deleteChat(id)`, `renameChat(id, title)`
- `frontend/lib/api/types.ts` — добавить тип `ChatListItem.title`
- `src/api/views/chats.py` — PATCH /api/v1/chats/{id}/ (rename), DELETE

**Что делать:**
- Левый sidebar 240px, collapsible на mobile
- Список чатов сгруппированный по дате (Сегодня / Вчера / 7 дней / Ранее)
- Hover: кнопки переименовать / удалить
- Активный чат подсвечен
- Кнопка "Новый чат" вверху
- Поиск по истории (Ctrl+K)

**Ожидаемый результат:** Retention ↑ 20–30%, пользователи возвращаются к чатам

---

#### 1.2 — Markdown рендеринг через react-markdown
**Зависимости:** `npm install react-markdown rehype-highlight rehype-raw remark-gfm`

**Файлы:**
- `frontend/app/chat/[chatId]/page.tsx` — заменить `AssistantContent` и `detectHTML` hack
- `frontend/components/chat/MarkdownContent.tsx` — новый компонент с react-markdown
- `frontend/app/globals.css` — стили для prose: таблицы, code blocks, цитаты

**Что делать:**
- Полноценный GFM (GitHub Flavored Markdown): таблицы, списки, чекбоксы
- Syntax highlighting кода через rehype-highlight (тема github-dark/github-light)
- Копирование блока кода одной кнопкой (уже есть логика, использовать её)
- `pre` с именем языка в заголовке блока

**Ожидаемый результат:** Отображение кода/таблиц как у ChatGPT, повышение воспринимаемого качества

---

#### 1.3 — Copy / Regenerate / Like кнопки на сообщениях
**Файлы:**
- `frontend/app/chat/[chatId]/page.tsx` → `MessageRow` компонент
- `frontend/lib/api/client.ts` → добавить `regenerateMessage(chatId, messageId)`
- `src/api/views/chats.py` → POST /api/v1/chats/{id}/regenerate/

**Что делать:**
- На каждом сообщении ассистента: кнопки Copy / Regenerate (появляются при hover)
- Copy: копирует plain text (без HTML)
- Regenerate: отправляет повторный запрос с тем же промтом пользователя
- Feedback: Like / Dislike (опционально, для будущей аналитики)

---

#### 1.4 — Dark Mode
**Файлы:**
- `frontend/app/globals.css` — CSS переменные для dark/light, `@media (prefers-color-scheme: dark)`
- `frontend/components/layout/Navbar.tsx` — добавить кнопку переключения темы
- `frontend/lib/stores/ui.ts` — добавить `theme: 'light' | 'dark' | 'system'`

**Что делать:**
- CSS-only dark mode через data-theme="dark" на `<html>`
- Системная тема по умолчанию
- Плавный переход `transition: background 0.2s, color 0.2s`
- Persist в localStorage

---

#### 1.5 — Улучшенный пустой экран чата (Starter prompts)
**Файлы:**
- `frontend/app/chat/[chatId]/page.tsx` → empty state

**Что делать:**
- Вместо "Введите вопрос или задачу ниже" — 4–6 карточек с примерами промтов
- Примеры специфичны для модели (из `chat.network.description` или хардкод по категории)
- Клик на карточку → заполняет textarea и отправляет
- Как у ChatGPT / Claude.ai

---

### SPRINT 2 — Критические UX-фичи (2–14 дней)

---

#### 2.1 — Загрузка файлов в chat UI
**Файлы:**
- `frontend/app/chat/[chatId]/page.tsx` — добавить кнопку attachment в форму
- `frontend/components/chat/FileUpload.tsx` — drag & drop зона
- `frontend/lib/api/client.ts` — `uploadFile(chatId, file)` → POST /api/v1/chats/{id}/upload/
- `src/api/views/chats.py` — эндпоинт загрузки файла, сохранение FileAttachment
- `src/aitext/file_utils.py` — уже есть, переиспользовать

**Что делать:**
- Кнопка Paperclip в chat input
- Drag & drop на область чата
- Превью: изображение thumbnail, PDF — иконка + имя файла
- После загрузки файл прикреплён к следующему сообщению
- Поддержка: jpg/png/gif/webp + pdf/txt/docx
- Показывать прогресс загрузки

---

#### 2.2 — Сравнение моделей (Model Arena)
**Файлы:**
- `frontend/app/compare/page.tsx` — новая страница
- `frontend/components/compare/ComparePanel.tsx`
- `frontend/lib/api/client.ts` — нужен новый эндпоинт или переиспользовать existing
- `src/api/views/` — `/api/v1/compare/` — отправить один промт к N моделям параллельно

**Что делать:**
- URL: `/compare/`
- Выбор 2–3 моделей через dropdown
- Один textarea для промта
- Ответы отображаются колонками side-by-side
- SSE стриминг для каждой колонки независимо
- Стоимость списывается как N * cost_per_message

---

#### 2.3 — Промпт-библиотека
**Файлы:**
- `src/aitext/models.py` — добавить модель `PromptTemplate(title, content, category, is_public, network, user)`
- `src/api/views/prompts.py` — CRUD + публичный список
- `frontend/app/prompts/page.tsx` — каталог промтов
- `frontend/components/chat/PromptPicker.tsx` — выпадающий список в пустом чате

**Что делать:**
- Встроенная библиотека промтов (50–100 шт.) по категориям: Код, Перевод, Анализ, Email, Учёба
- Пользователь может сохранить свои промты
- В пустом чате: кнопка "Шаблоны" открывает modal/dropdown
- Каждый промт: название + иконка + текст

---

#### 2.4 — Веб-поиск в чате
**Файлы:**
- `frontend/app/chat/[chatId]/page.tsx` — Toggle "Поиск в интернете" рядом с input
- `frontend/lib/api/client.ts` — передавать `{ message, web_search: true }` в sendMessage
- `src/api/views/chats.py` — параметр `web_search` в send_message view
- `src/aitext/tasks.py` — если web_search=True: использовать модель с web_search capability (perplexity/sonar или добавить DuckDuckGo API как pre-step)

**Что делать:**
- Toggle-кнопка "Интернет" в панели ввода (Globe иконка)
- Persist в localStorage для пользователя
- Если enabled: промт оборачивается с инструкцией поиска, или используется perplexity-sonar модель
- В ответе — источники выделены

---

#### 2.5 — Аналитика для пользователя
**Файлы:**
- `frontend/app/account/analytics/page.tsx` — новая страница
- `src/api/views/billing.py` — эндпоинт `/api/v1/billing/usage/` — статистика по дням
- `src/users/models.py` — `UserSpending` уже есть, доиспользовать

**Что делать:**
- Bar chart по дням (recharts или visx)
- Топ моделей по трате звёзд
- Сравнение с прошлой неделей
- Среднее в день

---

#### 2.6 — Страница "Начало работы" / Onboarding
**Файлы:**
- `frontend/app/welcome/page.tsx` — редирект после регистрации
- `frontend/components/onboarding/OnboardingWizard.tsx`

**Что делать:**
- 3-шаговый wizard: (1) выбор интереса → (2) первый чат → (3) куда идти дальше
- Показывается один раз, persist в localStorage / backend флаг
- Цель: снизить churn у новых пользователей

---

#### 2.7 — Лендинг 2.0
**Файлы:**
- `frontend/app/page.tsx` — полная переработка
- `frontend/components/landing/` — новая папка компонентов

**Что делать:**
- **Hero** с анимацией набора текста (несколько сценариев использования)
- **Social proof**: "X пользователей уже работают", "X сообщений отправлено"  
- **Comparison таблица**: aineron vs RouterAI vs ChatGPT — честное сравнение
- **Use cases** блок: Разработчик / Дизайнер / Маркетолог / Студент
- **Pricing preview** прямо на главной
- **FAQ** секция (Schema.org FAQPage уже есть)
- Анимации: CSS transitions, никаких тяжёлых библиотек

---

#### 2.8 — Projects (папки чатов)
**Файлы:**
- `src/aitext/models.py` — `Project(user, name, system_prompt, color, icon)`
- `src/api/views/` — CRUD для проектов
- `frontend/app/projects/page.tsx`
- `frontend/app/projects/[id]/page.tsx` — список чатов проекта
- `frontend/components/chat/ChatSidebar.tsx` — группировка по проектам

**Что делать:**
- Пользователь создаёт проект с именем, system prompt и цветом
- Чаты в проекте наследуют system prompt
- Sidebar: Projects section → Chats section
- Иконка + цвет для визуального различия

---

### SPRINT 3 — Масштаб (1–3 месяца)

---

#### 3.1 — Telegram-бот
**Файлы:**
- `src/telegram_bot/` — новое Django-приложение
- `src/telegram_bot/bot.py` — aiogram 3.x
- `src/telegram_bot/views.py` — вебхук endpoint
- `docker-compose.yml` — добавить сервис telegram_bot

**Что делать:**
- `/start` — авторизация через токен (ссылка из кабинета)
- Отправка сообщения → ответ AI (текущая дефолтная модель)
- `/models` — список и смена модели
- `/balance` — баланс звёзд
- Inline кнопки для быстрых действий
- Поддержка голосовых сообщений (через Whisper)

---

#### 3.2 — PWA / Mobile
**Файлы:**
- `frontend/public/manifest.json` — Web App Manifest
- `frontend/public/sw.js` — Service Worker (next-pwa)
- `frontend/next.config.ts` — withPWA конфиг

**Что делать:**
- Installable PWA (Add to Home Screen)
- Офлайн: показывать кешированную историю чатов
- Push-уведомления о завершении batch-задач
- Иконки всех размеров (192x192, 512x512)
- Позже: Capacitor wrapper для App Store / Google Play

---

#### 3.3 — Голосовой режим в чате
**Файлы:**
- `frontend/components/chat/VoiceInput.tsx` — запись голоса через Web Speech API
- `frontend/components/chat/VoiceOutput.tsx` — воспроизведение TTS ответа
- `frontend/app/chat/[chatId]/page.tsx` — кнопка микрофона в input

**Что делать:**
- Кнопка микрофона (Mic иконка) в форме отправки
- Запись → транскрипция через `/api/v1/audio/transcriptions` (уже есть!)
- TTS ответа через `/api/v1/audio/speech` (уже есть!)
- Режим "hands-free": автоматическая отправка после паузы

---

#### 3.4 — Persistent Memory
**Файлы:**
- `src/users/models.py` — `UserMemory(user, content, created_at)`
- `src/api/views/` — CRUD /api/v1/memory/
- `frontend/app/account/memory/page.tsx` — страница управления памятью
- `src/aitext/tasks.py` — добавить memory в system prompt каждого запроса

**Что делать:**
- Пользователь задаёт "факты о себе" (имя, профессия, предпочтения, язык)
- AI всегда помнит эти факты
- Можно отключить глобально или для конкретного чата
- "Memory" страница с CRUD

---

#### 3.5 — SEO-контент машина
**Файлы:**
- `src/blog/management/commands/generate_seo_content.py`
- `src/aitext/tasks.py` — Celery задача генерации статей
- `frontend/app/blog/` — уже существует, улучшить

**Что делать:**
- Management command: берёт список нейросетей → генерирует статью через DeepSeek
- Шаблоны статей: "Как использовать {model}", "{model} vs {model2}", "Лучшие промты для {model}"
- Цель: 200+ SEO-статей, каждая под конкретный запрос
- Internal linking между статьями

---

#### 3.6 — API Playground в UI
**Файлы:**
- `frontend/app/api-docs/page.tsx` — улучшить существующую страницу
- `frontend/components/api/Playground.tsx` — интерактивный тестер API

**Что делать:**
- Интерактивный редактор запросов прямо на странице документации
- Выбор модели, параметры, body → Execute → response JSON
- Copy curl / Copy Python / Copy JS
- Отображение стоимости запроса

---

## 6. Позиционирование против RouterAI

### Наша стратегия дифференциации

| Аспект | RouterAI | aineron.ru |
|---|---|---|
| Целевая аудитория | Разработчики | Разработчики + конечные пользователи |
| UX | Минимальный web-чат | Full-featured ChatGPT-level UI |
| Мобильные | Нет | PWA → App Store |
| Голос | Нет | Есть (TTS + STT) |
| Изображения в UI | Нет | Есть |
| Проекты | Нет | Есть (Sprint 2) |
| Telegram | Нет | Есть (Sprint 3) |
| Память | Нет | Есть (Sprint 3) |
| Сравнение моделей | Нет | Есть (Sprint 2) |
| B2B API | Есть | Есть (лучше: webhooks, batch, audit) |
| Цены | Pay-as-you-go | Звёзды (несгораемые) + подписки |

### Ключевой месседж против RouterAI
> «RouterAI — шлюз для разработчиков. aineron.ru — полноценный AI-продукт: такой же API для разработчиков, но плюс полноценный UI как ChatGPT, голос, изображения, Telegram-бот и Projects.»

---

## 7. Метрики успеха

| Метрика | Сейчас | Цель 3 мес | Цель 1 год |
|---|---|---|---|
| Позиция в топ-10 рос. AI | ? | Топ-5 | Топ-3 |
| Retention (D7) | ? | 35% | 50% |
| Конверсия регистрация → платёж | ? | 8% | 15% |
| Органический трафик | ? | 10к/мес | 100к/мес |
| B2B API клиенты | ? | 20 | 200 |

---

## 8. Дизайн-принципы (обязательно соблюдать)

- Ноль эмодзи в UI — только Lucide React SVG-иконки
- Цветовая палитра: `#0d0d0d` (текст), `#0a7cff` (accent), `rgba(13,13,13,0.XX)` (мuted)
- Анимации: CSS transitions 150ms ease, `requestAnimationFrame` для streaming
- Типографика: Inter (уже подключён)
- Стиль: Linear / Vercel Dashboard / Stripe — строгий, профессиональный, без декора
- Каждое действие: hover state, focus ring, loading state, error state
- Mobile-first: все компоненты responsive

---

*Этот документ должен обновляться по мере выполнения пунктов.*
