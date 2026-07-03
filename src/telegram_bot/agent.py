"""S9 — Agent Mode: инструменты и протокол многошагового агента.

Чистые функции без Django-зависимостей на уровне модуля (тестируемы отдельно).
Протокол: LLM на каждом шаге возвращает JSON
  {"action": "search"|"calc"|"finish", "input": "...", "reason": "..."}
Цикл исполняется в Celery (telegram_bot.tasks.run_agent).
"""
import ast
import json
import logging
import operator as op

logger = logging.getLogger(__name__)

MAX_STEPS = 6

_BASE_TOOLS = (
    '{"action": "search", "input": "поисковый запрос", "reason": "зачем"} — '
    'веб-поиск актуальной информации;\n'
    '{"action": "calc", "input": "математическое выражение", "reason": "зачем"} — '
    'точное вычисление (только числа и операторы + - * / // % **, функции '
    'round, abs, min, max);\n'
)

# U4: инструменты над Project Spaces (доступны при подключённом проекте)
_KB_TOOLS = (
    '{"action": "kb_search", "input": "запрос", "reason": "зачем"} — '
    'семантический поиск по базе знаний проекта (файлы, документы, код);\n'
    '{"action": "list_files", "input": "", "reason": "зачем"} — '
    'список файлов базы знаний проекта;\n'
    '{"action": "read_file", "input": "имя файла", "reason": "зачем"} — '
    'прочитать файл проекта целиком;\n'
    '{"action": "propose_edit", "input": {"path": "имя файла", '
    '"search": "уникальный старый фрагмент", "replace": "новый фрагмент", '
    '"message": "сообщение коммита"}, "reason": "зачем"} — '
    'предложить правку файла (создаёт коммит на подтверждение владельцу, '
    'НИЧЕГО не меняет без его одобрения);\n'
)

ALL_ACTIONS = ('search', 'calc', 'finish', 'kb_search', 'list_files',
               'read_file', 'propose_edit')


def build_agent_system(project_name: str = '') -> str:
    """Системный промт агента; при подключённом проекте — с KB-инструментами."""
    tools = _BASE_TOOLS + (_KB_TOOLS if project_name else '')
    project_note = (
        f'\nК тебе подключён проект «{project_name}» — используй его базу '
        f'знаний как первоисточник, веб-поиск — для внешних фактов.'
        if project_name else ''
    )
    return (
        'Ты — автономный AI-агент платформы aineron.ru. Тебе дана задача — '
        'выполни её пошагово, используя инструменты. На КАЖДОМ шаге отвечай '
        'ТОЛЬКО одним JSON-объектом без пояснений:\n'
        + tools +
        '{"action": "finish", "input": "итоговый отчёт в markdown", "reason": "готово"} — '
        'завершение с полным ответом пользователю.\n'
        f'Максимум {MAX_STEPS} шагов — планируй экономно. Отчёт в finish пиши '
        'на языке задачи, структурировано (заголовки, списки, таблицы), '
        'с фактами из наблюдений.'
        + project_note
    )


# Обратная совместимость (тесты, старые импорты)
AGENT_SYSTEM = build_agent_system()

# ─── Безопасный калькулятор (AST, без eval) ───

_BIN_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow,
}
_UNARY_OPS = {ast.UAdd: op.pos, ast.USub: op.neg}
_FUNCS = {'round': round, 'abs': abs, 'min': min, 'max': max}


def safe_calc(expr: str) -> str:
    """Вычисляет арифметическое выражение без eval. Возвращает строку-результат
    или строку с описанием ошибки (агент увидит её как наблюдение)."""
    expr = (expr or '').strip()
    if not expr or len(expr) > 300:
        return 'Ошибка: пустое или слишком длинное выражение'

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError('только числа')
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError('слишком большая степень')
            return _BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _FUNCS and not node.keywords:
            return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
        if isinstance(node, ast.Tuple):
            return tuple(_eval(e) for e in node.elts)
        raise ValueError(f'недопустимая конструкция: {type(node).__name__}')

    try:
        result = _eval(ast.parse(expr, mode='eval'))
        return str(result)
    except ZeroDivisionError:
        return 'Ошибка: деление на ноль'
    except Exception as e:
        return f'Ошибка вычисления: {e}'


def parse_action(raw: str) -> dict | None:
    """Извлекает JSON-действие из ответа LLM. None если распарсить нельзя.

    input — строка для простых инструментов; dict для propose_edit.
    """
    if not raw:
        return None
    start, end = raw.find('{'), raw.rfind('}') + 1
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end])
    except Exception:
        return None
    action = data.get('action')
    if action not in ALL_ACTIONS:
        return None
    raw_input = data.get('input')
    if action == 'propose_edit':
        if not isinstance(raw_input, dict):
            return None
        action_input = raw_input
    else:
        action_input = str(raw_input or '')
    return {
        'action': action,
        'input': action_input,
        'reason': str(data.get('reason') or '')[:200],
    }


def step_human(action: dict) -> str:
    """Человекочитаемое описание шага для живого прогресса."""
    kind = action['action']
    if kind == 'search':
        return f'Ищу в интернете: «{str(action["input"])[:80]}»'
    if kind == 'calc':
        return f'Вычисляю: {str(action["input"])[:80]}'
    if kind == 'kb_search':
        return f'Ищу в базе знаний: «{str(action["input"])[:80]}»'
    if kind == 'list_files':
        return 'Смотрю файлы проекта'
    if kind == 'read_file':
        return f'Читаю файл: {str(action["input"])[:80]}'
    if kind == 'propose_edit':
        path = action['input'].get('path', '') if isinstance(action['input'], dict) else ''
        return f'Готовлю правку файла: {path[:80]}'
    return 'Готовлю итоговый отчёт'


def apply_search_replace(text: str, search: str, replace: str) -> tuple:
    """Применяет замену с uniqueness-guard (как EDIT Blocks).

    Возвращает (new_text | None, err_msg)."""
    if not search:
        return None, 'пустой фрагмент search'
    count = text.count(search)
    if count == 0:
        return None, 'фрагмент search не найден в файле'
    if count > 1:
        return None, f'фрагмент search не уникален (встречается {count} раз)'
    return text.replace(search, replace, 1), ''
