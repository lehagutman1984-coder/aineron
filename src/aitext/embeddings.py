"""
Sprint 4.1 — Vector RAG.
Sprint 5.7 — Smart chunking + env-driven limits.

Функции:
  chunk_text(text)               → list[str]  — нарезка по словам (лексика, без структуры)
  smart_chunk(text, filename)    → list[str]  — нарезка по структуре кода (Sprint 5.7.3)
  embed_chunks(file)             → int         — создаёт/обновляет ProjectChunk + эмбеддинги
  vector_search(project, query, top_k) → str — семантический поиск (exact cosine scan per project)

Флаги (из settings.py / .env):
  PROJECT_VECTOR_RAG=1     — включает векторный путь
  PROJECT_SMART_CHUNK=1    — включает умный чанкинг по структуре кода (Sprint 5.7.3)
  PROJECT_EMBED_MODEL      — модель эмбеддингов (default: text-embedding-3-small, 1536 dim)
  PROJECT_EMBED_DIMS       — размерность (1536 по умолчанию)
  PROJECT_CHUNK_SIZE       — размер чанка в символах (default: 500, рекоменд. 1500)
  PROJECT_TOP_K            — кол-во чанков в vector_search (default: 6, рекоменд. 12)
"""

import logging
import math
import os
import re

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

_WORDS_PER_TOKEN = 0.75   # эвристика: 1 слово ≈ 1.33 токена; 1 токен ≈ 0.75 слова

# Regex-границы для умного чанкинга
_PY_BOUNDARY = re.compile(r'\n(?=(?:(?:async )?def |class )\s*\w)')
_JS_BOUNDARY = re.compile(
    r'\n(?=(?:(?:export (?:default )?)?(?:async )?function|(?:export )?class'
    r'|(?:export (?:const|let|var) \w+ ?= ?(?:async )?(?:function|\())'
    r'|(?:module\.exports)))'
)


def chunk_text(text: str) -> list[str]:
    """Нарезает текст на чанки ~PROJECT_CHUNK_SIZE символов с overlap.

    Используется как fallback или когда PROJECT_SMART_CHUNK=0.
    """
    chunk_chars = int(getattr(settings, 'PROJECT_CHUNK_SIZE', 500))
    chunk_words = int(chunk_chars * _WORDS_PER_TOKEN)
    overlap_words = max(1, chunk_words // 10)

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunks.append(' '.join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap_words
        if start < 0:
            start = 0

    return [c for c in chunks if c.strip()]


def _merge_blocks(blocks: list[str], max_chars: int) -> list[str]:
    """Объединяет мелкие блоки до max_chars, большие разбивает."""
    result = []
    current = ''
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) > max_chars:
            if current:
                result.append(current)
                current = ''
            for i in range(0, len(block), max_chars):
                result.append(block[i:i + max_chars])
        elif current and len(current) + len(block) + 2 > max_chars:
            result.append(current)
            current = block
        else:
            current = (current + '\n\n' + block).strip() if current else block
    if current:
        result.append(current)
    return [c for c in result if c.strip()]


def smart_chunk(text: str, filename: str = '') -> list[str]:
    """Sprint 5.7.3: умный чанкинг по структуре кода.

    .py -> по def/class; .ts/.tsx/.js/.jsx -> по function/class/export;
    остальные -> по параграфам (двойной перенос строки).
    Включается флагом PROJECT_SMART_CHUNK=1.
    """
    max_chars = int(getattr(settings, 'PROJECT_CHUNK_SIZE', 500)) * 3
    ext = os.path.splitext(filename)[1].lower() if filename else ''

    if ext == '.py':
        blocks = _PY_BOUNDARY.split(text)
    elif ext in ('.ts', '.tsx', '.js', '.jsx'):
        blocks = _JS_BOUNDARY.split(text)
    else:
        blocks = re.split(r'\n\n+', text)

    return _merge_blocks(blocks, max_chars)


def _get_embed_model():
    return getattr(settings, 'PROJECT_EMBED_MODEL', 'text-embedding-3-small')


def _get_embed_dims():
    return int(getattr(settings, 'PROJECT_EMBED_DIMS', 1536))


def embed_chunks(file) -> int:
    """Эмбеддирует текст файла: нарезает на чанки, вызывает laozhang.ai, сохраняет в БД.

    При PROJECT_SMART_CHUNK=1 используется smart_chunk (по структуре кода).
    Возвращает количество успешно сохранённых чанков.
    """
    from .tasks import get_laozhang_client

    text = file.extracted_text or ''
    if not text.strip():
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    use_smart = getattr(settings, 'PROJECT_SMART_CHUNK', False)
    if use_smart:
        chunks = smart_chunk(text, file.filename or '')
    else:
        chunks = chunk_text(text)

    if not chunks:
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    client = get_laozhang_client()
    model = _get_embed_model()

    try:
        resp = client.embeddings.create(input=chunks, model=model)
        embeddings = [item.embedding for item in resp.data]
    except Exception as e:
        logger.error(f"Ошибка эмбеддингов для файла {file.id}: {e}")
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    if len(embeddings) != len(chunks):
        logger.warning(f"Мисмэтч чанков/эмбеддингов для файла {file.id}: {len(chunks)} vs {len(embeddings)}")

    with connection.cursor() as cur:
        cur.execute('DELETE FROM aitext_projectchunk WHERE file_id = %s', [file.id])

    saved = 0
    with connection.cursor() as cur:
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            token_count = math.ceil(len(chunk.split()) / _WORDS_PER_TOKEN)
            emb_str = '[' + ','.join(str(round(v, 7)) for v in emb) + ']'
            try:
                cur.execute(
                    """
                    INSERT INTO aitext_projectchunk
                        (project_id, file_id, chunk_index, content, token_count, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s::vector)
                    """,
                    [file.project_id, file.id, idx, chunk, token_count, emb_str],
                )
                saved += 1
            except Exception as e:
                logger.error(f"Ошибка INSERT chunk {idx} для файла {file.id}: {e}")

    file.embed_status = 'done' if saved > 0 else 'error'
    file.save(update_fields=['embed_status'])
    logger.info(f"Файл {file.id}: {saved}/{len(chunks)} чанков эмбеддировано (smart={use_smart})")
    return saved


def _get_query_embedding(query: str, model: str, client) -> list[float] | None:
    """Возвращает эмбеддинг запроса. При PROJECT_EMBED_CACHE=1 кэширует в Redis на 24ч."""
    use_cache = getattr(settings, 'PROJECT_EMBED_CACHE', False)
    cache_key = None

    if use_cache:
        import hashlib
        from django.core.cache import cache
        digest = hashlib.sha256(f"{model}:{query}".encode()).hexdigest()
        cache_key = f'qemb:{digest}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        resp = client.embeddings.create(input=[query], model=model)
        emb = resp.data[0].embedding
    except Exception as e:
        logger.error(f"Ошибка эмбеддинга запроса: {e}")
        return None

    if use_cache and cache_key:
        try:
            from django.core.cache import cache as _cache
            _cache.set(cache_key, emb, 86400)  # 24ч
        except Exception:
            pass

    return emb


def vector_search(project, query: str, top_k: int = None) -> str:
    """Семантический поиск по чанкам проекта (exact cosine scan per-project).

    Возвращает склеенный текст top_k наиболее релевантных чанков.
    При PROJECT_EMBED_CACHE=1 кэширует эмбеддинг запроса (Redis, 24ч).
    """
    from .tasks import get_laozhang_client

    if top_k is None:
        top_k = int(getattr(settings, 'PROJECT_TOP_K', 6))

    if not query or not query.strip():
        return ''

    client = get_laozhang_client()
    model = _get_embed_model()

    q_emb = _get_query_embedding(query, model, client)
    if q_emb is None:
        return ''

    q_str = '[' + ','.join(str(round(v, 7)) for v in q_emb) + ']'

    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT content
                FROM aitext_projectchunk
                WHERE project_id = %s AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [project.id, q_str, top_k],
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка vector_search для проекта {project.id}: {e}")
        return ''

    if not rows:
        return ''

    return '\n...\n'.join(row[0] for row in rows)
