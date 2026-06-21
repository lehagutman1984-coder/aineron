import asyncio
import concurrent.futures
import json
import logging
import threading

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# One persistent event loop per process — avoids "Future attached to a different loop"
_bot_loop: asyncio.AbstractEventLoop | None = None
_bot_loop_lock = threading.Lock()
_routers_registered = False


def _get_bot_loop() -> asyncio.AbstractEventLoop:
    global _bot_loop
    if _bot_loop is not None and not _bot_loop.is_closed():
        return _bot_loop
    with _bot_loop_lock:
        if _bot_loop is None or _bot_loop.is_closed():
            loop = asyncio.new_event_loop()
            t = threading.Thread(target=loop.run_forever, daemon=True, name='tg-bot-loop')
            t.start()
            _bot_loop = loop
    return _bot_loop


async def _process_update(update_data: dict) -> None:
    global _routers_registered
    from aiogram import Bot, types
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from telegram_bot.bot import dp, register_routers

    if not _routers_registered:
        register_routers()
        _routers_registered = True

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        update = types.Update.model_validate(update_data)
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()


@csrf_exempt
@require_POST
def telegram_webhook(request):
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning('Telegram webhook: invalid secret token')
        return HttpResponse(status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse(status=400)

    try:
        loop = _get_bot_loop()
        future = asyncio.run_coroutine_threadsafe(_process_update(data), loop)
        future.result(timeout=25)
    except concurrent.futures.TimeoutError:
        logger.error('Telegram webhook timeout')
    except Exception as e:
        logger.exception(f'Telegram webhook error: {e}')

    return HttpResponse('ok')
