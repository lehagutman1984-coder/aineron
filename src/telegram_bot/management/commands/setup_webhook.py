"""
Usage:
  python manage.py setup_webhook              # Set webhook to SITE_URL/telegram/webhook/
  python manage.py setup_webhook --delete     # Delete current webhook
  python manage.py setup_webhook --info       # Show current webhook info
"""
import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Set / delete / inspect the Telegram webhook'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--delete', action='store_true', help='Delete the webhook')
        group.add_argument('--info', action='store_true', help='Show current webhook info')

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR('TELEGRAM_BOT_TOKEN is not set'))
            return

        asyncio.run(self._run(options))

    async def _run(self, options):
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        async with bot:
            if options['delete']:
                await bot.delete_webhook(drop_pending_updates=True)
                self.stdout.write(self.style.SUCCESS('Webhook deleted.'))
                return

            if options['info']:
                info = await bot.get_webhook_info()
                self.stdout.write(f'URL:              {info.url or "(none)"}')
                self.stdout.write(f'Pending updates:  {info.pending_update_count}')
                self.stdout.write(f'Last error:       {info.last_error_message or "(none)"}')
                if info.last_error_date:
                    self.stdout.write(f'Last error date:  {info.last_error_date}')
                return

            # Set webhook
            site_url = settings.SITE_URL.rstrip('/')
            webhook_url = f'{site_url}/telegram/webhook/'
            secret = settings.TELEGRAM_WEBHOOK_SECRET or None

            await bot.set_webhook(
                url=webhook_url,
                secret_token=secret,
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query', 'pre_checkout_query', 'successful_payment', 'inline_query', 'chosen_inline_result'],
            )
            self.stdout.write(self.style.SUCCESS(f'Webhook set: {webhook_url}'))

            # Register Russian command list visible in Telegram menu
            from aiogram.types import BotCommand
            commands = [
                BotCommand(command='start', description='Главное меню'),
                BotCommand(command='newchat', description='Начать новый чат'),
                BotCommand(command='models', description='Выбор модели AI'),
                BotCommand(command='image', description='Создать изображение'),
                BotCommand(command='video', description='Создать видео'),
                BotCommand(command='img2img', description='Редактировать фото через AI'),
                BotCommand(command='img2video', description='Оживить фото — фото → видео'),
                BotCommand(command='sticker', description='Создать AI-стикер'),
                BotCommand(command='ai', description='AI-агенты: пост, код-ревью, перевод'),
                BotCommand(command='memory', description='Что бот помнит о тебе'),
                BotCommand(command='digest', description='Ежедневный AI-дайджест'),
                BotCommand(command='balance', description='Баланс и пополнение'),
                BotCommand(command='settings', description='Настройки бота'),
                BotCommand(command='prompts', description='Библиотека промтов'),
                BotCommand(command='referral', description='Реферальная программа'),
                BotCommand(command='help', description='Справка'),
            ]
            await bot.set_my_commands(commands)
            self.stdout.write(self.style.SUCCESS('Bot commands registered.'))
