import logging

logger = logging.getLogger(__name__)

AI_COMMIT_INSTRUCTION = (
    "Если тебя просят изменить, добавить, создать или показать файлы в проекте — "
    "выводи их содержимое в формате:\n"
    "=== FILE: путь/к/файлу.ext ===\n"
    "<содержимое файла>\n"
    "=== END FILE ===\n"
    "Это правило действует и когда пользователь просит «дай полный файл», "
    "«покажи исправленный X», «напечатай файл с изменениями» — "
    "всегда выводи ПОЛНОЕ содержимое файла в этом формате без сокращений, "
    "НЕ ДОБАВЛЯЙ комментарии типа «...остальной код...» или «...не показан для краткости...» — "
    "пользователю нужен файл целиком чтобы применить изменения одним кликом.\n"
    "Можно выводить несколько файлов подряд. "
    "Заканчивай вывод файлов маркером: === END RESPONSE ==="
)


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

        connector = project.connectors.order_by('created_at').first()
        if not connector:
            return None

        # Эвристика: первая строка ответа как сообщение коммита
        first_line = assistant_text.split('\n')[0].strip().lstrip('#').strip()
        commit_msg = first_line[:200] if first_line else f"AI: {len(files)} файл(ов)"
        if not commit_msg:
            commit_msg = f"AI: {len(files)} файл(ов)"

        commit = ProjectCommit.objects.create(
            project=project,
            connector=connector,
            commit_message=commit_msg,
            files=[{'path': p, 'content': c} for p, c in files.items()],
            status='pending',
        )
        logger.info(f"AI-коммит {commit.id} создан для проекта {project.id}: {len(files)} файлов")
        return commit
    except Exception as e:
        logger.error(f"Ошибка extract_commit_from_response: {e}")
        return None
