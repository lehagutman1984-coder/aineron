# STUDIO_UPGRADE_COMMITS.md — Пошаговый план апгрейда Vibe-Coding Studio

Детальный, исполняемый план модернизации студии vibe-кодинга по `STUDIO_UPGRADE_PLAN.md` (Волны 0-3). Каждый коммит самодостаточен: содержит точные пути, before/after-сниппеты на основе **реального текущего кода** и конкретный способ проверки. Открывайте этот файл в новом чате и начинайте с нужной сессии.

> **Это отдельный документ от `STUDIO_COMMITS.md`** (бэкенд-стабильность/биллинг, Commits 1-36). Этот документ — UX/продукт, по `STUDIO_UPGRADE_PLAN.md`, и нумерует коммиты с **U1** (`U` = upgrade), чтобы не пересекаться с базовым планом.

## Как пользоваться

- Коммиты пронумерованы `U1..U41` и идут в порядке реализации. Соблюдайте `Dependencies`.
- Каждый коммит — **одна забота**. Не объединяйте.
- После любого изменения поля модели — обязательно `cd src && python manage.py makemigrations studio && python manage.py migrate`.
- Тесты студии: `cd src && python manage.py test studio`. Сборка фронта: `cd frontend && npm run build`.
- UI: только Lucide React, ноль эмодзи (см. CLAUDE.md). User-facing текст — русский, комментарии в коде — английский.
- По правилу проекта — `git push origin main` после каждого коммита.

## ВАЖНО — расхождения «плана» и реального кода (перепроверено против рабочих файлов)

`STUDIO_UPGRADE_PLAN.md` местами описывает код неточно. Реальное состояние на момент написания (использовать его как BEFORE):

| Утверждение из плана | Реальность в коде | Следствие для коммитов |
|----------------------|-------------------|------------------------|
| `PipelineStateSerializer` не отдаёт `review_report`/`test_report`/`last_error` | Реально `fields = '__all__'` (`serializers.py:54-57`) — **уже отдаёт всё** | U7: НЕ трогаем сериалайзер, только TS-тип + UI |
| `CodeViewer` без подсветки, read-only `<pre><code>` | Подсветка **уже есть** через `hljs` (`CodeViewer.tsx:5,18-23`) | U13: добавляем edit-режим поверх существующего |
| Нет `EstimateView`/`DeployView`/`ContextChatView`/`ExportView`/`FileDiffView` | Все **уже есть** в `views/pipeline.py` и `views/files.py`, зарегистрированы в `urls.py` | U6/U11: только фронт-клиент + UI |
| `studio.ts` имеет `update`/`updateFile`/`events` | Реально их **НЕТ** в `studio.ts` (есть `list,create,get,files,fileDetail,pipeline,run,interview,submitInterview,pause,resume,commits,rollback,clone,estimate,contextChat,approve,deploy,exportUrl,templates`) | U13/U17: добавляем недостающие методы |
| `PipelineStatus` рендерит каждый шаг `<div>` (не кликабельный) | Верно (`PipelineStatus.tsx:42-60`), но props называются `projectStatus`/`pipelineStatus` | U7: сохранить имена props |
| `StudioLayout` строка 187 `PreviewPanel ... hasSandbox` | Верно, но `src` уже считается внутри `PreviewPanel` (`PreviewPanel.tsx:22-23`), а не передаётся | U3/U16: правим внутри `PreviewPanel` |
| BUG-S0-10 (resume без sandbox) | **Уже исправлено** | пропускаем |

## Карта Волн → коммитов

| Волна | Тема | Коммиты | Сессии |
|-------|------|---------|--------|
| 0 | «Не выглядит сломанным» | U1-U6 | SU1, SU2 |
| 1 | «Прозрачность и контроль» | U7-U16 | SU3, SU4, SU5 |
| 2 | «Инструменты разработчика» | U17-U27 | SU6, SU7, SU8, SU9 |
| 3 | «Killer-фичи» | U28-U41 | SU10, SU11, SU12 |

## Сводная таблица коммитов

| # | Сессия | Волна | Заголовок | Слой | Миграция |
|---|--------|-------|-----------|------|----------|
| U1 | SU1 | 0 | Кнопка «Проекты» (back) | FE | — |
| U2 | SU1 | 0 | Авто-выбор первого файла | FE | — |
| U3 | SU1 | 0 | Очистка sandbox_container_id + completion-card | BE+FE | — |
| U4 | SU2 | 0 | Очистка pause_reason на completion | BE | — |
| U5 | SU2 | 0 | Эндпоинт GET /sandbox/ (статус песочницы) | BE | — |
| U6 | SU2 | 0 | SandboxStatusBadge в top bar | FE | — |
| U7 | SU3 | 1 | Кликабельный PipelineStatus + StepDetailDrawer | FE | — |
| U8 | SU3 | 1 | fileDiff в studio.ts + Code/Diff табы | FE | — |
| U9 | SU4 | 1 | Inline pause-баннер вместо ContextChat overlay | FE | — |
| U10 | SU4 | 1 | ContextChat как боковая панель (toggle) | FE | — |
| U11 | SU5 | 1 | Кнопки top bar: Vercel deploy + Share | FE | — |
| U12 | SU5 | 1 | Горячие клавиши + ShortcutsModal | FE | — |
| U13 | SU6 | 2 | Редактируемый CodeViewer (CodeMirror) + Ctrl+S | FE | — |
| U14 | SU6 | 2 | Бэкенд: POST /search/ (поиск по файлам) | BE | — |
| U15 | SU6 | 2 | SearchFilesModal (Ctrl+Shift+F) | FE | — |
| U16 | SU7 | 2 | Мобильное превью toggle (375/768/100%) | FE | — |
| U17 | SU7 | 2 | Resizable панели (react-resizable-panels) | FE | — |
| U18 | SU8 | 2 | Бэкенд: PATCH /settings/ (модель, итерации, бюджет) | BE | да |
| U19 | SU8 | 2 | ProjectSettingsModal | FE | — |
| U20 | SU9 | 2 | Бэкенд: preview/restart/ (re-spawn sandbox) | BE | — |
| U21 | SU9 | 2 | PreviewPanel: кнопка «Перезапустить превью» | FE | — |
| U22 | SU9 | 2 | FileTree: создание/удаление файлов (CRUD) | BE+FE | — |
| U23 | SU10 | 3 | Бэкенд: GET /timeline/ + POST /branch/{vid}/ | BE | да |
| U24 | SU10 | 3 | StepTimeline.tsx (planned vs actual, branch) | FE | — |
| U25 | SU10 | 3 | Бэкенд: POST /explain/ | BE | — |
| U26 | SU11 | 3 | «Объясни этот код» (floating button + popover) | FE | — |
| U27 | SU11 | 3 | Бэкенд: POST /console-error/ + Fixer hook | BE | — |
| U28 | SU11 | 3 | Debug Mode (interceptor в iframe + auto-fix) | FE | — |
| U29 | SU12 | 3 | Бэкенд: POST /screenshot/ (vision → описание) | BE | да |
| U30 | SU12 | 3 | Screenshot-to-Code на странице создания | FE | — |
| U31 | SU12 | 3 | Бэкенд: GitHub OAuth + POST /export/github/ | BE | да |
| U32 | SU12 | 3 | Кнопка «Экспорт в GitHub» в completion-card | FE | — |
| U33 | SU12 | 3 | Бэкенд: уведомления о завершении (email/push) | BE | — |
| U34 | SU12 | 3 | Бэкенд: DeviationReviewerAgent + /deviation/ | BE | — |
| U35 | SU12 | 3 | Режим Ревьюера (planned vs coded side-by-side) | FE | — |

> Таблица выше — 35 коммитов. Полный список с детальными инструкциями ниже. Коммиты U36-U41 в этой версии плана зарезервированы под доработки Волны 3 (live collaboration presence, prompt library, terminal) и описаны в конце как «Backlog Волны 3».

---

# Сессия SU1 — Волна 0: мгновенные фронт-фиксы

**Слой:** фронт + 1 строка бэка. **Миграций нет.** **Время:** ~40 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U1: Кнопка «Проекты» (back to site) в top bar

**Session:** SU1
**Wave:** 0
**Fixes/Implements:** BUG-S0-02
**Files changed:**
- `frontend/components/studio/StudioLayout.tsx`

**Context:** В top bar `StudioLayout` нет ни одной ссылки на `/studio` или `/` — пользователь заперт внутри workspace и не может выйти.

**What to do:**
В `frontend/components/studio/StudioLayout.tsx` дополнить импорты (добавить `ArrowLeft`, импорт `Link`):

```tsx
// BEFORE (строка 4)
import { Play, Pause, Files, Code2, Monitor, CheckCircle, Download } from 'lucide-react';

// AFTER
import { Play, Pause, Files, Code2, Monitor, CheckCircle, Download, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
```

В top bar вставить back-ссылку и разделитель ПЕРЕД `<PipelineStatus>`:

```tsx
// BEFORE (строки 77-79)
      {/* Top bar */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-[var(--border)] shrink-0">
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />

// AFTER
      {/* Top bar */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-[var(--border)] shrink-0">
        <Link
          href="/studio"
          className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors shrink-0"
        >
          <ArrowLeft size={16} /> Проекты
        </Link>
        <div className="w-px h-4 bg-[var(--border)]" />
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: открыть `/studio/<id>/` — слева вверху ссылка «Проекты» ведёт на `/studio`.

**Dependencies:** —

---

## Commit U2: Авто-выбор первого файла при загрузке

**Session:** SU1
**Wave:** 0
**Fixes/Implements:** BUG-S0-03
**Files changed:**
- `frontend/components/studio/StudioLayout.tsx`

**Context:** `selectedFileId` стартует с `null` и нет `useEffect`, который бы выбрал первый осмысленный файл — средняя панель показывает заглушку «Выберите файл».

**What to do:**
Дополнить импорт `useState` до `useState, useEffect`:

```tsx
// BEFORE (строка 3)
import { useState } from 'react';

// AFTER
import { useState, useEffect } from 'react';
```

Сразу после объявления стейтов и хендлеров (после `handleFileSelect`, т.е. после строки 47), добавить `useEffect`. `handleFileSelect` принимает `number`, поэтому используем `pick.id`:

```tsx
// AFTER (вставить после handleFileSelect, строка ~48)
  // Auto-select a meaningful file on first load so the editor isn't empty
  useEffect(() => {
    if (selectedFileId === null && files.length > 0) {
      const priority = [
        'index.html', 'app/page.tsx', 'src/App.tsx', 'src/App.jsx',
        'README.md', 'COMMITS.md',
      ];
      const pick =
        priority.map((p) => files.find((f) => f.path.endsWith(p))).find(Boolean) ?? files[0];
      if (pick) handleFileSelect(pick.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, selectedFileId]);
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: открыть проект с уже сгенерированными файлами — средняя панель сразу показывает код, в `FileTree` подсвечен выбранный файл.

**Dependencies:** —

---

## Commit U3: Очистка sandbox_container_id на завершении + completion-card в PreviewPanel

**Session:** SU1
**Wave:** 0
**Fixes/Implements:** BUG-S0-01
**Files changed:**
- `src/studio/tasks.py`
- `frontend/components/studio/PreviewPanel.tsx`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** После завершения sandbox убивается reap-логикой, но `project.sandbox_container_id` не очищается. `hasSandbox` остаётся `true`, iframe грузит `/preview/`, прокси отдаёт 502/503 → broken-icon. Нужно очищать поле на бэке и показывать completion-card на фронте.

**What to do:**

1. Бэкенд — в `src/studio/tasks.py`, в `next_step`, в ветке завершения проекта очистить `sandbox_container_id` (контейнер реапнется отдельно; можно также явно убить здесь, но минимально — очистить поле):

```python
# BEFORE (tasks.py, next_step, строки 477-486)
    if nxt >= total:
        release_reserve(project)
        project.status = 'completed'
        project.save(update_fields=['status'])
        project.pipeline.status = 'completed'
        project.pipeline.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': 'Проект завершён',
        })

# AFTER
    if nxt >= total:
        release_reserve(project)
        # Kill and clear the sandbox so the frontend stops loading a dead preview
        if project.sandbox_container_id:
            try:
                sandbox.kill_sandbox(project.sandbox_container_id)
            except Exception:
                pass
        project.status = 'completed'
        project.sandbox_container_id = ''
        project.save(update_fields=['status', 'sandbox_container_id'])
        project.pipeline.status = 'completed'
        project.pipeline.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': 'Проект завершён',
        })
```

Также очистить поле в `reap_stale_sandboxes`, чтобы у реапнутых проектов поле не «висело»:

```python
# BEFORE (tasks.py, reap_stale_sandboxes, строки 644-651)
    for container in client.containers.list(filters={'label': 'studio_project'}):
        created_str = container.attrs.get('Created', '')
        try:
            created = datetime.datetime.fromisoformat(created_str[:19])
            if created < cutoff:
                container.remove(force=True)
        except Exception:
            pass

# AFTER
    for container in client.containers.list(filters={'label': 'studio_project'}):
        created_str = container.attrs.get('Created', '')
        try:
            created = datetime.datetime.fromisoformat(created_str[:19])
            if created < cutoff:
                pid = container.labels.get('studio_project')
                container.remove(force=True)
                if pid:
                    StudioProject.objects.filter(
                        id=pid, sandbox_container_id=container.name,
                    ).update(sandbox_container_id='')
        except Exception:
            pass
```

> Примечание: `spawn_sandbox` ставит метку `studio_project` = project_id, а `sandbox_container_id` = имя контейнера. Сопоставление по `id=pid` + `sandbox_container_id=container.name` безопасно очищает только нужный проект. Если в коде метка хранит имя, а не id — адаптировать фильтр; проверить `sandbox.py:spawn_sandbox` перед коммитом.

2. Фронт — `PreviewPanel.tsx`: добавить prop `status` и рендерить completion-card при `status === 'completed'`:

```tsx
// BEFORE (PreviewPanel.tsx, строки 1-20)
'use client';

import { useState } from 'react';
import { RefreshCw, ExternalLink } from 'lucide-react';

interface PreviewPanelProps {
  projectId: string;
  hasSandbox: boolean;
}

export function PreviewPanel({ projectId, hasSandbox }: PreviewPanelProps) {
  const [key, setKey] = useState(0);

  if (!hasSandbox) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60 p-6 text-center">
        Preview появится после запуска кодинга
      </div>
    );
  }

// AFTER
'use client';

import { useState } from 'react';
import { RefreshCw, ExternalLink, CheckCircle, Download } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface PreviewPanelProps {
  projectId: string;
  hasSandbox: boolean;
  status?: string;
}

export function PreviewPanel({ projectId, hasSandbox, status }: PreviewPanelProps) {
  const [key, setKey] = useState(0);

  if (status === 'completed') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <CheckCircle size={48} className="text-green-500" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">Проект завершён</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Превью-сервер песочницы остановлен для экономии ресурсов.
          </p>
        </div>
        <a
          href={studioApi.exportUrl(projectId)}
          download
          className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
        >
          <Download size={14} /> Скачать ZIP
        </a>
      </div>
    );
  }

  if (!hasSandbox) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60 p-6 text-center">
        Preview появится после запуска кодинга
      </div>
    );
  }
```

3. Фронт — `StudioLayout.tsx`: передать `status` в оба вызова `PreviewPanel`:

```tsx
// BEFORE (строка 187)
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} />

// AFTER
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} />
```

```tsx
// BEFORE (строка 208)
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} />

// AFTER
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} />
```

> Кнопки «Развернуть на Vercel» и «Перезапустить превью» в completion-card добавим в U11/U21, когда подключим соответствующие методы.

**Verify:**
```bash
cd src && python manage.py test studio
cd frontend && npm run build
```
Ручная: завершённый проект показывает зелёную completion-card вместо broken iframe; в БД у завершённого проекта `sandbox_container_id == ''`.

**Dependencies:** —

---

# Сессия SU2 — Волна 0: статус песочницы

**Слой:** бэк (новый endpoint) + фронт. **Миграций нет.** **Время:** ~45 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U4: Очистка pause_reason/resume_hint/pause_requested на completion

**Session:** SU2
**Wave:** 0
**Fixes/Implements:** BUG-S0-05
**Files changed:**
- `src/studio/tasks.py`

**Context:** При `pipeline.status='completed'` поля `pause_reason`/`resume_hint`/`pause_requested` остаются со старыми значениями — UI продолжает показывать старую причину паузы.

**What to do:**
В `next_step` (после правок U3) дополнить очистку pipeline-полей в ветке завершения:

```python
# BEFORE (после U3)
        project.pipeline.status = 'completed'
        project.pipeline.save(update_fields=['status'])

# AFTER
        state = project.pipeline
        state.status = 'completed'
        state.pause_reason = ''
        state.resume_hint = ''
        state.pause_requested = False
        state.save(update_fields=['status', 'pause_reason', 'resume_hint', 'pause_requested'])
```

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект с `pipeline.pause_reason='old'`, `planned_steps=1`; вызвать `next_step(project_id, 0)` (замокать `release_reserve`, `sandbox.kill_sandbox`); проверить `state.pause_reason == ''`, `state.pause_requested == False`, `state.status == 'completed'`.

**Dependencies:** U3 (общая ветка завершения в `next_step`).

---

## Commit U5: Эндпоинт GET /sandbox/ — статус песочницы

**Session:** SU2
**Wave:** 0
**Fixes/Implements:** BUG-S0-06 (backend)
**Files changed:**
- `src/studio/views/pipeline.py`
- `src/studio/urls.py`

**Context:** Фронту нужен точный статус живости sandbox для индикатора. Добавляем лёгкий эндпоинт-пинг.

**What to do:**

1. В `src/studio/views/pipeline.py` добавить view (в конец файла):

```python
class SandboxStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        cid = project.sandbox_container_id
        if not cid:
            return Response({'alive': False, 'port': project.preview_port, 'uptime_s': 0})
        alive = False
        uptime_s = 0
        try:
            from .. import sandbox as _sb
            client = _sb.get_docker()
            container = client.containers.get(cid)
            alive = container.status == 'running'
            started = container.attrs.get('State', {}).get('StartedAt', '')
            if alive and started:
                import datetime
                start = datetime.datetime.fromisoformat(started[:19])
                uptime_s = int((datetime.datetime.utcnow() - start).total_seconds())
        except Exception:
            alive = False
        return Response({'alive': alive, 'port': project.preview_port, 'uptime_s': uptime_s})
```

2. В `src/studio/urls.py` импортировать и зарегистрировать (добавить `SandboxStatusView` в import-список из `.views.pipeline` и URL):

```python
# BEFORE (urls.py, импорт pipeline-вьюх, строки 3-7)
from .views.pipeline import (
    EstimateView, PipelineStateView, PipelineRunView, PipelineEventsView,
    PipelinePauseView, PipelineResumeView, PreviewProxyView, ContextChatView,
    ApproveStepView, DeployView,
)

# AFTER
from .views.pipeline import (
    EstimateView, PipelineStateView, PipelineRunView, PipelineEventsView,
    PipelinePauseView, PipelineResumeView, PreviewProxyView, ContextChatView,
    ApproveStepView, DeployView, SandboxStatusView,
)
```

```python
# AFTER (добавить рядом с другими projects/<uuid:id>/ маршрутами, например после строки 24)
    path('projects/<uuid:id>/sandbox/', SandboxStatusView.as_view(), name='sandbox_status'),
```

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект с `sandbox_container_id=''` → GET `/sandbox/` возвращает `{'alive': False, ...}`. С непустым cid и замоканным `get_docker().containers.get` (status='running') → `alive: True`.

**Dependencies:** —

---

## Commit U6: SandboxStatusBadge в top bar

**Session:** SU2
**Wave:** 0
**Fixes/Implements:** BUG-S0-06 (frontend)
**Files changed:**
- `frontend/components/studio/SandboxStatusBadge.tsx` (новый)
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** Пользователь не видит, жив ли sandbox. Добавляем индикатор + клиентский метод к эндпоинту U5.

**What to do:**

1. В `frontend/lib/api/studio.ts` добавить тип и метод (внутри `studioApi`, после `estimate`):

```ts
// AFTER (добавить в начало файла рядом с другими интерфейсами)
export interface SandboxStatus {
  alive: boolean;
  port: number | null;
  uptime_s: number;
}

// AFTER (внутри studioApi)
  sandbox: (id: string) =>
    request<SandboxStatus>(`/studio/projects/${id}/sandbox/`),
```

2. Новый файл `frontend/components/studio/SandboxStatusBadge.tsx`:

```tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { studioApi } from '@/lib/api/studio';

interface Props {
  projectId: string;
  projectStatus: string;
}

export function SandboxStatusBadge({ projectId, projectStatus }: Props) {
  const { data } = useQuery({
    queryKey: ['studio-sandbox', projectId],
    queryFn: () => studioApi.sandbox(projectId),
    refetchInterval: 10000,
  });

  let color = 'bg-[var(--text-secondary)]';
  let label = 'Песочница остановлена';
  if (data?.alive) {
    color = 'bg-green-500';
    label = 'Песочница активна';
  } else if (projectStatus === 'coding' && !data?.alive) {
    color = 'bg-amber-500';
    label = 'Запускается…';
  }

  return (
    <span className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] shrink-0">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
```

3. В `StudioLayout.tsx` импортировать и вставить бейдж в top bar после разделителя back-кнопки:

```tsx
// AFTER (импорты)
import { SandboxStatusBadge } from './SandboxStatusBadge';
```

```tsx
// BEFORE (top bar после back-ссылки из U1)
        <div className="w-px h-4 bg-[var(--border)]" />
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />

// AFTER
        <div className="w-px h-4 bg-[var(--border)]" />
        <SandboxStatusBadge projectId={project.id} projectStatus={project.status} />
        <div className="w-px h-4 bg-[var(--border)]" />
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: во время кодинга бейдж зелёный «Песочница активна», после завершения — серый «остановлена».

**Dependencies:** U5, U1 (back-кнопка и разделитель уже в top bar).

---

# Сессия SU3 — Волна 1: прозрачность пайплайна

**Слой:** только фронт. **Миграций нет.** **Время:** ~75 мин.
**Деплой:** `docker-compose build frontend && docker-compose up -d --force-recreate frontend`

## Commit U7: Кликабельный PipelineStatus + StepDetailDrawer

**Session:** SU3
**Wave:** 1
**Fixes/Implements:** BUG-S0-04
**Files changed:**
- `frontend/components/studio/PipelineStatus.tsx`
- `frontend/components/studio/StepDetailDrawer.tsx` (новый)
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** Каждый шаг рендерится неинтерактивным `<div>`. Нельзя посмотреть, что агент сгенерировал/завалил. Делаем шаги кнопками и открываем drawer с `review_report`/`test_report`/`fix_plan`. Серверный `PipelineStateSerializer` уже `fields='__all__'` — поля приходят, нужно лишь расширить TS-тип.

**What to do:**

1. В `frontend/lib/api/studio.ts` расширить `PipelineState`:

```ts
// BEFORE (строки 38-44)
export interface PipelineState {
  status: string;
  step_index: number;
  iteration_count: number;
  pause_reason: string;
  resume_hint: string;
}

// AFTER
export interface PipelineState {
  status: string;
  step_index: number;
  iteration_count: number;
  pause_reason: string;
  resume_hint: string;
  review_report: Record<string, unknown>;
  test_report: Record<string, unknown>;
  fix_plan: Record<string, unknown>;
  last_error: string;
}
```

2. `PipelineStatus.tsx`: добавить prop `onStepClick`, заменить `<div>` шага на `<button>`:

```tsx
// BEFORE (строки 25-31)
interface PipelineStatusProps {
  projectStatus: string;
  pipelineStatus: string;
}

export function PipelineStatus({ projectStatus, pipelineStatus }: PipelineStatusProps) {
  const activeAgent = STATUS_TO_ACTIVE[projectStatus] ?? '';
  const isRunning = pipelineStatus === 'running';

// AFTER
interface PipelineStatusProps {
  projectStatus: string;
  pipelineStatus: string;
  onStepClick?: (agentKey: string) => void;
}

export function PipelineStatus({ projectStatus, pipelineStatus, onStepClick }: PipelineStatusProps) {
  const activeAgent = STATUS_TO_ACTIVE[projectStatus] ?? '';
  const isRunning = pipelineStatus === 'running';
```

```tsx
// BEFORE (строки 42-51, внутренний div шага)
          <div key={agent.key} className="flex items-center gap-1 shrink-0">
            <div
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : isDone
                  ? 'text-green-500'
                  : 'text-[var(--text-secondary)] opacity-50'
              }`}
            >

// AFTER
          <div key={agent.key} className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => onStepClick?.(agent.key)}
              title={`Подробнее: ${agent.label}`}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full hover:ring-1 hover:ring-[var(--border)] transition ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : isDone
                  ? 'text-green-500'
                  : 'text-[var(--text-secondary)] opacity-50'
              }`}
            >
```

И закрывающий тег: заменить соответствующий `</div>` (строка 60) на `</button>`.

3. Новый файл `frontend/components/studio/StepDetailDrawer.tsx`:

```tsx
'use client';

import { X } from 'lucide-react';
import type { PipelineState } from '@/lib/api/studio';

interface Props {
  agentKey: string;
  agentLabel: string;
  pipeline: PipelineState;
  stepText: string;
  onClose: () => void;
}

export function StepDetailDrawer({ agentLabel, pipeline, stepText, onClose }: Props) {
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h2 className="text-sm font-medium">{agentLabel}</h2>
        <button onClick={onClose} className="hover:text-[var(--text)] text-[var(--text-secondary)]">
          <X size={18} />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-4 text-xs">
        {stepText && (
          <section>
            <h3 className="font-medium mb-1 text-[var(--text-secondary)]">Планировалось (COMMITS.md)</h3>
            <pre className="whitespace-pre-wrap font-mono text-[11px] bg-[var(--hover)] rounded p-2">{stepText}</pre>
          </section>
        )}
        <Report title="Review report" data={pipeline.review_report} />
        <Report title="Test report" data={pipeline.test_report} />
        <Report title="Fix plan" data={pipeline.fix_plan} />
        {pipeline.last_error && (
          <section>
            <h3 className="font-medium mb-1 text-red-500">Ошибка</h3>
            <pre className="whitespace-pre-wrap font-mono text-[11px] bg-red-950/30 text-red-300 rounded p-2">{pipeline.last_error}</pre>
          </section>
        )}
      </div>
    </div>
  );
}

function Report({ title, data }: { title: string; data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <section>
      <h3 className="font-medium mb-1 text-[var(--text-secondary)]">{title}</h3>
      <pre className="whitespace-pre-wrap font-mono text-[11px] bg-[var(--hover)] rounded p-2">
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}
```

4. В `StudioLayout.tsx` поднять стейт drawer и пробросить callback. Добавить импорт `StepDetailDrawer`, стейт `drawerAgent`, маппинг ключа агента → label, вычисление текста шага из `commits_md_content`:

```tsx
// AFTER (импорты)
import { StepDetailDrawer } from './StepDetailDrawer';

// AFTER (стейты, после approving)
  const [drawerAgent, setDrawerAgent] = useState<string | null>(null);

  const AGENT_LABELS: Record<string, string> = {
    interviewer: 'Интервью', analyst: 'Анализ', planner: 'План',
    coder: 'Кодинг', reviewer: 'Ревью', tester: 'Тест', fixer: 'Фикс',
  };

  // Split COMMITS.md into step sections (mirror of backend _split_steps)
  const stepText = (() => {
    const md = project.commits_md_content || '';
    const parts = md.split(/\n(?=#{2,3}\s)/).filter((p) => p.trim());
    return parts[pipeline.step_index] ?? '';
  })();
```

```tsx
// BEFORE (PipelineStatus в top bar — из U6)
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />

// AFTER
        <PipelineStatus
          projectStatus={project.status}
          pipelineStatus={pipeline.status}
          onStepClick={(key) => setDrawerAgent(key)}
        />
```

Перед закрывающим `</div>` корневого контейнера (перед строкой 229 `</div>`) добавить рендер drawer:

```tsx
// AFTER (перед закрытием корневого div)
      {drawerAgent && (
        <StepDetailDrawer
          agentKey={drawerAgent}
          agentLabel={AGENT_LABELS[drawerAgent] ?? drawerAgent}
          pipeline={pipeline}
          stepText={stepText}
          onClose={() => setDrawerAgent(null)}
        />
      )}
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: клик по шагу пайплайна открывает drawer справа с текстом шага и JSON-отчётами; крестик закрывает.

**Dependencies:** U6 (PipelineStatus в top bar уже с props).

---

## Commit U8: fileDiff в studio.ts + Code/Diff табы

**Session:** SU3
**Wave:** 1
**Fixes/Implements:** BUG-S0-08
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** `DiffViewer.tsx` — мёртвый код. Эндпоинт `/files/{id}/diff/?ref=` работает (`FileDiffView`), но `studio.ts` не имеет метода `fileDiff`, а в средней панели нет табов Code/Diff.

**What to do:**

1. В `frontend/lib/api/studio.ts` добавить тип и метод (внутри `studioApi`, после `fileDetail`):

```ts
// AFTER (интерфейс рядом с другими)
export interface StudioFileDiff {
  path: string;
  old: string;
  new: string;
}

// AFTER (внутри studioApi)
  fileDiff: (id: string, fileId: number, ref: string) =>
    request<StudioFileDiff>(`/studio/projects/${id}/files/${fileId}/diff/?ref=${encodeURIComponent(ref)}`),
```

2. В `StudioLayout.tsx` добавить табы Code | Diff над средней панелью. Импортировать `DiffViewer`, добавить стейты и логику загрузки diff:

```tsx
// AFTER (импорты)
import { DiffViewer } from './DiffViewer';
```

```tsx
// AFTER (стейты)
  const [centerTab, setCenterTab] = useState<'code' | 'diff'>('code');
  const [diff, setDiff] = useState<{ old: string; new: string; path: string } | null>(null);

  const loadDiff = async () => {
    if (!selectedFileId) return;
    // Diff vs latest committed version
    const versions = await studioApi.commits(project.id);
    const ref = versions[0]?.git_sha;
    if (!ref) { setDiff({ old: '', new: fileDetail?.content ?? '', path: fileDetail?.path ?? '' }); return; }
    const d = await studioApi.fileDiff(project.id, selectedFileId, ref);
    setDiff(d);
  };
```

Обернуть `<CodeViewer>` в desktop-колонке (строки 179-185) в табы:

```tsx
// BEFORE (строки 179-185)
            <div className="overflow-hidden flex flex-col">
              <CodeViewer
                content={fileDetail?.content ?? ''}
                language={fileDetail?.language ?? 'text'}
                path={fileDetail?.path}
              />
            </div>

// AFTER
            <div className="overflow-hidden flex flex-col">
              <div className="flex border-b border-[var(--border)] shrink-0 text-xs">
                <button
                  onClick={() => setCenterTab('code')}
                  className={`px-3 py-1.5 ${centerTab === 'code' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-[var(--text-secondary)]'}`}
                >Код</button>
                <button
                  onClick={() => { setCenterTab('diff'); loadDiff(); }}
                  className={`px-3 py-1.5 ${centerTab === 'diff' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-[var(--text-secondary)]'}`}
                >Diff</button>
              </div>
              {centerTab === 'code' ? (
                <CodeViewer
                  content={fileDetail?.content ?? ''}
                  language={fileDetail?.language ?? 'text'}
                  path={fileDetail?.path}
                />
              ) : (
                <div className="flex-1 overflow-auto">
                  {diff ? (
                    <DiffViewer oldContent={diff.old} newContent={diff.new} path={diff.path} />
                  ) : (
                    <div className="flex items-center justify-center h-full text-xs text-[var(--text-secondary)]">Нет diff</div>
                  )}
                </div>
              )}
            </div>
```

> `DiffViewer.tsx` принимает `{ oldContent, newContent, path }` — проверить точные имена props перед коммитом и при расхождении адаптировать.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: выбрать файл → таб «Diff» показывает зелёные/красные строки относительно последнего коммита.

**Dependencies:** U2 (есть выбранный файл), U7 (сессия фронта).

---

# Сессия SU4 — Волна 1: профессиональный pause-UX

**Слой:** только фронт. **Миграций нет.** **Время:** ~60 мин.
**Деплой:** `docker-compose build frontend && docker-compose up -d --force-recreate frontend`

## Commit U9: Inline pause-баннер вместо forced ContextChat overlay

**Session:** SU4
**Wave:** 1
**Fixes/Implements:** BUG-S0-07
**Files changed:**
- `frontend/components/studio/StudioLayout.tsx`

**Context:** При `status === 'paused_on_loop'` весь рабочий стол подменяется `<ContextChat>` overlay (строки 147-157), требующим ввести подсказку. Профи хочет компактный баннер с тремя кнопками `resume({action})`, не теряя 3-панельный layout.

**What to do:**

1. Удалить overlay-блок и условие `pipeline.status !== 'paused_on_loop'` вокруг трёх-панельного layout:

```tsx
// BEFORE (строки 147-160)
      {/* ContextChat overlay for paused_on_loop */}
      {pipeline.status === 'paused_on_loop' && (
        <div className="flex-1 overflow-hidden">
          <ContextChat
            projectId={project.id}
            pauseReason={pipeline.pause_reason}
            resumeHint={pipeline.resume_hint}
            onResume={onRefresh}
          />
        </div>
      )}

      {/* Three-panel layout (hidden when paused_on_loop) */}
      {pipeline.status !== 'paused_on_loop' && (
        <div className="flex-1 overflow-hidden flex flex-col">

// AFTER
      {/* Three-panel layout (always shown; pause handled by inline banner) */}
      <div className="flex-1 overflow-hidden flex flex-col">
```

И убрать парный закрывающий `)}` у этого условного блока (строка 228 `      )}` перед последним `</div>` — заменить на просто закрытие div). Итог: layout рендерится всегда.

2. Добавить хендлеры resume и стейт inline-подсказки (после `handlePause`):

```tsx
// AFTER (стейты/хендлеры)
  const [hintOpen, setHintOpen] = useState(false);
  const [hintText, setHintText] = useState('');
  const [resuming, setResuming] = useState(false);

  const doResume = async (action: 'continue' | 'with_hint' | 'skip_step', hint?: string) => {
    setResuming(true);
    try {
      await studioApi.resume(project.id, { action, hint });
      setHintOpen(false);
      setHintText('');
      onRefresh();
    } finally {
      setResuming(false);
    }
  };
```

3. Расширить approval-баннер: показывать compact-баннер при `paused_on_loop` тоже. Сразу после блока `isAwaitingApproval` (после строки 127) добавить:

```tsx
// AFTER (после блока isAwaitingApproval)
      {pipeline.status === 'paused_on_loop' && (
        <div className="flex flex-col gap-2 px-4 py-2.5 bg-amber-950/40 border-b border-amber-800/50 shrink-0">
          <div className="flex items-center gap-3">
            <CheckCircle size={16} className="text-amber-400 shrink-0" />
            <p className="text-xs text-amber-300 flex-1">{pipeline.pause_reason || 'Пайплайн на паузе'}</p>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => doResume('continue')} disabled={resuming} className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium">Продолжить</button>
              <button onClick={() => setHintOpen((v) => !v)} className="border border-amber-700 hover:bg-amber-900/40 text-amber-200 px-3 py-1.5 rounded-lg text-xs font-medium">Подсказать</button>
              <button onClick={() => doResume('skip_step')} disabled={resuming} className="border border-amber-700 hover:bg-amber-900/40 text-amber-200 px-3 py-1.5 rounded-lg text-xs font-medium">Пропустить шаг</button>
            </div>
          </div>
          {hintOpen && (
            <div className="flex gap-2">
              <textarea
                value={hintText}
                onChange={(e) => setHintText(e.target.value)}
                placeholder="Подсказка агенту..."
                className="flex-1 text-xs bg-[var(--bg)] border border-amber-800/50 rounded p-2 resize-none h-16"
              />
              <button onClick={() => doResume('with_hint', hintText)} disabled={resuming || !hintText.trim()} className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-3 rounded-lg text-xs font-medium self-stretch">Отправить</button>
            </div>
          )}
        </div>
      )}
```

> `ContextChat` импорт остаётся (используется в U10 как боковая панель). Если линтер ругается на неиспользуемый импорт между U9 и U10 — оставить, U10 в той же сессии его задействует.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: на `paused_on_loop` виден компактный баннер с тремя кнопками, 3-панельный layout сохраняется; «Подсказать» раскрывает textarea.

**Dependencies:** U3 (status в PreviewPanel — не критично, но та же область).

---

## Commit U10: ContextChat как опциональная боковая панель (toggle)

**Session:** SU4
**Wave:** 1
**Fixes/Implements:** BUG-S0-07 (часть 2 — чат как панель, не overlay)
**Files changed:**
- `frontend/components/studio/StudioLayout.tsx`

**Context:** После U9 `ContextChat` больше не overlay. Дать его как сворачиваемую боковую панель по кнопке «Открыть чат с агентом».

**What to do:**

1. Стейт toggle (после стейтов U9):

```tsx
// AFTER
  const [chatOpen, setChatOpen] = useState(false);
```

2. Кнопку «Открыть чат с агентом» добавить в pause-баннер `paused_on_loop` (рядом с тремя кнопками из U9):

```tsx
// AFTER (в ряд кнопок paused_on_loop)
              <button onClick={() => setChatOpen((v) => !v)} className="border border-amber-700 hover:bg-amber-900/40 text-amber-200 px-3 py-1.5 rounded-lg text-xs font-medium">Чат с агентом</button>
```

3. Рендер боковой панели: обернуть desktop 3-колоночную сетку так, чтобы при `chatOpen` появлялась 4-я колонка. Минимально — рядом с `<div className="hidden md:grid ...">` добавить fl-контейнер. Простейший вариант — рендерить ContextChat как fixed-панель справа:

```tsx
// AFTER (перед закрытием корневого div, рядом с StepDetailDrawer из U7)
      {chatOpen && (
        <div className="fixed inset-y-0 right-0 w-full max-w-sm bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-40 flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)]">
            <span className="text-sm font-medium">Чат с агентом</span>
            <button onClick={() => setChatOpen(false)} className="text-[var(--text-secondary)] hover:text-[var(--text)] text-xs">Закрыть</button>
          </div>
          <div className="flex-1 overflow-hidden">
            <ContextChat
              projectId={project.id}
              pauseReason={pipeline.pause_reason}
              resumeHint={pipeline.resume_hint}
              onResume={onRefresh}
            />
          </div>
        </div>
      )}
```

> Проверить актуальные props `ContextChat` (`projectId`, `pauseReason`, `resumeHint`, `onResume`) — они совпадают с тем, что было в overlay (StudioLayout строки 150-154). `ContextChat` уже умеет звать `studioApi.contextChat` (метод существует).

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: кнопка «Чат с агентом» открывает/закрывает боковую панель; чат отвечает (бэкенд `ContextChatView` уже работает).

**Dependencies:** U9.

---

# Сессия SU5 — Волна 1: кнопки действий + горячие клавиши

**Слой:** только фронт. **Миграций нет.** **Время:** ~60 мин.
**Деплой:** `docker-compose build frontend && docker-compose up -d --force-recreate frontend`

## Commit U11: Кнопки top bar — «Развернуть на Vercel» + «Поделиться»

**Session:** SU5
**Wave:** 1
**Fixes/Implements:** Раздел 1 пункт 10, Раздел 5 (Vercel/Share buttons)
**Files changed:**
- `frontend/components/studio/StudioLayout.tsx`

**Context:** `studioApi.deploy(id)` (POST `/deploy/`) уже есть, но кнопки в UI нет. Share-ссылка просто копирует URL проекта (collaborators-эндпоинт — отдельная фича).

**What to do:**
В top bar в блок `ml-auto` (строки 80-110) добавить кнопки. «Поделиться» доступна всегда, «Vercel» — при `completed`:

```tsx
// AFTER (импорты — добавить Rocket, Share2)
import { Play, Pause, Files, Code2, Monitor, CheckCircle, Download, ArrowLeft, Rocket, Share2 } from 'lucide-react';

// AFTER (хендлеры)
  const [deploying, setDeploying] = useState(false);
  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await studioApi.deploy(project.id);
      onRefresh();
    } finally {
      setDeploying(false);
    }
  };
  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
  };
```

```tsx
// BEFORE (внутри ml-auto блока, после кнопки "Скачать ZIP", строка ~109)
          )}
        </div>
      </div>

// AFTER
          )}
          {isCompleted && (
            <button
              onClick={handleDeploy}
              disabled={deploying}
              className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            >
              <Rocket size={14} />
              {deploying ? 'Публикуем...' : 'Развернуть на Vercel'}
            </button>
          )}
          <button
            onClick={handleShare}
            title="Скопировать ссылку"
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          >
            <Share2 size={14} />
            Поделиться
          </button>
        </div>
      </div>
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: завершённый проект показывает кнопку «Развернуть на Vercel»; «Поделиться» копирует URL в буфер.

**Dependencies:** —

---

## Commit U12: Горячие клавиши + ShortcutsModal

**Session:** SU5
**Wave:** 1
**Fixes/Implements:** Раздел 1.7
**Files changed:**
- `frontend/components/studio/ShortcutsModal.tsx` (новый)
- `frontend/components/studio/StudioLayout.tsx`

**Context:** Нет ни одной горячей клавиши. Профи ждут Ctrl+S (сохранить), Ctrl+` (лог), Ctrl+Enter (продолжить на паузе), Esc (закрыть). Плюс «?» показывает список.

**What to do:**

1. Новый файл `frontend/components/studio/ShortcutsModal.tsx`:

```tsx
'use client';

import { X } from 'lucide-react';

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: 'Ctrl/Cmd + S', action: 'Сохранить файл' },
  { keys: 'Ctrl/Cmd + `', action: 'Лог агентов' },
  { keys: 'Ctrl/Cmd + K', action: 'Поиск файлов' },
  { keys: 'Ctrl/Cmd + Enter', action: 'Продолжить на паузе' },
  { keys: 'Esc', action: 'Закрыть панель' },
];

export function ShortcutsModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium">Горячие клавиши</h2>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text)]"><X size={18} /></button>
        </div>
        <ul className="space-y-2">
          {SHORTCUTS.map((s) => (
            <li key={s.keys} className="flex items-center justify-between text-xs">
              <span className="text-[var(--text-secondary)]">{s.action}</span>
              <kbd className="font-mono bg-[var(--hover)] px-2 py-0.5 rounded">{s.keys}</kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

2. В `StudioLayout.tsx` импортировать, добавить стейт и глобальный обработчик клавиш:

```tsx
// AFTER (импорты)
import { ShortcutsModal } from './ShortcutsModal';
import { HelpCircle } from 'lucide-react';

// AFTER (стейты)
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === '`') { e.preventDefault(); setLogOpen((v) => !v); }
      else if (mod && e.key === 'Enter' && pipeline.status === 'paused_on_loop') { e.preventDefault(); doResume('continue'); }
      else if (e.key === 'Escape') { setShortcutsOpen(false); setDrawerAgent(null); setChatOpen(false); }
      else if (e.key === '?' && !mod) { setShortcutsOpen(true); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipeline.status]);
```

3. Кнопка «?» в top bar (в `ml-auto` блоке, первой):

```tsx
// AFTER (в начале ml-auto блока)
          <button onClick={() => setShortcutsOpen(true)} title="Горячие клавиши" className="text-[var(--text-secondary)] hover:text-[var(--text)] p-1.5">
            <HelpCircle size={16} />
          </button>
```

4. Рендер модалки (рядом с другими порталами):

```tsx
// AFTER
      {shortcutsOpen && <ShortcutsModal onClose={() => setShortcutsOpen(false)} />}
```

> Ctrl+S и Ctrl+K привязываются в U13/U15 (там появляются save и search). Здесь — базовый набор.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: «?» открывает модалку; Esc закрывает панели; Ctrl+` тогглит лог.

**Dependencies:** U7 (drawerAgent), U9 (doResume), U10 (chatOpen).

---

# Сессия SU6 — Волна 2: редактирование и поиск

**Слой:** фронт + бэк. **Миграций нет.** **Время:** ~90 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U13: Редактируемый CodeViewer (CodeMirror) + Ctrl+S → PATCH

**Session:** SU6
**Wave:** 2
**Fixes/Implements:** Раздел 2.2
**Files changed:**
- `frontend/package.json`
- `frontend/components/studio/CodeViewer.tsx`
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** `CodeViewer` сейчас read-only (`<pre><code>` + hljs). Дать редактирование через CodeMirror 6 с сохранением через PATCH `/files/{id}/`. Бэкенд `FileDetailView` (PATCH) + `sync_manual_edit.delay` уже есть.

**What to do:**

1. Установить CodeMirror:
```bash
cd frontend && npm i @uiw/react-codemirror @codemirror/lang-javascript @codemirror/lang-html @codemirror/lang-css @codemirror/theme-one-dark
```

2. Добавить метод в `studio.ts` (внутри `studioApi`):

```ts
// AFTER
  updateFile: (id: string, fileId: number, content: string) =>
    request<StudioFileDetail>(`/studio/projects/${id}/files/${fileId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),
```

3. Переписать `CodeViewer.tsx` на редактируемый компонент. Сохранить старый read-only режим как fallback, добавить `editable` и `onSave`:

```tsx
// AFTER (CodeViewer.tsx — полная новая версия)
'use client';

import { useEffect, useState } from 'react';
import { Copy, Check, Save } from 'lucide-react';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { oneDark } from '@codemirror/theme-one-dark';

interface CodeViewerProps {
  content: string;
  language: string;
  path?: string;
  editable?: boolean;
  onSave?: (content: string) => Promise<void> | void;
}

function extToLang(path?: string) {
  if (!path) return javascript({ jsx: true, typescript: true });
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  return javascript({ jsx: true, typescript: true });
}

export function CodeViewer({ content, language, path, editable, onSave }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => { setValue(content); setDirty(false); }, [content, path]);

  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleSave = async () => {
    if (!onSave || !dirty) return;
    setSaving(true);
    try { await onSave(value); setDirty(false); } finally { setSaving(false); }
  };

  if (!content && !editable) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60">
        Выберите файл
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {path && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] text-xs text-[var(--text-secondary)] shrink-0">
          <span className="font-mono">{path}{dirty ? ' •' : ''}</span>
          <div className="flex items-center gap-3">
            {editable && (
              <button onClick={handleSave} disabled={!dirty || saving} className="flex items-center gap-1 hover:text-[var(--text)] disabled:opacity-40 transition-colors">
                <Save size={14} />{saving ? 'Сохранение…' : 'Сохранить'}
              </button>
            )}
            <button onClick={handleCopy} className="flex items-center gap-1 hover:text-[var(--text)] transition-colors">
              {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <CodeMirror
          value={value}
          theme={oneDark}
          editable={!!editable}
          extensions={[extToLang(path)]}
          onChange={(v) => { setValue(v); setDirty(true); }}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave(); }
          }}
        />
      </div>
    </div>
  );
}
```

> `language` остаётся в props для обратной совместимости (используется как fallback при необходимости). hljs-импорт убран — подсветку даёт CodeMirror.

4. В `StudioLayout.tsx` сделать редактор editable и пробросить save (заменить оба вызова `CodeViewer` — desktop в табе Code из U8 и mobile):

```tsx
// AFTER (хендлер сохранения)
  const handleSaveFile = async (newContent: string) => {
    if (!selectedFileId) return;
    const updated = await studioApi.updateFile(project.id, selectedFileId, newContent);
    setFileDetail(updated);
    refetchFromParent?.();
  };
```

> `refetchFromParent` нет — просто вызвать `onRefresh()`. Используем `onRefresh`.

```tsx
// BEFORE (CodeViewer в табе Code — из U8)
                <CodeViewer
                  content={fileDetail?.content ?? ''}
                  language={fileDetail?.language ?? 'text'}
                  path={fileDetail?.path}
                />

// AFTER
                <CodeViewer
                  content={fileDetail?.content ?? ''}
                  language={fileDetail?.language ?? 'text'}
                  path={fileDetail?.path}
                  editable={project.status !== 'completed'}
                  onSave={handleSaveFile}
                />
```

И аналогично mobile-вариант (строки 200-205) — добавить `editable`/`onSave`.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: открыть файл, изменить, Ctrl+S → индикатор «Сохранение…», изменение уходит в sandbox (через `sync_manual_edit`).

**Dependencies:** U8 (таб Code), U12 (Ctrl+S как часть hotkeys — здесь привязан внутри CodeMirror).

---

## Commit U14: Бэкенд — POST /search/ (поиск по файлам)

**Session:** SU6
**Wave:** 2
**Fixes/Implements:** Раздел 2.3 (backend)
**Files changed:**
- `src/studio/views/files.py`
- `src/studio/urls.py`

**Context:** Нет поиска по содержимому файлов проекта. Добавляем БД-поиск по `StudioFile.content`.

**What to do:**

1. В `src/studio/views/files.py` добавить view:

```python
class SearchFilesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return Response([])
        files = StudioFile.objects.filter(
            project_id=id, project__user=request.user, content__icontains=q,
        )
        results = []
        for f in files[:50]:
            for i, line in enumerate(f.content.splitlines(), start=1):
                if q.lower() in line.lower():
                    results.append({
                        'file_id': f.id, 'path': f.path,
                        'line': i, 'snippet': line.strip()[:200],
                    })
                    if len([r for r in results if r['file_id'] == f.id]) >= 5:
                        break
        return Response(results[:100])
```

2. В `urls.py` импортировать `SearchFilesView` из `.views.files` и зарегистрировать:

```python
# BEFORE (urls.py, импорт files-вьюх)
from .views.files import FileTreeView, FileDetailView, FileDiffView, CommitHistoryView, RollbackView, ExportView

# AFTER
from .views.files import FileTreeView, FileDetailView, FileDiffView, CommitHistoryView, RollbackView, ExportView, SearchFilesView
```

```python
# AFTER (URL рядом с files-маршрутами)
    path('projects/<uuid:id>/search/', SearchFilesView.as_view(), name='search_files'),
```

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект с файлом `a.tsx` содержащим `useState`; GET `/search/?q=useState` → результат содержит `{file_id, path:'a.tsx', line, snippet}`.

**Dependencies:** —

---

## Commit U15: SearchFilesModal (Ctrl+Shift+F / Ctrl+K)

**Session:** SU6
**Wave:** 2
**Fixes/Implements:** Раздел 2.3 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/SearchFilesModal.tsx` (новый)
- `frontend/components/studio/StudioLayout.tsx`

**Context:** Дать оверлей поиска по файлам, открываемый по Ctrl+K / Ctrl+Shift+F.

**What to do:**

1. Метод и тип в `studio.ts`:

```ts
// AFTER (тип)
export interface FileSearchResult {
  file_id: number;
  path: string;
  line: number;
  snippet: string;
}

// AFTER (внутри studioApi)
  searchFiles: (id: string, q: string) =>
    request<FileSearchResult[]>(`/studio/projects/${id}/search/?q=${encodeURIComponent(q)}`),
```

2. Новый файл `frontend/components/studio/SearchFilesModal.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { Search, X } from 'lucide-react';
import { studioApi, type FileSearchResult } from '@/lib/api/studio';

interface Props {
  projectId: string;
  onClose: () => void;
  onPick: (fileId: number) => void;
}

export function SearchFilesModal({ projectId, onClose, onPick }: Props) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<FileSearchResult[]>([]);

  const run = async (value: string) => {
    setQ(value);
    if (value.trim().length < 2) { setResults([]); return; }
    setResults(await studioApi.searchFiles(projectId, value));
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-24" onClick={onClose}>
      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-xl w-full max-w-lg overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)]">
          <Search size={16} className="text-[var(--text-secondary)]" />
          <input
            autoFocus
            value={q}
            onChange={(e) => run(e.target.value)}
            placeholder="Поиск по файлам..."
            className="flex-1 bg-transparent text-sm outline-none"
          />
          <button onClick={onClose}><X size={16} className="text-[var(--text-secondary)]" /></button>
        </div>
        <div className="max-h-80 overflow-auto">
          {results.map((r, idx) => (
            <button
              key={`${r.file_id}-${r.line}-${idx}`}
              onClick={() => { onPick(r.file_id); onClose(); }}
              className="w-full text-left px-3 py-2 hover:bg-[var(--hover)] border-b border-[var(--border)]"
            >
              <div className="text-xs font-mono text-[var(--text-secondary)]">{r.path}:{r.line}</div>
              <div className="text-xs font-mono truncate">{r.snippet}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

3. В `StudioLayout.tsx` стейт + хоткей + рендер:

```tsx
// AFTER (импорт)
import { SearchFilesModal } from './SearchFilesModal';

// AFTER (стейт)
  const [searchOpen, setSearchOpen] = useState(false);
```

В обработчик `onKey` из U12 добавить:

```tsx
// AFTER (внутри onKey)
      else if (mod && (e.key === 'k' || (e.shiftKey && e.key.toLowerCase() === 'f'))) {
        e.preventDefault(); setSearchOpen(true);
      }
```

Рендер:

```tsx
// AFTER
      {searchOpen && (
        <SearchFilesModal
          projectId={project.id}
          onClose={() => setSearchOpen(false)}
          onPick={(fileId) => handleFileSelect(fileId)}
        />
      )}
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: Ctrl+K открывает поиск; ввод подстроки показывает результаты; клик выбирает файл.

**Dependencies:** U14, U12 (общий onKey).

---

# Сессия SU7 — Волна 2: превью и раскладка

**Слой:** только фронт. **Миграций нет.** **Время:** ~75 мин.
**Деплой:** `docker-compose build frontend && docker-compose up -d --force-recreate frontend`

## Commit U16: Мобильное превью toggle (375 / 768 / 100%)

**Session:** SU7
**Wave:** 2
**Fixes/Implements:** Раздел 3.4
**Files changed:**
- `frontend/components/studio/PreviewPanel.tsx`

**Context:** Нет способа проверить адаптивность. Добавляем переключатель ширины iframe.

**What to do:**
В `PreviewPanel.tsx` добавить стейт ширины и кнопки в toolbar:

```tsx
// AFTER (импорты)
import { RefreshCw, ExternalLink, CheckCircle, Download, Smartphone, Tablet, Monitor } from 'lucide-react';

// AFTER (стейт, после useState(0))
  const [width, setWidth] = useState<'100%' | '768px' | '375px'>('100%');
```

В toolbar (после `<span>preview</span>`, перед закрытием toolbar-div) добавить переключатель:

```tsx
// AFTER (в toolbar)
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => setWidth('375px')} title="375px" className={width === '375px' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}><Smartphone size={16} /></button>
          <button onClick={() => setWidth('768px')} title="768px" className={width === '768px' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}><Tablet size={16} /></button>
          <button onClick={() => setWidth('100%')} title="100%" className={width === '100%' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}><Monitor size={16} /></button>
        </div>
```

Обернуть iframe в центрирующий контейнер с шириной:

```tsx
// BEFORE
      <iframe
        key={key}
        src={src}
        className="flex-1 w-full border-0"
        title="Sandbox preview"
      />

// AFTER
      <div className="flex-1 overflow-auto flex justify-center bg-[var(--hover)]">
        <iframe
          key={key}
          src={src}
          style={{ width }}
          className="h-full border-0 bg-white"
          title="Sandbox preview"
        />
      </div>
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: переключение 375/768/100% меняет ширину iframe, контент центрируется.

**Dependencies:** U3 (PreviewPanel уже принимает status, импорты расширены).

---

## Commit U17: Resizable панели (react-resizable-panels)

**Session:** SU7
**Wave:** 2
**Fixes/Implements:** Раздел 5 (split/merge панелей)
**Files changed:**
- `frontend/package.json`
- `frontend/components/studio/StudioLayout.tsx`

**Context:** Desktop-сетка фиксированная `md:grid-cols-[220px_1fr_1fr]`. Дать draggable-разделители с сохранением раскладки в localStorage.

**What to do:**

1. Установить:
```bash
cd frontend && npm i react-resizable-panels
```

2. В `StudioLayout.tsx` заменить desktop-grid на `PanelGroup`. Импорт:

```tsx
// AFTER (импорт)
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
```

```tsx
// BEFORE (desktop сетка, строка 163)
          <div className="hidden md:grid md:grid-cols-[220px_1fr_1fr] flex-1 overflow-hidden divide-x divide-[var(--border)]">
            <div className="overflow-hidden flex flex-col">
              {/* FileTree + GitHistory */}
            ...
            <div className="overflow-hidden flex flex-col">
              {/* CodeViewer/Diff */}
            ...
            <div className="overflow-hidden flex flex-col">
              <PreviewPanel ... />
            </div>
          </div>

// AFTER
          <PanelGroup direction="horizontal" autoSaveId="studio-layout" className="hidden md:flex flex-1 overflow-hidden">
            <Panel defaultSize={18} minSize={12} className="overflow-hidden flex flex-col border-r border-[var(--border)]">
              {/* существующий блок FileTree + GitHistory без изменений */}
            </Panel>
            <PanelResizeHandle className="w-px bg-[var(--border)] hover:bg-blue-500 transition-colors" />
            <Panel defaultSize={41} minSize={20} className="overflow-hidden flex flex-col">
              {/* существующий блок CodeViewer/Diff табов без изменений */}
            </Panel>
            <PanelResizeHandle className="w-px bg-[var(--border)] hover:bg-blue-500 transition-colors" />
            <Panel defaultSize={41} minSize={20} className="overflow-hidden flex flex-col">
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} />
            </Panel>
          </PanelGroup>
```

> Сохранить внутреннее содержимое трёх старых `<div>` без изменений, лишь поменять обёртки на `<Panel>`. `autoSaveId` обеспечивает сохранение раскладки в localStorage. Mobile-вариант (строки 191-210) НЕ трогать.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: тянуть разделители между панелями — ширины меняются; после перезагрузки раскладка сохраняется.

**Dependencies:** U8 (табы Code/Diff в центральной панели), U16.

---

# Сессия SU8 — Волна 2: настройки проекта

**Слой:** бэк (миграция) + фронт. **Время:** ~75 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U18: Бэкенд — PATCH /settings/ (модель, max_iterations, режим, бюджет)

**Session:** SU8
**Wave:** 2
**Fixes/Implements:** Раздел 5 («Настройки на проект»)
**Files changed:**
- `src/studio/models.py` (миграция)
- `src/studio/views/projects.py`
- `src/studio/urls.py`

**Context:** Нет per-project настроек модели Coder, лимита итераций, бюджета звёзд. Добавляем поля и эндпоинт.

**What to do:**

1. В `src/studio/models.py` в `StudioProject` добавить поля:

```python
# AFTER (в StudioProject)
    coder_model = models.CharField(max_length=20, choices=[('fast', 'DeepSeek V3'), ('smart', 'Opus 4.8')], default='fast')
    max_iterations = models.IntegerField(default=0)  # 0 = use global STUDIO_MAX_ITERATIONS
    max_stars_budget = models.IntegerField(default=0)  # 0 = no cap
    auto_deploy = models.BooleanField(default=False)
```

Затем:
```bash
cd src && python manage.py makemigrations studio && python manage.py migrate
```

2. В `src/studio/views/projects.py` добавить view:

```python
class ProjectSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    ALLOWED = {'coder_model', 'max_iterations', 'max_stars_budget', 'auto_deploy', 'mode'}

    def patch(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        updated = []
        for key in self.ALLOWED:
            if key in request.data:
                setattr(project, key, request.data[key])
                updated.append(key)
        if updated:
            project.save(update_fields=updated)
        return Response({
            'coder_model': project.coder_model,
            'max_iterations': project.max_iterations,
            'max_stars_budget': project.max_stars_budget,
            'auto_deploy': project.auto_deploy,
            'mode': project.mode,
        })
```

3. URL в `urls.py` (импортировать `ProjectSettingsView` из `.views.projects`):

```python
    path('projects/<uuid:id>/settings/', ProjectSettingsView.as_view(), name='project_settings'),
```

> `coder_model`/`max_iterations` фактически читаются пайплайном в Coder/iteration-логике — подключение к `tasks.py` (использовать `project.coder_model` вместо эвристики) опционально и относится к Волне 3 (U34/роутинг). Здесь только хранение + API.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: PATCH `/settings/` с `{coder_model:'smart', max_iterations:3}` → поля сохранены, ответ их отражает.

**Dependencies:** —

---

## Commit U19: ProjectSettingsModal (шестерёнка в top bar)

**Session:** SU8
**Wave:** 2
**Fixes/Implements:** Раздел 5 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/ProjectSettingsModal.tsx` (новый)
- `frontend/components/studio/StudioLayout.tsx`

**Context:** UI для настроек проекта из U18.

**What to do:**

1. Расширить тип `StudioProject` и добавить метод в `studio.ts`:

```ts
// AFTER (поля StudioProject — добавить)
  coder_model: 'fast' | 'smart';
  max_iterations: number;
  max_stars_budget: number;
  auto_deploy: boolean;

// AFTER (метод)
  updateSettings: (id: string, data: Partial<{ coder_model: string; max_iterations: number; max_stars_budget: number; auto_deploy: boolean; mode: string }>) =>
    request<Record<string, unknown>>(`/studio/projects/${id}/settings/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
```

2. Новый файл `frontend/components/studio/ProjectSettingsModal.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { studioApi, type StudioProject } from '@/lib/api/studio';

interface Props { project: StudioProject; onClose: () => void; onSaved: () => void; }

export function ProjectSettingsModal({ project, onClose, onSaved }: Props) {
  const [model, setModel] = useState(project.coder_model);
  const [iterations, setIterations] = useState(project.max_iterations);
  const [budget, setBudget] = useState(project.max_stars_budget);
  const [mode, setMode] = useState(project.mode);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await studioApi.updateSettings(project.id, { coder_model: model, max_iterations: iterations, max_stars_budget: budget, mode });
      onSaved(); onClose();
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-sm space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Настройки проекта</h2>
          <button onClick={onClose}><X size={18} className="text-[var(--text-secondary)]" /></button>
        </div>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Модель Coder</span>
          <select value={model} onChange={(e) => setModel(e.target.value as 'fast' | 'smart')} className="w-full bg-[var(--hover)] rounded p-2">
            <option value="fast">DeepSeek V3 (быстро)</option>
            <option value="smart">Opus 4.8 (качество)</option>
          </select>
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Режим</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as StudioProject['mode'])} className="w-full bg-[var(--hover)] rounded p-2">
            <option value="auto">Авто</option>
            <option value="semi">Полу-авто</option>
            <option value="manual">Ручной</option>
          </select>
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Макс. итераций на шаг (0 = по умолчанию)</span>
          <input type="number" min={0} value={iterations} onChange={(e) => setIterations(Number(e.target.value))} className="w-full bg-[var(--hover)] rounded p-2" />
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Бюджет звёзд (0 = без лимита)</span>
          <input type="number" min={0} value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="w-full bg-[var(--hover)] rounded p-2" />
        </label>
        <button onClick={save} disabled={saving} className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-xs font-medium">
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
}
```

3. В `StudioLayout.tsx` — кнопка-шестерёнка в top bar + рендер:

```tsx
// AFTER (импорт)
import { ProjectSettingsModal } from './ProjectSettingsModal';
import { Settings } from 'lucide-react';

// AFTER (стейт)
  const [settingsOpen, setSettingsOpen] = useState(false);
```

```tsx
// AFTER (в ml-auto блоке)
          <button onClick={() => setSettingsOpen(true)} title="Настройки проекта" className="text-[var(--text-secondary)] hover:text-[var(--text)] p-1.5">
            <Settings size={16} />
          </button>
```

```tsx
// AFTER (рендер)
      {settingsOpen && (
        <ProjectSettingsModal project={project} onClose={() => setSettingsOpen(false)} onSaved={onRefresh} />
      )}
```

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: шестерёнка открывает модалку, сохранение меняет настройки проекта.

**Dependencies:** U18.

---

# Сессия SU9 — Волна 2: перезапуск превью + файловый CRUD

**Слой:** бэк + фронт. **Миграций нет.** **Время:** ~90 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U20: Бэкенд — POST /preview/restart/ (re-spawn sandbox)

**Session:** SU9
**Wave:** 2
**Fixes/Implements:** Раздел 1.3 / Раздел 5 («Перезапустить превью»)
**Files changed:**
- `src/studio/tasks.py`
- `src/studio/views/pipeline.py`
- `src/studio/urls.py`

**Context:** Завершённый проект не имеет живого sandbox. Дать кнопку «Перезапустить превью» → re-spawn контейнер и записать текущие `StudioFile`.

**What to do:**

1. Задача в `tasks.py`:

```python
@shared_task(queue=QUEUE)
def restart_preview(project_id):
    project = StudioProject.objects.get(id=project_id)
    # Kill old container if any
    if project.sandbox_container_id:
        try:
            sandbox.kill_sandbox(project.sandbox_container_id)
        except Exception:
            pass
    try:
        cid = sandbox.spawn_sandbox(project_id)
        files = {f.path: f.content for f in project.files.all()} or {'package.json': '{"name":"app","private":true}'}
        sandbox.write_files(cid, files)
        sandbox.install_deps(cid)
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
        project.sandbox_container_id = cid
        project.preview_port = 3000
        project.save(update_fields=['sandbox_container_id', 'preview_port'])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Превью перезапущено'})
    except Exception as exc:
        publish_event(project_id, {'agent': 'system', 'level': 'error', 'text': f'Не удалось перезапустить превью: {exc}'})
```

> Сверить имена функций sandbox (`spawn_sandbox`, `write_files`, `install_deps`, `isolate`, `start_dev_server`, `kill_sandbox`) с `run_pipeline` в `tasks.py` (строки ~190-200) — они там используются именно так.

2. View в `views/pipeline.py`:

```python
class PreviewRestartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import restart_preview
        restart_preview.delay(str(project.id))
        return Response({'status': 'restarting'}, status=202)
```

3. URL (импортировать `PreviewRestartView`). ВАЖНО: маршрут `preview/restart/` должен идти ДО общего `re_path(... preview/(?P<path>.*) ...)`, иначе `restart/` попадёт в path прокси:

```python
# AFTER (вставить ПЕРЕД re_path preview_proxy, т.е. до строки 36)
    path('projects/<uuid:id>/preview/restart/', PreviewRestartView.as_view(), name='preview_restart'),
```

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `restart_preview.delay`; POST `/preview/restart/` → 202 и delay вызван с project_id. Отдельно: прямой вызов `restart_preview` с замоканным sandbox устанавливает `sandbox_container_id`.

**Dependencies:** U3 (sandbox_container_id очищается на completion — restart его восстанавливает).

---

## Commit U21: PreviewPanel — кнопка «Перезапустить превью» в completion-card

**Session:** SU9
**Wave:** 2
**Fixes/Implements:** Раздел 1.3 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/PreviewPanel.tsx`

**Context:** Подключить кнопку перезапуска к completion-card из U3.

**What to do:**

1. Метод в `studio.ts`:

```ts
// AFTER (внутри studioApi)
  restartPreview: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/preview/restart/`, { method: 'POST' }),
```

2. В completion-card `PreviewPanel.tsx` (блок `status === 'completed'` из U3) добавить кнопки Vercel и Restart:

```tsx
// AFTER (импорт)
import { RefreshCw, ExternalLink, CheckCircle, Download, Smartphone, Tablet, Monitor, Rocket, RotateCw } from 'lucide-react';

// AFTER (в completion-card, рядом с кнопкой "Скачать ZIP")
        <div className="flex flex-wrap items-center justify-center gap-2">
          <a href={studioApi.exportUrl(projectId)} download className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium">
            <Download size={14} /> Скачать ZIP
          </a>
          <button onClick={() => studioApi.deploy(projectId)} className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium">
            <Rocket size={14} /> Развернуть на Vercel
          </button>
          <button onClick={() => studioApi.restartPreview(projectId)} className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium">
            <RotateCw size={14} /> Перезапустить превью
          </button>
        </div>
```

> Заменить одиночную ссылку «Скачать ZIP» из U3 на этот блок из трёх кнопок.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: на completion-card три кнопки; «Перезапустить превью» шлёт POST.

**Dependencies:** U20, U3.

---

## Commit U22: FileTree CRUD — создание и удаление файлов

**Session:** SU9
**Wave:** 2
**Fixes/Implements:** Раздел 2.2 (файловые операции)
**Files changed:**
- `src/studio/views/files.py`
- `src/studio/urls.py`
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/FileTree.tsx`

**Context:** Сейчас файлы только просматриваются. Дать создание/удаление с синком в sandbox (`FileDetailView` уже `RetrieveUpdate`; добавим Create+Destroy).

**What to do:**

1. Бэкенд — в `views/files.py` сделать `FileTreeView` ещё и Create, а `FileDetailView` — Destroy:

```python
# BEFORE
class FileTreeView(generics.ListAPIView):

# AFTER
class FileTreeView(generics.ListCreateAPIView):
```

Добавить в `FileTreeView`:
```python
    def get_serializer_class(self):
        return StudioFileDetailSerializer if self.request.method == 'POST' else StudioFileSerializer

    def perform_create(self, serializer):
        project = StudioProject.objects.get(id=self.kwargs['id'], user=self.request.user)
        instance = serializer.save(project=project, last_modified_by='user')
        from ..tasks import sync_manual_edit
        sync_manual_edit.delay(str(project.id), instance.pk)
```

```python
# BEFORE
class FileDetailView(generics.RetrieveUpdateAPIView):

# AFTER
class FileDetailView(generics.RetrieveUpdateDestroyAPIView):
```

Добавить в `FileDetailView`:
```python
    def perform_destroy(self, instance):
        project_id = str(self.kwargs['id'])
        path = instance.path
        cid = instance.project.sandbox_container_id
        instance.delete()
        if cid:
            from ..tasks import delete_sandbox_file
            delete_sandbox_file.delay(project_id, path)
```

Задача `delete_sandbox_file` в `tasks.py`:
```python
@shared_task(queue=QUEUE)
def delete_sandbox_file(project_id, path):
    project = StudioProject.objects.get(id=project_id)
    if project.sandbox_container_id:
        try:
            sandbox.exec_command(project.sandbox_container_id, f'rm -f {path}')
        except Exception:
            pass
```

> `exec_command` — проверить точное имя helper в `sandbox.py` (в STUDIO_COMMITS использовался `exec_command`).

2. Фронт — методы в `studio.ts`:

```ts
// AFTER
  createFile: (id: string, path: string, content = '') =>
    request<StudioFileDetail>(`/studio/projects/${id}/files/`, {
      method: 'POST', body: JSON.stringify({ path, content, language: '' }),
    }),
  deleteFile: (id: string, fileId: number) =>
    request<void>(`/studio/projects/${id}/files/${fileId}/`, { method: 'DELETE' }),
```

3. В `FileTree.tsx` добавить кнопку «+ Новый файл» (Lucide `FilePlus`) сверху и иконку удаления (Lucide `Trash2`) на hover каждого файла, вызывающие `onCreate`/`onDelete`-коллбэки, проброшенные из `StudioLayout` (которые зовут `studioApi.createFile/deleteFile` + `onRefresh`).

> Точная разметка зависит от текущего `FileTree.tsx` — прочитать файл, добавить минимально: хедер с кнопкой создания (prompt пути через простую модалку или `window.prompt` — но без эмодзи в тексте) и hover-иконку удаления.

**Verify:**
```bash
cd src && python manage.py test studio
cd frontend && npm run build
```
Юнит-тест: POST `/files/` создаёт `StudioFile`, `sync_manual_edit` поставлен; DELETE удаляет и ставит `delete_sandbox_file`. Ручная: создать/удалить файл в дереве.

**Dependencies:** U13 (редактор — создать пустой файл и сразу писать).

---

# Сессия SU10 — Волна 3: Visual Step Timeline

**Слой:** бэк (миграция) + фронт. **Время:** ~120 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U23: Бэкенд — GET /timeline/ + POST /branch/{version_id}/

**Session:** SU10
**Wave:** 3
**Fixes/Implements:** Раздел 3.1 (backend)
**Files changed:**
- `src/studio/models.py` (миграция: `forked_from`)
- `src/studio/views/projects.py`
- `src/studio/urls.py`
- `src/studio/tasks.py`

**Context:** Timeline-лента нуждается в агрегате шагов (planned + changed_files + reports + version_id). Branch создаёт форк проекта от версии.

**What to do:**

1. Поле форка в `StudioProject` (`models.py`):

```python
    forked_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='forks')
```
```bash
cd src && python manage.py makemigrations studio && python manage.py migrate
```

2. View в `views/projects.py`:

```python
class TimelineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import _split_steps
        steps = _split_steps(project.commits_md_content)
        changed = project.interview_data.get('last_changed', {})
        versions = {v.step_index: v for v in project.versions.all()}
        out = []
        for i, text in enumerate(steps):
            v = versions.get(i)
            out.append({
                'step_index': i,
                'name': text.strip().splitlines()[0][:120] if text.strip() else f'Шаг {i}',
                'planned': text[:2000],
                'changed_files': changed.get(str(i), []),
                'version_id': v.id if v else None,
                'git_sha': v.git_sha if v else '',
            })
        return Response(out)


class BranchFromVersionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id, version_id):
        from ..models import StudioVersion, StudioFile
        project = StudioProject.objects.get(id=id, user=request.user)
        version = StudioVersion.objects.get(id=version_id, project=project)
        fork = StudioProject.objects.create(
            user=request.user,
            name=f'{project.name} (ветка от шага {version.step_index})',
            description=project.description,
            mode=project.mode, entry_mode=project.entry_mode,
            target_url=project.target_url, target_stack=project.target_stack,
            project_md_content=project.project_md_content,
            commits_md_content=project.commits_md_content,
            interview_data=project.interview_data,
            forked_from=project, status='ready',
        )
        # Copy current files as the fork's starting point
        for f in project.files.all():
            StudioFile.objects.create(project=fork, path=f.path, content=f.content, language=f.language)
        return Response({'id': str(fork.id)}, status=201)
```

3. URL (импортировать `TimelineView`, `BranchFromVersionView`):

```python
    path('projects/<uuid:id>/timeline/', TimelineView.as_view(), name='timeline'),
    path('projects/<uuid:id>/branch/<int:version_id>/', BranchFromVersionView.as_view(), name='branch_from_version'),
```

> `StudioPipelineState` создаётся для проекта — проверить, как он создаётся для новых проектов (signal или в create). Если через signal на `StudioProject` post_save — форк получит pipeline автоматически; иначе создать `StudioPipelineState.objects.create(project=fork)`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект с 2 секциями COMMITS.md и версией шага 0 → GET `/timeline/` возвращает 2 элемента, у первого `version_id` заполнен. POST `/branch/{vid}/` создаёт новый проект с `forked_from` и копией файлов.

**Dependencies:** —

---

## Commit U24: StepTimeline.tsx (planned vs actual, branch from step)

**Session:** SU10
**Wave:** 3
**Fixes/Implements:** Раздел 3.1 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/StepTimeline.tsx` (новый)
- `frontend/components/studio/StudioLayout.tsx`

**Context:** UI ленты шагов с planned/actual и кнопкой «Ветка от этого шага».

**What to do:**

1. Типы и методы в `studio.ts`:

```ts
// AFTER (тип)
export interface TimelineStep {
  step_index: number;
  name: string;
  planned: string;
  changed_files: string[];
  version_id: number | null;
  git_sha: string;
}

// AFTER (методы)
  timeline: (id: string) =>
    request<TimelineStep[]>(`/studio/projects/${id}/timeline/`),
  branchFrom: (id: string, versionId: number) =>
    request<{ id: string }>(`/studio/projects/${id}/branch/${versionId}/`, { method: 'POST' }),
```

2. Новый файл `frontend/components/studio/StepTimeline.tsx`:

```tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { GitBranch } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

export function StepTimeline({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { data: steps = [] } = useQuery({
    queryKey: ['studio-timeline', projectId],
    queryFn: () => studioApi.timeline(projectId),
    refetchInterval: 5000,
  });

  const branch = async (versionId: number) => {
    const res = await studioApi.branchFrom(projectId, versionId);
    router.push(`/studio/${res.id}/`);
  };

  return (
    <div className="flex gap-3 overflow-x-auto p-3">
      {steps.map((s) => (
        <div key={s.step_index} className="shrink-0 w-64 border border-[var(--border)] rounded-lg p-3 space-y-2">
          <div className="text-xs font-medium truncate">{s.name}</div>
          <div className="text-[11px] text-[var(--text-secondary)]">
            Файлов изменено: {s.changed_files.length}
          </div>
          {s.changed_files.slice(0, 4).map((f) => (
            <div key={f} className="text-[11px] font-mono truncate text-[var(--text-secondary)]">{f}</div>
          ))}
          {s.version_id && (
            <button onClick={() => branch(s.version_id!)} className="flex items-center gap-1 text-[11px] text-blue-500 hover:underline">
              <GitBranch size={12} /> Ветка от этого шага
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
```

3. В `StudioLayout.tsx` показать timeline (например, как сворачиваемый блок рядом с логом агентов, или вкладкой в нижнем drawer). Минимально — добавить под top bar toggle-кнопку «Таймлайн» и рендер `<StepTimeline projectId={project.id} />`.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: лента шагов с числом изменённых файлов; «Ветка от этого шага» создаёт форк и переходит в него.

**Dependencies:** U23.

---

## Commit U25: Бэкенд — POST /explain/ (объяснение кода)

**Session:** SU10
**Wave:** 3
**Fixes/Implements:** Раздел 3.6 (backend)
**Files changed:**
- `src/studio/views/pipeline.py`
- `src/studio/urls.py`
- `src/studio/agents/explainer.py` (новый)

**Context:** «Объясни этот код» — выделенный фрагмент объясняется по-русски за 1 звезду.

**What to do:**

1. Лёгкий агент `src/studio/agents/explainer.py` (по образцу `assistant.py`):

```python
from .base import BaseAgent, MODEL_FAST

EXPLAINER_SYSTEM = (
    "Ты объясняешь код простыми словами по-русски. Кратко: что делает фрагмент, "
    "ключевые моменты, потенциальные проблемы. Без воды."
)


class ExplainerAgent(BaseAgent):
    name = 'explainer'
    model = MODEL_FAST

    def explain(self, code: str, path: str = '') -> str:
        user = f"Файл: {path}\n\nКод:\n```\n{code[:4000]}\n```"
        return self.run_prompt(EXPLAINER_SYSTEM, user, model=MODEL_FAST, max_tokens=1200, temperature=0.3)
```

> Сверить сигнатуру `BaseAgent.run_prompt` / `MODEL_FAST` с `agents/assistant.py` (он есть и работает — ContextChat использует `AssistantAgent`).

2. View в `views/pipeline.py`:

```python
class ExplainView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..billing import can_afford, charge
        cost = 1
        if not can_afford(request.user, cost):
            return Response({'error': 'Недостаточно звёзд'}, status=402)
        code = request.data.get('code', '')
        path = request.data.get('path', '')
        if not code.strip():
            return Response({'error': 'Пустой фрагмент'}, status=400)
        from ..agents.explainer import ExplainerAgent
        answer = ExplainerAgent(project).explain(code, path)
        charge(request.user, cost, project)
        return Response({'explanation': answer})
```

3. URL: `path('projects/<uuid:id>/explain/', ExplainView.as_view(), name='explain')`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `ExplainerAgent.explain` → «объяснение»; POST `/explain/` с `code` → ответ содержит `explanation`, `charge` вызван 1 раз; пустой код → 400.

**Dependencies:** —

---

# Сессия SU11 — Волна 3: объяснение кода + debug mode

**Слой:** бэк + фронт. **Миграций нет.** **Время:** ~100 мин.
**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`

## Commit U26: «Объясни этот код» — floating button + popover

**Session:** SU11
**Wave:** 3
**Fixes/Implements:** Раздел 3.6 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/CodeViewer.tsx`

**Context:** На выделение текста в CodeViewer показывать кнопку «Объясни», ответ — в поповере с markdown.

**What to do:**

1. Метод в `studio.ts`:

```ts
// AFTER
  explain: (id: string, code: string, path?: string) =>
    request<{ explanation: string }>(`/studio/projects/${id}/explain/`, {
      method: 'POST', body: JSON.stringify({ code, path }),
    }),
```

2. В `CodeViewer.tsx` (после U13) добавить prop `projectId`, отслеживание выделения и поповер. Использовать `react-markdown` (уже в зависимостях для чата):

```tsx
// AFTER (props)
  projectId?: string;

// AFTER (стейты)
  const [selection, setSelection] = useState('');
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);

  const onMouseUp = () => {
    const sel = window.getSelection()?.toString() ?? '';
    setSelection(sel.trim());
  };

  const runExplain = async () => {
    if (!projectId || !selection) return;
    setExplaining(true);
    try {
      const res = await studioApi.explain(projectId, selection, path);
      setExplanation(res.explanation);
    } finally { setExplaining(false); }
  };
```

Навесить `onMouseUp` на контейнер редактора, показать плавающую кнопку «Объясни» при наличии `selection`, и поповер с `explanation` (через `react-markdown`). Импортировать `studioApi`, `ReactMarkdown`, иконку `Sparkles`.

> Точная позиция floating-кнопки — простой вариант: фиксированная панель снизу справа CodeViewer при `selection`. Без эмодзи, иконка Lucide.

3. В `StudioLayout.tsx` пробросить `projectId={project.id}` в `CodeViewer`.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: выделить код → кнопка «Объясни» → поповер с объяснением на русском.

**Dependencies:** U25, U13.

---

## Commit U27: Бэкенд — POST /console-error/ + Fixer hook

**Session:** SU11
**Wave:** 3
**Fixes/Implements:** Раздел 3.9 (backend)
**Files changed:**
- `src/studio/views/pipeline.py`
- `src/studio/urls.py`

**Context:** Превью-iframe шлёт ошибки консоли → бэкенд сохраняет и (по запросу) передаёт Fixer-агенту как hint.

**What to do:**

1. View в `views/pipeline.py`:

```python
class ConsoleErrorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        err = {
            'message': request.data.get('message', '')[:1000],
            'stack': request.data.get('stack', '')[:2000],
            'file': request.data.get('file', ''),
            'line': request.data.get('line'),
        }
        errors = project.interview_data.setdefault('console_errors', [])
        errors.append(err)
        project.interview_data['console_errors'] = errors[-20:]
        project.save(update_fields=['interview_data'])
        # If autofix requested, feed to fixer via resume(with_hint)
        if request.data.get('autofix'):
            state = project.pipeline
            hint = f"Ошибка в превью: {err['message']} ({err['file']}:{err['line']})\n{err['stack']}"
            state.fix_plan = {'instructions': hint, 'target_files': [err['file']] if err['file'] else []}
            state.status = 'running'
            state.pause_requested = False
            state.save(update_fields=['fix_plan', 'status', 'pause_requested'])
            from ..tasks import coder_iteration
            coder_iteration.delay(str(project.id), state.step_index)
        return Response({'stored': True, 'count': len(errors)})
```

2. URL: `path('projects/<uuid:id>/console-error/', ConsoleErrorView.as_view(), name='console_error')`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: POST `/console-error/` с `message`/`autofix=true` (замокать `coder_iteration.delay`) → ошибка в `interview_data['console_errors']`, `fix_plan.instructions` содержит сообщение, delay вызван.

**Dependencies:** —

---

## Commit U28: Debug Mode — interceptor в iframe + auto-fix

**Session:** SU11
**Wave:** 3
**Fixes/Implements:** Раздел 3.9 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/PreviewPanel.tsx`

**Context:** Перехватывать `window.onerror`/`console.error` из превью-iframe (через postMessage) и показывать счётчик ошибок + кнопку «Исправить автоматически».

**What to do:**

1. Метод в `studio.ts`:

```ts
// AFTER
  reportConsoleError: (id: string, data: { message: string; stack?: string; file?: string; line?: number; autofix?: boolean }) =>
    request<{ stored: boolean; count: number }>(`/studio/projects/${id}/console-error/`, {
      method: 'POST', body: JSON.stringify(data),
    }),
```

2. В `PreviewPanel.tsx` слушать `message` от iframe и собирать ошибки:

```tsx
// AFTER (стейт)
  const [errors, setErrors] = useState<{ message: string; file?: string; line?: number; stack?: string }[]>([]);

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.data?.type === 'studio-console-error') {
        setErrors((prev) => [...prev, e.data.error].slice(-20));
        studioApi.reportConsoleError(projectId, e.data.error);
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [projectId]);
```

> Импортировать `useEffect`, `studioApi`. Чтобы превью слало postMessage, нужно внедрить interceptor-скрипт в sandbox при spawn (в `sandbox.py`/dev-сервере) ИЛИ инжектить через прокси. Для MVP — добавить в `restart_preview`/`spawn_sandbox` запись файла `public/__studio_debug.js`, подключаемого приложением. Это инфра-задача; в этом коммите фронт готов принимать сообщения, а инжект interceptor-скрипта пометить TODO в `restart_preview`.

3. Показать индикатор «N ошибок» в toolbar PreviewPanel и кнопку «Исправить автоматически» → `reportConsoleError(projectId, {...lastError, autofix:true})`.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: при ошибке в превью (если interceptor подключён) растёт счётчик; «Исправить автоматически» запускает Fixer.

**Dependencies:** U27, U16 (PreviewPanel toolbar расширен).

---

# Сессия SU12 — Волна 3: screenshot, GitHub, уведомления, режим ревьюера

**Слой:** бэк (миграции) + фронт. **Время:** ~150 мин (можно разбить).
**Деплой:** полный rebuild.

## Commit U29: Бэкенд — POST /screenshot/ (vision → описание)

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.5 (backend)
**Files changed:**
- `src/studio/models.py` (миграция: `screenshot`)
- `src/studio/views/projects.py`
- `src/studio/urls.py`
- `src/studio/agents/screenshot.py` (новый)

**Context:** Загруженный макет описывается vision-моделью и подмешивается в `interview_data` для обогащения промта Coder.

**What to do:**

1. Поле в `StudioProject`:
```python
    screenshot = models.ImageField(upload_to='studio/screenshots/', null=True, blank=True)
```
```bash
cd src && python manage.py makemigrations studio && python manage.py migrate
```

2. Агент `src/studio/agents/screenshot.py` — vision-промт через laozhang.ai (мультимодальный). Использовать тот же клиент, что и текстовые агенты (`BaseAgent`), но с image-контентом. Сверить, как `BaseAgent` строит сообщения; если он не поддерживает image — сделать прямой вызов `openai`-клиента с `image_url` (base64 data URL).

```python
from .base import BaseAgent, MODEL_SMART

SCREENSHOT_SYSTEM = (
    "Ты описываешь UI-макет для генерации кода. Опиши верстку, секции, цвета, "
    "компоненты, расположение. По-русски, структурировано."
)


class ScreenshotAgent(BaseAgent):
    name = 'screenshot'
    model = MODEL_SMART

    def describe(self, image_b64: str) -> str:
        # Build a multimodal message; adapt to BaseAgent's client API
        return self.run_vision(SCREENSHOT_SYSTEM, image_b64, model=MODEL_SMART, max_tokens=1500)
```

> Если в `BaseAgent` нет `run_vision` — реализовать его там по образцу `run_prompt`, передав `content=[{type:'text',...},{type:'image_url', image_url:{url: f'data:image/png;base64,{image_b64}'}}]`.

3. View в `views/projects.py` (multipart):

```python
class ScreenshotView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        import base64
        project = StudioProject.objects.get(id=id, user=request.user)
        img = request.FILES.get('image')
        if not img:
            return Response({'error': 'Нет файла'}, status=400)
        project.screenshot = img
        project.save(update_fields=['screenshot'])
        img.seek(0)
        b64 = base64.b64encode(img.read()).decode()
        from ..agents.screenshot import ScreenshotAgent
        desc = ScreenshotAgent(project).describe(b64)
        project.interview_data['screenshot_description'] = desc
        project.save(update_fields=['interview_data'])
        return Response({'description': desc})
```

4. URL: `path('projects/<uuid:id>/screenshot/', ScreenshotView.as_view(), name='screenshot')`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `ScreenshotAgent.describe` → «описание»; POST multipart с маленьким PNG → `interview_data['screenshot_description']` заполнен.

**Dependencies:** —

---

## Commit U30: Screenshot-to-Code на странице создания

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.5 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/app/studio/page.tsx`

**Context:** На странице создания/редактирования дать drag&drop изображения → описание подмешивается в `description`.

**What to do:**

1. Метод в `studio.ts` (multipart — через `FormData`, не JSON):

```ts
// AFTER (использовать fetch напрямую, т.к. request() ставит JSON-заголовки)
  uploadScreenshot: (id: string, file: File) => {
    const fd = new FormData();
    fd.append('image', file);
    return fetch(`${process.env.NEXT_PUBLIC_API_URL}/studio/projects/${id}/screenshot/`, {
      method: 'POST', body: fd, credentials: 'include',
    }).then((r) => r.json() as Promise<{ description: string }>);
  },
```

2. В `frontend/app/studio/page.tsx` (страница создания) добавить input файла. После создания проекта (есть `id`) можно загрузить скриншот и подставить `description` в форму. Минимально — кнопка «Загрузить макет» в форме создания, при выборе файла после создания проекта вызвать `uploadScreenshot` и показать полученное описание (которое уйдёт в interview).

> Прочитать `frontend/app/studio/page.tsx` для точного места вставки в форму создания.

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: загрузить макет на странице создания → получить описание UI.

**Dependencies:** U29.

---

## Commit U31: Бэкенд — GitHub OAuth + POST /export/github/

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.8 (backend)
**Files changed:**
- `src/studio/models.py` (миграция: `github_repo_url`)
- `src/config/settings.py` (allauth GitHub provider + `STUDIO_GITHUB_TOKEN` опционально)
- `src/studio/views/projects.py`
- `src/studio/urls.py`
- `src/studio/tasks.py`

**Context:** Экспорт всех `StudioFile` в новый GitHub-репозиторий через GitHub API. OAuth через allauth (уже в стеке).

**What to do:**

1. Поле в `StudioProject`:
```python
    github_repo_url = models.CharField(max_length=500, blank=True)
```
`makemigrations`/`migrate`.

2. В `settings.py` добавить `'allauth.socialaccount.providers.github'` в `INSTALLED_APPS` и конфиг провайдера (scope `repo`). Документировать необходимость GitHub OAuth App в `.env` (`GITHUB_CLIENT_ID`/`SECRET`).

3. Задача `export_to_github` в `tasks.py` — берёт токен пользователя из allauth `SocialToken`, создаёт репо (`POST https://api.github.com/user/repos`), пушит файлы через Contents API (`PUT /repos/{owner}/{repo}/contents/{path}`):

```python
@shared_task(bind=True, max_retries=2, queue=QUEUE)
def export_to_github(self, project_id, repo_name, private):
    import base64, requests
    from allauth.socialaccount.models import SocialToken
    project = StudioProject.objects.get(id=project_id)
    token_obj = SocialToken.objects.filter(account__user=project.user, account__provider='github').first()
    if not token_obj:
        publish_event(project_id, {'agent': 'system', 'level': 'error', 'text': 'GitHub не подключён'})
        return
    headers = {'Authorization': f'token {token_obj.token}', 'Accept': 'application/vnd.github+json'}
    try:
        r = requests.post('https://api.github.com/user/repos', headers=headers,
                          json={'name': repo_name, 'private': bool(private), 'auto_init': False}, timeout=30)
        data = r.json()
        owner = data.get('owner', {}).get('login')
        if not owner:
            raise RuntimeError(data)
        for f in project.files.all():
            requests.put(f'https://api.github.com/repos/{owner}/{repo_name}/contents/{f.path.lstrip("/")}',
                         headers=headers,
                         json={'message': f'Add {f.path}', 'content': base64.b64encode(f.content.encode()).decode()},
                         timeout=30)
        project.github_repo_url = data.get('html_url', '')
        project.save(update_fields=['github_repo_url'])
        publish_event(project_id, {'agent': 'system', 'level': 'success', 'text': f'Экспортировано: {project.github_repo_url}'})
    except Exception as e:
        raise self.retry(exc=e, countdown=30)
```

4. View + URL:
```python
class GithubExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import export_to_github
        export_to_github.delay(str(project.id), request.data.get('repo_name', f'aineron-{str(project.id)[:8]}'), request.data.get('private', True))
        return Response({'status': 'exporting'}, status=202)
```
```python
    path('projects/<uuid:id>/export/github/', GithubExportView.as_view(), name='export_github'),
```

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `SocialToken` и `requests.post/put`; вызвать `export_to_github` → `project.github_repo_url` установлен.

**Dependencies:** —

---

## Commit U32: Кнопка «Экспорт в GitHub» в completion-card

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.8 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/PreviewPanel.tsx`

**Context:** Подключить экспорт в GitHub к completion-card (U21).

**What to do:**

1. Метод в `studio.ts`:
```ts
  exportGithub: (id: string, repoName: string, isPrivate: boolean) =>
    request<{ status: string }>(`/studio/projects/${id}/export/github/`, {
      method: 'POST', body: JSON.stringify({ repo_name: repoName, private: isPrivate }),
    }),
```

2. В completion-card `PreviewPanel.tsx` добавить кнопку «Экспорт в GitHub» (Lucide `Github`), при клике — `window.prompt` имя репо (без эмодзи) → `exportGithub`. Если у проекта уже есть `github_repo_url` — показать ссылку (для этого пробросить `githubUrl` пропом из `StudioLayout`).

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: на completion-card кнопка «Экспорт в GitHub» шлёт POST.

**Dependencies:** U31, U21.

---

## Commit U33: Бэкенд — уведомления о завершении (email + push)

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.10 (backend)
**Files changed:**
- `src/studio/tasks.py`
- `src/studio/views/projects.py`
- `src/studio/urls.py`

**Context:** При завершении пайплайна слать email (`email_service` есть) и (если настроено) push/Telegram. Настройки храним в `interview_data['notify']` — **миграция не нужна** (поле `interview_data` уже существует как JSONField).

**What to do:**

1. Хранить настройки в `interview_data['notify']` (`{email:bool, telegram:bool, push:bool}`). Эндпоинт `PUT /studio/notifications/`:
```python
class NotificationPrefsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        project.interview_data['notify'] = {
            'email': bool(request.data.get('email', True)),
            'telegram': bool(request.data.get('telegram', False)),
            'push': bool(request.data.get('push', False)),
        }
        project.save(update_fields=['interview_data'])
        return Response(project.interview_data['notify'])
```

2. Задача `notify_project_done` в `tasks.py`:
```python
@shared_task(queue=QUEUE)
def notify_project_done(project_id):
    project = StudioProject.objects.get(id=project_id)
    prefs = (project.interview_data or {}).get('notify', {'email': True})
    if prefs.get('email'):
        try:
            from users.email_service import send_email  # сверить точное имя функции
            send_email(project.user.email, 'Проект готов',
                       f'Ваш проект «{project.name}» сгенерирован в aineron Studio.')
        except Exception:
            pass
```

3. В `next_step` (ветка завершения, U3/U4) добавить вызов:
```python
        from .tasks import notify_project_done
        notify_project_done.delay(project_id)
```

4. URL: `path('projects/<uuid:id>/notifications/', NotificationPrefsView.as_view(), name='notification_prefs')`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `send_email`; вызвать `notify_project_done` для проекта с `notify.email=True` → `send_email` вызван.

**Dependencies:** U3, U4 (ветка завершения).

---

## Commit U34: Бэкенд — DeviationReviewerAgent + GET /steps/{n}/deviation/

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.2 (backend)
**Files changed:**
- `src/studio/agents/deviation.py` (новый)
- `src/studio/views/projects.py`
- `src/studio/urls.py`

**Context:** Сравнить план шага (COMMITS.md) и реально написанный код, выделить отклонения.

**What to do:**

1. Агент `src/studio/agents/deviation.py`:
```python
import json
from .base import BaseAgent, MODEL_SMART

DEVIATION_SYSTEM = (
    "Сравни план шага и реализованный код. Верни JSON: "
    '{"matched": [..], "deviations": [{"planned": "..", "actual": "..", "severity": "low|medium|high"}]}'
)


class DeviationReviewerAgent(BaseAgent):
    name = 'deviation'
    model = MODEL_SMART

    def review(self, planned: str, changed_files: dict) -> dict:
        body = '\n'.join(f'### {p}\n```\n{c[:4000]}\n```' for p, c in changed_files.items())
        user = f"ПЛАН ШАГА:\n{planned}\n\nРЕАЛИЗОВАНО:\n{body}"
        return self.run_json(DEVIATION_SYSTEM, user, model=MODEL_SMART, max_tokens=2000)
```
> Сверить `run_json` в `BaseAgent` (используется в reviewer/tester — есть).

2. View:
```python
class DeviationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, id, n):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import _split_steps
        steps = _split_steps(project.commits_md_content)
        planned = steps[n] if n < len(steps) else ''
        changed_paths = (project.interview_data.get('last_changed', {})).get(str(n), [])
        files = {f.path: f.content for f in project.files.filter(path__in=changed_paths)}
        from ..agents.deviation import DeviationReviewerAgent
        report = DeviationReviewerAgent(project).review(planned, files)
        return Response(report)
```

3. URL: `path('projects/<uuid:id>/steps/<int:n>/deviation/', DeviationView.as_view(), name='deviation')`.

**Verify:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `DeviationReviewerAgent.review` → `{'matched':[],'deviations':[]}`; GET `/steps/0/deviation/` → 200 с JSON.

**Dependencies:** U23 (last_changed агрегат используется аналогично).

---

## Commit U35: Режим Ревьюера (planned vs coded side-by-side)

**Session:** SU12
**Wave:** 3
**Fixes/Implements:** Раздел 3.2 (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/ReviewerMode.tsx` (новый)
- `frontend/components/studio/StepDetailDrawer.tsx`

**Context:** В Step Detail Drawer добавить вкладку «Ревьюер»: слева план шага, справа отклонения от плана.

**What to do:**

1. Типы и метод в `studio.ts`:
```ts
export interface DeviationReport {
  matched: string[];
  deviations: { planned: string; actual: string; severity: 'low' | 'medium' | 'high' }[];
}

  deviation: (id: string, n: number) =>
    request<DeviationReport>(`/studio/projects/${id}/steps/${n}/deviation/`),
```

2. Новый `frontend/components/studio/ReviewerMode.tsx` — две колонки: planned-текст и список deviations с цветовой кодировкой severity (high=red, medium=amber, low=gray, через CSS-переменные где можно).

3. В `StepDetailDrawer.tsx` добавить кнопку/таб «Режим ревьюера», который грузит `studioApi.deviation(id, stepIndex)` и рендерит `<ReviewerMode>`.

> `StepDetailDrawer` нужно передать `projectId` и `stepIndex` — пробросить из `StudioLayout` (U7).

**Verify:**
```bash
cd frontend && npm run build
```
Ручная: в Step Drawer открыть «Режим ревьюера» → план vs отклонения.

**Dependencies:** U34, U7.

---

# Backlog Волны 3 (U36-U41) — описание без полных сниппетов

Эти фичи из `STUDIO_UPGRADE_PLAN.md` Раздела 3 требуют значительной инфраструктуры (ASGI/WebSocket, CRDT) — выносятся отдельными сессиями после стабилизации Волн 0-2. Каждую реализовывать по тому же формату (один концерн = один коммит):

- **U36** — Live Collaboration presence (Раздел 3.3): расширить `PipelineEventsView` событием `{type:'presence', users:[...]}`, эндпоинт `POST /presence/` (heartbeat), аватарки в top bar. Бэк+фронт, без миграций (использует существующий `StudioCollaborator`).
- **U37** — Библиотека промптов кодеров (Раздел 3.7): модель `StudioPrompt` (миграция), эндпоинты `GET/POST /studio/prompts/`, `fork`/`like`, страница `/studio/prompts/`.
- **U38** — Встроенный терминал (Раздел 2.1): `django-channels` (ASGI-воркер), WS `ws/studio/{id}/terminal/`, `container.exec_run(socket=True)`, фронт `Terminal.tsx` на `@xterm/xterm`. Инфра-задача.
- **U39** — .env editor (Раздел 2.6): `GET/PUT /studio/projects/{id}/env/`, хранение в `interview_data['env']`, фронт `EnvEditor.tsx`.
- **U40** — Управление зависимостями (Раздел 2.7): `GET/POST /studio/projects/{id}/deps/`, `exec_run('pnpm add ...')`, фронт `DependencyManager.tsx`.
- **U41** — Subdomain preview proxy (BUG-S0-09 / STUDIO_PLAN Sprint E7): nginx wildcard `sandbox-*.aineron.ru` + wildcard SSL, `PreviewPanel` строит прямой URL. Решает Next.js `/_next/static` 404 и latency. Инфра-задача, дублирует Commit 15-16 из STUDIO_COMMITS.md — выполнять по тому документу, не дублировать.

---

# Приложение — Сводная таблица зависимостей

| Commit | Сессия | Волна | Зависит от |
|--------|--------|-------|-----------|
| U1 | SU1 | 0 | — |
| U2 | SU1 | 0 | — |
| U3 | SU1 | 0 | — |
| U4 | SU2 | 0 | U3 |
| U5 | SU2 | 0 | — |
| U6 | SU2 | 0 | U5, U1 |
| U7 | SU3 | 1 | U6 |
| U8 | SU3 | 1 | U2, U7 |
| U9 | SU4 | 1 | U3 |
| U10 | SU4 | 1 | U9 |
| U11 | SU5 | 1 | — |
| U12 | SU5 | 1 | U7, U9, U10 |
| U13 | SU6 | 2 | U8, U12 |
| U14 | SU6 | 2 | — |
| U15 | SU6 | 2 | U14, U12 |
| U16 | SU7 | 2 | U3 |
| U17 | SU7 | 2 | U8, U16 |
| U18 | SU8 | 2 | — |
| U19 | SU8 | 2 | U18 |
| U20 | SU9 | 2 | U3 |
| U21 | SU9 | 2 | U20, U3 |
| U22 | SU9 | 2 | U13 |
| U23 | SU10 | 3 | — |
| U24 | SU10 | 3 | U23 |
| U25 | SU10 | 3 | — |
| U26 | SU11 | 3 | U25, U13 |
| U27 | SU11 | 3 | — |
| U28 | SU11 | 3 | U27, U16 |
| U29 | SU12 | 3 | — |
| U30 | SU12 | 3 | U29 |
| U31 | SU12 | 3 | — |
| U32 | SU12 | 3 | U31, U21 |
| U33 | SU12 | 3 | U3, U4 |
| U34 | SU12 | 3 | U23 |
| U35 | SU12 | 3 | U34, U7 |

---

# Сводная таблица сессий

| Сессия | Коммиты | Слой | Миграция | Deploy | Приоритет |
|--------|---------|------|----------|--------|-----------|
| SU1 | U1, U2, U3 | FE + 1 BE | — | Да | КРИТИЧНО (Волна 0) |
| SU2 | U4, U5, U6 | BE + FE | — | Да | КРИТИЧНО (Волна 0) |
| SU3 | U7, U8 | FE | — | Да | Важно (Волна 1) |
| SU4 | U9, U10 | FE | — | Да | Важно (Волна 1) |
| SU5 | U11, U12 | FE | — | Да | Важно (Волна 1) |
| SU6 | U13, U14, U15 | FE + BE | — | Да | Средний (Волна 2) |
| SU7 | U16, U17 | FE | — | Да | Средний (Волна 2) |
| SU8 | U18, U19 | BE + FE | да (U18) | Да | Средний (Волна 2) |
| SU9 | U20, U21, U22 | BE + FE | — | Да | Средний (Волна 2) |
| SU10 | U23, U24, U25 | BE + FE | да (U23) | Да | Низкий (Волна 3) |
| SU11 | U26, U27, U28 | BE + FE | — | Да | Низкий (Волна 3) |
| SU12 | U29-U35 | BE + FE | да (U29, U31) | Да | Низкий (Волна 3) |

**Итого:** 12 сессий, 35 коммитов (U1-U35) + 6 backlog-коммитов (U36-U41).

---

## Порядок реализации (рекомендованный)

1. **Волна 0 целиком (SU1-SU2, U1-U6)** — убирает «впечатление сломанности». Делать в первую очередь.
2. **Волна 1 (SU3-SU5, U7-U12)** — прозрачность пайплайна, наше дифференцирующее преимущество. ~40% — подключение уже написанного бэкенда.
3. **Волна 2 (SU6-SU9, U13-U22)** — инструменты разработчика. SU8 — первая миграция, делать первой в сессии.
4. **Волна 3 (SU10-SU12, U23-U35)** — killer-фичи. Backlog (U36-U41) — после стабилизации.

После каждого коммита: `cd src && python manage.py test studio` (backend) и/или `cd frontend && npm run build` (frontend). По правилу проекта — `git push origin main` после каждого коммита.

---

## Стартовая фраза для нового чата

```
Открой файл STUDIO_UPGRADE_COMMITS.md в корне проекта.
Реализуй сессию SUN (коммиты UX, UY, UZ) по инструкции из документа.
Сначала прочитай реальные затрагиваемые файлы и сверь BEFORE-сниппеты — код мог измениться.
После каждого коммита — git push origin main.
Деплой на сервере после завершения сессии.
```
