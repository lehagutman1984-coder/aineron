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

AGENT_SYSTEM = (
    'Ты — автономный AI-агент платформы aineron.ru. Тебе дана задача — '
    'выполни её пошагово, используя инструменты. На КАЖДОМ шаге отвечай '
    'ТОЛЬКО одним JSON-объектом без пояснений:\n'
    '{"action": "search", "input": "поисковый запрос", "reason": "зачем"} — '
    'веб-поиск актуальной информации;\n'
    '{"action": "calc", "input": "математическое выражение", "reason": "зачем"} — '
    'точное вычисление (только числа и операторы + - * / // % **, функции '
    'round, abs, min, max);\n'
    '{"action": "finish", "input": "итоговый отчёт в markdown", "reason": "готово"} — '
    'завершение с полным ответом пользователю.\n'
    f'Максимум {MAX_STEPS} шагов — планируй экономно. Отчёт в finish пиши '
    'на языке задачи, структурировано (заголовки, списки, таблицы), '
    'с фактами из наблюдений.'
)

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
    """Извлекает JSON-действие из ответа LLM. None если распарсить нельзя."""
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
    if action not in ('search', 'calc', 'finish'):
        return None
    return {
        'action': action,
        'input': str(data.get('input') or ''),
        'reason': str(data.get('reason') or '')[:200],
    }


def step_human(action: dict) -> str:
    """Человекочитаемое описание шага для живого прогресса."""
    kind = action['action']
    if kind == 'search':
        return f'Ищу в интернете: «{action["input"][:80]}»'
    if kind == 'calc':
        return f'Вычисляю: {action["input"][:80]}'
    return 'Готовлю итоговый отчёт'
