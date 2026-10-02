"""
Опциональный прокси для исходящих запросов aiogram к api.telegram.org.

2026-10-02: прямой доступ к api.telegram.org с продакшен-сервера aineron.ru
(Hostkey RU) нестабилен — наблюдалась выборочная блокировка/фильтрация,
похоже на фильтрацию для российских IP (то проходит, то нет). Чтобы не
терять сообщения бота, весь трафик aiogram можно завернуть через уже
существующий прокси на aineron.net (используется также для
TAVILY_PROXY_URL/OPENROUTER_PROXY_URL по той же причине — обход
гео-ограничений для RU-сервера).

Безопасный дефолт: TELEGRAM_PROXY_URL не задан -> get_bot_session()
возвращает None, и aiogram создаёт обычную сессию без прокси, как раньше.
"""
from django.conf import settings


def get_bot_session():
    """AiohttpSession с прокси, если settings.TELEGRAM_PROXY_URL задан, иначе
    None (aiogram.Bot сам создаст сессию по умолчанию при session=None)."""
    proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', '')
    if not proxy_url:
        return None
    from aiogram.client.session.aiohttp import AiohttpSession
    return AiohttpSession(proxy=proxy_url)
