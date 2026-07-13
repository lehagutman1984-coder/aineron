"""
G5 — /timezone: часовой пояс для /remind и /digest на aineron.net.

Запрашивается один раз (см. remind_cmd.py/digest_cmd.py — гейт при
timezone_offset_minutes is None), можно сменить в любой момент командой.
Пресеты покрывают регионы fa/tr/id/ar-аудитории + свободный ввод смещения.
"""
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.i18n import t, resolve_language
from telegram_bot.utils import DIVIDER

router = Router()


class TimezoneFSM(StatesGroup):
    waiting_custom = State()


# (смещение в минутах, ярлык) — примеры городов покрывают регионы
# запущенных локалей (fa=Иран, tr=Турция, id=Индонезия, ar=MENA).
TIMEZONE_PRESETS = [
    (60,  'UTC+1 (Casablanca)'),
    (120, 'UTC+2 (Cairo)'),
    (180, 'UTC+3 (Istanbul / Riyadh)'),
    (210, 'UTC+3:30 (Tehran)'),
    (240, 'UTC+4 (Dubai)'),
    (420, 'UTC+7 (Jakarta)'),
    (480, 'UTC+8 (Bali)'),
    (540, 'UTC+9 (Jayapura)'),
]


def offset_label(minutes: int) -> str:
    sign = '+' if minutes >= 0 else '-'
    h, m = divmod(abs(minutes), 60)
    return f'UTC{sign}{h}' + (f':{m:02d}' if m else '')


def parse_custom_offset(text: str):
    """'+3', '-5', '+3:30', '3:30' -> минуты, либо None если невалидно."""
    m = re.match(r'^([+-]?)(\d{1,2})(?::(\d{2}))?$', (text or '').strip())
    if not m:
        return None
    sign = -1 if m.group(1) == '-' else 1
    hours = int(m.group(2))
    minutes = int(m.group(3) or 0)
    if hours > 14 or minutes not in (0, 15, 30, 45):
        return None
    total = sign * (hours * 60 + minutes)
    if not (-720 <= total <= 840):  # UTC-12..UTC+14
        return None
    return total


def _set_timezone(tg_user, minutes: int):
    tg_user.timezone_offset_minutes = minutes
    tg_user.save(update_fields=['timezone_offset_minutes'])


set_timezone = sync_to_async(_set_timezone, thread_sensitive=True)


def timezone_kb(lang: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for minutes, label in TIMEZONE_PRESETS:
        row.append(InlineKeyboardButton(text=label, callback_data=f'tz:{minutes}'))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t('timezone.customButton', lang), callback_data='tz:custom')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _screen_text(lang: str, tg_user) -> str:
    current = tg_user.timezone_offset_minutes
    current_label = offset_label(current) if current is not None else t('timezone.notSet', lang)
    return (
        f"<b>{t('timezone.title', lang)}</b>\n{DIVIDER}\n"
        f"{t('timezone.current', lang)}: {current_label}\n\n"
        f"{t('timezone.subtitle', lang)}"
    )


@router.message(Command('timezone'))
async def cmd_timezone(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await message.answer(_screen_text(lang, tg_user), parse_mode='HTML', reply_markup=timezone_kb(lang))


@router.callback_query(F.data == 'tz:custom')
async def cb_timezone_custom(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    await query.message.answer(t('timezone.enterCustom', lang))
    await state.set_state(TimezoneFSM.waiting_custom)
    await query.answer()


@router.message(TimezoneFSM.waiting_custom)
async def on_custom_timezone(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    offset = parse_custom_offset(message.text or '')
    if offset is None:
        await message.answer(t('timezone.invalidCustom', lang))
        return
    await state.clear()
    await set_timezone(tg_user, offset)
    await message.answer(
        t('timezone.saved', lang, offset=offset_label(offset)),
        parse_mode='HTML',
    )


@router.callback_query(F.data.startswith('tz:'))
async def cb_timezone_preset(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    value = query.data.split(':', 1)[1]
    if value == 'custom':
        return  # обрабатывается cb_timezone_custom выше по регистрации
    lang = resolve_language(tg_user, query.from_user)
    minutes = int(value)
    await set_timezone(tg_user, minutes)
    await query.answer(t('timezone.saved', lang, offset=offset_label(minutes)))
    await query.message.edit_text(
        _screen_text(lang, tg_user), parse_mode='HTML', reply_markup=timezone_kb(lang),
    )
