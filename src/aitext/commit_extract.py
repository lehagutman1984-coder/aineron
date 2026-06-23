import logging
import re

logger = logging.getLogger(__name__)

# ── Commit instructions ──────────────────────────────────────────────────────

AI_COMMIT_INSTRUCTION = (
    "В этом проекте есть кнопка «Подтвердить коммит» — она записывает файл целиком в GitHub.\n\n"
    "Когда предлагаешь любое исправление файла (нашёл баг, добавил функцию, рефакторинг):\n"
    "1. Сначала объясни что не так и что именно меняешь (обычный текст).\n"
    "2. Затем выведи ПОЛНЫЙ исправленный файл в формате:\n"
    "=== FILE: путь/к/файлу.ext ===\n"
    "<полное содержимое файла от первой до последней строки>\n"
    "=== END FILE ===\n"
    "Пользователь увидит кнопку «Подтвердить» и одним кликом запушит изменения в GitHub.\n\n"
    "ОБЯЗАТЕЛЬНО выводи ПОЛНЫЙ файл — даже если файл 1000+ строк. "
    "Кнопка коммита работает ТОЛЬКО с полным файлом. Частичный вывод сломает репозиторий.\n\n"
    "СТРОГО ЗАПРЕЩЕНО:\n"
    "- заменять код заглушками: «# ...», «# остальной код без изменений», «# rest of code», «// ...»\n"
    "- обрезать файл на полуслове\n"
    "- писать «файл слишком большой» — это не причина не выводить, выводи всегда целиком\n\n"
    "Можно выводить несколько файлов подряд. Заканчивай маркером: === END RESPONSE ==="
)

AI_COMMIT_INSTRUCTION_WITH_EDITS = (
    "В этом проекте есть кнопка «Подтвердить коммит» — она записывает изменения в GitHub.\n\n"
    "Этот проект содержит файлы > 30 000 символов. Используй правильный формат по размеру файла:\n\n"
    "━━ МАЛЫЕ файлы (<30 000 симв.) — выводи ПОЛНЫЙ файл:\n"
    "=== FILE: путь/к/файлу.ext ===\n"
    "<полное содержимое файла от первой до последней строки>\n"
    "=== END FILE ===\n\n"
    "━━ БОЛЬШИЕ файлы (≥30 000 симв.) — выводи только ИЗМЕНЕНИЯ (EDIT-блоки):\n"
    "=== EDIT: путь/к/файлу.ext ===\n"
    "<<<SEARCH>>>\n"
    "<точный существующий текст, 5–20 строк с уникальным контекстом вокруг правки>\n"
    "<<<REPLACE>>>\n"
    "<новый текст>\n"
    "<<<END>>>\n"
    "=== END EDIT ===\n\n"
    "Правила EDIT-блоков:\n"
    "- SEARCH копируй дословно из базы знаний (пробелы, отступы, знаки — без изменений).\n"
    "- SEARCH должен быть уникальным в файле (5–20 строк, включая контекст вокруг правки).\n"
    "- Несколько правок одного файла — несколько <<<SEARCH>>>...<<<END>>> в одном EDIT-блоке.\n"
    "- Несколько файлов — несколько =EDIT=...=END EDIT= подряд.\n\n"
    "СТРОГО ЗАПРЕЩЕНО:\n"
    "- заглушки: «# ...», «# остальной код без изменений», «# rest of code», «// ...»\n"
    "- обрезать FILE-блок на полуслове\n"
    "- писать «файл слишком большой» — для больших файлов есть EDIT-блоки\n"
    "- изменять SEARCH-текст (копируй дословно из источника)\n\n"
    "Заканчивай маркером: === END RESPONSE ==="
)

# ── FILE-block patterns ──────────────────────────────────────────────────────

# Паттерны обрезки которые модель добавляет вместо реального кода
_TRUNCATION_RE = re.compile(
    r'^\s*(?:#|//|/\*)\s*'
    r'(?:\.\.\.|далее|остальн|rest of|not shown|omitted|продолжение|'
    r'Объём файла|полный файл|без изменений|unchanged|remaining)',
    re.IGNORECASE | re.MULTILINE,
)

# Незакрытый FILE-блок в конце ответа (обрезан API по токенам)
_UNCLOSED_FILE_RE = re.compile(
    r'===\s*FILE:\s*([^\n=]+?)\s*===\n([\s\S]+)$'
)

# Полный FILE-блок
_COMPLETE_FILE_RE = re.compile(
    r'===\s*FILE:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END FILE\s*===',
)

# ── EDIT-block patterns ──────────────────────────────────────────────────────

# Полный EDIT-блок
_EDIT_BLOCK_RE = re.compile(
    r'===\s*EDIT:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END EDIT\s*===',
    re.MULTILINE,
)

# Один SEARCH/REPLACE хunk внутри EDIT-блока
# Tolerant: допускаем trailing whitespace после маркеров
_HUNK_RE = re.compile(
    r'<<<SEARCH>>>[ \t]*\n([\s\S]*?)<<<REPLACE>>>[ \t]*\n([\s\S]*?)<<<END>>>',
    re.MULTILINE,
)


# ── FILE helpers ─────────────────────────────────────────────────────────────

def _is_truncated(content: str) -> bool:
    """Возвращает True если файл содержит маркеры обрезки модели."""
    return bool(_TRUNCATION_RE.search(content))


def _find_truncated_file(text: str):
    """Ищет незакрытый FILE-блок в конце ответа (обрезан по токенам).
    Возвращает (path, content) или None.
    """
    last_complete_end = 0
    for m in _COMPLETE_FILE_RE.finditer(text):
        last_complete_end = m.end()

    remaining = text[last_complete_end:]
    m = _UNCLOSED_FILE_RE.search(remaining)
    if m and len(m.group(2)) > 500:
        return m.group(1).strip(), m.group(2)
    return None


def _get_full_file_source(project, file_path: str) -> str | None:
    """Возвращает полный текст файла — сначала из KB, потом из коннектора (GitHub/Gitea)."""
    # 1. KB
    try:
        from .models import ProjectFile
        pf = ProjectFile.objects.filter(
            project=project, repo_path=file_path, status='ready', enabled=True,
        ).first()
        if pf and pf.extracted_text:
            return pf.extracted_text
    except Exception as exc:
        logger.warning(f"[commit] KB lookup error for {file_path}: {exc}")

    # 2. Connector fallback (GitHub/Gitea)
    try:
        from .tasks import _fetch_from_connector
        content = _fetch_from_connector(project, file_path)
        if content:
            logger.info(f"[commit] connector fallback OK для {file_path}")
            return content
    except Exception as exc:
        logger.warning(f"[commit] connector fallback failed для {file_path}: {exc}")

    return None


def _stitch_tail_from_kb(project, file_path: str, ai_content: str):
    """Дописывает неизменённый хвост файла из KB к обрезанному AI-выводу.

    Используется как последний fallback — только если EDIT-блоков нет.
    Если правки были в хвосте файла — хвост будет из KB без изменений (предупреждение в коммите).
    """
    try:
        kb_content = _get_full_file_source(project, file_path)
        if not kb_content:
            return None
        ai_len = len(ai_content)
        kb_len = len(kb_content)

        if ai_len >= kb_len:
            return ai_content

        for window in (500, 200, 80):
            if ai_len < window:
                continue
            search_window = ai_content[-window:]
            kb_pos = kb_content.find(search_window)
            if kb_pos != -1:
                tail_start = kb_pos + window
                stitched = ai_content + kb_content[tail_start:]
                logger.info(
                    f"[commit] KB-tail stitch: {file_path} "
                    f"ai={ai_len} kb={kb_len} stitched={len(stitched)} "
                    f"(window={window}, tail={kb_len - tail_start})"
                )
                return stitched

        logger.warning(f"[commit] KB-tail stitch failed: {file_path} — anchor not found in KB")
        return None
    except Exception as exc:
        logger.warning(f"[commit] KB-tail stitch error: {exc}")
        return None


# ── EDIT-block logic ─────────────────────────────────────────────────────────

def parse_edit_blocks(text: str) -> dict[str, list[dict]]:
    """Парсит EDIT-блоки из ответа AI.

    Возвращает {path: [{'search': str, 'replace': str}, ...]} или {}.
    """
    result: dict[str, list[dict]] = {}
    for m in _EDIT_BLOCK_RE.finditer(text):
        path = m.group(1).strip().lstrip('/')
        hunks = [
            {'search': h.group(1), 'replace': h.group(2)}
            for h in _HUNK_RE.finditer(m.group(2))
        ]
        if hunks:
            result[path] = hunks
    return result


def apply_edit_blocks(source: str, hunks: list[dict]) -> str:
    """Применяет список SEARCH/REPLACE патчей к тексту файла.

    Стратегии поиска (в порядке применения):
      1. Exact match — строгое совпадение строки.
      2. Normalized — strip trailing whitespace с каждой строки (справляется с пробелами в концах).

    Оба варианта требуют уникальности SEARCH — если совпадений > 1, выбрасывает ValueError
    (это намеренно: тихое исправление не того места хуже явной ошибки).

    Raises:
        ValueError: если SEARCH не найден, не уникален или пустой.
    """
    result = source
    for i, hunk in enumerate(hunks, start=1):
        search: str = hunk['search']
        replace: str = hunk['replace']

        if not search.strip():
            raise ValueError(f"Хunk #{i}: SEARCH пустой")

        # ── Strategy 1: exact match ──────────────────────────────────────────
        exact_count = result.count(search)
        if exact_count == 1:
            result = result.replace(search, replace, 1)
            continue
        if exact_count > 1:
            raise ValueError(
                f"Хunk #{i}: SEARCH не уникален ({exact_count} вхождений) — "
                f"добавь больше контекста. Начало: {search[:60]!r}"
            )

        # ── Strategy 2: normalized line match ───────────────────────────────
        src_lines = result.splitlines(keepends=True)
        search_norm = [line.rstrip() for line in search.splitlines()]
        # убираем trailing empty lines из search
        while search_norm and not search_norm[-1]:
            search_norm.pop()

        if not search_norm:
            raise ValueError(f"Хunk #{i}: SEARCH пустой после нормализации")

        n = len(search_norm)
        matches: list[int] = []
        for idx in range(len(src_lines) - n + 1):
            window = [ln.rstrip('\n\r').rstrip() for ln in src_lines[idx:idx + n]]
            if window == search_norm:
                matches.append(idx)

        if len(matches) == 1:
            found = matches[0]
            before = ''.join(src_lines[:found])
            after = ''.join(src_lines[found + n:])
            rep = replace if replace.endswith('\n') else replace + '\n'
            result = before + rep + after
            continue
        if len(matches) > 1:
            raise ValueError(
                f"Хunk #{i}: SEARCH не уникален после нормализации ({len(matches)} вхождений) — "
                f"добавь больше контекста. Начало: {search[:60]!r}"
            )

        raise ValueError(
            f"Хunk #{i}: SEARCH не найден в файле. "
            f"Убедись что текст скопирован дословно из базы знаний. "
            f"Начало: {search[:60]!r}"
        )

    return result


# ── Prompt injection ─────────────────────────────────────────────────────────

def inject_commit_instruction(project, messages_for_api: list) -> None:
    """Добавляет инструкцию о FILE/EDIT-формате если проект имеет git-коннектор.

    Выбирает расширенную инструкцию (с EDIT-блоками) если в KB проекта есть
    файлы длиннее 30 000 символов.
    """
    try:
        if not project.connectors.exists():
            return
        has_large = False
        try:
            from django.db.models.functions import Length
            has_large = (
                project.knowledge_files
                .filter(status='ready', enabled=True)
                .annotate(_tlen=Length('extracted_text'))
                .filter(_tlen__gt=80_000)
                .exists()
            )
        except Exception as e:
            logger.debug(f"[commit] large-file check failed: {e}")

        instruction = AI_COMMIT_INSTRUCTION_WITH_EDITS if has_large else AI_COMMIT_INSTRUCTION
        messages_for_api.append({"role": "system", "content": instruction})
    except Exception:
        pass


# ── Main extraction ──────────────────────────────────────────────────────────

def extract_commit_from_response(project, assistant_text: str):
    """Парсит FILE/EDIT-блоки из ответа AI и создаёт ProjectCommit(status='pending').

    Порядок приоритетов:
      1. Полные FILE-блоки (малые файлы, полный вывод).
      2. EDIT-блоки (большие файлы — патч-коммиты, применяются к KB/GitHub источнику).
      3. Незакрытый FILE-блок + KB tail-stitch (legacy fallback, файл обрезан по токенам).
      4. None — ничего подходящего не найдено.

    Возвращает ProjectCommit или None.
    """
    try:
        from studio.agents.blocks import parse_file_blocks
        from .models import ProjectCommit

        commit_flags: list[str] = []

        # ── 1. Полные FILE-блоки ─────────────────────────────────────────────
        files, _ = parse_file_blocks(assistant_text)

        # ── 2. EDIT-блоки ────────────────────────────────────────────────────
        if not files:
            edit_blocks = parse_edit_blocks(assistant_text)
            if edit_blocks:
                edit_files: dict[str, str] = {}
                edit_errors: list[str] = []

                for file_path, hunks in edit_blocks.items():
                    source = _get_full_file_source(project, file_path)
                    if not source:
                        msg = f"{file_path}: источник не найден в KB/GitHub"
                        edit_errors.append(msg)
                        logger.warning(f"[commit] EDIT-блок: {msg}")
                        continue
                    try:
                        patched = apply_edit_blocks(source, hunks)
                        if patched == source:
                            msg = f"{file_path}: EDIT применён, изменений не обнаружено"
                            edit_errors.append(msg)
                            logger.warning(f"[commit] {msg}")
                        else:
                            edit_files[file_path] = patched
                            logger.info(
                                f"[commit] EDIT-блок OK: {file_path} "
                                f"({len(hunks)} хунк(ов), project {project.id})"
                            )
                    except ValueError as e:
                        msg = f"{file_path}: {e}"
                        edit_errors.append(msg)
                        logger.error(f"[commit] EDIT-блок apply failed: {msg}")

                if edit_files:
                    files = edit_files
                    if edit_errors:
                        commit_flags.append(
                            f"[{len(edit_errors)} EDIT-блок(ов) не применено: "
                            + "; ".join(edit_errors[:3])
                            + (f" и ещё {len(edit_errors)-3}" if len(edit_errors) > 3 else "")
                            + "]"
                        )
                elif edit_errors:
                    # Все EDIT-блоки провалились — сообщаем ошибки в лог ERROR-уровня
                    logger.error(
                        f"[commit] Все EDIT-блоки провалились для project {project.id}: "
                        + "; ".join(edit_errors)
                    )
                    return None

        # ── 3. Legacy: незакрытый FILE-блок + KB tail-stitch ─────────────────
        tail_stitched = False
        tail_stitch_failed = False
        if not files:
            truncated = _find_truncated_file(assistant_text)
            if truncated:
                file_path, ai_content = truncated
                stitched = _stitch_tail_from_kb(project, file_path, ai_content)
                if stitched:
                    files = {file_path: stitched}
                    tail_stitched = True
                    logger.info(
                        f"[commit] legacy KB-tail stitch для {file_path} "
                        f"(project {project.id})"
                    )
                else:
                    files = {file_path: ai_content}
                    tail_stitch_failed = True
                    logger.warning(
                        f"[commit] KB-stitch не сработал, коммитим обрезанный: {file_path}"
                    )
            else:
                return None

        # ── Отфильтровываем маркеры обрезки ──────────────────────────────────
        safe_files = {p: c for p, c in files.items() if not _is_truncated(c)}
        if not safe_files:
            logger.warning(
                f"[commit] все {len(files)} файлов содержат маркеры обрезки — "
                f"коммит отменён (project {project.id})"
            )
            return None
        if len(safe_files) < len(files):
            skipped = set(files) - set(safe_files)
            logger.warning(f"[commit] обрезанные файлы исключены из коммита: {skipped}")

        connector = project.connectors.order_by('created_at').first()
        if not connector:
            return None

        first_line = assistant_text.split('\n')[0].strip().lstrip('#').strip()
        commit_msg = first_line[:200] if first_line else f"AI: {len(safe_files)} файл(ов)"
        if not commit_msg:
            commit_msg = f"AI: {len(safe_files)} файл(ов)"

        if tail_stitched:
            commit_flags.append(
                "[ВНИМАНИЕ: хвост файла взят из KB без изменений — проверьте конец файла]"
            )
        elif tail_stitch_failed:
            commit_flags.append(
                "[ВНИМАНИЕ: файл обрезан API (~55K лимит) — хвост файла отсутствует, "
                "проверьте перед мержем]"
            )

        if commit_flags:
            commit_msg += " " + " ".join(commit_flags)

        commit = ProjectCommit.objects.create(
            project=project,
            connector=connector,
            commit_message=commit_msg,
            files=[{'path': p, 'content': c} for p, c in safe_files.items()],
            status='pending',
        )
        logger.info(
            f"AI-коммит {commit.id} создан для проекта {project.id}: "
            f"{len(safe_files)} файл(ов)"
        )
        return commit

    except Exception as e:
        logger.error(f"Ошибка extract_commit_from_response: {e}")
        return None
