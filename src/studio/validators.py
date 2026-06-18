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
