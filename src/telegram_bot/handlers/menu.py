import logging
from aiogram import Router, F
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.conf import settings as dj_settings

from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language, DICT_LOCALES

logger = logging.getLogger(__name__)
router = Router()

MENU_ACTION_KEYS = (
    'chat', 'image', 'video', 'balance', 'models', 'settings',
    'history', 'help', 'projects', 'tasks', 'research',
)


def _all_menu_labels() -> set:
    """Все возможные подписи кнопок меню по всем локалям — для фильтра хендлера."""
    labels = set()
    for locale in DICT_LOCALES:
        for key in MENU_ACTION_KEYS:
            labels.add(t(f'menu.{key}', locale))
    return labels


def _label_to_action(text: str, lang: str) -> str | None:
    for key in MENU_ACTION_KEYS:
        if t(f'menu.{key}', lang) == text:
            return key
    # fallback: подпись могла прийти на другой локали (сменил язык клиента
    # Telegram между нажатиями) — ищем по всем словарям
    for locale in DICT_LOCALES:
        for key in MENU_ACTION_KEYS:
            if t(f'menu.{key}', locale) == text:
                return key
    return None


@router.message(F.text.func(lambda text: text in _all_menu_labels()))
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
