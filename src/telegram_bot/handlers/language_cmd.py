import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async

from telegram_bot.keyboards import language_kb
from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language, INTL_LOCALES

logger = logging.getLogger(__name__)
router = Router()


def _set_language(tg_user, code: str):
    tg_user.language = code
    tg_user.save(update_fields=['language'])


set_language = sync_to_async(_set_language, thread_sensitive=True)


def _picker_text(lang: str) -> str:
    return f"<b>{t('language.title', lang)}</b>\n{DIVIDER}\n{t('language.subtitle', lang)}"


@router.message(Command('language'))
async def cmd_language(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await message.answer(
        _picker_text(lang), parse_mode='HTML',
        reply_markup=language_kb(tg_user.language, lang),
    )


@router.callback_query(F.data == 'settings:language')
async def cb_open_language(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    await query.message.answer(
        _picker_text(lang), parse_mode='HTML',
        reply_markup=language_kb(tg_user.language, lang),
    )
    await query.answer()


@router.callback_query(F.data.startswith('lang:'))
async def cb_set_language(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    code = query.data.split(':', 1)[1]
    # 'auto' очищает explicit-поле — resolve_language() снова определяет
    # язык по from_user.language_code (см. telegram_bot/i18n.py).
    new_value = '' if code == 'auto' or code not in INTL_LOCALES else code
    await set_language(tg_user, new_value)

    # Подтверждение и клавиатура — уже на только что выбранном языке
    # (для 'auto' показываем на языке, определённом по клиенту Telegram).
    display_lang = new_value or resolve_language(tg_user, query.from_user)
    await query.answer(t('language.saved', display_lang))
    await query.message.edit_text(
        _picker_text(display_lang), parse_mode='HTML',
        reply_markup=language_kb(tg_user.language, display_lang),
    )
