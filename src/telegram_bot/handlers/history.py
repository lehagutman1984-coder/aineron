import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()
PAGE_SIZE = 8


class HistoryFSM(StatesGroup):
    browsing = State()


def _get_chat_page(user, page=0):
    from aitext.models import Chat
    qs = Chat.objects.filter(user=user).order_by('-updated_at').select_related('network')
    total = qs.count()
    chats = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    return chats, total


def _activate_chat(tg_user, chat_id):
    from aitext.models import Chat
    from telegram_bot.models import TelegramChat
    chat = Chat.objects.get(id=chat_id, user=tg_user.user)
    TelegramChat.objects.filter(tg_user=tg_user, is_active=True).update(is_active=False)
    tc, _ = TelegramChat.objects.get_or_create(tg_user=tg_user, chat=chat)
    if not tc.is_active:
        tc.is_active = True
        tc.save(update_fields=['is_active'])
    return chat


def _clear_chat(tg_user):
    from telegram_bot.models import TelegramChat
    TelegramChat.objects.filter(tg_user=tg_user, is_active=True).update(is_active=False)


get_chat_page = sync_to_async(_get_chat_page, thread_sensitive=True)
activate_chat = sync_to_async(_activate_chat, thread_sensitive=True)
clear_chat = sync_to_async(_clear_chat, thread_sensitive=True)


def _history_kb(chats, page, total):
    buttons = []
    for chat in chats:
        title = (chat.title or (chat.network.name if chat.network else 'Чат'))[:35]
        date = chat.updated_at.strftime('%d.%m')
        buttons.append([InlineKeyboardButton(
            text=f'{title} · {date}',
            callback_data=f'hist_open:{chat.id}',
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='← Назад', callback_data=f'hist_page:{page - 1}'))
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav.append(InlineKeyboardButton(text=f'{page + 1}/{pages}', callback_data='hist_noop'))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text='Вперёд →', callback_data=f'hist_page:{page + 1}'))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text='Новый чат', callback_data='hist_new')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_page(target, tg_user, state, page=0, edit=False):
    chats, total = await get_chat_page(tg_user.user, page)
    if state:
        await state.update_data(hist_page=page)
        await state.set_state(HistoryFSM.browsing)
    if not chats:
        text = 'История чатов пуста. Начни новый диалог!'
        kb = None
    else:
        text = f'<b>История чатов</b> ({total} всего):'
        kb = _history_kb(chats, page, total)
    if edit and hasattr(target, 'edit_text'):
        try:
            await target.edit_text(text, parse_mode='HTML', reply_markup=kb)
            return
        except Exception:
            pass
    await target.answer(text, parse_mode='HTML', reply_markup=kb)


@router.message(Command('history'))
async def cmd_history(message: Message, state: FSMContext = None, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжи аккаунт через /start')
        return
    await _show_page(message, tg_user, state, page=0, edit=False)


@router.callback_query(F.data.startswith('hist_page:'))
async def cb_hist_page(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    try:
        page = int(query.data.split(':')[1])
    except (ValueError, IndexError):
        page = 0
    await _show_page(query.message, tg_user, state, page=page, edit=True)
    await query.answer()


@router.callback_query(F.data.startswith('hist_open:'))
async def cb_hist_open(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    try:
        chat_id = int(query.data.split(':')[1])
        chat = await activate_chat(tg_user, chat_id)
        title = chat.title or 'Чат'
        if state:
            await state.clear()
        await query.message.edit_text(
            f'Чат <b>{title}</b> активирован. Продолжай диалог!',
            parse_mode='HTML',
        )
    except Exception as e:
        logger.warning(f'hist_open error: {e}')
        await query.message.edit_text('Чат не найден.')
    await query.answer()


@router.callback_query(F.data == 'hist_new')
async def cb_hist_new(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user:
        await clear_chat(tg_user)
    if state:
        await state.clear()
    await query.message.edit_text('Новый чат начат. Задай первый вопрос!')
    await query.answer('Новый чат')


@router.callback_query(F.data == 'hist_noop')
async def cb_hist_noop(query: CallbackQuery):
    await query.answer()
