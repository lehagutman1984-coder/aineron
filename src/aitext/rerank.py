"""
Sprint 6.3 — Cross-Encoder reranking (CPU, lazy singleton).

Retrieve-wide (top-50) → rerank-narrow (top-15).
Модель: cross-encoder/ms-marco-MiniLM-L-6-v2 (~80 МБ, CPU, бесплатно).

Флаг: PROJECT_RERANK=1 — включает реранкинг.
При недоступности пакета/модели — грациозный no-op (возвращает входной список без изменений).
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_cross_encoder = None   # ленивый синглтон
_load_attempted = False


def _get_cross_encoder():
    """Загружает модель один раз при первом вызове (ленивая инициализация)."""
    global _cross_encoder, _load_attempted
    if _load_attempted:
        return _cross_encoder
    _load_attempted = True
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        model_name = getattr(settings, 'PROJECT_RERANK_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        _cross_encoder = CrossEncoder(model_name)
        logger.info(f'[6.3] CrossEncoder loaded: {model_name}')
    except ImportError:
        logger.warning('[6.3] sentence-transformers not installed — reranking disabled')
    except Exception as e:
        logger.warning(f'[6.3] CrossEncoder load failed: {e}')
    return _cross_encoder


def rerank(query: str, candidates: list[dict], top_k: int = None) -> list[dict]:
    """Переранжирует кандидатов cross-encoder'ом, возвращает top_k.

    candidates: list[dict] с ключом 'content'
    При ошибке или недоступности модели — возвращает кандидатов в исходном порядке.
    """
    if not candidates:
        return candidates

    if top_k is None:
        top_k = int(getattr(settings, 'PROJECT_RERANK_TOPK', 15))

    model = _get_cross_encoder()
    if model is None:
        return candidates[:top_k]

    try:
        pairs = [(query, c['content']) for c in candidates]
        scores = model.predict(pairs)
        ranked = sorted(zip(scores, candidates), key=lambda x: -x[0])
        return [c for _, c in ranked[:top_k]]
    except Exception as e:
        logger.warning(f'[6.3] rerank predict failed: {e}')
        return candidates[:top_k]
