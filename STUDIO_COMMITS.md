# STUDIO_COMMITS.md — Пошаговый план коммитов Vibe-Coding Studio

Детальный, исполняемый план улучшения студии vibe-кодинга (`src/studio/` + `frontend/app/studio/`, `frontend/components/studio/`).

Этот документ — единственный источник для реализации. Каждый коммит самодостаточен: содержит точные пути, before/after-сниппеты на основе **реального текущего кода** и конкретный способ проверки. Открывайте его в новом чате и начинайте с Commit 1.

## Как пользоваться

- Коммиты пронумерованы и идут в порядке реализации. Соблюдайте `Dependencies`.
- Каждый коммит — **одна забота**. Не объединяйте.
- После любого изменения поля модели — обязательно `cd src && python manage.py makemigrations studio && python manage.py migrate`.
- Тесты студии лежат в `src/studio/tests.py`. Запуск: `cd src && python manage.py test studio`.
- Не трогайте старый `VIBECODING_STUDIO_COMMITS.md` — это отдельный legacy-документ.
- UI: только Lucide React, ноль эмодзи (см. CLAUDE.md).

## Карта багов → коммитов (аудит, чтобы ничего не задублировать)

| Баг | Описание | Коммит | Спринт |
|-----|----------|--------|--------|
| BUG-01 | STATUS: модель `'interview'`, view пишет `'interviewing'` | Commit 1 | Fix |
| BUG-02 | BILLING HOLE: `_billing_charge` тихо возвращает 0, пайплайн бежит бесплатно | Commit 3 | Fix |
| BUG-05 | Double-charge на retry: charge до возможного `raise` | Commit 2 | Fix |
| BUG-03 | `run_pipeline` без try/except вокруг Docker → застревание `coding` | Commit 4 | Fix |
| BUG-04 | Pause не останавливает in-flight Celery-задачи | Commit 5 | Fix |
| BUG-06 | `<STEPS_COUNT>` planner ≠ число секций в COMMITS.md | Commit 6 | Fix |
| BUG-07 | AgentLog SSE: `onerror→close` без reconnect, двойная подписка | Commit 11 | E |
| BUG-08 | Hardcoded `estimatedStars={50}` на review-странице | Commit 10 | E |
| BUG-09 | `reap_stale_sandboxes` не в расписании Celery beat | Commit 7 | Fix |
| BUG-10 | Ручные правки (`FileDetailView` PATCH) не идут в sandbox/Gitea | Commit 14 | E |

> **Важно по BUG-01 (расхождение с формулировкой задачи).** В задаче сказано, что код пишет `'interviewing'` «везде». Это не так. Эталонное значение — **`'interview'`**: его используют `STATUS_CHOICES` в `models.py`, фронтенд `PipelineStatus.STATUS_TO_ACTIVE` (`interview: 'interviewer'`) и review-страница (`status === 'interview'`). Единственный нарушитель — `InterviewView.get`, который пишет `'interviewing'`. Чиним выброс, а НЕ добавляем `'interviewing'` в модель.

---

# Sprint Fix — Критические баги

## Commit 1: Унифицировать статус интервью на 'interview'

**Sprint:** Fix
**Fixes/Implements:** BUG-01
**Files changed:**
- `src/studio/views/projects.py`

**What to do:**
В `InterviewView.get` атомарный guard пишет несуществующий в `STATUS_CHOICES` статус `'interviewing'`. Канон — `'interview'`. Заменить:

```python
# BEFORE (projects.py, InterviewView.get)
triggered = StudioProject.objects.filter(
    id=id, user=request.user, status='draft'
).update(status='interviewing')

# AFTER
triggered = StudioProject.objects.filter(
    id=id, user=request.user, status='draft'
).update(status='interview')
```

Прогрепать весь репозиторий на `interviewing`, чтобы не осталось других вхождений в backend (фронтенд уже использует `interview` корректно):

```bash
cd src && grep -rn "interviewing" . --include="*.py"
```

Ожидаемый результат grep после правки: пусто.

**Test:**
```bash
cd src && grep -rn "interviewing" . --include="*.py"   # должно быть пусто
cd src && python manage.py shell -c "from studio.models import StudioProject; print([c[0] for c in StudioProject.STATUS_CHOICES])"
```
Ручная проверка: создать проект, открыть `/studio/<id>/interview/` — фронт `PipelineStatus` должен подсветить точку «Интервью» (она маппится с `interview`), редирект на `[id]/page.tsx` должен работать.

**Dependencies:** —

---

## Commit 2: Убрать double-charge на retry (charge только после успеха)

**Sprint:** Fix
**Fixes/Implements:** BUG-05
**Files changed:**
- `src/studio/tasks.py`

**What to do:**
Сейчас `agent_analyze`, `agent_plan`, `coder_iteration` вызывают `_billing_charge(...)` внутри `try`, а при ошибке делают `raise self.retry(...)`. Если charge прошёл, а потом что-то упало (или задача ретраится по другой причине), пользователь оплачивается повторно при каждом ретрае.

Принцип: **списываем звёзды последним действием, после того как работа агента точно завершилась успешно и не будет переигрываться этим же вызовом.** В текущем коде `_billing_charge` уже стоит после `Agent(...).run()` — это правильно. Проблема в том, что между `run()` и `_billing_charge` (или после него) есть ещё работа, которая может бросить исключение и привести к ретраю всего тела.

Гарантировать порядок: `run()` → побочные эффекты (запись файлов, диспетчеризация следующей задачи) → **charge в самом конце, после диспетчеризации**, чтобы ретрай тела никогда не повторял charge для уже выполненной работы. Конкретно перенести `_billing_charge` ниже:

`agent_analyze`:
```python
# AFTER
@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_analyze(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.analyst import AnalystAgent
    try:
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'Анализирую требования...'})
        AnalystAgent(project).run()
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'PROJECT.md готов'})
        agent_plan.delay(project_id)
        _billing_charge(project, 'analyst', 0)   # charge last
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
```

`agent_plan`: перенести `_billing_charge(project, 'planner', 0)` так, чтобы он шёл **после** `_set_status(project, 'ready')` и publish:
```python
# AFTER (хвост try-блока agent_plan)
        _set_status(project, 'ready')
        publish_event(project_id, {
            'agent': 'planner', 'level': 'info',
            'text': f'COMMITS.md готов: {steps} шагов',
        })
        _billing_charge(project, 'planner', 0)   # charge last
```

`coder_iteration`: перенести `_billing_charge(project, 'coder', step_index)` так, чтобы он шёл **после** записи файлов и **после** `chord(...).apply_async()`:
```python
# AFTER (хвост try-блока coder_iteration)
        if project.sandbox_container_id:
            sandbox.write_files(project.sandbox_container_id, files)
        chord(
            [agent_review.s(project_id, step_index), agent_test.s(project_id, step_index)],
            merge_reports.s(project_id, step_index),
        ).apply_async()
        _billing_charge(project, 'coder', step_index)   # charge last
```

> Примечание про идемпотентность: ретрай `coder_iteration` после успешного charge всё ещё теоретически возможен, если упадёт сам Celery между charge и завершением. Полная идемпотентность звёзд — это Commit 28 (star reservation). Здесь убираем самый частый кейс — charge перед `raise`.

**Test:**
```bash
cd src && python manage.py test studio
```
Добавить юнит-тест в `studio/tests.py`: замокать `AnalystAgent.run` так, чтобы `agent_plan.delay` бросал исключение ПОСЛЕ записи (или замокать `charge` и проверить, что при двух ретраях `charge` зовётся не больше одного раза на успешный проход). Минимум — мокнуть `studio.tasks.charge` и убедиться, что в успешном прогоне он вызван ровно 1 раз.

**Dependencies:** —

---

## Commit 3: Закрыть billing hole — pre-flight гейт вместо тихого return 0

**Sprint:** Fix
**Fixes/Implements:** BUG-02
**Files changed:**
- `src/studio/tasks.py`

**What to do:**
Сейчас `_billing_charge` при `can_afford=False` молча `return 0`, и пайплайн продолжает работать — агенты выполняются бесплатно. Нужно: если денег не хватает, **остановить пайплайн** (поставить паузу) и сообщить пользователю, а не продолжать.

Ввести исключение и менять `_billing_charge` так, чтобы при нехватке средств оно бросалось, а вызывающая задача переводила проект в паузу:

```python
# tasks.py — рядом с _agent_cost
class InsufficientStars(Exception):
    """Raised when a user can't afford an agent run. Pauses the pipeline."""
    def __init__(self, needed):
        self.needed = needed
        super().__init__(f'Недостаточно звёзд: нужно {needed}')


def _billing_charge(project, agent_name: str, step_index: int):
    cost = _agent_cost(agent_name)
    user = project.user
    user.refresh_from_db(fields=['pages_count'])
    if not can_afford(user, cost):
        raise InsufficientStars(cost)
    charge(user, cost, project)
    publish_event(str(project.id), {
        'agent': agent_name, 'level': 'billing',
        'text': f'-{cost} зв. (шаг {step_index})',
    })
    log = project.interview_data.setdefault('billing_log', [])
    log.append({'agent': agent_name, 'stars': cost, 'step': step_index})
    project.save(update_fields=['interview_data'])
    return cost
```

Добавить общий helper для перевода пайплайна в паузу по нехватке средств:

```python
def _pause_no_funds(project, needed):
    state = project.pipeline
    state.status = 'paused_on_loop'
    state.pause_reason = f'Недостаточно звёзд для продолжения (нужно ещё ~{needed})'
    state.save(update_fields=['status', 'pause_reason'])
    project.status = 'paused'
    project.save(update_fields=['status'])
    publish_event(str(project.id), {
        'agent': 'system', 'level': 'error',
        'text': state.pause_reason, 'type': 'paused',
    })
```

В каждой задаче, которая зовёт `_billing_charge` (`agent_analyze`, `agent_plan`, `coder_iteration`, `merge_reports`), обернуть и НЕ ретраить при `InsufficientStars` — вместо этого пауза. Пример для `coder_iteration`:

```python
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed)
        return
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
```

Для `merge_reports` (не bind, без retry) — тот же `except InsufficientStars: _pause_no_funds(...)` вокруг `_billing_charge(project, 'reviewer'...)` / `'tester'` / `'fixer'`.

> Связка с Commit 2: т.к. charge теперь идёт ПОСЛЕДНИМ (после диспетчеризации `chord`), при `InsufficientStars` в `coder_iteration` работа уже частично запущена. Это приемлемо для Fix-спринта; полноценное резервирование звёзд до старта — Commit 28.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: создать пользователя с `pages_count=0`, проект в статусе `ready`, вызвать `coder_iteration` (замокав `CoderAgent.run`), проверить, что `project.pipeline.status == 'paused_on_loop'`, `project.status == 'paused'`, и `charge` НЕ вызывался.

**Dependencies:** Commit 2 (порядок charge), т.к. оба меняют `_billing_charge` и порядок списания — делать подряд.

---

## Commit 4: try/except вокруг Docker-вызовов в run_pipeline

**Sprint:** Fix
**Fixes/Implements:** BUG-03
**Files changed:**
- `src/studio/tasks.py`

**What to do:**
`run_pipeline` дёргает `spawn_sandbox`, `write_files`, `install_deps`, `isolate`, `start_dev_server` без обработки ошибок. Любой сбой Docker оставляет проект навсегда в `status='coding'`. Обернуть всю sandbox-секцию и при ошибке вернуть звёзды (если что-то уже списано) и поставить `failed`/`paused`.

```python
# AFTER (run_pipeline, секция запуска sandbox)
    publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Запускаю sandbox...'})
    try:
        cid = sandbox.spawn_sandbox(project_id)
        initial_files = _existing_files(project) or {'package.json': '{"name":"app","private":true}'}
        sandbox.write_files(cid, initial_files)
        sandbox.install_deps(cid)
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
    except Exception as exc:
        import logging
        logging.getLogger('studio.tasks').error(
            'run_pipeline sandbox setup FAILED project=%s: %s', project_id, repr(exc), exc_info=True)
        # try to clean up a half-spawned container
        try:
            if 'cid' in dir() and cid:
                sandbox.kill_sandbox(cid)
        except Exception:
            pass
        state.status = 'failed'
        state.last_error = repr(exc)
        state.save(update_fields=['status', 'last_error'])
        project.status = 'failed'
        project.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': 'Не удалось поднять sandbox. Попробуйте перезапустить.',
            'type': 'failed',
        })
        return
    project.sandbox_container_id = cid
    project.preview_port = 3000
    project.save(update_fields=['sandbox_container_id', 'preview_port'])
    start_step.delay(project_id, 0)
```

`kill_sandbox` уже есть в `sandbox.py`. Использовать его в cleanup. Проверка `'cid' in dir()` нужна, т.к. ошибка могла произойти прямо в `spawn_sandbox`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `studio.sandbox.spawn_sandbox` так, чтобы он бросал `RuntimeError`; вызвать `run_pipeline(project_id)`; проверить `project.status == 'failed'` и `project.pipeline.status == 'failed'`, а не зависание в `coding`.

**Dependencies:** —

---

## Commit 5: Pause реально останавливает in-flight задачи (revoke)

**Sprint:** Fix
**Fixes/Implements:** BUG-04
**Files changed:**
- `src/studio/models.py` (миграция)
- `src/studio/tasks.py`
- `src/studio/views/pipeline.py`

**What to do:**
`PipelinePauseView` только меняет `state.status`, но уже запущенные Celery-задачи (`coder_iteration`, `agent_review`, `agent_test`, `merge_reports`) продолжают работать и доводят шаг до конца. Нужен «pause-флаг», который задачи проверяют, плюс попытка `revoke` текущей задачи.

1. Добавить поле в `StudioPipelineState` (models.py):
```python
    pause_requested = models.BooleanField(default=False)
    current_task_id = models.CharField(max_length=64, blank=True)
```
Затем `cd src && python manage.py makemigrations studio && python manage.py migrate`.

2. В `coder_iteration` сохранять id текущей задачи и проверять флаг паузы в начале:
```python
@shared_task(bind=True, max_retries=3, queue=QUEUE)
def coder_iteration(self, project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    if state.pause_requested or state.status in ('paused_manual', 'paused_on_loop'):
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн на паузе — шаг не запущен'})
        return
    state.current_task_id = self.request.id
    state.save(update_fields=['current_task_id'])
    ...
```
Аналогичную проверку `if state.pause_requested: return` добавить в начало `start_step`, `next_step`, и в `merge_reports` перед диспетчеризацией следующего шага / `coder_iteration`.

3. `PipelinePauseView.post`:
```python
    def post(self, request, id):
        from celery import current_app
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'paused_manual'
        state.pause_requested = True
        state.pause_reason = request.data.get('reason', 'Пауза пользователем')
        state.save(update_fields=['status', 'pause_requested', 'pause_reason'])
        if state.current_task_id:
            current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')
        project.status = 'paused'
        project.save(update_fields=['status'])
        return Response({'status': 'paused_manual'})
```

4. В `PipelineResumeView.post` сбрасывать флаг: добавить `state.pause_requested = False` рядом с `state.iteration_count = 0`.

> Замечание про gevent: `celery_studio` работает на gevent — `terminate=True` корректно прерывает только выполняющиеся задачи; задачи в очереди revoke-нутся без запуска. Главная защита от продолжения — флаг `pause_requested`, проверяемый на границах задач. `revoke` — best-effort поверх флага.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект в `coding`, `state.pause_requested=False`; вызвать `PipelinePauseView` (через APIRequestFactory с аутентифицированным юзером); проверить `state.pause_requested == True`, `state.status == 'paused_manual'`, `project.status == 'paused'`. Отдельный тест: вызвать `start_step` при `pause_requested=True` и убедиться, что `coder_iteration.delay` не вызывается (замокать).

**Dependencies:** Commit 1 (статусы), Commit 3 (`paused_on_loop`/`paused`-семантика уже устаканена).

---

## Commit 6: Считать planned_steps по реальным секциям COMMITS.md

**Sprint:** Fix
**Fixes/Implements:** BUG-06
**Files changed:**
- `src/studio/agents/planner.py`
- `src/studio/tasks.py`

**What to do:**
`PlannerAgent` берёт число шагов из маркера `<STEPS_COUNT>N</STEPS_COUNT>`, но `_get_step_text` в tasks.py режет план по `\n(?=#{2,3}\s)` (заголовки `##`/`###`). N от модели и фактическое число секций часто расходятся → `next_step` завершает проект раньше или зацикливает на несуществующих шагах.

Единый источник истины — фактическое число секций. Вынести функцию подсчёта секций и использовать её и в planner, и в `_get_step_text`.

1. В `tasks.py` сделать helper:
```python
def _split_steps(commits_md: str):
    return [p for p in re.split(r'\n(?=#{2,3}\s)', commits_md or '') if p.strip()]
```
Переписать `_get_step_text` через него:
```python
def _get_step_text(project, step_index):
    parts = _split_steps(project.commits_md_content)
    return parts[step_index] if step_index < len(parts) else project.commits_md_content
```

2. В `planner.py` после генерации `md` считать шаги по секциям, маркер использовать только как fallback:
```python
        md = re.sub(r'<STEPS_COUNT>\d+</STEPS_COUNT>', '', md).strip()
        from ..tasks import _split_steps
        sections = len(_split_steps(md))
        m = re.search(r'<STEPS_COUNT>(\d+)</STEPS_COUNT>', raw_md_before_strip)  # см. ниже
        steps = sections if sections > 0 else (int(m.group(1)) if m else 5)
```
Чтобы не возиться с порядком strip/search — проще: сначала `search` по исходному `md`, потом strip, потом `sections`, и взять `steps = sections or marker or 5`:
```python
        md_raw = self.run_prompt(PLANNER_SYSTEM, user, model=MODEL_SMART, max_tokens=8192)
        m = re.search(r'<STEPS_COUNT>(\d+)</STEPS_COUNT>', md_raw)
        marker = int(m.group(1)) if m else 0
        md = re.sub(r'<STEPS_COUNT>\d+</STEPS_COUNT>', '', md_raw).strip()
        from ..tasks import _split_steps
        steps = len(_split_steps(md)) or marker or 5
        self.project.commits_md_content = md
        self.project.save(update_fields=['commits_md_content'])
        return md, steps
```

3. `next_step` уже читает `project.interview_data['planned_steps']` — ничего менять не нужно, но т.к. пользователь может править COMMITS.md на review-странице, добавить пересчёт `planned_steps` при старте: в `run_pipeline`, перед `start_step.delay`, синхронизировать:
```python
    project.interview_data['planned_steps'] = len(_split_steps(project.commits_md_content)) or project.interview_data.get('planned_steps', 5)
    project.save(update_fields=['interview_data'])
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: задать `commits_md_content` с 3 секциями `## ...`; проверить `len(_split_steps(...)) == 3`; замокать `PlannerAgent.run_prompt`, вернуть план с 3 секциями и маркером `<STEPS_COUNT>7</STEPS_COUNT>`; проверить, что `run()` вернул `steps == 3` (секции, а не маркер).

**Dependencies:** —

---

## Commit 7: Добавить reap_stale_sandboxes в Celery beat

**Sprint:** Fix
**Fixes/Implements:** BUG-09
**Files changed:**
- `src/config/settings.py`

**What to do:**
Задача `reap_stale_sandboxes` определена в `tasks.py`, но нигде не запланирована. Проект использует `DatabaseScheduler` (`CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'`), а статического `CELERY_BEAT_SCHEDULE` в settings нет. Чтобы расписание было воспроизводимым из кода (а не только через админку), добавить `CELERY_BEAT_SCHEDULE` — `DatabaseScheduler` подхватывает статические записи при старте beat.

В `src/config/settings.py` рядом с `CELERY_BEAT_SCHEDULER` добавить:
```python
from celery.schedules import crontab  # вверх к остальным celery-импортам, если ещё нет

CELERY_BEAT_SCHEDULE = {
    **(globals().get('CELERY_BEAT_SCHEDULE') or {}),
    'studio-reap-stale-sandboxes': {
        'task': 'studio.tasks.reap_stale_sandboxes',
        'schedule': crontab(minute='*/30'),  # каждые 30 минут
        'options': {'queue': 'studio_queue'},
    },
}
```

Проверить, что имя задачи зарегистрировано как `studio.tasks.reap_stale_sandboxes` (по умолчанию Celery именует задачи по módule path; в `tasks.py` декоратор `@shared_task(queue=QUEUE)` без явного `name`, значит имя = `studio.tasks.reap_stale_sandboxes`).

**Test:**
```bash
cd src && python manage.py shell -c "from django.conf import settings; print(settings.CELERY_BEAT_SCHEDULE['studio-reap-stale-sandboxes'])"
cd src && python manage.py shell -c "from studio.tasks import reap_stale_sandboxes; print(reap_stale_sandboxes.name)"
```
Имя из второй команды должно совпадать со значением `task` в расписании. В проде убедиться по логам `celery_beat`, что задача тикает.

**Dependencies:** —

---

# Sprint E — Стабильность и UX

## Commit 8: Backend — endpoint реальной оценки стоимости (estimate API)

**Sprint:** E
**Fixes/Implements:** Real billing estimate API (подготовка к BUG-08)
**Files changed:**
- `src/studio/views/pipeline.py` (новый view) или `src/studio/views/projects.py`
- `src/studio/urls.py`

**What to do:**
`billing.estimate_stars(project, planned_steps)` уже есть. Не хватает HTTP-эндпоинта, чтобы фронт получал реальную оценку вместо хардкода. Добавить `EstimateView`:

```python
# views/pipeline.py
from ..billing import estimate_stars

class EstimateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        planned = project.interview_data.get('planned_steps')
        if not planned:
            from ..tasks import _split_steps
            planned = len(_split_steps(project.commits_md_content)) or 5
        estimate = estimate_stars(project, planned_steps=planned)
        return Response({
            'estimated_stars': estimate,
            'planned_steps': planned,
            'balance': request.user.pages_count,
            'affordable': request.user.pages_count >= estimate,
        })
```

URL в `urls.py`:
```python
from .views.pipeline import EstimateView
...
    path('projects/<uuid:id>/estimate/', EstimateView.as_view(), name='pipeline_estimate'),
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: создать проект с `planned_steps=3`; GET `/studio/projects/<id>/estimate/`; проверить, что `estimated_stars` совпадает с `estimate_stars(project, 3)` и `affordable` отражает баланс.

**Dependencies:** Commit 6 (`_split_steps` доступен).

---

## Commit 9: Frontend — клиент studioApi.estimate

**Sprint:** E
**Fixes/Implements:** Real billing estimate API (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`

**What to do:**
Добавить тип и метод:
```ts
export interface StudioEstimate {
  estimated_stars: number;
  planned_steps: number;
  balance: number;
  affordable: boolean;
}

// внутри studioApi
  estimate: (id: string) =>
    request<StudioEstimate>(`/studio/projects/${id}/estimate/`),
```

**Test:**
```bash
cd frontend && npm run build
```
Сборка проходит, тип `StudioEstimate` экспортируется.

**Dependencies:** Commit 8.

---

## Commit 10: Frontend — review-страница использует реальную оценку

**Sprint:** E
**Fixes/Implements:** BUG-08
**Files changed:**
- `frontend/app/studio/[id]/review/page.tsx`

**What to do:**
Заменить хардкод `estimatedStars={50}`. Добавить запрос оценки и пробросить в `BillingEstimate`:

```tsx
  const { data: estimate } = useQuery({
    queryKey: ['studio-estimate', id],
    queryFn: () => studioApi.estimate(id),
    enabled: !!project && (project.status === 'ready' || project.status === 'planning'),
  });
...
  <BillingEstimate
    estimatedStars={estimate?.estimated_stars}
    plannedSteps={estimate?.planned_steps ?? plannedSteps}
  />
```
Если `estimate?.affordable === false`, под кнопкой «Начать кодинг» показать предупреждение (Lucide `AlertTriangle`, без эмодзи): «Недостаточно звёзд: нужно ~{estimated_stars}, на балансе {balance}». Кнопку при этом не блокировать насильно (бэкенд сам поставит паузу), но визуально предупредить.

`BillingEstimate` уже корректно рендерит `~{estimatedStars ?? '?'}` — отдельных правок компонента не нужно.

**Test:**
```bash
cd frontend && npm run build
```
Ручная проверка: открыть `/studio/<id>/review` — отображается реальная оценка из API, а не «~50».

**Dependencies:** Commit 9.

---

## Commit 11: AgentLog SSE — авто-reconnect, одна подписка, без дублей

**Sprint:** E
**Fixes/Implements:** BUG-07
**Files changed:**
- `frontend/components/studio/AgentLog.tsx`

**What to do:**
Две проблемы: (1) `es.onerror = () => es.close()` навсегда убивает поток без reconnect; (2) при двух монтированиях компонента создаются две EventSource → две Redis-подписки (через `PipelineEventsView`).

Переписать `useEffect` с реконнектом и единственным активным соединением через ref + флаг закрытия:

```tsx
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? '';
    let es: EventSource | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;
      es = new EventSource(
        `${base}/studio/projects/${projectId}/events/`,
        { withCredentials: true },
      );
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type !== 'connected') {
            setLines((prev) => [...prev, data]);
          }
        } catch {}
      };
      es.onerror = () => {
        es?.close();
        if (!closed) {
          retryTimer = setTimeout(connect, 3000);  // backoff reconnect
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      es?.close();
    };
  }, [projectId]);
```

Это гарантирует ровно одно живое соединение на смонтированный компонент и переподключение при разрыве. Для защиты от двойного монтирования (React StrictMode dev) флаг `closed` в cleanup корректно закрывает старое соединение до создания нового.

**Test:**
```bash
cd frontend && npm run build
```
Ручная: открыть workspace, в DevTools → Network → EventSource видно одно соединение `/events/`; перезапустить `celery_studio` — после разрыва соединение восстанавливается через ~3с, лог продолжает капать.

**Dependencies:** —

---

## Commit 12: CodeViewer — подсветка синтаксиса

**Sprint:** E
**Fixes/Implements:** Syntax highlighting
**Files changed:**
- `frontend/components/studio/CodeViewer.tsx`
- `frontend/package.json` (если нужна зависимость)

**What to do:**
Проект уже использует `rehype-highlight` (highlight.js) для markdown. Переиспользовать highlight.js напрямую для CodeViewer, чтобы не тащить новый пакет. В `CodeViewer.tsx`:

```tsx
'use client';
import { useEffect, useRef } from 'react';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

export function CodeViewer({ content, language }: { content: string; language?: string }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (ref.current) {
      ref.current.removeAttribute('data-highlighted');
      hljs.highlightElement(ref.current);
    }
  }, [content, language]);

  return (
    <pre className="text-xs overflow-auto h-full m-0">
      <code ref={ref} className={language ? `language-${language}` : ''}>
        {content}
      </code>
    </pre>
  );
}
```
Если `highlight.js` не в зависимостях фронта напрямую (он приходит транзитивно через `rehype-highlight`) — добавить явно: `cd frontend && npm i highlight.js`. Сопоставление расширения файла → language: маппить из `StudioFile.language` (бэкенд) или из расширения пути в месте вызова.

**Test:**
```bash
cd frontend && npm run build
```
Ручная: открыть файл `.tsx`/`.ts` в workspace — код подсвечен.

**Dependencies:** —

---

## Commit 13: Backend — DiffViewer данные (diff между версиями)

**Sprint:** E
**Fixes/Implements:** DiffViewer wired (backend)
**Files changed:**
- `src/studio/views/files.py`
- `src/studio/urls.py`

**What to do:**
`DiffViewer.tsx` — мёртвый код, нет данных. Дать ему API: diff содержимого файла между текущим состоянием и git_sha версии (через Gitea). Добавить `FileDiffView`:

```python
# views/files.py
class FileDiffView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, file_id):
        from .. import gitea_client
        f = StudioFile.objects.get(pk=file_id, project_id=id, project__user=request.user)
        project = f.project
        ref = request.query_params.get('ref')  # git_sha версии
        old = ''
        if ref and project.repo_url and project.user.gitea_username:
            owner = project.user.gitea_username
            repo = project.repo_url.rstrip('/').split('/')[-1]
            old = gitea_client.get_file_content(owner, repo, f.path, ref=ref)
        return Response({'path': f.path, 'old': old, 'new': f.content})
```
URL:
```python
    path('projects/<uuid:id>/files/<int:file_id>/diff/', FileDiffView.as_view(), name='file_diff'),
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `gitea_client.get_file_content` → вернуть «старое содержимое»; GET diff с `?ref=abc`; проверить `{'old': 'старое...', 'new': <current>}`.

**Dependencies:** —

---

## Commit 14: Ручные правки файлов идут в sandbox и Gitea

**Sprint:** E
**Fixes/Implements:** BUG-10, Manual edits to sandbox
**Files changed:**
- `src/studio/views/files.py`
- `src/studio/tasks.py`

**What to do:**
`FileDetailView.perform_update` сохраняет только в БД. Нужно: после ручной правки протолкнуть файл в работающий sandbox и (если есть repo) в Gitea. Делать это асинхронно через Celery, чтобы PATCH отвечал быстро.

1. Новая задача в `tasks.py`:
```python
@shared_task(queue=QUEUE)
def sync_manual_edit(project_id, file_id):
    from . import gitea_client
    project = StudioProject.objects.get(id=project_id)
    f = StudioFile.objects.get(pk=file_id, project=project)
    if project.sandbox_container_id:
        try:
            sandbox.write_files(project.sandbox_container_id, {f.path: f.content})
        except Exception as exc:
            publish_event(project_id, {'agent': 'system', 'level': 'warning',
                                       'text': f'Не удалось записать {f.path} в sandbox: {exc}'})
    owner = project.user.gitea_username
    repo = project.repo_url.rstrip('/').split('/')[-1] if project.repo_url else None
    if owner and repo:
        try:
            gitea_client.put_file(owner, repo, f.path, f.content,
                                  message=f'Manual edit: {f.path}')
        except Exception as exc:
            publish_event(project_id, {'agent': 'system', 'level': 'warning',
                                       'text': f'Git push failed for {f.path}: {exc}'})
    publish_event(project_id, {'agent': 'system', 'level': 'info',
                               'text': f'Файл обновлён: {f.path}'})
```

2. `FileDetailView.perform_update`:
```python
    def perform_update(self, serializer):
        instance = serializer.save(last_modified_by='user')
        from ..tasks import sync_manual_edit
        sync_manual_edit.delay(str(self.kwargs['id']), instance.pk)
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `sandbox.write_files` и `gitea_client.put_file`; PATCH файла; проверить, что `sync_manual_edit` поставлена в очередь (мок `sync_manual_edit.delay`) с правильными аргументами. Отдельный тест прямого вызова `sync_manual_edit` проверяет, что `write_files` получил `{path: content}`.

**Dependencies:** —

---

## Commit 15: Backend — subdomain/path preview proxy

**Sprint:** E
**Fixes/Implements:** Subdomain preview
**Files changed:**
- `src/studio/views/pipeline.py` (PreviewProxyView)
- `src/studio/urls.py`
- `nginx.conf` (комментарий-инструкция)

**What to do:**
Preview сейчас в iframe указывает напрямую на порт sandbox, который изолирован в `sandbox_net` и недоступен браузеру. Нужен прокси через Django/Nginx. Простой вариант: Django-вью, которое проксирует HTTP к контейнеру по DNS-имени `sandbox_<id8>:3000` внутри docker-сети.

`web` контейнер должен быть подключён к `STUDIO_SANDBOX_NET`, чтобы резолвить имя sandbox. Проверить/добавить в `docker-compose.yml` сеть для сервиса `web` (см. Commit 16 — там же лимиты; здесь — сеть).

```python
# views/pipeline.py
import requests as _rq
from django.http import HttpResponse

class PreviewProxyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, path=''):
        project = StudioProject.objects.get(id=id, user=request.user)
        if not project.sandbox_container_id:
            return HttpResponse('Sandbox не запущен', status=503)
        host = project.sandbox_container_id  # имя контейнера = DNS-имя в sandbox_net
        try:
            upstream = _rq.get(f'http://{host}:3000/{path}', timeout=10,
                               headers={'Accept': request.headers.get('Accept', '*/*')})
        except Exception:
            return HttpResponse('Preview недоступен', status=502)
        resp = HttpResponse(upstream.content, status=upstream.status_code)
        ct = upstream.headers.get('Content-Type')
        if ct:
            resp['Content-Type'] = ct
        return resp
```
URL:
```python
    re_path(r'projects/(?P<id>[0-9a-f-]+)/preview/(?P<path>.*)$', PreviewProxyView.as_view(), name='preview_proxy'),
```
(`from django.urls import re_path` в urls.py.)

В `nginx.conf` добавить комментарий: preview обслуживается через `/api/v1/studio/projects/<id>/preview/` (буферизация off для dev-сервера HMR — на этом этапе достаточно базового проксирования; WebSocket HMR — отдельная доработка).

> Ограничение: dev-сервер Next.js/Vite использует WebSocket для HMR — базовый прокси отдаёт статическую страницу без live-reload. Для MVP preview этого достаточно; полноценный WS-прокси — backlog.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `requests.get` → вернуть `<html>ok</html>` со статусом 200 и `Content-Type: text/html`; GET preview; проверить тело и content-type. Ручная: поднять пайплайн, открыть PreviewPanel — рендерится страница из sandbox.

**Dependencies:** Commit 4 (sandbox стабильно поднимается).

---

## Commit 16: Frontend — PreviewPanel через прокси-URL

**Sprint:** E
**Fixes/Implements:** Subdomain preview (frontend)
**Files changed:**
- `frontend/components/studio/PreviewPanel.tsx`

**What to do:**
Указать iframe `src` на прокси-эндпоинт вместо прямого порта:
```tsx
const base = process.env.NEXT_PUBLIC_API_URL ?? '';
const src = `${base}/studio/projects/${projectId}/preview/`;
```
Добавить кнопку «Обновить» (Lucide `RotateCw`) — пересоздаёт iframe (через ключ-стейт `reloadKey`), и индикатор загрузки. Если sandbox не запущен (502/503) — показать «Preview появится после запуска кодинга».

**Test:**
```bash
cd frontend && npm run build
```
Ручная: iframe грузит страницу через `/studio/projects/<id>/preview/`.

**Dependencies:** Commit 15.

---

# Sprint F — Полнота функционала

## Commit 17: ContextChat — LLM-ответ на паузе (backend)

**Sprint:** F
**Fixes/Implements:** ContextChat LLM (backend)
**Files changed:**
- `src/studio/views/pipeline.py` (ContextChatView)
- `src/studio/urls.py`
- `src/studio/agents/` (новый `assistant.py`)

**What to do:**
`ContextChat.tsx` — пока статичная панель-подсказка. Дать ей реальный LLM-диалог в контексте проекта (PROJECT.md, текущий шаг, last_error/pause_reason). Новый лёгкий агент:

```python
# agents/assistant.py
from .base import BaseAgent, MODEL_FAST

ASSISTANT_SYSTEM = (
    "Ты ассистент студии генерации приложений. Пользователь на паузе пайплайна. "
    "Кратко отвечай на вопросы по проекту и предлагай, как продолжить (hint/skip). "
    "Контекст проекта дан ниже. Отвечай по-русски, по делу."
)

class AssistantAgent(BaseAgent):
    name = 'assistant'
    model = MODEL_FAST

    def answer(self, message: str, history: list) -> str:
        state = self.project.pipeline
        ctx = (
            f"PROJECT.md:\n{self.project.project_md_content[:3000]}\n\n"
            f"Текущий шаг: {state.step_index}\n"
            f"Причина паузы: {state.pause_reason}\n"
            f"Последняя ошибка: {state.last_error[:1000]}\n"
        )
        hist = '\n'.join(f"{h['role']}: {h['text']}" for h in history[-6:])
        user = f"{ctx}\nДиалог:\n{hist}\n\nВопрос: {message}"
        return self.run_prompt(ASSISTANT_SYSTEM, user, model=MODEL_FAST, max_tokens=1500, temperature=0.5)
```

View (синхронно — короткий ответ, или через Celery+SSE; для MVP синхронно):
```python
class ContextChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..agents.assistant import AssistantAgent
        from ..billing import can_afford, charge
        cost = 1
        if not can_afford(request.user, cost):
            return Response({'error': 'Недостаточно звёзд'}, status=402)
        msg = request.data.get('message', '')
        history = project.interview_data.get('assistant_history', [])
        answer = AssistantAgent(project).answer(msg, history)
        charge(request.user, cost, project)
        history += [{'role': 'user', 'text': msg}, {'role': 'assistant', 'text': answer}]
        project.interview_data['assistant_history'] = history[-20:]
        project.save(update_fields=['interview_data'])
        return Response({'answer': answer})
```
URL: `path('projects/<uuid:id>/chat/', ContextChatView.as_view(), name='context_chat')`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `AssistantAgent.answer` → «ответ»; POST `/chat/` с `message`; проверить, что ответ возвращён, `charge` вызван, `assistant_history` пополнилась двумя записями.

**Dependencies:** Commit 1, Commit 3 (билинг/паузы устаканены).

---

## Commit 18: ContextChat — frontend-диалог

**Sprint:** F
**Fixes/Implements:** ContextChat LLM (frontend)
**Files changed:**
- `frontend/components/studio/ContextChat.tsx`
- `frontend/lib/api/studio.ts`

**What to do:**
В `studio.ts`:
```ts
  contextChat: (id: string, message: string) =>
    request<{ answer: string }>(`/studio/projects/${id}/chat/`, {
      method: 'POST', body: JSON.stringify({ message }),
    }),
```
В `ContextChat.tsx` — поле ввода + список сообщений (локальный стейт), отправка через `useMutation`, индикатор загрузки (Lucide `Loader2`), кнопки быстрых действий: «Продолжить», «Пропустить шаг», «Дать подсказку» — последние вызывают существующий `studioApi.resume(...)`.

**Test:**
```bash
cd frontend && npm run build
```
Ручная: на паузе ввести вопрос — приходит ответ ассистента.

**Dependencies:** Commit 17.

---

## Commit 19: SPA-краулинг через Playwright (clone-mode)

**Sprint:** F
**Fixes/Implements:** SPA crawling Playwright
**Files changed:**
- `src/studio/tasks.py`
- `src/studio/crawler.py` (уже есть `crawl_spa`)

**What to do:**
`crawl_spa` готов, но `crawl_and_analyze` зовёт статический `crawl`. SPA (React/Vue) отдаёт пустой `<div id="root">`. Маршрутизировать: если статический текст слишком короткий → перекинуть на Playwright-воркер (`celery_studio_playwright`, prefork — НЕ gevent).

1. Отдельная задача в очереди playwright. В `docker-compose.yml` `celery_studio_playwright` слушает свою очередь (например `studio_playwright`). Объявить:
```python
@shared_task(bind=True, max_retries=1, queue='studio_playwright')
def crawl_spa_task(self, project_id):
    from .crawler import crawl_spa
    project = StudioProject.objects.get(id=project_id)
    try:
        data = crawl_spa(project.target_url)
        project.interview_data['crawled'] = {'title': data['title'], 'text': data['text'][:8000]}
        project.status = 'planning'
        project.save(update_fields=['interview_data', 'status'])
        agent_analyze.delay(project_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
```
2. В `crawl_and_analyze` после статического crawl проверять достаточность контента:
```python
        data = crawl(project.target_url)
        if len((data.get('text') or '').strip()) < 200:
            publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'SPA — рендерю через браузер...'})
            crawl_spa_task.delay(project_id)
            return
        project.interview_data['crawled'] = {'title': data['title'], 'text': data['text'][:8000]}
        ...
```

Проверить, что `celery_studio_playwright` подписан на очередь `studio_playwright` (флаг `-Q` в команде сервиса в `docker-compose.yml`).

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `crawl` → вернуть `{'text': '', 'title': ''}`; вызвать `crawl_and_analyze`; проверить, что `crawl_spa_task.delay` вызвана (мок). Второй тест: `crawl` возвращает длинный текст → `crawl_spa_task` НЕ вызывается.

**Dependencies:** —

---

## Commit 20: Режимы approval — semi и manual (backend gate)

**Sprint:** F
**Fixes/Implements:** Semi/Manual approval mode
**Files changed:**
- `src/studio/tasks.py`
- `src/studio/views/pipeline.py` (ApproveStepView)
- `src/studio/urls.py`

**What to do:**
`StudioProject.mode` (`auto`/`semi`/`manual`) уже есть, но пайплайн всегда идёт авто. Поведение:
- `auto`: после успешного шага сразу `next_step` (как сейчас).
- `semi`: после успешного шага — пауза «ждёт подтверждения», пользователь жмёт «Подтвердить» → следующий шаг.
- `manual`: пауза перед КАЖДЫМ шагом (и до первого).

В `merge_reports`, в ветке «шаг пройден», вместо безусловного `commit_to_gitea.delay`:
```python
    if review.get('passed') and test.get('passed'):
        publish_event(...)  # как есть
        commit_to_gitea.delay(project_id, step_index)
```
оставить commit, но в `commit_to_gitea` после `StudioVersion.objects.create(...)` перед `next_step.delay` учесть режим:
```python
    if project.mode in ('semi', 'manual'):
        state = project.pipeline
        state.status = 'paused_manual'
        state.pause_reason = f'Шаг {step_index} готов — подтвердите продолжение'
        state.save(update_fields=['status', 'pause_reason'])
        project.status = 'paused'
        project.save(update_fields=['status'])
        publish_event(project_id, {'agent': 'system', 'level': 'info',
                                   'text': state.pause_reason, 'type': 'awaiting_approval'})
        return
    next_step.delay(project_id, step_index)
```
Эндпоинт подтверждения:
```python
class ApproveStepView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'running'
        state.pause_requested = False
        state.save(update_fields=['status', 'pause_requested'])
        project.status = 'coding'
        project.save(update_fields=['status'])
        from ..tasks import next_step
        next_step.delay(str(project.id), state.step_index)
        return Response({'status': 'running'})
```
URL: `path('projects/<uuid:id>/approve/', ApproveStepView.as_view(), name='approve_step')`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проект `mode='semi'`, прогнать `commit_to_gitea` (замокав gitea) → проверить `status='paused'`, `next_step` НЕ вызван. Затем `ApproveStepView` → `next_step.delay` вызван.

**Dependencies:** Commit 5 (`pause_requested`), Commit 1.

---

## Commit 21: Frontend — UI подтверждения шага (semi/manual)

**Sprint:** F
**Fixes/Implements:** Semi/Manual approval mode (frontend)
**Files changed:**
- `frontend/components/studio/ContextChat.tsx` или новый `ApprovalBar.tsx`
- `frontend/lib/api/studio.ts`

**What to do:**
В `studio.ts`:
```ts
  approve: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/approve/`, { method: 'POST' }),
```
Когда `pipeline.status === 'paused_manual'` и событие `type === 'awaiting_approval'`, показать панель с кнопкой «Подтвердить и продолжить» (Lucide `Check`) → `studioApi.approve(id)`. Для `manual`-режима — та же панель перед стартом каждого шага.

**Test:**
```bash
cd frontend && npm run build
```
Ручная: создать проект с `mode=semi`, после первого шага появляется кнопка подтверждения.

**Dependencies:** Commit 20.

---

## Commit 22: Роутинг сложных шагов на Opus (smart Coder)

**Sprint:** F
**Fixes/Implements:** Complex step → Opus routing
**Files changed:**
- `src/studio/agents/coder.py`
- `src/studio/tasks.py`
- `src/studio/billing.py`

**What to do:**
`CoderAgent` всегда использует `MODEL_FAST` (deepseek-v3). Сложные шаги (много файлов, ключевые слова) лучше отдавать `MODEL_SMART` (claude-opus-4-8). Простая эвристика по тексту шага.

В `coder.py`:
```python
from .base import BaseAgent, MODEL_FAST, MODEL_SMART

COMPLEX_HINTS = ('auth', 'оплат', 'payment', 'websocket', 'realtime', 'state machine',
                 'миграц', 'schema', 'api', 'интеграц')

class CoderAgent(BaseAgent):
    name = 'coder'
    model = MODEL_FAST

    def _pick_model(self, step_text: str, existing_files: dict) -> str:
        text = step_text.lower()
        file_mentions = step_text.count('`') // 2  # грубая оценка кол-ва файлов в шаге
        if file_mentions >= 5 or any(h in text for h in COMPLEX_HINTS):
            return MODEL_SMART
        return MODEL_FAST

    def run(self, step_index, step_text, existing_files):
        model = self._pick_model(step_text, existing_files)
        ...
        data = self.run_json(CODER_SYSTEM, user, model=model, max_tokens=8192)
        # вернуть и использованную модель, чтобы tasks.py знал тариф
        self.last_model = model
        return data.get('files', {})
```
В `billing.py` различать тариф coder по модели — добавить функцию:
```python
def coder_tier_for_model(model: str) -> str:
    from .agents.base import MODEL_SMART
    return 'smart' if model == MODEL_SMART else 'fast'
```
В `tasks.coder_iteration` после `CoderAgent(project).run(...)` использовать `agent.last_model` для расчёта стоимости (заменить фиксированный `_billing_charge(project, 'coder', ...)` на динамический tier). Минимально — если `last_model == MODEL_SMART`, зарядить как 'smart' budget. Реализовать через расширение `_billing_charge`, принимающий явный tier override:
```python
def _billing_charge(project, agent_name, step_index, tier_override=None):
    base_tier, budget = AGENT_BUDGET.get(agent_name, ('fast', 2000))
    tier = tier_override or base_tier
    cost = max(1, int((budget / 1000.0) * STAR_RATE[tier]))
    ...
```
И в coder-ветке: `_billing_charge(project, 'coder', step_index, tier_override=coder_tier_for_model(agent.last_model))`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: `_pick_model('Реализуй auth и payment', {})` → `MODEL_SMART`; `_pick_model('Добавь кнопку', {})` → `MODEL_FAST`. Тест billing: charge для smart-coder больше, чем для fast.

**Dependencies:** Commit 2, Commit 3 (сигнатура `_billing_charge` — менять согласованно).

---

## Commit 23: Атомарные commit-ы в Gitea (один commit на шаг)

**Sprint:** F
**Fixes/Implements:** Atomic Gitea commits
**Files changed:**
- `src/studio/gitea_client.py`
- `src/studio/tasks.py`

**What to do:**
Сейчас `commit_to_gitea` делает по одному `put_file` на каждый файл → N commit-ов на шаг, шумная история и неатомарность. Использовать Gitea Contents Batch API (`POST /repos/{owner}/{repo}/contents` с массивом `files`), один commit на шаг.

В `gitea_client.py`:
```python
def put_files_batch(owner, repo, files: dict, message, branch='main') -> dict:
    """Один commit на множество файлов через /contents batch API."""
    ops = []
    for path, content in files.items():
        url = _api(f'/repos/{owner}/{repo}/contents/{path}')
        get = requests.get(url, headers=_headers(), params={'ref': branch})
        op = {
            'operation': 'update' if get.status_code == 200 else 'create',
            'path': path,
            'content': base64.b64encode(content.encode()).decode(),
        }
        if get.status_code == 200:
            op['sha'] = get.json().get('sha')
        ops.append(op)
    r = requests.post(
        _api(f'/repos/{owner}/{repo}/contents'),
        headers=_headers(),
        json={'files': ops, 'message': message, 'branch': branch},
    )
    return r.json()
```
В `commit_to_gitea` заменить цикл `put_file` на единый `put_files_batch`:
```python
    if owner and repo:
        files = {f.path: f.content for f in project.files.all()}
        try:
            res = gitea_client.put_files_batch(owner, repo, files, message=f'Step {step_index}')
            git_sha = (res.get('commit') or {}).get('sha', '')
        except Exception as exc:
            publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': f'Git push failed: {exc}'})
```

> Проверить версию Gitea в `docker-compose.yml` — batch Contents API доступен с Gitea 1.18+. Если версия старее — оставить `put_file` в цикле, но это backlog.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `requests.get` (sha lookup) и `requests.post`; вызвать `put_files_batch` с 3 файлами; проверить, что `requests.post` вызван ОДИН раз с массивом из 3 `files`.

**Dependencies:** —

---

## Commit 24: Лимит sandbox на пользователя

**Sprint:** F
**Fixes/Implements:** Per-user sandbox limit
**Files changed:**
- `src/config/settings.py`
- `src/studio/sandbox.py`
- `src/studio/tasks.py`

**What to do:**
Нет ограничения на число одновременных sandbox-контейнеров у пользователя — риск исчерпания ресурсов хоста. Ввести лимит.

1. Настройка: `STUDIO_MAX_SANDBOXES_PER_USER = int(os.getenv('STUDIO_MAX_SANDBOXES_PER_USER', '2'))`.
2. Helper в `sandbox.py` — посчитать активные контейнеры пользователя по метке. Добавить в `spawn_sandbox` метку с user_id:
```python
        labels={'studio_project': project_id, 'studio_user': str(user_id)},
```
(прокинуть `user_id` параметром в `spawn_sandbox`).
```python
def count_user_sandboxes(user_id) -> int:
    client = get_docker()
    return len(client.containers.list(filters={'label': f'studio_user={user_id}'}))
```
3. В `run_pipeline` перед `spawn_sandbox`:
```python
    from django.conf import settings as _s
    if sandbox.count_user_sandboxes(project.user_id) >= _s.STUDIO_MAX_SANDBOXES_PER_USER:
        publish_event(project_id, {'agent': 'system', 'level': 'error',
            'text': 'Достигнут лимит одновременных проектов. Завершите другой проект.'})
        project.status = 'paused'; project.save(update_fields=['status'])
        state.status = 'paused_manual'; state.pause_reason = 'Лимит sandbox'; state.save()
        return
    cid = sandbox.spawn_sandbox(project_id, project.user_id)
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `sandbox.count_user_sandboxes` → вернуть значение >= лимита; вызвать `run_pipeline`; проверить, что `spawn_sandbox` НЕ вызван и проект ушёл в паузу.

**Dependencies:** Commit 4 (try/except sandbox), Commit 3 (паузы).

---

## Commit 25: Резервирование звёзд при старте пайплайна

**Sprint:** F
**Fixes/Implements:** Star reservation
**Files changed:**
- `src/studio/models.py` (уже есть `stars_reserved`)
- `src/studio/billing.py`
- `src/studio/tasks.py`
- `src/studio/views/pipeline.py`

**What to do:**
Поле `stars_reserved` есть, но не используется. Идея: при старте пайплайна зарезервировать оценку (`estimate_stars`) с баланса, чтобы пользователь не потратил их в другом месте; по факту списывать из резерва, остаток вернуть в конце.

1. `billing.py`:
```python
def reserve(user, amount, project):
    if user.pages_count < amount:
        return False
    user.spend_pages(amount)
    project.stars_reserved += amount
    project.save(update_fields=['stars_reserved'])
    return True

def charge_from_reserve(amount, project):
    """Списывает из резерва. Если резерв мал — добирает из баланса пользователя."""
    take = min(amount, project.stars_reserved)
    project.stars_reserved -= take
    project.stars_spent += take
    rest = amount - take
    if rest > 0:
        if project.user.pages_count < rest:
            return False
        project.user.spend_pages(rest)
        project.stars_spent += rest
    project.save(update_fields=['stars_reserved', 'stars_spent'])
    return True

def release_reserve(project):
    if project.stars_reserved > 0:
        project.user.add_pages(project.stars_reserved)
        project.stars_reserved = 0
        project.save(update_fields=['stars_reserved'])
```
2. В `run_pipeline` (после affordability-проверки, до старта шага) вызвать `reserve(project.user, estimate_stars(project, planned), project)`. Если `False` → пауза «недостаточно звёзд».
3. `_billing_charge` использует `charge_from_reserve` вместо `charge`; при `False` → `InsufficientStars`.
4. В `next_step` при завершении проекта и в `_pause_no_funds`/refund-ветке `merge_reports` вызывать `release_reserve(project)`.

> Это полноценное закрытие идемпотентности из примечания к Commit 2/3.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: `reserve` уменьшает `pages_count`, увеличивает `stars_reserved`; `charge_from_reserve` тратит из резерва; `release_reserve` возвращает остаток на баланс. Интеграционно: запустить и завершить мини-пайплайн (всё замокано), проверить, что `stars_reserved == 0` в конце и сумма списаний сходится.

**Dependencies:** Commit 3, Commit 8 (`estimate_stars` через API/планирование), Commit 22 (общая сигнатура `_billing_charge`).

---

# Sprint G — Качество генерации

## Commit 26: Coder получает полный контент релевантных файлов

**Sprint:** G
**Fixes/Implements:** Multi-file context for Coder
**Files changed:**
- `src/studio/agents/coder.py`

**What to do:**
Сейчас Coder видит только первые 10 файлов, обрезанных до 2000 символов (`c[:2000]`) — он переписывает файлы вслепую. Улучшить отбор контекста: выбирать файлы, упомянутые в тексте шага, целиком; остальные — список путей.

```python
    def run(self, step_index, step_text, existing_files):
        import re
        mentioned = [p for p in existing_files if p in step_text]
        # плюс по расширению/именам из бэктиков
        ticked = re.findall(r'`([^`]+)`', step_text)
        for t in ticked:
            if t in existing_files and t not in mentioned:
                mentioned.append(t)
        full = {p: existing_files[p] for p in mentioned[:8]}
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(пусто)'
        body = '\n'.join(f'### {p}\n```\n{c[:6000]}\n```' for p, c in full.items())
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}\n\n"
            f"Шаг #{step_index}:\n{step_text}\n\n"
            f"Все файлы проекта:\n{listing}\n\n"
            f"Содержимое релевантных файлов:\n{body}"
        )
        ...
```
Поднять лимит per-file с 2000 до 6000, число полных файлов — до 8, остальные дать списком путей.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: проверить, что в `user`-промпте, переданном в `run_json` (замокать `run_json`, перехватить аргумент), присутствует полное содержимое файла, упомянутого в `step_text`, и список всех путей.

**Dependencies:** Commit 22 (тот же файл `coder.py` — делать после).

---

## Commit 27: Реальный прогон тестов/сборки в sandbox

**Sprint:** G
**Fixes/Implements:** Real test execution
**Files changed:**
- `src/studio/sandbox.py`
- `src/studio/tasks.py`
- `src/studio/agents/tester.py`

**What to do:**
`TesterAgent` сейчас лишь анализирует логи dev-сервера через LLM. Добавить реальный запуск проверок (build/typecheck) в контейнере и отдавать реальный exit code Tester-у.

1. `sandbox.py`:
```python
def run_build_check(container_id: str) -> tuple:
    """Запускает быстрый typecheck/build. Возвращает (exit_code, output)."""
    # Next.js/React: попытка type-check, иначе build
    return exec_command(container_id, 'pnpm -s exec tsc --noEmit 2>&1 | tail -n 100 || pnpm -s build 2>&1 | tail -n 120')
```
2. В `agent_test` собирать реальный результат:
```python
@shared_task(queue=QUEUE)
def agent_test(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.tester import TesterAgent
    logs, exit_code = '', None
    if project.sandbox_container_id:
        try:
            exit_code, build_out = sandbox.run_build_check(project.sandbox_container_id)
            logs = build_out
        except Exception as exc:
            logs = f'build check error: {exc}'; exit_code = 1
    report = TesterAgent(project).run(logs, exit_code=exit_code)
    publish_event(project_id, {'agent': 'tester', 'level': 'info', 'text': report.get('summary', '')})
    return {'kind': 'test', 'report': report}
```
3. `TesterAgent.run` принимает `exit_code` и трактует ненулевой как fail независимо от LLM:
```python
    def run(self, build_logs: str, exit_code=None) -> dict:
        user = f"exit_code={exit_code}\nЛоги сборки:\n{build_logs[-6000:]}"
        report = self.run_json(TESTER_SYSTEM, user, model=MODEL_FAST, max_tokens=4000)
        if exit_code is not None and exit_code != 0:
            report['build_ok'] = False
            report['passed'] = False
        report.setdefault('passed', report.get('build_ok', False) and not report.get('errors'))
        return report
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: `TesterAgent.run(logs='', exit_code=1)` (замокав `run_json` → `{'passed': True}`) → итог `passed == False` (exit_code побеждает). Ручная: шаг с битым TS не проходит ревью-цикл.

**Dependencies:** Commit 4 (sandbox), Commit 15.

---

## Commit 28: Ожидание компиляции перед тестом (wait-for-compile)

**Sprint:** G
**Fixes/Implements:** Wait-for-compile
**Files changed:**
- `src/studio/sandbox.py`
- `src/studio/tasks.py`

**What to do:**
После записи файлов dev-сервер компилирует не мгновенно — Tester может прочитать логи до завершения сборки и дать ложный «passed». Добавить активное ожидание готовности dev-сервера.

```python
# sandbox.py
def wait_for_ready(container_id: str, timeout=60) -> bool:
    """Опрашивает локальный dev-сервер внутри контейнера до HTTP 200 или таймаута."""
    import time
    for _ in range(timeout // 3):
        code, out = exec_command(
            container_id,
            'curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ || echo 000')
        if out.strip().endswith('200'):
            return True
        time.sleep(3)
    return False
```
В `coder_iteration` после `sandbox.write_files(...)` и до `chord(...)`:
```python
        if project.sandbox_container_id:
            sandbox.write_files(project.sandbox_container_id, files)
            sandbox.wait_for_ready(project.sandbox_container_id, timeout=60)
```
> Внимание про gevent: `time.sleep` под gevent кооперативно уступает loop — это безопасно в `celery_studio` (gevent-пул). Если задача в prefork-пуле — тоже ок.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `exec_command` так, чтобы первые 2 вызова вернули `'000'`, третий — `'...200'`; `wait_for_ready` → `True`, и вызвался 3 раза. Таймаут-кейс: всегда `'000'` → `False`.

**Dependencies:** Commit 27.

---

## Commit 29: Diff-ориентированный Review

**Sprint:** G
**Fixes/Implements:** Diff-based Review
**Files changed:**
- `src/studio/agents/reviewer.py`
- `src/studio/tasks.py`

**What to do:**
`ReviewerAgent` сейчас получает ВСЕ файлы целиком (`_existing_files(project)`) — дорого и размывает фокус. Передавать только файлы, изменённые на этом шаге (их Coder вернул), а контекст остального — списком.

1. `coder_iteration` уже знает `files` (результат Coder). Передать их паттерны в reports. Проще: в `coder_iteration` сохранить набор изменённых путей в state:
```python
        state = project.pipeline
        state.fix_plan = state.fix_plan  # без изменений
        project.interview_data.setdefault('last_changed', {})[str(step_index)] = list(files.keys())
        project.save(update_fields=['interview_data'])
```
2. `agent_review` берёт только изменённые файлы:
```python
@shared_task(queue=QUEUE)
def agent_review(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.reviewer import ReviewerAgent
    changed = project.interview_data.get('last_changed', {}).get(str(step_index), [])
    all_files = _existing_files(project)
    review_files = {p: all_files[p] for p in changed if p in all_files} or all_files
    report = ReviewerAgent(project).run(_get_step_text(project, step_index), review_files)
    ...
```
3. В `ReviewerAgent.run` добавить в промпт список остальных файлов (контекст), но проверять только переданные.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: записать `last_changed = {'0': ['a.tsx']}`, файлы `a.tsx`,`b.tsx`; замокать `ReviewerAgent.run`, перехватить аргумент `files` → должен содержать только `a.tsx`.

**Dependencies:** Commit 26.

---

## Commit 30: FixPlan ограничивает Coder списком target_files

**Sprint:** G
**Fixes/Implements:** FixPlan target_files scope
**Files changed:**
- `src/studio/tasks.py`
- `src/studio/agents/coder.py`

**What to do:**
`FixerAgent` уже возвращает `target_files`, но `coder_iteration` подмешивает только `instructions`, игнорируя `target_files`. В режиме фикса Coder должен трогать ТОЛЬКО эти файлы, чтобы не ломать прошедшие шаги.

В `coder_iteration`, ветка фикса:
```python
        if project.pipeline.iteration_count > 0 and project.pipeline.fix_plan:
            fp = project.pipeline.fix_plan
            targets = fp.get('target_files') or []
            step_text += f"\n\nИСПРАВЬ согласно FixPlan:\n{fp.get('instructions', '')}"
            if targets:
                step_text += f"\n\nИЗМЕНЯЙ ТОЛЬКО эти файлы: {', '.join(targets)}. Остальные не трогай."
```
В `CoderAgent.run` добавить параметр `allowed_files` (optional); после получения `files` из LLM в режиме фикса отфильтровать результат:
```python
    def run(self, step_index, step_text, existing_files, allowed_files=None):
        ...
        files = data.get('files', {})
        if allowed_files:
            files = {p: c for p, c in files.items() if p in allowed_files}
        return files
```
И передавать `allowed_files=targets` из `coder_iteration` при фиксе.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: `CoderAgent.run(..., allowed_files=['a.tsx'])` с замоканным `run_json`, вернувшим `{'files': {'a.tsx': '...', 'b.tsx': '...'}}` → результат содержит только `a.tsx`.

**Dependencies:** Commit 26, Commit 22 (тот же `coder.py`).

---

## Commit 31: Стабилизировать назначение модели по сложности шага (метрики)

**Sprint:** G
**Fixes/Implements:** Planner step count fix (продолжение) + надёжность роутинга
**Files changed:**
- `src/studio/agents/planner.py`

**What to do:**
Усилить Commit 6 и Commit 22: planner должен помечать каждый шаг тегом сложности, чтобы роутинг на Opus был детерминированным, а не эвристическим по бэктикам. Добавить в `PLANNER_SYSTEM` требование помечать сложные шаги маркером `[COMPLEX]` в заголовке. Тогда `CoderAgent._pick_model` проверяет наличие `[COMPLEX]` в `step_text` в первую очередь:
```python
        if '[COMPLEX]' in step_text:
            return MODEL_SMART
```
Обновить `PLANNER_SYSTEM`:
```python
PLANNER_SYSTEM = (
    "... Помечай заголовок шага тегом [COMPLEX], если шаг включает auth, оплату, "
    "интеграции, realtime, миграции БД или затрагивает 5+ файлов. ..."
)
```

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: `_pick_model('## [COMPLEX] Auth', {})` → `MODEL_SMART`; `_pick_model('## Простой шаг', {})` → `MODEL_FAST`.

**Dependencies:** Commit 22 (`_pick_model`), Commit 6 (planner).

---

# Sprint H — Продукт и рост

## Commit 32: Деплой проекта на Vercel (backend)

**Sprint:** H
**Fixes/Implements:** Vercel deploy
**Files changed:**
- `src/studio/models.py` (миграция: `vercel_deployment_url`)
- `src/studio/tasks.py` (deploy_to_vercel)
- `src/studio/views/pipeline.py` (DeployView)
- `src/studio/urls.py`
- `src/config/settings.py` (`STUDIO_VERCEL_TOKEN`)

**What to do:**
Дать кнопку «Опубликовать». Через Vercel API создать deployment из файлов проекта.

1. Модель: `vercel_deployment_url = models.URLField(blank=True)`. `makemigrations`/`migrate`.
2. Настройка: `STUDIO_VERCEL_TOKEN = os.getenv('STUDIO_VERCEL_TOKEN', '')`.
3. Задача:
```python
@shared_task(bind=True, max_retries=2, queue=QUEUE)
def deploy_to_vercel(self, project_id):
    import requests
    project = StudioProject.objects.get(id=project_id)
    if not settings.STUDIO_VERCEL_TOKEN:
        publish_event(project_id, {'agent': 'system', 'level': 'error', 'text': 'Vercel не настроен'})
        return
    files = [{'file': f.path, 'data': f.content} for f in project.files.all()]
    try:
        r = requests.post('https://api.vercel.com/v13/deployments',
            headers={'Authorization': f'Bearer {settings.STUDIO_VERCEL_TOKEN}'},
            json={'name': f'aineron-{str(project.id)[:8]}', 'files': files,
                  'projectSettings': {'framework': 'nextjs'}}, timeout=60)
        data = r.json()
        url = 'https://' + data.get('url', '') if data.get('url') else ''
        project.vercel_deployment_url = url
        project.save(update_fields=['vercel_deployment_url'])
        publish_event(project_id, {'agent': 'system', 'level': 'success', 'text': f'Опубликовано: {url}'})
    except Exception as e:
        raise self.retry(exc=e, countdown=30)
```
4. View `DeployView.post` → `deploy_to_vercel.delay(...)`; URL `path('projects/<uuid:id>/deploy/', ...)`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: замокать `requests.post` → `{'url': 'app.vercel.app'}`; вызвать `deploy_to_vercel`; проверить `project.vercel_deployment_url == 'https://app.vercel.app'`.

**Dependencies:** Commit 23 (стабильный набор файлов).

---

## Commit 33: Frontend — кнопка публикации + ссылка на деплой

**Sprint:** H
**Fixes/Implements:** Vercel deploy (frontend)
**Files changed:**
- `frontend/lib/api/studio.ts`
- `frontend/components/studio/BillingEstimate.tsx` (блок «завершён»)

**What to do:**
`studio.ts`:
```ts
  deploy: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/deploy/`, { method: 'POST' }),
```
В блоке «Проект завершён» `BillingEstimate` добавить кнопку «Опубликовать на Vercel» (Lucide `Rocket`/`Globe`); если в проекте уже есть `vercel_deployment_url` — показать ссылку. Передать `deploymentUrl` пропом и вызывать `studioApi.deploy(id)`.

**Test:**
```bash
cd frontend && npm run build
```
Ручная: завершённый проект показывает кнопку публикации, после клика — ссылку.

**Dependencies:** Commit 32.

---

## Commit 34: Совместная работа — приглашение соавтора (read/collab)

**Sprint:** H
**Fixes/Implements:** Collaboration
**Files changed:**
- `src/studio/models.py` (новая модель `StudioCollaborator` + миграция)
- `src/studio/views/projects.py` (CollaboratorView)
- `src/studio/urls.py`
- права доступа в существующих views

**What to do:**
Сейчас доступ к проекту строго по `user=request.user`. Ввести соавторов.

1. Модель:
```python
class StudioCollaborator(models.Model):
    ROLE_CHOICES = [('viewer', 'Просмотр'), ('editor', 'Редактирование')]
    project = models.ForeignKey(StudioProject, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='studio_collabs')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer')
    class Meta:
        unique_together = [('project', 'user')]
```
`makemigrations`/`migrate`.
2. Helper доступа (заменить точечно `filter(user=request.user)` на «владелец ИЛИ соавтор»):
```python
from django.db.models import Q
def accessible_projects(user):
    return StudioProject.objects.filter(Q(user=user) | Q(collaborators__user=user)).distinct()
```
Применить в `StudioProjectListCreateView.get_queryset`, `StudioProjectDetailView`, `FileTreeView`, и т.д. Запись (PATCH файлов, run) разрешать только владельцу и `editor`.
3. `CollaboratorView`: POST приглашает по email (`add`/`remove`), доступно только владельцу. URL `path('projects/<uuid:id>/collaborators/', ...)`.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: добавить collaborator-viewer; от его имени GET проекта → 200; PATCH файла → 403. Владелец видит проект в списке, соавтор тоже.

**Dependencies:** Commit 1 (стабильные статусы); затрагивает много views — делать после Sprint E/F стабилизации доступа.

---

## Commit 35: Маркетплейс шаблонов — публикация проекта как шаблона

**Sprint:** H
**Fixes/Implements:** Template marketplace
**Files changed:**
- `src/studio/models.py` (поля у `StudioTemplate`: `author`, `is_public`, `usage_count` + миграция)
- `src/studio/views/projects.py` (PublishTemplateView)
- `src/studio/urls.py`
- `frontend/app/studio/page.tsx` (выбор шаблона при создании)

**What to do:**
`StudioTemplate` существует, но только сидируется. Дать пользователям публиковать свои проекты как шаблоны и создавать новые из шаблона.

1. Поля:
```python
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='studio_templates')
    is_public = models.BooleanField(default=False)
    usage_count = models.IntegerField(default=0)
```
`makemigrations`/`migrate`. `TemplateListView.queryset` → `filter(is_public=True)`.
2. `PublishTemplateView.post(id)`: создаёт `StudioTemplate` из проекта (slug из имени, `seed_prompt` = `description` + `project_md_content[:2000]`, `stack=target_stack`, `author=user`, `is_public=True`).
3. При создании проекта из шаблона: в `StudioProjectCreateSerializer`/view принять `template_slug`, скопировать `seed_prompt` в `description`, `stack`, инкрементить `template.usage_count`.
4. Frontend `studio/page.tsx`: при создании — список публичных шаблонов (`studioApi.templates()`), клик подставляет данные.

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: опубликовать проект как шаблон → `StudioTemplate.objects.filter(is_public=True, author=user)` не пуст; создать проект из шаблона → `description` подтянут, `usage_count == 1`.

**Dependencies:** Commit 1.

---

## Commit 36: Экспорт проекта (zip-архив)

**Sprint:** H
**Fixes/Implements:** Project export
**Files changed:**
- `src/studio/views/files.py` (ExportView)
- `src/studio/urls.py`
- `frontend/lib/api/studio.ts` + кнопка в UI

**What to do:**
Дать скачать весь проект zip-ом из `StudioFile`.

```python
# views/files.py
import io, zipfile
from django.http import HttpResponse

class ExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)  # или accessible_projects
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in project.files.all():
                zf.writestr(f.path.lstrip('/'), f.content)
        buf.seek(0)
        resp = HttpResponse(buf.read(), content_type='application/zip')
        resp['Content-Disposition'] = f'attachment; filename="{project.name}.zip"'
        return resp
```
URL `path('projects/<uuid:id>/export/', ExportView.as_view(), name='export')`.
Frontend: кнопка «Скачать ZIP» (Lucide `Download`) — открывает `${API}/studio/projects/${id}/export/` с credentials (через `window.location` или fetch→blob).

**Test:**
```bash
cd src && python manage.py test studio
```
Юнит-тест: создать проект с 2 файлами; GET export; распаковать ответ через `zipfile.ZipFile(io.BytesIO(resp.content))` → namelist содержит оба пути, содержимое совпадает.

**Dependencies:** —

---

# Приложение — Сводная таблица зависимостей

| Commit | Спринт | Зависит от |
|--------|--------|-----------|
| 1 | Fix | — |
| 2 | Fix | — |
| 3 | Fix | 2 |
| 4 | Fix | — |
| 5 | Fix | 1, 3 |
| 6 | Fix | — |
| 7 | Fix | — |
| 8 | E | 6 |
| 9 | E | 8 |
| 10 | E | 9 |
| 11 | E | — |
| 12 | E | — |
| 13 | E | — |
| 14 | E | — |
| 15 | E | 4 |
| 16 | E | 15 |
| 17 | F | 1, 3 |
| 18 | F | 17 |
| 19 | F | — |
| 20 | F | 5, 1 |
| 21 | F | 20 |
| 22 | F | 2, 3 |
| 23 | F | — |
| 24 | F | 4, 3 |
| 25 | F | 3, 8, 22 |
| 26 | G | 22 |
| 27 | G | 4, 15 |
| 28 | G | 27 |
| 29 | G | 26 |
| 30 | G | 26, 22 |
| 31 | G | 22, 6 |
| 32 | H | 23 |
| 33 | H | 32 |
| 34 | H | 1 |
| 35 | H | 1 |
| 36 | H | — |

---

## Порядок реализации (рекомендованный)

1. **Sprint Fix целиком** (1→7) — закрывает все критические баги. Обязательно перед остальным.
2. **Sprint E** (8→16) — стабильность и UX. Можно параллелить независимые ветки (11, 12, 13 не зависят ни от чего).
3. **Sprint F** (17→25) — функционал. 22 и 25 трогают billing — делать аккуратно, после Fix.
4. **Sprint G** (26→31) — качество. Все зависят от F-роутинга/контекста.
5. **Sprint H** (32→36) — продукт. Делать последним.

После каждого коммита: `cd src && python manage.py test studio` (backend) и `cd frontend && npm run build` (если затронут фронт). По правилу проекта — `git push origin main` после каждого коммита.

---

## Оптимальный план сессий

> Каждая сессия — **один новый чат**. Открываешь STUDIO_COMMITS.md и говоришь: *"Реализуй сессию X по плану из STUDIO_COMMITS.md"*.
> Деплой после каждой сессии — обязателен для проверки на живом сервере.

### Правила сессий

| Правило | Почему |
|---------|--------|
| Максимум 4-5 коммитов за сессию | Больше — контекст чата переполняется, ошибки растут |
| Только один слой за раз (бэкенд ИЛИ фронт) | Легче дебажить, меньше конфликтов |
| Коммиты с миграциями — отдельная сессия или первые в сессии | Миграция должна пройти до запуска других кодов |
| Деплой после каждой сессии | Ловить баги пока контекст свежий |
| Если сессия сломала что-то → откатить и исправить до следующей | Не копить технический долг |

---

### Сессия 1 — Критические баги бэкенда (коммиты 1, 2, 4)

**Что делать:** коммиты 1, 2, 4
**Слой:** только бэкенд (`src/studio/`)
**Миграций нет**
**Время:** ~45 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 1 | `views/projects.py` — статус `'interviewing'` → `'interview'` |
| 2 | Commit 2 | `tasks.py` — идемпотентность billing, charge-after-save |
| 3 | Commit 4 | `tasks.py` — try/except вокруг Docker в `run_pipeline` |

**Деплой:** `docker-compose build web celery_studio && docker-compose up -d --force-recreate web celery_studio`
**Проверка:** Создать новый проект → интервью должно запускаться, статус в БД = `'interview'`

---

### Сессия 2 — Биллинг и пауза (коммиты 3, 5)

**Что делать:** коммиты 3, 5
**Слой:** только бэкенд (`src/studio/`)
**Миграций нет**
**Зависит от:** Сессии 1 (нужен исправленный billing из Commit 2)
**Время:** ~30 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 3 | `tasks.py` — пауза при нулевом балансе вместо бесплатного прогона |
| 2 | Commit 5 | `models.py` + `views/pipeline.py` + `tasks.py` — пауза реально останавливает Celery через revoke |

**Миграции:** Commit 5 добавляет `current_task_id` в `StudioPipelineState` → `makemigrations studio` + `migrate`
**Деплой:** `docker-compose build web celery_studio && docker-compose up -d --force-recreate web celery_studio`
**Проверка:** Нажать "Пауза" во время кодинга → задачи должны прекратиться

---

### Сессия 3 — Мелкие критические фиксы (коммиты 6, 7)

**Что делать:** коммиты 6, 7
**Слой:** только бэкенд
**Миграций нет**
**Время:** ~20 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 6 | `agents/planner.py` — `planned_steps` из реального числа секций |
| 2 | Commit 7 | `config/settings.py` — `reap_stale_sandboxes` в `CELERY_BEAT_SCHEDULE` |

**Деплой:** `docker-compose up -d --force-recreate web celery_studio celery_beat`
**Проверка:** Проверить в Django Admin → Periodic Tasks → должна появиться задача

---

### Сессия 4 — Биллинг-эстимейт и UX ревью-страницы (коммиты 8, 9, 10)

**Что делать:** коммиты 8, 9, 10
**Слой:** бэкенд (новый endpoint) + фронт (review page + BillingEstimate)
**Миграций нет**
**Зависит от:** Сессии 3 (commit 6 исправляет planned_steps для estimate)
**Время:** ~60 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 8 | `views/pipeline.py` — новый `EstimateView GET /estimate/` → `{estimated_stars, breakdown}` |
| 2 | Commit 9 | `lib/api/studio.ts` + `BillingEstimate.tsx` — fetch реального estimate вместо 50 |
| 3 | Commit 10 | `app/studio/[id]/review/page.tsx` — показ реального estimate, убрать хардкод |

**Деплой:** `docker-compose build web frontend && docker-compose up -d --force-recreate web frontend`
**Проверка:** Открыть review-страницу → сумма звёзд должна зависеть от числа шагов

---

### Сессия 5 — SSE reconnect + подсветка кода (коммиты 11, 12)

**Что делать:** коммиты 11, 12
**Слой:** только фронт (`frontend/components/studio/`)
**Миграций нет**
**Время:** ~45 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 11 | `AgentLog.tsx` — reconnect с exponential backoff, singleton через Context |
| 2 | Commit 12 | `CodeViewer.tsx` + `StudioFile.language` — синтаксическая подсветка через highlight.js |

**Деплой:** `docker-compose build frontend && docker-compose up -d --force-recreate frontend`
**Проверка:** Отключить интернет на 5с и снова включить → лог должен восстановиться

---

### Сессия 6 — DiffViewer + ручные правки (коммиты 13, 14)

**Что делать:** коммиты 13, 14
**Слой:** фронт + бэкенд (FileDetailView)
**Миграций нет**
**Время:** ~60 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 13 | `StudioLayout.tsx` + `DiffViewer.tsx` — подключить DiffViewer, табы Code/Diff |
| 2 | Commit 14 | `views/files.py` — FileDetailView.patch() пишет в sandbox + Gitea |

**Деплой:** полный rebuild
**Проверка:** Отредактировать файл в CodeViewer → изменение должно появиться в preview iframe

---

### Сессия 7 — Sandbox subdomain preview (коммит 15, 16)

**Что делать:** коммиты 15, 16
**Слой:** инфраструктура (nginx.conf, docker-compose.yml) + фронт
**Сложность:** ВЫСОКАЯ — требует wildcard SSL или ручной настройки nginx
**Время:** ~90 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 15 | `nginx.conf` — wildcard `sandbox-*.aineron.ru` → sandbox container |
| 2 | Commit 16 | `PreviewPanel.tsx` — URL строить как `https://sandbox-{cid}.aineron.ru` |

**Деплой:** nginx + certbot wildcard SSL (`certbot certonly --manual -d "*.aineron.ru"`)
**Проверка:** Preview должен показывать рабочий Next.js сайт с правильными /_next/ ассетами

---

### Сессия 8 — ContextChat с LLM (коммиты 17, 18)

**Что делать:** коммиты 17, 18
**Слой:** новый агент (бэкенд) + фронт
**Зависит от:** Сессий 1-2 (статус + billing исправлены)
**Время:** ~75 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 17 | `agents/context_chat.py` (новый) + `views/chat.py` (новый) + `urls.py` — LLM-чат с контекстом |
| 2 | Commit 18 | `ContextChat.tsx` — полноценный чат-интерфейс, polling ответов агента |

**Деплой:** `docker-compose build web celery_studio frontend && docker-compose up -d --force-recreate web celery_studio frontend`
**Проверка:** На экране паузы — написать вопрос, получить ответ от Opus с контекстом проекта

---

### Сессия 9 — SPA-клонирование через Playwright (коммит 19)

**Что делать:** коммит 19
**Слой:** только бэкенд (tasks.py, crawler.py)
**Миграций нет**
**Время:** ~45 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 19 | `tasks.py` — роутинг SPA → `celery_studio_playwright`, `crawler.py` — Playwright crawl + palette |

**Деплой:** `docker-compose build celery_studio_playwright && docker-compose up -d --force-recreate celery_studio_playwright`
**Проверка:** Клонировать React SPA (например vercel.com) → должен получить контент, а не пустой HTML

---

### Сессия 10 — Semi/Manual режим + Opus для сложных шагов (коммиты 20, 21, 22)

**Что делать:** коммиты 20, 21, 22
**Слой:** бэкенд + фронт
**Миграций нет**
**Время:** ~75 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 20 | `tasks.py` — `paused_approval` после каждого шага в semi-режиме |
| 2 | Commit 21 | `StudioLayout.tsx` — кнопка "Одобрить" в semi-режиме |
| 3 | Commit 22 | `agents/coder.py` — detect `[complex]` тег → MODEL_SMART (Opus) |

**Деплой:** полный rebuild
**Проверка:** Создать проект в Semi режиме → после каждого шага должна появляться кнопка "Одобрить"

---

### Сессия 11 — Атомарные Gitea-коммиты + лимиты sandbox (коммиты 23, 24, 25)

**Что делать:** коммиты 23, 24, 25
**Слой:** бэкенд
**Миграций нет**
**Время:** ~60 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 23 | `gitea_client.py` — batch Tree API, один коммит на шаг |
| 2 | Commit 24 | `sandbox.py` + `billing.py` — `can_spawn()`, лимит 2 sandbox на пользователя |
| 3 | Commit 25 | `billing.py` + `tasks.py` + `models.py` — резервация звёзд при старте |

**Деплой:** `docker-compose build web celery_studio && docker-compose up -d --force-recreate web celery_studio`
**Проверка:** Запустить два проекта → третий должен получить 429, история Gitea — чистая (один коммит/шаг)

---

### Сессия 12 — Качество генерации: multi-file context + тесты (коммиты 26, 27, 28)

**Что делать:** коммиты 26, 27, 28
**Слой:** бэкенд (агенты)
**Время:** ~60 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 26 | `agents/coder.py` — убрать [:10]/[:2000], smart context по импортам |
| 2 | Commit 27 | `sandbox.py` — `wait_for_ready()` polling `/tmp/dev.log` |
| 3 | Commit 28 | `tasks.py` — реальный `pnpm test --run` перед TesterAgent |

**Деплой:** `docker-compose build celery_studio && docker-compose up -d --force-recreate celery_studio`
**Проверка:** Создать проект с 5+ файлами → кодер должен видеть все, не только первые 10

---

### Сессия 13 — Качество: diff-ревью + исправления (коммиты 29, 30, 31)

**Что делать:** коммиты 29, 30, 31
**Слой:** бэкенд (агенты)
**Время:** ~45 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 29 | `agents/reviewer.py` — ревьювать только `changed_files` текущего шага |
| 2 | Commit 30 | `agents/fixer.py` — `target_files` передаётся Кодеру для скоупинга |
| 3 | Commit 31 | `agents/planner.py` — валидация числа шагов, предупреждение > 15 |

**Деплой:** `docker-compose build celery_studio && docker-compose up -d --force-recreate celery_studio`

---

### Сессия 14 — Продукт: деплой на Vercel + экспорт (коммиты 32, 33, 35)

**Что делать:** коммиты 32, 33, 35
**Слой:** бэкенд (новые views) + фронт
**Время:** ~90 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 32 | `views/deploy.py` (новый) — интеграция с Vercel API |
| 2 | Commit 33 | `BillingEstimate.tsx` — кнопка "Опубликовать на Vercel" |
| 3 | Commit 35 | `views/export.py` (новый) — ZIP всех файлов + экспорт в GitHub |

**Деплой:** полный rebuild
**Проверка:** Завершить проект → нажать "Опубликовать" → должен появиться URL на vercel.app

---

### Сессия 15 — Продукт: marketplace шаблонов + аналитика (коммиты 34, 36)

**Что делать:** коммиты 34, 36
**Слой:** бэкенд + фронт
**Миграции:** Commit 34 добавляет поля в StudioTemplate
**Время:** ~60 мин

| # | Коммит | Что меняется |
|---|--------|-------------|
| 1 | Commit 34 | `models.py` + `views/templates.py` — публикация проекта как шаблона, рейтинг |
| 2 | Commit 36 | `app/account/studio/page.tsx` (новый) — аналитика Studio в кабинете |

**Деплой:** полный rebuild
**Проверка:** Завершить проект → опубликовать как шаблон → шаблон виден в галерее

---

## Сводная таблица сессий

| Сессия | Коммиты | Слой | Deploy? | Время | Приоритет |
|--------|---------|------|---------|-------|-----------|
| 1 | 1, 2, 4 | Backend | Да | 45 мин | КРИТИЧНО |
| 2 | 3, 5 | Backend + Migration | Да | 30 мин | КРИТИЧНО |
| 3 | 6, 7 | Backend | Да | 20 мин | КРИТИЧНО |
| 4 | 8, 9, 10 | Backend + Frontend | Да | 60 мин | Важно |
| 5 | 11, 12 | Frontend | Да | 45 мин | Важно |
| 6 | 13, 14 | Frontend + Backend | Да | 60 мин | Важно |
| 7 | 15, 16 | Infra + Frontend | Да | 90 мин | Важно |
| 8 | 17, 18 | Backend + Frontend | Да | 75 мин | Важно |
| 9 | 19 | Backend | Да | 45 мин | Средний |
| 10 | 20, 21, 22 | Backend + Frontend | Да | 75 мин | Средний |
| 11 | 23, 24, 25 | Backend | Да | 60 мин | Средний |
| 12 | 26, 27, 28 | Backend | Да | 60 мин | Средний |
| 13 | 29, 30, 31 | Backend | Да | 45 мин | Средний |
| 14 | 32, 33, 35 | Backend + Frontend | Да | 90 мин | Низкий |
| 15 | 34, 36 | Backend + Frontend + Migration | Да | 60 мин | Низкий |

**Итого:** 15 сессий, ~14 часов работы, 36 коммитов

---

## Стартовая фраза для нового чата

Скопируй в начало каждого нового чата:

```
Открой файл STUDIO_COMMITS.md в корне проекта.
Реализуй сессию N (коммиты X, Y, Z) по инструкции из документа.
После каждого коммита — git push origin main.
Деплоить не нужно / задеплой на сервере после завершения сессии.
```
