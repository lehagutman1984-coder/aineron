"""
Sprint 5.3 — Knowledge intelligence: гибридный FTS+вектор поиск по базе знаний.

Точка входа:
  search_knowledge(project, query, top_n) -> list[ProjectFile]

Флаг: PROJECT_FILE_SEARCH=1 — включает гибридный поиск.
При PROJECT_FILE_SEARCH=0 или выключённом PROJECT_VECTOR_RAG — только FTS.
"""

import logging

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import FloatField, Value
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


def search_knowledge(project, query: str, top_n: int = 10):
    """Гибридный FTS + вектор поиск по файлам базы знаний проекта.

    Возвращает список ProjectFile отсортированный по релевантности.
    Режим:
      - Всегда: Postgres FTS по extracted_text (SearchVector annotated).
      - При PROJECT_VECTOR_RAG=1: семантический поиск (vector_search) по чанкам.
    Дедуп по file_id — побеждает наивысший ранг.
    """
    from aitext.models import ProjectFile

    if not query or not query.strip():
        return list(project.knowledge_files.filter(status='ready', enabled=True).order_by('-created_at')[:top_n])

    # ── FTS (Postgres full-text search) ──────────────────────────────────────
    fts_ids = []
    try:
        sv = SearchVector('extracted_text', config='russian')
        sq = SearchQuery(query, config='russian', search_type='websearch')
        fts_qs = (
            project.knowledge_files
            .filter(status='ready', enabled=True)
            .exclude(extracted_text='')
            .annotate(rank=SearchRank(sv, sq))
            .filter(rank__gt=0)
            .order_by('-rank')[:top_n]
        )
        fts_ids = list(fts_qs.values_list('id', flat=True))
    except Exception as e:
        logger.warning(f"FTS search error for project {project.id}: {e}")

    # ── Семантический поиск (вектор) ──────────────────────────────────────────
    vec_ids = []
    if getattr(settings, 'PROJECT_VECTOR_RAG', False) and getattr(settings, 'PROJECT_FILE_SEARCH', False):
        try:
            from django.db import connection
            from .embeddings import _get_embed_model, _get_query_embedding, _get_embed_dims
            from .tasks import get_laozhang_client

            client = get_laozhang_client()
            model = _get_embed_model()
            q_emb = _get_query_embedding(query, model, client)
            if q_emb:
                q_str = '[' + ','.join(str(round(v, 7)) for v in q_emb) + ']'
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT file_id
                        FROM aitext_projectchunk
                        WHERE project_id = %s AND embedding IS NOT NULL
                        ORDER BY MIN(embedding <=> %s::vector)
                        LIMIT %s
                        """,
                        [project.id, q_str, top_n],
                    )
                    vec_ids = [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.warning(f"Vector search error for project {project.id}: {e}")

    # ── Дедуп и ранжирование ─────────────────────────────────────────────────
    seen_ids = []
    for file_id in fts_ids:
        if file_id not in seen_ids:
            seen_ids.append(file_id)
    for file_id in vec_ids:
        if file_id not in seen_ids:
            seen_ids.append(file_id)

    if not seen_ids:
        return []

    # Возвращаем в порядке ранжирования
    files_by_id = {f.id: f for f in ProjectFile.objects.filter(id__in=seen_ids)}
    return [files_by_id[fid] for fid in seen_ids if fid in files_by_id]
