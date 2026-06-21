import logging
from aiogram import Router, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()

MENU_BUTTONS = {'Чат', 'Изображение', 'Видео', 'Баланс', 'Модели', 'Настройки', 'История', 'Помощь'}


@router.message(F.text.in_(MENU_BUTTONS))
async def handle_menu_button(message: Message, tg_user=None):
    text = message.text
    if text == 'Чат':
        await message.answer('Просто напиши свой вопрос или задачу — отвечу!')
    elif text == 'Изображение':
        await message.answer(
            'Отправь описание изображения:\n'
            '<code>/image закат над морем в стиле аниме</code>',
            parse_mode='HTML',
        )
    elif text == 'Видео':
        await message.answer(
            'Отправь описание видео:\n'
            '<code>/video закат над морем, медленный полёт камеры</code>',
            parse_mode='HTML',
        )
    elif text == 'Баланс':
        if tg_user:
            from telegram_bot.handlers.balance import send_balance
            await send_balance(message, tg_user)
        else:
            await message.answer('Привяжи аккаунт через /start')
    elif text == 'Модели':
        if tg_user:
            from telegram_bot.handlers.models_cmd import _send_tab
            await _send_tab(message, tg_user, 'text', edit=False)
        else:
            await message.answer('Привяжи аккаунт через /start')
    elif text == 'Настройки':
        if tg_user:
            from telegram_bot.handlers.settings_cmd import send_settings
            await send_settings(message, tg_user)
        else:
            await message.answer('Привяжи аккаунт через /start')
    elif text == 'История':
        if tg_user:
            from telegram_bot.handlers.history import cmd_history
            await cmd_history(message, state=None, tg_user=tg_user)
        else:
            await message.answer('Привяжи аккаунт через /start')
    elif text == 'Помощь':
        await message.answer(
            '<b>Как пользоваться ботом:</b>\n\n'
            'Просто напиши любой вопрос — получи ответ AI.\n\n'
            '<b>Генерация медиа:</b>\n'
            '/image &lt;описание&gt; — создать изображение\n'
            '/video &lt;описание&gt; — создать видео (5-15 мин)\n\n'
            '<b>Управление:</b>\n'
            '/models — выбор модели AI\n'
            '/balance — баланс и пополнение\n'
            '/settings — настройки\n'
            '/newchat — начать новый чат\n'
            '/referral — реферальная программа\n\n'
            'Пополнить баланс: https://aineron.ru/account/billing/',
            parse_mode='HTML',
        )
