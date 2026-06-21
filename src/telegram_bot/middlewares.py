import asyncio
import logging
import random
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from asgiref.sync import sync_to_async
from django.core.cache import cache

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 30
_middleware_installed = False


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, 'from_user', None) or data.get('event_from_user')
        if not from_user:
            return await handler(event, data)

        # /start обрабатывается без авторизации — это точка входа
        text = getattr(event, 'text', '') or ''
        if text.startswith('/start'):
            return await handler(event, data)

        get_tg = sync_to_async(self._get_tg_user, thread_sensitive=True)
        tg_user = await get_tg(from_user.id)

        if tg_user is None:
            await event.answer(
                "Чтобы начать работу, привяжи аккаунт:\n\n"
                "1. Зайди на aineron.ru\n"
                "2. Кабинет → Telegram → Подключить\n\n"
                "После привязки все функции будут доступны."
            )
            return

        if tg_user.user.shadow_banned:
            await asyncio.sleep(random.uniform(5, 10))

        # Antispam: 30 сообщений/мин через Django cache (Redis)
        rate_key = f'tg_rate:{tg_user.telegram_id}'
        count = cache.get(rate_key, 0)
        if count >= RATE_LIMIT_PER_MINUTE:
            if hasattr(event, 'answer'):
                await event.answer("Слишком много запросов. Подожди минуту и попробуй снова.")
            return
        cache.set(rate_key, count + 1, timeout=60)

        data['tg_user'] = tg_user
        return await handler(event, data)

    @staticmethod
    def _get_tg_user(telegram_id):
        from telegram_bot.models import TelegramUser
        try:
            return TelegramUser.objects.select_related('user', 'default_network', 'default_image_network').get(
                telegram_id=telegram_id
            )
        except TelegramUser.DoesNotExist:
            return None


def get_auth_middleware():
    global _middleware_installed
    inst = AuthMiddleware()
    _middleware_installed = True
    return inst
