# STUDIO_UPGRADE_PLAN.md

**Документ:** План модернизации Vibe-Coding Studio (по результатам ручного тестирования + конкурентного анализа)
**Цель:** Сделать aineron.ru Studio платформой №1 для vibe-coding в России за 3 месяца
**Дата:** 2026-06-16
**Стек:** Django 4.2 + Celery/gevent + Docker sandbox + Next.js 14 App Router
**Отличие от `STUDIO_PLAN.md`:** тот документ — внутренний аудит бэкенда (BUG-01..14, Sprints E-H). Этот — driven скриншотом UI и конкурентами, с точными именами компонентов, label кнопок и эндпоинтами. Где пересекается — даю перекрёстную ссылку, не дублирую.

> **ВАЖНО про актуальность:** часть багов из старого `STUDIO_PLAN.md` уже исправлена в текущем коде. Я перепроверил против рабочих файлов. Ниже — только то, что реально сломано в коде на момент написания.

---

## РАЗДЕЛ 0: КРИТИЧЕСКИЕ БАГИ (исправить немедленно)

Это 10 багов, найденных при ручном тестировании. Каждый — с точным путём к файлу и описанием фикса. Для UX-багов фикс детализируется в Разделе 1, тут — корень проблемы.

### BUG-S0-01 — Preview всегда сломан на завершённых проектах (broken icon)

**Файлы:**
- `frontend/components/studio/PreviewPanel.tsx` (строки 11-24)
- `frontend/components/studio/StudioLayout.tsx` (строки 187, 208 — передача `hasSandbox`)
- `src/studio/views/pipeline.py` → `PreviewProxyView` (строки 168-188)
- `src/studio/tasks.py` → задача завершения пайплайна (там, где выставляется `status='completed'`)

**Корень:** `PreviewPanel` ветвится ТОЛЬКО на `hasSandbox={!!project.sandbox_container_id}` (StudioLayout, строка 187). После завершения проекта sandbox-контейнер убивается reap-логикой, НО поле `project.sandbox_container_id` **не очищается** в БД. Значит `hasSandbox` остаётся `true`, iframe грузит `${API_URL}/studio/projects/{id}/preview/`, а `PreviewProxyView` возвращает 502/503 (`if not project.sandbox_container_id` не срабатывает, контейнера уже нет) → broken file icon.

**Фикс (двойной):**
1. Бэкенд: при завершении пайплайна и в `reap_stale_sandboxes` после `kill_sandbox` — `project.sandbox_container_id = ''; project.save(update_fields=['sandbox_container_id'])`.
2. Фронт: передать `status={project.status}` в `PreviewPanel`. При `status === 'completed'` рендерить **completion-card** вместо iframe (детали — Раздел 1, пункт 1.3 и Раздел 4, пункт 4.3): «Проект завершён. Превью-сервер остановлен» + кнопки «Скачать ZIP», «Развернуть на Vercel», «Перезапустить превью».

### BUG-S0-02 — Нет навигации обратно на сайт (пользователь заперт)

**Файлы:**
- `frontend/components/studio/StudioLayout.tsx` (top bar, строки 77-111)
- `frontend/app/studio/[id]/layout.tsx`

**Корень:** В top bar StudioLayout нет ни одной ссылки на `/` или `/studio`. Пользователь не может выйти.

**Фикс:** В StudioLayout top bar, **слева, ПЕРЕД `<PipelineStatus>`** (вставка перед строкой 79), добавить:
```tsx
<Link href="/studio" className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors shrink-0">
  <ArrowLeft size={16} /> Проекты
</Link>
```
Импорт `ArrowLeft` из `lucide-react`, `Link` из `next/navigation`/`next/link`. Детали — Раздел 1, пункт 1.1.

### BUG-S0-03 — Редактор файла пуст по умолчанию («Выберите файл»)

**Файлы:**
- `frontend/components/studio/StudioLayout.tsx` (строка 25 — `selectedFileId` инициализируется `null`)
- `frontend/components/studio/CodeViewer.tsx` (строки 32-38 — заглушка «Выберите файл»)

**Корень:** `selectedFileId` стартует с `null`, нет `useEffect`, который выбрал бы первый осмысленный файл при загрузке `files`. Средняя панель пуста.

**Фикс:** В StudioLayout добавить `useEffect`, который при появлении `files` и `selectedFileId === null` авто-выбирает приоритетный файл (порядок приоритета: `index.html` → `app/page.tsx` → `src/App.tsx` → `README.md`/`COMMITS.md` → первый файл). Вызывать `handleFileSelect(fileId)`. Детали — Раздел 1, пункт 1.2.

### BUG-S0-04 — Pipeline status bar не кликабельный

**Файлы:**
- `frontend/components/studio/PipelineStatus.tsx` (весь файл — `div`, не `button`)

**Корень:** Каждый шаг рендерится как неинтерактивный `<div>` (строки 42-60). Нельзя посмотреть, что сгенерировал/завалил конкретный агент.

**Фикс:** Сделать каждый шаг `<button onClick={() => onStepClick(agent.key)}>`, поднять callback `onStepClick` в StudioLayout, который открывает **Step Detail Drawer** (новый компонент `StepDetailDrawer.tsx`) с: planned-текстом шага из `commits_md_content`, `review_report`, `test_report`, `fix_plan`, diff шага. Детали — Раздел 1, пункт 1.4; полная версия (Visual Step Timeline) — Раздел 3, пункт 3.1.

### BUG-S0-05 — Pause reason не сбрасывается после завершения

**Файлы:**
- `frontend/components/studio/StudioLayout.tsx` (строка 117 — `{pipeline.pause_reason || ...}`)
- `src/studio/tasks.py` (завершение пайплайна) и `src/studio/views/pipeline.py` → `ApproveStepView`/`PipelineResumeView`

**Корень:** При выставлении `pipeline.status='completed'` поле `pause_reason` остаётся со старым текстом. UI продолжает показывать баннер одобрения / старую причину.

**Фикс:** Бэкенд: в задаче, выставляющей `status='completed'`, добавить `state.pause_reason = ''; state.resume_hint = ''; state.pause_requested = False` в `update_fields`. Фронт: показывать approval-баннер только при `pipeline.status === 'paused_manual'` (уже так на строке 114, но проблема в том, что `pause_reason` не чистится на бэке — фикс именно бэкендный).

### BUG-S0-06 — Нет индикатора статуса sandbox

**Файлы:**
- `frontend/components/studio/StudioLayout.tsx` (top bar)
- `frontend/components/studio/PreviewPanel.tsx`

**Корень:** Пользователь не видит, жив ли sandbox. Нет ни «active», ни «inactive».

**Фикс:** Добавить компонент-индикатор `SandboxStatusBadge` в top bar StudioLayout (рядом с back-кнопкой): зелёная точка + «Песочница активна» если `project.sandbox_container_id` и `project.preview_port`, серая + «Песочница остановлена» иначе. Для точности — новый эндпоинт `GET /studio/projects/{id}/sandbox/` → `{ alive: bool, port: int, uptime_s: int }` (пинг контейнера). Детали — Раздел 1, пункт 1.5.

### BUG-S0-07 — В paused_on_loop форсится ContextChat overlay (мешает профи)

**Файлы:**
- `frontend/components/studio/StudioLayout.tsx` (строки 64-67, 147-157)
- `src/studio/views/pipeline.py` → `PipelineResumeView` (строки 89-119)

**Корень:** При `status === 'paused_on_loop'` весь рабочий стол подменяется `<ContextChat>` overlay (строки 147-157), который требует ввести подсказку. Профи хочет просто нажать «Продолжить» и идти дальше, а вместо панелей — чат на весь экран.

**Фикс:** Не подменять весь layout. Показывать **компактный pause-баннер** (как у `paused_manual`, строки 114-127) с тремя кнопками, маппящимися на существующий `resume({action})`:
- «Продолжить» → `action: 'continue'`
- «Подсказать и продолжить» → раскрывает inline-поле, `action: 'with_hint'`
- «Пропустить шаг» → `action: 'skip_step'`

ContextChat сделать **опциональной боковой панелью** (toggle), а не overlay. Детали — Раздел 1, пункт 1.6.

### BUG-S0-08 — DiffViewer существует, но нигде не показывается

**Файлы:**
- `frontend/components/studio/DiffViewer.tsx` (готовый компонент, props `{oldContent, newContent, path}`)
- `frontend/lib/api/studio.ts` (НЕТ метода `fileDiff` — эндпоинт есть, клиент его не зовёт)
- `src/studio/views/files.py` → `FileDiffView` (строки 40-53 — эндпоинт `/files/{id}/diff/?ref=` РАБОТАЕТ, возвращает `{path, old, new}`)

**Корень:** `DiffViewer` — мёртвый код. `FileDiffView` существует и работает, но `studio.ts` не имеет метода `fileDiff()`, и StudioLayout не имеет вкладки Diff.

**Фикс:**
1. В `studio.ts` добавить: `fileDiff: (id, fileId, ref) => request<{path, old, new}>(\`/studio/projects/${id}/files/${fileId}/diff/?ref=${ref}\`)`.
2. В StudioLayout среднюю панель сделать табами **Code | Diff** (как в Разделе 2, пункт 2.4): при выборе Diff грузить `fileDiff(id, fileId, versionRef)` и рендерить `<DiffViewer>`.

### BUG-S0-09 — Preview proxy через Django добавляет latency и падает при неготовом порте

**Файлы:**
- `src/studio/views/pipeline.py` → `PreviewProxyView` (строки 168-188)
- `frontend/components/studio/PreviewPanel.tsx` (строка 23)
- `nginx.conf`

**Корень:** Превью идёт `iframe → Next.js → Django (PreviewProxyView) → requests.get(http://{cid}:3000) → обратно`. Это: (а) добавляет latency на каждый ассет; (б) для Next.js-приложений `/_next/static/...` запрашивается абсолютными путями → 404 (это же BUG-11 из STUDIO_PLAN.md); (в) при неготовом dev-сервере — `requests` exception → 502 без retry.

**Фикс (поэтапно):**
- Краткосрочно: в `PreviewProxyView` добавить retry с backoff + проксировать sub-path корректно (сейчас path берётся, но iframe грузит корень без path-rewrite). Отдавать 425 «Too Early» + спиннер на фронте, пока dev-сервер не «ready».
- Среднесрочно (рекомендуется): subdomain-proxy `sandbox-{cid}.aineron.ru → http://{cid}:3000` через nginx + wildcard SSL `*.aineron.ru`. `PreviewPanel` строит URL напрямую. Это же Sprint E7 в STUDIO_PLAN.md — см. там. Решает и latency, и `_next/static` 404.

### BUG-S0-10 — coder_iteration без sandbox на resume-пути — ИСПРАВЛЕНО

**Статус:** УЖЕ ИСПРАВЛЕНО (задеплоено). Ранее resume-путь (`PipelineResumeView` → `coder_iteration.delay`) обходил спавн sandbox. Оставляю в списке для трассируемости. **Регресс-тест:** после паузы на `paused_on_loop` → resume `continue` → убедиться, что `coder_iteration` видит живой контейнер (проверить `project.sandbox_container_id` непустой перед `write_files`).

### Перепроверка устаревших багов из STUDIO_PLAN.md (НЕ включать как открытые)

Эти пункты из старого аудита **уже закрыты** в текущем коде — не тратить на них спринт:
- **BUG-01** (`'interviewing'` vs `'interview'`): `models.py` строка 9 = `('interview', ...)`, `PipelineStatus.STATUS_TO_ACTIVE` использует `interview:` — совпадает. Закрыто.
- **BUG-04** (pause не ревокает таски): `PipelinePauseView` строки 82-83 вызывает `current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')`. Закрыто.
- **BUG-10** (ручная правка не синкается): `FileDetailView.perform_update` строки 34-37 вызывает `sync_manual_edit.delay(...)`. Закрыто (но проверить, что `sync_manual_edit` реально пишет в sandbox+Gitea — см. Раздел 2, пункт 2.2).
- **`current_task_id`** поле уже есть в `StudioPipelineState` (models.py строка 91). Закрыто.

> Биллинг-баги (BUG-02, BUG-03, BUG-05, BUG-09) из STUDIO_PLAN.md **остаются актуальны** — это бэкенд-стабильность, делать по тому документу параллельно. Здесь не дублирую.

---

## РАЗДЕЛ 1: UX/UI — Первоочередные улучшения (Sprint 1, 1-2 недели)

Всё, что видно на скриншоте как сломанное/отсутствующее. Точное размещение, label, поведение.

### 1.1 Кнопка «← Проекты» (back to site)

**Где:** `StudioLayout.tsx`, top bar, первым элементом ДО `<PipelineStatus>` (вставка перед строкой 79, внутри `<div className="flex items-center gap-4 px-4 py-2 ...">`).
**Что:**
```tsx
<Link href="/studio" className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] shrink-0">
  <ArrowLeft size={16} /> Проекты
</Link>
<div className="w-px h-4 bg-[var(--border)]" /> {/* разделитель */}
```
**Дополнительно:** в `frontend/app/studio/[id]/layout.tsx` или в самой странице добавить хлебные крошки `Studio / {project.name}`. Логотип aineron.ru в левом углу top bar ведёт на `/` (главная сайта). На мобильном back-кнопка остаётся (иконка без текста).

### 1.2 Авто-выбор первого файла при загрузке

**Где:** `StudioLayout.tsx`, после объявления state (после строки 30).
**Что:**
```tsx
useEffect(() => {
  if (selectedFileId === null && files.length > 0) {
    const priority = ['index.html', 'app/page.tsx', 'src/App.tsx', 'src/App.jsx', 'README.md', 'COMMITS.md'];
    const pick = priority.map(p => files.find(f => f.path.endsWith(p))).find(Boolean) ?? files[0];
    if (pick) handleFileSelect(pick.id);
  }
}, [files, selectedFileId]);
```
**Поведение:** при первой загрузке проекта средняя панель сразу показывает код, а не «Выберите файл». В `FileTree` соответствующий файл подсвечивается (`selectedId`).

### 1.3 Поведение Preview на завершённых проектах

**Где:** `PreviewPanel.tsx` — добавить prop `status: string`. `StudioLayout.tsx` строки 187, 208 — передавать `status={project.status}`.
**Что показывать при `status === 'completed'`** (вместо iframe) — completion-card:
```
[CheckCircle зелёный]  Проект завершён
Превью-сервер песочницы остановлен для экономии ресурсов.
[ Скачать ZIP ]  [ Развернуть на Vercel ]  [ Перезапустить превью ]
```
- «Скачать ZIP» → `studioApi.exportUrl(id)`.
- «Развернуть на Vercel» → `studioApi.deploy(id)` (эндпоинт `/deploy/` уже есть).
- «Перезапустить превью» → новый эндпоинт `POST /studio/projects/{id}/preview/restart/` → re-spawn sandbox, обновить `sandbox_container_id`.

При `status === 'failed'` — error-card (см. Раздел 4, пункт 4.5).

### 1.4 Кликабельный Pipeline status bar с деталями

**Где:** `PipelineStatus.tsx` (рефактор), новый `StepDetailDrawer.tsx`, проброс callback в `StudioLayout`.
**Что:** каждый шаг → `<button>`, `onClick` открывает drawer снизу/сбоку с:
- Заголовок шага (из `commits_md_content`, секция по индексу).
- Статус: pending / running / done / failed.
- `review_report` (issues[], summary), `test_report` (errors[], build_ok), `fix_plan` (instructions, target_files) — из `pipeline`.
- Кнопка «Показать diff шага» → DiffViewer.
**Данные:** `review_report`/`test_report`/`fix_plan` уже в `StudioPipelineState` (models.py 84-86), но текущий `PipelineStateSerializer` их, вероятно, не отдаёт — **добавить эти поля в сериалайзер** + в TS-тип `PipelineState`.

### 1.5 Индикатор статуса sandbox

**Где:** top bar StudioLayout (после back-кнопки), новый компонент `SandboxStatusBadge.tsx`.
**Что:**
- Зелёная точка + «Песочница активна» — если `project.sandbox_container_id && project.preview_port`.
- Жёлтая + «Запускается…» — если `status === 'coding'` и порт ещё `null`.
- Серая + «Остановлена» — иначе.
**Эндпоинт (для точности живости):** `GET /studio/projects/{id}/sandbox/` → `{ alive, port, uptime_s }`. Polling раз в 10с (можно совместить с уже идущим polling проекта).

### 1.6 Профессиональный pause-UX (вместо forced ContextChat)

**Где:** `StudioLayout.tsx` строки 147-157 (убрать overlay), строки 113-127 (расширить баннер на оба paused-статуса).
**Что:** единый pause-баннер для `paused_manual` И `paused_on_loop`:
```
[AlertTriangle жёлтый] {pause_reason}
[ Продолжить ]  [ Подсказать и продолжить ]  [ Пропустить шаг ]  [ Открыть чат с агентом ]
```
Маппинг на существующий API:
- «Продолжить» → `resume(id, {action:'continue'})`
- «Подсказать и продолжить» → inline-textarea → `resume(id, {action:'with_hint', hint})`
- «Пропустить шаг» → `resume(id, {action:'skip_step'})`
- «Открыть чат с агентом» → toggle боковой панели `<ContextChat>` (не overlay).
**При `paused_manual`** (ручное одобрение в SEMI) кнопка «Подтвердить» → `approve(id)` остаётся.

### 1.7 Профессиональные горячие клавиши

**Где:** новый хук `useStudioHotkeys()` в `StudioLayout`.
| Клавиша | Действие |
|---------|----------|
| `Ctrl/Cmd + S` | Сохранить редактируемый файл (PATCH) |
| `Ctrl/Cmd + B` | Свернуть/развернуть FileTree |
| `Ctrl/Cmd + \`` | Открыть/закрыть лог агентов (drawer, строки 213-226) |
| `Ctrl/Cmd + K` | Палитра команд (поиск файлов + действия) |
| `Ctrl/Cmd + Enter` | «Продолжить» на паузе |
| `Esc` | Закрыть drawer/overlay |
Показать подсказку «?» в углу → панель шорткатов (см. Раздел 5).

---

## РАЗДЕЛ 2: Профессиональные инструменты (Sprint 2, 2-3 недели)

### 2.1 Встроенный терминал (WebSocket → bash в sandbox)

**Новое:**
- Бэкенд: **WebSocket-эндпоинт** (через `django-channels`, т.к. текущий стек на SSE/gunicorn WSGI не держит WS — нужен ASGI-воркер). Путь `ws/studio/{id}/terminal/`. Внутри — `docker exec -it {cid} /bin/bash` через `container.exec_run(..., stream=True, socket=True)`.
- Фронт: компонент `Terminal.tsx` на `xterm.js` (`@xterm/xterm` + `@xterm/addon-fit`), новая вкладка в нижнем drawer рядом с «Лог агентов».
**Безопасность:** терминал только при живом sandbox и только владельцу; ограничить по CPU/времени; запретить при `status==='completed'`.
**Эндпоинт:** новый, WS. Это самостоятельная инфра-задача (ASGI).

### 2.2 Редактирование файла прямо в дереве (не только просмотр)

**Где:** `CodeViewer.tsx` → сделать редактируемым (заменить `<pre><code>` на **CodeMirror 6** или Monaco), auto-save debounce 1с.
**API:** `FileDetailView` (PATCH) уже есть и уже вызывает `sync_manual_edit.delay()` (files.py 34-37). **Проверить**, что `sync_manual_edit` реально: (а) пишет в sandbox через `sandbox.write_files()`; (б) коммитит в Gitea. Если нет — дореализовать (это бывший BUG-10).
**Фронт:** добавить метод `updateFile(id, fileId, content)` в `studio.ts` (PATCH на `/files/{id}/`). Индикатор «Сохранено / Сохранение…».
**Файловые операции в самом дереве (CRUD):** помимо редактирования контента — операции над файлами прямо в `FileTree.tsx` через контекстное-меню (right-click) и кнопки-иконки на hover: «Создать файл», «Создать папку», «Переименовать», «Удалить», «Переместить» (drag&drop). Новые эндпоинты: `POST /studio/projects/{id}/files/` `{path, content}` (создание), `DELETE /studio/projects/{id}/files/{file_id}/` (удаление — `FileDetailView` уже `RetrieveUpdate`, добавить `Destroy`), `POST /studio/projects/{id}/files/{file_id}/rename/` `{new_path}`. Каждая операция синкается в sandbox + Gitea (как `sync_manual_edit`).

### 2.3 Поиск по файлам (Ctrl+Shift+F)

**Новое:**
- Бэкенд: новый эндпоинт `GET /studio/projects/{id}/search/?q=...&regex=0` → `[{file_id, path, line, snippet}]`. Поиск по `StudioFile.content` (ILIKE или regex). При живом sandbox можно `exec_run('grep -rn ...')`, но БД-поиск надёжнее.
- Фронт: компонент `SearchPanel.tsx`, открывается по `Ctrl+Shift+F`, оверлей слева. Клик по результату → `handleFileSelect` + скролл к строке.
**Метод в studio.ts:** `searchFiles(id, q)`.

### 2.4 Diff-вкладка для каждого шага (подключить DiffViewer)

**Где:** `StudioLayout` средняя панель → табы **Code | Diff**.
**API:** эндпоинт `/files/{id}/diff/?ref=` УЖЕ РАБОТАЕТ (files.py 40-53). Нужен только метод `fileDiff(id, fileId, ref)` в `studio.ts` (это фикс BUG-S0-08).
**Поведение:** Diff показывает изменения файла относительно выбранной версии (`ref` = `git_sha` из `StudioVersion`). Дропдаун выбора версии над DiffViewer. Использует готовый `DiffViewer.tsx` (props `oldContent`/`newContent`/`path`).

### 2.5 Мульти-выбор файлов для инструкций AI

**Где:** `FileTree.tsx` → чекбоксы на файлах (Shift+click для диапазона).
**Поведение:** выбранные файлы образуют «контекст» → при отправке инструкции в ContextChat/Fixer передаются как `target_files`. Эндпоинт `resume`/`chat` уже принимает контекст; расширить payload `{message, target_files: string[]}`.
**UI:** счётчик «Выбрано N файлов» + кнопка «Дать инструкцию по выбранным».

### 2.6 Управление переменными окружения (.env editor)

**Новое:**
- Бэкенд: эндпоинты `GET/PUT /studio/projects/{id}/env/` → `{ vars: {KEY: VALUE} }`. Хранить в `StudioProject.interview_data['env']` (или новое поле `env_vars` JSONField). При записи — `sandbox.write_files(cid, {'.env': ...})` + рестарт dev-сервера.
- Фронт: `EnvEditor.tsx` — таблица KEY/VALUE, маскировка значений (показать/скрыть), кнопка «Применить и перезапустить».
**Безопасность:** значения не отдавать в открытых логах SSE.

### 2.7 UI управления зависимостями (package.json)

**Новое:**
- Бэкенд: эндпоинты `GET /studio/projects/{id}/deps/` (парсит `package.json` из `StudioFile`), `POST /studio/projects/{id}/deps/` `{name, version, dev}` → `exec_run(cid, 'pnpm add ...')` + обновить `package.json` в БД/Gitea.
- Фронт: `DependencyManager.tsx` — список зависимостей с версиями, поле «добавить пакет», кнопка удаления. Индикатор установки (стрим из `exec_run`).

---

## РАЗДЕЛ 3: Уникальные фичи (Sprint 3, 3-4 недели) — чего нет ни у кого в России

### 3.1 Visual Step Timeline (киллер-фича)

**Новое:** горизонтальная/вертикальная лента кликабельных **step-карточек** (развитие BUG-S0-04). Каждая карточка:
- Заголовок шага из `commits_md_content`.
- **Планировалось vs реализовано**: planned-описание (из COMMITS.md) рядом с фактически изменёнными файлами (из `StudioVersion` + diff).
- Diff шага (через `DiffViewer` + `fileDiff`).
- Статус: passed на 1-й итерации / N итераций / завален.
- **«Ветка от этого шага»** — кнопка `branchFromStep(versionId)`: создаёт новый `StudioProject` (форк), откатанный к этой версии, дальше можно вести независимо.
**Эндпоинты:** `GET /studio/projects/{id}/timeline/` → агрегат `[{step_index, name, planned, changed_files, review, test, version_id}]`; `POST /studio/projects/{id}/branch/{version_id}/`.
**Компонент:** `StepTimeline.tsx`.

### 3.2 «Режим Ревьюера» — planned vs coded side-by-side

**Новое:** после каждого шага AI показывает 2 колонки: слева — что планировал Planner (текст шага из COMMITS.md), справа — что реально написал Coder (изменённые файлы), с подсветкой **отклонений** от плана.
**Бэкенд:** новый агент `DeviationReviewerAgent` (Opus 4.8) → `{matched: [], deviations: [{planned, actual, severity}]}`. Эндпоинт `GET /studio/projects/{id}/steps/{n}/deviation/`.
**Фронт:** `ReviewerMode.tsx`, переключатель в Step Detail Drawer.

### 3.3 Live Collaboration (несколько юзеров видят пайплайн в реальном времени)

**Существует основа:** модель `StudioCollaborator` (models.py 115-127) и эндпоинт `CollaboratorView` уже есть.
**Новое:** presence через SSE (`PipelineEventsView` уже стримит) — добавить событие `{type:'presence', users:[...]}`. Фронт: аватарки активных пользователей в top bar, индикатор «кто смотрит какой файл». Курсоры в редакторе — опционально (CRDT, фаза 2).
**Эндпоинты:** расширить `/events/` событиями presence; `POST /studio/projects/{id}/presence/` (heartbeat).

### 3.4 Переключатель мобильного превью (375px)

**Где:** `PreviewPanel.tsx` — toolbar добавить toggle Desktop / Mobile / Tablet.
**Что:** при Mobile — обернуть iframe в контейнер `width:375px` (iPhone) с рамкой-«телефоном», центрировать. Кнопки 375 / 768 / 100%. Чисто фронтовая фича, эндпоинт не нужен.

### 3.5 AI Screenshot-to-Code (загрузил макет → код)

**Новое:**
- Фронт: на странице создания (`frontend/app/studio/page.tsx`) и в чате — upload изображения (drag&drop).
- Бэкенд: новый эндпоинт `POST /studio/projects/{id}/screenshot/` (multipart) → vision-модель (через laozhang.ai, мультимодальная) генерирует описание UI → подмешивается в `interview_data`/инструкцию Coder. Хранить картинку в `media/studio/`.
**Агент:** `ScreenshotAgent` — vision prompt «опиши верстку, цвета, компоненты».

### 3.6 «Объясни этот код» (выделил блок → объяснение по-русски)

**Где:** `CodeViewer.tsx` — на выделение текста показывать floating-кнопку «Объясни».
**Бэкенд:** `POST /studio/projects/{id}/explain/` `{code, path}` → DeepSeek/Opus → объяснение на русском. Списывает 1 звезду (как ContextChat).
**Фронт:** поповер с объяснением + markdown-рендер (переиспользовать `react-markdown` из чата).

### 3.7 Библиотека промптов для кодеров

**Новое:**
- Модель `StudioPrompt` (user, title, body, is_public, likes, forks).
- Эндпоинты `GET/POST /studio/prompts/`, `POST /studio/prompts/{id}/fork/`, `POST /studio/prompts/{id}/like/`.
- Фронт: `/studio/prompts/` — встроенные + пользовательские + community. Кнопка «Использовать» подставляет в описание проекта.
**Связь:** переиспользовать паттерн существующей `/prompts/` библиотеки чата.

### 3.8 Экспорт в GitHub (не только Vercel)

**Новое:**
- GitHub OAuth (добавить провайдер; allauth уже в стеке).
- Эндпоинт `POST /studio/projects/{id}/export/github/` `{repo_name, private}` → создать репо через GitHub API, запушить все `StudioFile`.
- Фронт: кнопка «Экспорт в GitHub» рядом с «Скачать ZIP» (top bar + completion-card). Показать URL репозитория.
**Хранить:** `github_repo_url` в `StudioProject`.

### 3.9 «Режим отладки» — AI читает ошибки консоли браузера → авто-фикс

**Новое:**
- Фронт: внедрить в превью-iframe скрипт-перехватчик `window.onerror`/`console.error` → postMessage в родителя → отправка на бэкенд.
- Бэкенд: `POST /studio/projects/{id}/console-error/` `{message, stack, file, line}` → передать Fixer-агенту → предложить фикс. Кнопка «Исправить автоматически» → `resume(with_hint)` с текстом ошибки.
**Компонент:** `DebugMode.tsx`, индикатор «N ошибок в консоли» на PreviewPanel.

### 3.10 Система уведомлений (Telegram/email по завершении)

**Новое:**
- Celery: в задаче завершения пайплайна — `notify_project_done.delay(project_id)`: email (есть `email_service`) + Telegram (если у юзера привязан chat_id; задел — `TELEGRAM_BOT_PLAN.md`).
- PWA push (next-pwa уже в стеке) — уведомление «Проект {name} готов».
- Настройка в `/account/`: галочки «уведомлять по email / Telegram / push».
**Эндпоинт:** `PUT /studio/notifications/` `{email, telegram, push}`.

---

## РАЗДЕЛ 4: Дизайн-улучшения (детально)

### 4.1 Цветовая схема и визуальная иерархия

- Использовать существующие CSS-переменные (`--border`, `--hover`, `--text`, `--text-secondary`) — уже есть dark-mode основа.
- **Акцент:** единый `--accent` (сейчас хардкод `blue-600`/`blue-700` по StudioLayout). Завести `--studio-accent` (фиолетово-синий, как Linear) и заменить хардкоды.
- **Семантика статусов:** running=blue, done=green, paused=amber, failed=red, idle=gray. Сейчас разбросано — централизовать в `studioColors.ts`.
- Иерархия: top bar (фон чуть темнее), панели разделены `divide-x divide-[var(--border)]` (уже так). Активная панель — лёгкая подсветка границы.

### 4.2 Редизайн Pipeline status bar

- Сейчас (PipelineStatus.tsx): пилюли с точками, неинтерактивные. **Стало:** кликабельные сегменты-кнопки (BUG-S0-04 / Раздел 1.4) с:
  - прогресс-заливкой внутри активного шага (итерации);
  - tooltip при наведении (название + статус);
  - бейдж количества итераций на шаге Coder/Fixer;
  - тонкая connecting-линия с анимацией «бегущей точки» на активном сегменте.

### 4.3 Редизайн completion-state (вместо broken preview)

**Сейчас:** broken file icon (BUG-S0-01). **Стало** — completion-card (центр правой панели):
```
┌─────────────────────────────────────┐
│  [CheckCircle 48px green]            │
│  Проект завершён                    │
│  {N} шагов · {M} звёзд потрачено    │
│  Превью-сервер остановлен.          │
│                                     │
│  [ Скачать ZIP ]                    │
│  [ Развернуть на Vercel ]           │
│  [ Экспорт в GitHub ]               │
│  [ Перезапустить превью ]           │
│  ссылка на репозиторий →            │
└─────────────────────────────────────┘
```
Данные — из `BillingEstimate` (уже показывает `spentStars`/`plannedSteps`/`repoUrl`).

### 4.4 Loading states и skeleton-экраны

- Сейчас: один `<Loader2>` по центру (page.tsx 38-44). **Стало:** skeleton 3-панельного layout (серые блоки file tree / code / preview) — ощущение скорости.
- FileTree во время генерации: skeleton-строки + «Агент создаёт файлы…».
- Preview: спиннер «Запускаем dev-сервер…» пока порт не ready (вместо 502).

### 4.5 Error-состояния

- `status === 'failed'`: error-card (красная) с `pipeline.last_error`, кнопками «Повторить с шага N», «Откатиться», «Связаться с поддержкой».
- 402 (нет звёзд): баннер «Недостаточно звёзд» + кнопка «Пополнить» → `/account/billing/`.
- 502 preview: «Превью недоступно — перезапустить?» вместо broken icon.

### 4.6 Мобильная адаптивность

- Мобильные табы уже есть (StudioLayout 130-145). Улучшить: swipe между Files/Code/Preview; sticky pause-баннер; FileTree как bottom-sheet.
- CodeViewer: горизонтальный скролл + кнопка «перенос строк».
- Pause-кнопки — крупные, full-width на мобильном.

### 4.7 Полнота Dark Mode

- CodeViewer уже грузит `github-dark.css` (строка 6) — для light-mode подгружать `github.css` по `data-theme`.
- Проверить все хардкод-цвета (`bg-amber-950/40`, `text-green-300`, `bg-red-950`) на читаемость в light-mode — заменить на пары через CSS-переменные.
- DiffViewer (`bg-green-950`/`bg-red-950`) — добавить light-варианты.

---

## РАЗДЕЛ 5: Технические кнопки и controls (полный список)

Размещение: **[TB]** = top bar StudioLayout; **[PV]** = toolbar PreviewPanel; **[CV]** = toolbar CodeViewer; **[DR]** = нижний drawer; **[CC]** = completion-card.

| Контрол / label | Где | Поведение | Статус |
|-----------------|-----|-----------|--------|
| `← Проекты` | [TB] слева | `Link href="/studio"` | НЕТ (BUG-S0-02) |
| Логотип aineron.ru | [TB] крайний левый | → `/` | НЕТ |
| `Песочница активна/остановлена` badge | [TB] | индикатор + ping `/sandbox/` | НЕТ (BUG-S0-06) |
| `Остановить` (Stop/Abort) | [TB] при running | `POST /pause/` (revoke уже работает) | частично (pause есть, нужен label «Остановить») |
| `Перезапустить с шага N` | [TB] / Step Drawer | `POST /studio/projects/{id}/restart-step/{n}/` (новый) | НЕТ |
| `Открыть в новой вкладке` | [PV] | `target=_blank` на preview URL | ЕСТЬ (PreviewPanel 35-43) |
| `Обновить превью` | [PV] | reload iframe (`setKey`) | ЕСТЬ (28-34) |
| Mobile/Tablet/Desktop toggle | [PV] | resize iframe-контейнера | НЕТ (Раздел 3.4) |
| Split/merge панелей (ресайз/свернуть) | границы панелей + [TB] | draggable-разделители между FileTree/Code/Preview (react-resizable-panels); toggle «Свернуть превью» / «Свернуть дерево»; двойной клик по панели — развернуть на весь экран (maximize); раскладка сохраняется в localStorage | НЕТ |
| `Перезапустить превью` | [PV] / [CC] | `POST /preview/restart/` (новый) | НЕТ |
| Code \| Diff табы | [CV] | переключение CodeViewer/DiffViewer | НЕТ (BUG-S0-08) |
| `Скопировать` | [CV] | clipboard | ЕСТЬ (CodeViewer 45-51) |
| `Сохранить` (Ctrl+S) | [CV] | PATCH `/files/{id}/` | НЕТ (Раздел 2.2) |
| `Объясни` | [CV] на выделении | `POST /explain/` | НЕТ (Раздел 3.6) |
| Поиск по файлам (Ctrl+Shift+F) | overlay | `GET /search/` | НЕТ (Раздел 2.3) |
| Терминал | [DR] вкладка | WS `/terminal/` | НЕТ (Раздел 2.1) |
| Лог агентов toggle | [DR] | свернуть/развернуть | ЕСТЬ (StudioLayout 213-226) |
| Панель шорткатов `?` | [TB] | модалка со списком | НЕТ (Раздел 1.7) |
| Настройки проекта (шестерёнка) | [TB] | модалка: модель, max итераций, режим | НЕТ |
| `Поделиться` (share link) | [TB] | копирует ссылку + invite collaborator | частично (`/collaborators/` есть) |
| `Развернуть на Vercel` | [TB]/[CC] | `POST /deploy/` | API есть, кнопки в UI нет |
| `Экспорт в GitHub` | [TB]/[CC] | `POST /export/github/` (новый) | НЕТ (Раздел 3.8) |
| `Скачать ZIP` | [TB]/[CC] | `exportUrl(id)` | ЕСТЬ (StudioLayout 100-108) |
| Pause-кнопки (Продолжить/Подсказать/Пропустить) | pause-баннер | `resume({action})` | API есть, UX переделать (BUG-S0-07) |

### Настройки на проект (модалка «шестерёнка»)
Новый эндпоинт `PATCH /studio/projects/{id}/settings/`:
- Модель Coder: DeepSeek V3 (быстро) / Opus 4.8 (качество).
- `max_iterations` на шаг (сейчас глобальный `STUDIO_MAX_ITERATIONS`).
- Режим: auto / semi / manual (смена на лету).
- Бюджет звёзд на проект (`max_stars_budget`).
- Авто-деплой по завершении (вкл/выкл).

---

## РАЗДЕЛ 6: Порядок реализации (по соотношению impact/effort)

### Волна 0 — «Не выглядит сломанным» (3-4 дня) — МАКСИМАЛЬНЫЙ impact, минимальный effort
Чисто фронтовые правки + мелкие бэкенд-чистки. Сразу убирают «вау, тут всё сломано»:
1. **BUG-S0-02** — кнопка «← Проекты» (Раздел 1.1). *5 строк.*
2. **BUG-S0-03** — авто-выбор первого файла (Раздел 1.2). *useEffect.*
3. **BUG-S0-01** — completion-card вместо broken preview (Раздел 1.3 + 4.3) + очистка `sandbox_container_id` на бэке.
4. **BUG-S0-05** — чистить `pause_reason` при completed (бэк, 1 строка).
5. **BUG-S0-06** — sandbox badge (Раздел 1.5).
> Эффект: профи открывает Studio и видит законченный, навигируемый интерфейс. Это решает 80% «впечатления сломанности» из скриншота.

### Волна 1 — «Прозрачность и контроль» (Sprint 1, 1 неделя)
6. **BUG-S0-08 + Раздел 2.4** — подключить DiffViewer (метод `fileDiff` + Code/Diff табы). *Оживляет мёртвый код, дёшево.*
7. **BUG-S0-04 + Раздел 1.4** — кликабельный pipeline + Step Detail Drawer (review/test/fix в сериалайзер).
8. **BUG-S0-07** — профессиональный pause-UX (Раздел 1.6).
9. **Раздел 1.7** — горячие клавиши + панель шорткатов.
10. Кнопки в top bar: «Развернуть на Vercel» (API уже есть), «Поделиться».
> Эффект: видимая прозрачность пайплайна — то, чего НЕТ ни у Lovable, ни у Bolt (они скрывают шаги). Это наше дифференцирующее преимущество, и оно почти бесплатно.

### Волна 2 — «Инструменты разработчика» (Sprint 2, 2-3 недели)
11. **Раздел 2.2** — редактируемый CodeViewer (CodeMirror) + проверка `sync_manual_edit`.
12. **Раздел 2.3** — поиск по файлам (Ctrl+Shift+F).
13. **Раздел 3.4** — мобильное превью toggle (дёшево, эффектно для демо).
14. **BUG-S0-09 / Sprint E7** — subdomain-proxy превью (решает Next.js 404 + latency). *Инфра, но критично для «реально работает».*
15. **Раздел 2.1** — встроенный терминал (xterm + channels/ASGI). *Дорого по инфре — после превью.*

### Волна 3 — «Killer-фичи, которых нет в России» (Sprint 3, 3-4 недели)
16. **Раздел 3.1** — Visual Step Timeline + branch from step. *Главный дифференциатор.*
17. **Раздел 3.6** — «Объясни этот код» (дёшево, вирусно, 1 звезда).
18. **Раздел 3.9** — «Режим отладки» (console error → авто-фикс). *Уникально.*
19. **Раздел 3.5** — Screenshot-to-Code. *Догоняет Lovable, но на русском без VPN.*
20. **Раздел 3.8** — экспорт в GitHub.
21. **Раздел 3.2** — Режим Ревьюера (planned vs coded).
22. **Раздел 3.10** — уведомления (email/Telegram/push).
23. **Раздел 3.3** — live collaboration (основа есть).
24. **Раздел 3.7** — библиотека промптов кодеров.

### Параллельно (бэкенд-стабильность, из STUDIO_PLAN.md)
- Биллинг-баги BUG-02/03/05 (пауза при нулевом балансе, try/except Docker, идемпотентность retry).
- A1 (prefork pool для Docker), A4 (SSE cleanup), reap_stale в Beat.
- Эти не видны в UI, но без них Волны 1-3 будут падать под нагрузкой.

### Логика приоритизации
- **Волна 0** даёт максимальный сдвиг восприятия за минимум кода — делать в первую очередь, можно за выходные.
- **Волна 1** превращает скрытый пайплайн в видимый — это то, чем мы бьём Lovable/Bolt (у них шаги скрыты). Дёшево, потому что данные (`review_report`/`test_report`/`fix_plan`, `FileDiffView`, `DiffViewer`) уже есть — нужно только соединить.
- **Волна 2** делает Studio пригодной для профи (терминал, поиск, редактирование, рабочее превью).
- **Волна 3** — то, ради чего о нас напишут: Step Timeline, режим отладки, screenshot-to-code — ни у одного российского конкурента (GigaCode, YaGPT) этого нет вообще, а глобальные не работают без VPN и не на русском.

---

## Сводка: что уже есть и просто не подключено (самый дешёвый impact)

| Готово в коде | Не подключено к UI | Действие |
|---------------|---------------------|----------|
| `DiffViewer.tsx` | нет вкладки Diff, нет метода `fileDiff` | Раздел 2.4 |
| `FileDiffView` (`/files/{id}/diff/`) | клиент не зовёт | добавить `fileDiff` в studio.ts |
| `review_report`/`test_report`/`fix_plan` (модель) | не в сериалайзере, не в UI | Step Drawer (1.4) |
| `DeployView` (`/deploy/`) | нет кнопки в top bar | добавить кнопку |
| `StudioCollaborator` + `/collaborators/` | нет share-UI | Раздел 3.3 |
| `current_task_id` + revoke в pause | работает | — |
| `sync_manual_edit` на PATCH | редактор read-only | Раздел 2.2 |
| `pause_reason`/`resume_hint`/3 action в resume | overlay вместо баннера | Раздел 1.6 |

**Вывод:** ~40% «новых» фич Волн 0-1 — это подключение уже написанного кода. Это и есть самый быстрый путь «вау» для профи при минимальном риске.

---

*Документ создан: 2026-06-16. Парный документ — `STUDIO_PLAN.md` (бэкенд-аудит, биллинг, архитектура). Этот — UX/продукт, driven скриншотом и конкурентами.*
