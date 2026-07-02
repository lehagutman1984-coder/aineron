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


# ─── S4: Paid Media в канале + статистика партнёрки ───

@router.message(Command('paidpost'))
async def cmd_paidpost(message: Message):
    """Эксклюзивный платный пост: ответьте на фото/видео командой
    /paidpost <stars> <@канал или chat_id>."""
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or '').split()
    reply = message.reply_to_message
    if len(parts) != 3 or reply is None or not (reply.photo or reply.video):
        await message.answer(
            'Использование: ответьте на сообщение с фото/видео командой\n'
            '/paidpost <stars> <@канал>',
        )
        return
    try:
        star_count = int(parts[1])
    except ValueError:
        await message.answer('Первый аргумент — цена в Stars (число).')
        return
    target = parts[2]
    chat_id = int(target) if target.lstrip('-').isdigit() else target

    send_paid = getattr(message.bot, 'send_paid_media', None)
    if send_paid is None:
        await message.answer('Эта версия aiogram не поддерживает sendPaidMedia.')
        return
    try:
        from aiogram.types import InputPaidMediaPhoto, InputPaidMediaVideo
        if reply.photo:
            media = [InputPaidMediaPhoto(media=reply.photo[-1].file_id)]
        else:
            media = [InputPaidMediaVideo(media=reply.video.file_id)]
        await send_paid(
            chat_id=chat_id, star_count=star_count, media=media,
            caption=reply.caption or 'Эксклюзив от aineron',
        )
        await message.answer(f'Платный пост отправлен в {target} за {star_count} XTR.')
    except Exception as e:
        logger.error(f'paidpost failed: {e}')
        await message.answer(f'Ошибка отправки: {e}')


@router.message(Command('affstats'))
async def cmd_affstats(message: Message):
    """Статистика Stars-транзакций, включая партнёрские начисления (S4)."""
    if not _is_admin(message.from_user.id):
        return
    get_tx = getattr(message.bot, 'get_star_transactions', None)
    if get_tx is None:
        await message.answer('Эта версия aiogram не поддерживает getStarTransactions.')
        return
    try:
        result = await get_tx(limit=100)
        txs = getattr(result, 'transactions', [])
        total_in = sum(t.amount for t in txs if getattr(t, 'source', None) is not None)
        affiliate = 0
        for t in txs:
            src = getattr(t, 'source', None)
            if src is not None and 'Affiliate' in type(src).__name__:
                affiliate += t.amount
        await message.answer(
            f'<b>Stars-транзакции (последние {len(txs)})</b>\n'
            f'Всего получено: {total_in} XTR\n'
            f'Из партнёрской программы: {affiliate} XTR',
            parse_mode='HTML',
        )
    except Exception as e:
        await message.answer(f'Ошибка: {e}')
