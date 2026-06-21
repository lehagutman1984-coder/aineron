"""
Persistent Memory — ядро системы долговременной памяти.

build_memory_context()         — собирает блок памяти для system-prompt
get_history_with_compression() — умная замена [:20]: сжимает старые сообщения через DeepSeek
estimate_tokens()              — быстрая оценка токенов без tiktoken
"""
from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING

_HTML_RE = re.compile(r'<[^>]+')

if TYPE_CHECKING:
    from aitext.models import Chat

logger = logging.getLogger(__name__)

# Оценка: ~0.40 символа на токен (кириллица ≈2–3 симв./токен, лат. ≈4–5; берём консервативно)
_CHARS_PER_TOKEN = 0.40

# Контекстные окна популярных моделей (токены)
_CONTEXT_WINDOWS: dict[str, int] = {
    'gpt-4o':               128_000,
    'gpt-4o-mini':          128_000,
    'gpt-4.1':              128_000,
    'claude-sonnet':        200_000,
    'claude-opus':          200_000,
    'claude-haiku':         200_000,
    'deepseek-v3':           64_000,
    'deepseek-r1':           64_000,
    'gemini-2.0-flash':   1_000_000,
    'gemini-1.5':         1_000_000,
    'llama':                128_000,
    'qwen':                 128_000,
    'mistral':               32_000,
    '_default':              32_000,
}

# Параметры сжатия
RECENT_WINDOW = 20        # сообщений сохраняем verbatim (не сжимаем)
SUMMARY_TRIGGER = 30      # при >30 сообщений запускаем суммаризацию
COMPRESS_THRESHOLD = 0.70 # сжимаем если история > 70% контекстного окна
MAX_MEMORY_FACTS = 40     # максимум фактов в system-prompt


def estimate_tokens(text: str) -> int:
    """Быстрая оценка числа токенов без tiktoken."""
    if not text:
        return 0
    return max(1, int(len(text) * _CHARS_PER_TOKEN))


def _get_context_window(model_name: str | None) -> int:
    if not model_name:
        return _CONTEXT_WINDOWS['_default']
    model_lower = (model_name or '').lower()
    for key, window in _CONTEXT_WINDOWS.items():
        if key != '_default' and key in model_lower:
            return window
    return _CONTEXT_WINDOWS['_default']


def build_memory_context(user, chat: 'Chat') -> str:
    """
    Возвращает строку для инжекции в system-prompt перед историей.
    Пустая строка если память отключена или нечего добавить.
    """
    from aitext.models import UserMemory, ChatSummary

    # Глобальный тоггл (CustomUser.memory_enabled)
    if not getattr(user, 'memory_enabled', True):
        return ''

    # Per-chat тоггл (Chat.settings['memory_enabled'])
    chat_settings = getattr(chat, 'settings', None) or {}
    if not chat_settings.get('memory_enabled', True):
        return ''

    parts: list[str] = []

    # 1. Факты о пользователе (до MAX_MEMORY_FACTS активных, закреплённые первыми)
    memories = list(
        UserMemory.objects
        .filter(user=user, is_active=True)
        .order_by('-is_pinned', '-created_at')[:MAX_MEMORY_FACTS]
    )
    if memories:
        lines = '\n'.join(f'- [{m.get_category_display()}] {m.content}' for m in memories)
        parts.append(f'Долговременная память о пользователе:\n{lines}')

    # 2. Резюме последних 3 чатов (кроме текущего)
    try:
        past_summaries = list(
            ChatSummary.objects
            .filter(chat__user=user)
            .exclude(chat=chat)
            .select_related('chat')
            .order_by('-updated_at')[:3]
        )
        for s in reversed(past_summaries):
            date_str = f"{s.updated_at.day} {s.updated_at.strftime('%b %Y')}" if hasattr(s.updated_at, 'strftime') else ''
            label = f'[Прошлая сессия, {date_str}]' if date_str else '[Прошлая сессия]'
            parts.append(f'{label}: {s.summary_text[:500]}')
    except Exception as e:
        logger.warning(f'[memory] build_memory_context past_summaries error: {e}')

    return '\n\n'.join(parts)


def get_history_with_compression(
    chat: 'Chat',
    exclude_msg_id: int | None = None,
    memory_context: str = '',
    network_prompt: str = '',
) -> tuple[list, str]:
    """
    Умная замена history_qs[:20].

    Возвращает (messages_list, new_rolling_summary).

    Логика:
    - Загружаем ВСЮ историю выполненных сообщений
    - Оцениваем токены
    - Если история + overhead <= COMPRESS_THRESHOLD * context_window → берём последние RECENT_WINDOW
    - Если история > порога → сжимаем старые через DeepSeek, оставляем последние RECENT_WINDOW verbatim
    - rolling_summary хранится в ChatSummary.rolling_summary
    """
    from aitext.models import Message, ChatSummary
    from .tasks import get_laozhang_client

    network = chat.network
    context_window = _get_context_window(network.model_name)
    token_threshold = int(context_window * COMPRESS_THRESHOLD)

    # Получаем все завершённые сообщения
    qs = chat.messages.filter(status=Message.Status.COMPLETED)
    if exclude_msg_id:
        qs = qs.exclude(id=exclude_msg_id)
    all_msgs = list(qs.order_by('created_at'))

    # Загружаем текущий rolling_summary
    try:
        chat_summary = ChatSummary.objects.get(chat=chat)
        rolling = chat_summary.rolling_summary or ''
    except ChatSummary.DoesNotExist:
        rolling = ''

    # Быстрый путь: история маленькая — просто берём последние RECENT_WINDOW
    if len(all_msgs) <= RECENT_WINDOW:
        return all_msgs, rolling

    # Считаем токены полной истории
    overhead = (
        estimate_tokens(memory_context)
        + estimate_tokens(network_prompt)
        + estimate_tokens(rolling)
        + 800  # запас на форматирование + ответ
    )
    history_tokens = sum(
        estimate_tokens(_HTML_RE.sub('', m.plain_text or m.content or '')[:4000])
        for m in all_msgs
    )

    if overhead + history_tokens <= token_threshold:
        # Всё помещается в окно — отдаём ВСЮ историю, ничего не теряем.
        return all_msgs, rolling

    # Нужна компрессия: оставляем RECENT_WINDOW, сжимаем остальное
    recent_msgs = all_msgs[-RECENT_WINDOW:]
    to_compress = all_msgs[:-RECENT_WINDOW]

    if not to_compress:
        return recent_msgs, rolling

    # Собираем текст для сжатия
    compress_parts: list[str] = []
    if rolling:
        compress_parts.append(f'[Предыдущее сжатое резюме]:\n{rolling}\n')
    compress_parts.append('[Диалог для сжатия]:')
    for msg in to_compress:
        role_label = 'Пользователь' if msg.role == 'user' else 'Ассистент'
        text = _HTML_RE.sub('', msg.plain_text or msg.content or '')[:2000]
        compress_parts.append(f'{role_label}: {text}')
    compress_input = '\n'.join(compress_parts)

    compression_system = (
        'Ты система управления контекстом диалога. '
        'Сожми предоставленный диалог в связное резюме на 150-250 слов. '
        'Сохрани: все принятые решения и выводы, ключевые факты о пользователе '
        '(имя, профессия, проект, предпочтения), незакрытые вопросы и задачи, '
        'технические детали: стек, архитектура, ошибки. '
        'Не сохраняй: светские фразы, повторяющиеся вопросы, вводные слова. '
        'Пиши на том же языке что и диалог. '
        'Выдай только резюме — без заголовков и вступления.'
    )

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model='deepseek-v3',
            messages=[
                {'role': 'system', 'content': compression_system},
                {'role': 'user', 'content': compress_input[:6000]},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        new_rolling = resp.choices[0].message.content.strip()
        logger.info(f'[memory] chat={chat.id}: compressed {len(to_compress)} msgs → rolling_summary')
    except Exception as e:
        logger.warning(f'[memory] compression failed for chat {chat.id}: {e}')
        new_rolling = rolling  # не трогаем при ошибке

    return recent_msgs, new_rolling


def update_rolling_summary(chat: 'Chat', new_rolling: str) -> None:
    """Сохраняет rolling_summary в ChatSummary (upsert)."""
    from aitext.models import ChatSummary
    try:
        cs, _ = ChatSummary.objects.get_or_create(
            chat=chat,
            defaults={'summary_text': '', 'rolling_summary': new_rolling},
        )
        if cs.rolling_summary != new_rolling:
            cs.rolling_summary = new_rolling
            cs.save(update_fields=['rolling_summary', 'updated_at'])
    except Exception as e:
        logger.warning(f'[memory] update_rolling_summary error for chat {chat.id}: {e}')
