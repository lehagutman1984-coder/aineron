"""
Sprint 4.1 — Vector RAG.

Функции:
  chunk_text(text)         → list[str]   — нарезка текста на чанки ~500 токенов, overlap 50
  embed_chunks(file)       → int          — создаёт/обновляет ProjectChunk + эмбеддинги через laozhang.ai
  vector_search(project, query, top_k) → str — семантический поиск (exact cosine scan per project)

Флаги (из settings.py):
  PROJECT_VECTOR_RAG=1     — включает векторный путь в build_project_knowledge_context
  PROJECT_EMBED_MODEL      — модель эмбеддингов (default: text-embedding-3-small, 1536 dim)
  PROJECT_EMBED_DIMS       — размерность (1536 по умолчанию)

Лексика (`_retrieve_relevant_chunks` из tasks.py) остаётся как fallback при:
  - embed_status != 'done'
  - пустой векторной выдаче
"""

import logging
import math

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500          # токенов на чанк (приблизительно, через кол-во слов)
CHUNK_OVERLAP = 50        # overlap в токенах

_WORDS_PER_TOKEN = 0.75   # эвристика: 1 слово ≈ 1.33 токена; 1 токен ≈ 0.75 слова
_CHUNK_WORDS = int(CHUNK_SIZE * _WORDS_PER_TOKEN)
_OVERLAP_WORDS = int(CHUNK_OVERLAP * _WORDS_PER_TOKEN)


def chunk_text(text: str) -> list[str]:
    """Нарезает текст на чанки ~CHUNK_SIZE токенов с overlap CHUNK_OVERLAP."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_WORDS, len(words))
        chunks.append(' '.join(words[start:end]))
        if end >= len(words):
            break
        start = end - _OVERLAP_WORDS
        if start < 0:
            start = 0

    return [c for c in chunks if c.strip()]


def _get_embed_model():
    return getattr(settings, 'PROJECT_EMBED_MODEL', 'text-embedding-3-small')


def _get_embed_dims():
    return int(getattr(settings, 'PROJECT_EMBED_DIMS', 1536))


def embed_chunks(file) -> int:
    """Эмбеддирует текст файла: нарезает на чанки, вызывает laozhang.ai, сохраняет в БД.

    Возвращает количество успешно сохранённых чанков.
    """
    from .tasks import get_laozhang_client

    text = file.extracted_text or ''
    if not text.strip():
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    chunks = chunk_text(text)
    if not chunks:
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    client = get_laozhang_client()
    model = _get_embed_model()

    try:
        # Батчевый запрос (laozhang поддерживает списки)
        resp = client.embeddings.create(input=chunks, model=model)
        embeddings = [item.embedding for item in resp.data]
    except Exception as e:
        logger.error(f"Ошибка эмбеддингов для файла {file.id}: {e}")
        file.embed_status = 'error'
        file.save(update_fields=['embed_status'])
        return 0

    if len(embeddings) != len(chunks):
        logger.warning(f"Мисмэтч чанков/эмбеддингов для файла {file.id}: {len(chunks)} vs {len(embeddings)}")

    # Удаляем старые чанки файла
    with connection.cursor() as cur:
        cur.execute('DELETE FROM aitext_projectchunk WHERE file_id = %s', [file.id])

    saved = 0
    with connection.cursor() as cur:
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            # Считаем токены приблизительно через слова
            token_count = math.ceil(len(chunk.split()) / _WORDS_PER_TOKEN)
            # Вектор передаём как строку в формате pgvector '[...]'
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
    logger.info(f"Файл {file.id}: {saved}/{len(chunks)} чанков эмбеддировано")
    return saved


def vector_search(project, query: str, top_k: int = 6) -> str:
    """Семантический поиск по чанкам проекта (exact cosine scan per-project).

    Возвращает склеенный текст top_k наиболее релевантных чанков.
    """
    from .tasks import get_laozhang_client

    if not query or not query.strip():
        return ''

    client = get_laozhang_client()
    model = _get_embed_model()

    try:
        resp = client.embeddings.create(input=[query], model=model)
        q_emb = resp.data[0].embedding
    except Exception as e:
        logger.error(f"Ошибка эмбеддинга запроса для проекта {project.id}: {e}")
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
