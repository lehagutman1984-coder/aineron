# Studio V3 — Детальный план по коммитам

> Автор: Claude Opus 4.8
> Цель: Реализация Studio V3 по `STUDIO_V3_PLAN.md` — полный переход на FILE_BLOCKS,
> детерминированную валидацию, EDIT blocks, DESIGN.md.
> Для пошаговой реализации в новых сессиях Claude Sonnet.
>
> Этот файл написан против **фактического состояния кода** на момент написания:
> - последняя миграция studio: `0012_agent_models`
> - флаги STUDIO_* в `src/config/settings.py` строки 301-313
> - `src/studio/tests.py` использует `APITestCase` (есть класс `StudioAPITests`)
> - `base.py` уже имеет `run_prompt_with_continuation(stop_marker=...)`, чтение usage, streaming
> - в `coder.py` основной путь — `_run_legacy` (JSON `{"files":{...}}`), плюс per-file fallback
> - в `guardian.py` формат вывода: VERDICT / ISSUES / INSTRUCTIONS / FILES

---

## Обзор изменений

| Коммит | Цель | Риск | Затронутые файлы |
|--------|------|------|------------------|
| **1** | Фундамент: парсер FILE_BLOCKS + валидаторы + флаг `STUDIO_V3` + тесты | нулевой | `agents/blocks.py` (new), `validators.py` (new), `config/settings.py`, `tests.py` |
| **2** | Coder: FILE_BLOCKS как основной путь под флагом (legacy сохраняется) | средний | `agents/coder.py` |
| **3** | Pipeline: structure gate + dependency gate перед guardian_review | средний | `tasks.py` |
| **4** | Architect: DESIGN.md + новый COMMITS-формат + `plan` JSON + миграция | низкий | `models.py`, миграция (new), `agents/architect.py`, `tasks.py` |
| **5** | Coder/Guardian читают DESIGN.md и лимиты строк | низкий | `agents/coder.py`, `agents/guardian.py` |
| **6** | EDIT blocks: диффы вместо перегенерации | средний | `agents/edits.py` (new), `agents/guardian.py`, `tasks.py`, `tests.py` |
| **7** | Стартовый scaffold: UI-примитивы в шаге 1 | низкий | `agents/architect.py` или `tasks.py`, `scaffold.py` (new) |
| **8** | Метрики per-step в `interview_data['metrics']` | нулевой | `tasks.py`, `agents/coder.py` |

---

## Фиче-флаг STUDIO_V3

**Важнейший принцип всего плана: при `STUDIO_V3=False` поведение должно быть БАЙТ-В-БАЙТ идентично текущему.** Это инвариант каждого коммита 2-8. Именно он делает каждый коммит самодостаточным и безопасным к деплою: если что-то сломалось — выключаем флаг в `.env`, и pipeline работает как до V3.

### Как добавляется (часть Коммита 1)

В `src/config/settings.py` рядом со строкой 313 (после `STUDIO_PIPELINE_MAX_SEC`):

```python
STUDIO_V3 = os.getenv('STUDIO_V3', '0') == '1'
```

По умолчанию **выключен**. Коммиты 2-6 читают его через `from django.conf import settings` и `if settings.STUDIO_V3:`.

### Как использовать в коде

Везде в коде:
```python
from django.conf import settings
...
if settings.STUDIO_V3:
    # новый путь V3 (FILE_BLOCKS / DESIGN.md / EDIT blocks / gates)
else:
    # старый путь (JSON _run_legacy, без gate, полная перегенерация)
```

### КРИТИЧЕСКОЕ РАЗРЕШЕНИЕ ПРОТИВОРЕЧИЯ (читать обязательно)

`STUDIO_V3_PLAN.md` §9 Коммит 2 говорит «**Удалить** `_run_legacy`». **НЕ ДЕЛАЙ ЭТОГО в рамках этих 8 коммитов.**

Причина: задача требует фиче-флаг `STUDIO_V3` (по умолчанию False), который **переключает** новый и старый путь. Если удалить `_run_legacy`, то ветки `STUDIO_V3=False` некуда переключаться — pipeline сломается при выключенном флаге. Поэтому:

- `_run_legacy` **остаётся** как ветка `STUDIO_V3=False`.
- FILE_BLOCKS работает только под `if settings.STUDIO_V3:`.
- Удаление `_run_legacy` — отдельная задача **после** того, как V3 проверен в проде и флаг включён по умолчанию. В эти 8 коммитов она НЕ входит.

Это единственное место, где два исходных документа (`STUDIO_V3_PLAN.md` и постановка задачи) расходятся. Приоритет — у требования фиче-флага из постановки задачи.

---

## Коммит 1: Парсер FILE_BLOCKS + валидаторы + флаг STUDIO_V3 (фундамент, ничего не ломает)

### Заголовок коммита
```
studio v3: add FILE_BLOCKS parser, structure/dependency validators, STUDIO_V3 flag
```

### Цель
Создать фундамент V3 — два новых модуля с чистыми (без LLM, без сети) функциями: парсер блочного формата и детерминированные валидаторы. Добавить фиче-флаг. Покрыть тестами. Ничего из существующего кода эти модули пока **не вызывает** — риск нулевой.

### Затронутые файлы
- `src/studio/agents/blocks.py` — **создать**
- `src/studio/validators.py` — **создать**
- `src/config/settings.py` — добавить 1 строку (флаг)
- `src/studio/tests.py` — добавить тест-класс

### Детальные изменения

#### Новый файл `src/studio/agents/blocks.py` (полный код)

```python
"""
Парсер блочного текстового формата FILE_BLOCKS (заменяет JSON-упаковку кода).

Формат вывода модели:
    === FILE: src/components/Header.tsx ===
    <содержимое файла>
    === END FILE ===
    === FILE: src/lib/utils.ts ===
    <содержимое>
    === END FILE ===
    === END RESPONSE ===

Преимущество перед JSON: нет escaping (ни один " или \\ не ломает структуру),
а целостность файла проверяется детерминированно по наличию маркера === END FILE ===.
"""
import re

# Открывающий маркер: === FILE: <путь> ===
FILE_OPEN = re.compile(r'^===\s*FILE:\s*(.+?)\s*===\s*$', re.MULTILINE)
# Закрывающий маркер файла
FILE_CLOSE = '=== END FILE ==='
# Терминальный маркер всего ответа (используется как stop_marker в многофайловом режиме)
RESPONSE_END = '=== END RESPONSE ==='


def parse_file_blocks(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Парсит вывод модели в формате FILE_BLOCKS.

    Возвращает (files, incomplete):
      files      — {path: content} для блоков (полных и частичных);
      incomplete — список путей блоков БЕЗ закрывающего маркера === END FILE ===
                   (обрезаны — нужен дозапрос продолжения).

    Частичный (обрезанный) блок всё равно попадает в files — чтобы вызывающий код
    мог сохранить накопленное и продолжить генерацию.
    """
    files: dict[str, str] = {}
    incomplete: list[str] = []
    opens = list(FILE_OPEN.finditer(text))
    for i, m in enumerate(opens):
        path = m.group(1).strip().lstrip('/')
        body_start = m.end()
        body_end = opens[i + 1].start() if i + 1 < len(opens) else len(text)
        body = text[body_start:body_end]
        # Отрезаем терминальный маркер ответа, если он попал в хвост последнего блока
        if RESPONSE_END in body:
            body = body.split(RESPONSE_END)[0]
        if FILE_CLOSE in body:
            content = body.split(FILE_CLOSE)[0]
            files[path] = _normalize(content)
        else:
            incomplete.append(path)
            files[path] = _normalize(body)
    return files, incomplete


def _normalize(content: str) -> str:
    """Убирает обрамляющие пустые строки и случайные markdown-fences вокруг кода."""
    content = content.strip('\n')
    # Случай, когда модель всё же обернула содержимое в ```lang ... ```
    content = re.sub(r'^```[\w]*\n', '', content)
    content = re.sub(r'\n```\s*$', '', content)
    return content.rstrip() + '\n'
```

#### Новый файл `src/studio/validators.py` (полный код)

> ВАЖНО: в `STUDIO_V3_PLAN.md` есть две версии `is_structurally_complete` — одна с JSX-проверкой (§3.4), другая без (§2 в постановке). Ниже — **единая самодостаточная версия**: все вызываемые хелперы (`_strip_strings_and_comments`, `_jsx_tags_balanced`) определены прямо здесь. Ничего «дописать самому» не нужно. Помни оговорку плана §3.4: **жёсткий критерий обрезки — только отсутствие end-маркера** (его проверяет gate в Коммите 3 через `incomplete` из `parse_file_blocks`). Дисбаланс скобок/JSX из `is_structurally_complete` — **advisory-сигнал** (эвристика, ломается на дженериках/template-литералах), а финальный судья синтаксиса — реальный build check.

```python
"""
Детерминированные валидаторы (без LLM, без сети). Запускаются синхронно
внутри coder_iteration ДО guardian_review. Мгновенны, не стоят звёзд.

Два валидатора:
  is_structurally_complete(path, content) — структурная целостность одного файла.
  validate_dependencies(files)            — сверка bare-импортов с package.json.
"""
import re
import json


# ---------- StructureValidator ----------

def _strip_strings_and_comments(s: str) -> str:
    """
    Грубо вырезает строковые литералы и комментарии, чтобы скобки внутри строк
    ("}", "// (") не считались при балансе. Это эвристика, не полноценный лексер.
    """
    # Блочные комментарии /* ... */
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
    # Строчные комментарии // ... до конца строки
    s = re.sub(r'//[^\n]*', '', s)
    # Строки в одинарных, двойных и обратных кавычках (template literals)
    s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
    s = re.sub(r"'(?:\\.|[^'\\])*'", "''", s)
    s = re.sub(r'`(?:\\.|[^`\\])*`', '``', s, flags=re.DOTALL)
    return s


def _jsx_tags_balanced(s: str) -> bool:
    """
    Очень грубая проверка баланса JSX/HTML-тегов. Самозакрывающиеся (<br/>),
    фрагменты (<>...</>) и void-элементы учитываются приблизительно. Это
    advisory-эвристика: при сомнении возвращаем True (не блокируем ложно).
    """
    opens = re.findall(r'<([A-Za-z][A-Za-z0-9.]*)(?:\s[^<>]*?)?(?<!/)>', s)
    closes = re.findall(r'</([A-Za-z][A-Za-z0-9.]*)\s*>', s)
    # Если закрывающих больше, чем открывающих — точно что-то не так.
    if len(closes) > len(opens):
        return False
    # Иначе доверяем (открытых может быть больше из-за самозакрывающихся,
    # которые наш regex не всегда ловит) — не блокируем.
    return True


def is_structurally_complete(path: str, content: str) -> tuple[bool, str]:
    """
    Проверяет структурную целостность файла.
    Возвращает (ok, reason). reason пустой при ok=True.

    ПРЕДУПРЕЖДЕНИЕ: для .ts/.tsx подсчёт скобок остаётся эвристикой
    (дженерики Array<{x}>, template ${...}, regex). Поэтому в pipeline (Коммит 3)
    единственный ЖЁСТКИЙ критерий обрезки — отсутствие end-маркера (из incomplete),
    а результат is_structurally_complete используется как advisory-подсказка
    в дозапрос. Подлинные синтаксические ошибки ловит build check.
    """
    s = content.rstrip()
    if not s:
        return False, 'empty'

    # 1. JSON — реальный парс (это надёжно, не эвристика)
    if path.endswith('.json'):
        try:
            json.loads(s)
        except Exception as e:
            return False, f'invalid JSON: {e}'
        return True, ''

    # 2. Последний значимый символ — мягкий признак обрыва на середине statement
    if s[-1] not in '}>);\'"`]':
        return False, 'ends mid-statement'

    # 3. Баланс парных символов (по очищенному от строк/комментов тексту)
    stripped = _strip_strings_and_comments(s)
    for open_c, close_c in [('{', '}'), ('(', ')'), ('[', ']')]:
        if stripped.count(open_c) != stripped.count(close_c):
            return False, f'unbalanced {open_c}{close_c}'

    # 4. JSX/TSX: грубый баланс тегов
    if path.endswith(('.tsx', '.jsx')):
        if not _jsx_tags_balanced(s):
            return False, 'unclosed JSX tag'

    return True, ''


# ---------- DependencyValidator ----------

# bare-import: import x from 'pkg'  /  require('pkg')  /  from 'pkg'
# Игнорируем относительные './', '../' и абсолютные '/'.
IMPORT_RE = re.compile(
    r"""(?:import\b[^'"]*?from\s*|import\s*|require\(\s*|from\s*)['"]([^'".][^'"]*)['"]"""
)


def validate_dependencies(files: dict[str, str]) -> dict:
    """
    Сверяет bare-импорты в .ts/.tsx/.js/.jsx с dependencies+devDependencies
    в package.json.

    Возвращает:
      {'ok': True, 'missing': []}                 — всё объявлено;
      {'ok': False, 'missing': ['lucide-react']}  — есть необъявленные;
      {'ok': False, 'reason': '...'}              — package.json не парсится.
    """
    pkg_raw = files.get('package.json')
    if pkg_raw is None:
        # Нет package.json среди переданных файлов — нечего сверять, не блокируем.
        return {'ok': True, 'missing': []}
    try:
        pkg = json.loads(pkg_raw)
    except Exception:
        return {'ok': False, 'reason': 'package.json не парсится'}

    declared = set(pkg.get('dependencies', {})) | set(pkg.get('devDependencies', {}))
    used: set[str] = set()
    for path, content in files.items():
        if not path.endswith(('.ts', '.tsx', '.js', '.jsx', '.mjs')):
            continue
        for imp in IMPORT_RE.findall(content):
            if imp.startswith('@'):  # scoped: @scope/pkg
                pkg_name = '/'.join(imp.split('/')[:2])
            else:
                pkg_name = imp.split('/')[0]
            used.add(pkg_name)

    # Отбрасываем относительные и node:-встроенные
    missing = {
        m for m in (used - declared)
        if not m.startswith(('node:', '.', '/'))
        and m not in ('fs', 'path', 'os', 'crypto', 'http', 'https', 'url', 'util', 'stream')
    }
    return {'ok': not missing, 'missing': sorted(missing)}
```

#### Изменение `src/config/settings.py`

Найти блок (строки ~301-313):
```python
STUDIO_STEP_STALL_SEC = int(os.getenv('STUDIO_STEP_STALL_SEC', '240'))
STUDIO_PIPELINE_MAX_SEC = int(os.getenv('STUDIO_PIPELINE_MAX_SEC', '2700'))
```

Добавить **после** последней строки:
```python
STUDIO_STEP_STALL_SEC = int(os.getenv('STUDIO_STEP_STALL_SEC', '240'))
STUDIO_PIPELINE_MAX_SEC = int(os.getenv('STUDIO_PIPELINE_MAX_SEC', '2700'))
STUDIO_V3 = os.getenv('STUDIO_V3', '0') == '1'  # Studio V3 pipeline (FILE_BLOCKS, validators, EDIT blocks)
```

#### Изменение `src/studio/tests.py`

Добавить в конец файла (импорт `SimpleTestCase` — тесты не трогают БД и не требуют сервера):

```python
from django.test import SimpleTestCase
from studio.agents.blocks import parse_file_blocks
from studio.validators import is_structurally_complete, validate_dependencies


class FileBlocksParserTests(SimpleTestCase):
    def test_single_complete_block(self):
        text = (
            "=== FILE: src/App.tsx ===\n"
            "export default function App() { return <div/> }\n"
            "=== END FILE ===\n"
            "=== END RESPONSE ==="
        )
        files, incomplete = parse_file_blocks(text)
        self.assertIn('src/App.tsx', files)
        self.assertEqual(incomplete, [])
        self.assertIn('export default', files['src/App.tsx'])

    def test_truncated_block_goes_to_incomplete(self):
        text = (
            "=== FILE: src/App.tsx ===\n"
            "export default function App() { return (\n"
            "  <div>\n"  # обрыв — нет === END FILE ===
        )
        files, incomplete = parse_file_blocks(text)
        self.assertEqual(incomplete, ['src/App.tsx'])
        self.assertIn('src/App.tsx', files)  # частичное содержимое сохранено

    def test_multiple_blocks(self):
        text = (
            "=== FILE: a.ts ===\nexport const a = 1\n=== END FILE ===\n"
            "=== FILE: b.ts ===\nexport const b = 2\n=== END FILE ===\n"
            "=== END RESPONSE ==="
        )
        files, incomplete = parse_file_blocks(text)
        self.assertEqual(set(files), {'a.ts', 'b.ts'})
        self.assertEqual(incomplete, [])

    def test_strips_leading_slash(self):
        text = "=== FILE: /src/x.ts ===\nexport const x = 1\n=== END FILE ==="
        files, _ = parse_file_blocks(text)
        self.assertIn('src/x.ts', files)


class StructureValidatorTests(SimpleTestCase):
    def test_valid_tsx(self):
        ok, _ = is_structurally_complete(
            'src/App.tsx', 'export default function A() { return <div>hi</div> }\n')
        self.assertTrue(ok)

    def test_empty_fails(self):
        ok, reason = is_structurally_complete('x.ts', '   \n')
        self.assertFalse(ok)
        self.assertEqual(reason, 'empty')

    def test_invalid_json_fails(self):
        ok, reason = is_structurally_complete('package.json', '{"a": 1,')
        self.assertFalse(ok)
        self.assertIn('invalid JSON', reason)

    def test_valid_json_ok(self):
        ok, _ = is_structurally_complete('package.json', '{"name": "app"}')
        self.assertTrue(ok)

    def test_unbalanced_braces_fails(self):
        ok, reason = is_structurally_complete('x.ts', 'function f() { return 1;')
        self.assertFalse(ok)


class DependencyValidatorTests(SimpleTestCase):
    def test_missing_dependency_detected(self):
        files = {
            'package.json': '{"dependencies": {"react": "18"}}',
            'src/App.tsx': "import { Menu } from 'lucide-react'\nimport React from 'react'\n",
        }
        result = validate_dependencies(files)
        self.assertFalse(result['ok'])
        self.assertIn('lucide-react', result['missing'])

    def test_all_declared_ok(self):
        files = {
            'package.json': '{"dependencies": {"react": "18", "lucide-react": "0.4"}}',
            'src/App.tsx': "import { Menu } from 'lucide-react'\nimport React from 'react'\n",
        }
        result = validate_dependencies(files)
        self.assertTrue(result['ok'])

    def test_relative_imports_ignored(self):
        files = {
            'package.json': '{"dependencies": {}}',
            'src/App.tsx': "import { x } from './utils'\nimport { y } from '../lib/z'\n",
        }
        result = validate_dependencies(files)
        self.assertTrue(result['ok'])

    def test_scoped_package(self):
        files = {
            'package.json': '{"dependencies": {}}',
            'src/App.tsx': "import x from '@tanstack/react-query'\n",
        }
        result = validate_dependencies(files)
        self.assertIn('@tanstack/react-query', result['missing'])

    def test_bad_package_json(self):
        files = {'package.json': 'not json', 'src/App.tsx': "import x from 'react'"}
        result = validate_dependencies(files)
        self.assertFalse(result['ok'])
        self.assertIn('reason', result)
```

### Тест-критерии
```bash
cd src
python manage.py test studio.tests.FileBlocksParserTests studio.tests.StructureValidatorTests studio.tests.DependencyValidatorTests
```
Все тесты должны пройти. Сервер/Docker/sandbox не нужны (это `SimpleTestCase`).

Дополнительно: проверить, что `from studio.agents.blocks import parse_file_blocks` и `from studio.validators import validate_dependencies` импортируются без ошибок (`python -c` или внутри shell).

### На что обратить внимание
- **Инвариант флага:** `STUDIO_V3=False` по умолчанию. Этот коммит вообще не меняет поведение pipeline — модули не вызываются нигде. Безопасен всегда.
- `validators.py` лежит в `src/studio/` (НЕ в `agents/`) — так указано в плане (Приложение A). `blocks.py` — в `src/studio/agents/`.
- `_jsx_tags_balanced` намеренно консервативен (при сомнении True) — чтобы не плодить ложные fail. Не «улучшай» его до строгого, иначе словишь ложные срабатывания на дженериках.
- IMPORT_RE должен ловить `import X from 'pkg'`, `import 'pkg'`, `require('pkg')`. Проверь это тестом `test_missing_dependency_detected`.

---

## Коммит 2: Coder на FILE_BLOCKS (под флагом STUDIO_V3; legacy сохранён)

### Заголовок коммита
```
studio v3: coder generates FILE_BLOCKS per file when STUDIO_V3 is on
```

### Цель
Сделать FILE_BLOCKS основным путём генерации **под флагом** `STUDIO_V3`. При `STUDIO_V3=False` — старый путь (`_run_legacy` JSON) полностью сохраняется. `_run_legacy` НЕ удаляется (см. раздел «Разрешение противоречия» выше).

### Затронутые файлы
- `src/studio/agents/coder.py`

### Детальные изменения

#### 1. Добавить новые промпты FILE_BLOCKS

В начало `coder.py` (после существующих `FILE_SYSTEM_RU/EN`) добавить:

```python
CODER_FILE_BLOCKS_RU = (
    "Ты senior-разработчик. Напиши ОДИН полный файл в формате FILE_BLOCKS.\n\n"
    "ФОРМАТ ВЫВОДА СТРОГО:\n"
    "=== FILE: <путь> ===\n"
    "<полное содержимое файла>\n"
    "=== END FILE ===\n\n"
    "Маркер === END FILE === ОБЯЗАТЕЛЕН в конце — это сигнал завершения файла.\n"
    "НЕ используй JSON. НЕ оборачивай код в markdown-fences (```).\n\n"
    "ТРЕБОВАНИЯ:\n"
    "- Файл 100% полный и production-ready: все JSX-теги закрыты, все функции закрыты, export присутствует.\n"
    "- НЕ обрезай. НЕ пиши TODO, заглушки или placeholder-комментарии.\n"
    "- Реализуй ВСЕ элементы UI: навигацию, кнопки, иконки, стили.\n"
    "- Обработай состояния: loading, empty, error.\n"
    "- Next.js: 'use client' там где нужно; dev-скрипт: \"next dev -p 3000 -H 0.0.0.0\".\n"
    "- Vite/React: vite.config.ts с server:{host:true,port:3000,hmr:false}.\n"
    "Комментарии в коде можно на русском."
)
CODER_FILE_BLOCKS_EN = (
    "You are a senior software engineer. Write ONE complete source file in FILE_BLOCKS format.\n\n"
    "OUTPUT FORMAT STRICTLY:\n"
    "=== FILE: <path> ===\n"
    "<full file content>\n"
    "=== END FILE ===\n\n"
    "The marker === END FILE === is MANDATORY at the end — it signals completion.\n"
    "Do NOT use JSON. Do NOT wrap the code in markdown fences (```).\n\n"
    "REQUIREMENTS:\n"
    "- 100% complete, production-ready: ALL JSX tags closed, ALL functions closed, export present.\n"
    "- NEVER truncate. NO TODO comments, stubs or placeholders.\n"
    "- Implement ALL UI elements: navigation, buttons, icons, styles.\n"
    "- Handle states: loading, empty, error.\n"
    "- Next.js: add 'use client' where needed; dev script \"next dev -p 3000 -H 0.0.0.0\".\n"
    "- Vite/React: vite.config.ts with server:{host:true,port:3000,hmr:false}.\n"
    "Code comments may be in Russian."
)
```

#### 2. Импорт парсера

В шапку `coder.py`:
```python
from django.conf import settings
from .blocks import parse_file_blocks, FILE_CLOSE
```

#### 3. Изменить `_generate_one_file` — раздвоить по флагу

Старый метод заканчивается так:
```python
        raw = self.run_prompt_with_continuation(
            system, user, model=model, max_tokens=24000, temperature=0.15,
        )
        return _strip_fences(raw)
```

Новая версия метода (полностью заменить тело `_generate_one_file`):

```python
    def _generate_one_file(self, path, step_index, step_text, existing_files, model) -> str:
        existing_content = existing_files.get(path, '')
        if existing_content:
            from .blocks import FILE_CLOSE  # local import safe
            if _is_truncated(existing_content):
                existing_str = (
                    f"\n\nIMPORTANT: {path} currently exists but is TRUNCATED/INCOMPLETE. "
                    "Write it COMPLETELY from scratch — do NOT continue or patch the existing content."
                )
            else:
                existing_str = (
                    f"\n\nCurrent content of {path} (modify/replace as needed):\n"
                    f"```\n{existing_content[:6000]}\n```"
                )
        else:
            existing_str = ''
        context = _select_context_files(
            step_text, {k: v for k, v in existing_files.items() if k != path}, max_files=8
        )
        context_str = '\n'.join(
            f'### {p}\n```\n{c[:3000]}\n```' for p, c in context.items()
        )
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'

        if settings.STUDIO_V3:
            system = pick_prompt(CODER_FILE_BLOCKS_RU, CODER_FILE_BLOCKS_EN)
            user = (
                f"PROJECT.md:\n{self.project.project_md_content[:4000]}\n\n"
                f"Step #{step_index}:\n{step_text}\n\n"
                f"FILE TO WRITE: {path}{existing_str}\n\n"
                f"All project files (for reference):\n{listing}\n\n"
                f"Relevant file contents:\n{context_str}\n\n"
                f"Output the file wrapped in:\n=== FILE: {path} ===\n...\n=== END FILE ==="
            )
            raw = self.run_prompt_with_continuation(
                system, user, model=model, max_tokens=24000, temperature=0.15,
                stop_marker=FILE_CLOSE,
            )
            files, incomplete = parse_file_blocks(raw)
            # per-file: ожидаем ровно один блок; берём по точному пути или единственный
            content = files.get(path)
            if content is None and len(files) == 1:
                content = next(iter(files.values()))
            if content is None:
                # модель проигнорировала формат — fallback на голый текст
                self.log(f'FILE_BLOCKS не распарсился для {path}, fallback на сырой текст', level='warning')
                content = _strip_fences(raw)
            if path in incomplete or (len(files) == 1 and incomplete):
                self.log(f'{path}: блок обрезан (нет END-маркера) даже после дозапросов', level='warning')
            return content

        # --- legacy путь (STUDIO_V3=False): голый текст ---
        system = pick_prompt(FILE_SYSTEM_RU, FILE_SYSTEM_EN)
        user = (
            f"PROJECT.md:\n{self.project.project_md_content[:4000]}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"FILE TO WRITE: {path}{existing_str}\n\n"
            f"All project files (for reference):\n{listing}\n\n"
            f"Relevant file contents:\n{context_str}"
        )
        raw = self.run_prompt_with_continuation(
            system, user, model=model, max_tokens=24000, temperature=0.15,
        )
        return _strip_fences(raw)
```

#### 4. Изменить `run()` — при `STUDIO_V3` использовать per-file как основной путь

Старый `run()` начинается с проверки `allowed_files`, иначе зовёт `_run_legacy`. Заменить тело `run()`:

```python
    def run(self, step_index, step_text, existing_files, allowed_files=None) -> dict:
        model = self._pick_model(step_text)
        self.last_model = model
        self.log(f'Модель: {model}')

        # Fix-итерация (allowed_files задан) — всегда per-file, в обоих режимах
        if allowed_files:
            self.log(f'Исправляю {len(allowed_files)} файлов: {", ".join(allowed_files)}')
            results = self._generate_files(allowed_files, step_index, step_text, existing_files, model)
            if not results and not settings.STUDIO_V3:
                self.log('Per-file генерация ничего не вернула — пробую одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            return results

        if settings.STUDIO_V3:
            # V3 основной путь: манифест файлов → per-file FILE_BLOCKS
            self.log('V3: получаю список файлов шага...')
            file_list = self._get_manifest(step_index, step_text, existing_files, model)
            if not file_list:
                self.log('Манифест пустой — fallback на одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            results = self._generate_files(file_list, step_index, step_text, existing_files, model)
            if not results:
                self.log('Per-file ничего не вернула — fallback на одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            return results

        # --- legacy путь (STUDIO_V3=False), идентичен прежнему поведению ---
        self.log('Генерирую все файлы одним запросом...')
        try:
            results = self._run_legacy(step_index, step_text, existing_files, model)
            if results:
                return results
        except Exception as exc:
            self.log(f'Одиночный запрос не удался ({exc}) — получаю список файлов', level='warning')
        file_list = self._get_manifest(step_index, step_text, existing_files, model)
        if not file_list:
            self.log('Манифест пустой — повторяю одиночный запрос', level='warning')
            return self._run_legacy(step_index, step_text, existing_files, model)
        results = self._generate_files(file_list, step_index, step_text, existing_files, model)
        if not results:
            self.log('Per-file генерация ничего не вернула — повторяю одиночный запрос', level='warning')
            return self._run_legacy(step_index, step_text, existing_files, model)
        return results
```

> Примечание: даже под V3 `_run_legacy` остаётся доступен как аварийный fallback (если манифест пуст). Это нормально — это резерв, а не основной путь.

### Тест-критерии
- `STUDIO_V3=0` (по умолчанию): запустить `python manage.py test studio` — все существующие тесты проходят. Поведение `run()` идентично прежнему (`_run_legacy` JSON-путь основной).
- Юнит-проверка парсинга в `_generate_one_file` (можно добавить мок-тест): замокать `run_prompt_with_continuation`, чтобы вернул FILE_BLOCKS строку, проверить, что `run()` под `STUDIO_V3=True` извлёк правильный content.
- Статически прочитать диф: убедиться, что ветка `else` (legacy) текстуально совпадает с прежним кодом.

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` метод `run()` и `_generate_one_file()` должны вести себя точно как раньше. Перепроверь, что legacy-ветки скопированы дословно.
- `stop_marker=FILE_CLOSE` (`'=== END FILE ==='`) корректен **только в per-file** (один блок). Не используй его в многофайловом режиме (там нужен `RESPONSE_END`) — но многофайловый режим в этих коммитах не вводится, основной путь V3 = per-file.
- Не удаляй `_run_legacy`, `_is_truncated`, `FILE_SYSTEM_*`, `SYSTEM_*` — они нужны для legacy-ветки и fallback.
- `_get_manifest` уже существует и используется — переиспользуй, не дублируй.

---

## Коммит 3: Структурный + dependency gate перед guardian_review

### Заголовок коммита
```
studio v3: structure & dependency gate before guardian (re-request truncated files)
```

### Цель
Врезать два синхронных детерминированных gate в `coder_iteration` ПОСЛЕ генерации и ДО `guardian_review.delay(...)`, под флагом `STUDIO_V3`. Gate ловит обрезанные файлы (по отсутствию end-маркера через повторную генерацию) и недостающие зависимости. Всё синхронно, без новых Celery-тасок.

### Затронутые файлы
- `src/studio/tasks.py`

### Детальные изменения

В `tasks.py:coder_iteration` (строки ~339-382) есть блок:
```python
        agent = CoderAgent(project)
        files = agent.run(step_index, step_text, existing, allowed_files=allowed_files)
        coder_tier = coder_tier_for_model(agent.last_model)
```
... далее идёт same-diff detection и запись файлов ...
```python
        for path, content in files.items():
            StudioFile.objects.update_or_create(...)
        ...
        if project.sandbox_container_id:
            sandbox.write_files(project.sandbox_container_id, files)
            sandbox.wait_for_ready(project.sandbox_container_id, timeout=60)
        guardian_review.delay(project_id, step_index)
        _billing_charge(project, 'coder', step_index, tier_override=coder_tier)
```

**Вставить gate ПОСЛЕ `agent.run(...)` и ДО записи в StudioFile** (сразу после строки `coder_tier = coder_tier_for_model(agent.last_model)`):

```python
        # ===== V3: детерминированные gate перед guardian =====
        if settings.STUDIO_V3 and files:
            files = _structure_gate(project, project_id, step_index, step_text, existing, files, agent, model_tier=coder_tier)
            files = _dependency_gate(project, project_id, files)
        # =====================================================
```

И добавить две модульные функции в `tasks.py` (рядом с `_existing_files`, выше `coder_iteration`):

```python
def _structure_gate(project, project_id, step_index, step_text, existing, files, agent, model_tier=None, max_fixes=2):
    """
    Детерминированный structure gate. ЖЁСТКИЙ критерий — обрезка (нет end-маркера):
    его сигналит coder через лог, но здесь мы дополнительно проверяем целостность
    через is_structurally_complete и точечно дозапрашиваем сломанные файлы.
    Advisory-дисбаланс скобок НЕ гонит на бесконечную перегенерацию (max_fixes).
    """
    from .validators import is_structurally_complete
    from .agents.coder import CoderAgent
    broken = {}
    for path, content in files.items():
        ok, reason = is_structurally_complete(path, content)
        if not ok:
            broken[path] = reason
    if not broken:
        return files
    publish_event(project_id, {
        'agent': 'system', 'level': 'warning',
        'text': f'Структурная проверка: {len(broken)} файл(ов) требуют дозапроса',
    })
    fixed = dict(files)
    for path, reason in list(broken.items())[:8]:
        for attempt in range(max_fixes):
            hint = (
                f"\n\nФАЙЛ {path} структурно неполон (причина: {reason}). "
                "Сгенерируй его ПОЛНОСТЬЮ заново, со всеми закрытыми скобками и тегами."
            )
            try:
                regen = agent.run(step_index, step_text + hint, existing, allowed_files=[path])
            except Exception as exc:
                publish_event(project_id, {'agent': 'system', 'level': 'warning',
                                           'text': f'Дозапрос {path} упал: {exc}'})
                break
            new_content = regen.get(path)
            if not new_content:
                break
            ok, reason = is_structurally_complete(path, new_content)
            fixed[path] = new_content
            if ok:
                break
    return fixed


# Минимальный whitelist версий для авто-добавления недостающих пакетов.
DEP_VERSIONS = {
    'lucide-react': '^0.460.0',
    'clsx': '^2.1.1',
    'tailwind-merge': '^2.5.4',
    'recharts': '^2.13.0',
    'date-fns': '^4.1.0',
    'zustand': '^5.0.0',
    '@tanstack/react-query': '^5.59.0',
    'react-router-dom': '^6.27.0',
    'framer-motion': '^11.11.0',
}


def _dependency_gate(project, project_id, files):
    """
    Детерминированно сверяет импорты с package.json. Недостающие пакеты с известной
    версией добавляются автоматически; остальные логируются (Guardian/build их поймает).
    """
    import json as _json
    from .validators import validate_dependencies
    # Сверяем по полному набору файлов проекта (существующие + новые), чтобы видеть весь импорт-граф
    all_files = {f.path: f.content for f in project.files.all()}
    all_files.update(files)
    result = validate_dependencies(all_files)
    if result.get('ok'):
        return files
    missing = result.get('missing', [])
    if not missing:
        return files
    pkg_content = files.get('package.json') or all_files.get('package.json')
    addable = [m for m in missing if m in DEP_VERSIONS]
    if pkg_content and addable:
        try:
            pkg = _json.loads(pkg_content)
            deps = pkg.setdefault('dependencies', {})
            for m in addable:
                deps[m] = DEP_VERSIONS[m]
            files = dict(files)
            files['package.json'] = _json.dumps(pkg, indent=2, ensure_ascii=False) + '\n'
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': f'Добавлены зависимости: {", ".join(addable)}',
            })
        except Exception:
            pass
    unknown = [m for m in missing if m not in DEP_VERSIONS]
    if unknown:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'Неизвестные зависимости (проверит сборка): {", ".join(unknown)}',
        })
    return files
```

> ВАЖНО: `from django.conf import settings` уже импортирован в `tasks.py` (строка 4). `publish_event` тоже. Дополнительные импорты — локальные внутри функций.

### Тест-критерии
- `STUDIO_V3=0`: gate не вызывается (условие `if settings.STUDIO_V3`), pipeline идентичен прежнему.
- Юнит-тест `_dependency_gate` (можно как `SimpleTestCase` с фейковым project-like объектом или мок `project.files.all()`): передать файлы с `import 'lucide-react'` без него в package.json → проверить, что `lucide-react` добавлен в результат.
- Юнит-тест `_structure_gate`: замокать `agent.run`, чтобы вернул валидный файл на втором заходе; передать обрезанный → проверить, что результат починен (или хотя бы дозапрос вызван).

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` ни одна из новых функций не вызывается. `coder_iteration` идентичен прежнему.
- Gate вставлен **до** записи в `StudioFile` и до `sandbox.write_files` — чтобы в sandbox и БД попадали уже починенные файлы.
- `agent.run(..., allowed_files=[path])` переиспользует per-file путь coder — НЕ пиши отдельную генерацию.
- `max_fixes=2` ограничивает дозапросы — защита от бесконечного цикла на ложном advisory-дисбалансе (дженерики). Финальный судья — build check в Guardian.
- Same-diff detection (хэш файлов) идёт ПОСЛЕ gate в существующем коде — это нормально, хэш считается от уже починенных файлов.

---

## Коммит 4: Architect DESIGN.md + новый COMMITS-формат + миграция

### Заголовок коммита
```
studio v3: architect emits DESIGN.md and structured COMMITS plan; add design_md_content field
```

### Цель
Добавить третий артефакт архитектора — DESIGN.md (дизайн-система). Новый формат COMMITS.md с манифестом файлов и лимитами строк. Парсинг шагов в `interview_data['plan']` (JSON). Новое поле модели + миграция.

### Затронутые файлы
- `src/studio/models.py` — новое поле
- `src/studio/migrations/0013_studioproject_design_md_content.py` — **создать**
- `src/studio/agents/architect.py` — DESIGN.md + новый COMMITS + парсер
- `src/studio/tasks.py:agent_analyze` — сохранять design_md и plan

### Детальные изменения

#### 1. `src/studio/models.py` — добавить поле

После строки `commits_md_content = models.TextField(blank=True)` (строка 36):
```python
    commits_md_content = models.TextField(blank=True)
    design_md_content = models.TextField(blank=True)  # V3: дизайн-система проекта
```

#### 2. Миграция `src/studio/migrations/0013_studioproject_design_md_content.py`

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0012_agent_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='design_md_content',
            field=models.TextField(blank=True, default=''),
        ),
    ]
```

> Проверка: последняя существующая миграция — `0012_agent_models`. Зависимость указана верно. Если в проекте появились новые миграции — обнови `dependencies` на актуальную последнюю.

#### 3. `src/studio/agents/architect.py` — новые промпты + DESIGN + парсер

Добавить промпты (после существующих `SYSTEM_COMMITS_*`):

```python
ARCHITECT_DESIGN_RU = (
    "Ты ведущий продуктовый дизайнер. Напиши DESIGN.md — дизайн-систему проекта.\n"
    "Ориентир: Linear, Vercel, Stripe — строгий минимализм, профессионально.\n"
    "Включи разделы: Дизайн-направление; Цветовая палитра (CSS-переменные, тёмная+светлая тема);\n"
    "Типографика (шрифт Inter, размеры, веса); Компоненты по умолчанию (кнопки, карточки,\n"
    "инпуты — с КОНКРЕТНЫМИ Tailwind-классами); Сетка и отступы; Иконки (только lucide-react,\n"
    "без эмодзи); Состояния (loading/empty/error).\n"
    "Давай КОНКРЕТНЫЕ значения (#hex, rounded-lg, h-10), не общие слова.\n"
    "Выводи ТОЛЬКО markdown. На русском. Без JSON, без code-fences вокруг всего документа."
)
ARCHITECT_DESIGN_EN = (
    "You are a lead product designer. Write DESIGN.md — the project's design system.\n"
    "Reference: Linear, Vercel, Stripe — strict minimalism, professional.\n"
    "Include sections: Design direction; Color palette (CSS variables, dark+light);\n"
    "Typography (Inter font, sizes, weights); Default components (buttons, cards, inputs —\n"
    "with CONCRETE Tailwind classes); Grid & spacing; Icons (lucide-react only, no emoji);\n"
    "States (loading/empty/error).\n"
    "Give CONCRETE values (#hex, rounded-lg, h-10), not vague words.\n"
    "Output ONLY markdown. Write content in Russian. No JSON, no outer code fences."
)

ARCHITECT_COMMITS_V3_RU = (
    "Ты ведущий архитектор. Составь пошаговый план COMMITS.md.\n\n"
    "ЖЁСТКИЕ ПРАВИЛА ДЕКОМПОЗИЦИИ:\n"
    "- Каждый файл <= 200 строк. Если выйдет больше — РАЗБЕЙ на несколько файлов.\n"
    "- <= 5 файлов на шаг. Файлы шага логически связаны (один экран/фича).\n"
    "- Один компонент = один файл. Логика (хуки/утилиты/типы) отдельно от UI.\n"
    "- Моки и данные — в lib/data.ts, не внутри компонента.\n"
    "- 6-14 шагов. Шаг 1: package.json + конфиги + точка входа + UI-примитивы (ui/).\n"
    "- Для Vite: vite.config.ts с server:{host:true,port:3000,hmr:false}.\n"
    "- Для Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'.\n"
    "- Архитектурно сложные шаги помечай [COMPLEX] в заголовке.\n\n"
    "ФОРМАТ КАЖДОГО ШАГА СТРОГО:\n"
    "## Шаг N: Название\n"
    "Описание что реализовать.\n"
    "FILES:\n"
    "- путь/файл.tsx | <=120 | роль файла\n"
    "- путь/файл2.ts | <=60 | роль файла\n\n"
    "Выводи ТОЛЬКО markdown. Без JSON, без code-fences."
)
ARCHITECT_COMMITS_V3_EN = (
    "You are a lead architect. Write a COMMITS.md implementation plan.\n\n"
    "STRICT DECOMPOSITION RULES:\n"
    "- Each file <= 200 lines. If it would be larger — SPLIT into several files.\n"
    "- <= 5 files per step. Files in a step are logically related (one screen/feature).\n"
    "- One component = one file. Logic (hooks/utils/types) separate from UI.\n"
    "- Mocks and data in lib/data.ts, not inside components.\n"
    "- 6-14 steps. Step 1: package.json + configs + entry point + UI primitives (ui/).\n"
    "- For Vite: vite.config.ts with server:{host:true,port:3000,hmr:false}.\n"
    "- For Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'.\n"
    "- Mark architecturally complex steps with [COMPLEX] in the title.\n\n"
    "EACH STEP FORMAT STRICTLY:\n"
    "## Шаг N: Title\n"
    "Description of what to implement.\n"
    "FILES:\n"
    "- path/file.tsx | <=120 | file role\n"
    "- path/file2.ts | <=60 | file role\n\n"
    "Write step titles/descriptions in Russian. Output ONLY markdown. No JSON, no code fences."
)
```

Заменить метод `run()` в `ArchitectAgent` (добавить DESIGN-вызов и парсер plan, под флагом):

```python
    def run(self, description: str, stack: str, features: list, answers: list) -> dict:
        from django.conf import settings as _s
        model = self.resolve_model()
        context = self._build_context(description, stack, features, answers)

        system_project = pick_prompt(SYSTEM_PROJECT_RU, SYSTEM_PROJECT_EN)
        project_md = self.run_prompt(
            system_project, context, model=model, max_tokens=4096, temperature=0.3,
        )

        design_md = ''
        if _s.STUDIO_V3:
            system_design = pick_prompt(ARCHITECT_DESIGN_RU, ARCHITECT_DESIGN_EN)
            design_md = self.run_prompt(
                system_design,
                context + f"\n\nPROJECT.md:\n{project_md[:2000]}",
                model=model, max_tokens=3000, temperature=0.4,
            )

        if _s.STUDIO_V3:
            system_commits = pick_prompt(ARCHITECT_COMMITS_V3_RU, ARCHITECT_COMMITS_V3_EN)
        else:
            system_commits = pick_prompt(SYSTEM_COMMITS_RU, SYSTEM_COMMITS_EN)
        commits_md = self.run_prompt(
            system_commits,
            context + f"\n\nPROJECT.md already written:\n{project_md[:2000]}",
            model=model, max_tokens=4096, temperature=0.3,
        )

        planned_steps = len(re.findall(r'^##\s+(?:Step|Шаг)\s+\d+', commits_md, re.MULTILINE))
        if not planned_steps:
            planned_steps = len(re.findall(r'^##\s+', commits_md, re.MULTILINE))
        if not planned_steps:
            planned_steps = 5

        result = {
            'project_md': project_md.strip(),
            'commits_md': commits_md.strip(),
            'planned_steps': planned_steps,
        }
        if _s.STUDIO_V3:
            result['design_md'] = design_md.strip()
            result['plan'] = self._parse_plan(commits_md)
        return result

    def _parse_plan(self, commits_md: str) -> list:
        """
        Парсит COMMITS.md в структурированный план:
        [{step, title, description, files:[{path, max_lines, role}]}, ...]
        Устойчив к отсутствию секции FILES: (тогда files=[]).
        """
        plan = []
        # делим по заголовкам шагов
        sections = re.split(r'\n(?=##\s+(?:Step|Шаг)\s+\d+)', commits_md or '')
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            title_m = re.match(r'##\s+(?:Step|Шаг)\s+(\d+)\s*:?\s*(.*)', sec)
            if not title_m:
                continue
            step_num = int(title_m.group(1))
            title = title_m.group(2).strip()
            files = []
            fm = re.search(r'FILES\s*:\s*\n(.*?)(?=\n##\s|\Z)', sec, re.DOTALL | re.IGNORECASE)
            if fm:
                for line in fm.group(1).splitlines():
                    line = re.sub(r'^[\s\-\*]+', '', line).strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split('|')]
                    path = parts[0].lstrip('/')
                    max_lines = 200
                    role = ''
                    if len(parts) >= 2:
                        ml = re.search(r'(\d+)', parts[1])
                        if ml:
                            max_lines = int(ml.group(1))
                    if len(parts) >= 3:
                        role = parts[2]
                    if path:
                        files.append({'path': path, 'max_lines': max_lines, 'role': role})
            # описание — текст между заголовком и FILES:
            desc_m = re.search(r'##[^\n]*\n(.*?)(?=\nFILES\s*:|\Z)', sec, re.DOTALL | re.IGNORECASE)
            description = desc_m.group(1).strip() if desc_m else ''
            plan.append({
                'step': step_num, 'title': title,
                'description': description, 'files': files,
            })
        return plan
```

#### 4. `src/studio/tasks.py:agent_analyze` — сохранять design_md и plan

В `agent_analyze` (строки ~132-137) после:
```python
        project.project_md_content = data.get('project_md', '')
        project.commits_md_content = data.get('commits_md', '')
```
добавить:
```python
        if settings.STUDIO_V3:
            project.design_md_content = data.get('design_md', '')
            if data.get('plan'):
                project.interview_data['plan'] = data['plan']
```
и в `project.save(update_fields=[...])` добавить `'design_md_content'`:
```python
        project.save(update_fields=['project_md_content', 'commits_md_content', 'design_md_content', 'interview_data', 'status'])
```

### Тест-критерии
- Создать и применить миграцию: `cd src && python manage.py makemigrations studio --check` (должна уже существовать), затем `python manage.py migrate studio` (на тестовой SQLite).
- Юнит-тест `_parse_plan`: подать markdown с двумя шагами и секциями FILES → проверить структуру (`step`, `title`, `files[].max_lines`).
- `STUDIO_V3=0`: `architect.run()` возвращает только `project_md/commits_md/planned_steps` (без `design_md`/`plan`), `agent_analyze` не трогает `design_md_content`. Существующие тесты проходят.

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` архитектор делает ровно 2 вызова (project + commits) старыми промптами, поля `design_md_content` и `plan` не заполняются. Поведение идентично.
- Поле модели добавляется всегда (даже при флаге off) — это безопасно, дефолт `''`. Миграцию накатить обязательно в обоих режимах.
- `_parse_plan` должен быть устойчив к мусору: если FILES: нет — `files=[]`, шаг всё равно в плане. Не падать на нестандартном выводе модели.
- `update_fields` ОБЯЗАТЕЛЬНО включить `design_md_content`, иначе поле не сохранится.

---

## Коммит 5: Coder и Guardian читают DESIGN.md и лимиты строк

### Заголовок коммита
```
studio v3: feed DESIGN.md and per-file line limits into coder and guardian
```

### Цель
Передавать выжимку DESIGN.md и лимит строк/роль целевого файла в промпты coder и guardian (под флагом). Дизайн становится единым ограничением на весь проект.

### Затронутые файлы
- `src/studio/agents/coder.py`
- `src/studio/agents/guardian.py`

### Детальные изменения

#### 1. `coder.py` — хелпер чтения лимита файла из plan + впрыск DESIGN

Добавить хелпер в `CoderAgent`:
```python
    def _file_spec(self, path):
        """Из interview_data['plan'] достаёт {max_lines, role} для файла, если есть."""
        plan = (self.project.interview_data or {}).get('plan', [])
        for step in plan:
            for f in step.get('files', []):
                if f.get('path') == path:
                    return f.get('max_lines', 200), f.get('role', '')
        return 200, ''

    def _design_excerpt(self) -> str:
        d = getattr(self.project, 'design_md_content', '') or ''
        return d[:2500]
```

В `_generate_one_file` (внутри ветки `if settings.STUDIO_V3:`) расширить user-промпт:
```python
            max_lines, role = self._file_spec(path)
            design = self._design_excerpt()
            design_block = f"\n\nDESIGN.md (соблюдай дизайн-систему):\n{design}" if design else ''
            limit_block = (
                f"\n\nЛИМИТ: файл должен быть <= {max_lines} строк. Роль файла: {role}"
                if role or max_lines else ''
            )
            user = (
                f"PROJECT.md:\n{self.project.project_md_content[:4000]}\n\n"
                f"Step #{step_index}:\n{step_text}{limit_block}\n\n"
                f"FILE TO WRITE: {path}{existing_str}{design_block}\n\n"
                f"All project files (for reference):\n{listing}\n\n"
                f"Relevant file contents:\n{context_str}\n\n"
                f"Output the file wrapped in:\n=== FILE: {path} ===\n...\n=== END FILE ==="
            )
```
(заменить прежний `user = (...)` в V3-ветке на этот расширенный вариант).

#### 2. `guardian.py` — добавить DESIGN в контекст и дизайн-чек в промпт

Добавить V3-промпт (после существующих `SYSTEM_RU/EN`):
```python
SYSTEM_V3_RU = (
    "Ты старший ревьюер. Структурная целостность (скобки, обрезка, импорты, сборка)\n"
    "УЖЕ проверена кодом ДО тебя — НЕ комментируй обрезку и баланс скобок.\n\n"
    "Проверь ТОЛЬКО:\n"
    "1. Реализован ли замысел шага (фичи на месте)?\n"
    "2. Соответствие DESIGN.md: токены вместо хардкод-цветов (#fff), lucide-иконки,\n"
    "   состояния loading/empty/error, отсутствие эмодзи?\n"
    "3. Логика: кнопки с обработчиками, формы с сабмитом, нет мёртвых ссылок?\n"
    "Если есть build-логи с ошибкой — учти их.\n\n"
    "Только реальные проблемы. Стиль = PASS.\n\n"
    "Ответь СТРОГО:\n"
    "VERDICT: pass\nили\nVERDICT: fix\n"
    "ISSUES:\n- проблема\n"
    "INSTRUCTIONS:\nКонкретные инструкции.\n"
    "FILES:\n- путь/к/файлу.ts"
)
SYSTEM_V3_EN = (
    "You are a senior reviewer. Structural integrity (braces, truncation, imports,\n"
    "build) is ALREADY checked by code BEFORE you — do NOT comment on truncation or braces.\n\n"
    "Check ONLY:\n"
    "1. Is the step's intent implemented (features present)?\n"
    "2. DESIGN.md compliance: design tokens instead of hardcoded colors, lucide icons,\n"
    "   loading/empty/error states, no emoji?\n"
    "3. Logic: buttons with handlers, forms with submit, no dead links?\n"
    "If build logs with errors are provided — account for them.\n\n"
    "Only real problems. Style = PASS.\n\n"
    "Respond STRICTLY:\n"
    "VERDICT: pass\nor\nVERDICT: fix\n"
    "ISSUES:\n- problem\n"
    "INSTRUCTIONS:\nConcrete fix instructions in Russian.\n"
    "FILES:\n- path/to/file.ts"
)
```

В `GuardianAgent.run` выбрать промпт и добавить DESIGN-блок:
```python
    def run(self, step_text: str, files: dict, build_logs: str = '', attempt: int = 0) -> dict:
        from django.conf import settings
        if settings.STUDIO_V3:
            system = pick_prompt(SYSTEM_V3_RU, SYSTEM_V3_EN)
            design = (getattr(self.project, 'design_md_content', '') or '')[:2000]
            design_section = f'\n\nDESIGN.md (проверь соответствие):\n{design}' if design else ''
        else:
            system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
            design_section = ''
        files_content = '\n'.join(
            f'### {path}\n```\n{content[:8000]}\n```'
            for path, content in list(files.items())[:10]
        )
        build_section = (f'\n\nBuild logs:\n```\n{build_logs[-2000:]}\n```' if build_logs else '')
        attempt_note = (f'\n\n(Fix attempt #{attempt}. Verify previous issues are resolved.)'
                        if attempt > 0 else '')
        user = (
            f'Planned step:\n{step_text}{design_section}\n\n'
            f'Implemented files:{attempt_note}\n{files_content}'
            f'{build_section}'
        )
        raw = self.run_prompt(system, user, model=self.resolve_model(), max_tokens=2048)
        return _parse_guardian_response(raw)
```

### Тест-критерии
- `STUDIO_V3=0`: guardian и coder используют старые промпты, DESIGN не впрыскивается. Существующие тесты проходят.
- `STUDIO_V3=1` с замоканной моделью: проверить, что user-промпт coder содержит `DESIGN.md` и `ЛИМИТ` когда `design_md_content`/`plan` заданы.
- `_parse_guardian_response` НЕ меняется в этом коммите — формат вывода тот же (VERDICT/ISSUES/INSTRUCTIONS/FILES). EDIT blocks добавляются в Коммите 6.

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` — старые промпты, нулевой DESIGN-блок. Поведение идентично.
- `getattr(self.project, 'design_md_content', '')` — через getattr для безопасности (поле есть после Коммита 4, но getattr страхует).
- Не превышай разумный размер промпта: DESIGN обрезается (`[:2500]` в coder, `[:2000]` в guardian).
- В этом коммите формат guardian-ответа НЕ трогаем — иначе сломаем `_parse_guardian_response`. EDIT — следующий коммит.

---

## Коммит 6: EDIT blocks — диффы вместо полной перегенерации

### Заголовок коммита
```
studio v3: guardian emits EDIT blocks, apply search/replace patches in fix branch
```

### Цель
Guardian при `STUDIO_V3` выдаёт точечные диффы (search/replace) в секции EDITS. Pipeline применяет их детерминированно через `apply_edits`. Полная перегенерация — только если SEARCH не найден / файл структурно мёртв / правок > 40%.

### Затронутые файлы
- `src/studio/agents/edits.py` — **создать**
- `src/studio/agents/guardian.py` — EDITS-секция в промпте + парсинг
- `src/studio/tasks.py` — EDIT-ветка в fix-логике
- `src/studio/tests.py` — тесты edits

### Детальные изменения

#### 1. Новый файл `src/studio/agents/edits.py` (полный код)

```python
"""
Парсер и применение EDIT blocks (search/replace патчи в стиле aider/Cline).

Формат:
    === EDIT: src/components/Header.tsx ===
    <<<<<<< SEARCH
    <точный текущий фрагмент>
    =======
    <новый фрагмент>
    >>>>>>> REPLACE
    === END EDIT ===
"""
import re

EDIT_OPEN = re.compile(r'^===\s*EDIT:\s*(.+?)\s*===\s*$', re.MULTILINE)
EDIT_CLOSE = '=== END EDIT ==='
_SEARCH_REPLACE = re.compile(
    r'<<<<<<<\s*SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>\s*REPLACE',
    re.DOTALL,
)


def parse_edits(text: str) -> list[dict]:
    """Возвращает [{'path', 'search', 'replace'}, ...]."""
    edits = []
    opens = list(EDIT_OPEN.finditer(text))
    for i, m in enumerate(opens):
        path = m.group(1).strip().lstrip('/')
        body_start = m.end()
        body_end = opens[i + 1].start() if i + 1 < len(opens) else len(text)
        body = text[body_start:body_end]
        if EDIT_CLOSE in body:
            body = body.split(EDIT_CLOSE)[0]
        for sm in _SEARCH_REPLACE.finditer(body):
            edits.append({
                'path': path,
                'search': sm.group(1),
                'replace': sm.group(2),
            })
    return edits


def apply_edits(files: dict[str, str], edits: list[dict]) -> tuple[dict, list[str]]:
    """
    Применяет патчи. Возвращает (updated_files, failed_paths).
    failed_paths — патчи, где файла нет или SEARCH-фрагмент не найден
    (нужен fallback на полную перегенерацию файла).
    Заменяется ПЕРВОЕ вхождение SEARCH — детерминированно.
    """
    out = dict(files)
    failed = []
    for e in edits:
        content = out.get(e['path'])
        if content is None or e['search'] not in content:
            failed.append(e['path'])
            continue
        out[e['path']] = content.replace(e['search'], e['replace'], 1)
    return out, failed


def edits_too_large(files: dict[str, str], edits: list[dict], threshold: float = 0.4) -> set[str]:
    """
    Возвращает множество путей, где суммарный объём SEARCH-фрагментов превышает
    threshold (40%) строк файла — для таких диффы не выгодны, нужна перегенерация.
    """
    by_path: dict[str, int] = {}
    for e in edits:
        by_path[e['path']] = by_path.get(e['path'], 0) + e['search'].count('\n') + 1
    big = set()
    for path, search_lines in by_path.items():
        total = files.get(path, '').count('\n') + 1
        if total and search_lines / total > threshold:
            big.add(path)
    return big
```

#### 2. `guardian.py` — добавить EDITS в промпт и парсер

В V3-промпты (`SYSTEM_V3_RU/EN` из Коммита 5) **добавить** перед строкой `"Ответь СТРОГО:"`:
```
    "Для ЛОКАЛЬНЫХ правок выдавай EDIT blocks (точечные диффы), НЕ перегенерацию:\n"
    "=== EDIT: <путь> ===\n"
    "<<<<<<< SEARCH\n<точный текущий кусок>\n=======\n<новый кусок>\n>>>>>>> REPLACE\n"
    "=== END EDIT ===\n"
    "SEARCH должен ТОЧНО совпадать с текущим кодом (включая отступы).\n\n"
```
И в формат ответа добавить секцию `EDITS:` между INSTRUCTIONS и FILES:
```
    "INSTRUCTIONS:\nКонкретные инструкции.\n"
    "EDITS:\n<edit blocks или пусто>\n"
    "FILES:\n- путь (только если нужна ПОЛНАЯ перегенерация файла)"
```

**Критично — обновить `_parse_guardian_response`** (это integration trap). Текущий regex INSTRUCTIONS:
```python
    instr_m = re.search(r'INSTRUCTIONS\s*:\s*\n(.*?)(?=FILES\s*:|$)',
                        text, re.DOTALL | re.IGNORECASE)
```
заменить на (добавить `EDITS\s*:` в lookahead, иначе INSTRUCTIONS проглотит блоки EDIT):
```python
    instr_m = re.search(r'INSTRUCTIONS\s*:\s*\n(.*?)(?=EDITS\s*:|FILES\s*:|$)',
                        text, re.DOTALL | re.IGNORECASE)
```
И добавить извлечение edits (в `_parse_guardian_response`, перед `return`):
```python
    edits = []
    try:
        from django.conf import settings
        if settings.STUDIO_V3:
            from .edits import parse_edits
            edits_m = re.search(r'EDITS\s*:\s*\n(.*?)(?=\nFILES\s*:|$)',
                                text, re.DOTALL | re.IGNORECASE)
            edits_text = edits_m.group(1) if edits_m else text
            edits = parse_edits(edits_text)
    except Exception:
        edits = []
    return {
        'verdict': verdict,
        'issues': issues,
        'instructions': instructions,
        'target_files': target_files,
        'edits': edits,
    }
```
(добавить `'edits': edits` в возвращаемый dict; в legacy режиме `edits=[]`).

#### 3. `tasks.py` — EDIT-ветка в guardian_review и coder_iteration

В `guardian_review`, где формируется `state.fix_plan` (строки ~473-477):
```python
        state.fix_plan = {
            'instructions': result.get('instructions', ''),
            'target_files': result.get('target_files', []),
            'priority': 'high',
        }
```
добавить `edits`:
```python
        state.fix_plan = {
            'instructions': result.get('instructions', ''),
            'target_files': result.get('target_files', []),
            'edits': result.get('edits', []) if settings.STUDIO_V3 else [],
            'priority': 'high',
        }
```

В `coder_iteration`, в начале fix-ветки (строки ~328-334), добавить попытку применить EDITS ДО вызова coder:
```python
        allowed_files = None
        if project.pipeline.iteration_count > 0 and project.pipeline.fix_plan:
            fp = project.pipeline.fix_plan
            # === V3: попытка применить EDIT blocks без перегенерации ===
            if settings.STUDIO_V3 and fp.get('edits'):
                applied = _try_apply_edits(project, project_id, step_index, fp['edits'])
                if applied:
                    return  # патчи применены, шаг отправлен в guardian внутри _try_apply_edits
            # ==========================================================
            targets = fp.get('target_files') or []
            step_text += f"\n\nИСПРАВЬ согласно FixPlan:\n{fp.get('instructions', '')}"
            if targets:
                step_text += f"\n\nИЗМЕНЯЙ ТОЛЬКО эти файлы: {', '.join(targets)}. Остальные не трогай."
                allowed_files = targets
```

И добавить функцию `_try_apply_edits` в `tasks.py`:
```python
def _try_apply_edits(project, project_id, step_index, edits):
    """
    Применяет EDIT blocks к файлам проекта. Возвращает True, если удалось
    применить хотя бы часть патчей и шаг отправлен в guardian; False — если
    нужна полная перегенерация (fallback на обычный coder).
    """
    from .agents.edits import apply_edits, edits_too_large
    from .validators import is_structurally_complete
    files = {f.path: f.content for f in project.files.all()}
    big = edits_too_large(files, edits, threshold=0.4)
    edits_small = [e for e in edits if e['path'] not in big]
    if not edits_small:
        return False  # все правки крупные → перегенерация
    updated, failed = apply_edits(files, edits_small)
    if failed:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'SEARCH не найден в {len(failed)} файлах — перегенерирую их',
        })
        return False  # часть SEARCH не найдена → fallback на coder
    # проверяем структуру изменённых файлов
    changed = {p: updated[p] for p in {e['path'] for e in edits_small}}
    for path, content in changed.items():
        ok, _ = is_structurally_complete(path, content)
        if not ok:
            return False  # патч сломал файл → перегенерация
    # сохраняем
    for path, content in changed.items():
        StudioFile.objects.update_or_create(
            project=project, path=path,
            defaults={'content': content, 'last_modified_by': 'agent'},
        )
    project.interview_data.setdefault('last_changed', {})[str(step_index)] = list(changed.keys())
    project.save(update_fields=['interview_data'])
    if project.sandbox_container_id:
        sandbox.write_files(project.sandbox_container_id, changed)
        sandbox.wait_for_ready(project.sandbox_container_id, timeout=60)
    publish_event(project_id, {
        'agent': 'coder', 'level': 'info',
        'text': f'Применены патчи EDIT к {len(changed)} файлам (без перегенерации)',
    })
    guardian_review.delay(project_id, step_index)
    return True
```

#### 4. `tests.py` — тесты edits

```python
from studio.agents.edits import parse_edits, apply_edits, edits_too_large


class EditBlocksTests(SimpleTestCase):
    def test_parse_single_edit(self):
        text = (
            "=== EDIT: src/App.tsx ===\n"
            "<<<<<<< SEARCH\n<div>old</div>\n=======\n<div>new</div>\n>>>>>>> REPLACE\n"
            "=== END EDIT ==="
        )
        edits = parse_edits(text)
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]['path'], 'src/App.tsx')
        self.assertEqual(edits[0]['search'], '<div>old</div>')
        self.assertEqual(edits[0]['replace'], '<div>new</div>')

    def test_apply_edit_success(self):
        files = {'a.ts': 'const x = 1\nconst y = 2\n'}
        edits = [{'path': 'a.ts', 'search': 'const x = 1', 'replace': 'const x = 42'}]
        updated, failed = apply_edits(files, edits)
        self.assertEqual(failed, [])
        self.assertIn('const x = 42', updated['a.ts'])

    def test_apply_edit_search_not_found(self):
        files = {'a.ts': 'const x = 1\n'}
        edits = [{'path': 'a.ts', 'search': 'NOPE', 'replace': 'X'}]
        updated, failed = apply_edits(files, edits)
        self.assertEqual(failed, ['a.ts'])

    def test_edits_too_large(self):
        files = {'a.ts': 'l1\nl2\nl3\nl4\nl5\n'}  # 5 строк
        edits = [{'path': 'a.ts', 'search': 'l1\nl2\nl3', 'replace': 'x'}]  # 3 строки > 40%
        big = edits_too_large(files, edits, threshold=0.4)
        self.assertIn('a.ts', big)
```

### Тест-критерии
```bash
cd src
python manage.py test studio.tests.EditBlocksTests
```
- `STUDIO_V3=0`: guardian-ответ парсится как раньше, `edits=[]`, fix-ветка не применяет патчи (полная перегенерация). Существующие тесты проходят.
- Проверить регрессию `_parse_guardian_response`: при отсутствии EDITS секции INSTRUCTIONS извлекается корректно (lookahead `EDITS\s*:|FILES\s*:|$`).

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` — `edits=[]`, `_try_apply_edits` не вызывается, fix-логика идентична прежней.
- **Integration trap (главное):** обновить INSTRUCTIONS-regex с `(?=FILES\s*:|$)` на `(?=EDITS\s*:|FILES\s*:|$)` — иначе INSTRUCTIONS проглотит весь EDIT-блок.
- `_try_apply_edits` возвращает True ТОЛЬКО при успехе (патчи применены + структура цела + отправлено в guardian). Любой сбой → False → обычная перегенерация через coder. Это сохраняет полный fallback.
- `sandbox`, `StudioFile`, `publish_event`, `guardian_review` уже импортированы/определены в `tasks.py`.
- Не забудь `'edits': edits` в return `_parse_guardian_response` и `'edits': edits` в обоих режимах (в legacy — пустой список).

---

## Коммит 7: Стартовый scaffold — UI-примитивы в шаге 1

### Заголовок коммита
```
studio v3: scaffold UI primitives and globals.css on first step
```

### Цель
Гарантировать, что у каждого React/Next-проекта на шаге 1 появляются UI-примитивы (`Button`, `Card`, `Input`, `Badge`) и `globals.css` с токенами — детерминированно, статическим словарём, а не на усмотрение LLM. Это даёт визуальную консистентность.

### Затронутые файлы
- `src/studio/scaffold.py` — **создать**
- `src/studio/tasks.py` — впрыск scaffold перед/на шаге 0

### Детальные изменения

#### 1. Новый файл `src/studio/scaffold.py`

```python
"""
Статический scaffold UI-примитивов для V3. Записывается детерминированно
на шаге 0, чтобы не доверять качество базовых компонентов LLM.
Зависит только от Tailwind + lucide-react (без shadcn/radix).
"""

_BUTTON = """import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const styles: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:opacity-90',
  secondary: 'bg-muted text-foreground hover:bg-muted/80',
  ghost: 'bg-transparent hover:bg-muted',
}

export function Button({ variant = 'primary', className = '', ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg h-10 px-4 text-sm font-medium transition disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}
"""

_CARD = """import { HTMLAttributes } from 'react'

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-xl border border-border bg-card p-6 shadow-sm ${className}`} {...props} />
  )
}
"""

_INPUT = """import { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-lg border border-border bg-background h-10 px-3 text-sm outline-none focus:ring-2 focus:ring-primary ${className}`}
      {...props}
    />
  )
}
"""

_BADGE = """import { HTMLAttributes } from 'react'

export function Badge({ className = '', ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`inline-flex items-center rounded-md border border-border px-2 py-0.5 text-xs font-medium ${className}`} {...props} />
  )
}
"""


def scaffold_files(stack: str, design_md: str = '') -> dict[str, str]:
    """
    Возвращает {path: content} стартовых UI-примитивов для react/nextjs.
    Для vue/html — пустой dict (примитивы не применяются).
    """
    if stack not in ('react', 'nextjs'):
        return {}
    base = 'src/components/ui'
    return {
        f'{base}/Button.tsx': _BUTTON,
        f'{base}/Card.tsx': _CARD,
        f'{base}/Input.tsx': _INPUT,
        f'{base}/Badge.tsx': _BADGE,
    }
```

> Примечание: `globals.css` с токенами лучше оставить на генерацию архитектора/coder из DESIGN.md (т.к. палитра проектозависима), либо добавить минимальный дефолт здесь. В рамках этого коммита достаточно UI-примитивов; токены приходят через DESIGN.md (Коммит 5).

#### 2. `tasks.py` — впрыск scaffold

В `run_pipeline`, перед `start_step.delay(project_id, 0)` (строка ~260), добавить:
```python
    if settings.STUDIO_V3:
        from .scaffold import scaffold_files
        sf = scaffold_files(project.target_stack, project.design_md_content)
        if sf:
            for path, content in sf.items():
                StudioFile.objects.get_or_create(
                    project=project, path=path,
                    defaults={'content': content, 'last_modified_by': 'scaffold'},
                )
            if project.sandbox_container_id:
                try:
                    sandbox.write_files(project.sandbox_container_id, sf)
                except Exception:
                    pass
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': f'Установлены UI-примитивы ({len(sf)} файлов)',
            })
    start_step.delay(project_id, 0)
```

> Используем `get_or_create` — чтобы не перезатереть, если coder уже создал эти файлы. Scaffold ставит базу, coder может её дополнить.

### Тест-критерии
- Юнит-тест `scaffold_files`: для `'nextjs'`/`'react'` возвращает 4 файла с путями `src/components/ui/*.tsx`; для `'html'`/`'vue'` — пустой dict.
- `STUDIO_V3=0`: scaffold не впрыскивается. Существующие тесты проходят.
- Статически: убедиться, что примитивы используют только Tailwind + react (нет внешних зависимостей).

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` scaffold не применяется.
- `get_or_create` (НЕ `update_or_create`) — чтобы пользовательские/coder-правки не затирались при повторном запуске.
- Примитивы используют токены `bg-primary`, `border-border`, `bg-card`, `bg-muted` — они должны быть определены в `globals.css`/`tailwind.config` из DESIGN.md. Если их нет, классы просто не применятся (не сломает сборку Tailwind v4/JIT).
- Для `vue`/`html` scaffold пустой — не навязываем React-примитивы.

---

## Коммит 8: Метрики per-step в interview_data['metrics']

### Заголовок коммита
```
studio v3: per-step metrics logging (truncation, structure fails, iterations, build)
```

### Цель
Логировать измеримые показатели качества по каждому шагу в `interview_data['metrics']` — для доказательства «мирового уровня» (см. §10 плана). Риск нулевой: только запись данных.

### Затронутые файлы
- `src/studio/tasks.py`

### Детальные изменения

Добавить хелпер в `tasks.py`:
```python
def _record_metric(project, step_index, **kwargs):
    """Накапливает per-step метрики в interview_data['metrics'][str(step_index)]."""
    metrics = project.interview_data.setdefault('metrics', {})
    step_m = metrics.setdefault(str(step_index), {})
    for k, v in kwargs.items():
        if isinstance(v, (int, float)) and k in step_m and isinstance(step_m[k], (int, float)):
            step_m[k] += v  # счётчики суммируются
        else:
            step_m[k] = v
    project.save(update_fields=['interview_data'])
```

Точки вызова (все под `if settings.STUDIO_V3:`):

1. В `_structure_gate` (Коммит 3) — после подсчёта `broken`:
```python
    if settings.STUDIO_V3:
        _record_metric(project, step_index, structure_fails=len(broken))
```

2. В `_dependency_gate` (Коммит 3) — при непустом `missing`:
```python
    _record_metric(project, project_id and step_index, dep_fails=1)
```
(вызвать с правильным step_index — передать его параметром в `_dependency_gate`; при необходимости расширь сигнатуру `_dependency_gate(project, project_id, step_index, files)`).

3. В `guardian_review` — при verdict pass без итераций (first-pass):
```python
    if settings.STUDIO_V3:
        _record_metric(project, step_index,
                       guardian_iterations=state.iteration_count,
                       build_pass=1 if (build_logs and 'error' not in build_logs.lower()) else 0,
                       verdict=verdict)
```

4. В `_try_apply_edits` (Коммит 6) — при успешном применении:
```python
    if settings.STUDIO_V3:
        _record_metric(project, step_index, edits_applied=1)
```

5. В `coder_iteration` — после `agent.run`, посчитать truncation (если coder экспонирует incomplete; иначе — число файлов):
```python
    if settings.STUDIO_V3:
        _record_metric(project, step_index, files_generated=len(files))
```

> Опционально: чтобы считать `truncation_rate`, coder может класть число incomplete в `agent.last_incomplete` (добавить атрибут в Коммите 2). Если этого нет — метрика truncation пропускается, остальные считаются.

### Тест-критерии
- Юнит-тест `_record_metric`: вызвать дважды с `structure_fails=1` → проверить сумму `2` в `interview_data['metrics']['0']`.
- `STUDIO_V3=0`: метрики не пишутся. Существующие тесты проходят.
- После прогона проекта (ручной/интеграционный) — проверить наличие `interview_data['metrics']` со счётчиками.

### На что обратить внимание
- **Инвариант:** при `STUDIO_V3=False` метрики не пишутся, поведение идентично.
- `_record_metric` делает `project.save(update_fields=['interview_data'])` — есть риск гонки с другими записями в `interview_data` (как с `billing_log`). Минимизируй частоту вызовов; при сомнении — `project.refresh_from_db(fields=['interview_data'])` перед изменением (по аналогии с `_billing_charge`).
- Это коммит наблюдаемости — он не должен влиять на логику pipeline. Любая ошибка записи метрики — оборачивай в `try/except`, чтобы не уронить шаг.

---

## План реализации по сессиям

Рекомендуемая группировка коммитов в сессии Claude Sonnet. Принцип: одна сессия = один связный слой, который можно протестировать целиком, не держа в голове остальное.

### Сессия 1 — Фундамент (Коммит 1)
**Только Коммит 1.** Создать `blocks.py`, `validators.py`, флаг `STUDIO_V3`, тесты. Прогнать `python manage.py test studio`. Это изолированный, безопасный коммит — отдельная сессия гарантирует, что фундамент корректен до того, как на него опираются остальные. Запушить.

### Сессия 2 — Coder + gates (Коммиты 2 и 3)
Связаны напрямую: Коммит 2 даёт FILE_BLOCKS-генерацию, Коммит 3 — gate, который её валидирует. Их логично делать и тестировать вместе (gate без FILE_BLOCKS бессмысленен). Тестировать обязательно при `STUDIO_V3=0` (регрессия) и при `STUDIO_V3=1` (новый путь, с моками модели). **Самая рискованная сессия** — горячий путь генерации. Не объединять с другими.

### Сессия 3 — Architect + DESIGN (Коммит 4)
**Только Коммит 4** (миграция + новый артефакт + парсер плана). Миграция БД — повод изолировать. После применения миграции и тестов `_parse_plan` — запушить.

### Сессия 4 — DESIGN в промптах + EDIT blocks (Коммиты 5 и 6)
Коммит 5 (читать DESIGN/лимиты) — лёгкий. Коммит 6 (EDIT blocks) опирается на V3-промпты guardian, введённые в Коммите 5 (туда добавляется EDITS-секция). Логично делать подряд в одной сессии. Особое внимание — integration trap в `_parse_guardian_response` (regex INSTRUCTIONS).

### Сессия 5 — Scaffold + метрики (Коммиты 7 и 8)
Оба низкорисковые и независимые от горячего пути. Scaffold (Коммит 7) — статические файлы. Метрики (Коммит 8) — только запись данных, врезается в точки, созданные в Сессиях 2-4. Делать последними.

### Сводная таблица сессий

| Сессия | Коммиты | Риск | Ключевой тест |
|--------|---------|------|---------------|
| 1 | 1 | нулевой | `test studio` (парсеры/валидаторы) |
| 2 | 2, 3 | высокий | регрессия `STUDIO_V3=0` + моки FILE_BLOCKS |
| 3 | 4 | низкий | миграция + `_parse_plan` |
| 4 | 5, 6 | средний | `_parse_guardian_response` regex + EditBlocksTests |
| 5 | 7, 8 | нулевой | `scaffold_files` + `_record_metric` |

### Универсальный чек-лист для каждой сессии
1. Прочитать актуальный код затронутых файлов (он мог измениться с момента написания этого плана).
2. Реализовать изменения коммита.
3. **Проверить инвариант флага:** при `STUDIO_V3=0` поведение байт-в-байт прежнее.
4. Прогнать `cd src && python manage.py test studio`.
5. Закоммитить с указанным заголовком.
6. `git push origin main` (правило проекта — пушить после каждого коммита).

### Что НЕ делать ни в одной сессии (до отдельного решения)
- НЕ удалять `_run_legacy`, `FILE_SYSTEM_*`, `SYSTEM_*` из coder — они нужны для ветки `STUDIO_V3=False` и fallback.
- НЕ менять `base.py` (continuation/usage/streaming уже работают).
- НЕ включать `STUDIO_V3=1` по умолчанию в settings/.env до полного прогона всех 8 коммитов на реальном проекте.
- НЕ трогать биллинг, same-diff detection, эскалацию моделей, sandbox — V3 строится поверх них.
```
