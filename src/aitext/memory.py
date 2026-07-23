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
from django.conf import settings

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


def scoped_content_key(text: str, project_id: int | None = None, organization_id: int | None = None) -> str:
    """
    Ключ дедупликации с учётом скоупа памяти (B12).

    Без этого префикса одинаковый по тексту факт в разных проектах (или проект vs
    глобальный) схлопывался в ОДНУ строку по общему UniqueConstraint(user, content_key) —
    факт молча "перескакивал" между проектами при повторной экстракции, теряясь для
    одного из них. Префикс делает (user, scope, текст) — а не только (user, текст) —
    единицей дедупликации, что и требует UniqueConstraint(user, content_key).
    """
    base = normalize_fact(text)
    if not base:
        return ''
    if project_id:
        prefix = f'proj{project_id}:'
    elif organization_id:
        prefix = f'org{organization_id}:'
    else:
        prefix = ''
    return (prefix + base)[:255]


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


# U2 — Total Recall: интент «вопрос о прошлом» (только тогда лезем в recall,
# чтобы не раздувать контекст и не жечь эмбеддинг на каждый запрос)
import re as _re

_RECALL_RE = _re.compile(
    r'(помнишь|мы (уже )?(обсуждали|говорили|решали|разбирали)|'
    r'в прошл(ый|ом) раз|ранее (ты|мы|я)|напомни|о ч[её]м мы|'
    r'что мы (решили|выбрали|договорились)|'
    r'do you remember|we (discussed|talked about)|last time)',
    _re.IGNORECASE,
)


def is_recall_query(text: str) -> bool:
    """Похоже ли сообщение на вопрос о прошлых разговорах."""
    return bool(text and _RECALL_RE.search(text))


def _org_facts_block(user) -> str:
    """U1 — общая память организаций пользователя (кэш 5 мин).

    Факты пишут owner/editor через /dashboard/organization/ или /account/memory/;
    видят все члены во всех своих чатах (командный контекст: стек, процессы, сроки).
    """
    from django.core.cache import cache
    from aitext.models import UserMemory

    cache_key = f'memfacts:org:{user.id}'
    block = cache.get(cache_key)
    if block is not None:
        return block

    org_ids = list(user.org_memberships.values_list('organization_id', flat=True))
    owned = list(user.owned_organizations.values_list('id', flat=True))
    org_ids = list({*org_ids, *owned})
    if not org_ids:
        cache.set(cache_key, '', MEMORY_CACHE_TTL)
        return ''

    memories = list(
        UserMemory.objects
        .filter(organization_id__in=org_ids, is_active=True)
        .select_related('organization')
        .order_by('-is_pinned', '-created_at')[:15]
    )
    if not memories:
        cache.set(cache_key, '', MEMORY_CACHE_TTL)
        return ''

    lines = '\n'.join(f'- [{m.organization.name}] {m.content}' for m in memories)
    block = f'Память команды (общие факты организации):\n{lines}'
    cache.set(cache_key, block, MEMORY_CACHE_TTL)
    return block


def invalidate_org_memory_cache(user_ids) -> None:
    """Сброс кэша орг-памяти для списка пользователей (при изменении фактов)."""
    from django.core.cache import cache
    for uid in user_ids:
        cache.delete(f'memfacts:org:{uid}')


def build_memory_context(user, chat: 'Chat', user_message: str = '') -> str:
    """
    Возвращает строку для инжекции в system-prompt перед историей.

    user_message (U2): текущий вопрос — при recall-интенте («помнишь…»)
    добавляется семантический поиск по резюме всех чатов пользователя.

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

    # --- Глобальные факты: кэшируем per-user (стабильны между чатами) ---
    # U1: в глобальный блок идут только факты без project-скоупа
    facts_key = _facts_cache_key(user.id)
    facts_block = cache.get(facts_key)
    if facts_block is None:
        memories = list(
            UserMemory.objects
            .filter(user=user, is_active=True, project__isnull=True,
                    organization__isnull=True)
            .order_by('-is_pinned', '-created_at')[:MAX_MEMORY_FACTS]
        )
        if memories:
            lines = '\n'.join(f'- [{m.get_category_display()}] {m.content}' for m in memories)
            facts_block = f'Долговременная память о пользователе:\n{lines}'
        else:
            facts_block = ''
        cache.set(facts_key, facts_block, MEMORY_CACHE_TTL)

    parts: list[str] = []
    if facts_block:
        parts.append(facts_block)

    # --- U1: факты текущего проекта (приоритетный блок, лёгкий запрос) ---
    if getattr(settings, 'MEMORY_PROJECT_SCOPE', True) and getattr(chat, 'project_id', None):
        try:
            proj_memories = list(
                UserMemory.objects
                .filter(user=user, project_id=chat.project_id, is_active=True)
                .order_by('-is_pinned', '-created_at')[:20]
            )
            if proj_memories:
                lines = '\n'.join(f'- {m.content}' for m in proj_memories)
                parts.append(
                    f'Контекст проекта «{chat.project.name}» (важнее общих фактов):\n{lines}'
                )
        except Exception as e:
            logger.warning(f'[memory] project facts error: {e}')

    # --- U1: общая память организации (факты команды) ---
    if getattr(settings, 'MEMORY_ORG_SCOPE', True):
        try:
            org_block = _org_facts_block(user)
            if org_block:
                parts.append(org_block)
        except Exception as e:
            logger.warning(f'[memory] org facts error: {e}')

    recent_chat_ids = {chat.id}
    try:
        past_summaries = list(
            ChatSummary.objects
            .filter(chat__user=user)
            .exclude(chat=chat)
            .select_related('chat')
            .order_by('-updated_at')[:getattr(settings, 'MEMORY_PAST_SESSIONS', 5)]
        )
        for s in reversed(past_summaries):
            text = (s.summary_text or s.rolling_summary or '').strip()
            if not text:
                continue
            recent_chat_ids.add(s.chat_id)
            dt = s.updated_at
            date_str = f"{dt.day} {dt.strftime('%b %Y')}" if hasattr(dt, 'strftime') else ''
            label = f'[Прошлая сессия, {date_str}]' if date_str else '[Прошлая сессия]'
            parts.append(f'{label}: {text[:500]}')
    except Exception as e:
        logger.warning(f'[memory] build_memory_context past_summaries error: {e}')

    # --- U2: Total Recall — семантический поиск по всей истории при интенте ---
    if (user_message and getattr(settings, 'RECALL_CHATS', True)
            and is_recall_query(user_message)):
        try:
            from aitext.embeddings import recall_search
            hits = recall_search(user, user_message, top_k=3,
                                 exclude_chat_ids=recent_chat_ids)
            for h in hits:
                dt = h['updated_at']
                date_str = f"{dt.day} {dt.strftime('%b %Y')}" if hasattr(dt, 'strftime') else ''
                title = (h['title'] or 'Без названия')[:60]
                parts.append(
                    f'[Из прошлых разговоров, {date_str}, «{title}»]: '
                    f'{h["summary"][:450]}'
                )
        except Exception as e:
            logger.warning(f'[memory] recall error: {e}')

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


def update_rolling_summary(
    chat: 'Chat',
    new_rolling: str,
    msg_count: int = 0,
    last_compressed_message_id: int | None = None,
) -> None:
    """Атомарный upsert rolling_summary с select_for_update против гонок (B4).

    C2: принимает last_compressed_message_id — ID последнего сжатого сообщения;
    используется в compress_chat_history для истинной идемпотентности.
    """
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
                    'last_compressed_message_id': last_compressed_message_id,
                },
            )
            update_fields: list[str] = []
            if cs.rolling_summary != new_rolling:
                cs.rolling_summary = new_rolling
                update_fields.append('rolling_summary')
            if msg_count and cs.message_count != msg_count:
                cs.message_count = msg_count
                update_fields.append('message_count')
            if (
                last_compressed_message_id is not None
                and cs.last_compressed_message_id != last_compressed_message_id
            ):
                cs.last_compressed_message_id = last_compressed_message_id
                update_fields.append('last_compressed_message_id')
            if update_fields:
                update_fields.append('updated_at')
                cs.save(update_fields=update_fields)
    except Exception as e:
        logger.warning(f'[memory] update_rolling_summary error for chat {chat.id}: {e}')
