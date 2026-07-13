"""
/digest — manage daily AI digest for user.

Commands (ru / aineron.ru):
  /digest         — show current schedule or enable prompt
  /digest on      — enable daily digest at default time (09:00 Moscow)
  /digest off     — disable
  /digest 08:30   — set custom time (HH:MM, Moscow timezone)

G5 (aineron.net): требует tg_user.timezone_offset_minutes (см.
timezone_cmd.py) — гейт при первом обращении. digest_hour/digest_minute
на intl-инстансе хранятся В UTC (конвертация туда-обратно через offset
на границе ввода/вывода) — так send_daily_digests (tasks.py) может
сравнивать с текущим UTC-временем без привязки к конкретному языку/
часовому поясу пользователя. На aineron.ru семантика полей не менялась —
литеральное московское время, как было.
"""
import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.i18n import t, resolve_language

router = Router()

_TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})$')
DEFAULT_HOUR = 9
DEFAULT_MINUTE = 0


def _local_to_utc(hour: int, minute: int, offset_minutes: int):
    total_utc = (hour * 60 + minute - offset_minutes) % 1440
    return divmod(total_utc, 60)


def _utc_to_local(hour: int, minute: int, offset_minutes: int):
    total_local = (hour * 60 + minute + offset_minutes) % 1440
    return divmod(total_local, 60)


@sync_to_async
def _get_tg_user(telegram_id: int):
    from telegram_bot.models import TelegramUser
    try:
        return TelegramUser.objects.select_related('user').get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


@sync_to_async
def _set_digest(tg_user, enabled: bool, hour: int, minute: int):
    tg_user.digest_enabled = enabled
    tg_user.digest_hour = hour
    tg_user.digest_minute = minute
    tg_user.save(update_fields=['digest_enabled', 'digest_hour', 'digest_minute'])


def _digest_keyboard(enabled: bool, lang: str) -> InlineKeyboardMarkup:
    if lang == 'ru':
        label = 'Выключить дайджест' if enabled else 'Включить дайджест'
    else:
        label = t('digest.disableButton', lang) if enabled else t('digest.enableButton', lang)
    callback = 'digest_off' if enabled else 'digest_on'
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=callback)]])


@router.message(Command('digest'))
async def cmd_digest(message: Message):
    tg_user = await _get_tg_user(message.from_user.id)
    if not tg_user or not tg_user.user:
        lang = resolve_language(None, message.from_user)
        await message.answer(
            "Привяжите аккаунт через /start прежде чем настраивать дайджест."
            if lang == 'ru' else t('digest.linkFirst', lang)
        )
        return

    lang = resolve_language(tg_user, message.from_user)
    if lang != 'ru' and tg_user.timezone_offset_minutes is None:
        await message.answer(t('digest.setTimezoneFirst', lang))
        return
    offset = tg_user.timezone_offset_minutes or 0

    args = (message.text or '').split(maxsplit=1)
    arg = args[1].strip() if len(args) > 1 else ''

    if arg == 'off':
        await _set_digest(tg_user, False, tg_user.digest_hour, tg_user.digest_minute)
        await message.answer("Ежедневный дайджест отключён." if lang == 'ru' else t('digest.disabled', lang))
        return

    if arg == 'on' or arg == '':
        if not arg and not tg_user.digest_enabled:
            if lang == 'ru':
                text = (
                    "Ежедневный дайджест <b>отключён</b>.\n"
                    "Он будет приходить раз в день с краткой сводкой новостей AI и советом от нейросети.\n\n"
                    "Отправьте /digest on или укажите время: /digest 09:00"
                )
            else:
                text = f"<b>{t('digest.offTitle', lang)}</b>\n{t('digest.offBody', lang)}"
            await message.answer(text, parse_mode='HTML', reply_markup=_digest_keyboard(False, lang))
            return
        if lang == 'ru':
            hour, minute = (DEFAULT_HOUR, DEFAULT_MINUTE) if not arg else (tg_user.digest_hour, tg_user.digest_minute)
            await _set_digest(tg_user, True, hour, minute)
            await message.answer(
                f"Ежедневный дайджест <b>включён</b>. Будет приходить в {hour:02d}:{minute:02d} МСК.",
                parse_mode='HTML', reply_markup=_digest_keyboard(True, lang),
            )
        else:
            if arg:
                local_hour, local_minute = DEFAULT_HOUR, DEFAULT_MINUTE
                utc_hour, utc_minute = _local_to_utc(local_hour, local_minute, offset)
            else:
                utc_hour, utc_minute = tg_user.digest_hour, tg_user.digest_minute
                local_hour, local_minute = _utc_to_local(utc_hour, utc_minute, offset)
            await _set_digest(tg_user, True, utc_hour, utc_minute)
            await message.answer(
                t('digest.enabledAt', lang, time=f'{local_hour:02d}:{local_minute:02d}'),
                parse_mode='HTML', reply_markup=_digest_keyboard(True, lang),
            )
        return

    # Parse HH:MM
    m = _TIME_RE.match(arg)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await message.answer(
                "Некорректное время. Используйте формат ЧЧ:ММ, например /digest 09:00"
                if lang == 'ru' else t('digest.invalidTime', lang)
            )
            return
        if lang == 'ru':
            await _set_digest(tg_user, True, hour, minute)
            await message.answer(
                f"Ежедневный дайджест включён. Будет приходить в <b>{hour:02d}:{minute:02d} МСК</b>.",
                parse_mode='HTML', reply_markup=_digest_keyboard(True, lang),
            )
        else:
            utc_hour, utc_minute = _local_to_utc(hour, minute, offset)
            await _set_digest(tg_user, True, utc_hour, utc_minute)
            await message.answer(
                t('digest.enabledAt', lang, time=f'{hour:02d}:{minute:02d}'),
                parse_mode='HTML', reply_markup=_digest_keyboard(True, lang),
            )
        return

    if tg_user.digest_enabled:
        if lang == 'ru':
            h, mn = tg_user.digest_hour, tg_user.digest_minute
            text = (
                f"Ежедневный дайджест <b>включён</b>, время: {h:02d}:{mn:02d} МСК.\n\n"
                "Команды:\n"
                "• /digest off — отключить\n"
                "• /digest ЧЧ:ММ — изменить время\n"
            )
        else:
            local_hour, local_minute = _utc_to_local(tg_user.digest_hour, tg_user.digest_minute, offset)
            text = f"<b>{t('digest.onStatus', lang, time=f'{local_hour:02d}:{local_minute:02d}')}</b>\n\n{t('digest.onCommands', lang)}"
        await message.answer(text, parse_mode='HTML', reply_markup=_digest_keyboard(True, lang))
    else:
        if lang == 'ru':
            text = "Ежедневный дайджест <b>отключён</b>.\n\nВключить: /digest on или /digest 09:00"
        else:
            text = f"<b>{t('digest.offStatus', lang)}</b>\n\n{t('digest.offCommands', lang)}"
        await message.answer(text, parse_mode='HTML', reply_markup=_digest_keyboard(False, lang))


@router.callback_query(lambda c: c.data in ('digest_on', 'digest_off'))
async def cb_digest_toggle(callback: CallbackQuery):
    tg_user = await _get_tg_user(callback.from_user.id)
    if not tg_user:
        lang = resolve_language(None, callback.from_user)
        await callback.answer(
            "Привяжите аккаунт через /start" if lang == 'ru' else t('menu.notLinkedShort', lang),
            show_alert=True,
        )
        return

    lang = resolve_language(tg_user, callback.from_user)
    offset = tg_user.timezone_offset_minutes or 0

    if callback.data == 'digest_on':
        if lang == 'ru':
            await _set_digest(tg_user, True, DEFAULT_HOUR, DEFAULT_MINUTE)
            text = f"Дайджест включён. Буду присылать в {DEFAULT_HOUR:02d}:{DEFAULT_MINUTE:02d} МСК."
        else:
            utc_hour, utc_minute = _local_to_utc(DEFAULT_HOUR, DEFAULT_MINUTE, offset)
            await _set_digest(tg_user, True, utc_hour, utc_minute)
            text = t('digest.enabledAt', lang, time=f'{DEFAULT_HOUR:02d}:{DEFAULT_MINUTE:02d}')
        kb = _digest_keyboard(True, lang)
    else:
        await _set_digest(tg_user, False, tg_user.digest_hour, tg_user.digest_minute)
        text = "Дайджест отключён." if lang == 'ru' else t('digest.disabled', lang)
        kb = _digest_keyboard(False, lang)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
