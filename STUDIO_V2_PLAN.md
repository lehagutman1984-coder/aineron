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

---

# ДОПОЛНЕНИЕ V2.1 — Краулер, промты, синхронизация, выбор модели, онбординг

> Это дополнение к плану выше. Все задачи опираются на **фактический код** (`src/studio/*`), а не на гипотезы. Где брифом предлагалось «добавить с нуля», но функционал уже существует — это явно отмечено, чтобы не плодить дубли (принцип «no lazy shortcuts», см. раздел E).

---

## A. Краулинг и копирование сайтов — профессиональный рефакторинг

### A.1 Честный аудит текущего краулера

Текущий `src/studio/crawler.py` — это **две функции-заглушки**, достаточные для «понять о чём сайт», но непригодные для копирования:

| Что краулер делает сейчас | Что НЕ делает |
|---------------------------|----------------|
| `crawl()` — один GET через `requests`, парсит `<title>`, текст (`get_text`, обрезан до 20000), список `<link rel=stylesheet href>` | Не скачивает CSS-файлы — только собирает их URL и выбрасывает |
| `crawl_spa()` — Playwright рендерит SPA, отдаёт HTML+текст | Не скачивает JS, шрифты, изображения |
| `is_safe_url()` защищает от SSRF | Не обходит вложенные страницы — только переданный URL |
| `crawl_and_analyze` falls back на `crawl_spa` если текста < 200 символов | Не удаляет аналитику (GA/YM/Hotjar) — она утечёт в клон |
| Результат складывается в `interview_data['crawled']` (только `title` + `text[:8000]`) | Не нормализует относительные URL → ресурсы 404 при сборке клона |
| | Не извлекает структуру навигации (меню, разделы) для планировщика |
| | Не уникализирует ресурсы (EXIF, хэши имён классов) |

**Вывод:** сегодня «Клон по URL» по сути даёт AI текстовый пересказ страницы, по которому агенты пишут *новый* сайт «по мотивам». Это не копирование — это «вдохновлённая реконструкция». Для честного позиционирования «клон» нужен настоящий ресурсный краулер.

### A.2 Gap-анализ против KopirkaCMS

| Возможность | KopirkaCMS | Studio сейчас | Цель V2.1 |
|-------------|------------|---------------|-----------|
| Копирование 1-10 страниц | да | 1 (только входной URL) | до N=10, рекурсивно по внутренним ссылкам |
| Скачивание CSS/JS/шрифтов/картинок | да | нет (только URL CSS) | да, полная выгрузка ресурсов |
| Уникализация изображений (EXIF, quality) | да | нет | да (Pillow), опционально |
| Удаление аналитики (GA, YM, Hotjar, Intercom) | да | нет | да, чёрный список доменов/скриптов |
| AI-переписывание контента | да (GPT) | да (наш AnalystAgent/CoderAgent уже переписывают) | оставляем как есть — это наша сильная сторона |
| Рандомизация CSS-классов | да | нет | опционально, фаза 2 |
| JS-движок для SPA | scrape.do | свой Playwright-воркер (`celery_studio_playwright`) | улучшаем — у нас уже есть, бесплатно |

**Наше преимущество:** у нас уже есть собственный Playwright-воркер (не платный scrape.do) и агенты, которые переписывают контент осмысленно, а не «спинят» текст. Дыра — именно ресурсный слой.

### A.3 Архитектура нового краулера

Многоуровневый модуль `src/studio/crawler.py` + новый пакет `src/studio/crawl/`:

```
src/studio/crawl/
├── __init__.py
├── fetcher.py        # Уровень 1 (requests) и Уровень 2 (Playwright) с единым интерфейсом
├── resources.py      # Скачивание и сохранение CSS/JS/шрифтов/картинок
├── sanitizer.py      # Удаление аналитики/чатов, нормализация URL
├── navigation.py     # Извлечение структуры навигации для PlannerAgent
└── pipeline.py       # Оркестрация: fetch → recurse → resources → sanitize → pack
```

**Уровень 1 — статика (`fetcher.fetch_static`)**
- `requests.get` + BeautifulSoup (как сейчас), но возвращает полный распарсенный DOM-объект, а не обрезанный текст.
- Используется по умолчанию; если итоговый текст < 200 символов → эскалация на Уровень 2.

**Уровень 2 — SPA (`fetcher.fetch_spa`)**
- Playwright (`celery_studio_playwright`, prefork, не gevent — это критично, уже соблюдается).
- `wait_until='networkidle'` + перехват сетевых ответов (`page.on('response')`), чтобы собрать реальные URL подгруженных ресурсов (CSS/JS/шрифты), а не только статические `<link>`.

**Полная загрузка ресурсов (`resources.download_all`)**
- Из DOM + перехваченных ответов собираем множество URL: `<link rel=stylesheet>`, `<script src>`, `<img src/srcset>`, `@font-face` в CSS, `url(...)` в CSS.
- Каждый ресурс качаем (с `is_safe_url` проверкой), складываем как `StudioFile` с относительным путём (`assets/css/...`, `assets/js/...`, `assets/img/...`, `assets/fonts/...`).
- Переписываем ссылки в HTML/CSS на локальные относительные пути.

**Рекурсивный обход (`pipeline.crawl_site`)**
- Параметр `max_pages` (default 1, максимум 10), BFS по внутренним ссылкам того же домена.
- Дедупликация по нормализованному URL (без query/fragment, trailing slash).
- Лимит глубины + общий timeout (используем тот же паттерн, что `wait_for_ready`).

**Удаление аналитики/чатов (`sanitizer.strip_trackers`)**
- Чёрный список хостов/паттернов: `google-analytics.com`, `googletagmanager.com`, `mc.yandex.ru`, `mc.webvisor.org`, `static.hotjar.com`, `widget.intercom.io`, `connect.facebook.net`, `vk.com/js/api/openapi`, `top-fwz1.mail.ru`, `cdn.jsdelivr.net/npm/@vkontakte`, чат-виджеты (`jivo`, `carrotquest`, `tawk.to`, `bitrix24`).
- Удаляем соответствующие `<script>`, `<noscript>` пиксели и inline-`dataLayer`/`ym(`/`gtag(` блоки.

**Нормализация URL (`sanitizer.normalize_urls`)**
- Абсолютные → относительные локальные пути.
- Устранение дублей: один и тот же ресурс с разными query-хвостами сохраняется один раз (хэш содержимого).

**Извлечение навигации (`navigation.extract_nav`)**
- Парсим `<nav>`, `<header>`, `role=navigation`, частые селекторы меню.
- Возвращаем структуру `[{label, href, children}]`, кладём в `interview_data['crawled']['navigation']`.
- PlannerAgent использует её, чтобы спланировать многостраничную структуру (раздел B/G).

### A.4 Задачи по коммитам — краулер

- [ ] **Коммит A-1. Каркас пакета `crawl/` + единый fetcher.**
  Создать `src/studio/crawl/__init__.py`, `fetcher.py` с `fetch_static()` и `fetch_spa()` (перенести логику из `crawler.py`, добавить перехват `page.on('response')` в SPA-режиме). Сохранить `is_safe_url()` на входе обеих функций. Файлы: `src/studio/crawl/fetcher.py`, рефактор `src/studio/crawler.py` (делегирует в новый пакет, сохраняет публичные `crawl`/`crawl_spa` для обратной совместимости с `tasks.py`).

- [ ] **Коммит A-2. Скачивание и сохранение ресурсов.**
  `src/studio/crawl/resources.py` — `collect_urls(dom, captured)`, `download_all(urls, project)` → создаёт `StudioFile` записи (`assets/...`). Лимит размера на ресурс (например 5 МБ), общий лимит на проект. Файлы: `src/studio/crawl/resources.py`.

- [ ] **Коммит A-3. Санитайзер аналитики и чатов.**
  `src/studio/crawl/sanitizer.py` — `strip_trackers(dom)` по чёрному списку, удаление inline-трекинга. Юнит-тест с фикстурой HTML, содержащей GA+YM+Jivo. Файлы: `src/studio/crawl/sanitizer.py`, `src/studio/tests.py`.

- [ ] **Коммит A-4. Нормализация URL и дедуп ресурсов.**
  В `sanitizer.normalize_urls(dom, base_url)` + дедуп по SHA-256 содержимого в `resources.py`. Переписать ссылки в HTML и внутри CSS (`url(...)`, `@import`). Файлы: `src/studio/crawl/sanitizer.py`, `src/studio/crawl/resources.py`.

- [ ] **Коммит A-5. Рекурсивный обход страниц.**
  `src/studio/crawl/pipeline.py` — `crawl_site(url, max_pages, mode)` BFS, дедуп URL, общий timeout. Параметр `max_pages` приходит из `project.interview_data['clone_opts']`. Файлы: `src/studio/crawl/pipeline.py`.

- [ ] **Коммит A-6. Извлечение навигации для планировщика.**
  `src/studio/crawl/navigation.py` — `extract_nav(dom)`. Складывать в `interview_data['crawled']['navigation']`. Файлы: `src/studio/crawl/navigation.py`, правка `src/studio/tasks.py` (`crawl_and_analyze`, `crawl_spa_task`).

- [ ] **Коммит A-7. Опциональная уникализация изображений.**
  `resources.uniquify_image(bytes)` — снять EXIF, лёгкая ре-компрессия (Pillow). Включается флагом `clone_opts.uniquify=True`. Файлы: `src/studio/crawl/resources.py`.

- [ ] **Коммит A-8. Интеграция в задачи + UI-опции клонирования.**
  Переключить `crawl_and_analyze`/`crawl_spa_task` на `pipeline.crawl_site`. На фронте — поля «Страниц (1-10)» и чекбоксы «Удалить аналитику», «Уникализировать картинки» в форме «Клон по URL». Файлы: `src/studio/tasks.py`, `frontend/app/studio/page.tsx`, `frontend/lib/api/studio.ts`.

### A.5 Новые Python-зависимости

| Пакет | Зачем | Примечание |
|-------|-------|------------|
| `playwright` | уже используется (`crawl_spa`) | без изменений |
| `beautifulsoup4` | уже используется | без изменений |
| `Pillow` | уникализация изображений (EXIF, recompress) | вероятно уже в зависимостях (медиа) — проверить `requirements.txt` |
| `tinycss2` | парсинг CSS для извлечения `url(...)` и `@font-face` | **новый**, лёгкий, без C-расширений |

> Не тянем тяжёлых зависимостей (Scrapy, selenium). Playwright + tinycss2 покрывают всё.

---

## B. Профессиональные промты агентов — билингвальный подход

### B.1 Принцип переключения языков

Факт из кода: сейчас **все** системные промты в `src/studio/agents/*.py` написаны по-русски, а пользовательский ввод (`PROJECT.md`, описание) — тоже русский. Модели laozhang.ai (Claude, GPT, DeepSeek, Qwen) дают заметно более стабильный код и строже следуют JSON-схемам, когда **системные инструкции на английском**, при этом **контент для пользователя** (вопросы интервью, PROJECT.md, COMMITS.md) должен оставаться **русским**.

**Правило:**
- **System prompt → английский.** Инструкции, схемы JSON, ограничения. Модель «думает» по-английски надёжнее.
- **Пользовательский вывод → русский.** В конце каждого английского промта явно указываем: `All user-facing text (questions, PROJECT.md, COMMITS.md, summaries) MUST be in Russian.`
- **Код и идентификаторы → английский** всегда (имена файлов, переменные, комментарии — на усмотрение, по умолчанию русские комментарии для не-кодера).
- Реализация: каждый агент хранит `SYSTEM_RU` и `SYSTEM_EN`; выбор управляется `settings.STUDIO_PROMPT_LANG` (default `'en'`). Это даёт A/B без передеплоя и быстрый откат, если конкретная модель деградирует на английском.

Ниже — полные промты. RU оставляем как fallback/референс; EN — рабочий по умолчанию.

### B.2 InterviewerAgent (`src/studio/agents/interviewer.py`)

**RU:**
```
Ты интервьюер сервиса генерации веб-приложений. По краткому описанию проекта
задай 3-5 умных уточняющих вопросов, которые реально влияют на функционал,
дизайн и стек. Не задавай очевидных или избыточных вопросов. Учитывай выбранный
стек. Для вопросов с выбором давай 2-4 варианта.
Верни СТРОГО JSON-массив: [{"id":"q1","question":"...","type":"text|choice","options":["..."]}].
Вопросы — на русском. Никакого текста вне JSON.
```

**EN (рабочий):**
```
You are an interviewer for a web-app generation service. Given a short project
description, ask 3-5 smart clarifying questions that materially affect scope,
design, and stack. Do not ask obvious or redundant questions. Respect the chosen
stack (Next.js/React/Vue/HTML). For choice questions provide 2-4 options.
Return STRICTLY a JSON array: [{"id":"q1","question":"...","type":"text|choice","options":["..."]}].
The "question" and "options" text MUST be written in Russian. Output nothing outside the JSON.
```

### B.3 AnalystAgent (`src/studio/agents/analyst.py`)

**RU:**
```
Ты системный аналитик. На основе описания проекта, ответов интервью и (если есть)
данных краулинга составь технический документ PROJECT.md: цель, целевая аудитория,
функциональные требования (нумерованный список), карта страниц, модель данных,
стек и обоснование, нефункциональные требования (производительность, адаптив,
доступность), ограничения и допущения. Документ должен быть конкретным и
реализуемым. Markdown на русском, без преамбулы.
```

**EN (рабочий):**
```
You are a systems analyst. Using the project description, interview answers, and
(if present) crawled site data, produce a technical PROJECT.md document containing:
goal, target audience, functional requirements (numbered), page map, data model,
chosen stack with justification, non-functional requirements (performance,
responsiveness, accessibility), constraints and assumptions. Be concrete and
buildable — avoid vague aspirations. Output Markdown in Russian, no preamble.
```

### B.4 PlannerAgent (`src/studio/agents/planner.py`)

**RU:**
```
Ты технический планировщик. На основе PROJECT.md составь COMMITS.md — пошаговый
план реализации. Каждый шаг (коммит) атомарный: заголовок, краткая цель, точный
список создаваемых/изменяемых файлов. Порядок шагов учитывает зависимости
(сначала каркас и конфиг, затем компоненты, затем интеграции). Помечай заголовок
тегом [COMPLEX], если шаг включает auth, оплату, интеграции, realtime, миграции БД
или затрагивает 5+ файлов. Не превышай 15 шагов. В конце верни маркер
<STEPS_COUNT>N</STEPS_COUNT>. Markdown на русском, без преамбулы.
```

**EN (рабочий):**
```
You are a technical planner. From PROJECT.md, produce COMMITS.md — a step-by-step
implementation plan. Each step (commit) is atomic: a heading, a one-line goal, and
the exact list of files created/modified. Order steps by dependency (scaffold and
config first, then components, then integrations). Tag a heading with [COMPLEX] if
the step involves auth, payments, third-party integrations, realtime, DB migrations,
or touches 5+ files. Do not exceed 15 steps. End the document with the marker
<STEPS_COUNT>N</STEPS_COUNT> where N is the number of steps. Output Markdown in
Russian, no preamble.
```
> Совместимо с `planner.py`: код по-прежнему парсит `<STEPS_COUNT>` и `_split_steps` по `##`/`###` заголовкам, а `[COMPLEX]` читается `coder._pick_model`.

### B.5 CoderAgent (`src/studio/agents/coder.py`)

**RU:**
```
Ты senior-разработчик. Реализуй РОВНО ОДИН шаг из COMMITS.md. Ты владеешь
TypeScript, Next.js 14 (App Router), React (hooks, функциональные компоненты),
Vue 3 (Composition API) и семантическим HTML/CSS. Пиши production-ready код:
типобезопасный, без TODO-заглушек, с обработкой ошибок и состояний загрузки.
Для Vite-проектов всегда указывай server.host:true. Не выдумывай несуществующие
зависимости. Учитывай уже существующие файлы (даны в контексте) — не дублируй и
не ломай их. Верни СТРОГО JSON: {"files":{"относительный/путь":"полное содержимое"}}.
Полные файлы целиком, не диффы.
```

**EN (рабочий):**
```
You are a senior software engineer. Implement EXACTLY ONE step from COMMITS.md.
You are fluent in TypeScript, Next.js 14 (App Router), React (hooks, function
components), Vue 3 (Composition API), and semantic HTML/CSS. Write production-ready
code: type-safe, no TODO stubs, with error handling and loading states. For Vite
projects always set server.host:true in vite.config. Never invent nonexistent
dependencies. Respect existing project files (provided in context) — do not
duplicate or break them. If a FixPlan is provided, change ONLY the listed files.
Return STRICTLY JSON: {"files":{"relative/path":"full file content"}} — whole files,
never diffs. Code comments may be in Russian; identifiers must be English.
```
> Совместимо с `coder.run()`: парсер ждёт `{"files": {...}}`, `allowed_files` фильтрует результат. Упоминание FixPlan соответствует ветке `iteration_count > 0` в `tasks.coder_iteration`.

### B.6 ReviewerAgent (`src/studio/agents/reviewer.py`)

**RU:**
```
Ты ревьюер кода уровня senior. Проверь ТОЛЬКО изменённые файлы (раздел «Изменённые
файлы»; полный список — лишь контекст). Проверяй: синтаксис и типы, корректность
импортов и путей, соответствие шагу, явные баги и edge-cases, БЕЗОПАСНОСТЬ (XSS,
инъекции, секреты в коде, небезопасный dangerouslySetInnerHTML/eval, открытые
CORS). severity=error — блокирует; severity=warning — желательно поправить.
Верни СТРОГО JSON: {"passed":bool,"issues":[{"file":"...","severity":"error|warning","message":"..."}],"summary":"..."}.
summary — на русском.
```

**EN (рабочий):**
```
You are a senior code reviewer. Review ONLY the changed files (the "Изменённые
файлы" section; the full list is context only). Check: syntax and types, import
correctness and paths, conformance to the step, obvious bugs and edge cases, and
SECURITY (XSS, injection, secrets in code, unsafe dangerouslySetInnerHTML/eval,
permissive CORS). severity=error blocks the step; severity=warning is advisory.
Return STRICTLY JSON:
{"passed":bool,"issues":[{"file":"...","severity":"error|warning","message":"..."}],"summary":"..."}.
The "summary" and "message" text MUST be in Russian.
```

### B.7 TesterAgent (`src/studio/agents/tester.py`)

**RU:**
```
Ты QA-инженер. Проанализируй логи сборки/typecheck из sandbox и exit_code.
Определи ошибки компиляции (TS/build) и рантайма. Для каждой ошибки укажи тип,
файл (если виден) и понятное сообщение. Если exit_code != 0 — build_ok=false.
Верни СТРОГО JSON: {"passed":bool,"errors":[{"type":"build|runtime","message":"...","file":"..."}],"build_ok":bool,"summary":"..."}.
summary — на русском.
```

**EN (рабочий):**
```
You are a QA engineer. Analyze the sandbox build/typecheck logs and exit_code.
Identify compilation (TS/build) and runtime errors. For each error give type, file
(if identifiable), and a clear message. If exit_code != 0 then build_ok=false.
Return STRICTLY JSON:
{"passed":bool,"errors":[{"type":"build|runtime","message":"...","file":"..."}],"build_ok":bool,"summary":"..."}.
The "summary" and "message" text MUST be in Russian.
```
> Совместимо с `tester.run()`: код принудительно ставит `build_ok=false`/`passed=false`, если `exit_code != 0`.

### B.8 FixerAgent (`src/studio/agents/fixer.py`)

**RU:**
```
Ты ведущий инженер. Сведи ReviewReport и TestReport в чёткий FixPlan для кодера.
Сначала устраняй ошибки сборки (build), затем error-уровня ревью, затем warning.
Инструкции — конкретные, по делу: что именно и в каком файле поправить. Минимизируй
список target_files (только реально затронутые). Если ошибки указывают на ошибки
из console превью — учитывай их.
Верни СТРОГО JSON: {"instructions":"...","target_files":["..."],"priority":"high|medium"}.
instructions — на русском.
```

**EN (рабочий):**
```
You are a lead engineer. Merge the ReviewReport and TestReport into a precise
FixPlan for the coder. Prioritize: build errors first, then error-severity review
issues, then warnings. Instructions must be concrete and actionable: exactly what
to change and in which file. Keep target_files minimal (only genuinely affected
files). If errors come from the preview console, account for them.
Return STRICTLY JSON: {"instructions":"...","target_files":["..."],"priority":"high|medium"}.
The "instructions" text MUST be in Russian.
```
> Совместимо с `fixer.run()` и потреблением `fix_plan` в `tasks.coder_iteration` (читает `target_files`/`instructions`).

### B.9 Задачи по коммитам — промты

- [ ] **Коммит B-1.** Ввести `STUDIO_PROMPT_LANG` (`settings.py`, default `'en'`) и хелпер `pick_prompt(ru, en)` в `src/studio/agents/base.py`.
- [ ] **Коммит B-2.** Вынести `SYSTEM_RU`/`SYSTEM_EN` во все 7 агентов, переключение через `pick_prompt`. Файлы: `src/studio/agents/{interviewer,analyst,planner,coder,reviewer,tester,fixer}.py`.
- [ ] **Коммит B-3.** Тесты: парсинг JSON-схем не сломан на EN-промтах (мок-ответы модели). Файл: `src/studio/tests.py`.

---

## C. Синхронизация агентов — анти-зацикливание и визуальный статус

### C.1 Аудит текущей защиты

Что **уже есть** в коде:
- `StudioPipelineState.iteration_count` + `settings.STUDIO_MAX_ITERATIONS` (default 3). В `tasks.merge_reports` при недостижении `passed` инкремент и повтор `coder_iteration`; при достижении лимита — возврат звёзд и `status='paused_on_loop'`.
- `pause_requested` / `paused_manual` / `paused_on_loop` — проверяются в начале `start_step`, `coder_iteration`, `merge_reports`, `next_step`.
- `current_task_id` сохраняется в `coder_iteration` — есть точка для `celery revoke`.
- `reap_stale_sandboxes` (beat) убивает контейнеры старше 6 ч.
- Финансовый предохранитель: `reserve` → `charge_from_reserve` → `_pause_no_funds`.

### C.2 Анализ дыр

| Дыра | Почему зацикливание/зависание всё ещё возможно |
|------|-----------------------------------------------|
| Лимит на **шаг**, а не на проект | 12 шагов × 3 итерации = до 36 прогонов CoderAgent — пользователь ждёт и платит, прогресса нет |
| **Нет детектора одинакового diff** | `interview_data['last_changed'][step]` хранит только **пути файлов**, не содержимое — модель может 3 раза подряд вернуть идентичный код, лимит «сгорит» впустую |
| **Нет глобального timeout пайплайна** | если задача Celery зависла внутри `run_prompt` (synchronous, timeout 180с на вызов, но цепочка задач может тянуться часами на ретраях) — проект «висит» в `coding` |
| **Нет heartbeat** | `pipeline.updated_at` обновляется, но никто не проверяет «давно не было событий → агент завис» |
| `reap_stale_sandboxes` судит по **возрасту контейнера**, а не по активности пайплайна | живой, но зависший проект не освобождается до 6 ч |

### C.3 Многоуровневая защита

1. **Лимит итераций на шаг** (есть) — оставляем `STUDIO_MAX_ITERATIONS`, но логируем в SSE «Попытка K из N» (для UI, раздел C.4).
2. **Детектор одинакового diff.** В `coder_iteration` после генерации считать `sha256` от конкатенации `sorted(files.items())` и хранить в `pipeline` (новое поле `last_files_hash` + `same_diff_count`). Если хэш совпал с предыдущей итерацией → инкремент `same_diff_count`; при `>= 2` — не тратить ещё одну итерацию впустую, а сразу `paused_on_loop` с понятным reason «Агент не может изменить код — нужна ваша подсказка».
3. **Детектор зацикленных тестов.** Если `test_report.passed=false` с **той же** первой ошибкой N раз подряд (хранить `last_error_signature`), эскалировать модель кодера на `smart` на одну попытку (см. раздел D), затем пауза.
4. **Глобальный timeout пайплайна.** Новое поле `pipeline.started_at`; новый beat-таск `watchdog_pipelines` (каждые 2 мин): если `status='running'` и `now - updated_at > STUDIO_STEP_STALL_SEC` (например 240с) → пометить `paused_on_loop`, при `now - started_at > STUDIO_PIPELINE_MAX_SEC` (например 45 мин) → `failed` + освободить sandbox + `release_reserve`.
5. **Heartbeat.** Каждый агент уже шлёт события через `publish_event`. Watchdog (п.4) использует `updated_at` как heartbeat. Дополнительно — `coder_iteration`/`agent_test` обновляют `pipeline.save()` (touch `updated_at`) в начале работы. Если воркер завис на `run_prompt`, `current_task_id` позволяет `app.control.revoke(task_id, terminate=True)`.

### C.4 Визуальный статус для пользователя

Компонент `frontend/components/studio/PipelineTimeline.tsx`:
- **Timeline шагов** из COMMITS.md: каждый шаг — строка с иконкой Lucide:
  - выполнен — `Check` (`var(--success)`)
  - текущий — `Loader2` (spin, `var(--muted)`)
  - ожидает — `Circle` (приглушённый)
  - ошибка/пауза — `AlertCircle` (`var(--danger)`)
- **Текущий агент** + дружелюбная фраза (маппинг агент→текст):
  - `analyst` → «Разбираю, что нужно построить»
  - `planner` → «Составляю план по шагам»
  - `coder` → «Пишу код»
  - `reviewer` → «Проверяю код на ошибки»
  - `tester` → «Запускаю сборку»
  - `fixer` → «Готовлю исправления»
- **Счётчик попыток**: «Попытка 2 из 3» (из `iteration_count` + `STUDIO_MAX_ITERATIONS`, отдаётся в pipeline-статусе).
- **Таймер на шаге**: время с момента `pipeline.updated_at` для текущего шага.

### C.5 Информативное восстановление после ошибки

Компонент `frontend/components/studio/PipelineRecovery.tsx` (показывается при `status='paused'`/`paused_on_loop`/`failed`):
- **Понятное объяснение** из `pause_reason` (мы уже пишем человекочитаемые причины: «Шаг N не сошёлся за K итераций», «Недостаточно звёзд», «Агент не может изменить код»).
- **Три кнопки:**
  - «Попробовать снова» → `POST .../pipeline/resume` (существующий `PipelineResumeView`), при «одинаковом diff» — открыть поле подсказки и переслать её в FixPlan.
  - «Пропустить шаг» → новый эндпоинт `POST .../pipeline/skip` (помечает шаг как принятый, `next_step.delay`).
  - «Описать проблему» → текстовое поле, текст уходит в `fix_plan.instructions` и запускает `coder_iteration` заново.
- **При зависании** (watchdog пометил `failed` по timeout) — автоматически: `kill_sandbox` + `release_reserve` уже сделаны, UI предлагает «Продолжить с этого шага» (re-spawn sandbox через `_ensure_sandbox`).

### C.6 Задачи по коммитам — синхронизация

- [ ] **Коммит C-1. Поля анти-цикла.** Миграция: `pipeline.last_files_hash` (char), `same_diff_count` (int), `last_error_signature` (char), `started_at` (datetime). Файлы: `src/studio/models.py`, `src/studio/migrations/00XX_pipeline_antiloop.py`.
- [ ] **Коммит C-2. Детектор одинакового diff + зацикленных тестов.** Логика в `coder_iteration` (хэш файлов) и `merge_reports` (сигнатура ошибки, эскалация модели). Файл: `src/studio/tasks.py`.
- [ ] **Коммит C-3. Watchdog-beat.** `watchdog_pipelines` + регистрация в beat-расписании; настройки `STUDIO_STEP_STALL_SEC`, `STUDIO_PIPELINE_MAX_SEC`. Использует `current_task_id` для revoke. Файлы: `src/studio/tasks.py`, `src/config/celery.py`, `src/config/settings.py`.
- [ ] **Коммит C-4. PipelineTimeline + дружелюбные фразы.** Компонент + расширить pipeline-статус (`step_index`, `iteration_count`, `max_iterations`, фразы). Файлы: `frontend/components/studio/PipelineTimeline.tsx`, `src/studio/views/pipeline.py` (сериализация статуса).
- [ ] **Коммит C-5. PipelineRecovery + эндпоинт skip.** Компонент с 3 кнопками + `PipelineSkipView`. Файлы: `frontend/components/studio/PipelineRecovery.tsx`, `src/studio/views/pipeline.py`, `src/studio/urls.py`.
- [ ] **Коммит C-6. Подсказка пользователя → FixPlan.** Поле подсказки в Recovery прокидывает текст в `fix_plan.instructions` через resume. Файлы: `frontend/components/studio/PipelineRecovery.tsx`, `src/studio/views/pipeline.py`.

---

## D. Выбор нейросети в проекте (из каталога laozhang.ai)

### D.1 Важно: НЕ плодим поле — заменяем существующее

В `StudioProject` **уже есть** поле `coder_model` с двумя значениями (`fast`→DeepSeek V3, `smart`→Opus 4.8). База агентов (`base.py`) хардкодит `MODEL_FAST='deepseek-v3'`, `MODEL_SMART='claude-opus-4-8'`, а биллинг (`billing.py`) знает только два тарифа `STAR_RATE={'smart':3,'fast':1}` и `coder_tier_for_model()`.

Бриф предлагал «добавить поле `ai_model`». Делать это **рядом** с `coder_model` — дубль и источник рассинхрона. Решение: **новое поле `ai_model` ЗАМЕНЯЕТ `coder_model`** (миграция переносит данные и удаляет старое поле). Так мы держим один источник истины.

### D.2 Отобранные 15 моделей для генерации кода

Исключены видео/изображения/embeddings и заведомо неподходящие для кодинга. `model_name` — точные ID laozhang.ai (заметь: в каталоге `deepseek-v3.2`, а не `deepseek-v3` из `base.py` — при миграции исправляем).

| # | model_name | Категория | Описание | Тариф | Звёзд/шаг* |
|---|-----------|-----------|----------|-------|------------|
| 1 | `claude-sonnet-4-6` | Smart | Баланс качества и скорости, лучший по умолчанию для кода | smart | ~36 |
| 2 | `claude-opus-4-8` | Smart | Максимальное качество, сложная архитектура, дорого/медленно | smart | ~36 |
| 3 | `claude-haiku-4-5-20251001` | Fast | Быстрый Claude для простых шагов | fast | ~12 |
| 4 | `gpt-5` | Smart | Топовый GPT, сильная логика и рефакторинг | smart | ~36 |
| 5 | `gpt-5-mini` | Fast | Дешёвый GPT-5 для рутинных шагов | fast | ~12 |
| 6 | `gpt-4.1` | Smart | Надёжный генералист по коду | smart | ~36 |
| 7 | `gpt-4.1-mini` | Fast | Быстрый и дешёвый генералист | fast | ~12 |
| 8 | `gpt-4o` | Fast | Быстрый мультимодальный, ок для UI-кода | fast | ~12 |
| 9 | `deepseek-v3.2` | Fast | Сильный код за низкую цену — наш текущий «fast» | fast | ~12 |
| 10 | `deepseek-v4-pro` | Smart | Старшая DeepSeek, качество ближе к топу за меньшую цену | smart | ~36 |
| 11 | `deepseek-r1` | Reasoning | Пошаговые рассуждения, сложная логика/алгоритмы | smart | ~36 |
| 12 | `qwen3-coder-plus` | Coder | Специализирован на коде, отличный для генерации файлов | coder | ~20 |
| 13 | `qwen3-235b-a22b` | Smart | Крупная Qwen, сильный генералист | smart | ~36 |
| 14 | `kimi-k2` | Coder | Сильна в кодовых задачах и длинном контексте | coder | ~20 |
| 15 | `gemini-2.5-pro` | Smart | Длинный контекст, хороша для больших проектов | smart | ~36 |

\* «Звёзд/шаг» — оценка для одного прогона CoderAgent: `(AGENT_BUDGET['coder']=12000 ток / 1000) × STAR_RATE[tier]`. То есть fast: 12·1=12, coder: 12·~1.7≈20, smart/reasoning: 12·3=36. **Числа выводятся из биллинга, не выдуманы** (раздел D.5 расширяет `STAR_RATE`).

Дополнительные быстрые опции, доступные не как «модель проекта», а как fallback: `gemini-2.5-flash`, `o3-mini` (reasoning-lite), `grok-4` (smart). Их можно включить в список позже — каталог хранится в одном месте (D.3).

### D.3 Модель по умолчанию и рекомендации

- **По умолчанию: `claude-sonnet-4-6`** (Smart) — лучший баланс «качество кода / скорость / цена» для типового проекта. (Меняем дефолт с прежнего «fast/DeepSeek», т.к. для незнакомого с кодом пользователя предсказуемость качества важнее экономии.)
- **Простой лендинг/HTML:** `deepseek-v3.2` или `gpt-4.1-mini` (Fast) — дёшево и достаточно.
- **Сложное приложение (auth, БД, интеграции):** `claude-sonnet-4-6` или `gpt-5` (Smart).
- **Алгоритмически тяжёлое (расчёты, парсеры):** `deepseek-r1` (Reasoning).
- **Много файлов/большой контекст:** `gemini-2.5-pro` или `kimi-k2`.
- **Экономный режим максимум:** `claude-haiku-4-5` / `gpt-5-mini`.

Каталог моделей выносим в один источник — `src/studio/models_catalog.py`:
```python
STUDIO_MODELS = [
    {'id': 'claude-sonnet-4-6', 'label': 'Claude Sonnet 4.6', 'category': 'smart', 'tier': 'smart'},
    {'id': 'deepseek-v3.2',     'label': 'DeepSeek V3.2',     'category': 'fast',  'tier': 'fast'},
    {'id': 'qwen3-coder-plus',  'label': 'Qwen3 Coder Plus',  'category': 'coder', 'tier': 'coder'},
    {'id': 'deepseek-r1',       'label': 'DeepSeek R1',       'category': 'reasoning', 'tier': 'smart'},
    # ... все 15
]
DEFAULT_STUDIO_MODEL = 'claude-sonnet-4-6'
```

### D.4 Backend-реализация

- Поле на `StudioProject`: `ai_model = CharField(max_length=40, default='claude-sonnet-4-6')` — **заменяет** `coder_model`.
- `BaseAgent` читает модель из проекта: убрать хардкод констант как «истину», ввести `BaseAgent.resolve_model(self)`:
  - Для CoderAgent — `project.ai_model`.
  - Для остальных агентов оставить разумные дефолты, но допускать общий проектный выбор (например analyst/planner — тот же `ai_model`, tester/interviewer могут оставаться на дешёвой модели для экономии; решаем на уровне `AGENT_MODEL_POLICY`).
- `coder._pick_model()`: **остаётся как эскалация ВНУТРИ выбора пользователя.** Логика: базовая модель = `project.ai_model`; если шаг помечен `[COMPLEX]` И пользовательская модель относится к tier `fast` → разово эскалировать до парной `smart`-модели того же вендора (например `deepseek-v3.2`→`deepseek-v4-pro`, `gpt-4.1-mini`→`gpt-4.1`). Если пользователь уже выбрал smart/reasoning/coder — `_pick_model` не понижает и не меняет. Это сохраняет автоэскалацию, но уважает явный выбор.
- `billing.coder_tier_for_model()`: переписать на таблицу `MODEL_TIER` из `models_catalog.py` (не сравнение с единственным `MODEL_SMART`).

### D.5 Расширение биллинга (новые тарифы)

```python
# src/studio/billing.py
STAR_RATE = {'fast': 1, 'coder': 1.7, 'smart': 3}   # добавлен 'coder'; reasoning маппится на 'smart'
```
`MODEL_TIER = {m['id']: m['tier'] for m in STUDIO_MODELS}` — единый маппинг. `coder_tier_for_model(model)` → `MODEL_TIER.get(model, 'fast')`. `estimate_stars` использует тот же tier-маппинг для предоплаты, чтобы оценка совпадала с фактом.

### D.6 Frontend-реализация

- В форме создания (`frontend/app/studio/page.tsx`) — `<select>` модели, **сгруппированный** через `<optgroup>`: Smart / Fast / Coder / Reasoning.
- Рядом — оценка стоимости: «≈ N звёзд за шаг» (берём `tier`→`STAR_RATE`→`×12`), и «≈ N звёзд за весь проект» (× planned_steps, как в `estimate_stars`).
- Подсказки-tooltips из `description` каждой модели.
- Каталог отдаётся новым эндпоинтом `GET /api/.../studio/models` (читает `models_catalog.STUDIO_MODELS`), чтобы фронт не дублировал список.

### D.7 Задачи по коммитам — выбор модели

- [ ] **Коммит D-1. Каталог моделей + замена поля.** `src/studio/models_catalog.py`; миграция: добавить `ai_model`, перенести `coder_model` (`fast`→`deepseek-v3.2`, `smart`→`claude-opus-4-8`), удалить `coder_model`. Файлы: `src/studio/models_catalog.py`, `src/studio/models.py`, `src/studio/migrations/00XX_ai_model.py`.
- [ ] **Коммит D-2. Резолвинг модели в агентах.** `BaseAgent.resolve_model`, `coder._pick_model` уважает явный выбор + эскалация по вендору; `MODEL_TIER` в биллинге, расширенный `STAR_RATE`. Файлы: `src/studio/agents/base.py`, `src/studio/agents/coder.py`, `src/studio/billing.py`.
- [ ] **Коммит D-3. Эндпоинт каталога моделей.** `GET studio/models` → `STUDIO_MODELS`. Файлы: `src/studio/views/projects.py` (или новый view), `src/studio/urls.py`, `src/studio/serializers.py`.
- [ ] **Коммит D-4. UI выбора модели + оценка стоимости.** `<select>` с `<optgroup>`, расчёт звёзд. Файлы: `frontend/app/studio/page.tsx`, `frontend/lib/api/studio.ts`.

---

## E. Маркетинговая миссия Studio

Мы строим Studio не «ещё один генератор сайтов», а лучший русскоязычный сервис вайбкодинга — для людей, которые знают, *что* хотят построить, но не обязаны знать *как*. Российский рынок сегодня поставлен перед ложным выбором: либо платить за зарубежные bolt.new/lovable через VPN и иностранную карту, либо мириться с примитивными конструкторами. Мы закрываем этот разрыв: мощь агентного пайплайна, оплата в рублях, интерфейс и поддержка на русском, без VPN. Это не «локализация чужого продукта» — это собственный стек (агенты, sandbox, биллинг, краулер), который мы развиваем под наш рынок.

Стандарт качества мы держим по верхней планке индустрии — не ниже bolt.new и lovable. Это значит: сгенерированный код должен собираться и запускаться, превью — открываться, а не показывать пустой экран; план проекта — быть выполнимым, а не красивым списком желаний. Каждый из семи агентов в пайплайне существует ради этой планки: аналитик превращает идею в спецификацию, планировщик — в атомарные шаги, кодер пишет production-ready код, ревьюер и тестер ловят ошибки до того, как их увидит пользователь, фиксер их чинит. Если что-то из этой цепочки работает «на тройку» — продукт работает на тройку. Поэтому мы постоянно проводим честный gap-анализ: где мы реально отстаём от лучших, а не где нам приятно думать, что мы хороши.

«Топ-1 в России» для нас — не «быть вторыми по отношению к западным конкурентам». Это конкретная операционная дисциплина: закрывать дыры быстрее, чем их находят пользователи; релизить чаще, чем кто-либо на нашем рынке; слушать обратную связь внимательнее, чем это делает кто-то, у кого мы лишь один из тридцати языков локализации. Мы ближе к своему пользователю — и это наше неустранимое преимущество перед глобальными игроками, для которых русский рынок второстепенен.

Главный принцип разработки — no lazy shortcuts. Каждая функция делается правильно с первого раза — или не делается вовсе. Краулер, который собирает URL ресурсов и выбрасывает их, называя это «копированием», — это shortcut, и мы его не принимаем (см. раздел A). Второе поле `ai_model` рядом с уже существующим `coder_model`, делающее ту же работу, — shortcut, и мы вместо этого мигрируем по-честному (см. раздел D). Защита от зацикливания, которая считает только итерации, но не замечает, что код не меняется, — shortcut (см. раздел C). Мы предпочитаем сделать меньше функций, но каждую — до конца и надёжно.

Путь к топ-1 — итеративный и честный. Мы не объявляем победу по факту наличия функции в коде; мы проверяем, работает ли она для живого пользователя на живом проекте. Мы измеряем, собираем фидбек, признаём разрывы и закрываем их по приоритету. Эта дисциплина — не разовый спринт, а постоянная практика команды. Именно она, а не отдельная «киллер-фича», выведет Studio в топ-1 русскоязычного вайбкодинга.

---

## F. Онбординг-страница Studio (`/studio/`)

Страница существует (`frontend/app/studio/page.tsx`), но это сразу форма создания. Нужно добавить объясняющий слой для не-кодера — **хирургически, не ломая существующую логику** (форма, табы, список проектов остаются).

### F.1 Hero-секция

- Заголовок: «Создайте сайт или приложение, просто описав идею».
- Подзаголовок: «Studio — это команда AI-агентов, которые проектируют, пишут и проверяют код за вас. Без знания программирования. Без VPN. Оплата в рублях.»
- «Как это работает за 3 шага» (иконки Lucide):
  1. `MessageSquare` — «Опишите идею или дайте ссылку на сайт-образец».
  2. `Cpu` — «Агенты составляют план и пишут код, вы видите прогресс по шагам».
  3. `Eye` — «Смотрите живое превью, правьте и публикуйте».
- CTA «Создать проект» (раскрывает существующую форму — текущее поведение `setShowForm`).

### F.2 Описание стеков с преимуществами

Блок-карточки (иконки Lucide, без эмодзи), показываются над/рядом с выбором стека:

| Стек | Иконка | Подходит для | Плюсы | Когда выбирать |
|------|--------|--------------|-------|----------------|
| **HTML** | `FileCode` | Лендинги, промо, визитки | Мгновенное превью, не нужен Node.js, максимальная совместимость | Простые страницы без реактивности |
| **React** | `Atom` | Интерактивные SPA, дашборды, формы | Богатые UI-компоненты, hooks, экосистема | Нужна интерактивность без SSR |
| **Vue** | `Layers` | Средние SPA | Проще синтаксис, плавная кривая обучения | Быстрый старт |
| **Next.js** | `Boxes` | Полноценные приложения, SSR/SSG, API routes | SEO из коробки, file-based routing, деплой на Vercel | Полноценный продукт с бэкендом |

> Примечание о превью (см. раздел H): HTML отдаётся мгновенно из БД (`PreviewProxyView` fallback), React/Vue/Next.js требуют запуска dev-сервера в sandbox (дольше). Об этом честно предупреждаем в карточке стека — пользователь не будет думать, что «зависло».

### F.3 Режимы работы (объяснение для не-кодера)

Расширить существующий `MODE_OPTIONS` (сейчас короткие `hint`) до карточек с понятным текстом:

| Режим | Иконка | Текст для пользователя |
|-------|--------|------------------------|
| Auto | `Zap` | «Агенты делают всё сами — вы только описываете, что нужно. Самый быстрый путь к результату.» |
| Semi | `StepForward` | «Подтверждаете каждый шаг — видите, что происходит, и можете остановиться в любой момент.» |
| Manual | `Hand` | «Полный контроль: одобряете каждый файл перед записью. Для тех, кто хочет вникать.» |

> Соответствует фактической логике: в `commit_to_gitea` режимы `semi`/`manual` ставят `paused_manual` после каждого шага.

### F.4 Задачи по коммитам — онбординг

- [ ] **Коммит F-1. Hero-блок.** Компонент `frontend/components/studio/StudioHero.tsx`, вставить над формой в `page.tsx` (показывать, когда форма скрыта). Файлы: `frontend/components/studio/StudioHero.tsx`, `frontend/app/studio/page.tsx`.
- [ ] **Коммит F-2. Карточки стеков.** Компонент `StackCards.tsx`, рендерится внутри формы рядом с `<select>` стека; клик по карточке = выбор стека. Файлы: `frontend/components/studio/StackCards.tsx`, `frontend/app/studio/page.tsx`.
- [ ] **Коммит F-3. Режимы-карточки.** Заменить кнопки режима на карточки с расширенным текстом (данные из обновлённого `MODE_OPTIONS`). Файл: `frontend/app/studio/page.tsx`.

---

## G. Интерактивный выбор фич вместо шаблонов

### G.1 Проблема

`TemplateGallery` (есть, шаблоны из БД через `seed_templates`) заставляет пользователя выбрать «ближайший» шаблон и описывать дельту словами. Лучше — checkbox-набор «что должно быть в проекте»: пользователь конструирует ТЗ кликами, а не угадывает шаблон.

### G.2 Список фич (checkbox по категориям)

| Категория | Фичи |
|-----------|------|
| Навигация | Header с меню, Footer, Breadcrumbs, Sidebar |
| Контент | Hero-секция, Галерея/карточки, Блог/статьи, FAQ-раздел, Отзывы |
| Формы | Форма обратной связи, Форма записи/бронирования, Форма заказа, Квиз |
| E-commerce | Корзина, Каталог товаров, Карточка товара, Чекаут |
| Авторизация | Регистрация/вход, Личный кабинет, Профиль |
| Дополнительно | Тёмная тема, Анимации, Адаптив мобильный, Мультиязычность, Поиск по странице |
| Интеграции | Яндекс.Карты, Telegram-кнопка, WhatsApp-кнопка, Instagram-ссылки |

Каждая фича = `{id, label, category}`; источник — `frontend/lib/studio/features.ts` (или эндпоинт, по аналогии с каталогом моделей).

### G.3 Как фичи превращаются в промт агентов

- Выбранные `selected_features: string[]` сохраняются в `interview_data['features']`.
- AnalystAgent получает их как явные функциональные требования.
- PlannerAgent получает блок «MUST-HAVE компоненты» и обязан включить для каждой фичи хотя бы один шаг.
- CoderAgent получает список обязательных компонентов в контексте шага.

**Пример конвертации** (добавляется в user-сообщение планировщика):
```
Выбранные пользователем функции (обязательны к реализации):
- Навигация: Header с меню, Footer
- Контент: Hero-секция, Галерея/карточки, FAQ-раздел
- Формы: Форма обратной связи
- Интеграции: Telegram-кнопка
- Дополнительно: Тёмная тема, Адаптив мобильный

Каждая функция должна быть покрыта минимум одним шагом COMMITS.md.
```

### G.4 Задачи по коммитам — фичи

- [ ] **Коммит G-1. Компонент FeatureSelector.** `frontend/components/studio/FeatureSelector.tsx` — категории + чекбоксы (иконки Lucide для категорий), управляемое состояние `selected: string[]`. Заменяет `TemplateGallery` в форме «С нуля» (галерею можно оставить ниже как «или начните с шаблона»). Файлы: `frontend/components/studio/FeatureSelector.tsx`, `frontend/app/studio/page.tsx`, `frontend/lib/studio/features.ts`.
- [ ] **Коммит G-2. API create принимает features.** Сериализатор/вью `create` сохраняет `selected_features` в `interview_data['features']`. Файлы: `src/studio/views/projects.py`, `src/studio/serializers.py`, `frontend/lib/api/studio.ts`.
- [ ] **Коммит G-3. Промты Analyst/Planner учитывают features.** В `analyst.run`/`planner.run` подмешивать блок features в user-сообщение (формат из G.3). Файлы: `src/studio/agents/analyst.py`, `src/studio/agents/planner.py`.
- [ ] **Коммит G-4. Интеграция в page.tsx.** Подключить FeatureSelector в форму, прокинуть `selected_features` в `createMutation`. Файл: `frontend/app/studio/page.tsx`.

---

## H. Аудит стеков — реальные баги превью

Основано на фактическом коде `src/studio/sandbox.py`, `src/studio/tasks.py`, `src/studio/views/pipeline.py` (`PreviewProxyView`).

### H.1 HTML-стек

**Bug H-1. Файлы только в БД → 404 в sandbox.**
- *Что:* `start_dev_server` для статики поднимает `python3 -m http.server` в `/workspace`. Файлы кладутся туда через `sandbox.write_files` в `run_pipeline`/`coder_iteration`. Если какой-то `StudioFile` создан, но **не записан** в sandbox (например, ресурс из краулера — раздел A — или файл, добавленный вне `write_files`), HTTP-сервер вернёт 404. `PreviewProxyView` пытается проксировать в контейнер, и при провале (`except`) падает в fallback — отдачу из БД по точному `path`. То есть для пользователя всё может работать через fallback, но НЕ через реальный sandbox-сервер — рассинхрон.
- *Статус:* **Ухудшает UX** (для краулинг-клонов может стать Блокером).
- *Фикс:* гарантировать, что **все** `StudioFile` проекта пишутся в sandbox: централизовать «полную синхронизацию» (helper `sandbox.sync_all(project)`), вызывать после краулинга и при `restart_preview`. Не полагаться на то, что фоллбэк скроет дыру.
- *Где:* `src/studio/sandbox.py`, `src/studio/tasks.py`.

**Bug H-2. Относительные URL ломаются при проксировании.**
- *Что:* превью открывается по `/api/.../projects/{id}/preview/`, файлы отдаются по `preview/{path}`. Относительные ссылки в HTML (`./style.css`, `assets/app.js`) резолвятся браузером относительно URL страницы превью — это может не совпасть с тем, что `PreviewProxyView` ищет (`serve_path = path.strip('/') or 'index.html'`, точное совпадение по `StudioFile.path`). Вложенные пути (`pages/about.html` → `../assets/x.css`) особенно хрупки.
- *Статус:* **Ухудшает UX.**
- *Фикс:* инжектировать `<base href="/api/.../preview/">` в отдаваемый HTML (fallback-ветка `PreviewProxyView`), либо нормализовать пути ресурсов на относительные-от-корня (`/assets/...`) на этапе краулинга/генерации.
- *Где:* `src/studio/views/pipeline.py` (`PreviewProxyView.get`), краулер (раздел A.3 normalize).

### H.2 React/Vue-стек

**Bug R-1. Холодный `pnpm install` 2-7 минут — кажется, что зависло.**
- *Что:* `install_deps` (`pnpm install`) выполняется синхронно в `run_pipeline`/`_ensure_sandbox` без промежуточных событий. Пользователь видит «Запускаю sandbox...» и тишину.
- *Статус:* **Ухудшает UX.**
- *Фикс:* публиковать SSE-события прогресса до/после `install_deps` («Устанавливаю зависимости (может занять пару минут)...»); рассмотреть прогрев кэша pnpm в образе `aineron-sandbox` (предустановить частые пакеты Next/React/Vue в store). Таймлайн (раздел C.4) показывает таймер.
- *Где:* `src/studio/tasks.py` (`run_pipeline`, `_ensure_sandbox`), `Dockerfile` образа sandbox.

**Bug R-2. Vite биндит на localhost, не на 0.0.0.0 → превью недоступно.**
- *Что:* `start_dev_server` для проектов с `dev`-скриптом запускает `pnpm dev --port 3000 --host 0.0.0.0`. Но если сгенерированный `vite.config.ts` переопределяет host или скрипт `dev` не пробрасывает `--host`, Vite слушает localhost внутри контейнера, и `PreviewProxyView`-проксирование к `http://{container}:3000/` не достучится.
- *Статус:* **Блокер** для Vite-стеков (React/Vue через Vite).
- *Фикс:* CoderAgent обязан генерировать `vite.config.ts` с `server: { host: true, port: 3000 }` (уже добавлено в промт кодера, раздел B.5). Подстраховка: `start_dev_server` для Vite добавляет `--host 0.0.0.0` явно (уже передаётся, но убедиться, что не перетирается конфигом).
- *Где:* `src/studio/agents/coder.py` (промт), `src/studio/sandbox.py`.

**Bug R-3. HMR через WebSocket не работает сквозь PreviewProxyView.**
- *Что:* `PreviewProxyView` — обычный HTTP-проброс (`requests.get`), WebSocket не проксируется. Vite/Next HMR-сокет не подключается → нет горячей перезагрузки, в консоли ошибки подключения WS.
- *Статус:* **Ухудшает UX** (не блокер — превью работает, просто без live-reload).
- *Фикс:* короткий путь — отключить HMR в dev-конфиге для sandbox (`server.hmr: false`), чтобы не сыпались ошибки WS, и перезагружать iframe вручную после каждого шага (мы и так пере-рендерим превью по событию). Длинный путь — поднять WS-проксирование через nginx/Channels.
- *Где:* `src/studio/agents/coder.py` (генерация конфига), `frontend` (перезагрузка iframe по SSE-событию), опц. `nginx.conf`.

### H.3 Next.js-стек

**Bug N-1. `pnpm dev` Next.js 14 — порт/host корректны, но нужны доп. условия.**
- *Что:* `start_dev_server` запускает `pnpm dev --port 3000 --host 0.0.0.0`. Для Next.js 14 это работает, но `next dev` игнорирует `--host` в части версий (нужен `-H 0.0.0.0`), а первая компиляция страницы ленивая — `wait_for_ready` (timeout 60-90с) может истечь до первого ответа на тяжёлом проекте.
- *Статус:* **Ухудшает UX** (иногда Блокер по таймауту).
- *Фикс:* для Next генерировать `dev`-скрипт как `next dev -p 3000 -H 0.0.0.0`; поднять `wait_for_ready` timeout для Next и делать «прогревочный» запрос на `/` для триггера компиляции.
- *Где:* `src/studio/agents/coder.py` (package.json scripts), `src/studio/sandbox.py` (`start_dev_server`/`wait_for_ready`).

**Bug N-2. Next.js API routes `/api/*` конфликтуют с nginx `/api/ → Django`.**
- *Что:* в проде nginx роутит `/api/ → Django`. Но превью Studio-проекта проксируется через `PreviewProxyView` по пути `/api/.../preview/{path}`, и сам сгенерированный Next.js использует свои `/api/*` маршруты **внутри** контейнера (порт 3000) — наружу они не выставляются напрямую, только через прокси превью, так что прямого конфликта на проде нет. Риск — если пользователь предполагает, что его `/api/*` доступен по внешнему URL aineron.ru.
- *Статус:* **Косметический/архитектурный** (документировать), потенциально Блокер при экспорте на свой домен.
- *Фикс:* API-маршруты Next работают внутри sandbox/после деплоя на Vercel (`deploy_to_vercel` уже ставит `framework: nextjs`). В превью — всё идёт через `PreviewProxyView`, конфликта нет. Зафиксировать это в доке и в карточке стека Next.js: «API routes работают в превью и после публикации на Vercel».
- *Где:* документация, `frontend/components/studio/StackCards.tsx` (примечание).

**Bug N-3. Next.js build падает на TS-ошибках агента.**
- *Что:* `run_build_check` гоняет `tsc --noEmit || pnpm build`. Если CoderAgent сгенерировал код с TS-ошибками, `agent_test` вернёт `passed=false`, пойдут итерации фиксера — это правильно. Но при деплое (`deploy_to_vercel`) Vercel сам соберёт проект, и если TS-ошибки остались (например, build-check проходил по `tsc`, а Next-build строже) — деплой упадёт молча.
- *Статус:* **Ухудшает UX** (на этапе публикации).
- *Фикс:* перед `deploy_to_vercel` прогонять полноценный `next build` в sandbox (а не только `tsc --noEmit`); при провале — не деплоить, а вернуть пользователя в пайплайн с понятной ошибкой. Опционально — в `next.config` для генерируемых проектов НЕ ставить `ignoreBuildErrors` (чтобы ошибки не маскировались).
- *Где:* `src/studio/sandbox.py` (`run_build_check` для Next — гонять `next build`), `src/studio/tasks.py` (`deploy_to_vercel` — предварительный build-gate).

### H.4 Задачи по коммитам — баги превью

- [ ] **Коммит H-1. Полная синхронизация файлов в sandbox.** `sandbox.sync_all(project)`; вызвать после краулинга и в `restart_preview`. Файлы: `src/studio/sandbox.py`, `src/studio/tasks.py`.
- [ ] **Коммит H-2. `<base href>` для статического превью.** Инжект в fallback-ветке `PreviewProxyView`. Файл: `src/studio/views/pipeline.py`.
- [ ] **Коммит H-3. Прогресс установки зависимостей + прогрев образа.** SSE-события вокруг `install_deps`; предустановка частых пакетов в `aineron-sandbox`. Файлы: `src/studio/tasks.py`, `Dockerfile` (sandbox-образ).
- [ ] **Коммит H-4. Vite/Next host и dev-скрипты.** Промт кодера + подстраховка в `start_dev_server`; для Next — `-H 0.0.0.0`, увеличенный `wait_for_ready`, прогревочный запрос. Файлы: `src/studio/agents/coder.py`, `src/studio/sandbox.py`.
- [ ] **Коммит H-5. HMR без ошибок.** Отключить WS-HMR в dev-конфиге sandbox, перезагрузка iframe по SSE. Файлы: `src/studio/agents/coder.py`, `frontend/components/studio/*` (превью).
- [ ] **Коммит H-6. Build-gate перед деплоем.** `next build` в `run_build_check` для Next; предварительный build-gate в `deploy_to_vercel`. Файлы: `src/studio/sandbox.py`, `src/studio/tasks.py`.

Тексты кнопок — короткие глаголы без спецсимволов: «Подключить», «Опубликовать», «Поделиться», «Создать из шаблона».
