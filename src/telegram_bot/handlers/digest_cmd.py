"""
/digest — manage daily AI digest for user.

Commands:
  /digest         — show current schedule or enable prompt
  /digest on      — enable daily digest at default time (09:00 Moscow)
  /digest off     — disable
  /digest 08:30   — set custom time (HH:MM, Moscow timezone)
"""
import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

router = Router()

_TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})$')
DEFAULT_HOUR = 9
DEFAULT_MINUTE = 0


@sync_to_async
def _get_tg_user(telegram_id: int):
    from telegram_bot.models import TelegramUser
    try:
        return TelegramUser.objects.select_related('user').get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


@sync_to_async
def _set_digest(tg_user, enabled: bool, hour: int, minute: int):
    from telegram_bot.models import TelegramUser
    tg_user.digest_enabled = enabled
    tg_user.digest_hour = hour
    tg_user.digest_minute = minute
    tg_user.save(update_fields=['digest_enabled', 'digest_hour', 'digest_minute'])


def _digest_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    if enabled:
        row = [InlineKeyboardButton(text='Выключить дайджест', callback_data='digest_off')]
    else:
        row = [InlineKeyboardButton(text='Включить дайджест', callback_data='digest_on')]
    return InlineKeyboardMarkup(inline_keyboard=[row])


@router.message(Command('digest'))
async def cmd_digest(message: Message):
    tg_user = await _get_tg_user(message.from_user.id)
    if not tg_user or not tg_user.user:
        await message.answer("Привяжите аккаунт через /start прежде чем настраивать дайджест.")
        return

    args = (message.text or '').split(maxsplit=1)
    arg = args[1].strip() if len(args) > 1 else ''

    if arg == 'off':
        await _set_digest(tg_user, False, tg_user.digest_hour, tg_user.digest_minute)
        await message.answer("Ежедневный дайджест отключён.")
        return

    if arg == 'on' or arg == '':
        if not arg and not tg_user.digest_enabled:
            # No argument, digest off — show status with toggle button
            await message.answer(
                "Ежедневный дайджест <b>отключён</b>.\n"
                "Он будет приходить раз в день с краткой сводкой новостей AI и советом от нейросети.\n\n"
                "Отправьте /digest on или укажите время: /digest 09:00",
                parse_mode='HTML',
                reply_markup=_digest_keyboard(False),
            )
            return
        hour, minute = DEFAULT_HOUR, DEFAULT_MINUTE
        if not arg:
            hour, minute = tg_user.digest_hour, tg_user.digest_minute
        await _set_digest(tg_user, True, hour, minute)
        await message.answer(
            f"Ежедневный дайджест <b>включён</b>. Будет приходить в {hour:02d}:{minute:02d} МСК.",
            parse_mode='HTML',
            reply_markup=_digest_keyboard(True),
        )
        return

    # Parse HH:MM
    m = _TIME_RE.match(arg)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await message.answer("Некорректное время. Используйте формат ЧЧ:ММ, например /digest 09:00")
            return
        await _set_digest(tg_user, True, hour, minute)
        await message.answer(
            f"Ежедневный дайджест включён. Будет приходить в <b>{hour:02d}:{minute:02d} МСК</b>.",
            parse_mode='HTML',
            reply_markup=_digest_keyboard(True),
        )
        return

    if tg_user.digest_enabled:
        h, mn = tg_user.digest_hour, tg_user.digest_minute
        await message.answer(
            f"Ежедневный дайджест <b>включён</b>, время: {h:02d}:{mn:02d} МСК.\n\n"
            "Команды:\n"
            "• /digest off — отключить\n"
            "• /digest ЧЧ:ММ — изменить время\n",
            parse_mode='HTML',
            reply_markup=_digest_keyboard(True),
        )
    else:
        await message.answer(
            "Ежедневный дайджест <b>отключён</b>.\n\n"
            "Включить: /digest on или /digest 09:00",
            parse_mode='HTML',
            reply_markup=_digest_keyboard(False),
        )


@router.callback_query(lambda c: c.data in ('digest_on', 'digest_off'))
async def cb_digest_toggle(callback: CallbackQuery):
    tg_user = await _get_tg_user(callback.from_user.id)
    if not tg_user:
        await callback.answer("Привяжите аккаунт через /start", show_alert=True)
        return

    if callback.data == 'digest_on':
        await _set_digest(tg_user, True, DEFAULT_HOUR, DEFAULT_MINUTE)
        text = f"Дайджест включён. Буду присылать в {DEFAULT_HOUR:02d}:{DEFAULT_MINUTE:02d} МСК."
        kb = _digest_keyboard(True)
    else:
        await _set_digest(tg_user, False, tg_user.digest_hour, tg_user.digest_minute)
        text = "Дайджест отключён."
        kb = _digest_keyboard(False)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
