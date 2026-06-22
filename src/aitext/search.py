"""
Sprint 5.3 — Knowledge intelligence: гибридный FTS+вектор поиск по базе знаний.
Sprint 6.1 — hybrid_search: RRF-слияние FTS + вектор на уровне чанков.

Точки входа:
  search_knowledge(project, query, top_n) -> list[ProjectFile]  — Sprint 5.3 (файловый уровень)
  hybrid_search(project, queries, top_k, restrict_file_ids) -> list[dict]  — Sprint 6.1 (чанковый уровень, RRF)

Флаг: PROJECT_FILE_SEARCH=1 — включает гибридный поиск в search_knowledge.
      PROJECT_HYBRID_SEARCH=1 — включает RRF-пайплайн hybrid_search.
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


def hybrid_search(project, queries, top_k: int = 12,
                  restrict_file_ids=None) -> list[dict]:
    """Sprint 6.1: RRF-слияние FTS (файловый) + вектор (чанковый).

    queries: str | list[str] — один или несколько запросов (Sprint 6.2 expansion).
    restrict_file_ids: list[int] | None — ограничить поиск (Sprint 6.5 two-level).

    Алгоритм:
      FTS ранжирует файлы → все чанки файла получают FTS-ранг файла.
      Вектор ранжирует чанки напрямую.
      RRF: score(chunk) = Σ_queries [ 1/(k+rank_fts) + 1/(k+rank_vec) ]
      Возвращает top_k чанков по убыванию RRF-скора.

    Каждый элемент результата: {'file_id', 'chunk_index', 'content', 'score'}.
    """
    from django.db import connection as _conn

    if isinstance(queries, str):
        queries = [queries]
    queries = [q for q in queries if q and q.strip()]
    if not queries:
        return []

    rrf_k = int(getattr(settings, 'PROJECT_RRF_K', 60))

    rrf_scores = {}       # (file_id, chunk_index) -> float
    chunk_content = {}    # (file_id, chunk_index) -> str

    for query in queries:

        # ── FTS: file-level → chunk expansion ────────────────────────────────
        try:
            sv = SearchVector('extracted_text', config='russian')
            sq = SearchQuery(query, config='russian', search_type='websearch')

            from aitext.models import ProjectFile as _PF
            fts_qs = _PF.objects.filter(
                project=project, status='ready', enabled=True,
            ).exclude(extracted_text='')
            if restrict_file_ids is not None:
                fts_qs = fts_qs.filter(id__in=restrict_file_ids)

            fts_files = list(
                fts_qs.annotate(rank=SearchRank(sv, sq))
                .filter(rank__gt=0)
                .order_by('-rank')
                .values_list('id', flat=True)[:top_k]
            )

            if fts_files:
                placeholders = ','.join(['%s'] * len(fts_files))
                with _conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT file_id, chunk_index, content
                        FROM aitext_projectchunk
                        WHERE project_id = %s AND chunk_index >= 0
                          AND file_id IN ({placeholders})
                        ORDER BY file_id, chunk_index
                        """,
                        [project.id, *fts_files],
                    )
                    fts_chunks_by_file = {}
                    for file_id, chunk_index, content in cur.fetchall():
                        fts_chunks_by_file.setdefault(file_id, []).append((chunk_index, content))

                for fts_rank, fid in enumerate(fts_files):
                    for chunk_index, content in fts_chunks_by_file.get(fid, []):
                        key = (fid, chunk_index)
                        chunk_content[key] = content
                        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (rrf_k + fts_rank)
        except Exception as e:
            logger.warning(f'[hybrid_search] FTS failed for query "{query[:40]}": {e}')

        # ── Vector candidates ─────────────────────────────────────────────────
        try:
            from .embeddings import vector_search_candidates
            vec_candidates = vector_search_candidates(
                project, query, top_n=top_k, restrict_file_ids=restrict_file_ids,
            )
            for vec_rank, c in enumerate(vec_candidates):
                key = (c['file_id'], c['chunk_index'])
                chunk_content[key] = c['content']
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (rrf_k + vec_rank)
        except Exception as e:
            logger.warning(f'[hybrid_search] vector search failed for query "{query[:40]}": {e}')

    if not rrf_scores:
        return []

    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: -rrf_scores[k])
    return [
        {
            'file_id': fid,
            'chunk_index': ci,
            'content': chunk_content.get((fid, ci), ''),
            'score': rrf_scores[(fid, ci)],
        }
        for fid, ci in sorted_keys[:top_k]
    ]
