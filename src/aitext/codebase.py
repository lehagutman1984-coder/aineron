"""
Sprint 5.2 — Codebase intelligence.

@codebase: semantic search over repo-synced files.
repo_tree_map: compact structural overview (paths-only, ≤3 KB) for LLM context.

Both functions are no-ops when the project has no connector or no repo files.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_TREE_MAP_MAX_CHARS = 3_000
_CODEBASE_TOP_K = 8


def repo_tree_map(project) -> str:
    """Return a compact list of repo file paths (≤3 KB) for LLM structural awareness."""
    from aitext.models import ProjectFile
    paths = list(
        ProjectFile.objects
        .filter(project=project, source='repo', status='ready', enabled=True)
        .order_by('filename')
        .values_list('filename', flat=True)[:200]
    )
    if not paths:
        return ''
    text = '\n'.join(paths)
    if len(text) > _TREE_MAP_MAX_CHARS:
        text = text[:_TREE_MAP_MAX_CHARS] + '\n... (truncated)'
    return text


def codebase_search(project, query: str, top_k: int = _CODEBASE_TOP_K) -> list:
    """Return list of ProjectFile objects most relevant to query over repo files.

    When PROJECT_VECTOR_RAG=1: semantic vector search filtered to source='repo'.
    Otherwise: fallback lexical search over extracted_text.
    """
    from django.conf import settings
    from aitext.models import ProjectFile

    base_qs = ProjectFile.objects.filter(
        project=project, source='repo', status='ready', enabled=True,
    ).exclude(extracted_text='')

    if not base_qs.exists():
        return []

    if getattr(settings, 'PROJECT_VECTOR_RAG', False):
        try:
            from aitext.embeddings import vector_search
            return vector_search(project, query, top_k=top_k, source_filter='repo')
        except Exception as e:
            logger.warning('[codebase_search] vector_search failed, falling back to lexical: %s', e)

    # Lexical fallback: rank by keyword overlap in extracted_text
    q_words = set(query.lower().split())
    results = []
    for pf in base_qs:
        text_lower = (pf.extracted_text or '').lower()
        score = sum(text_lower.count(w) for w in q_words)
        if score > 0:
            results.append((score, pf))

    results.sort(key=lambda x: -x[0])
    return [pf for _, pf in results[:top_k]]


def build_codebase_context(project, query: str) -> str:
    """Build a text block injecting repo-file snippets for LLM context.

    Returns empty string if feature is disabled or no results.
    """
    from django.conf import settings
    if not getattr(settings, 'PROJECT_CODEBASE', False):
        return ''

    files = codebase_search(project, query)
    if not files:
        return ''

    tree = repo_tree_map(project)
    parts = []
    if tree:
        parts.append(f'--- REPO STRUCTURE ---\n{tree}\n--- END REPO STRUCTURE ---')

    for pf in files:
        snippet = (pf.extracted_text or '')[:2_000]
        parts.append(f'--- FILE: {pf.filename} ---\n{snippet}\n--- END FILE ---')

    return '\n\n'.join(parts)
