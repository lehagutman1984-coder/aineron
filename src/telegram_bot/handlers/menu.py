import logging
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.conf import settings as dj_settings

from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


# BUG-N (TELEGRAM_SUPREMACY_PLAN_V2.md): не было глобального выхода из FSM —
# /cancel работал только точечно в паре хендлеров. menu.router подключается
# одним из первых (bot.py), поэтому /cancel здесь перехватывает и сбрасывает
# состояние независимо от того, в каком именно мастере (напоминание, /task,
# /mybot, секретарь и т.д.) сейчас находится пользователь.
@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state=None, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    current_state = await state.get_state() if state else None
    if current_state is None:
        text = 'Нечего отменять.' if lang == 'ru' else t('menu.cancelNothing', lang)
    else:
        await state.clear()
        text = 'Отменено.' if lang == 'ru' else t('menu.cancelDone', lang)
    await message.answer(text)

MENU_ACTION_KEYS = (
    'chat', 'image', 'video', 'balance', 'models', 'settings',
    'history', 'help', 'projects', 'tasks', 'research',
)


def _label_to_action(text: str, lang: str) -> str | None:
    """Матчинг только по подписям ТЕКУЩЕГО языка пользователя (BUG-M,
    TELEGRAM_SUPREMACY_PLAN_V2.md) — раньше сравнение шло по всем локалям
    сразу, и обычное сообщение, случайно совпавшее с подписью кнопки на
    ДРУГОМ языке (например, слово «Chat» или «Help» от русского
    пользователя), перехватывалось статичной карточкой меню вместо ответа
    нейросети."""
    for key in MENU_ACTION_KEYS:
        if t(f'menu.{key}', lang) == text:
            return key
    return None


async def _is_menu_button(message: Message, tg_user=None) -> bool:
    if not message.text:
        return False
    lang = resolve_language(tg_user, message.from_user)
    return _label_to_action(message.text, lang) is not None


# StateFilter(None) — тот же паттерн, что и на catch-all чата (chat.py):
# без него нажатие кнопки меню посреди любого FSM-шага (например, ввод
# текста напоминания) съедало сообщение сюда и не сбрасывало состояние.
@router.message(StateFilter(None), _is_menu_button)
async def handle_menu_button(message: Message, state=None, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    action = _label_to_action(message.text, lang)
    if action is None:
        return

    if action == 'chat':
        await message.answer(
            f"<b>{t('menu.chatTitle', lang)}</b>\n{DIVIDER}\n{t('menu.chatBody', lang)}",
            parse_mode='HTML',
        )

    elif action == 'image':
        await message.answer(
            f"<b>{t('menu.imageTitle', lang)}</b>\n{DIVIDER}\n{t('menu.imageBody', lang)}",
            parse_mode='HTML',
        )

    elif action == 'video':
        if lang == 'ru':
            await message.answer(
                '<b>Aineron · Генерация видео</b>\n' + DIVIDER + '\n'
                'Опишите видео командой:\n\n'
                '<code>/video закат над морем, медленный полёт камеры</code>\n\n'
                '<i>Готово через 5–15 минут — пришлю результат.</i>',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('menu.videoTitle', lang)}</b>\n{DIVIDER}\n{t('menu.videoBody', lang)}",
                parse_mode='HTML',
            )

    elif action == 'balance':
        if tg_user:
            from telegram_bot.handlers.balance import send_balance
            await send_balance(message, tg_user, lang=lang)
        else:
            await message.answer(t('menu.notLinkedShort', lang))

    elif action == 'models':
        if tg_user:
            from telegram_bot.handlers.models_cmd import _send_tab
            await _send_tab(message, tg_user, 'text', edit=False, lang=lang)
        else:
            await message.answer(t('menu.notLinkedShort', lang))

    elif action == 'settings':
        if tg_user:
            from telegram_bot.handlers.settings_cmd import send_settings
            await send_settings(message, tg_user, lang=lang)
        else:
            await message.answer(t('menu.notLinkedShort', lang))

    elif action == 'history':
        if tg_user:
            from telegram_bot.handlers.history import cmd_history
            await cmd_history(message, state=None, tg_user=tg_user)
        else:
            await message.answer(t('menu.notLinkedShort', lang) if lang != 'ru' else 'Привяжите аккаунт через /start')

    elif action == 'projects':
        if tg_user:
            from telegram_bot.handlers.projects_cmd import send_project_list
            await send_project_list(message, None, tg_user, offset=0)
        else:
            await message.answer(t('menu.notLinkedShort', lang) if lang != 'ru' else 'Привяжите аккаунт через /start')

    elif action == 'tasks':
        if not tg_user:
            await message.answer(t('menu.notLinkedShort', lang) if lang != 'ru' else 'Привяжите аккаунт через /start')
        elif lang != 'ru':
            # tasks_cmd не подключён для INTL_MODE (bot.py::register_routers) —
            # завязан на рублёвые пресеты, отдельная задача (GLOBAL_EXPANSION_PLAN.md)
            await message.answer(t('menu.featureUnavailable', lang))
        else:
            from telegram_bot.handlers.tasks_cmd import _send_task_list
            await _send_task_list(message, tg_user)

    elif action == 'research':
        if not tg_user:
            await message.answer(t('menu.notLinkedShort', lang) if lang != 'ru' else 'Привяжите аккаунт через /start')
        elif lang != 'ru':
            # research_cmd не подключён для INTL_MODE — та же причина, что tasks
            await message.answer(t('menu.featureUnavailable', lang))
        else:
            from telegram_bot.handlers.research_cmd import _ask_confirmation
            await _ask_confirmation(message, state, tg_user, '')

    elif action == 'help':
        await message.answer(
            f"<b>{t('menu.helpTitle', lang)}</b>\n{DIVIDER}\n{t('menu.helpBody', lang)}",
            parse_mode='HTML',
        )
