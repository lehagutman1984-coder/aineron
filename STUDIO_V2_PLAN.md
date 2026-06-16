# STUDIO V2 PLAN — путь к топ-1 вайбкодингу в России

> Документ архитектуры и роста для **aineron.ru Studio** — full-stack vibe-coding для русскоязычного рынка.
>
> Статус: planning. Автор: Studio Architecture. Дата ревизии: 2026-06-16.
>
> **Важно (дизайн-система):** во всех UI-элементах этого плана НЕ используются эмодзи. Статусы и индикаторы реализуются иконками Lucide React (`Check`, `X`, `Loader2`, `CircleCheck`, `CircleAlert`) или текстом. Любые `✓`/`✗` в исходном брифе заменяются на `<Check size={16} />` / `<X size={16} />`. Это обязательное требование `CLAUDE.md`.

---

## 0. TL;DR — что мы строим за 4 спринта

| Спринт | Тема | Главный результат | Длительность |
|--------|------|-------------------|--------------|
| Tech Debt | Фундамент | Шифрование токенов, `GITHUB_TOKEN` в settings, hardening Gitea-сигналов | 0.5 недели |
| Sprint 1 | Integrations & Trust | Персональные GitHub PAT / Vercel токены, страница `/account/integrations/` | 1 неделя |
| Sprint 2 | Non-Coder UX Revolution | Онбординг-визард Studio, magic-describe, 20+ шаблонов, дружелюбный прогресс, публикация на `*.aineron.ru` | 1 неделя |
| Sprint 3 | Collaboration & Virality | Публичные share-ссылки, галерея, форк проектов, базовый realtime, embed-виджет | 1 неделя |
| Sprint 4 | Power User | Кастомные домены, env-переменные, БД-провижининг, генерация API, CI/CD | 1 неделя |

**Сквозная цель:** русскоязычный предприниматель/студент/основатель MVP должен собрать рабочее приложение за 10 минут, без VPN, без иностранной карты, оплачивая звёздами, и опубликовать его на `myapp.aineron.ru` в один клик.

---

## 1. Конкурентный анализ — где мы честно стоим

### 1.1 Матрица возможностей

| Возможность | bolt.new | lovable.dev | replit | v0.dev | **aineron Studio (сейчас)** | **после V2** |
|-------------|:--------:|:-----------:|:------:|:------:|:---------------------------:|:------------:|
| Чат-driven итерации | да | да | частично | да | **да** | да |
| Мгновенный preview | WebContainer | да | да | да | Docker sandbox + DB-preview | sandbox + mobile toggle |
| Редактирование файлов в браузере | да | ограничено | да | нет | **да** (CodeViewer/Diff) | да |
| One-click deploy | Netlify/Vercel | custom domain | Replit deploy | copy-paste | Vercel (global token) | **per-user Vercel + `*.aineron.ru`** |
| GitHub sync | да | да | да | нет | частично (нет токена) | **per-user PAT** |
| Внутренний git/версии | нет | нет | да | нет | **да (Gitea + rollback)** | да |
| Форк/шаблоны | share-links | да | да | да | шаблоны есть, форк есть (backend) | **галерея + UI форка** |
| Multiplayer/realtime | нет | нет | **да** | нет | модель есть, не подключена | базовый presence |
| БД-провижининг | нет | Supabase | **да** | нет | нет | **Postgres per project** |
| Onboarding для не-кодеров | средний | **лучший** | средний | средний | общий `/welcome/` | **визард Studio** |
| Русский язык | нет | нет | нет | нет | **да (нативно)** | да |
| Оплата рублями без VPN | нет | нет | нет | нет | **да (Robokassa, звёзды)** | да |
| Микробиллинг pay-per-use | подписка | подписка | подписка | подписка | **звёзды per-step** | да |

### 1.2 Честные разрывы (gap-анализ)

**Где мы отстаём:**
- **Deploy/integrations доверие.** Vercel — глобальный токен админа, GitHub-токена нет вовсе (`GITHUB_TOKEN` читается в `tasks.py`, но не определён в `settings.py` → всегда пустой). Пользователь не может задеплоить «к себе». Это блокер №1.
- **Onboarding не-кодеров.** Lovable выигрывает за счёт «опиши приложение одним полем + красивый прогресс». У нас технический лог (`coder_iteration step 3/7`), который пугает не-кодера.
- **Скорость preview.** bolt.new (WebContainer) показывает результат мгновенно в браузере; у нас Docker sandbox с `pnpm install` — медленнее на холодном старте. Митигируем: статический HTML-preview уже из БД (сделано), плюс прогрев образа.
- **Виральность.** Нет публичных share-ссылок и галереи — нет виральной петли, которая кормит bolt/lovable.

**Где мы уже на уровне или впереди (не переделывать):**
- Внутренний git с rollback на любую версию (Gitea) — у bolt/lovable/v0 этого нет.
- Полный agent-pipeline (Interviewer→Analyst→Planner→Coder→Reviewer→Tester→Fixer) с reserve/charge/refund звёзд по шагам.
- Клонирование с URL (HTTP + Playwright), screenshot→AI-описание.
- 55 готовых API-эндпоинтов, SSE-стриминг, context-chat, console-autofix, code-explain.

**Вывод:** мы НЕ строим pipeline заново. Мы закрываем 4 разрыва: **доверие к деплою, UX не-кодера, виральность, power-фичи** — поверх уже сильного движка.

---

## 2. Стратегия «Топ-1 в России»

### 2.1 Почему русский пользователь выберет нас вместо «VPN + bolt.new»

Тезис: для россиянина bolt.new стоит **3 барьера**: VPN, иностранная карта, английский интерфейс. Каждый барьер — это отток. Мы убираем все три и добавляем то, что иностранцы не дадут.

| Барьер у конкурента | Наше решение |
|---------------------|--------------|
| Нужен VPN для доступа к Claude/GPT | Доступ к моделям через `api.laozhang.ai` без VPN |
| Иностранная карта (Stripe) | Robokassa, оплата рублями, звёзды |
| Английский UI и поддержка | Полностью русский интерфейс, русская поддержка, русские шаблоны |
| Подписка $20/мес лок-ин | Микробиллинг звёздами — платишь за то, что сгенерировал |
| Деплой на зарубежный хостинг | Публикация на `*.aineron.ru` + опционально свой Vercel |

### 2.2 Русско-специфичные фичи-«рвы» (moat)

1. **Шаблоны под русский рынок** (Sprint 2): лендинг для Telegram-канала, карточка товара для Avito/Wildberries, лендинг под маркетплейс, запись к мастеру (барбершоп/салон), меню кафе с QR.
2. **`*.aineron.ru` публикация** (Sprint 2): мгновенный публичный URL без домена и хостинга — для россиянина это «магия», т.к. купить домен/хостинг = ещё барьер.
3. **Русский magic-describe** (Sprint 2): «Опиши приложение по-русски» → AI понимает русские формулировки бизнеса («хочу сайт для записи на маникюр»).
4. **Интеграция с российскими платежами в сгенерированном приложении** (Sprint 4 stretch): кнопка «добавить приём оплат» → вставка Robokassa/ЮKassa-сниппета в проект пользователя.
5. **Контент-машина SEO на русском** (раздел 7): захват запросов «создать сайт с помощью ИИ», «вайбкодинг».

### 2.3 Позиционирование одной строкой

> **«Создай сайт или приложение, просто описав его словами. На русском, без VPN, оплата звёздами. Опубликуй за 10 минут на `myapp.aineron.ru`.»**

---

## TECH DEBT — закрыть до Sprint 1 (P0)

Эти 4 пункта блокируют или подрывают всё остальное. Делаем первыми, ~0.5 недели.

### TD-1. Шифрование токенов в покое (P0, 4ч)

**Контекст:** `cryptography` уже в `requirements.txt` (Fernet доступен из коробки — НОВЫЙ пакет не нужен). `gitea_password` сейчас в плейнтексте (`users/models.py:471`).

- [ ] Добавить env-переменную `STUDIO_TOKEN_ENCRYPTION_KEY` (Fernet key, `Fernet.generate_key()`), в `settings.py` и `.env.example`.
- [ ] Создать `src/studio/crypto.py` с хелперами:

```python
# src/studio/crypto.py
from cryptography.fernet import Fernet
from django.conf import settings

def _fernet() -> Fernet:
    return Fernet(settings.STUDIO_TOKEN_ENCRYPTION_KEY.encode())

def encrypt_token(raw: str) -> str:
    if not raw:
        return ''
    return _fernet().encrypt(raw.encode()).decode()

def decrypt_token(token: str) -> str:
    if not token:
        return ''
    return _fernet().decrypt(token.encode()).decode()
```

- [ ] Мигрировать `gitea_password` → `gitea_password_encrypted` (хранить шифровано, читать через `decrypt_token`).
- [ ] Data-миграция: зашифровать существующие плейнтекст-пароли.

**Файлы:** `src/studio/crypto.py` (new), `src/config/settings.py`, `src/users/models.py`, `src/users/migrations/000X_encrypt_gitea_password.py` (new), `src/studio/signals.py` (использовать `encrypt_token` при записи).

### TD-2. `GITHUB_TOKEN` в settings.py (P0, 0.5ч)

**Контекст:** `tasks.py:783` читает `getattr(settings, 'GITHUB_TOKEN', '')`, но `settings.py` его не определяет → всегда пусто, fallback-экспорт мёртв.

- [ ] В `settings.py` добавить: `GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')`.
- [ ] Добавить `GITHUB_TOKEN=` в `.env.example`.

**Файлы:** `src/config/settings.py`, `.env.example`.

### TD-3. Hardening Gitea-сигналов (P0, 3ч)

**Контекст (важно — бриф неточен):** auto-provisioning Gitea **уже подключён** через `src/studio/signals.py` — `ensure_gitea_account` (post_save User) и `ensure_repo` (post_save StudioProject) уже создают аккаунт и репозиторий. Проблема НЕ в отсутствии — а в том, что при исключении они **молча падают** (`logger.warning` и всё), и пользователь остаётся без репо, не зная об этом.

- [ ] Вынести провижининг в Celery-задачу с retry (синхронный сигнал блокирует регистрацию и теряет ошибку):
  - `ensure_gitea_account.delay(user_id)` и `ensure_repo.delay(project_id)`.
- [ ] Добавить поле `gitea_provision_status` на `StudioProject` (`pending|ok|failed`) и показывать в UI (`SandboxStatusBadge` рядом).
- [ ] При `failed` — кнопка «Повторить провижининг» (эндпоинт `POST /studio/projects/<id>/reprovision/`).
- [ ] Шифровать `gitea_password` при записи (см. TD-1).

**Файлы:** `src/studio/signals.py`, `src/studio/tasks.py` (new tasks), `src/studio/models.py` (+поле), `src/studio/views/projects.py` (+`ReprovisionView`), `src/studio/urls.py`.

### TD-4. SOCIALACCOUNT_PROVIDERS — добавить `github` (P1, 1ч)

**Контекст:** `allauth.socialaccount.providers.github` есть в `INSTALLED_APPS` (`settings.py:45`), но в `SOCIALACCOUNT_PROVIDERS` (`settings.py:200-222`) блока `github` НЕТ → OAuth-приложение не сконфигурировано.

- [ ] Добавить блок `'github': {'SCOPE': ['repo', 'read:user']}` в `SOCIALACCOUNT_PROVIDERS`.
- [ ] (Опционально, после Sprint 1) — связать OAuth-токен GitHub с экспортом как альтернативу PAT.

**Файлы:** `src/config/settings.py`.

---

## SPRINT 1 — Integrations & Trust (1 неделя, P0)

**Цель:** каждый пользователь подключает СВОИ GitHub PAT и Vercel-токен; экспорт и деплой идут от его имени; Gitea остаётся внутренним версионированием, работающим всегда без настройки.

### 1.1 DB-модель (новые поля на CustomUser)

```python
# src/users/models.py — CustomUser
github_pat_encrypted   = models.CharField(max_length=512, blank=True, default='')
vercel_token_encrypted = models.CharField(max_length=512, blank=True, default='')
github_pat_login       = models.CharField(max_length=128, blank=True, default='')  # кэш GitHub-логина
vercel_account_label   = models.CharField(max_length=128, blank=True, default='')  # для отображения
```

Запись/чтение — через `studio.crypto.encrypt_token` / `decrypt_token`. В сериализаторах НИКОГДА не отдаём расшифрованный токен — только булев `connected` + маскированный хвост (`****abcd`).

### 1.2 Новые API-эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| `GET` | `/api/v1/account/integrations/` | Статус подключений (connected/нет, маска, label) |
| `PUT` | `/api/v1/account/integrations/github/` | Сохранить GitHub PAT (валидация через GitHub API `/user`) |
| `DELETE` | `/api/v1/account/integrations/github/` | Отключить GitHub |
| `PUT` | `/api/v1/account/integrations/vercel/` | Сохранить Vercel-токен (валидация `GET /v2/user`) |
| `DELETE` | `/api/v1/account/integrations/vercel/` | Отключить Vercel |
| `POST` | `/api/v1/account/integrations/github/test/` | Проверить токен (rate-limit, scopes) |

**Валидация при сохранении:** перед записью дёргаем API провайдера. GitHub: `GET https://api.github.com/user` с `Authorization: token <PAT>` → если 200, кэшируем `login`. Vercel: `GET https://api.vercel.com/v2/user` → кэшируем `username`. Если 401 — ошибка «Токен недействителен», не сохраняем.

### 1.3 Изменение логики экспорта/деплоя

- [ ] `export_to_github` (`tasks.py:765`): приоритет токенов — **(1)** `user.github_pat_encrypted` (расшифровать) → **(2)** OAuth-токен allauth (если есть) → **(3)** `settings.GITHUB_TOKEN` (admin fallback). Создавать репо через GitHub API `POST /user/repos`, пушить.
- [ ] `deploy_to_vercel` (`tasks.py:620`): использовать `user.vercel_token_encrypted`; `settings.STUDIO_VERCEL_TOKEN` остаётся только как admin-fallback для `*.aineron.ru`-публикации (см. Sprint 2).
- [ ] Если у пользователя нет нужного токена — внятная ошибка в SSE: «Подключите GitHub на странице Интеграции», со ссылкой `/account/integrations/`.

### 1.4 Frontend — страница `/account/integrations/`

- [ ] Новый роут `frontend/app/account/integrations/page.tsx`.
- [ ] Две карточки: **GitHub** и **Vercel**. Каждая:
  - Статус подключения: иконка Lucide `CircleCheck` (подключено) / `CircleAlert` (не подключено) + текст «Подключено как `login`» / «Не подключено». **Без эмодзи.**
  - Поле ввода токена (`type=password`), кнопка «Проверить и сохранить», кнопка «Отключить».
  - Ссылка-инструкция «Как создать токен» (раскрывающийся блок со скриншот-шагами на русском).
- [ ] Карточка **Gitea (внутреннее версионирование)** — read-only: «Активно, настройка не требуется» + статус провижининга проекта.
- [ ] В `frontend/lib/api/` добавить методы `getIntegrations`, `saveGithubPat`, `saveVercelToken`, `disconnect*`.
- [ ] В Studio при ошибке экспорта/деплоя — тост со ссылкой на `/account/integrations/`.

### 1.5 Файлы Sprint 1

**Backend:** `src/users/models.py` (+поля), `src/users/migrations/000X_integration_tokens.py` (new), `src/api/views/integrations.py` (new), `src/api/serializers/integrations.py` (new), `src/api/urls.py`, `src/studio/tasks.py` (export/deploy logic), `src/studio/crypto.py` (из TD-1).

**Frontend:** `frontend/app/account/integrations/page.tsx` (new), `frontend/components/account/IntegrationCard.tsx` (new), `frontend/lib/api/account.ts` (или `integrations.ts`, new), `frontend/components/layout/` — пункт меню «Интеграции» в навигации кабинета.

### 1.6 Оценки и приоритеты

| Задача | Сложность | Приоритет |
|--------|-----------|-----------|
| Поля + миграция + crypto | 3ч | P0 |
| API-эндпоинты integrations + валидация | 6ч | P0 |
| Перепиновка export/deploy на user-токены | 5ч | P0 |
| Страница `/account/integrations/` + карточки | 8ч | P0 |
| Инструкции «как создать токен» (RU) | 2ч | P1 |
| **Итого Sprint 1** | **~24ч** | **P0** |

---

## SPRINT 2 — Non-Coder UX Revolution (1 неделя, P0/P1)

**Цель:** человек, который не умеет кодить, проходит путь «идея → опубликованное приложение» без единого технического термина.

### 2.1 Онбординг-визард Studio (отдельный от `/welcome/`)

- [ ] Новый роут `frontend/app/studio/onboarding/page.tsx` (3-4 шага):
  1. «Что хотите создать?» — крупные карточки выбора (Лендинг / Магазин / Портфолио / Дашборд / Telegram-лендинг / Своё).
  2. «Опишите словами» — большое текстовое поле с примерами-плейсхолдерами на русском.
  3. «Загрузите картинку (необязательно)» — скриншот/вайрфрейм для magic-describe.
  4. «Выберите модель и бюджет звёзд» — упрощённый, с человеческим объяснением «дороже = умнее».
- [ ] Запоминать прохождение в `localStorage` + поле `studio_onboarded` на user; показывать визард только при первом входе в `/studio/`.

### 2.2 Magic-describe (скриншот/вайрфрейм → приложение)

**Контекст:** механизм screenshot→AI-описание уже есть (`src/studio/agents/screenshot.py`, `ScreenshotView`). Расширяем на старт проекта.

- [ ] При создании проекта с изображением: прогоняем через `screenshot`-агента → получаем структурное описание → передаём как seed в InterviewerAgent/Planner.
- [ ] UI: drag&drop зоны в форме создания и в онбординге.

**Дельта:** backend-агент существует, нужна интеграция в create-flow + DnD-UI. **Не строить агента заново.**

### 2.3 Template marketplace (20+ реальных шаблонов)

**Контекст:** модель `StudioTemplate` есть, команда `seed_templates` есть, `TemplateListView` и `PublishTemplateView` есть. Нужен контент шаблонов + UI-галерея.

- [ ] Расширить `src/studio/management/commands/seed_templates.py` до 20+ шаблонов под РФ-рынок:
  - Лендинг продукта, Интернет-магазин, Портфолио, SaaS-дашборд, Лендинг Telegram-канала/бота, Карточка товара (маркетплейс), Запись к мастеру (салон/барбершоп), Меню кафе с QR, Лендинг мероприятия, Блог, Прайс-лист, Landing для курса, Форма заявки/квиз, Корпоративный сайт, One-page визитка, Сайт-каталог услуг, Промо-страница акции, Сбор отзывов, Mini-CRM, Калькулятор стоимости.
- [ ] Каждый шаблон: превью-картинка, русское название/описание, теги, стартовые файлы.
- [ ] UI-галерея шаблонов в `frontend/app/studio/page.tsx` (вкладка «Шаблоны») + «Создать из шаблона».

### 2.4 Progress storytelling (дружелюбный прогресс)

**Цель:** заменить `coder_iteration step 3/7` на человеческие фразы.

- [ ] Маппинг технических шагов агентов → дружелюбные русские сообщения, например:
  - `interviewer` → «Уточняю детали вашей идеи...»
  - `planner` → «Составляю план приложения...»
  - `coder_iteration` → «Собираю навигационное меню... Готово» (используем заголовок шага плана как описание).
  - `reviewer` → «Проверяю качество...»
  - `tester` → «Тестирую, что всё работает...»
- [ ] Завершённые шаги отмечаем иконкой Lucide `Check` (зелёная), текущий — `Loader2` (спиннер). **Без эмодзи.**
- [ ] Технический лог (`AgentLog`) скрываем за переключателем «Показать детали для разработчиков».

**Файлы:** `frontend/components/studio/PipelineStatus.tsx`, `StepTimeline.tsx`, новый словарь `frontend/lib/studio/step-labels.ts`.

### 2.5 One-click publish на `*.aineron.ru`

**Цель:** мгновенный публичный URL без домена/хостинга — главная «магия» для россиян.

- [ ] DB: поле `subdomain` на `StudioProject` (unique, slug-валидация, blacklist зарезервированных).
- [ ] Backend: статические проекты (HTML/SPA build) публикуем через nginx wildcard `*.aineron.ru` → отдаём из `media/published/<subdomain>/` или проксируем sandbox. Для статики — `STUDIO_VERCEL_TOKEN` (admin) деплой под суб-домен ИЛИ собственный CDN-каталог.
- [ ] nginx: добавить `server_name *.aineron.ru;` блок с роутингом на published-каталог.
- [ ] API: `POST /studio/projects/<id>/publish/` (body: `subdomain`), `DELETE` для снятия.
- [ ] UI: кнопка «Опубликовать», поле выбора суб-домена с live-проверкой доступности, после публикации — карточка с URL `myapp.aineron.ru` и кнопкой «Открыть»/«Скопировать».

**Файлы:** `src/studio/models.py` (+`subdomain`), миграция, `src/studio/views/projects.py` (+`PublishView`), `src/studio/tasks.py` (publish-задача), `nginx.conf`, `frontend/app/studio/[id]/page.tsx` (+кнопка), `frontend/components/studio/PublishModal.tsx` (new).

### 2.6 Mobile preview toggle

- [ ] В `PreviewPanel` добавить переключатель Desktop / Mobile (Lucide `Monitor` / `Smartphone`).
- [ ] Mobile — фиксированный iframe-вьюпорт 390×844 с рамкой устройства.

**Файлы:** `frontend/components/studio/PreviewPanel.tsx`.

### 2.7 «Что делает этот код?» — тултипы для не-кодеров

**Контекст:** `ExplainView` + `explainer`-агент уже есть.

- [ ] В `CodeViewer` — кнопка/иконка Lucide `HelpCircle` рядом с файлом/блоком → вызов `explain`-эндпоинта → поповер с объяснением на русском простыми словами.

**Файлы:** `frontend/components/studio/CodeViewer.tsx`.

### 2.8 Файлы и оценки Sprint 2

| Задача | Дельта | Сложность | Приоритет |
|--------|--------|-----------|-----------|
| Онбординг-визард Studio | новое (FE) | 8ч | P0 |
| Magic-describe в create-flow | backend есть, FE+интеграция | 5ч | P1 |
| 20+ шаблонов + галерея | модель есть, контент+FE | 10ч | P0 |
| Progress storytelling | FE-маппинг | 5ч | P0 |
| Publish на `*.aineron.ru` | backend+nginx+FE | 12ч | P0 |
| Mobile preview toggle | FE | 3ч | P1 |
| Explain-тултипы | backend есть, FE | 3ч | P2 |
| **Итого Sprint 2** | | **~46ч** | **P0** |

---

## SPRINT 3 — Collaboration & Virality (1 неделя, P1)

**Цель:** запустить виральную петлю — публичные ссылки, галерея, форк, presence, embed.

### 3.1 Публичная share-ссылка (read-only, без логина)

- [ ] DB: `share_token` (uuid, nullable) + `is_public` на `StudioProject`.
- [ ] API: `POST /studio/projects/<id>/share/` (генерит токен), `DELETE` (отзывает).
- [ ] Публичный роут `frontend/app/p/[token]/page.tsx` — read-only preview опубликованного проекта, без авторизации, с CTA «Создай своё на aineron.ru» (виральная петля).
- [ ] Публичный API-эндпоинт `GET /api/v1/public/projects/<token>/` (без auth, throttled).

**Файлы:** `src/studio/models.py`, миграция, `src/studio/views/projects.py` (+`ShareView`, +`PublicProjectView`), `src/api/urls.py`, `frontend/app/p/[token]/page.tsx` (new).

### 3.2 Публичная галерея проектов (showcase)

- [ ] DB: `gallery_approved` (bool, модерация админом) + `gallery_title`/`gallery_description`.
- [ ] API: `GET /api/v1/gallery/` (пагинация, фильтр по категории).
- [ ] Роут `frontend/app/studio/gallery/page.tsx` — сетка карточек с превью; клик → публичный preview.
- [ ] Админ-модерация в Django Admin (`gallery_approved`).

**Файлы:** `src/studio/models.py`, миграция, `src/studio/admin.py`, `src/api/views/gallery.py` (new), `frontend/app/studio/gallery/page.tsx` (new).

### 3.3 Форк проекта («использовать как шаблон»)

**Контекст:** поле `forked_from` уже есть (`migration 0007`), `PublishTemplateView` существует. Нужен UI и fork-эндпоинт.

- [ ] API: `POST /studio/projects/<id>/fork/` — копирует файлы/версии в новый проект текущего пользователя, ставит `forked_from`.
- [ ] UI: кнопка «Использовать как шаблон» на публичной странице проекта и в галерее.

**Дельта:** модель готова, нужен fork-эндпоинт + кнопка.

**Файлы:** `src/studio/views/projects.py` (+`ForkView`), `src/studio/urls.py`, `frontend/app/p/[token]/page.tsx`, `frontend/app/studio/gallery/page.tsx`.

### 3.4 Базовый realtime (presence — кто смотрит)

**Контекст:** `StudioCollaborator` модель есть (`migration 0005`), `CollaboratorView` есть, но НЕ подключена к фронту.

- [ ] Подключить `CollaboratorView` к UI: список коллабораторов в `ProjectSettingsModal`, добавление по email.
- [ ] Presence через существующий SSE-канал (`PipelineEventsView`): эвенты `viewer_joined`/`viewer_left`, в шапке Studio — аватары активных зрителей (Lucide `Users` + счётчик).
- [ ] (Полноценный multiplayer-курсор — out of scope этого спринта, отдельный эпик.)

**Дельта:** backend-модель и view готовы → **frontend-only** для коллабораторов; presence — лёгкое расширение SSE.

**Файлы:** `frontend/components/studio/ProjectSettingsModal.tsx`, `frontend/components/studio/PresenceBar.tsx` (new), `src/studio/events.py` (presence-эвенты).

### 3.5 Embed preview widget

- [ ] Роут `frontend/app/embed/[token]/page.tsx` — минимальный iframe-friendly preview (без шапки сайта).
- [ ] На странице проекта — «Скопировать iframe-код» для вставки в соцсети/блог.

**Файлы:** `frontend/app/embed/[token]/page.tsx` (new), `frontend/components/studio/EmbedModal.tsx` (new).

### 3.6 Файлы и оценки Sprint 3

| Задача | Дельта | Сложность | Приоритет |
|--------|--------|-----------|-----------|
| Share-ссылки + публичный preview | новое | 8ч | P1 |
| Галерея + модерация | новое | 8ч | P1 |
| Форк проекта | модель есть, +эндпоинт+UI | 5ч | P1 |
| Presence + коллабораторы UI | backend есть, FE+SSE | 7ч | P2 |
| Embed-виджет | новое | 4ч | P2 |
| **Итого Sprint 3** | | **~32ч** | **P1** |

---

## SPRINT 4 — Power User Features (1 неделя, P2)

**Цель:** удержать продвинутых пользователей и малый бизнес: домены, env, БД, API, CI/CD.

### 4.1 Кастомные домены (CNAME на CDN aineron.ru)

- [ ] DB: `custom_domain` + `domain_verified` на `StudioProject`.
- [ ] Flow: пользователь добавляет домен → выдаём CNAME-таргет (`cname.aineron.ru`) → проверка DNS (Celery-задача) → выпуск SSL (Let's Encrypt через nginx/certbot или Caddy on-demand TLS).
- [ ] API: `POST /studio/projects/<id>/domain/`, `GET .../domain/verify/`.

**Файлы:** `src/studio/models.py`, миграция, `src/studio/views/projects.py`, `src/studio/tasks.py` (DNS+TLS), `nginx.conf` (или Caddy-sidecar), `frontend/components/studio/DomainModal.tsx` (new).

### 4.2 Env-переменные проекта

- [ ] DB: модель `StudioEnvVar(project, key, value_encrypted)` (шифруем через `studio.crypto`).
- [ ] API: CRUD `/studio/projects/<id>/env/`.
- [ ] Инжект env в sandbox при старте dev-сервера (`sandbox.py`).
- [ ] UI: секция «Переменные окружения» в `ProjectSettingsModal` (значения маскированы).

**Файлы:** `src/studio/models.py` (+`StudioEnvVar`), миграция, `src/studio/views/` (+`EnvVarView`), `src/studio/sandbox.py`, `frontend/components/studio/ProjectSettingsModal.tsx`.

### 4.3 БД-провижининг (Supabase-style Postgres per project)

- [ ] При запросе «добавить БД» — создаём изолированную БД/схему в shared Postgres-кластере (db-сервис docker), отдельный пользователь/пароль (шифровано).
- [ ] DB: `StudioDatabase(project, db_name, db_user, db_password_encrypted, connection_string_masked)`.
- [ ] Инжектим `DATABASE_URL` в env проекта (см. 4.2).
- [ ] UI: кнопка «Добавить базу данных» + панель с таблицами (минимальный просмотр).
- [ ] Лимиты по тарифу/звёздам (провижининг БД стоит звёзд).

**Файлы:** `src/studio/models.py` (+`StudioDatabase`), миграция, `src/studio/db_provisioner.py` (new), `src/studio/views/`, `frontend/components/studio/DatabasePanel.tsx` (new).

### 4.4 Генерация API-эндпоинтов (приложение со своим API)

- [ ] Шаблоны/агент-инструкции для генерации backend-роутов (Next.js API routes / Express) в проекте.
- [ ] Coder-агент получает инструкцию «добавь API-эндпоинт для X» → генерит route + подключает к БД (4.3).
- [ ] UI: «Добавить API-эндпоинт» в чат-панели проекта.

**Файлы:** `src/studio/agents/coder.py` (расширить системный промпт), `frontend/components/studio/ContextChat.tsx`.

### 4.5 GitHub Actions CI/CD авто-setup

- [ ] При экспорте в GitHub (Sprint 1) опционально добавляем `.github/workflows/deploy.yml` (build + deploy на Vercel/`*.aineron.ru`).
- [ ] UI: чекбокс «Настроить авто-деплой (CI/CD)» в модалке экспорта.

**Файлы:** `src/studio/tasks.py` (export-задача добавляет workflow-файл), `frontend/components/studio/ExportModal.tsx`.

### 4.6 Файлы и оценки Sprint 4

| Задача | Сложность | Приоритет |
|--------|-----------|-----------|
| Кастомные домены + TLS | 12ч | P2 |
| Env-переменные | 6ч | P2 |
| БД-провижининг | 14ч | P2 |
| Генерация API | 8ч | P2 |
| CI/CD авто-setup | 5ч | P2 |
| **Итого Sprint 4** | **~45ч** | **P2** |

---

## 7. Lead Generation & Growth — стратегия для РФ

### 7.1 SEO-страницы на русском (P0 для роста)

Создать программные landing-страницы под высокочастотные коммерческие запросы:

| Запрос | URL | Тип |
|--------|-----|-----|
| создать сайт с помощью ИИ | `/sozdat-sayt-ii` | SSG-лендинг |
| вайбкодинг / vibe coding | `/vibecoding` | SSG-лендинг |
| создать приложение без программирования | `/sozdat-prilozhenie-bez-koda` | SSG-лендинг |
| создать интернет-магазин онлайн | `/sozdat-internet-magazin` | SSG-лендинг |
| сделать лендинг за час | `/sdelat-lending` | SSG-лендинг |
| no-code конструктор сайтов | `/no-code-konstruktor` | SSG-лендинг |

Каждая страница: H1 с ключом, демо-видео, 3 примера из галереи (Sprint 3), CTA «Создать бесплатно», FAQ с JSON-LD (FAQPage), внутренние ссылки на блог. Подключить к `sitemap.ts`.

**Файлы:** `frontend/app/(seo)/[slug]/page.tsx` или отдельные роуты, `frontend/app/sitemap.ts`, `src/blog/management/commands/create_seo_posts.py` (генерация сопутствующих статей).

### 7.2 Видео-контент (YouTube / VK Видео / Rutube)

- Серия «Собрал X за 10 минут без кода»: интернет-магазин, лендинг Telegram-канала, портфолио, запись к мастеру.
- Формат: реальный экран, реальный человек-не-кодер, таймер 10 минут.
- CTA: промокод на звёзды в описании (трекинг канала).

### 7.3 Партнёрства с комьюнити

- **VC.ru** — статья-кейс «Как мы сделали российский ответ Lovable».
- **Habr** — техническая статья про agent-pipeline + Gitea-версионирование (для разработчиков).
- **Product Radar / Russian ProductHunt-аналоги** — запуск.
- Telegram-каналы про стартапы и no-code — интеграции/обзоры.

### 7.4 Реферальная программа (используем существующую инфраструктуру)

**Контекст:** реферальная система уже есть (`referral_code`, `referrer`, `ReferralEarning`).

- Механика для Studio: «Пригласи друга → оба получаете 50 звёзд после первого собранного проекта друга».
- Виральный множитель от share-ссылок (Sprint 3): на публичной странице проекта — реф-CTA.

### 7.5 «Бесплатный MVP» — посевная виральность

- Первый проект бесплатно (списываем из welcome-звёзд) → пользователь получает рабочий результат → делится share-ссылкой → петля.
- Кампания «Покажи свой проект — получи звёзды» для наполнения галереи.

### 7.6 Кейсы (контент-маркетинг)

- «Как я запустил интернет-магазин за 2 часа без программиста».
- «Лендинг для Telegram-канала с нуля: пошагово».
- «Сайт записи в барбершоп без разработчика».
- Публиковать в блоге (`/blog/`, SSR+ISR уже есть) + кросс-постинг в соцсети.

### 7.7 Метрики роста (что мерить)

| Метрика | Цель |
|---------|------|
| Activation (создал первый проект) | > 40% от регистраций |
| Time-to-first-preview | < 3 мин |
| Publish rate (опубликовал на `*.aineron.ru`) | > 25% активированных |
| Viral coefficient (share→signup) | > 0.3 |
| Звёзд потрачено на проект (median) | трекинг для ценообразования |

---

## 8. Сводка технического долга (приоритезированно)

| # | Долг | Реальное состояние | Фикс | Приоритет |
|---|------|--------------------|------|-----------|
| TD-1 | Gitea-пароль в плейнтексте | `gitea_password` plaintext (`models.py:471`) | Fernet-шифрование (`cryptography` уже есть) | P0 |
| TD-2 | `GITHUB_TOKEN` мёртв | читается в `tasks.py:783`, не определён в `settings.py` | `GITHUB_TOKEN = os.getenv(...)` | P0 |
| TD-3 | Gitea-провижининг падает молча | **уже подключён** в `signals.py`, но silent-fail | вынести в Celery + retry + статус в UI | P0 |
| TD-4 | `github` OAuth не сконфигурирован | в `INSTALLED_APPS`, нет в `SOCIALACCOUNT_PROVIDERS` | добавить блок `'github'` | P1 |
| TD-5 | `StudioCollaborator` не на фронте | модель+`CollaboratorView` есть, FE нет | frontend-only (Sprint 3) | P1 |

> **Заметка о точности брифа:** исходный бриф утверждал, что Gitea-провижининг «не триггерится» и «collaborator/template UI не реализованы как backend». Фактически: провижининг **подключён** (`signals.py`), а `PublishTemplateView`, `CollaboratorView`, `forked_from`, `ScreenshotView`, `ExplainView`, `export_to_github` — **уже существуют на backend**. Поэтому в этом плане соответствующие задачи помечены как «frontend-only» или «интеграция существующего», а не «построить с нуля» — это снижает оценки часов и риски.

---

## 9. Дорожная карта на одной странице

```
Неделя 0   [TECH DEBT]  crypto • GITHUB_TOKEN • hardening signals • github provider
Неделя 1   [SPRINT 1]   per-user GitHub PAT + Vercel token • /account/integrations/
Неделя 2   [SPRINT 2]   онбординг • magic-describe • 20+ шаблонов • storytelling • *.aineron.ru • mobile preview
Неделя 3   [SPRINT 3]   share-ссылки • галерея • форк • presence • embed
Неделя 4   [SPRINT 4]   домены • env • БД • API-генерация • CI/CD
Сквозняком [GROWTH]     SEO-лендинги (RU) • видео • рефералка • кейсы • галерея-виральность
```

**Критический путь к «топ-1 РФ»:** Tech Debt → Sprint 1 (доверие к деплою) → Sprint 2 (UX не-кодера + `*.aineron.ru`) → Sprint 3 (виральность). Sprint 4 — удержание и монетизация продвинутых.

---

## Приложение A — соответствие дизайн-системе

Все UI-индикаторы статусов в этом плане используют **Lucide React**, не эмодзи (требование `CLAUDE.md`):

| Состояние | Иконка Lucide | Цвет |
|-----------|---------------|------|
| Подключено / успех | `CircleCheck` / `Check` | `var(--success)` |
| Не подключено / ошибка | `CircleAlert` / `X` | `var(--danger)` |
| В процессе | `Loader2` (spin) | `var(--muted)` |
| Зрители онлайн | `Users` | `var(--fg)` |
| Mobile/Desktop preview | `Smartphone` / `Monitor` | `var(--fg)` |
| Объяснение кода | `HelpCircle` | `var(--muted)` |

Тексты кнопок — короткие глаголы без спецсимволов: «Подключить», «Опубликовать», «Поделиться», «Создать из шаблона».
