import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()


def _get_tg_user(telegram_id):
    from telegram_bot.models import TelegramUser
    try:
        return TelegramUser.objects.select_related('user', 'default_network').get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


_get_tg_user_async = sync_to_async(_get_tg_user, thread_sensitive=True)


@router.message(F.chat.type.in_({'group', 'supergroup'}))
async def handle_group_message(message: Message, bot: Bot):
    if not message.text:
        return

    bot_user = await bot.get_me()
    is_reply_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot_user.id
    )
    is_mention = bool(
        bot_user.username and f'@{bot_user.username}' in message.text
    )

    if not is_reply_to_bot and not is_mention:
        return

    tg_user = await _get_tg_user_async(message.from_user.id)
    if not tg_user:
        await message.reply('Привяжи аккаунт aineron.ru: напиши /start боту @aineron_bot')
        return

    text = message.text
    if bot_user.username:
        text = text.replace(f'@{bot_user.username}', '').strip()
    if not text:
        return

    from telegram_bot.handlers.chat import process_text
    await process_text(message, tg_user, text)
