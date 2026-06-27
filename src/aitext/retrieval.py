"""
Sprint 6.1 — Adaptive top_k + Conversation-aware search query building.
Sprint 6.2 — Query expansion (LLM → N variants, Redis cache).
Sprint 6.4 — @file/@web directive parser.

Единая точка «как формируется поисковый запрос, его ширина и явный контекст».
"""

import hashlib
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# ── Маркеры типа запроса для adaptive top_k ──────────────────────────────────
_BROAD_MARKERS = re.compile(
    r'\b(посмотри|проанализируй|обзор|overview|весь|all|billing|анализ|расскажи|explain|summarize|summary)\b',
    re.IGNORECASE,
)
_NARROW_MARKERS = re.compile(
    r'\b(где|where|how|как|find|найди|покажи|show)\s+\w+',
    re.IGNORECASE,
)
_PATH_RE = re.compile(r'[\w./\-]+\.\w{1,6}')   # path-like string with extension


def adaptive_top_k(query: str) -> int:
    """Эвристика для выбора top_k по типу запроса (без вызова LLM).

    Широкий вопрос (обзор / длинный) → 20; узкий / путь → 8; иначе → дефолт из settings.
    """
    default = int(getattr(settings, 'PROJECT_TOP_K', 12))
    if not query:
        return default

    q = query.strip()
    # Narrow: short + specific identifier/path
    if len(q) < 60 and _PATH_RE.search(q):
        return 8
    if _NARROW_MARKERS.search(q) and len(q) < 80:
        return 8
    # Broad: explicit review markers or long query
    if _BROAD_MARKERS.search(q) or len(q) > 200:
        return 20
    return default


def build_search_query(project, user_message: str, conv_window: int = None, current_msg_id: int | None = None) -> str:
    """Conversation-aware поисковый запрос: конкатенация последних N user-сообщений.

    Берёт последние conv_window сообщений role='user' из последнего чата проекта,
    конкатенирует с текущим запросом. Суммарная длина ограничена 1500 символами.
    current_msg_id: ID текущего user-сообщения — исключается точно по ID (если известен).
    """
    if conv_window is None:
        conv_window = int(getattr(settings, 'PROJECT_CONV_WINDOW', 4))

    if not user_message:
        return user_message

    try:
        from aitext.models import Message
        qs = Message.objects.filter(chat__project=project, role='user').order_by('-created_at')
        if current_msg_id is not None:
            qs = qs.exclude(id=current_msg_id)
            limit = conv_window
        else:
            limit = conv_window + 1  # +1 потому что текущее может уже быть сохранено
        recent = qs.values_list('content', flat=True)[:limit]

        context_parts = []
        total = 0
        CAP = 1500
        for msg in reversed(list(recent)):
            if not msg:
                continue
            if current_msg_id is None and msg.strip() == user_message.strip():
                continue  # fallback dedup когда ID неизвестен
            available = CAP - total - len(user_message)
            if available <= 0:
                break
            snippet = msg[:available]
            context_parts.append(snippet)
            total += len(snippet)

        if context_parts:
            context_str = ' '.join(context_parts)
            combined = f"{context_str} {user_message}"
            return combined[:CAP + len(user_message)]
    except Exception as e:
        logger.warning(f'[6.1] build_search_query failed: {e}')

    return user_message


def expand_query(query: str) -> list[str]:
    """Sprint 6.2: LLM-генерация вариантов запроса, Redis-кэш по sha256(query).

    Возвращает список [original, var1, var2, ...] длиной ≤ PROJECT_EXPAND_N+1.
    При ошибке — плавная деградация: возвращает [query].
    """
    if not query or not query.strip():
        return [query]

    try:
        from django.core.cache import cache as _cache
        digest = hashlib.sha256(query.encode()).hexdigest()
        cache_key = f'qexp:{digest}'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        cache_key = None
        _cache = None

    try:
        from aitext.tasks import get_laozhang_client
        client = get_laozhang_client()
        model = getattr(settings, 'PROJECT_EXPAND_MODEL', 'gpt-4o-mini')
        n = int(getattr(settings, 'PROJECT_EXPAND_N', 3))

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        f'Generate {n} alternative phrasings of the user search query. '
                        'Output one per line, no numbering, no explanations. '
                        'Preserve the original language.'
                    ),
                },
                {'role': 'user', 'content': query},
            ],
            max_tokens=200,
            temperature=0.4,
        )
        text = resp.choices[0].message.content.strip()
        variants = [ln.strip() for ln in text.split('\n') if ln.strip()][:n]
        result = [query] + variants

        if cache_key and _cache is not None:
            try:
                _cache.set(cache_key, result, 86400)
            except Exception:
                pass

        return result
    except Exception as e:
        logger.warning(f'[6.2] expand_query failed: {e}')
        return [query]


# ── 6.4: @file/@web directive parser ─────────────────────────────────────────

_FILE_DIRECTIVE = re.compile(r'@file\s+([\w./\-]+\S*)', re.IGNORECASE)
_WEB_DIRECTIVE = re.compile(r'@web\b', re.IGNORECASE)


def parse_context_directives(text: str) -> dict:
    """Парсит директивы @file <path> и @web из пользовательского запроса.

    Возвращает:
        {
            'files': list[str],   # пути из @file
            'web': bool,          # True если есть @web
            'clean_query': str,   # запрос с вырезанными директивами
        }
    """
    if not text:
        return {'files': [], 'web': False, 'clean_query': text}

    files = _FILE_DIRECTIVE.findall(text)
    web = bool(_WEB_DIRECTIVE.search(text))

    # Remove directives from query
    clean = _FILE_DIRECTIVE.sub('', text)
    clean = _WEB_DIRECTIVE.sub('', clean)
    clean = re.sub(r'\s{2,}', ' ', clean).strip()

    return {'files': files, 'web': web, 'clean_query': clean}
