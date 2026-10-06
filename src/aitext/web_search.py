"""
Sprint 6.4 — @web явный контекст + общий веб-поиск (Tavily Search API).

WEB_SEARCH_ACCURACY_PLAN.md, шаги 0/1/2/6 (2026-10-06):
- _tavily_search() — единственная реализация HTTP-вызова к Tavily + дедуп по
  домену + буст RU-источников (шаг 0: раньше было 3 независимые копии этого
  вызова в tasks.py/web_search.py; шаг 2: дедуп/буст). call_web_search() и
  _web_search_chunks() в aitext/tasks.py теперь тонкие обёртки над этим модулем.
- rewrite_search_query() — рерайт запроса с учётом истории диалога +
  needs_search/time_sensitive флаги (шаг 1). Один короткий вызов gpt-4o-mini
  (та же роль "дешёвый фоновый LLM-вызов", что уже использует
  tasks.py::translate_to_english). Fail-open: любая ошибка — needs_search=True
  и query = последнее сообщение дословно, то есть поведение ДО этого шага.
  Рерайт может только улучшить поиск, никогда не должен его сломать.

Экспортирует:
    web_search(query, max_results=5, time_sensitive=False, log_prefix="") -> str
    rewrite_search_query(recent_messages, log_prefix="") -> dict
    format_as_chunks(items) -> list[dict]           — для deep research
    format_results_as_text(items) -> str            — для обычного чата
    _tavily_search(query, max_results, time_sensitive, log_prefix) -> list[dict]
"""

import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Шаг 2: небольшой boost-список авторитетных RU-источников — поднимаем выше в
# выдаче, если попали в топ Tavily. Намеренно короткий и только "поднимаем",
# НЕ деним — deny-список без данных golden-set рискует выкинуть единственный
# источник с ответом (WEB_SEARCH_ACCURACY_PLAN.md, раздел 2, шаг 2).
_RU_BOOST_DOMAINS = {
    'cbr.ru', 'consultant.ru', 'garant.ru', 'nalog.gov.ru',
    'gosuslugi.ru', 'kremlin.ru', 'minfin.gov.ru',
}


def _domain(url: str) -> str:
    m = re.match(r'https?://(?:www\.)?([^/]+)', url or '')
    return m.group(1).lower() if m else ''


def _dedupe_and_boost(items: list) -> list:
    """Не больше 2 результатов с одного домена; приоритетные RU-источники — выше
    (стабильная сортировка — порядок внутри группы Tavily не меняется)."""
    seen_domains = {}
    deduped = []
    for item in items:
        domain = _domain(item.get('url', ''))
        count = seen_domains.get(domain, 0)
        if domain and count >= 2:
            continue
        seen_domains[domain] = count + 1
        deduped.append(item)

    deduped.sort(key=lambda it: 0 if _domain(it.get('url', '')) in _RU_BOOST_DOMAINS else 1)
    return deduped


def _tavily_search(query: str, max_results: int = 6, time_sensitive: bool = False,
                    log_prefix: str = "") -> list:
    """
    Единственная реализация HTTP-вызова к Tavily. Возвращает список сырых
    результатов (dict: title/content/url/published_date) — уже с дедупом по
    домену и RU-буст сортировкой применёнными. Пустой список при отсутствии
    ключа/ошибке/0 результатов.
    """
    api_key = getattr(settings, 'TAVILY_API_KEY', '')
    if not api_key:
        logger.error(f"{log_prefix}TAVILY_API_KEY не задан в .env")
        return []
    if not query:
        return []

    proxy_url = getattr(settings, 'TAVILY_PROXY_URL', '')
    payload = {
        'api_key': api_key,
        'query': query[:400],
        'search_depth': 'basic',
        'max_results': max_results,
        'include_answer': False,
    }
    if time_sensitive:
        # Шаг 1: для time-sensitive вопросов (курсы, новости) сужаем окно
        # свежести у Tavily вместо того чтобы полагаться только на текст запроса.
        payload['time_range'] = 'week'
        payload['topic'] = 'news'

    try:
        r = requests.post(
            'https://api.tavily.com/search',
            json=payload,
            timeout=12,
            proxies={'https': proxy_url} if proxy_url else None,
        )
        r.raise_for_status()
        items = r.json().get('results', [])
        if not items:
            logger.warning(f"{log_prefix}Tavily вернул 0 результатов")
            return []
        items = _dedupe_and_boost(items)
        logger.info(f"{log_prefix}Tavily OK: {len(items)} результатов (после дедупа)")
        return items
    except Exception as e:
        logger.error(f"{log_prefix}Tavily FAILED: {e}")
        return []


def format_results_as_text(items: list, snippet_len: int = 250) -> str:
    """Формат для обычного чата (tasks.py::call_web_search) — без префикса @web."""
    if not items:
        return ''
    lines = []
    for i, item in enumerate(items, 1):
        parts = [
            f"[{i}] {item.get('title', '')}",
            item.get('content', '')[:snippet_len],
            f"URL: {item.get('url', '')}",
        ]
        if item.get('published_date'):
            parts.append(f"Дата: {item['published_date']}")
        lines.append('\n'.join(p for p in parts if p))
    return '\n\n'.join(lines)


def format_as_chunks(items: list) -> list:
    """Для deep research (замена дублированного форматирования в _web_search_chunks)."""
    return [
        {'text': f"{it.get('title', '')}\n{it.get('content', '')[:300]}",
         'source': it.get('url', ''), 'kind': 'web'}
        for it in items
    ]


def web_search(query: str, max_results: int = 5, time_sensitive: bool = False,
                log_prefix: str = "") -> str:
    """Поиск через Tavily для директивы @web (Projects) и AI-задач бота.
    Публичная сигнатура не изменилась для существующих вызывающих —
    time_sensitive/log_prefix необязательные, по умолчанию прежнее поведение."""
    if not query:
        return ''
    items = _tavily_search(query, max_results=max_results, time_sensitive=time_sensitive,
                            log_prefix=log_prefix)
    if not items:
        return ''
    return '[Результаты веб-поиска (@web)]\n\n' + format_results_as_text(items)


# ── Шаг 1: рерайт запроса с учётом истории + needs_search/time_sensitive ──────

_REWRITE_SYSTEM_PROMPT = (
    "Ты помогаешь подготовить поисковый запрос для веб-поиска в AI-чате. "
    "По истории диалога определи: "
    "1) самостоятельный поисковый запрос, понятный без контекста (разверни "
    "местоимения и ссылки на предыдущие реплики, например 'а в евро?' после "
    "вопроса про доллары → 'курс доллара к евро'); "
    "2) нужен ли вообще веб-поиск для ответа на последнее сообщение "
    "(needs_search) — false для благодарностей, просьб переписать/объяснить "
    "код выше, общих вопросов не требующих свежих данных из интернета; "
    "3) зависит ли ответ от свежести данных на сегодня — курсы, новости, "
    "погода, актуальные события (time_sensitive).\n"
    "Ответь СТРОГО JSON без markdown и пояснений: "
    '{"query": "...", "needs_search": true/false, "time_sensitive": true/false}'
)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text')
    return ''


def rewrite_search_query(recent_messages: list, log_prefix: str = "") -> dict:
    """
    Шаг 1 (WEB_SEARCH_ACCURACY_PLAN.md): рерайт последнего вопроса пользователя
    с учётом истории диалога + needs_search/time_sensitive классификация.
    Один короткий вызов gpt-4o-mini с жёстким таймаутом 4с (не наследует
    дефолтный 90с таймаут чат-провайдера — это служебный вызов ДО основной
    генерации, не должен раздувать время до первого токена).

    Fail-open: любая ошибка (таймаут, невалидный JSON, сбой апстрима) —
    возвращает needs_search=True и query = последнее сообщение дословно,
    то есть ТЕКУЩЕЕ поведение до этого шага. Рерайт может только улучшить
    поиск, никогда не должен его сломать.
    """
    last_user_text = ""
    for m in reversed(recent_messages):
        if m.get('role') == 'user':
            last_user_text = _extract_text(m.get('content', ''))
            if last_user_text:
                break

    fallback = {'query': last_user_text or 'информация', 'needs_search': True, 'time_sensitive': False}
    if not last_user_text:
        return fallback

    try:
        from aitext.tasks import get_laozhang_client
        client = get_laozhang_client()

        history_lines = []
        for m in recent_messages[-6:]:
            role = m.get('role', '')
            text = _extract_text(m.get('content', ''))
            if text:
                history_lines.append(f"{role}: {text[:300]}")
        history_text = '\n'.join(history_lines) or last_user_text

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": history_text},
            ],
            temperature=0.1,
            max_tokens=200,
            timeout=4,
        )
        raw = completion.choices[0].message.content.strip()
        # Страховка на случай если апстрим всё же обернёт ответ в markdown-код
        # несмотря на инструкцию "строго JSON без markdown".
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(match.group(0) if match else raw)

        query = str(data.get('query') or '').strip()[:400] or last_user_text
        needs_search = bool(data.get('needs_search', True))
        time_sensitive = bool(data.get('time_sensitive', False))
        logger.info(
            f"{log_prefix}Рерайт поиска: '{last_user_text[:60]}' → '{query[:60]}' "
            f"(needs_search={needs_search}, time_sensitive={time_sensitive})"
        )
        return {'query': query, 'needs_search': needs_search, 'time_sensitive': time_sensitive}
    except Exception as e:
        logger.warning(f"{log_prefix}Рерайт поиска не удался, используем исходный запрос дословно: {e}")
        return fallback
