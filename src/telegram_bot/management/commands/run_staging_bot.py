"""
manage.py run_staging_bot — polling-режим для QA/staging-бота.

Отдельный от прода Bot-инстанс (TELEGRAM_STAGING_BOT_TOKEN), общий код и БД —
для живого тестирования через MTProto-аккаунт (Telethon/Pyrogram), не трогая
реальный @aineron_bot и его вебхук. run_bot.py (старая dev-команда) не
подходит: она импортирует несуществующий telegram_bot.bot.bot — устарела ещё
до перехода на архитектуру с вебхуком (views.py создаёт Bot сам, отдельно).

Запуск (обычно в screen/systemd, процесс должен жить долго):
    python manage.py run_staging_bot
"""
import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the staging Telegram bot in polling mode (QA only, not production).'

    async def _run(self):
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from telegram_bot.bot import dp, register_routers

        # register_routers() сама подключает AuthMiddleware на dp.message/
        # callback_query/inline_query (bot.py:33-35) — повторный вызов здесь
        # задвоил бы её.
        register_routers()

        bot = Bot(
            token=settings.TELEGRAM_STAGING_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            me = await bot.get_me()
            self.stdout.write(self.style.SUCCESS(
                f'Staging bot polling started: @{me.username} (id={me.id})'
            ))
            await dp.start_polling(bot)
        finally:
            await bot.session.close()

    def handle(self, *args, **options):
        if not settings.TELEGRAM_STAGING_BOT_TOKEN:
            raise CommandError(
                'TELEGRAM_STAGING_BOT_TOKEN не задан в .env — нечего запускать.'
            )
        asyncio.run(self._run())
