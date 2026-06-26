# Studio V5 — План надёжного генератора

> Цель V5 — не переписать архитектуру, а **включить и закалить** то, что уже написано.
> Пайплайн (Architect → Coder → Guardian → commit → next_step) хороший. Проблема в том,
> что половина наработок лежит за выключенными фича-флагами (STUDIO_V3, STUDIO_V4_*),
> а build-гейт сделан «мягким» — билд падает, но шаг всё равно проходит дальше.
> V5 = «железобетонная генерация»: ничего сломанного не уезжает в коммит.

---

## Статус после текущей сессии

Уже сделано в этой сессии (закоммичено / готово к коммиту):

1. **Баг `log` NameError в `coder_iteration`** — `src/studio/tasks.py:575`.
   При отмене пайплайна вместо аккуратного `return` бросался `NameError`, из-за чего
   Celery уходил в retry-цикл. Исправлено: graceful return.
2. **Guardian auto-pass при ошибке парсинга** — `src/studio/agents/guardian.py:134`.
   Если regex вердикта не матчился → дефолт был `'pass'` → битый код уезжал в коммит.
   Изменено на `'fix'` (fail-closed).
3. **Guardian force-pass при исключении + исчерпании retry** — `src/studio/tasks.py:672-673`.
   Раньше при ошибке API после всех retry шаг молча проходил. Теперь — пауза пайплайна
   (`status='paused_on_loop'`, `pause_reason`) с понятным сообщением пользователю.
4. **SSE / streaming UI** — канал событий (`publish_event`, `type: 'file_delta'`) приведён
   в порядок, фронт корректно дорисовывает дельты файлов.
5. **Адаптивный layout** студии — раскладка панелей под разные ширины экрана.

Итог: пайплайн перестал «тихо» отправлять брак в коммит на трёх известных путях.
Дальше — включаем готовый, но выключенный функционал и закрываем мягкий build-гейт.

---

## Фаза 1: Быстрые победы (1-2 часа, минимальный риск)

Весь код уже написан и протестирован в 6+ коммитах, просто выключен флагами. Включаем
по одному, проверяя пайплайн на тестовом проекте после каждого флага.

### 1.1 Включить `STUDIO_V3=1` в `.env`
- Флаг: `src/config/settings.py:431` (`STUDIO_V3`).
- Что включает: Architect эмитит `DESIGN.md` + структурированный план `COMMITS`;
  Coder переходит на структурированный вывод `FILE_BLOCKS` (`=== FILE: ... ===`)
  вместо сырого JSON; включаются structure-gate и dependency-gate перед Guardian;
  Guardian получает контекст `DESIGN.md` и умеет выдавать `EDIT`-блоки (точечные патчи
  без полной регенерации файла).
- Риск: средний из «быстрых» — меняется формат вывода Coder. Проверить на 1 тестовом
  проекте каждого стека перед прод-включением.

### 1.2 Включить `STUDIO_V4_GUARDIAN_CONTEXT=1`
- Флаг: `src/config/settings.py:439`.
- Что включает: дополнительная инъекция контекста (DESIGN.md + смежные файлы) в Guardian
  при ревью. Меньше ложных «всё ок» из-за того, что Guardian не видел зависимостей.
- Риск: низкий — расширяет промпт ревью, поведение не ломает.

### 1.3 Включить `STUDIO_V4_STREAMING=1`
- Флаг: `src/config/settings.py:438`.
- Что включает: стриминг вывода LLM в UI. Код уже есть в `src/studio/agents/coder.py:264-289`
  (`on_delta` → `publish_event` с `type: 'file_delta'`). Пользователь видит, как код
  печатается в реальном времени (как у Bolt/Cursor), а не пустой экран до конца шага.
- Риск: низкий — чисто UX-слой, на результат генерации не влияет.

### 1.4 Включить `STUDIO_V4_AUTOFIX=1`
- Флаг: `src/config/settings.py:437`, лимит `STUDIO_MAX_AUTOFIX` (`settings.py:442`, дефолт 3).
- Что включает: авто-фикс консольных ошибок из preview-iframe. Логика сброса счётчика
  уже в `src/studio/tasks.py:709-712` (при `verdict='pass'` обнуляет `autofix_count`
  и `seen_error_hashes`).
- Риск: низкий-средний — есть лимит итераций, зацикливания не будет.

### 1.5 Добавить `python`, `django`, `telegram_bot` в `STACK_CHOICES`
- Файл: `src/studio/models.py:19-22`.
- Сейчас: `nextjs`, `react`, `vue`, `html`, `tma`. Python/Django **уже принимаются**
  E2B preview-эндпоинтами, но недоступны как официальный выбор стека.
- Изменить на:
  ```python
  STACK_CHOICES = [
      ('nextjs', 'Next.js'), ('react', 'React'), ('vue', 'Vue'), ('html', 'HTML'),
      ('tma', 'Telegram Mini App'),
      ('python', 'Python (FastAPI/Flask)'),
      ('django', 'Django'),
      ('telegram_bot', 'Telegram Bot'),
  ]
  ```
- Также проверить `max_length=10` у `target_stack` (`models.py:38`) — `telegram_bot`
  = 12 символов, увеличить до `max_length=20`.

### 1.6 Создать миграцию
- `python src/manage.py makemigrations studio` → миграция меняет `choices` и `max_length`
  поля `target_stack`. Применить `python src/manage.py migrate`.
- На прод-деплое: миграция должна попасть в `deploy.sh` (она не нулевая — `max_length`
  меняется, это реальное изменение схемы для некоторых БД).

**Критерий приёмки Фазы 1:** на каждом из 5 текущих стеков тестовый проект проходит
полный цикл Architect→Coder→Guardian→commit без NameError/auto-pass; стриминг виден в UI;
python/django доступны в выпадающем списке выбора стека.

---

## Фаза 2: Жёсткий Build Gate (4-6 часов)

**Проблема (главная дыра в надёжности):** сейчас если `npm run build`/`tsc` падает,
мы только логируем warning и **всё равно идём на следующий шаг**. У Bolt сломанный билд
не уезжает в проект — у нас уезжает.

Сейчас в `src/studio/tasks.py:655-700` build выполняется так:
```python
build_logs = ''
if project.sandbox_container_id:
    try:
        _, build_logs = sandbox.run_build_check(project.sandbox_container_id)
    except Exception as exc:
        build_logs = f'build check unavailable: {exc}'
```
А вердикт билда нигде не блокирует переход — он лишь записывается в метрику
(`build_pass=1 if (build_logs and 'error' not in build_logs.lower()) else 0`, строка 699)
и в контекст Guardian. Итоговый `verdict` определяет только LLM-Guardian.

### Что сделать

**2.1 Сделать build-гейт детерминированным (не зависящим от мнения LLM).**
В `guardian_review` (`tasks.py:644`) после получения `build_logs` и `exit_code`
завести явный признак провала билда:
```python
exit_code, build_logs = sandbox.run_build_check(
    project.sandbox_container_id, is_nextjs=(project.target_stack == 'nextjs')
)
build_failed = (exit_code != 0) or _has_build_error(build_logs)
```
Сейчас `run_build_check` (`src/studio/sandbox.py:176`) возвращает `(exit_code, output)`,
но код в `tasks.py:658` распаковывает только `_, build_logs` — **exit_code выбрасывается**.
Начать его использовать.

**2.2 Завести хелпер `_has_build_error(logs)`** (в `tasks.py`, рядом с пайплайном):
матчить `error`, `Error:`, `Cannot find module`, `Type error`, `failed to compile`,
`Module not found` без учёта регистра. Не считать ошибкой строки вида
`0 errors`, `no errors`.

**2.3 Если `build_failed` — НЕ коммитить, форсить итерацию исправления.**
В блоке `if verdict == 'pass':` (`tasks.py:708`) добавить проверку ПЕРЕД `commit_to_gitea`:
```python
if verdict == 'pass' and not build_failed:
    ...commit_to_gitea.delay(...)
    return
# иначе — переопределяем вердикт на 'fix' и идём в итерацию
if build_failed and verdict == 'pass':
    verdict = 'fix'
    result.setdefault('issues', []).insert(0, 'BUILD FAILED — билд не собирается')
    result['instructions'] = (result.get('instructions', '') +
        '\n\nКРИТИЧНО: проект не собирается. Логи билда:\n' + build_logs[-3000:])
```
Так build становится **hard gate**: даже если LLM-Guardian сказал «pass», но билд красный —
шаг уходит в исправление.

**2.4 Если исчерпаны итерации (`iteration_count >= max_iter`), а билд всё ещё красный —
ставить пайплайн на паузу, а не коммитить.**
В ветке исчерпания итераций (`tasks.py:715` и далее) при `build_failed` выставить
`state.status = 'paused_on_loop'`, `pause_reason = 'Build не собирается после N итераций'`,
`project.status='paused'` — по аналогии с фиксом Guardian-исключения из этой сессии.
Никогда не коммитить красный билд молча.

**2.5 Учитывать неподнявшийся sandbox.**
Сейчас при недоступном sandbox (`tasks.py:490`, `516` — «продолжаем без build check»)
билд не проверяется вообще. Для V5 ввести флаг `STUDIO_V5_BUILD_GATE_STRICT`
(новый, в `settings.py` рядом с V4-флагами, дефолт `0`): если `1` и sandbox недоступен —
не «продолжаем без проверки», а пауза с просьбой повторить. Включить строгий режим
только после стабилизации поднятия sandbox.

**Критерий приёмки Фазы 2:** искусственно ломаем импорт в сгенерированном файле →
шаг НЕ коммитится, уходит в итерацию; после N неудачных итераций — пайплайн на паузе
с понятным `pause_reason`, а не «зелёный» проект с битым билдом.

---

## Фаза 3: Per-Stack промпты (6-8 часов)

**Проблема:** Coder использует один и тот же системный промпт для всех стеков
(`src/studio/agents/coder.py:246-247` — `pick_prompt(CODER_FILE_BLOCKS_RU, CODER_FILE_BLOCKS_EN)`,
плюс отдельная ветка только для TMA). У Bolt в промпт зашиты глубокие знания каждого
стека (Next.js app router, Vite-React, и т.д.). Из-за общего промпта Coder путает
конвенции (например, пишет pages-router в Next.js-проекте с app-router).

### Что сделать

**3.1 Завести словарь стек-специфичных промптов** в `src/studio/prompts.py`
(там же, где `CODER_FILE_BLOCKS_RU/EN`, `FILE_SYSTEM_TMA`). Для каждого стека —
короткий блок «правил стека», который **дописывается к общему system-промпту**, а не
заменяет его целиком:

- **nextjs**: TypeScript, **app router** (`app/`, `layout.tsx`, `page.tsx`),
  server components по умолчанию, `'use client'` только где нужны хуки/события,
  Tailwind, `next/image`, `next/link`. Не использовать `pages/`.
- **react**: Vite + TypeScript, функциональные компоненты + хуки, `src/main.tsx`,
  `index.html` в корне, импорты с `.tsx`. Без CRA-конвенций.
- **vue**: Vue 3 **Composition API** (`<script setup>`), Vite, TypeScript,
  `ref`/`reactive`/`computed`, SFC `.vue`.
- **html**: vanilla JS или **Alpine.js** для интерактива, без сборщика,
  один `index.html` + `style.css` + `app.js`, CDN-подключения.
- **tma**: Telegram WebApp API (`window.Telegram.WebApp`), `@twa-dev/sdk`,
  `ready()`/`expand()`/`MainButton`, тема из `themeParams`. (Уже есть `FILE_SYSTEM_TMA`
  — привести к единому механизму.)
- **python**: **FastAPI** (предпочтительно) или Flask, `main.py`, pydantic-модели,
  `requirements.txt`, `uvicorn`. Эндпоинты с типами.
- **django**: Django views/urls/templates, при API — DRF (`serializers.py`, `viewsets`),
  `settings.py`/`urls.py` правильно, `models.py` + миграции.
- **telegram_bot**: aiogram 3.x (для Python) или grammY (для TS), хендлеры,
  FSM где нужно, `Dispatcher`/`Bot`, токен из env.

**3.2 Подключить выбор промпта по `target_stack`** в `_generate_one_file`
(`src/studio/agents/coder.py:215-263`). Сейчас:
```python
system = FILE_SYSTEM_TMA if is_tma else pick_prompt(CODER_FILE_BLOCKS_RU, CODER_FILE_BLOCKS_EN)
```
Заменить на сборку: базовый промпт + `STACK_RULES.get(self.project.target_stack, '')`:
```python
base = pick_prompt(CODER_FILE_BLOCKS_RU, CODER_FILE_BLOCKS_EN)
stack_rules = STACK_RULES.get(self.project.target_stack, '')
system = f"{base}\n\n## Правила стека {self.project.target_stack}:\n{stack_rules}"
```
Ветку TMA свернуть в общий механизм (TMA-правила переезжают в `STACK_RULES['tma']`),
оставив совместимость с `FILE_SYSTEM_TMA` за флагом `STUDIO_V4_TMA` до миграции.

**3.3 То же для манифеста файлов** (`_generate_files_manifest`, около `coder.py:200`) —
чтобы список файлов сразу соответствовал конвенциям стека (например, для nextjs
предлагал `app/page.tsx`, а не `pages/index.tsx`).

**3.4 Architect тоже должен знать стек** — в `src/studio/agents/architect.py`
при генерации `DESIGN.md` / `COMMITS` подмешивать те же `STACK_RULES`, чтобы план
структуры файлов был стек-корректным с самого начала.

**Критерий приёмки Фазы 3:** nextjs-проект использует app-router; react — Vite;
vue — Composition API; python — FastAPI с pydantic; никаких «react-конвенций в vue».

---

## Фаза 4: Контекстный документ по всему пайплайну (4-6 часов)

**Проблема:** `DESIGN.md` сейчас (под `STUDIO_V3`) читают только Architect (создаёт)
и Coder/Guardian (через `_design_excerpt()`, `coder.py:250`). Но он **не обновляется
по ходу пайплайна** — каждый агент видит исходный дизайн, а не актуальное состояние
проекта после уже сделанных шагов. Из-за этого на шаге N агент не знает, что реально
появилось на шагах 1..N-1, и дублирует/конфликтует.

### Что сделать

**4.1 Превратить `DESIGN.md` в живой документ состояния.** После каждого успешного
коммита (`commit_to_gitea` в `tasks.py`, перед `next_step.delay(...)`) дописывать в
`DESIGN.md` (или в отдельное поле `project.design_state`) краткую сводку шага:
какие файлы созданы/изменены, какие компоненты/эндпоинты/маршруты добавлены, какие
ключевые решения приняты. Генерировать сводку дешёвой моделью (1-2 предложения на шаг).

**4.2 Хранение.** Завести поле `StudioProject.design_state` (`TextField`, `models.py`)
или переиспользовать `project_md_content`/`interview_data['design_state']`, если не
хотим новую миграцию. Обновлять атомарно после коммита шага.

**4.3 Раздать актуальный контекст ВСЕМ агентам, не только architect/guardian.**
- Coder: в `_generate_one_file` (`coder.py:250-251`) `_design_excerpt()` должен брать
  **обновлённый** `design_state`, а не первоначальный `DESIGN.md`.
- Guardian: в `guardian_review` (`tasks.py:666`) передавать актуальный design_state
  (уже частично делается под `STUDIO_V4_GUARDIAN_CONTEXT` — расширить на живой документ).
- Manifest-фаза Coder: тоже видит, что уже существует, чтобы не пересоздавать.

**4.4 Ограничить размер.** Держать «сводку проекта» в пределах ~2-3 КБ (последние N шагов
+ список текущих файлов с ролями), чтобы не раздувать каждый промпт. Старые шаги
сворачивать в одну строку.

**Критерий приёмки Фазы 4:** на шаге 5 Coder в контексте видит, что реально было создано
на шагах 1-4 (актуальные имена компонентов/маршрутов), и не дублирует существующее.

---

## Фаза 5: TypeScript/ESLint валидация (8-12 часов)

**Проблема:** мы запускаем только build. Bolt после генерации гоняет `tsc --noEmit`
+ `eslint` и не отдаёт код с type-ошибками. Сейчас `run_build_check`
(`src/studio/sandbox.py:176-183`) для не-nextjs уже делает `tsc --noEmit || pnpm build`,
но: (а) это «или», а не «и»; (б) для nextjs (`is_nextjs=True`) делается только `pnpm build`
без отдельного tsc; (в) eslint не запускается вообще; (г) результат не блокирует
(см. Фазу 2).

### Что сделать

**5.1 Добавить раздельные проверки в `sandbox.py`.** Завести функцию
`run_quality_gate(container_id, stack)` рядом с `run_build_check` (`sandbox.py:176`),
которая возвращает структуру `{'tsc': (code, out), 'eslint': (code, out), 'build': (code, out)}`:
- для TS-стеков (nextjs/react/vue/tma): `pnpm -s exec tsc --noEmit`, затем
  `pnpm -s exec eslint . --max-warnings=0` (если eslint сконфигурён), затем build;
- для python/django: `python -m py_compile`/`ruff check` вместо tsc/eslint;
- использовать существующий `exec_command(container_id, cmd, workdir='/workspace')`
  (`sandbox.py:70`).

**5.2 Опционально устанавливать eslint/ruff** в scaffold-фазе, если их нет, чтобы
гейт был применим. Иначе — gracefully пропускать недоступную проверку (но логировать).

**5.3 Включить в `guardian_review` flow** (`tasks.py:644`). Заменить одиночный
`run_build_check` на `run_quality_gate`. Любая красная проверка (tsc ИЛИ eslint ИЛИ build)
→ `build_failed = True` → попадает в hard-gate из Фазы 2 (форс-итерация, потом пауза).
Логи tsc/eslint подмешивать в `instructions` для Coder, чтобы он чинил конкретные ошибки
по файлам/строкам.

**5.4 Флаг `STUDIO_V5_QUALITY_GATE`** (`settings.py`, дефолт `0`): tsc — обязательный,
eslint — сначала как warning-only (`--max-warnings` не 0), потом, когда генерация
стабильно чистая, ужесточить до `--max-warnings=0`. Поэтапно, чтобы не заблокировать
пайплайн потоком линт-замечаний.

**Критерий приёмки Фазы 5:** файл с type-ошибкой (`const x: number = 'foo'`) не уезжает
в коммит — гейт красный, шаг уходит на исправление с конкретным сообщением tsc.

---

## Северная звезда (через 2-3 спринта)

Через V5 Studio aineron.ru должна давать то, чего нет у локальных конкурентов и что на
уровне Bolt/v0:

1. **Железобетонная генерация.** Никакой сломанный код не уезжает в коммит. Hard-гейты:
   build + tsc + eslint. Если не собирается — не отдаём, чиним или честно ставим на паузу
   с понятной причиной. Ноль «тихих» auto-pass (закрыто в этой сессии + Фаза 2).

2. **Глубокое знание стеков.** Per-stack промпты (Фаза 3) уровня Bolt: nextjs app-router,
   Vite-react, Vue Composition API, FastAPI/Django, aiogram/grammY — каждый стек по своим
   правильным конвенциям, а не «усреднённый React».

3. **Реалтайм-прозрачность.** Стриминг кода в UI (Фаза 1.3), видно как печатается файл,
   видно вердикт Guardian, видно логи билда/tsc — как у Cursor/Bolt, не «чёрный ящик».

4. **Память проекта.** Живой `DESIGN.md`/design_state (Фаза 4): каждый шаг знает, что уже
   построено. Большие проекты на много шагов остаются связными, без дублей и конфликтов.

5. **Российский фокус, которого нет у Bolt:** официальная поддержка Telegram Mini App
   и Telegram Bot стеков (aiogram/grammY) с деплоем в Timeweb/Selectel, русские
   стек-доки (`STUDIO_V4_RU_STACK`), биллинг в звёздах. Это наш ров — Bolt/v0 не делают
   TMA/боты и не деплоят в РФ-облака.

**Принцип V5:** мы не переписываем архитектуру — она правильная. Мы **включаем готовое**
(Фаза 1), **закрываем мягкие гейты** (Фазы 2, 5), **углубляем знания** (Фаза 3) и
**даём памяти течь по пайплайну** (Фаза 4). Каждая фаза — отдельный включаемый флаг,
любую можно откатить одной переменной окружения.
