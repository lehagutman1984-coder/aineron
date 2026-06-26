# Studio V5 — Надёжный генератор (100% CODE-COMPLETE)

> **Статус: ВСЕ 5 ФАЗ CODE-COMPLETE** (2026-06-26). Последний коммит: `51d851d`.
> Дополняет [STUDIO_MASTER_PLAN.md](STUDIO_MASTER_PLAN.md) — тот описывает **Live Preview Runtime** (E2B/Sandpack/db-proxy/billing), этот — **надёжность AI-генерации** (Architect → Coder → Guardian → commit).
>
> Два плана решают разные слои Studio: V5 = качество кода на выходе, MASTER = среда запуска.

---

## Цель V5

Не переписать архитектуру (она правильная), а **включить и закалить** то, что уже написано.
V5 = «железобетонная генерация»: ничего сломанного не уезжает в коммит.

---

## Фаза 1: Быстрые победы — ✅ DONE

### 1.1 `STUDIO_V3=1` — включено в `.env`
Architect эмитит `DESIGN.md` + структурированный план `COMMITS`; Coder → `FILE_BLOCKS` (`=== FILE: ... ===`); Guardian получает DESIGN.md-контекст и умеет выдавать EDIT-блоки (точечные патчи без полной регенерации).

### 1.2 `STUDIO_V4_GUARDIAN_CONTEXT=1` — включено
Символьная карта всего проекта в контексте Guardian: до 40 файлов × до 15 экспортов. Меньше ложных «всё ок» из-за невидимых зависимостей.

### 1.3 `STUDIO_V4_STREAMING=1` — включено
Стриминг вывода LLM в UI: `on_delta` → `publish_event(type='file_delta')`. Пользователь видит, как код печатается в реальном времени.

### 1.4 `STUDIO_V4_AUTOFIX=1`, `STUDIO_MAX_AUTOFIX=3` — включено
Авто-фикс консольных ошибок из preview-iframe. Лимит итераций исключает зацикливание.

### 1.5 Python/Django/TelegramBot стеки — добавлены в `STACK_CHOICES`
`src/studio/models.py` — все 8 стеков официально: `nextjs`, `react`, `vue`, `html`, `tma`, `python`, `django`, `telegram_bot`.

### 1.6 Migration 0020 — создана и применена
`target_stack` и `stack` поля: `max_length=10` → `max_length=20` (`telegram_bot` = 12 символов, не влезало).

---

## Фаза 2: Жёсткий Build Gate — ✅ DONE

**`src/studio/tasks.py`:**
- `_has_build_error(logs)` — хелпер: матчит `error`, `Type error`, `Cannot find module`, `failed to compile`, `Module not found`; исключает строки вида `0 errors`.
- `_GATE_INAPPLICABLE_RE` — regex-guard: `No inputs were found|Cannot find a tsconfig|No ESLint configuration|error TS18003`. Config-absence ≠ build failure — не блокируем.
- `_JS_BUILD_STACKS = frozenset({'nextjs', 'react', 'vue', 'tma'})` — `html` исключён: нет tsconfig → tsc всегда exits 1 с TS18003 → false-fail loop.
- `build_failed` canonical bool = `_raw_build_failed and not _GATE_INAPPLICABLE_RE.search(build_logs)`.
- **Hard gate**: `verdict='pass' and build_failed` → verdict → `'fix'`, build logs добавляются в instructions.
- **Пауза при исчерпании**: `iteration_count >= max_iter and build_failed` → `paused_on_loop` вместо молчаливого коммита сломанного кода.
- `build_pass` метрика: `0 if build_failed else 1` (раньше был stale string match на 'error' в логах).

**`src/studio/sandbox.py`:**
- `run_build_check()`: exit_code захватывается через `_c=$?; exit $_c` — tail больше не маскирует реальный код возврата.
- `is_nextjs=True` → `pnpm build`; иначе → `pnpm exec tsc --noEmit`.

**Архитектурное уточнение:** `STUDIO_DEPRECATE_DOCKER_FRONTEND` (settings.py, default=1) влияет **только** на health check view `views/pipeline.py:328` (возвращает `alive=False, sandpack=True` для frontend-стеков). На генерационный пайплайн `tasks.py` **не влияет** — Docker sandbox спавнится для всех стеков при каждой генерации.

---

## Фаза 3: Per-Stack промпты — ✅ DONE

**`src/studio/agents/coder.py`:**
- `_STACK_RULES: dict[str, str]` — правила (Opus 4.8 content) для всех 8 стеков:
  - **nextjs**: TypeScript, app router (`app/`, `layout.tsx`, `page.tsx`), server components по умолчанию, `'use client'` только там где нужны хуки/события, не использовать `pages/`
  - **react**: Vite + TypeScript, `src/main.tsx`, `index.html` в корне, без CRA
  - **vue**: Vue 3 Composition API (`<script setup>`), Vite, `ref`/`reactive`/`computed`
  - **html**: vanilla JS / Alpine.js, без сборщика, CDN-подключения
  - **tma**: `@twa-dev/sdk`, `ready()`/`expand()`/`MainButton`, `themeParams`
  - **python**: FastAPI (предпочтительно), pydantic, uvicorn, `requirements.txt`
  - **django**: DRF, `serializers.py`, viewsets, правильный `settings.py`/`urls.py`
  - **telegram_bot**: aiogram 3.x, FSM, `Dispatcher`/`Bot`, токен из env
- `_generate_one_file()`: `base_system + "\n\n## Правила стека:\n" + _STACK_RULES.get(stack, '')` (TMA использует `FILE_SYSTEM_TMA` под `STUDIO_V4_TMA`).

**`src/studio/agents/architect.py`:**
- `_ARCHITECT_STACK_NOTES: dict` — предотвращает генерацию pnpm/vite/tsconfig шагов для Python-проектов.

---

## Фаза 4: Живой DESIGN.md — ✅ DONE

**`src/studio/tasks.py`:**
- `commit_to_gitea`: сохраняет `project.interview_data['design_state']` = `{completed_steps, last_step_files, build_status}` после каждого успешного коммита. Хранится в JSONField — нет доп. миграций.

**`src/studio/agents/coder.py`:**
- `_design_excerpt()`: читает актуальный `design_state` из `interview_data`, добавляет прогресс-блок к DESIGN.md перед каждым шагом.

**`src/studio/agents/guardian.py`:**
- `design_section` включает `design_state` (`completed_steps` + `last_step_files`) — Guardian видит актуальное состояние, а не только исходный DESIGN.md.

---

## Фаза 5: Quality Gate — ✅ DONE

**`src/studio/sandbox.py`:**
- `run_quality_gate(container_id, stack)`:
  - `nextjs` → `pnpm exec next lint --max-warnings 0` (ESLint встроен в Next.js)
  - `python`/`django`/`telegram_bot` → `find /workspace -name "*.py" | xargs python3 -m py_compile`
  - остальные JS-стеки → `(0, '')` (tsc уже покрыт `run_build_check`)
- Использует `python3` — подтверждено: `Dockerfile.sandbox:3` явно устанавливает `python3 python3-pip`.
- `pnpm`, `node`, `tsc` (через devDependencies) доступны (`node:22-slim` + corepack).

**`src/studio/tasks.py`:**
- Quality gate запускается ПОСЛЕ build check (если build green).
- `_GATE_INAPPLICABLE_RE` защищает и здесь — "No ESLint configuration" / "configure ESLint" не считается ошибкой.
- Ошибки quality gate → `build_failed = True`, linter logs дописываются к `build_logs` → Coder получает конкретные сообщения с файлами/строками.

---

## Исправленные баги V5

| # | Баг | Файл | Фикс |
|---|---|---|---|
| 1 | `log` NameError в `coder_iteration` при отмене | tasks.py | graceful return |
| 2 | Guardian auto-pass при ошибке парсинга (дефолт `'pass'`) | guardian.py:134 | `'fix'` (fail-closed) |
| 3 | Guardian force-pass при API exception после retry | tasks.py | → pause + SSE error |
| 4 | SSE blocking Gunicorn | tasks.py + views | async view + redis.asyncio |
| 5 | Mobile layout PanelGroup style bug | UI | fixed |
| 6 | `html` в `_JS_BUILD_STACKS` → tsc TS18003 false-fail loop | tasks.py | html исключён из frozenset |
| 7 | Config-absence = build failure (нет `_GATE_INAPPLICABLE_RE`) | tasks.py | regex-guard добавлен |
| 8 | `python` вместо `python3` в quality gate | sandbox.py | `python3 -m py_compile` |
| 9 | `build_pass` метрика stale string match | tasks.py | canonical `build_failed` bool |

---

## Северная звезда (достигнута)

1. **Железобетонная генерация** ✅ — hard-гейты: build + tsc + next lint + py_compile. Никакой сломанный код не уезжает в коммит.
2. **Глубокое знание стеков** ✅ — per-stack промпты: nextjs app-router, Vite-react, Vue Composition API, FastAPI/Django, aiogram/grammY.
3. **Реалтайм-прозрачность** ✅ — стриминг кода в UI (STUDIO_V4_STREAMING=1).
4. **Память проекта** ✅ — живой `design_state`: каждый шаг знает, что построено до него.
5. **Российский фокус** ✅ — TMA + Telegram Bot стеки, деплой в Timeweb/Selectel (Sprint 11), биллинг в звёздах.

---

## Что остаётся (не в V5)

| Задача | Где | Приоритет |
|---|---|---|
| E2B холодный старт — кастомные шаблоны | STUDIO_MASTER_PLAN.md Sprint 9 | КРИТ |
| SSE realtime логи превью | STUDIO_MASTER_PLAN.md Sprint 10 | Важно |
| Timeweb провизия (152-ФЗ) | STUDIO_MASTER_PLAN.md Sprint 11 | Важно |
| `STUDIO_V5_BUILD_GATE_STRICT=1` | tasks.py | Опц. (после стабилизации sandbox) |
| ESLint для react/vue | sandbox.py `run_quality_gate` | Опц. (tsc достаточен) |
| ruff check для Python | sandbox.py | Опц. |

*При изменении архитектуры генерации — обновлять этот файл.*
