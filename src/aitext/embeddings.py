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


def vector_search_candidates(project, query: str, top_n: int = 50,
                              restrict_file_ids=None) -> list[dict]:
    """Sprint 6.1: Семантический поиск — возвращает ранжированный список кандидатов.

    Каждый кандидат: {'file_id', 'chunk_index', 'content', 'distance'}.
    restrict_file_ids: list[int] | None — ограничить поиск файлами (6.5 two-level).
    Чанки с chunk_index=-1 (summary) исключаются.
    """
    from .tasks import get_laozhang_client

    if not query or not query.strip():
        return []

    client = get_laozhang_client()
    model = _get_embed_model()

    q_emb = _get_query_embedding(query, model, client)
    if q_emb is None:
        return []

    q_str = '[' + ','.join(str(round(v, 7)) for v in q_emb) + ']'

    try:
        with connection.cursor() as cur:
            if restrict_file_ids:
                placeholders = ','.join(['%s'] * len(restrict_file_ids))
                cur.execute(
                    f"""
                    SELECT file_id, chunk_index, content, embedding <=> %s::vector AS distance
                    FROM aitext_projectchunk
                    WHERE project_id = %s AND embedding IS NOT NULL AND chunk_index >= 0
                      AND file_id IN ({placeholders})
                    ORDER BY distance
                    LIMIT %s
                    """,
                    [q_str, project.id, *restrict_file_ids, top_n],
                )
            else:
                cur.execute(
                    """
                    SELECT file_id, chunk_index, content, embedding <=> %s::vector AS distance
                    FROM aitext_projectchunk
                    WHERE project_id = %s AND embedding IS NOT NULL AND chunk_index >= 0
                    ORDER BY distance
                    LIMIT %s
                    """,
                    [q_str, project.id, top_n],
                )
            rows = cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка vector_search_candidates для проекта {project.id}: {e}")
        return []

    return [
        {'file_id': r[0], 'chunk_index': r[1], 'content': r[2], 'distance': float(r[3])}
        for r in rows
    ]


def vector_search(project, query: str, top_k: int = None) -> str:
    """Семантический поиск по чанкам проекта (exact cosine scan per-project).

    Обёртка над vector_search_candidates — контракт существующих вызовов сохраняется.
    При PROJECT_EMBED_CACHE=1 кэширует эмбеддинг запроса (Redis, 24ч).
    """
    if top_k is None:
        top_k = int(getattr(settings, 'PROJECT_TOP_K', 6))

    candidates = vector_search_candidates(project, query, top_n=top_k)
    if not candidates:
        return ''

    return '\n...\n'.join(c['content'] for c in candidates)


def embed_file_summary(file) -> bool:
    """Sprint 6.5: генерирует summary файла через дешёвую LLM и эмбеддит его.

    Summary сохраняется в ProjectFile.summary (TextField).
    Эмбеддинг summary хранится как ProjectChunk с chunk_index=-1.
    Возвращает True при успехе.
    """
    from .tasks import get_laozhang_client
    from django.db import connection as _conn

    text = file.extracted_text or ''
    if not text.strip():
        return False

    client = get_laozhang_client()
    model = _get_embed_model()

    # 1. Generate summary via cheap LLM
    summary_model = getattr(settings, 'PROJECT_EXPAND_MODEL', 'gpt-4o-mini')
    try:
        prompt = (
            f"File: {file.filename or 'unknown'}\n\n"
            f"{text[:6000]}"
        )
        resp = client.chat.completions.create(
            model=summary_model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Write a concise summary (150-200 words) of this file: '
                        'its purpose, key entities, and main functionality. '
                        'Be factual and specific.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=250,
            temperature=0.2,
        )
        summary_text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f'[6.5] embed_file_summary: LLM failed for file {file.id}: {e}')
        return False

    # 2. Embed the summary
    try:
        emb_resp = client.embeddings.create(input=[summary_text], model=model)
        emb = emb_resp.data[0].embedding
    except Exception as e:
        logger.error(f'[6.5] embed_file_summary: embedding failed for file {file.id}: {e}')
        return False

    emb_str = '[' + ','.join(str(round(v, 7)) for v in emb) + ']'

    # 3. Save summary text to ProjectFile
    try:
        from .models import ProjectFile
        ProjectFile.objects.filter(pk=file.pk).update(summary=summary_text)
    except Exception as e:
        logger.warning(f'[6.5] embed_file_summary: could not save summary text for file {file.id}: {e}')

    # 4. Store embedding as chunk_index=-1 (upsert)
    try:
        with _conn.cursor() as cur:
            cur.execute(
                'DELETE FROM aitext_projectchunk WHERE file_id = %s AND chunk_index = -1',
                [file.id],
            )
            cur.execute(
                """
                INSERT INTO aitext_projectchunk
                    (project_id, file_id, chunk_index, content, token_count, embedding)
                VALUES (%s, %s, -1, %s, %s, %s::vector)
                """,
                [file.project_id, file.id, summary_text,
                 math.ceil(len(summary_text.split()) / _WORDS_PER_TOKEN), emb_str],
            )
    except Exception as e:
        logger.error(f'[6.5] embed_file_summary: DB insert failed for file {file.id}: {e}')
        return False

    logger.info(f'[6.5] File {file.id} summary embedded ({len(summary_text)} chars)')
    return True


def file_level_search(project, query: str, top_files: int = 5) -> list:
    """Sprint 6.5: Уровень 1 — поиск по summary-эмбеддингам файлов.

    Возвращает список ProjectFile, отсортированных по близости к запросу.
    Использует chunk_index=-1 как маркер summary-чанка.
    """
    from .tasks import get_laozhang_client
    from .models import ProjectFile

    if not query or not query.strip():
        return []

    client = get_laozhang_client()
    model = _get_embed_model()

    q_emb = _get_query_embedding(query, model, client)
    if q_emb is None:
        return []

    q_str = '[' + ','.join(str(round(v, 7)) for v in q_emb) + ']'

    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (file_id) file_id
                FROM aitext_projectchunk
                WHERE project_id = %s AND chunk_index = -1 AND embedding IS NOT NULL
                ORDER BY file_id, embedding <=> %s::vector
                LIMIT %s
                """,
                [project.id, q_str, top_files],
            )
            file_ids = [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f'[6.5] file_level_search failed for project {project.id}: {e}')
        return []

    if not file_ids:
        return []

    files_by_id = {f.id: f for f in ProjectFile.objects.filter(id__in=file_ids)}
    return [files_by_id[fid] for fid in file_ids if fid in files_by_id]
