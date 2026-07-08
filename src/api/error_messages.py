# -*- coding: utf-8 -*-
"""
Локализованные сообщения об ошибках API (/api/v1/*).

USE_I18N=False в проекте — Django gettext не используется нигде в пути
запрос/ответ. Вместо него простой dict-каталог: язык выбирается по
LANGUAGE_CODE инстанса (тот же принцип, что modeltranslation для контента —
aineron.ru → ru, aineron.net при INTL_MODE=1 → en). Ключ — стабильный
идентификатор ошибки, а не сам текст, чтобы одинаковые по смыслу сообщения
в разных вью не разошлись со временем.

Использование:
    from api.error_messages import em
    return Response({"error": em("insufficient_funds")}, status=402)
    return Response({"error": em("max_connectors", limit=3)}, status=400)
"""
from django.conf import settings

# key -> {"ru": "...", "en": "..."}. Заполняется по мере извлечения строк
# из вью (см. GLOBAL_EXPANSION_PLAN.md G2 — коды ошибок API).
MESSAGES: dict[str, dict[str, str]] = {
    # api/views/connectors.py
    "max_connectors_per_project": {"ru": "Максимум 3 коннектора на проект", "en": "Maximum 3 connectors per project"},
    "invalid_connector_type": {"ru": "Тип коннектора: github, gitea, website или rss", "en": "Connector type must be one of: github, gitea, website, rss"},
    "repo_url_required": {"ru": "Укажите URL", "en": "URL is required"},
    "website_rss_disabled": {"ru": "Website/RSS коннекторы отключены", "en": "Website/RSS connectors are disabled"},
    "invalid_url": {"ru": "Некорректный URL", "en": "Invalid URL"},
    "source_already_connected": {"ru": "Этот источник уже подключён", "en": "This source is already connected"},
    "pat_required": {"ru": "Укажите Personal Access Token", "en": "Personal access token is required"},
    "owner_repo_parse_failed": {"ru": "Не удалось разобрать owner/repo из URL", "en": "Could not parse owner/repo from URL"},
    "token_error": {"ru": "Ошибка токена: {e}", "en": "Token error: {e}"},
    "repo_access_error": {"ru": "Ошибка доступа к репозиторию: {e}", "en": "Repository access error: {e}"},
    "path_required": {"ru": "Укажите path", "en": "path is required"},
    "file_read_error": {"ru": "Ошибка чтения файла: {e}", "en": "Error reading file: {e}"},
    "commit_message_required": {"ru": "Укажите сообщение коммита", "en": "Commit message is required"},
    "files_required": {"ru": "Добавьте хотя бы один файл", "en": "At least one file is required"},
    "max_files_per_commit": {"ru": "Максимум 50 файлов на коммит", "en": "Maximum 50 files per commit"},
    "file_missing_path_content": {"ru": "Каждый файл должен содержать path и content", "en": "Each file must include path and content"},
    "commit_already_processed": {"ru": "Коммит уже обработан: {status}", "en": "Commit already processed: {status}"},
    "no_connector_for_push": {"ru": "Нет коннектора для пуша", "en": "No connector configured for push"},
    "pr_mode_disabled": {"ru": "PR-режим отключён (PROJECT_PR_PROPOSALS=0)", "en": "PR mode is disabled (PROJECT_PR_PROPOSALS=0)"},
    "invalid_commit_action": {"ru": "action должен быть push, pr или reject", "en": "action must be push, pr, or reject"},
    "cannot_delete_pending_commit": {"ru": "Нельзя удалить коммит со статусом pending", "en": "Cannot delete a commit with pending status"},

    # studio/views/pipeline.py
    "insufficient_balance": {"ru": "Недостаточно средств на балансе. Пополните баланс.", "en": "Insufficient balance. Please top up your balance."},
    "autofix_limit_reached": {"ru": "Достигнут лимит автоисправлений ({limit}). Опишите проблему вручную.", "en": "Auto-fix limit reached ({limit}). Please describe the issue manually."},
    "empty_code_fragment": {"ru": "Пустой фрагмент", "en": "Code fragment is empty"},
    "invalid_db_mode": {"ru": "Недопустимый режим базы данных", "en": "Invalid database mode"},
    "neon_api_key_required": {"ru": "Требуется Neon API-ключ", "en": "Neon API key is required"},
    "connection_string_required": {"ru": "Требуется строка подключения", "en": "Connection string is required"},
    "dsn_invalid_prefix": {"ru": "DSN должен начинаться с postgresql://", "en": "DSN must start with postgresql://"},
    "schema_creation_error": {"ru": "Ошибка создания схемы: {exc}", "en": "Schema creation failed: {exc}"},
    "database_not_connected": {"ru": "База не подключена", "en": "Database is not connected"},
    "database_not_provisioned": {"ru": "База ещё не провизионирована", "en": "Database has not been provisioned yet"},
    "schema_not_found": {"ru": "Схема {schema} не найдена", "en": "Schema {schema} not found"},
    "dsn_not_configured": {"ru": "DSN не настроен", "en": "DSN is not configured"},
    "psycopg2_not_installed": {"ru": "psycopg2 не установлен", "en": "psycopg2 is not installed"},
    "db_test_not_implemented": {"ru": "Тест для режима {mode} не реализован", "en": "Connectivity test is not implemented for mode {mode}"},
    "export_aineron_only": {"ru": "Экспорт доступен только для режима Aineron. Для Neon/External используйте собственный инструмент БД.", "en": "Export is only available for Aineron mode. For Neon/External, use your own database tooling."},
    "invalid_schema_name": {"ru": "Некорректное имя схемы", "en": "Invalid schema name"},
    "pg_dump_not_found": {"ru": "pg_dump не найден на сервере", "en": "pg_dump was not found on the server"},
    "e2b_unsupported_stack": {"ru": "E2B не поддерживает стек {stack}", "en": "E2B does not support the {stack} stack"},
    "daily_preview_limit_exceeded": {"ru": "Дневной лимит превью ({cap_min} мин/день) исчерпан — использовано {used_min} мин. Лимит обновится завтра.", "en": "Daily preview limit ({cap_min} min/day) exceeded — {used_min} min used. The limit resets tomorrow."},
    "insufficient_balance_preview": {"ru": "Недостаточно средств для запуска превью (нужно {amount})", "en": "Insufficient balance to start preview (requires {amount})"},
    "preview_service_unavailable_dev": {"ru": "preview-service недоступен. Запустите: cd preview-service && uvicorn main:app --port 8001", "en": "Preview service is unavailable. Start it with: cd preview-service && uvicorn main:app --port 8001"},
    "too_many_previews": {"ru": "Слишком много превью", "en": "Too many active previews"},
    "preview_service_unexpected_response": {"ru": "preview-service вернул неожиданный ответ", "en": "Preview service returned an unexpected response"},
    "session_not_found": {"ru": "Сессия не найдена", "en": "Session not found"},
    "empty_message": {"ru": "Пустое сообщение", "en": "Message is empty"},
    "llm_no_response": {"ru": "(нет ответа)", "en": "(no response)"},
    "llm_error": {"ru": "Ошибка LLM: {exc}", "en": "LLM error: {exc}"},
    "project_not_telegram_bot": {"ru": "Проект не является Telegram Bot", "en": "Project is not a Telegram bot"},
    "invalid_bot_token_format": {"ru": "Неверный формат токена. Получите тестовый токен у @BotFather.", "en": "Invalid token format. Get a test token from @BotFather."},
    "preview_service_unavailable": {"ru": "preview-service недоступен", "en": "Preview service is unavailable"},
    "bot_already_running": {"ru": "Этот бот уже запущен в другой сессии. Остановите её перед новым запуском.", "en": "This bot is already running in another session. Stop it before starting a new one."},
    "preview_service_no_session_id": {"ru": "preview-service не вернул session_id", "en": "Preview service did not return a session_id"},
    "bot_token_sandbox_warning": {"ru": "Токен передан в изолированную E2B среду и хранится только в памяти sandbox. Сессия автоматически завершится через 15 мин.", "en": "The token was sent to an isolated E2B environment and is only kept in the sandbox's memory. The session will automatically end after 15 minutes."},
    "file_not_found": {"ru": "Файл не найден", "en": "File not found"},
    "paused_by_user": {"ru": "Пауза пользователем", "en": "Paused by user"},
    "cancelled_by_user": {"ru": "Отменено пользователем", "en": "Cancelled by user"},

    # api/views/project_files.py, deep_research.py, collaborators.py
    "max_files_per_project": {"ru": "Максимум {max_files} файлов на проект", "en": "Maximum {max_files} files per project"},
    "file_missing": {"ru": "Файл не передан", "en": "No file provided"},
    "file_too_large": {"ru": "Файл слишком большой (макс. {size_mb} МБ)", "en": "File too large (max {size_mb} MB)"},
    "file_format_unsupported": {"ru": "Формат {ext} не поддерживается", "en": "Format {ext} is not supported"},
    "file_search_disabled": {"ru": "Поиск по файлам отключён", "en": "File search is disabled"},
    "file_versions_disabled": {"ru": "Версии файлов отключены", "en": "File versions are disabled"},
    "research_not_finished": {"ru": "Исследование ещё не завершено", "en": "Research is not finished yet"},
    "research_chat_no_project": {"ru": "Чат не принадлежит проекту", "en": "Chat does not belong to a project"},
    "research_no_report": {"ru": "Нет отчёта для сохранения", "en": "No report available to save"},
    "collaborator_email_required": {"ru": "Укажите email", "en": "Email is required"},
    "collaborator_role_invalid": {"ru": "role: viewer или editor", "en": "role must be 'viewer' or 'editor'"},
    "collaborator_user_not_found": {"ru": "Пользователь {email} не найден", "en": "User {email} not found"},
    "collaborator_cannot_add_self": {"ru": "Нельзя добавить себя", "en": "You cannot add yourself"},
    "collaborator_already_owner": {"ru": "Пользователь уже является владельцем", "en": "User is already the project owner"},

    # api/views/arena.py, memory.py, tasks.py, files.py, agent.py
    "arena_winner_loser_required": {"ru": "winner_slug и loser_slug обязательны", "en": "winner_slug and loser_slug are required"},
    "arena_winner_loser_same": {"ru": "winner и loser должны быть разными моделями", "en": "Winner and loser must be different models"},
    "arena_compare_chat_ids_required": {"ru": "compare_chat_ids должен содержать хотя бы один chat_id", "en": "compare_chat_ids must contain at least one chat_id"},
    "arena_already_voted": {"ru": "Вы уже голосовали по этому сравнению", "en": "You have already voted on this comparison"},
    "arena_model_not_found": {"ru": "Одна из моделей не найдена", "en": "One of the models was not found"},
    "memory_text_required": {"ru": "text обязателен", "en": "text is required"},
    "memory_org_owner_admin_only": {"ru": "Только owner/admin организации", "en": "Only the organization owner or admin can perform this action"},
    "memory_content_required": {"ru": "content обязателен", "en": "content is required"},
    "memory_fact_id_required": {"ru": "fact_id обязателен", "en": "fact_id is required"},
    "memory_enabled_required": {"ru": "memory_enabled обязателен", "en": "memory_enabled is required"},
    "tasks_run_time_required": {"ru": "Для daily/weekly укажите время запуска (HH:MM, МСК)", "en": "For daily/weekly schedules, specify a run time (HH:MM, Moscow time)"},
    "tasks_weekday_required": {"ru": "Для weekly укажите день недели 0–6 (0 = понедельник)", "en": "For weekly schedules, specify a weekday 0-6 (0 = Monday)"},
    "tasks_cron_fields_required": {"ru": "Cron-выражение должно содержать 5 полей", "en": "The cron expression must contain 5 fields"},
    "tasks_once_via_bot": {"ru": "Разовые задачи создаются в боте: /task", "en": "One-time tasks can only be created via the bot: /task"},
    "tasks_limit_reached_with_limit": {"ru": "Достигнут лимит активных задач по тарифу: {limit}", "en": "Active task limit reached for your plan: {limit}"},
    "tasks_limit_reached": {"ru": "Достигнут лимит активных задач по тарифу", "en": "Active task limit reached for your plan"},
    "tasks_telegram_link_required": {"ru": "Для доставки результата привяжите Telegram в кабинете", "en": "Link your Telegram account in your dashboard to receive the result"},
    "files_rerun_no_source_chat": {"ru": "Эту генерацию нельзя повторить (нет исходного чата).", "en": "This generation cannot be rerun (no source chat)."},
    "files_media_paid_only": {"ru": "Генерация изображений и видео доступна только на платных тарифах.", "en": "Image and video generation is available on paid plans only."},
    "files_insufficient_funds": {"ru": "Недостаточно средств. Нужно {needed}, у вас {have}.", "en": "Insufficient funds. Required: {needed}, available: {have}."},
    "files_upscale_images_only": {"ru": "Апскейл доступен только для изображений.", "en": "Upscaling is only available for images."},
    "files_upscale_paid_only": {"ru": "Апскейл изображений доступен только на платных тарифах.", "en": "Image upscaling is available on paid plans only."},
    "files_variations_no_source_chat": {"ru": "Для этой генерации нельзя создать вариации (нет исходного чата).", "en": "Variations cannot be created for this generation (no source chat)."},
    "files_variations_paid_only": {"ru": "Создание вариаций доступно только на платных тарифах.", "en": "Creating variations is available on paid plans only."},
    "files_insufficient_funds_variations": {"ru": "Недостаточно средств. Нужно {needed} на {count} вариаций, у вас {have}.", "en": "Insufficient funds. Required: {needed} for {count} variations, available: {have}."},
    "files_image_not_found": {"ru": "Изображение не найдено", "en": "Image not found"},
    "files_describe_failed": {"ru": "Не удалось получить описание", "en": "Failed to generate a description"},
    "files_rembg_unavailable": {"ru": "Функция временно недоступна — обновление сервиса. Попробуйте через img2img с промптом «remove background».", "en": "This feature is temporarily unavailable due to a service update. Try img2img with the prompt \"remove background\" instead."},
    "files_access_denied": {"ru": "Доступ запрещён", "en": "Access denied"},
    "files_read_image_failed": {"ru": "Не удалось прочитать изображение: {error}", "en": "Failed to read image: {error}"},
    "files_remove_background_failed": {"ru": "Ошибка удаления фона: {error}", "en": "Background removal failed: {error}"},
    "files_save_failed": {"ru": "Ошибка сохранения: {error}", "en": "Save failed: {error}"},
    "agent_goal_required": {"ru": "goal обязателен", "en": "goal is required"},
    "agent_insufficient_funds": {"ru": "Недостаточно средств: Agent Mode стоит {price}", "en": "Insufficient funds: Agent Mode costs {price}"},
    "agent_project_not_found": {"ru": "Проект не найден", "en": "Project not found"},

    # studio/views/projects.py, aitext/consumers.py
    "email_required": {"ru": "Email обязателен", "en": "Email is required."},
    "user_not_found": {"ru": "Пользователь не найден", "en": "User not found."},
    "no_file": {"ru": "Нет файла", "en": "No file provided."},
    "unknown_model": {"ru": "Неизвестная модель: {model}", "en": "Unknown model: {model}."},
    "agent_models_must_be_object": {"ru": "agent_models должен быть объектом", "en": "agent_models must be an object."},
    "unknown_models": {"ru": "Неизвестные модели: {models}", "en": "Unknown models: {models}."},
    "field_must_be_nonnegative": {"ru": "{field} должен быть неотрицательным числом", "en": "{field} must be a non-negative integer."},
    "insufficient_balance_voice": {"ru": "Недостаточно средств для голосового режима", "en": "Insufficient balance for voice mode."},
    "voice_processing_error": {"ru": "Ошибка обработки голоса", "en": "Voice processing failed."},
}


def em(key: str, **kwargs) -> str:
    lang = "en" if settings.LANGUAGE_CODE == "en" else "ru"
    entry = MESSAGES[key]
    text = entry.get(lang) or entry["ru"]
    return text.format(**kwargs) if kwargs else text
