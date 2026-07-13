"""
§7.14 Scheduled AI reminders — /remind FSM.

Flow:
  /remind → ask text → ask time → confirm → save Reminder
  /reminders → list upcoming reminders with cancel buttons

G5: на aineron.net часовой пояс берётся из tg_user.timezone_offset_minutes
(см. timezone_cmd.py) — гейт при /remind, если ещё не задан. Синтаксис
времени для intl — фиксированный ASCII-формат (+30m/+2h/+1d/HH:MM/
tomorrow HH:MM), не завязан на конкретный язык (естественный парсинг
относительного времени на 4 языках — отдельная, гораздо более объёмная
задача, см. GLOBAL_EXPANSION_PLAN.md).
"""
import logging
import re
from datetime import timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.utils import timezone

from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()

MOSCOW = ZoneInfo('Europe/Moscow')

_TIME_PATTERNS = [
    (re.compile(r'^через\s+(\d+)\s*мин', re.I),   lambda m: timedelta(minutes=int(m.group(1)))),
    (re.compile(r'^через\s+(\d+)\s*час', re.I),   lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r'^через\s+(\d+)\s*д', re.I),     lambda m: timedelta(days=int(m.group(1)))),
    (re.compile(r'^(\d{1,2}):(\d{2})$'),          None),  # HH:MM today
    (re.compile(r'^завтра\s+(\d{1,2}):(\d{2})$', re.I), None),  # завтра HH:MM
]

# G5: language-agnostic ASCII syntax for aineron.net — +30m / +2h / +1d /
# HH:MM / tomorrow HH:MM. "tomorrow" is the one literal English keyword,
# spelled out in the (translated) instructions shown to the user.
_TIME_PATTERNS_INTL = [
    (re.compile(r'^\+\s*(\d+)\s*m(in)?s?$', re.I), lambda m: timedelta(minutes=int(m.group(1)))),
    (re.compile(r'^\+\s*(\d+)\s*h(our|r)?s?$', re.I), lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r'^\+\s*(\d+)\s*d(ay)?s?$', re.I), lambda m: timedelta(days=int(m.group(1)))),
]


class RemindStates(StatesGroup):
    waiting_text = State()
    waiting_time = State()


def _parse_time(text: str):
    """Parse Russian-language user input into a UTC datetime. Returns None if unrecognised."""
    now_msk = timezone.now().astimezone(MOSCOW)
    t_ = text.strip()

    # через N мин / час / дн
    for pattern, calc in _TIME_PATTERNS[:3]:
        m = pattern.match(t_)
        if m and calc:
            return timezone.now() + calc(m)

    # HH:MM (today MSK)
    m = re.match(r'^(\d{1,2}):(\d{2})$', t_)
    if m:
        candidate = now_msk.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if candidate <= now_msk:
            candidate += timedelta(days=1)
        return candidate.astimezone(dt_timezone.utc)

    # завтра HH:MM
    m = re.match(r'^завтра\s+(\d{1,2}):(\d{2})$', t_, re.I)
    if m:
        tomorrow = now_msk + timedelta(days=1)
        candidate = tomorrow.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return candidate.astimezone(dt_timezone.utc)

    return None


def _parse_time_intl(text: str, offset_minutes: int):
    """Parse the ASCII intl syntax into a UTC datetime, using a fixed UTC
    offset (not a real IANA zone — no DST awareness, by design; see
    timezone_cmd.py). Returns None if unrecognised."""
    local_tz = dt_timezone(timedelta(minutes=offset_minutes))
    now_local = timezone.now().astimezone(local_tz)
    t_ = text.strip()

    for pattern, calc in _TIME_PATTERNS_INTL:
        m = pattern.match(t_)
        if m:
            return timezone.now() + calc(m)

    m = re.match(r'^(\d{1,2}):(\d{2})$', t_)
    if m:
        candidate = now_local.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(dt_timezone.utc)

    m = re.match(r'^tomorrow\s+(\d{1,2}):(\d{2})$', t_, re.I)
    if m:
        tomorrow = now_local + timedelta(days=1)
        candidate = tomorrow.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return candidate.astimezone(dt_timezone.utc)

    return None


@sync_to_async
def _save_reminder(tg_user, text: str, remind_at):
    from telegram_bot.models import Reminder
    return Reminder.objects.create(tg_user=tg_user, text=text, remind_at=remind_at)


@sync_to_async
def _list_reminders(tg_user):
    from telegram_bot.models import Reminder
    return list(Reminder.objects.filter(tg_user=tg_user, is_sent=False).order_by('remind_at')[:10])


@sync_to_async
def _cancel_reminder(reminder_id: int, tg_user):
    from telegram_bot.models import Reminder
    return Reminder.objects.filter(pk=reminder_id, tg_user=tg_user).delete()


@router.message(Command('remind'))
async def cmd_remind(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    if lang != 'ru' and tg_user.timezone_offset_minutes is None:
        await message.answer(t('remind.setTimezoneFirst', lang))
        return
    await state.set_state(RemindStates.waiting_text)
    if lang == 'ru':
        text = '<b>Новое напоминание</b>\n\nО чём напомнить? Напишите текст напоминания.'
    else:
        text = f"<b>{t('remind.newTitle', lang)}</b>\n\n{t('remind.askText', lang)}"
    await message.answer(text, parse_mode='HTML')


@router.message(RemindStates.waiting_text)
async def remind_got_text(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await state.update_data(remind_text=message.text or '')
    await state.set_state(RemindStates.waiting_time)
    if lang == 'ru':
        text = (
            'Когда напомнить?\n\n'
            'Форматы:\n'
            '  • <code>через 30 мин</code>\n'
            '  • <code>через 2 часа</code>\n'
            '  • <code>через 1 день</code>\n'
            '  • <code>15:30</code> — сегодня в 15:30 МСК\n'
            '  • <code>завтра 09:00</code>'
        )
    else:
        text = (
            f"{t('remind.askTime', lang)}\n\n"
            f"{t('remind.formats', lang)}:\n"
            f"  • <code>+30m</code>\n"
            f"  • <code>+2h</code>\n"
            f"  • <code>+1d</code>\n"
            f"  • <code>15:30</code>\n"
            f"  • <code>tomorrow 09:00</code>"
        )
    await message.answer(text, parse_mode='HTML')


@router.message(RemindStates.waiting_time)
async def remind_got_time(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)

    if lang == 'ru':
        remind_at = _parse_time(message.text or '')
        if not remind_at:
            await message.answer(
                'Не понял время. Попробуйте:\n'
                '<code>через 30 мин</code>, <code>15:30</code>, <code>завтра 09:00</code>',
                parse_mode='HTML',
            )
            return
    else:
        remind_at = _parse_time_intl(message.text or '', tg_user.timezone_offset_minutes)
        if not remind_at:
            await message.answer(t('remind.parseError', lang), parse_mode='HTML')
            return

    data = await state.get_data()
    text = data.get('remind_text', '')
    await state.clear()

    await _save_reminder(tg_user, text, remind_at)

    if lang == 'ru':
        msk_str = remind_at.astimezone(MOSCOW).strftime('%d.%m.%Y %H:%M МСК')
        confirm = f'Напоминание установлено на <b>{msk_str}</b>.\n\nТекст: {text[:200]}'
    else:
        local_tz = dt_timezone(timedelta(minutes=tg_user.timezone_offset_minutes))
        local_str = remind_at.astimezone(local_tz).strftime('%d.%m.%Y %H:%M')
        from telegram_bot.handlers.timezone_cmd import offset_label
        confirm = t('remind.set', lang, time=f'{local_str} ({offset_label(tg_user.timezone_offset_minutes)})',
                    text=text[:200])
    await message.answer(confirm, parse_mode='HTML')


@router.message(Command('reminders'))
async def cmd_reminders(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    reminders = await _list_reminders(tg_user)
    if not reminders:
        await message.answer('У вас нет активных напоминаний.' if lang == 'ru' else t('remind.emptyList', lang))
        return

    buttons = []
    if lang == 'ru':
        lines = ['<b>Ваши напоминания:</b>\n']
        cancel_label = 'Отменить'
        display_tz = MOSCOW
        fmt = '%d.%m %H:%M'
    else:
        lines = [f"<b>{t('remind.listTitle', lang)}</b>\n"]
        cancel_label = t('remind.cancelButton', lang)
        display_tz = dt_timezone(timedelta(minutes=tg_user.timezone_offset_minutes))
        fmt = '%d.%m %H:%M'

    for i, r in enumerate(reminders, 1):
        local_str = r.remind_at.astimezone(display_tz).strftime(fmt)
        lines.append(f'{i}. {r.text[:60]} — <i>{local_str}</i>')
        buttons.append([InlineKeyboardButton(
            text=f'{cancel_label} #{i}',
            callback_data=f'cancel_remind:{r.pk}',
        )])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('\n'.join(lines), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith('cancel_remind:'))
async def cb_cancel_remind(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    reminder_id = int(query.data.split(':', 1)[1])
    deleted, _ = await _cancel_reminder(reminder_id, tg_user)
    if lang == 'ru':
        msg = 'Напоминание отменено.' if deleted else 'Напоминание не найдено или уже выполнено.'
    else:
        msg = t('remind.cancelled', lang) if deleted else t('remind.notFound', lang)
    await query.answer(msg)
    await query.message.delete()
