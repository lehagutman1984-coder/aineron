"""
i18n-словари Telegram-бота (GLOBAL_EXPANSION_PLAN.md §4.6).

JSON-словари (не gettext) — тот же формат и LLM-пайплайн, что и у
frontend/messages/*.json, единообразие с веб-переводом. Плейсхолдеры —
Python str.format(), НЕ ICU (у бота нет плюралов/gender, упрощаем).

aineron.ru (INTL_MODE=0): resolve_language() всегда возвращает 'ru' —
from_user.language_code игнорируется. Это доказуемый no-op: поведение
бота на .ru не меняется ни для одного пользователя независимо от того,
какой язык у него в Telegram.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / 'locales'
DICT_LOCALES = ('ru', 'en', 'fa', 'tr')
DEFAULT_LOCALE = 'ru'

# Локали, которые resolve_language() может выбрать пользователю международного
# бота. 'ru' сюда намеренно не входит — план явно исключает русский с aineron.net,
# СНГ-аудиторию обслуживает aineron.ru.
INTL_LOCALES = ('en', 'fa', 'tr')
INTL_DEFAULT_LOCALE = 'en'


def _flatten(obj: dict, prefix: str = '') -> dict:
    out = {}
    for k, v in obj.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@lru_cache(maxsize=None)
def _load(locale: str) -> dict:
    """Плоский словарь {'namespace.key': 'значение'} — JSON на диске вложенный
    (namespace-объекты), как frontend/messages/*.json, для читаемости."""
    path = LOCALES_DIR / f'{locale}.json'
    if not path.exists():
        return {}
    return _flatten(json.loads(path.read_text(encoding='utf-8')))


def t(key: str, lang: str = DEFAULT_LOCALE, **kwargs) -> str:
    """Строка по ключу с fallback на ru, если перевод/ключ отсутствует."""
    locale = lang if lang in DICT_LOCALES else DEFAULT_LOCALE
    value = _load(locale).get(key)
    if value is None:
        value = _load(DEFAULT_LOCALE).get(key)
    if value is None:
        logger.warning('telegram_bot i18n: missing key %s', key)
        return key
    if not kwargs:
        return value
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError):
        logger.warning('telegram_bot i18n: bad format args for %s', key)
        return value


def resolve_language(tg_user, from_user) -> str:
    """
    tg_user — telegram_bot.models.TelegramUser | None (может отсутствовать,
    например на /start до привязки аккаунта).
    from_user — aiogram-объект (message.from_user / callback.from_user),
    источник Telegram-локали клиента (from_user.language_code).
    """
    from django.conf import settings
    if not getattr(settings, 'INTL_MODE', False):
        return DEFAULT_LOCALE

    explicit = getattr(tg_user, 'language', '') if tg_user is not None else ''
    if explicit in INTL_LOCALES:
        return explicit

    code = (getattr(from_user, 'language_code', '') or '').split('-')[0].lower()
    if code in INTL_LOCALES:
        return code
    return INTL_DEFAULT_LOCALE
