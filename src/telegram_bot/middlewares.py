import asyncio
import logging
import random
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, InlineQuery
from asgiref.sync import sync_to_async
from django.core.cache import cache

from telegram_bot.i18n import resolve_language, t

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

        # /start обрабатывается без авторизации — это точка входа.
        # BUG-I: CallbackQuery не имеет .text, поэтому кнопки выбора
        # «новый пользователь / уже есть аккаунт» из cmd_start (start.py,
        # NEW_USER_CB='start_new', HAS_ACCOUNT_CB='start_has_account')
        # нужно пропускать отдельно — иначе они попадают под tg_user is None
        # ниже и никогда не доходят до хендлера. tg_user всё равно
        # резолвится и прокидывается (если найден) — иначе повторный
        # /start уже привязанного пользователя всегда попадал бы в
        # cmd_start с tg_user=None и не видел бы свой дашборд (был найден
        # живым тестом BUG-I на aineron.net, не сам баг BUG-I).
        text = getattr(event, 'text', '') or ''
        cb_data = getattr(event, 'data', '') or ''
        if text.startswith('/start') or cb_data.startswith('start_new:') or cb_data == 'start_has_account':
            get_tg = sync_to_async(self._get_tg_user, thread_sensitive=True)
            tg_user = await get_tg(from_user.id)
            data['lang'] = resolve_language(tg_user, from_user)
            if tg_user is not None:
                data['tg_user'] = tg_user
            return await handler(event, data)

        get_tg = sync_to_async(self._get_tg_user, thread_sensitive=True)
        tg_user = await get_tg(from_user.id)
        lang = resolve_language(tg_user, from_user)
        data['lang'] = lang

        if tg_user is None:
            await self._deny(event, t('auth.notLinked', lang))
            return

        if tg_user.user.shadow_banned:
            await asyncio.sleep(random.uniform(5, 10))

        # Найдено при повторном ревью: successful_payment считался в тот же
        # 30/мин antispam-счётчик, что и обычные сообщения/тапы по меню.
        # Telegram уже списал деньги (XTR) к моменту доставки этого апдейта —
        # он не переотправляется при отказе (webhook отвечает 200 сразу,
        # views.py::telegram_webhook). Если пользователь до этого успел
        # набрать 30 взаимодействий за минуту (обычные тапы по меню), апдейт
        # с оплатой молча дропался ЗДЕСЬ, до хендлера — деньги у Telegram
        # списаны, баланс не пополнен, никакого алерта. Оплата не участвует
        # в antispam — Telegram сам не даёт оплатить чаще одного раза за
        # инвойс, троттлить здесь нечего.
        is_payment = getattr(event, 'successful_payment', None) is not None
        if not is_payment:
            # Antispam: 30 сообщений/мин через Django cache (Redis).
            # cache.* — блокирующие вызовы, поэтому уводим их с event loop.
            rate_key = f'tg_rate:{tg_user.telegram_id}'
            count = await sync_to_async(cache.get, thread_sensitive=False)(rate_key, 0)
            if count >= RATE_LIMIT_PER_MINUTE:
                await self._deny(event, t('auth.rateLimited', lang))
                return
            await sync_to_async(cache.set, thread_sensitive=False)(rate_key, count + 1, 60)

        data['tg_user'] = tg_user
        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject, text: str) -> None:
        """Отправить отказ (не привязан / rate limit) с учётом типа апдейта.

        Найдено при повторном ревью: `event.answer(text)` вызывался
        безусловно для ЛЮБОГО типа события. У `Message`/`CallbackQuery`
        `.answer(text: str)` — корректная сигнатура, но у `InlineQuery`
        `.answer()` первым аргументом ждёт `results: list`, не строку —
        падал `ValidationError`, гасился generic except в
        `views.py::_process_update`. Непривязанный пользователь, набравший
        инлайн-запрос, получал полную тишину вместо любой обратной связи;
        `inline.py` был из-за этого недостижим для незалогиненных.
        """
        if isinstance(event, InlineQuery):
            try:
                await event.answer(
                    [], cache_time=1, is_personal=True,
                    switch_pm_text=text[:64], switch_pm_parameter='link',
                )
            except Exception as e:
                logger.warning(f'InlineQuery deny-answer failed: {e}')
            return
        if hasattr(event, 'answer'):
            try:
                await event.answer(text)
            except Exception as e:
                logger.warning(f'deny-answer failed for {type(event).__name__}: {e}')

    @staticmethod
    def _get_tg_user(telegram_id):
        from telegram_bot.models import TelegramUser
        try:
            # ВСЕ default_* FK обязаны быть в select_related: хендлеры работают
            # в async-контексте, и ленивая загрузка FK там бросает
            # SynchronousOnlyOperation (вкладка «Видео» в /models так и умерла).
            return TelegramUser.objects.select_related(
                'user', 'default_network', 'default_image_network', 'default_video_network',
            ).get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            return None


def get_auth_middleware():
    global _middleware_installed
    inst = AuthMiddleware()
    _middleware_installed = True
    return inst
