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
