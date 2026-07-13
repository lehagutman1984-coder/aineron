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

            allowed_updates = [
                'message', 'callback_query', 'pre_checkout_query',
                'successful_payment', 'inline_query', 'chosen_inline_result',
            ]
            # S5: AI-секретарь — апдейты Telegram Business (за флагом)
            if getattr(settings, 'TG_BUSINESS', False):
                allowed_updates += [
                    'business_connection', 'business_message',
                    'edited_business_message', 'deleted_business_messages',
                ]
            await bot.set_webhook(
                url=webhook_url,
                secret_token=secret,
                drop_pending_updates=True,
                allowed_updates=allowed_updates,
            )
            self.stdout.write(self.style.SUCCESS(f'Webhook set: {webhook_url}'))

            from aiogram.types import BotCommand

            if getattr(settings, 'INTL_MODE', False):
                # G4/G5 — только команды, реально зарегистрированные в
                # bot.py register_routers() для INTL_MODE (wave 1). Каждый
                # язык — отдельный вызов set_my_commands(language_code=...):
                # Telegram сам показывает нужный список по языку клиента,
                # список без language_code — дефолт для всех остальных
                # (см. https://core.telegram.org/bots/api#setmycommands).
                for lang_code, cmds in INTL_COMMANDS.items():
                    commands = [BotCommand(command=c, description=d) for c, d in cmds]
                    await bot.set_my_commands(commands, language_code=lang_code or None)
                self.stdout.write(self.style.SUCCESS(
                    f'Bot commands registered for: default(en), {", ".join(k for k in INTL_COMMANDS if k)}.'
                ))
                return

            # Register Russian command list visible in Telegram menu
            commands = [
                BotCommand(command='start', description='Главное меню'),
                BotCommand(command='newchat', description='Начать новый чат'),
                BotCommand(command='models', description='Выбор модели AI'),
                BotCommand(command='image', description='Создать изображение'),
                BotCommand(command='video', description='Создать видео'),
                BotCommand(command='img2img', description='Редактировать фото через AI'),
                BotCommand(command='img2video', description='Оживить фото — фото → видео'),
                BotCommand(command='videoset', description='Настройки видео: длительность, качество, звук'),
                BotCommand(command='sticker', description='Создать AI-стикер'),
                BotCommand(command='ai', description='AI-агенты: пост, код-ревью, перевод'),
                BotCommand(command='task', description='AI-задача по расписанию'),
                BotCommand(command='tasks', description='Мои AI-задачи'),
                BotCommand(command='agent', description='Agent Mode: многошаговая задача'),
                BotCommand(command='research', description='Глубокое исследование с источниками'),
                BotCommand(command='channel', description='AI-посты в ваш канал'),
                BotCommand(command='subscribe', description='Подписка на тариф в Stars'),
                BotCommand(command='secretary', description='AI-секретарь для Telegram Business'),
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


# Ключ '' — список без language_code (дефолт Telegram для всех клиентов,
# чей язык не перечислен явно ниже); используем английские описания, т.к.
# INTL_DEFAULT_LOCALE = 'en' (telegram_bot/i18n.py).
INTL_COMMANDS = {
    '': [
        ('start', 'Main menu'),
        ('newchat', 'Start a new chat'),
        ('models', 'Choose an AI model'),
        ('image', 'Generate an image'),
        ('balance', 'Balance and top-up'),
        ('settings', 'Bot settings'),
        ('language', 'Change bot language'),
        ('help', 'Help'),
    ],
    'fa': [
        ('start', 'منوی اصلی'),
        ('newchat', 'شروع چت جدید'),
        ('models', 'انتخاب مدل هوش مصنوعی'),
        ('image', 'تولید تصویر'),
        ('balance', 'موجودی و شارژ'),
        ('settings', 'تنظیمات ربات'),
        ('language', 'تغییر زبان ربات'),
        ('help', 'راهنما'),
    ],
    'tr': [
        ('start', 'Ana menü'),
        ('newchat', 'Yeni sohbet başlat'),
        ('models', 'AI modeli seç'),
        ('image', 'Görüntü oluştur'),
        ('balance', 'Bakiye ve yükleme'),
        ('settings', 'Bot ayarları'),
        ('language', 'Bot dilini değiştir'),
        ('help', 'Yardım'),
    ],
    'id': [
        ('start', 'Menu utama'),
        ('newchat', 'Mulai obrolan baru'),
        ('models', 'Pilih model AI'),
        ('image', 'Buat gambar'),
        ('balance', 'Saldo dan isi ulang'),
        ('settings', 'Pengaturan bot'),
        ('language', 'Ubah bahasa bot'),
        ('help', 'Bantuan'),
    ],
    'ar': [
        ('start', 'القائمة الرئيسية'),
        ('newchat', 'بدء محادثة جديدة'),
        ('models', 'اختيار نموذج الذكاء الاصطناعي'),
        ('image', 'توليد صورة'),
        ('balance', 'الرصيد وإعادة الشحن'),
        ('settings', 'إعدادات البوت'),
        ('language', 'تغيير لغة البوت'),
        ('help', 'مساعدة'),
    ],
}
