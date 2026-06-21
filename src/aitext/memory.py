"""
Persistent Memory — ядро системы долговременной памяти.

build_memory_context()         — собирает блок памяти для system-prompt (Redis-кэш, 5 мин)
get_history_with_compression() — read-only: recent msgs + существующий summary (без LLM)
should_compress()              — дешёвая проверка нужна ли фоновая компрессия
normalize_fact()               — нормализация текста для дедупликации (B3)
estimate_tokens()              — оценка токенов language-aware (B10)
invalidate_memory_cache()      — сброс Redis-кэша при мутации фактов (B11)
update_rolling_summary()       — атомарный upsert с select_for_update (B4)
"""
from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aitext.models import Chat

logger = logging.getLogger(__name__)

_HTML_RE = re.compile(r'<[^>]+>')

# Параметры сжатия
RECENT_WINDOW = 20         # сообщений сохраняем verbatim (не сжимаем)
COMPRESS_TRIGGER = 30      # при >30 сообщений запускаем суммаризацию
COMPRESS_THRESHOLD = 0.70  # сжимаем если история > 70% контекстного окна
MAX_MEMORY_FACTS = 40      # максимум фактов в system-prompt
EXTRACT_EVERY_N = 3        # каждые N ответов извлекаем факты
MEMORY_CACHE_TTL = 300     # 5 мин TTL для Redis-кэша контекста памяти

# Контекстные окна популярных моделей (токены)
_CONTEXT_WINDOWS: dict[str, int] = {
    'gpt-4o':              128_000,
    'gpt-4o-mini':         128_000,
    'gpt-4.1':             128_000,
    'claude-sonnet':       200_000,
    'claude-opus':         200_000,
    'claude-haiku':        200_000,
    'deepseek-v3':          64_000,
    'deepseek-r1':          64_000,
    'gemini-2.0-flash':  1_000_000,
    'gemini-1.5':        1_000_000,
    'llama':               128_000,
    'qwen':                128_000,
    'mistral':              32_000,
    '_default':             32_000,
}


def normalize_fact(text: str) -> str:
    """
    Нормализует текст факта для дедупликации.
    Пробелы СХЛОПЫВАЮТСЯ (не вырезаются), пунктуация убирается.
    'Любит Go' и 'Любитgo' теперь РАЗНЫЕ ключи — коллизия не ложная.
    """
    t = (text or '').lower().strip()
    t = re.sub(r'[^\w\s]', '', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:255]


def estimate_tokens(text: str) -> int:
    """
    Быстрая оценка токенов без tiktoken.
    Language-aware: кириллица ~2.5 симв/токен, латиница ~4.0 симв/токен.
    """
    if not text:
        return 0
    cyr = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c.lower() == 'ё')
    cyr_frac = cyr / max(1, len(text))
    chars_per_token = 2.5 * cyr_frac + 4.0 * (1 - cyr_frac)
    return max(1, int(len(text) / chars_per_token))


def _get_context_window(model_name: str | None) -> int:
    if not model_name:
        return _CONTEXT_WINDOWS['_default']
    model_lower = (model_name or '').lower()
    for key, window in _CONTEXT_WINDOWS.items():
        if key != '_default' and key in model_lower:
            return window
    return _CONTEXT_WINDOWS['_default']


def _facts_cache_key(user_id: int) -> str:
    return f'memfacts:{user_id}'


def invalidate_memory_cache(user_id: int) -> None:
    """Сбрасывает Redis-кэш фактов памяти при изменении фактов пользователя."""
    try:
        from django.core.cache import cache
        cache.delete(_facts_cache_key(user_id))
    except Exception:
        pass


def build_memory_context(user, chat: 'Chat') -> str:
    """
    Возвращает строку для инжекции в system-prompt перед историей.

    Факты пользователя кэшируются в Redis (memfacts:{user_id}, 5 мин) — они
    не зависят от текущего чата, поэтому общий ключ безопасен.

    Резюме прошлых сессий запрашиваются ВСЕГДА СВЕЖО (chat-dependent: зависят
    от того, какой чат открыт) — один лёгкий индексированный запрос.

    Пустая строка если память отключена или нечего добавить.
    """
    from aitext.models import UserMemory, ChatSummary
    from django.core.cache import cache

    if not getattr(user, 'memory_enabled', True):
        return ''

    chat_settings = getattr(chat, 'settings', None) or {}
    if not chat_settings.get('memory_enabled', True):
        return ''

    # --- Факты: кэшируем per-user (стабильны между чатами) ---
    facts_key = _facts_cache_key(user.id)
    facts_block = cache.get(facts_key)
    if facts_block is None:
        memories = list(
            UserMemory.objects
            .filter(user=user, is_active=True)
            .order_by('-is_pinned', '-created_at')[:MAX_MEMORY_FACTS]
        )
        if memories:
            lines = '\n'.join(f'- [{m.get_category_display()}] {m.content}' for m in memories)
            facts_block = f'Долговременная память о пользователе:\n{lines}'
        else:
            facts_block = ''
        cache.set(facts_key, facts_block, MEMORY_CACHE_TTL)

    # --- Резюме прошлых сессий: всегда свежо (один лёгкий запрос) ---
    parts: list[str] = []
    if facts_block:
        parts.append(facts_block)

    try:
        past_summaries = list(
            ChatSummary.objects
            .filter(chat__user=user)
            .exclude(chat=chat)
            .select_related('chat')
            .order_by('-updated_at')[:3]
        )
        for s in reversed(past_summaries):
            text = (s.summary_text or s.rolling_summary or '').strip()
            if not text:
                continue
            dt = s.updated_at
            date_str = f"{dt.day} {dt.strftime('%b %Y')}" if hasattr(dt, 'strftime') else ''
            label = f'[Прошлая сессия, {date_str}]' if date_str else '[Прошлая сессия]'
            parts.append(f'{label}: {text[:500]}')
    except Exception as e:
        logger.warning(f'[memory] build_memory_context past_summaries error: {e}')

    return '\n\n'.join(parts)


def should_compress(chat: 'Chat', exclude_msg_id: int | None = None) -> bool:
    """
    Дешёвая проверка: нужно ли запускать фоновую компрессию.
    Никаких сетевых вызовов — только счётчики в БД.
    """
    from aitext.models import Message, ChatSummary
    qs = chat.messages.filter(status=Message.Status.COMPLETED)
    if exclude_msg_id:
        qs = qs.exclude(id=exclude_msg_id)
    msg_count = qs.count()
    if msg_count < COMPRESS_TRIGGER:
        return False
    try:
        cs = ChatSummary.objects.get(chat=chat)
        # Сжимаем если накопилось RECENT_WINDOW новых сообщений с последнего сжатия
        unsummarized = msg_count - cs.message_count
        return unsummarized >= RECENT_WINDOW
    except ChatSummary.DoesNotExist:
        return True


def get_history_with_compression(
    chat: 'Chat',
    exclude_msg_id: int | None = None,
    memory_context: str = '',
    network_prompt: str = '',
) -> tuple[list, str]:
    """
    Read-only замена history_qs[:20]. Никаких сетевых вызовов.

    Возвращает (messages_list, existing_summary).
    Если нужна компрессия — вызывающий код проверяет should_compress() и
    запускает compress_chat_history.delay(chat.id) в фоне.

    Логика:
    - Загружаем ВСЮ историю выполненных сообщений
    - Читаем готовый summary из ChatSummary (результат фоновой compress_chat_history)
    - Если история + overhead <= COMPRESS_THRESHOLD * context_window → ВСЯ история (B2 fix)
    - Если история > порога → RECENT_WINDOW + существующий summary
    """
    from aitext.models import Message, ChatSummary

    network = chat.network
    context_window = _get_context_window(network.model_name)
    token_threshold = int(context_window * COMPRESS_THRESHOLD)

    qs = chat.messages.filter(status=Message.Status.COMPLETED)
    if exclude_msg_id:
        qs = qs.exclude(id=exclude_msg_id)
    all_msgs = list(qs.order_by('created_at'))

    # Читаем готовое сжатие — rolling или финальное, что есть
    existing_summary = ''
    try:
        cs = ChatSummary.objects.get(chat=chat)
        existing_summary = (cs.rolling_summary or cs.summary_text or '').strip()
    except ChatSummary.DoesNotExist:
        pass

    # Быстрый путь: история маленькая
    if len(all_msgs) <= RECENT_WINDOW:
        return all_msgs, existing_summary

    # Жёсткий потолок: даже если токены «помещаются», O(N) queries взрываются на больших чатах.
    # При >80 сообщений сразу переходим в ветку recent+summary — компрессия должна уже была
    # отработать раньше (COMPRESS_TRIGGER=30), поэтому existing_summary тут почти всегда есть.
    HARD_MSG_CAP = 80
    if len(all_msgs) > HARD_MSG_CAP:
        return all_msgs[-RECENT_WINDOW:], existing_summary

    # Считаем токены
    overhead = (
        estimate_tokens(memory_context)
        + estimate_tokens(network_prompt)
        + estimate_tokens(existing_summary)
        + 800  # запас на форматирование + ответ
    )
    history_tokens = sum(
        estimate_tokens(_HTML_RE.sub('', m.plain_text or m.content or '')[:4000])
        for m in all_msgs
    )

    if overhead + history_tokens <= token_threshold:
        # Всё помещается в окно — возвращаем ВСЮ историю (B2 fix: не обрезаем!)
        return all_msgs, existing_summary

    # Превышаем порог: только свежие + готовый summary
    # Фоновое сжатие запустит вызывающий код через should_compress()
    recent_msgs = all_msgs[-RECENT_WINDOW:]
    return recent_msgs, existing_summary


def update_rolling_summary(chat: 'Chat', new_rolling: str, msg_count: int = 0) -> None:
    """Атомарный upsert rolling_summary с select_for_update против гонок (B4)."""
    from aitext.models import ChatSummary
    from django.db import transaction
    if not new_rolling:
        return
    try:
        with transaction.atomic():
            cs, _ = ChatSummary.objects.select_for_update().get_or_create(
                chat=chat,
                defaults={
                    'summary_text': '',
                    'rolling_summary': new_rolling,
                    'message_count': msg_count,
                },
            )
            changed = cs.rolling_summary != new_rolling
            if changed:
                cs.rolling_summary = new_rolling
            if msg_count and cs.message_count != msg_count:
                cs.message_count = msg_count
                changed = True
            if changed:
                cs.save(update_fields=['rolling_summary', 'message_count', 'updated_at'])
    except Exception as e:
        logger.warning(f'[memory] update_rolling_summary error for chat {chat.id}: {e}')
