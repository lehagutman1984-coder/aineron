import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in getattr(settings, 'TELEGRAM_ADMIN_IDS', [])


class BroadcastFSM(StatesGroup):
    typing_message = State()
    confirming = State()


def _admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Статистика', callback_data='adm:stats')],
        [InlineKeyboardButton(text='Рассылка', callback_data='adm:broadcast')],
    ])


def _get_stats():
    from telegram_bot.models import TelegramUser, TelegramEvent
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    total = TelegramUser.objects.count()
    dau = TelegramEvent.objects.filter(
        created_at__gte=now - timedelta(days=1)
    ).values('telegram_user').distinct().count()
    wau = TelegramEvent.objects.filter(
        created_at__gte=now - timedelta(days=7)
    ).values('telegram_user').distinct().count()
    msgs = TelegramEvent.objects.filter(
        created_at__gte=now - timedelta(days=1), event_type='message',
    ).count()
    imgs = TelegramEvent.objects.filter(
        created_at__gte=now - timedelta(days=1), event_type='image',
    ).count()
    vids = TelegramEvent.objects.filter(
        created_at__gte=now - timedelta(days=1), event_type='video',
    ).count()
    return (
        f'<b>Статистика бота</b>\n\n'
        f'Всего пользователей: <b>{total}</b>\n'
        f'DAU (24ч): <b>{dau}</b>\n'
        f'WAU (7д): <b>{wau}</b>\n\n'
        f'За сегодня:\n'
        f'Сообщений: <b>{msgs}</b>\n'
        f'Изображений: <b>{imgs}</b>\n'
        f'Видео: <b>{vids}</b>'
    )


def _count_users():
    from telegram_bot.models import TelegramUser
    return TelegramUser.objects.filter(user__isnull=False).count()


def _grant_stars(tg_id, stars):
    from telegram_bot.models import TelegramUser
    from core.money import format_rub
    try:
        tu = TelegramUser.objects.select_related('user').get(telegram_id=tg_id)
        tu.user.add_kopecks(stars * 100, type='admin', reference='')
        return f'Начислено {format_rub(stars * 100)} → {tu.user.email} (новый баланс: {format_rub(tu.user.balance_kopecks)})'
    except TelegramUser.DoesNotExist:
        return 'Пользователь не найден'


_get_stats_async = sync_to_async(_get_stats, thread_sensitive=True)
_count_users_async = sync_to_async(_count_users, thread_sensitive=True)
_grant_stars_async = sync_to_async(_grant_stars, thread_sensitive=True)


@router.message(Command('admin'))
async def cmd_admin(message: Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer('<b>Панель администратора</b>', parse_mode='HTML', reply_markup=_admin_kb())


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    if not _is_admin(message.from_user.id):
        return
    stats = await _get_stats_async()
    await message.answer(stats, parse_mode='HTML')


@router.callback_query(F.data == 'adm:stats')
async def cb_adm_stats(query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer()
        return
    stats = await _get_stats_async()
    await query.message.edit_text(stats, parse_mode='HTML', reply_markup=_admin_kb())
    await query.answer()


@router.callback_query(F.data == 'adm:broadcast')
async def cb_adm_broadcast(query: CallbackQuery, state: FSMContext):
    if not _is_admin(query.from_user.id):
        await query.answer()
        return
    await query.message.answer('Введи текст рассылки (HTML поддерживается):')
    await state.set_state(BroadcastFSM.typing_message)
    await query.answer()


@router.message(BroadcastFSM.typing_message)
async def on_broadcast_text(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_text=message.html_text or message.text)
    count = await _count_users_async()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f'Отправить {count} пользователям',
            callback_data='adm:confirm_broadcast',
        )],
        [InlineKeyboardButton(text='Отмена', callback_data='adm:cancel_broadcast')],
    ])
    await message.answer(
        f'<b>Превью:</b>\n\n{message.html_text or message.text}',
        parse_mode='HTML',
        reply_markup=kb,
    )
    await state.set_state(BroadcastFSM.confirming)


@router.callback_query(F.data == 'adm:confirm_broadcast', BroadcastFSM.confirming)
async def cb_confirm_broadcast(query: CallbackQuery, state: FSMContext):
    if not _is_admin(query.from_user.id):
        await query.answer()
        return
    data = await state.get_data()
    text = data.get('broadcast_text', '')
    await state.clear()
    await query.message.edit_text('Рассылка запущена...')
    from telegram_bot.tasks import broadcast_message
    broadcast_message.delay(text, query.from_user.id)
    await query.answer('Запущено!')


@router.callback_query(F.data == 'adm:cancel_broadcast')
async def cb_cancel_broadcast(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text('Рассылка отменена.')
    await query.answer()


@router.message(Command('grant'))
async def cmd_grant(message: Message):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer('Использование: /grant <tg_id> <stars>')
        return
    try:
        tg_id = int(parts[1])
        stars = int(parts[2])
    except ValueError:
        await message.answer('Неверный формат: /grant <число> <число>')
        return
    result = await _grant_stars_async(tg_id, stars)
    await message.answer(result)
