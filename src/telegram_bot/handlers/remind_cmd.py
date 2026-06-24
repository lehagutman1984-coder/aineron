"""
§7.14 Scheduled AI reminders — /remind FSM.

Flow:
  /remind → ask text → ask time → confirm → save Reminder
  /reminders → list upcoming reminders with cancel buttons
"""
import logging
import re
from datetime import timedelta

import pytz
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)
router = Router()

MOSCOW = pytz.timezone('Europe/Moscow')

_TIME_PATTERNS = [
    (re.compile(r'^через\s+(\d+)\s*мин', re.I),   lambda m: timedelta(minutes=int(m.group(1)))),
    (re.compile(r'^через\s+(\d+)\s*час', re.I),   lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r'^через\s+(\d+)\s*д', re.I),     lambda m: timedelta(days=int(m.group(1)))),
    (re.compile(r'^(\d{1,2}):(\d{2})$'),          None),  # HH:MM today
    (re.compile(r'^завтра\s+(\d{1,2}):(\d{2})$', re.I), None),  # завтра HH:MM
]


class RemindStates(StatesGroup):
    waiting_text = State()
    waiting_time = State()


def _parse_time(text: str):
    """Parse user input into a UTC datetime. Returns None if unrecognised."""
    now_msk = timezone.now().astimezone(MOSCOW)
    t = text.strip()

    # через N мин / час / дн
    for pattern, calc in _TIME_PATTERNS[:3]:
        m = pattern.match(t)
        if m and calc:
            return (timezone.now() + calc(m)).astimezone(pytz.utc).replace(tzinfo=None)
            return timezone.now() + calc(m)

    # HH:MM (today MSK)
    m = re.match(r'^(\d{1,2}):(\d{2})$', t)
    if m:
        candidate = now_msk.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if candidate <= now_msk:
            candidate += timedelta(days=1)
        return candidate.astimezone(pytz.utc)

    # завтра HH:MM
    m = re.match(r'^завтра\s+(\d{1,2}):(\d{2})$', t, re.I)
    if m:
        tomorrow = now_msk + timedelta(days=1)
        candidate = tomorrow.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return candidate.astimezone(pytz.utc)

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
    await state.set_state(RemindStates.waiting_text)
    await message.answer(
        '<b>Новое напоминание</b>\n\nО чём напомнить? Напишите текст напоминания.',
        parse_mode='HTML',
    )


@router.message(RemindStates.waiting_text)
async def remind_got_text(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    await state.update_data(remind_text=message.text or '')
    await state.set_state(RemindStates.waiting_time)
    await message.answer(
        'Когда напомнить?\n\n'
        'Форматы:\n'
        '  • <code>через 30 мин</code>\n'
        '  • <code>через 2 часа</code>\n'
        '  • <code>через 1 день</code>\n'
        '  • <code>15:30</code> — сегодня в 15:30 МСК\n'
        '  • <code>завтра 09:00</code>',
        parse_mode='HTML',
    )


@router.message(RemindStates.waiting_time)
async def remind_got_time(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    remind_at = _parse_time(message.text or '')
    if not remind_at:
        await message.answer(
            'Не понял время. Попробуйте:\n'
            '<code>через 30 мин</code>, <code>15:30</code>, <code>завтра 09:00</code>',
            parse_mode='HTML',
        )
        return

    data = await state.get_data()
    text = data.get('remind_text', '')
    await state.clear()

    await _save_reminder(tg_user, text, remind_at)

    msk_str = remind_at.astimezone(MOSCOW).strftime('%d.%m.%Y %H:%M МСК')
    await message.answer(
        f'Напоминание установлено на <b>{msk_str}</b>.\n\n'
        f'Текст: {text[:200]}',
        parse_mode='HTML',
    )


@router.message(Command('reminders'))
async def cmd_reminders(message: Message, tg_user=None):
    if tg_user is None:
        return
    reminders = await _list_reminders(tg_user)
    if not reminders:
        await message.answer('У вас нет активных напоминаний.')
        return

    buttons = []
    lines = ['<b>Ваши напоминания:</b>\n']
    for i, r in enumerate(reminders, 1):
        msk_str = r.remind_at.astimezone(MOSCOW).strftime('%d.%m %H:%M')
        lines.append(f'{i}. {r.text[:60]} — <i>{msk_str}</i>')
        buttons.append([InlineKeyboardButton(
            text=f'Отменить #{i}',
            callback_data=f'cancel_remind:{r.pk}',
        )])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('\n'.join(lines), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith('cancel_remind:'))
async def cb_cancel_remind(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    reminder_id = int(query.data.split(':', 1)[1])
    deleted, _ = await _cancel_reminder(reminder_id, tg_user)
    if deleted:
        await query.answer('Напоминание отменено.')
    else:
        await query.answer('Напоминание не найдено или уже выполнено.')
    await query.message.delete()
