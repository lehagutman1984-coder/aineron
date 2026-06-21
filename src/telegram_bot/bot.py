from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.conf import settings

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN or 'placeholder:placeholder_for_import',
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Роутеры подключаются при первом запросе, чтобы избежать circular imports
_routers_registered = False


def register_routers():
    global _routers_registered
    if _routers_registered:
        return
    from telegram_bot.handlers import start, chat, balance, payment, models_cmd, voice, images, prompts_cmd, settings_cmd, referral
    dp.include_router(start.router)
    dp.include_router(chat.router)
    dp.include_router(balance.router)
    dp.include_router(payment.router)
    dp.include_router(models_cmd.router)
    dp.include_router(voice.router)
    dp.include_router(images.router)
    dp.include_router(prompts_cmd.router)
    dp.include_router(settings_cmd.router)
    dp.include_router(referral.router)
    _routers_registered = True
