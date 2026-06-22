import logging
import re

logger = logging.getLogger(__name__)

AI_COMMIT_INSTRUCTION = (
    "Если тебя просят изменить, добавить, создать или показать файлы в проекте — "
    "выводи их содержимое в формате:\n"
    "=== FILE: путь/к/файлу.ext ===\n"
    "<содержимое файла>\n"
    "=== END FILE ===\n"
    "Это правило действует и когда пользователь просит «дай полный файл», "
    "«покажи исправленный X», «напечатай файл с изменениями» — "
    "всегда выводи ПОЛНОЕ содержимое файла в этом формате без сокращений. "
    "СТРОГО ЗАПРЕЩЕНО добавлять любые комментарии-заглушки вместо кода: "
    "«...остальной код...», «...не показан для краткости...», «# ...», "
    "«# (далее весь полный файл...)», «# остальные методы без изменений», "
    "«// ... rest of code ...» и любые аналогичные сокращения — "
    "пользователю нужен файл целиком чтобы применить изменения одним кликом.\n"
    "Можно выводить несколько файлов подряд. "
    "Заканчивай вывод файлов маркером: === END RESPONSE ==="
)

# Паттерны обрезки которые модель добавляет вместо реального кода
_TRUNCATION_RE = re.compile(
    r'^\s*(?:#|//|/\*)\s*'
    r'(?:\.\.\.|далее|остальн|rest of|not shown|omitted|продолжение|'
    r'Объём файла|полный файл|без изменений|unchanged|remaining)',
    re.IGNORECASE | re.MULTILINE,
)


def _is_truncated(content: str) -> bool:
    """Возвращает True если файл содержит маркеры обрезки модели."""
    return bool(_TRUNCATION_RE.search(content))


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
    """
    try:
        from studio.agents.blocks import parse_file_blocks
        from .models import ProjectCommit

        files, _ = parse_file_blocks(assistant_text)
        if not files:
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
