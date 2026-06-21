import asyncio
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run Telegram bot in polling mode (dev only)'

    def handle(self, *args, **options):
        from telegram_bot.bot import bot, dp, register_routers
        from telegram_bot.middlewares import AuthMiddleware
        register_routers()
        dp.message.middleware(AuthMiddleware())
        self.stdout.write(self.style.SUCCESS('Starting Telegram bot (polling mode)...'))
        asyncio.run(dp.start_polling(bot))
