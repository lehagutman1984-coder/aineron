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
