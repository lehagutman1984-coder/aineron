"""S1 — конвертер Markdown-ответа LLM в дерево Rich-блоков (Bot API 10.1).

Чистый python-модуль без зависимостей от Django/aiogram — покрыт юнит-тестами
(test_rich.py). Используется из notify.send_rich_or_markdown(); при любой
ошибке или выключенном флаге TG_RICH_MESSAGES вызывающий код обязан упасть
обратно на HTML-путь (telegram_format).

Поддерживаемые блоки:
  paragraph      — обычный текст (инлайн-разметка сохраняется как markdown)
  heading        — # / ## / ### заголовки
  table          — GFM-таблицы (RichBlockTable)
  preformatted   — ```код``` с языком (RichBlockPreformatted)
  math           — $$формула$$ (RichBlockMathematicalExpression)
  thinking       — <think>…</think> reasoning-блоки (RichBlockThinking)
  list           — маркированные и нумерованные списки
"""
import re
from dataclasses import dataclass, field


@dataclass
class RichBlock:
    type: str = 'paragraph'
    text: str = ''

    def to_dict(self) -> dict:
        return {'type': self.type, 'text': self.text}


@dataclass
class RichBlockHeading(RichBlock):
    level: int = 1

    def __post_init__(self):
        self.type = 'heading'

    def to_dict(self) -> dict:
        return {'type': 'heading', 'level': self.level, 'text': self.text}


@dataclass
class RichBlockPreformatted(RichBlock):
    language: str = ''

    def __post_init__(self):
        self.type = 'preformatted'

    def to_dict(self) -> dict:
        return {'type': 'preformatted', 'language': self.language, 'code': self.text}


@dataclass
class RichBlockTable(RichBlock):
    header: list = field(default_factory=list)
    rows: list = field(default_factory=list)

    def __post_init__(self):
        self.type = 'table'

    def to_dict(self) -> dict:
        return {'type': 'table', 'header': self.header, 'rows': self.rows}


@dataclass
class RichBlockMathematicalExpression(RichBlock):
    def __post_init__(self):
        self.type = 'math'

    def to_dict(self) -> dict:
        return {'type': 'math', 'expression': self.text}


@dataclass
class RichBlockThinking(RichBlock):
    def __post_init__(self):
        self.type = 'thinking'

    def to_dict(self) -> dict:
        return {'type': 'thinking', 'text': self.text}


@dataclass
class RichBlockList(RichBlock):
    ordered: bool = False
    items: list = field(default_factory=list)

    def __post_init__(self):
        self.type = 'list'

    def to_dict(self) -> dict:
        return {'type': 'list', 'ordered': self.ordered, 'items': self.items}


_TABLE_SEPARATOR_RE = re.compile(r'^\s*\|?[\s:|-]+\|[\s:|-]*$')
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_BULLET_RE = re.compile(r'^\s*[-*+]\s+(.*)$')
_ORDERED_RE = re.compile(r'^\s*\d+[.)]\s+(.*)$')


def _split_table_row(line: str) -> list:
    """'| a | b |' → ['a', 'b'] (крайние пустые ячейки отбрасываются)."""
    cells = [c.strip() for c in line.split('|')]
    if cells and cells[0] == '':
        cells = cells[1:]
    if cells and cells[-1] == '':
        cells = cells[:-1]
    return cells


def _extract_thinking(text: str):
    """Вырезает <think>/<thinking>-блоки reasoning-моделей. Возвращает (text, [thinking])."""
    thinking = []

    def _capture(m):
        content = m.group(2).strip()
        if content:
            thinking.append(content)
        return ''

    text = re.sub(r'<(think|thinking)>(.*?)</\1>', _capture, text, flags=re.DOTALL)
    return text, thinking


def md_to_rich_blocks(md_text: str) -> list:
    """Разбирает markdown-текст в список RichBlock. Пустой вход → []."""
    if not md_text or not md_text.strip():
        return []

    md_text, thinking_parts = _extract_thinking(md_text)
    blocks = []
    for part in thinking_parts:
        blocks.append(RichBlockThinking(text=part))

    # Выносим код-блоки и math-блоки, чтобы их содержимое не парсилось построчно
    placeholders = {}

    def _stash_code(m):
        key = f'\x00BLOCK{len(placeholders)}\x00'
        placeholders[key] = RichBlockPreformatted(
            text=m.group(2).strip('\n'), language=(m.group(1) or '').strip(),
        )
        return f'\n{key}\n'

    def _stash_math(m):
        key = f'\x00BLOCK{len(placeholders)}\x00'
        placeholders[key] = RichBlockMathematicalExpression(text=m.group(1).strip())
        return f'\n{key}\n'

    md_text = re.sub(r'```(\w*)\n?(.*?)```', _stash_code, md_text, flags=re.DOTALL)
    md_text = re.sub(r'\$\$(.+?)\$\$', _stash_math, md_text, flags=re.DOTALL)

    lines = md_text.split('\n')
    i = 0
    paragraph_buf = []
    list_buf = None  # (ordered, [items])

    def _flush_paragraph():
        nonlocal paragraph_buf
        if paragraph_buf:
            text = '\n'.join(paragraph_buf).strip()
            if text:
                blocks.append(RichBlock(text=text))
            paragraph_buf = []

    def _flush_list():
        nonlocal list_buf
        if list_buf and list_buf[1]:
            blocks.append(RichBlockList(ordered=list_buf[0], items=list_buf[1]))
        list_buf = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Плейсхолдер код/math-блока
        if stripped in placeholders:
            _flush_paragraph()
            _flush_list()
            blocks.append(placeholders[stripped])
            i += 1
            continue

        # Таблица: строка с | и следующая — разделитель
        if ('|' in stripped and i + 1 < len(lines)
                and _TABLE_SEPARATOR_RE.match(lines[i + 1] or '')
                and (stripped.startswith('|') or len(_split_table_row(stripped)) >= 2)):
            _flush_paragraph()
            _flush_list()
            header = _split_table_row(stripped)
            rows = []
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append(_split_table_row(lines[i]))
                i += 1
            blocks.append(RichBlockTable(header=header, rows=rows))
            continue

        m = _HEADING_RE.match(stripped)
        if m:
            _flush_paragraph()
            _flush_list()
            blocks.append(RichBlockHeading(level=min(len(m.group(1)), 3), text=m.group(2).strip()))
            i += 1
            continue

        m = _BULLET_RE.match(line)
        if m:
            _flush_paragraph()
            if list_buf is None or list_buf[0] is not False:
                _flush_list()
                list_buf = (False, [])
            list_buf[1].append(m.group(1).strip())
            i += 1
            continue

        m = _ORDERED_RE.match(line)
        if m:
            _flush_paragraph()
            if list_buf is None or list_buf[0] is not True:
                _flush_list()
                list_buf = (True, [])
            list_buf[1].append(m.group(1).strip())
            i += 1
            continue

        if not stripped:
            _flush_paragraph()
            _flush_list()
            i += 1
            continue

        _flush_list()
        paragraph_buf.append(line)
        i += 1

    _flush_paragraph()
    _flush_list()
    return blocks


def blocks_to_payload(blocks: list) -> list:
    """Сериализация блоков в payload для sendRichMessage."""
    return [b.to_dict() for b in blocks]


def extract_first_code(md_text: str, max_len: int = 256) -> str:
    """Первый код-блок или инлайн-код ответа — для кнопки copy_text (≤256 симв.)."""
    if not md_text:
        return ''
    m = re.search(r'```\w*\n?(.*?)```', md_text, flags=re.DOTALL)
    if m:
        code = m.group(1).strip()
        return code if 0 < len(code) <= max_len else ''
    m = re.search(r'`([^`\n]+)`', md_text)
    if m:
        code = m.group(1).strip()
        return code if 0 < len(code) <= max_len else ''
    return ''
