import json
import logging
from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from aiogram import types

logger = logging.getLogger(__name__)


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
        from telegram_bot.bot import dp, register_routers
        register_routers()

        async def _process(update_data):
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode
            # Создаём Bot внутри async-контекста — избегаем "Session is closed"
            async with Bot(
                token=settings.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            ) as bot:
                update = types.Update.model_validate(update_data)
                await dp.feed_update(bot, update)

        async_to_sync(_process)(data)
    except Exception as e:
        logger.exception(f'Telegram webhook error: {e}')

    return HttpResponse('ok')
