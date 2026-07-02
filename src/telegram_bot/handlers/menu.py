import logging
from aiogram import Router, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

from telegram_bot.utils import DIVIDER

logger = logging.getLogger(__name__)
router = Router()

MENU_BUTTONS = {'Чат', 'Картинка', 'Видео', 'Баланс', 'Модели', 'Настройки', 'История', 'Помощь',
                'Проекты', 'Задачи', 'Исследование'}


@router.message(F.text.in_(MENU_BUTTONS))
async def handle_menu_button(message: Message, state=None, tg_user=None):
    text = message.text

    if text == 'Чат':
        await message.answer(
            f'<b>Aineron · Чат</b>\n{DIVIDER}\n'
            'Напишите вопрос или задачу — AI ответит.\n\n'
            'Для нового диалога: /newchat',
            parse_mode='HTML',
        )

    elif text == 'Картинка':
        await message.answer(
            f'<b>Aineron · Генерация изображения</b>\n{DIVIDER}\n'
            'Опишите изображение командой:\n\n'
            '<code>/image закат над морем в стиле аниме</code>',
            parse_mode='HTML',
        )

    elif text == 'Видео':
        await message.answer(
            f'<b>Aineron · Генерация видео</b>\n{DIVIDER}\n'
            'Опишите видео командой:\n\n'
            '<code>/video закат над морем, медленный полёт камеры</code>\n\n'
            '<i>Готово через 5–15 минут — пришлю результат.</i>',
            parse_mode='HTML',
        )

    elif text == 'Баланс':
        if tg_user:
            from telegram_bot.handlers.balance import send_balance
            await send_balance(message, tg_user)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Модели':
        if tg_user:
            from telegram_bot.handlers.models_cmd import _send_tab
            await _send_tab(message, tg_user, 'text', edit=False)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Настройки':
        if tg_user:
            from telegram_bot.handlers.settings_cmd import send_settings
            await send_settings(message, tg_user)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'История':
        if tg_user:
            from telegram_bot.handlers.history import cmd_history
            await cmd_history(message, state=None, tg_user=tg_user)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Проекты':
        if tg_user:
            from telegram_bot.handlers.projects_cmd import send_project_list
            await send_project_list(message, None, tg_user, offset=0)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Задачи':
        if tg_user:
            from telegram_bot.handlers.tasks_cmd import _send_task_list
            await _send_task_list(message, tg_user)
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Исследование':
        if tg_user:
            from telegram_bot.handlers.research_cmd import _ask_confirmation
            await _ask_confirmation(message, state, tg_user, '')
        else:
            await message.answer('Привяжите аккаунт через /start')

    elif text == 'Помощь':
        await message.answer(
            f'<b>Aineron · Помощь</b>\n{DIVIDER}\n'
            '<b>Чат и генерация</b>\n'
            'Напишите любой вопрос — AI ответит.\n'
            '/image &lt;описание&gt; — создать изображение\n'
            '/video &lt;описание&gt; — создать видео (5–15 мин)\n\n'
            '<b>Управление</b>\n'
            '/models — выбор модели AI\n'
            '/balance — баланс и пополнение\n'
            '/settings — настройки\n'
            '/newchat — начать новый диалог\n\n'
            '<b>Инструменты</b>\n'
            '/task — AI-задачи по расписанию (утренний бриф, мониторинг)\n'
            '/tasks — мои задачи\n'
            '/research &lt;вопрос&gt; — глубокое исследование с источниками\n'
            '/search &lt;запрос&gt; — поиск по истории\n'
            '/export — скачать текущий чат (.md)\n'
            '/digest — AI-дайджест\n'
            '/ai — AI-агенты: пост, код-ревью, перевод\n'
            '/img2video &lt;промт&gt; — фото → анимация\n'
            '/sticker &lt;промт&gt; — AI-стикер\n'
            '/memory — что бот помнит о вас\n'
            '/projects — проекты и база знаний\n'
            '/referral — реферальная программа\n'
            f'{DIVIDER}\n'
            'Пополнение баланса: aineron.ru/account/billing/',
            parse_mode='HTML',
        )
