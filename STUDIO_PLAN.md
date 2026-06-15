# Vibe-Coding Studio — Полный план развития

**Цель:** Топ-3 в России, конкурентоспособность с Lovable, Bolt.new, Replit Agent (США/ЕС)  
**Дата аудита:** 2026-06-16  
**Стек:** Django 4.2 + Celery/gevent + Docker sandbox + Next.js 14 App Router

---

## Часть I — Что уже реализовано

### Бэкенд (`src/studio/`)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Модели (5 шт.) | ГОТОВО | `StudioProject`, `StudioFile`, `StudioPipelineState`, `StudioVersion`, `StudioTemplate` |
| Агент-интервьюер (0) | ГОТОВО | DeepSeek V3, 3-5 вопросов в JSON, сохраняет в `interview_data` |
| Агент-аналитик (1) | ГОТОВО | Opus 4.8, пишет `PROJECT.md` из описания + ответов интервью |
| Агент-плановик (2) | ГОТОВО | Opus 4.8, пишет `COMMITS.md`, извлекает `<STEPS_COUNT>` |
| Агент-кодер (3) | ГОТОВО | DeepSeek V3, реализует один шаг, возвращает `{path: content}` |
| Агент-ревьювер (4) | ГОТОВО | Opus 4.8, статический анализ кода → `ReviewReport {passed, issues[], summary}` |
| Агент-тестер (5) | ГОТОВО | DeepSeek V3, анализирует `dev.log` → `TestReport {passed, errors[], build_ok}` |
| Агент-фиксер (6) | ГОТОВО | Opus 4.8, объединяет ревью+тест → `FixPlan {instructions, target_files, priority}` |
| Celery chord pipeline | ГОТОВО | `run_pipeline → start_step → coder_iteration → chord(review+test) → merge_reports` |
| Self-heal loop | ГОТОВО | До `STUDIO_MAX_ITERATIONS` итераций на шаг, потом пауза |
| Docker sandbox | ГОТОВО | `spawn_sandbox` → `write_files` → `install_deps` → `isolate` → `start_dev_server` |
| SSE события | ГОТОВО | Redis pubsub → `StreamingHttpResponse`, X-Accel-Buffering |
| Gitea интеграция | ГОТОВО | per-file PUT через Gitea Contents API, `StudioVersion` на каждый шаг |
| Билинг агентов | ГОТОВО | `_billing_charge` per-agent, `_billing_charge` в `merge_reports` (без race condition) |
| Клон по URL | ГОТОВО | `crawl_and_analyze`, `is_safe_url` SSRF-guard, статический crawl |
| Шаблоны | ГОТОВО | 4 шаблона (Landing/CRUD/Chat/Portfolio), `seed_templates` команда |
| API endpoints | ГОТОВО | 14 эндпоинтов `/api/v1/studio/`, DRF, session auth |
| Атомарные guards | ГОТОВО | `filter(status='draft').update()` — только один запрос триггерит задачу |
| Идемпотентность | ГОТОВО | PipelineRunView atomic guard, run_pipeline статус-проверка |

### Фронтенд (`frontend/app/studio/`, `frontend/components/studio/`)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Страница списка проектов | ГОТОВО | Табы "С нуля"/"Клон", форма создания, `TemplateGallery` |
| Страница интервью | ГОТОВО | Polling 3s, авто-старт агента, retry на ошибке |
| Страница ревью | ГОТОВО | `PROJECT.md`/`COMMITS.md` viewer+editor (PATCH), старт кодинга |
| Workspace (main) | ГОТОВО | 3-панельный desktop layout, мобильные табы |
| FileTree | ГОТОВО | Вложенные папки, file-type иконки, collapsible |
| CodeViewer | ГОТОВО | Read-only code display, copy button |
| AgentLog (SSE) | ГОТОВО | EventSource, color-coded по level |
| PipelineStatus | ГОТОВО | 7-точечный прогресс (interviewer→fixer) |
| PreviewPanel | ГОТОВО | iframe `/studio/preview/{containerId}/`, refresh+open-tab |
| GitHistory | ГОТОВО | Список версий, rollback с confirm |
| ContextChat | ГОТОВО | Панель паузы: причина, подсказка, resume-кнопки |
| BillingEstimate | ГОТОВО | Баннер потраченных звёзд, ссылка на репо |
| InterviewCards | ГОТОВО | One-by-one wizard, progress bar, choice/text, валидация |
| DiffViewer | ГОТОВО (не подключён) | Компонент построен, но не используется |

---

## Часть II — Известные баги (приоритет: КРИТИЧНЫЙ → НИЗКИЙ)

### КРИТИЧНЫЕ (ломают работу прямо сейчас)

#### BUG-01: Статус `'interviewing'` vs `'interview'` — НЕСОВПАДЕНИЕ
**Файл:** `src/studio/models.py` строка 9, `frontend/app/studio/[id]/page.tsx`  
**Проблема:** Код везде пишет `status='interviewing'`, но в `STATUS_CHOICES` записано `'interview'`. Это ломает:
- `PipelineStatus.STATUS_TO_ACTIVE` — шаг Интервьюера никогда не светится
- `[id]/page.tsx` — редирект на `/interview` не срабатывает (проверяет `'interview'`, получает `'interviewing'`)
- Все `STATUS_LABEL` в UI  

**Исправление:** В `models.py` заменить `'interview'` → `'interviewing'` в `STATUS_CHOICES`.

#### BUG-02: Биллинг не останавливает пайплайн при нулевом балансе
**Файл:** `src/studio/tasks.py` → `_billing_charge()`  
**Проблема:** Когда у пользователя кончаются звёзды, `can_afford()` возвращает `False` и `_billing_charge()` просто возвращает `0` — но пайплайн **продолжает работать бесплатно**. Агенты Opus 4.8 генерируют тысячи токенов за счёт сервиса.  
**Исправление:** Если `not can_afford` — ставить паузу `paused_on_balance`, рефандить текущий шаг, отправлять SSE-уведомление.

#### BUG-03: `run_pipeline` без try/except вокруг Docker
**Файл:** `src/studio/tasks.py` → `run_pipeline()`  
**Проблема:** `spawn_sandbox()`, `install_deps()`, `isolate()`, `start_dev_server()` вызываются подряд без обработки ошибок. Любой сбой Docker оставляет проект в `status='coding'` навсегда — без SSE-ошибки, без рефанда.  
**Исправление:** Обернуть в `try/except`, на исключение: `_set_status(project, 'failed')`, рефанд, SSE `level='error'`.

#### BUG-04: Пауза не останавливает задачи Celery
**Файл:** `src/studio/views/pipeline.py` → `PipelinePauseView`  
**Проблема:** `PipelinePauseView` только меняет `PipelineState.status = 'paused_manual'`. Уже запущенный `chord(review, test) → merge_reports` продолжает работать и **списывает звёзды**.  
**Исправление:** Сохранять task_id в `PipelineState.current_task_id`, при паузе вызывать `celery.control.revoke(task_id, terminate=True)`.

### ВАЖНЫЕ (ухудшают работу)

#### BUG-05: Double-charge при retry агентов
**Файл:** `src/studio/tasks.py` → `agent_analyze`, `agent_plan`, `coder_iteration`  
**Проблема:** `_billing_charge()` вызывается ДО потенциально падающего кода. При retry (до 3 раз) звёзды списываются повторно.  
**Исправление:** Зарядка только после успешного сохранения результата. Или проверка `billing_log` на дубль по `(agent, step)`.

#### BUG-06: `_get_step_text` vs `planned_steps` — рассинхронизация
**Файл:** `src/studio/tasks.py`  
**Проблема:** `planned_steps` берётся из `<STEPS_COUNT>N</STEPS_COUNT>` в COMMITS.md, а `_get_step_text` разбивает тот же файл по `## / ###` заголовкам. Если их количество не совпадает — шаги пропускаются или контент повторяется.  
**Исправление:** Парсить `planned_steps` из реального количества заголовков при сохранении COMMITS.md в `agent_plan`.

#### BUG-07: AgentLog — нет реконнекта SSE
**Файл:** `frontend/components/studio/AgentLog.tsx`  
**Проблема:** `es.onerror = () => es.close()` — при потере соединения лог замирает навсегда. При монтировании из двух мест (drawer + ContextChat) — два Redis pubsub подключения.  
**Исправление:** Экспоненциальный retry reconnect, singleton через `useRef` или React Context.

#### BUG-08: Hardcoded `estimatedStars={50}` на Review-странице
**Файл:** `frontend/app/studio/[id]/review/page.tsx`  
**Проблема:** Пользователь видит "~50 звёзд" независимо от реального размера проекта.  
**Исправление:** Вызвать `billing.estimate_stars(project, planned_steps)` и вернуть через отдельный эндпоинт или в `pipeline` ответе.

#### BUG-09: `reap_stale_sandboxes` не зарегистрирован в Beat
**Файл:** `src/studio/tasks.py`, Django Admin (celery_beat)  
**Проблема:** Задача создана, но не добавлена в расписание — стейл-контейнеры копятся.  
**Исправление:** Добавить в `CELERY_BEAT_SCHEDULE` в `settings.py`.

#### BUG-10: Ручное редактирование файлов не пишет в sandbox/Gitea
**Файл:** `src/studio/views/files.py` → `FileDetailView.patch()`  
**Проблема:** PATCH обновляет `StudioFile.content` в БД, но не пушит в sandbox и не делает git-коммит.  
**Исправление:** В `FileDetailView.patch()` добавить `sandbox.write_files()` + Gitea API вызов.

### НИЗКИЕ (косметические / plan-vs-impl)

#### BUG-11: Preview broken для Next.js apps (path-based proxy)
`/_next/static/...` ассеты запрашиваются абсолютными путями — 404 через nginx proxy.

#### BUG-12: Синтаксическая подсветка в CodeViewer не работает
`className="language-X"` выставляется, но highlight.js / rehype не вызываются.

#### BUG-13: DiffViewer — мёртвый код
Компонент есть, но нигде не используется. Semi/Manual режим игнорируется.

#### BUG-14: `stars_reserved` всегда 0
Поле объявлено в модели, но логика резервации не реализована.

---

## Часть III — Критические исправления (Sprint Fix)

> Делать ДО новых фич. Это основа стабильности.

### Fix-1: Исправить статус `'interviewing'`

```python
# src/studio/models.py — STATUS_CHOICES
('interviewing', 'Интервью'),   # было 'interview'
```

### Fix-2: Биллинг-пауза при нулевом балансе

```python
# src/studio/tasks.py — _billing_charge()
def _billing_charge(project, agent_name: str, step_index: int):
    cost = _agent_cost(agent_name)
    user = project.user
    if not can_afford(user, cost):
        # Пауза вместо молчаливого пропуска
        project.status = 'paused'
        project.save(update_fields=['status'])
        state = project.pipeline
        state.status = 'paused_on_balance'
        state.pause_reason = f'Недостаточно звёзд для агента {agent_name}'
        state.save(update_fields=['status', 'pause_reason'])
        publish_event(str(project.id), {
            'agent': 'system', 'level': 'error',
            'text': f'Пауза: недостаточно звёзд (нужно {cost})',
            'type': 'paused',
        })
        return 0
    ...
```

### Fix-3: try/except вокруг Docker в `run_pipeline`

```python
@shared_task(queue=QUEUE)
def run_pipeline(project_id):
    project = StudioProject.objects.get(id=project_id)
    ...
    try:
        cid = sandbox.spawn_sandbox(project_id)
        sandbox.write_files(cid, initial_files)
        sandbox.install_deps(cid)
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
    except Exception as exc:
        _set_status(project, 'failed')
        project.pipeline.last_error = str(exc)
        project.pipeline.save(update_fields=['last_error'])
        publish_event(project_id, {'agent': 'system', 'level': 'error',
                                   'text': f'Sandbox error: {exc}'})
        return
    ...
```

### Fix-4: Зарегистрировать reap_stale_sandboxes в settings.py

```python
# src/config/settings.py
CELERY_BEAT_SCHEDULE = {
    ...
    'reap-stale-sandboxes': {
        'task': 'studio.tasks.reap_stale_sandboxes',
        'schedule': crontab(minute=0),  # каждый час
    },
}
```

### Fix-5: Двойное биллинг при retry — идемпотентность

```python
def _billing_charge(project, agent_name: str, step_index: int):
    log = project.interview_data.setdefault('billing_log', [])
    if any(e['agent'] == agent_name and e['step'] == step_index for e in log):
        return 0  # уже заряжено
    ...
```

---

## Часть IV — План развития (Sprints E-H)

### Sprint E — Стабильность и UX (2-3 недели)

**Цель:** Убрать все критические и важные баги, улучшить UX до уровня "работает без сюрпризов"

#### E1: Все Fix-1..Fix-5 из Части III

#### E2: Реальный биллинг-эстимейт на Review-странице
- Новый эндпоинт `GET /studio/projects/{id}/estimate/` → `{ estimated_stars, per_agent_breakdown }`
- Источник: `billing.estimate_stars(project, planned_steps)`
- Фронт: `BillingEstimate` берёт данные из API, не хардкод

#### E3: Pause реально останавливает задачи
- `StudioPipelineState` получает поле `current_task_id`
- `coder_iteration` сохраняет `self.request.id` в `state.current_task_id`
- `PipelinePauseView` вызывает `app.control.revoke(task_id, terminate=True, signal='SIGTERM')`

#### E4: AgentLog — reconnect + singleton
- Exponential backoff reconnect (1s → 2s → 4s → max 30s)
- Singleton через React Context → один EventSource на проект

#### E5: Синтаксическая подсветка в CodeViewer
- Подключить `highlight.js` (уже есть в проекте для chat Markdown)
- `detectLanguage(path)` по расширению файла
- Попутно: `StudioFile.language` заполнять в CoderAgent по extension

#### E6: DiffViewer — подключить в StudioLayout
- После каждой итерации кодера показывать diff текущий vs предыдущий
- `StudioFile` добавить поле `previous_content` (или сравнивать с `StudioVersion`)
- StudioLayout: правая панель переключается Code/Diff tabs

#### E7: Preview для Next.js — subdomain proxy
- Nginx: `sandbox-{cid}.aineron.ru` → `http://{cid}:3000`
- Docker sandbox подключается к bridge сети с известным именем
- `PreviewPanel`: строить URL как `https://sandbox-{cid}.aineron.ru/`
- Wildcard SSL через certbot или сертификат `*.aineron.ru`

#### E8: Ручные правки → sandbox + Gitea
- `FileDetailView.patch()`: после сохранения `StudioFile` вызывать `sandbox.write_files()` (если sandbox alive) и `gitea_client.put_file()`
- CodeViewer: сделать редактируемым (Monaco / CodeMirror) с auto-save debounce 1s

---

### Sprint F — Полнота функционала (3-4 недели)

**Цель:** Реализовать всё что в плане но не сделано

#### F1: ContextChat — реальный LLM-чат с контекстом
- Новый Celery endpoint `POST /studio/projects/{id}/chat/` 
- `ContextChatAgent`: Opus 4.8, получает `{message, context: {project_md, current_file, last_fix_plan, last_error}}`
- Streaming ответ через SSE (или polling)
- Фронт: полноценный чат-интерфейс внутри ContextChat (переиспользовать компонент из `/chat/`)

#### F2: SPA-клонирование через Playwright
- `crawl_and_analyze` → определять тип сайта по `Content-Type` / JS-фреймворку
- Если SPA → `crawl_spa.delay()` в `celery_studio_playwright` очередь
- `crawl_spa`: Playwright chromium headless, `page.goto()` → `page.content()`, screenshot для палитры
- Извлекать CSS palette (top-5 цветов), сохранять в `interview_data['palette']`
- AnalystAgent использует palette в PROJECT.md

#### F3: Semi/Manual режим (пошаговое одобрение)
- `StudioPipelineState.mode_override` — работает поверх project.mode
- После каждого шага кодера: если `mode == 'semi'` → пауза `paused_approval`, ждать `POST .../approve/`
- Фронт: кнопка "Одобрить и продолжить" / "Редактировать перед продолжением"

#### F4: Роутинг Кодер Opus 4.8 для сложных шагов
- В COMMITS.md плановик помечает шаги тегом `[complex]`
- `coder_iteration` парсит тег → выбирает `MODEL_SMART` вместо `MODEL_FAST`
- UI: сложные шаги показываются с иконкой и другим цветом

#### F5: Атомарные git-коммиты в Gitea
- Вместо per-file PUT использовать Gitea Tree API (batch)
- Один коммит на шаг с осмысленным message из COMMITS.md заголовка
- `StudioVersion.git_sha` = реальный SHA коммита

#### F6: Лимит одновременных sandbox per-user
- `can_spawn(user)` → `StudioProject.objects.filter(user=user, sandbox_container_id__isnull=False).count() < MAX_SANDBOXES`
- `MAX_SANDBOXES = 2` (настройка в settings)
- При превышении: 429-ответ с `retry_after`

#### F7: Резервирование звёзд при старте
- При `run_pipeline`: `user.reserve_pages(estimated_total)` — блокирует на балансе
- При завершении/паузе — списать реальное, остаток вернуть
- `stars_reserved` поле начинает использоваться

---

### Sprint G — Качество генерации (4-5 недель)

**Цель:** Сделать качество кода на уровне Lovable/Bolt.new

#### G1: Multi-file context для Кодера
- Убрать ограничение `[:10] files / [:2000] chars`
- Смарт-контекст: включать только файлы, связанные с текущим шагом (по `target_files` из FixPlan + импорт-граф)
- Для больших проектов: summarize через `gpt-4o-mini` (или deepseek) до 200 строк/файл

#### G2: Улучшенный Тестер — реальное выполнение тестов
- Перед `merge_reports`: если есть `*.test.*` или `*.spec.*` файлы → `exec_command(cid, 'pnpm test --run')`
- TesterAgent получает реальные результаты теста, а не только dev.log
- Playwright-тест для базового smoke: `page.goto('http://localhost:3000')` → 200, нет консольных ошибок

#### G3: Тестер — ждать завершения компиляции
- Перед запуском TesterAgent: polling `/tmp/dev.log` пока не появится "compiled" или "ready" (max 60s)
- `sandbox.wait_for_ready(cid, timeout=60)` — новая утилита

#### G4: Ревьювер — только diff текущего шага
- `ReviewerAgent.run()` получать `changed_files` (только файлы этого шага)
- Экономит токены, убирает false-positive замечания на старый код

#### G5: Улучшенный Плановик — валидация количества шагов
- После генерации COMMITS.md: парсить реальное число `## / ###` заголовков
- `planned_steps = len(sections)` — из реального контента, а не `<STEPS_COUNT>`
- Предупреждать если количество шагов > 15 (предложить разбить на под-проекты)

#### G6: Умный Фиксер — target_files в работе
- `coder_iteration`: если `pipeline.fix_plan['target_files']` непустой — Кодер видит только эти файлы + шаг
- Уменьшает context, ускоряет итерацию фикса

#### G7: Fine-tuned промпты
- A/B тестирование промптов (feature flag в SiteSettings)
- Собирать метрики: `passed_on_first_try`, `avg_iterations`, `total_stars_per_project`
- Логировать в `UserSpending` (уже есть) или новую таблицу `StudioMetrics`

---

### Sprint H — Продукт и рост (5-6 недель)

**Цель:** Фичи для роста, монетизации и удержания

#### H1: Публикация проекта (Deploy to Vercel/Netlify)
- Интеграция с Vercel API: `POST /v13/deployments` с файлами проекта
- Кнопка "Опубликовать" на финальном экране
- Отображение URL задеплоенного сайта в `BillingEstimate`
- Хранить `deployment_url` в `StudioProject`

#### H2: Совместная работа (Shared Projects)
- `StudioCollaborator` модель: project + user + role (view/edit)
- Invite по email
- Real-time presence через SSE (кто сейчас смотрит файл)

#### H3: Marketplace шаблонов
- Пользователи могут публиковать свои завершённые проекты как шаблоны
- Рейтинг, лайки, форки
- Монетизация: премиум-шаблоны за звёзды

#### H4: История чата с агентом
- Сохранять все сообщения ContextChat в `StudioChatMessage` (project, role, content, created_at)
- Показывать историю при возврате в проект
- Возможность "продолжить разговор" через несколько сессий

#### H5: Экспорт проекта
- ZIP всех файлов проекта (`/studio/projects/{id}/export/`)
- Экспорт в GitHub (через GitHub OAuth + API)
- Скачать как Docker Compose проект

#### H6: Мобильный UX
- Сейчас мобильные табы есть, но workspace не оптимизирован
- Адаптивный CodeViewer (font-size, горизонтальный скролл)
- Swipe-навигация между панелями
- Push-уведомления когда проект готов (PWA)

#### H7: Dashboard аналитики для пользователя
- `/account/studio/` — статистика Studio: проектов создано, звёзд потрачено, агентов запущено
- Графики по времени (аналогично `/account/analytics/`)
- Топ-агент по стоимости

#### H8: Тарифы для Studio
- Отдельный Studio-тариф с пулом звёзд на генерацию
- `StudioProject.max_stars_budget` — лимит на один проект
- Корпоративный план: shared sandbox pool, priority queue

---

## Часть V — Архитектурные улучшения

### A1: celery_studio pool — prefork вместо gevent

**Проблема:** `docker-compose.yml` запускает `celery_studio` с `--pool=gevent`, но Docker SDK (`docker-py`) использует синхронные сокеты, несовместимые с gevent.  
**Решение:** Отдельный воркер `celery_studio_docker` с `--pool=prefork --concurrency=4` только для задач Docker (run_pipeline, reap_stale_sandboxes).

```yaml
# docker-compose.yml
celery_studio_docker:
  command: celery -A config worker -Q studio_docker_queue --pool=prefork --concurrency=4
```

```python
# src/studio/tasks.py
DOCKER_QUEUE = 'studio_docker_queue'

@shared_task(queue=DOCKER_QUEUE)
def run_pipeline(project_id): ...

@shared_task(queue=DOCKER_QUEUE)
def reap_stale_sandboxes(): ...
```

### A2: Sandbox network — изолированная подсеть per-проект

**Сейчас:** Все sandbox-контейнеры в одной `sandbox_net` сети → потенциально могут общаться между собой.  
**Решение:** Создавать отдельную docker network `sbx-{project_id8}` для каждого проекта, удалять при `kill_sandbox`.

### A3: Sandbox с tmpfs для безопасности

```python
container = client.containers.run(
    ...
    tmpfs={'/tmp': 'size=100m,mode=1777'},
    read_only=True,  # root filesystem read-only
    volumes={...}    # только /workspace writable
)
```

### A4: SSE cleanup — закрывать Redis pubsub

**Сейчас:** `get_pipeline_events()` блокирует gunicorn worker на весь lifetime SSE соединения.  
**Решение:** 
- Перейти на `django-channels` + WebSocket ИЛИ
- Использовать `nginx_push_stream_module` для fan-out
- Или: SSE через отдельный `uvicorn` ASGI сервис

### A5: Мониторинг агентов — метрики

```python
# src/studio/metrics.py
from django.utils import timezone

class StudioMetrics:
    @classmethod
    def record_agent_run(cls, project, agent_name, duration_s, success, stars):
        StudioAgentRun.objects.create(
            project=project,
            agent=agent_name,
            duration_seconds=duration_s,
            success=success,
            stars_charged=stars,
        )
```

Дашборд в Django Admin: avg duration по агентам, pass rate ревьювера/тестера.

### A6: Очередь приоритетов

**Сейчас:** Все задачи в одной `studio_queue`.  
**Решение:** `studio_queue_fast` (interview, analyze, plan — быстрые) и `studio_queue_coding` (coder, review, test, fix — тяжёлые). Пользователи с платным тарифом → приоритет.

---

## Часть VI — Конкурентный анализ и позиционирование

| Фича | Lovable.dev | Bolt.new | Replit Agent | **aineron.ru Studio** |
|------|------------|----------|--------------|----------------------|
| Языки | React | React | Любой | Next.js/React/Vue/HTML |
| Self-heal loop | Да | Ограничено | Да | Да (max 3 iter/step) |
| Preview | iframe | iframe | Replit IDE | iframe (BUG: broken для Next.js) |
| Git интеграция | GitHub | GitHub | Replit Git | Gitea self-hosted |
| Цена | $25/мес | $20/мес | $25/мес | Звёзды (гибко) |
| Русский язык | Нет | Нет | Нет | ДА |
| VPN не нужен | Нет | Нет | Нет | ДА |
| Клон сайта | Нет | Нет | Нет | ДА (в разработке) |
| Mobile | Нет | Нет | Нет | Табы (базово) |

**Уникальные преимущества aineron.ru Studio:**
1. Русский язык и русская поддержка
2. Без VPN — все модели напрямую
3. Клонирование существующего сайта
4. Гибкая оплата звёздами (не подписка)
5. Self-hosted Gitea — данные пользователя в России

**Что нужно для топ-3 России:**
- Исправить критические баги (часть III)
- Рабочий preview (Sprint E7)
- Качество кода на уровне Lovable (Sprint G)
- Публикация в один клик (Sprint H1)

---

## Часть VII — Порядок выполнения (рекомендуемый)

```
Неделя 1-2:   Fix-1..Fix-5 (критические баги)
Неделя 3:     E2 (реальный estimate) + E3 (пауза останавливает таски) + E5 (подсветка)
Неделя 4:     E7 (preview subdomain) + E8 (ручное редактирование в sandbox)
Неделя 5-6:   F1 (ContextChat с LLM) + F2 (SPA клонирование)
Неделя 7-8:   G1 (multi-file context) + G2 (реальные тесты) + G3 (wait for compile)
Неделя 9-10:  G4-G7 (качество генерации)
Неделя 11-14: H1 (деплой) + H3 (marketplace) + H5 (экспорт)
Параллельно:  A1 (prefork pool) + A4 (SSE cleanup) — архитектура
```

---

## Часть VIII — Метрики успеха

| Метрика | Сейчас | Цель (3 мес) |
|---------|--------|-------------|
| Pass rate (первая итерация) | ~50% (оценка) | >75% |
| Avg звёзд/проект | ~200 (оценка) | <150 |
| Avg время до ready project | >10 мин | <5 мин |
| Preview работает | ~60% | >95% |
| Пользователей Studio/день | 0 (launch) | 50+ |
| Конверсия попробовал→купил | - | >30% |

---

*Документ обновлён: 2026-06-16. Следующий ревью: после Sprint E.*
