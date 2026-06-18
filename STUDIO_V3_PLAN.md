# Studio V3 — Архитектурный план vibe-coding платформы мирового уровня

> Автор: главный архитектор AI-системы (Opus 4.8).
> Цель: довести aineron Studio до уровня Bolt.new / Lovable / v0 и превзойти их по надёжности генерации.
> Этот документ написан против **текущего состояния кода** (`src/studio/`), а не против старых планов.

---

## 0. Важное предисловие: что уже работает, и что НЕ надо переделывать

Прежде чем проектировать «новое», зафиксируем фактическое состояние кода, чтобы V3 не «решал» уже решённые проблемы (это первый признак плохого плана — разработчик перестаёт ему верить).

**Уже работает и НЕ требует переделки:**

| Механизм | Где | Статус |
|----------|-----|--------|
| Чтение реальных usage-токенов | `base.py:86,89-90` — `stream_options={'include_usage': True}`, читает `chunk.usage.completion_tokens` | ✅ работает |
| Continuation при упоре в лимит | `base.py:118` — `run_prompt_with_continuation()`, подставляет накопленный текст как `prior` assistant turn | ✅ работает, **в т.ч. уже принимает `stop_marker`** |
| Guardian видит 8000 символов | `guardian.py:104` — `content[:8000]` | ✅ исправлено (было 3000) |
| Streaming | `base.py:80` `stream=True` | ✅ работает |
| Sandbox + live preview | `sandbox.py`, `tasks.py:run_pipeline` | ✅ работает |
| Build check в Guardian | `tasks.py:426` `sandbox.run_build_check()` | ✅ работает |
| SSE events для UI | `events.py:publish_event`, вызовы `self.log()` | ✅ работает |
| Same-diff loop detection | `tasks.py:344-370` (хэш файлов, пауза после 2 одинаковых) | ✅ работает |
| Эскалация модели на повторных ошибках | `tasks.py:567-593`, `models_catalog.ESCALATION_MAP` | ✅ работает |
| Per-file генерация без JSON | `coder.py:_generate_one_file` (148) — используется в fix-итерациях и fallback | ✅ работает, но не является основным путём |

**Реально открытые проблемы (ровно их решает V3), из постановки задачи:**

1. **JSON-упаковка кода** — основной путь `coder._run_legacy` (216) просит `{"files":{path:content}}`. Один сломанный escape рушит весь шаг.
2. **Архитектор проектирует монолиты** — в `architect.py` нет НИ ОДНОГО правила про размер файла. Промпт `SYSTEM_COMMITS_*` не ограничивает декомпозицию.
3. **Fix-итерации перегенерируют весь файл** — `_generate_one_file` всегда пишет файл целиком, даже когда Guardian просит «добавь 2 ссылки в навбар».
4. **Нет детерминированной структурной проверки ПЕРЕД Guardian** — баланс скобок проверяет только примитивный `_is_truncated` (coder.py:72), и только внутри coder, не как gate.
5. **Нет визуального/дизайн-контроля** — ни архитектор, ни Guardian не отвечают за UI-качество. Нет DESIGN.md.
6. **Нет валидации зависимостей** — никто не сверяет `import` в коде с `dependencies` в package.json.
7. **Steps содержат 10+ файлов** — `planned_steps` ничем не ограничивает размер шага.

> **Оговорка про «потолок обрезки».** Старый `STUDIO_QUALITY_PLAN.md` предполагал, что обрезка происходит в прокси laozhang.ai. Проверить это из кода нельзя, и строить план на этом нельзя. Решение V3 (FILE_BLOCKS + per-file бюджет + continuation по явному маркеру) надёжно **независимо от того, где находится потолок** — потому что оно ловит обрыв детерминированно по отсутствию end-маркера и дозапрашивает с места обрыва. Это ключевое свойство: мы не угадываем причину, мы делаем механизм устойчивым к любой причине.

---

## 1. Концепция и философия

### Что отличает Bolt.new / Lovable / v0 от посредственных vibe-coders

Посредственный генератор кода оптимизирует **«сгенерировать файлы»**. Платформа мирового уровня оптимизирует **«пользователь увидел работающий красивый продукт за один проход»**. Разница в пяти принципах:

1. **Детерминизм важнее интеллекта.** Лучшие платформы не доверяют LLM то, что можно проверить кодом. Баланс скобок, целостность файла, наличие импортов, соответствие package.json — это **парсер и AST**, а не «попроси модель посмотреть». LLM подключается только там, где нужен вкус и смысл.

2. **Маленькие единицы генерации.** v0 генерирует компонент, а не приложение. Bolt пишет файл за файлом с явными границами. Никто не генерирует 10 файлов в одном JSON-блобе. Единица атомарности — **один файл ≤ 200 строк**.

3. **Дизайн — это вход, а не выход.** Lovable выдаёт красивый UI потому, что у него есть встроенная дизайн-система (shadcn/ui + Tailwind + продуманные токены), и промпт *требует* её использовать. Красота не «получается случайно» — она задаётся как ограничение на входе.

4. **Правки — это патчи, а не переписывание.** Когда пользователь говорит «сделай кнопку синей», Lovable меняет одну строку. Переписывать весь файл из-за одной правки — это и медленно, и источник регрессий, и упор в потолок токенов.

5. **Обратная связь от реального рантайма.** Bolt показывает ошибки сборки прямо из WebContainer и чинит их. Не «LLM думает, что код правильный» — а «vite собрал, или не собрал, вот лог».

### Философия V3 в одной фразе

> **Код передаётся в текстовом блочном формате с явными маркерами; всё, что можно проверить детерминированно, проверяется кодом до LLM; LLM-агенты отвечают только за смысл, архитектуру и вкус; правки идут диффами; дизайн задан как жёсткое ограничение на входе.**

---

## 2. Новый pipeline — детально

### 2.1 Диаграмма

```
Пользователь описывает проект
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Interviewer]  — 3-5 вопросов (без изменений, уже работает)          │
└─────────────────────────────────────────────────────────────────────┘
        │ answers
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Architect]  — 3 артефакта вместо 2:                                 │
│     • PROJECT.md   — спецификация (как сейчас)                         │
│     • DESIGN.md    — дизайн-система: палитра, типографика, компоненты  │
│     • COMMITS.md   — шаги с ЖЁСТКИМ манифестом файлов и лимитом строк  │
└─────────────────────────────────────────────────────────────────────┘
        │ steps[] (каждый шаг = {title, files:[{path, max_lines, role}]})
        ▼
   для каждого шага:
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Coder]  — генерирует ОДИН файл за раз в формате FILE_BLOCKS          │
│             (не JSON). Continuation по маркеру === END FILE ===        │
└─────────────────────────────────────────────────────────────────────┘
        │ files: dict[path, content]
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [StructureValidator]  — ЧИСТЫЙ КОД, не LLM. Gate перед Guardian:     │
│     • баланс {} () [] ; закрытость JSX-тегов                          │
│     • наличие end-маркера (файл не обрезан)                           │
│     • парс package.json                                               │
│     • import-граф vs dependencies                                     │
│     → FAIL: точечный авто-дозапрос coder (не весь шаг)                │
│     → PASS: дальше                                                    │
└─────────────────────────────────────────────────────────────────────┘
        │ structurally valid files
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [BuildCheck]  — sandbox: vite/next реально собирает (уже есть)       │
│     → ошибки компиляции идут в Guardian как факты, не догадки         │
└─────────────────────────────────────────────────────────────────────┘
        │ build logs
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Guardian]  — LLM, ТОЛЬКО смысл и логика:                            │
│     • реализован ли замысел шага                                      │
│     • интеграция с DESIGN.md (визуальное соответствие)               │
│     • НЕ проверяет обрезку/скобки (это сделал StructureValidator)     │
│     → PASS: commit, следующий шаг                                     │
│     → FIX: выдаёт EDIT-инструкции (что и где менять)                  │
└─────────────────────────────────────────────────────────────────────┘
        │ FIX
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Fixer/Coder]  — применяет EDIT blocks (search/replace),            │
│     а НЕ перегенерирует весь файл. Полная перегенерация — только      │
│     если файл структурно мёртв или правок > 40% файла.               │
└─────────────────────────────────────────────────────────────────────┘
        │ max 3 итерации → skip (как сейчас)
```

### 2.2 Агенты: роли и синхронизация

| Агент | Тип | Вход | Выход | Изменение vs текущего |
|-------|-----|------|-------|------------------------|
| **Interviewer** | LLM | описание | вопросы JSON | без изменений |
| **Architect** | LLM (×3 вызова) | answers | PROJECT.md, **DESIGN.md**, COMMITS.md (структурированный) | +DESIGN.md, +лимиты строк, +манифест файлов в шаге |
| **Coder** | LLM (per-file) | шаг + 1 целевой файл | 1 файл в FILE_BLOCKS | формат FILE_BLOCKS вместо JSON; основной путь = per-file |
| **StructureValidator** | **ЧИСТЫЙ КОД** | файлы | pass/fail + точные проблемы | **НОВЫЙ** |
| **DependencyValidator** | **ЧИСТЫЙ КОД** | файлы + package.json | недостающие/лишние deps | **НОВЫЙ** |
| **BuildCheck** | sandbox | файлы | build logs | без изменений (уже есть) |
| **Guardian** | LLM | шаг + DESIGN.md + build logs | pass / EDIT-инструкции | больше не проверяет обрезку; добавлен дизайн-чек |
| **Fixer** | LLM (per-file) | EDIT-инструкции | EDIT blocks | **НОВЫЙ формат**: диффы, не полные файлы |

**Синхронизация** остаётся на текущей Celery-цепочке (`coder_iteration → guardian_review → commit_to_gitea → next_step`), но в неё врезаются два детерминированных gate ПЕРЕД `guardian_review`:

```
coder_iteration
   → structure_gate (NEW, sync, в той же таске — это просто Python-функции)
       → если fail и итерация < N: точечный дозапрос coder того же файла
       → если pass: guardian_review.delay(...)
```

StructureValidator и DependencyValidator **не являются Celery-тасками** — это синхронные функции, вызываемые внутри `coder_iteration` сразу после генерации. Они мгновенны (мс), не стоят звёзд, не ходят в сеть.

### 2.3 Передача данных между агентами

- **PROJECT.md / DESIGN.md / COMMITS.md** хранятся в `StudioProject.project_md_content`, новом поле `design_md_content`, `commits_md_content`.
- **Структурированный план шагов** (`steps[]` с манифестом файлов и лимитами) хранится в `interview_data['plan']` как JSON — чтобы coder и валидаторы читали лимиты строк и роль файла без повторного парса markdown.
- **Файлы** — как сейчас, `StudioFile` (path, content) + зеркало в sandbox.
- **EDIT-инструкции от Guardian** → `pipeline.fix_plan` (уже есть поле), но новый формат (см. §5).

---

## 3. Решение проблемы обрезки раз и навсегда

### 3.1 Формат FILE_BLOCKS вместо JSON

JSON-упаковка кода — корневое зло (`_run_legacy`). Меняем на текстовый блочный формат с явными маркерами:

```
=== FILE: src/components/Header.tsx ===
'use client'
import { Menu } from 'lucide-react'

export default function Header() {
  return (
    <header className="...">...</header>
  )
}
=== END FILE ===
```

**Почему это решает обрезку:**
1. **Нет escaping** — код пишется как есть, ни один `"` или `\` не ломает структуру.
2. **Детерминированная проверка целостности** — файл считается полным ⇔ присутствует `=== END FILE ===`. Это не эвристика по скобкам, это явный маркер.
3. **Continuation по маркеру уже встроен.** `run_prompt_with_continuation(stop_marker='=== END FILE ===')` — параметр `stop_marker` уже существует (`base.py:122,137`). Если маркера нет → модель упёрлась в лимит → дозапрос с накопленным `prior` → модель продолжает ровно с обрыва.
4. **Один файл = один бюджет.** Не «4 файла на 12000 токенов», а каждый файл получает полные 24000 токенов.

### 3.2 Парсер FILE_BLOCKS (новый модуль `src/studio/agents/blocks.py`)

```python
import re

FILE_OPEN = re.compile(r'^===\s*FILE:\s*(.+?)\s*===\s*$', re.MULTILINE)
FILE_CLOSE = '=== END FILE ==='

def parse_file_blocks(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Парсит вывод модели в формате FILE_BLOCKS.
    Возвращает (files, incomplete_paths):
      files            — {path: content} для ПОЛНЫХ блоков (с END-маркером)
      incomplete_paths — пути блоков без END-маркера (обрезаны → нужен дозапрос)
    """
    files: dict[str, str] = {}
    incomplete: list[str] = []
    # Находим все открывающие маркеры с их позициями
    opens = list(FILE_OPEN.finditer(text))
    for i, m in enumerate(opens):
        path = m.group(1).strip().lstrip('/')
        body_start = m.end()
        body_end = opens[i + 1].start() if i + 1 < len(opens) else len(text)
        body = text[body_start:body_end]
        if FILE_CLOSE in body:
            content = body.split(FILE_CLOSE)[0]
            files[path] = _normalize(content)
        else:
            # блок не закрыт — обрезан
            incomplete.append(path)
            files[path] = _normalize(body)  # сохраняем частичное для continuation
    return files, incomplete


def _normalize(content: str) -> str:
    # убрать ведущий/замыкающий пустой и случайные markdown-fences внутри блока
    content = content.strip('\n')
    content = re.sub(r'^```[\w]*\n', '', content)
    content = re.sub(r'\n```\s*$', '', content)
    return content.rstrip() + '\n'
```

**Ключевая идея:** даже при per-file генерации мы оборачиваем единственный файл в FILE_BLOCKS, чтобы `=== END FILE ===` служил `stop_marker` для continuation. Это даёт детерминированный сигнал «файл закончился», которого нет у голого текста.

### 3.3 Многофайловый шаг в FILE_BLOCKS (для редких шагов, где файлы мелкие)

Если шаг создаёт несколько мелких файлов (≤ 60 строк каждый — например, типы, конфиги), можно сгенерировать их одним вызовом:

```
=== FILE: src/types/user.ts ===
export interface User { id: string; name: string }
=== END FILE ===
=== FILE: src/lib/constants.ts ===
export const API_URL = '/api'
=== END FILE ===
=== END RESPONSE ===
```

Парсер вернёт оба файла. **Один сломанный файл больше не рушит остальные** — каждый имеет свои границы.

> **ВНИМАНИЕ — тонкость continuation в многофайловом режиме.** `run_prompt_with_continuation` (`base.py:137`) останавливается на **первом** вхождении `stop_marker`:
> ```python
> if stop_marker and stop_marker in full:
>     break
> ```
> Поэтому для многофайлового вызова `stop_marker` НЕ должен быть `=== END FILE ===`: иначе после первого же закрытого файла цикл прервётся, и обрезанный последний файл не будет дозапрошен. Решение — **терминальный маркер всего ответа** `=== END RESPONSE ===` как `stop_marker`; отдельные файлы парсятся внутри по `=== FILE ===`/`=== END FILE ===`. Тогда continuation дозапрашивает, пока модель не выдаст `=== END RESPONSE ===`, и обрезанный хвост любого файла корректно достраивается.
>
> Для **per-file режима** (основной путь, один файл за вызов) `stop_marker='=== END FILE ==='` корректен — там вхождение ровно одно. Именно per-file остаётся главным truncation-safe путём; многофайловый — оптимизация для пачки мелких файлов.

### 3.4 Детерминированная проверка целостности

```python
def is_structurally_complete(path: str, content: str) -> tuple[bool, str]:
    """True если файл выглядит целым. Возвращает (ok, reason)."""
    s = content.rstrip()
    if not s:
        return False, 'empty'
    # 1. Баланс парных символов
    for open_c, close_c in [('{', '}'), ('(', ')'), ('[', ']')]:
        if s.count(open_c) != s.count(close_c):
            # допускаем перекос в строках/комментах — поэтому это soft-сигнал,
            # см. _strip_strings ниже для точности
            stripped = _strip_strings_and_comments(s)
            if stripped.count(open_c) != stripped.count(close_c):
                return False, f'unbalanced {open_c}{close_c}'
    # 2. JSX/TSX: открытые теги
    if path.endswith(('.tsx', '.jsx')):
        if not _jsx_tags_balanced(s):
            return False, 'unclosed JSX tag'
    # 3. JSON — реальный парс
    if path.endswith('.json'):
        import json
        try:
            json.loads(s)
        except Exception as e:
            return False, f'invalid JSON: {e}'
    # 4. Последний значимый символ
    if s[-1] not in '}>);\'"`]':
        return False, 'ends mid-statement'
    return True, ''
```

`_strip_strings_and_comments` убирает строковые литералы и комментарии перед подсчётом скобок (чтобы `"}"` в строке не считалось закрытием).

> **Важно про авторитетность сигналов.** Единственный **по-настоящему детерминированный** признак обрезки — это **отсутствие end-маркера** (`=== END FILE ===`): либо он есть, либо нет. Подсчёт скобок на TS/JS остаётся эвристикой даже после вычистки строк и комментариев — его ломают дженерики (`Array<{x:number}>`), template-литералы (`${...}`), regex-литералы. Поэтому:
> - **Отсутствие end-маркера** → жёсткий gate (файл точно обрезан → дозапрос).
> - **Дисбаланс скобок/JSX** → **advisory-сигнал**, не жёсткий gate. Он добавляется как подсказка в дозапрос, но финальным судьёй синтаксиса служит **реальный build check** (`run_build_check`, уже есть), который ловит подлинные ошибки компиляции без ложных срабатываний.
>
> Это страхует от ровно того цикла, который V3 убивает: ложный structure-fail из-за дженерика не должен сам по себе гнать файл на бесконечную перегенерацию.

---

## 4. Архитектор нового уровня

### 4.1 Правила декомпозиции (файлы ≤ 200 строк)

Архитектор обязан планировать так, чтобы каждый файл был ≤ 200 строк. Правила декомпозиции, зашитые в промпт:

1. **Одна ответственность на файл.** Страница не содержит inline-компонентов > 30 строк — они выносятся.
2. **UI-компонент = отдельный файл.** Header, Footer, Card, Button, Modal — каждый свой файл.
3. **Логика отделена от представления.** Хуки (`useX.ts`), утилиты (`lib/`), типы (`types/`) — отдельно от компонентов.
4. **Данные/моки — отдельный файл** (`lib/data.ts`), не зашиты в компонент.
5. **Стили** — глобальные в одном `globals.css`, остальное Tailwind-классами в JSX (не отдельные CSS-файлы на компонент).
6. Если по оценке архитектора файл выйдет > 200 строк — он **обязан** разбить его на 2+ файла в плане.

### 4.2 DESIGN.md — отдельный документ дизайн-решений

Новый артефакт, генерируется архитектором между PROJECT.md и COMMITS.md. Структура:

```markdown
# DESIGN.md

## Дизайн-направление
Минималистичный, профессиональный (ориентир: Linear / Vercel).

## Цветовая палитра (CSS-переменные)
--background: #0a0a0a; --foreground: #fafafa;
--primary: #6366f1; --muted: #27272a; --border: #27272a;
(светлая тема — отдельный блок)

## Типографика
Шрифт: Inter (через next/font или bunny.net). 
Заголовки: font-semibold, tracking-tight. Тело: text-sm/text-base, text-muted.

## Компоненты по умолчанию
- Кнопки: rounded-lg, h-10, px-4, transition, hover:opacity-90
- Карточки: rounded-xl, border, bg-card, p-6, shadow-sm
- Инпуты: rounded-lg, border, h-10, focus:ring-2

## Сетка и отступы
Контейнер max-w-6xl mx-auto px-4. Вертикальный ритм: space-y-6 / py-16.

## Иконки
Только lucide-react, size 16/20/24. Никаких эмодзи.

## Состояния
loading (skeleton), empty (иллюстрация + CTA), error (тост).
```

DESIGN.md передаётся **в каждый вызов coder и Guardian** — так дизайн становится единым ограничением на весь проект, а не «как повезёт в каждом файле».

### 4.3 Новый формат COMMITS.md + структурированный план

Markdown для человека + JSON для машины. Архитектор выводит шаги так:

```markdown
## Шаг 2: Хедер и навигация
Создать адаптивный хедер с логотипом и навигацией.

FILES:
- src/components/Header.tsx | ≤120 | компонент хедера, мобильное меню
- src/components/Nav.tsx | ≤60 | список ссылок навигации
```

Парсер (в архитекторе) превращает это в:

```python
{
  "step": 2,
  "title": "Хедер и навигация",
  "description": "...",
  "files": [
    {"path": "src/components/Header.tsx", "max_lines": 120, "role": "компонент хедера, мобильное меню"},
    {"path": "src/components/Nav.tsx",    "max_lines": 60,  "role": "список ссылок навигации"}
  ]
}
```

**Жёсткие ограничения в промпте архитектора:**
- ≤ 5 файлов на шаг (проблема №7: «10+ файлов за раз»).
- Каждый файл ≤ 200 строк (`max_lines`).
- 6-14 шагов на проект.
- Шаг 1: всегда package.json + конфиги + точка входа.
- Файлы внутри шага логически связаны (один экран / одна фича).

### 4.4 Как обеспечить визуальную красоту

Красота не «получается» — она задаётся. Три рычага:
1. **DESIGN.md как контракт** — конкретные токены и классы, не «сделай красиво».
2. **Стартовый scaffold** (см. §7) — Tailwind + предустановленные UI-примитивы в шаге 1.
3. **Guardian-дизайн-чек** — Guardian сверяет, использует ли код токены из DESIGN.md (а не хардкод цветов), есть ли состояния loading/empty/error.

---

## 5. Fix-итерации через Search/Replace (EDIT blocks)

### 5.1 Формат EDIT blocks

Когда правка локальна, Guardian выдаёт не «перепиши файл», а точечные диффы:

```
=== EDIT: src/components/Header.tsx ===
<<<<<<< SEARCH
<nav className="flex gap-4">
  <a href="/">Главная</a>
</nav>
=======
<nav className="flex gap-4">
  <a href="/">Главная</a>
  <a href="/about">О нас</a>
  <a href="/contact">Контакты</a>
</nav>
>>>>>>> REPLACE
=== END EDIT ===
```

Это формат aider/Cline — проверенный в проде. SEARCH-блок должен **точно** совпадать с куском файла (включая отступы).

### 5.2 Парсер и применение патчей (`src/studio/agents/edits.py`)

```python
import re

EDIT_OPEN = re.compile(r'^===\s*EDIT:\s*(.+?)\s*===\s*$', re.MULTILINE)

def parse_edits(text: str) -> list[dict]:
    """Возвращает [{path, search, replace}, ...]."""
    edits = []
    for m in EDIT_OPEN.finditer(text):
        path = m.group(1).strip().lstrip('/')
        body = text[m.end():].split('=== END EDIT ===')[0]
        sm = re.search(r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
                       body, re.DOTALL)
        if sm:
            edits.append({'path': path, 'search': sm.group(1), 'replace': sm.group(2)})
    return edits


def apply_edits(files: dict[str, str], edits: list[dict]) -> tuple[dict, list[str]]:
    """
    Применяет патчи. Возвращает (updated_files, failed_paths).
    failed_paths — патчи, где SEARCH не найден (нужен fallback на полный файл).
    """
    out = dict(files)
    failed = []
    for e in edits:
        content = out.get(e['path'])
        if content is None or e['search'] not in content:
            failed.append(e['path'])
            continue
        # заменяем первое вхождение — детерминированно
        out[e['path']] = content.replace(e['search'], e['replace'], 1)
    return out, failed
```

### 5.3 Когда diff, когда полная перегенерация

Детерминированное правило (не на усмотрение LLM):

| Условие | Действие |
|---------|----------|
| Файл структурно мёртв (StructureValidator fail) | **Полная перегенерация** через FILE_BLOCKS |
| SEARCH-блок не найден в файле | Fallback: перегенерация этого файла |
| Объём правок > 40% строк файла | Полная перегенерация (диффы не дают выигрыша) |
| Новый файл (не существует) | FILE_BLOCKS (нечего патчить) |
| Локальная правка существующего целого файла | **EDIT blocks** |

Эвристику «40%» считает код по числу SEARCH-строк vs строк файла, до вызова модели.

---

## 6. Валидация и тестирование

### 6.1 StructureValidator (детерминированно, без LLM) — `src/studio/validators.py`

Запускается синхронно сразу после coder, ДО Guardian. Главный жёсткий критерий — **наличие end-маркера** (файл не обрезан); дисбаланс скобок/JSX из `is_structurally_complete` (§3.4) идёт как advisory-подсказка. При отсутствии маркера — точечный дозапрос coder того же файла (с конкретной причиной), без траты на Guardian и без перегенерации остальных файлов. Подлинные синтаксические ошибки целого, но кривого файла ловит build check, а не структурный gate — это исключает ложноположительные циклы.

### 6.2 DependencyValidator (детерминированно) — `src/studio/validators.py`

```python
import re, json

# bare-import: import x from 'pkg'  /  require('pkg')  — не относительные './'
IMPORT_RE = re.compile(r"""(?:import[^'"]*|require\()\s*['"]([^'".][^'"]*)['"]""")
BUILTIN = {'react', 'react-dom', 'next', 'vite'}  # частичный, расширяется

def validate_dependencies(files: dict[str, str]) -> dict:
    """Сверяет bare-импорты с dependencies в package.json."""
    pkg_raw = files.get('package.json', '{}')
    try:
        pkg = json.loads(pkg_raw)
    except Exception:
        return {'ok': False, 'reason': 'package.json не парсится'}
    declared = set(pkg.get('dependencies', {})) | set(pkg.get('devDependencies', {}))
    used = set()
    for path, content in files.items():
        if not path.endswith(('.ts', '.tsx', '.js', '.jsx')):
            continue
        for imp in IMPORT_RE.findall(content):
            pkg_name = imp.split('/')[0]
            if imp.startswith('@'):  # scoped: @scope/pkg
                pkg_name = '/'.join(imp.split('/')[:2])
            used.add(pkg_name)
    missing = used - declared - {'node:fs', 'node:path'}
    missing = {m for m in missing if not m.startswith(('node:', '.'))}
    return {'ok': not missing, 'missing': sorted(missing)}
```

Если `missing` непуст → автоматически добавить пакеты в package.json (с известными версиями из whitelist) ИЛИ вернуть coder на исправление импорта. Это закрывает проблему №6 («нет валидации зависимостей» из §0) детерминированно.

### 6.3 Реальный build check vs LLM-ревью

- **Build check (sandbox)** — источник истины о компиляции. Уже работает (`run_build_check`). В V3 он запускается **до** Guardian, и его лог идёт в Guardian как факт.
- **LLM-ревью (Guardian)** — только то, что не ловит компилятор: смысл, дизайн, UX, логические дыры.

### 6.4 Что проверяет Guardian и что НЕ должен

**Guardian проверяет (только LLM-уровень):**
- Реализован ли замысел шага (фичи на месте).
- Соответствие DESIGN.md (токены, состояния, отсутствие эмодзи).
- Логические дыры (кнопка без обработчика, форма без сабмита).
- UX: есть ли loading/empty/error.

**Guardian НЕ проверяет (это делает код ДО него):**
- Обрезку/целостность файла → StructureValidator.
- Баланс скобок/тегов → StructureValidator.
- Недостающие зависимости → DependencyValidator.
- Ошибки компиляции → BuildCheck (Guardian только читает готовый лог).

Это убирает главную патологию текущего Guardian — попытки судить об обрезке по `content[:8000]` (он всё равно не видит конца большого файла).

---

## 7. Визуальное качество

### 7.1 Стартовый scaffold (шаг 1 всегда одинаковый каркас)

Чтобы UI был красивым без дизайнера, шаг 1 каждого React/Next-проекта ставит готовый дизайн-фундамент:

- **Tailwind CSS** + CSS-переменные из DESIGN.md в `globals.css`.
- **UI-примитивы** в `src/components/ui/` (Button, Card, Input, Badge) — стилизованы под DESIGN.md, как урезанный shadcn/ui (но без зависимости — просто Tailwind-обёртки, чтобы не тянуть генерацию).
- **lucide-react** для иконок (правило проекта — без эмодзи).
- **Inter** через next/font или bunny.net.

Coder в последующих шагах **обязан** использовать эти примитивы, а не верстать кнопки с нуля. Это даёт визуальную консистентность.

### 7.2 Библиотеки по умолчанию

| Назначение | Библиотека | Почему |
|-----------|-----------|--------|
| Стили | Tailwind CSS | детерминируемый, нет CSS-файлов на компонент |
| Иконки | lucide-react | правило проекта, единый стиль |
| Компоненты | свои Tailwind-примитивы (shadcn-стиль) | без тяжёлых зависимостей |
| Анимации | tailwindcss-animate / CSS transitions | лёгкие |
| Графики (если нужны) | recharts | стандарт |
| Формы | нативные + Tailwind | без лишнего |

### 7.3 Стандарты дизайна в промптах

В системный промпт coder и Guardian встраивается выжимка DESIGN.md + жёсткие запреты:
- Никаких inline-стилей, только Tailwind-классы.
- Никаких хардкод-цветов (`#fff`) — только токены (`bg-background`).
- Каждый интерактивный элемент имеет hover/focus-состояние.
- Обязательны состояния loading/empty/error для любых данных.
- Запрет эмодзи (правило проекта), только lucide-иконки.

---

## 8. Промпт-инжиниринг нового уровня

### 8.1 Architect — COMMITS (с декомпозицией)

```python
ARCHITECT_COMMITS_RU = (
"Ты ведущий архитектор. Составь пошаговый план COMMITS.md.\n\n"
"ЖЁСТКИЕ ПРАВИЛА ДЕКОМПОЗИЦИИ:\n"
"- Каждый файл ≤ 200 строк. Если файл выйдет больше — РАЗБЕЙ на несколько.\n"
"- ≤ 5 файлов на шаг. Файлы шага логически связаны (один экран/фича).\n"
"- Один компонент = один файл. Логика (хуки/утилиты/типы) отдельно от UI.\n"
"- Моки и данные — в lib/data.ts, не внутри компонента.\n"
"- 6-14 шагов. Шаг 1: package.json + конфиги + точка входа + UI-примитивы.\n"
"- Для Vite: vite.config.ts с server:{host:true,port:3000,hmr:false}.\n"
"- Для Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'.\n\n"
"Формат каждого шага СТРОГО:\n"
"## Шаг N: Название\n"
"Описание.\n"
"FILES:\n"
"- путь/файл.tsx | ≤<макс_строк> | роль файла\n\n"
"Выводи ТОЛЬКО markdown. Без JSON, без code-fences."
)
```

### 8.2 Architect — DESIGN.md

```python
ARCHITECT_DESIGN_RU = (
"Ты ведущий продуктовый дизайнер. Напиши DESIGN.md — дизайн-систему проекта.\n"
"Ориентир: Linear, Vercel, Stripe — строгий минимализм, профессионально.\n"
"Включи разделы: Дизайн-направление; Цветовая палитра (CSS-переменные, тёмная+светлая);\n"
"Типографика (шрифт Inter, размеры, веса); Компоненты по умолчанию (кнопки, карточки,\n"
"инпуты — с конкретными Tailwind-классами); Сетка и отступы; Иконки (только lucide-react,\n"
"без эмодзи); Состояния (loading/empty/error).\n"
"Давай КОНКРЕТНЫЕ значения (#hex, rounded-lg, h-10), не общие слова.\n"
"Выводи ТОЛЬКО markdown. На русском."
)
```

### 8.3 Coder — FILE_BLOCKS

```python
CODER_FILE_RU = (
"Ты senior-разработчик. Напиши ОДИН полный файл в формате FILE_BLOCKS.\n\n"
"ФОРМАТ ВЫВОДА СТРОГО:\n"
"=== FILE: <путь> ===\n"
"<полное содержимое файла>\n"
"=== END FILE ===\n\n"
"Маркер === END FILE === ОБЯЗАТЕЛЕН в конце — это сигнал завершения.\n"
"Не используй JSON. Не используй markdown-fences вокруг кода.\n\n"
"ТРЕБОВАНИЯ:\n"
"- Файл 100% полный и production-ready, ≤ указанного лимита строк.\n"
"- Используй UI-примитивы из src/components/ui/ и токены из DESIGN.md.\n"
"- Только Tailwind-классы, без inline-стилей и хардкод-цветов.\n"
"- Иконки только lucide-react, без эмодзи.\n"
"- Обработай состояния: loading, empty, error.\n"
"- Next.js: 'use client' где нужно. Без TODO и заглушек.\n"
"Комментарии можно на русском."
)
```

В user-промпт coder передаётся: целевой путь и его `max_lines`/`role`, выжимка DESIGN.md, список примитивов из `ui/`, и (для существующего файла) текущее содержимое.

### 8.4 Guardian — только логика и дизайн

```python
GUARDIAN_RU = (
"Ты старший ревьюер. Структурная целостность (скобки, обрезка, импорты,\n"
"сборка) УЖЕ проверена кодом до тебя — НЕ комментируй обрезку и скобки.\n\n"
"Проверь ТОЛЬКО:\n"
"1. Реализован ли замысел шага (фичи на месте)?\n"
"2. Соответствие DESIGN.md: токены вместо хардкод-цветов, lucide-иконки,\n"
"   состояния loading/empty/error, без эмодзи?\n"
"3. Логика: кнопки с обработчиками, формы с сабмитом, нет мёртвых ссылок?\n"
"Если есть build-логи с ошибкой — учти их.\n\n"
"Для правок выдавай EDIT blocks (точечные диффы), НЕ перегенерацию:\n"
"=== EDIT: <путь> ===\n"
"<<<<<<< SEARCH\n<точный кусок>\n=======\n<новый кусок>\n>>>>>>> REPLACE\n"
"=== END EDIT ===\n\n"
"Ответь:\n"
"VERDICT: pass | fix\n"
"ISSUES:\n- ...\n"
"EDITS:\n<edit blocks или пусто>\n"
"FILES:\n- путь (только если нужна полная перегенерация файла)"
)
```

---

## 9. Реализация по коммитам

Порядок выбран так, чтобы каждый коммит был самодостаточным, тестируемым и не ломал работающий pipeline.

### Коммит 1 — Парсер FILE_BLOCKS + структурный валидатор (фундамент, без интеграции)
- **Новый** `src/studio/agents/blocks.py`: `parse_file_blocks`, `_normalize`.
- **Новый** `src/studio/validators.py`: `is_structurally_complete`, `_strip_strings_and_comments`, `_jsx_tags_balanced`, `validate_dependencies`.
- **Тесты** `src/studio/tests.py`: обрезанный блок → `incomplete`; полный → `files`; невалидный package.json → fail; недостающая зависимость → в `missing`.
- Риск: нулевой (ничего не вызывает эти модули ещё).

### Коммит 2 — Coder на FILE_BLOCKS (замена `_run_legacy`)
- `src/studio/agents/coder.py`:
  - Заменить `FILE_SYSTEM_*` промпты на `CODER_FILE_RU/EN` (формат FILE_BLOCKS).
  - `_generate_one_file` оборачивает запрос: `run_prompt_with_continuation(..., stop_marker='=== END FILE ===')`, затем `parse_file_blocks` для извлечения.
  - **Удалить** `_run_legacy` (JSON-путь) и сделать per-file основным путём в `run()`.
  - `_is_truncated` заменить вызовом `is_structurally_complete`.
- Риск: средний — основной путь генерации. Тестировать на одном проекте до релиза.

### Коммит 3 — Структурный gate в pipeline
- `src/studio/tasks.py:coder_iteration`: после `agent.run(...)` и до `guardian_review.delay(...)` вставить:
  - `is_structurally_complete` по каждому файлу; при fail и `iteration < N` — точечный дозапрос coder того же файла с указанием причины;
  - `validate_dependencies`; при `missing` — авто-добавление в package.json из whitelist либо дозапрос.
- Это синхронные вызовы внутри таски (не новые Celery-таски).
- Риск: средний — врезка в горячий путь. Покрыть тестом на «обрезанном» файле.

### Коммит 4 — Architect: DESIGN.md + декомпозиция
- `src/studio/models.py`: новое поле `design_md_content = models.TextField(blank=True)` + миграция.
- `src/studio/agents/architect.py`:
  - Третий вызов — генерация DESIGN.md (`ARCHITECT_DESIGN_RU`).
  - Новый `ARCHITECT_COMMITS_RU` с правилами декомпозиции и форматом `FILES: - path | ≤N | role`.
  - Парсер шагов → `interview_data['plan']` (список шагов с файлами и `max_lines`).
- `src/studio/tasks.py:agent_analyze`: сохранять `design_md_content` и `plan`.
- Риск: низкий — расширение, обратная совместимость (если plan не распарсился — fallback на старое поведение).

### Коммит 5 — Coder/Guardian читают DESIGN.md и лимиты
- `coder.py`: в user-промпт добавить выжимку `design_md_content`, `max_lines`/`role` целевого файла, список `ui/`-примитивов.
- `guardian.py`: добавить `design_md_content` в контекст + дизайн-чек в промпт (`GUARDIAN_RU`).
- Риск: низкий.

### Коммит 6 — EDIT blocks (диффы вместо перегенерации)
- **Новый** `src/studio/agents/edits.py`: `parse_edits`, `apply_edits`.
- `guardian.py`: новый формат вывода с `EDITS:` секцией; парсинг в `_parse_guardian_response` → `fix_plan['edits']`.
- `tasks.py:coder_iteration` (fix-ветка) и/или новый `fixer`: если `fix_plan['edits']` есть и SEARCH найден — `apply_edits`; иначе fallback на per-file перегенерацию (правило §5.3, эвристика 40%).
- Тесты: применение патча; не найден SEARCH → failed; >40% → перегенерация.
- Риск: средний — меняет fix-логику. Сохранить полный fallback.

### Коммит 7 — Стартовый scaffold (UI-примитивы)
- `architect.py`/шаблон шага 1: гарантировать генерацию `src/components/ui/{Button,Card,Input,Badge}.tsx` + `globals.css` с токенами из DESIGN.md.
- Можно как статический scaffold-словарь, записываемый при инициализации (надёжнее, чем доверять LLM шаг 1).
- Риск: низкий, повышает качество.

### Коммит 8 — Метрики и наблюдаемость
- `events.py` / `interview_data`: писать в `billing_log`/новый `metrics` per-step: число continuation-раундов, structure-fail count, dep-fail count, итерации до pass, build pass/fail.
- Риск: нулевой.

> **Откат:** каждый коммит за фиче-флагом `settings.STUDIO_V3` (по умолчанию off в проде до прогона). Коммиты 1, 8 безопасны всегда.

---

## 10. Метрики качества

Чтобы доказать «мировой уровень», нужны измеримые показатели, логируемые per-step в `interview_data['metrics']`:

| Метрика | Как считать | Целевое значение |
|---------|-------------|------------------|
| **Truncation rate** | доля файлов, попавших в `incomplete` при первом проходе | < 2% |
| **Structure-fail rate** | доля файлов, не прошедших StructureValidator с первого раза | < 5% |
| **Dependency-fail rate** | доля шагов с непустым `missing` | < 5% |
| **First-pass Guardian rate** | доля шагов, принятых Guardian без fix-итераций | > 70% |
| **Avg fix iterations** | среднее число итераций до pass | < 0.5 |
| **Build success rate** | доля шагов, где `run_build_check` exit 0 | > 90% |
| **Skip rate** | доля шагов, упёршихся в max_iterations и пропущенных | < 3% |
| **Diff-vs-rewrite ratio** | доля fix-итераций, решённых EDIT blocks (не перегенерацией) | > 60% |
| **Avg file length** | средняя длина сгенерированного файла | < 150 строк |
| **Stars per project** | среднее списание звёзд на завершённый проект | падает vs V2 (меньше итераций) |
| **Time to first preview** | от старта до первого живого preview | падает vs V2 |
| **Visual pass** (ручная выборка) | % проектов, где UI «выглядит как продукт» (ревью человеком, 20 проектов/нед) | > 80% |

**Главный интегральный KPI:** доля проектов, дошедших до `completed` **без паузы на `paused_on_loop`** и с успешной сборкой. Цель — **> 85%**. Это и есть «работающий красивый продукт за один проход».

---

## Приложение A — Сводка новых/изменённых файлов

| Файл | Действие |
|------|----------|
| `src/studio/agents/blocks.py` | **создать** — парсер FILE_BLOCKS |
| `src/studio/agents/edits.py` | **создать** — парсер/применение EDIT blocks |
| `src/studio/validators.py` | **создать** — StructureValidator + DependencyValidator |
| `src/studio/agents/coder.py` | переписать на FILE_BLOCKS, убрать `_run_legacy` (JSON) |
| `src/studio/agents/architect.py` | +DESIGN.md, новый COMMITS с декомпозицией и манифестом |
| `src/studio/agents/guardian.py` | дизайн-чек, EDIT-формат, убрать структурные проверки |
| `src/studio/tasks.py` | structure/dep gate перед Guardian; EDIT-ветка в fix |
| `src/studio/models.py` | +`design_md_content`, миграция |
| `src/studio/models_catalog.py` | без изменений (модели/эскалация уже ок) |
| `src/studio/agents/base.py` | без изменений (continuation+usage уже есть) |
| `src/studio/tests.py` | тесты парсеров и валидаторов |

## Приложение B — Что осознанно НЕ меняем

- `run_prompt_with_continuation`, чтение usage, streaming, SSE, sandbox, same-diff detection, эскалация моделей, биллинг — работают, трогать не нужно. V3 строится **поверх** этих механизмов, а не вместо них.
