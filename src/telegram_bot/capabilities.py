"""Фиче-флаги и определение поддержки Bot API 9.3+/10.1 (TELEGRAM_SUPREMACY_PLAN, S0).

Определить возможности клиента Telegram ботам недоступно, поэтому каждая
супер-фича управляется env-флагом (см. config/settings.py) и дополнительно
проверяется на поддержку установленной версией aiogram через bot_supports().
Любой вызов новой фичи обязан иметь fallback на старый путь (см. notify.py).
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Соответствие фича → (env-флаг в settings, имя метода aiogram Bot)
_FEATURES = {
    'native_streaming':    ('TG_NATIVE_STREAMING',    'send_message_draft'),
    'rich_messages':       ('TG_RICH_MESSAGES',       'send_rich_message'),
    'stars_subscriptions': ('TG_STARS_SUBSCRIPTIONS', 'create_invoice_link'),
    'business':            ('TG_BUSINESS',            'get_business_connection'),
    'affiliate':           ('TG_AFFILIATE',           None),
    'gifts':               ('TG_GIFTS',               'send_gift'),
    'topics':              ('TG_TOPICS',              'create_forum_topic'),
    'managed_bots':        ('TG_MANAGED_BOTS',        'get_managed_bot_token'),
    'styled_buttons':      ('TG_STYLED_BUTTONS',      None),
}


def is_enabled(feature: str) -> bool:
    """Включена ли фича env-флагом. Неизвестная фича = выключена."""
    entry = _FEATURES.get(feature)
    if not entry:
        return False
    return bool(getattr(settings, entry[0], False))


def bot_supports(bot, method_name: str) -> bool:
    """Поддерживает ли установленная версия aiogram метод Bot API.

    aiogram добавляет методы Bot API как методы Bot — отсутствие метода
    означает, что версия библиотеки старее нужного Bot API.
    """
    if not method_name:
        return True
    return callable(getattr(bot, method_name, None))


def available(feature: str, bot=None) -> bool:
    """Фича включена флагом И (если передан bot) поддерживается aiogram."""
    if not is_enabled(feature):
        return False
    entry = _FEATURES.get(feature)
    if bot is not None and entry and entry[1]:
        if not bot_supports(bot, entry[1]):
            logger.warning(
                f'capabilities: {feature} включена флагом, но aiogram не поддерживает '
                f'{entry[1]} — используется fallback'
            )
            return False
    return True


def enabled_features() -> list:
    """Список включённых фич — для /admin-диагностики и логов старта."""
    return [name for name in _FEATURES if is_enabled(name)]
