"""
Sprint 6.4 — @web явный контекст: Tavily Search API.

Экспортирует:
    web_search(query, max_results=5) -> str   — форматированные сниппеты с источниками
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def web_search(query: str, max_results: int = 5) -> str:
    """Поиск через Tavily. Возвращает форматированные сниппеты или '' при ошибке/без ключа."""
    api_key = getattr(settings, 'TAVILY_API_KEY', '')
    if not api_key or not query:
        return ''

    try:
        r = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': api_key,
                'query': query[:400],
                'search_depth': 'basic',
                'max_results': max_results,
                'include_answer': False,
            },
            timeout=12,
        )
        r.raise_for_status()
        items = r.json().get('results', [])
        if not items:
            return ''

        lines = []
        for i, item in enumerate(items, 1):
            parts = [
                f"[{i}] {item.get('title', '')}",
                item.get('content', '')[:250],
                f"URL: {item.get('url', '')}",
            ]
            if item.get('published_date'):
                parts.append(f"Дата: {item['published_date']}")
            lines.append('\n'.join(p for p in parts if p))

        return '[Результаты веб-поиска (@web)]\n\n' + '\n\n'.join(lines)
    except Exception as e:
        logger.warning(f'[6.4] web_search failed: {e}')
        return ''
