import logging
import re

logger = logging.getLogger(__name__)

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


def _is_truncated(content: str) -> bool:
    """Возвращает True если файл содержит маркеры обрезки модели."""
    return bool(_TRUNCATION_RE.search(content))


def _find_truncated_file(text: str):
    """Ищет незакрытый FILE-блок в конце ответа (обрезан по токенам).
    Возвращает (path, content) или None.
    """
    # Найдём конец последнего полного блока
    last_complete_end = 0
    for m in _COMPLETE_FILE_RE.finditer(text):
        last_complete_end = m.end()

    remaining = text[last_complete_end:]
    m = _UNCLOSED_FILE_RE.search(remaining)
    if m and len(m.group(2)) > 500:  # не меньше 500 символов — иначе не стоит
        return m.group(1).strip(), m.group(2)
    return None


def _get_full_file_source(project, file_path: str) -> str | None:
    """Возвращает полный текст файла — сначала из KB, потом из GitHub API."""
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

    # 2. GitHub API fallback
    try:
        from aitext.github_client import get_file_content
        connector = project.connectors.order_by('created_at').first()
        if connector and connector.token:
            content = get_file_content(
                connector.owner, connector.repo, connector.token,
                file_path, ref=connector.branch or 'main',
            )
            if content:
                logger.info(f"[commit] GitHub API fallback OK для {file_path}")
                return content
    except Exception as exc:
        logger.warning(f"[commit] GitHub API fallback failed для {file_path}: {exc}")

    return None


def _stitch_tail_from_kb(project, file_path: str, ai_content: str):
    """Дописывает неизменённый хвост файла из KB (или GitHub) к обрезанному AI-выводу.

    Логика: берём последние 500 символов AI-вывода, ищем их в источнике,
    и дописываем всё что идёт после найденной позиции.
    Возвращает полный текст файла или None если не удалось.
    """
    try:
        kb_content = _get_full_file_source(project, file_path)
        if not kb_content:
            return None
        ai_len = len(ai_content)
        kb_len = len(kb_content)

        if ai_len >= kb_len:
            # AI вывел столько же или больше — нечего дописывать
            return ai_content

        # Ищем конец AI-вывода в KB — пробуем окна 500, 200, 80 символов
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


def inject_commit_instruction(project, messages_for_api: list) -> None:
    """Добавляет инструкцию о FILE-формате если проект имеет git-коннектор."""
    try:
        if not project.connectors.exists():
            return
        messages_for_api.append({"role": "system", "content": AI_COMMIT_INSTRUCTION})
    except Exception:
        pass


def extract_commit_from_response(project, assistant_text: str):
    """Парсит FILE-блоки из ответа AI и создаёт ProjectCommit(status='pending').

    Возвращает созданный ProjectCommit или None если FILE-блоков не найдено / нет коннектора.
    Для файлов обрезанных по токенам — дописывает хвост из KB автоматически.
    """
    try:
        from studio.agents.blocks import parse_file_blocks
        from .models import ProjectCommit

        files, _ = parse_file_blocks(assistant_text)

        # Если нет полных FILE-блоков — ищем незакрытый (обрезанный по API-лимиту)
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
                        f"[commit] использован KB-tail stitch для {file_path} "
                        f"(project {project.id})"
                    )
                else:
                    # KB не нашёл файл — коммитим обрезанный с предупреждением
                    files = {file_path: ai_content}
                    tail_stitch_failed = True
                    logger.warning(
                        f"[commit] KB-stitch не сработал, коммитим обрезанный файл: {file_path}"
                    )
            else:
                return None

        # Отфильтровываем файлы с маркерами обрезки — коммитить неполный файл опасно
        safe_files = {p: c for p, c in files.items() if not _is_truncated(c)}
        if not safe_files:
            logger.warning(
                f"[commit] все {len(files)} файлов содержат маркеры обрезки — коммит отменён (project {project.id})"
            )
            return None
        if len(safe_files) < len(files):
            skipped = set(files) - set(safe_files)
            logger.warning(f"[commit] обрезанные файлы исключены из коммита: {skipped}")

        connector = project.connectors.order_by('created_at').first()
        if not connector:
            return None

        # Эвристика: первая строка ответа как сообщение коммита
        first_line = assistant_text.split('\n')[0].strip().lstrip('#').strip()
        commit_msg = first_line[:200] if first_line else f"AI: {len(safe_files)} файл(ов)"
        if not commit_msg:
            commit_msg = f"AI: {len(safe_files)} файл(ов)"
        if tail_stitched:
            commit_msg += " [ВНИМАНИЕ: хвост файла взят из KB без изменений — проверьте конец файла]"
        elif tail_stitch_failed:
            commit_msg += " [ВНИМАНИЕ: файл обрезан API (~55K лимит) — хвост файла отсутствует, проверьте перед мержем]"

        commit = ProjectCommit.objects.create(
            project=project,
            connector=connector,
            commit_message=commit_msg,
            files=[{'path': p, 'content': c} for p, c in safe_files.items()],
            status='pending',
        )
        logger.info(f"AI-коммит {commit.id} создан для проекта {project.id}: {len(files)} файлов")
        return commit
    except Exception as e:
        logger.error(f"Ошибка extract_commit_from_response: {e}")
        return None
