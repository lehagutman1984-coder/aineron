import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from telegram_bot.i18n import t, resolve_language

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


def _history_kb(chats, page, total, lang: str = 'ru'):
    buttons = []
    for chat in chats:
        default_title = 'Чат' if lang == 'ru' else t('history.defaultChatTitle', lang)
        title = (chat.title or (chat.network.name if chat.network else default_title))[:35]
        date = chat.updated_at.strftime('%d.%m')
        buttons.append([InlineKeyboardButton(
            text=f'{title} · {date}',
            callback_data=f'hist_open:{chat.id}',
        )])
    nav = []
    if page > 0:
        back_label = '← Назад' if lang == 'ru' else t('history.back', lang)
        nav.append(InlineKeyboardButton(text=back_label, callback_data=f'hist_page:{page - 1}'))
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav.append(InlineKeyboardButton(text=f'{page + 1}/{pages}', callback_data='hist_noop'))
    if (page + 1) * PAGE_SIZE < total:
        forward_label = 'Вперёд →' if lang == 'ru' else t('history.forward', lang)
        nav.append(InlineKeyboardButton(text=forward_label, callback_data=f'hist_page:{page + 1}'))
    if nav:
        buttons.append(nav)
    new_chat_label = 'Новый чат' if lang == 'ru' else t('history.newChatButton', lang)
    buttons.append([InlineKeyboardButton(text=new_chat_label, callback_data='hist_new')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_page(target, tg_user, state, page=0, edit=False, lang: str = 'ru'):
    chats, total = await get_chat_page(tg_user.user, page)
    if state:
        await state.update_data(hist_page=page)
        await state.set_state(HistoryFSM.browsing)
    if not chats:
        text = 'История чатов пуста. Начни новый диалог!' if lang == 'ru' else t('history.empty', lang)
        kb = None
    else:
        text = f'<b>История чатов</b> ({total} всего):' if lang == 'ru' else t('history.title', lang, total=total)
        kb = _history_kb(chats, page, total, lang)
    if edit and hasattr(target, 'edit_text'):
        try:
            await target.edit_text(text, parse_mode='HTML', reply_markup=kb)
            return
        except Exception:
            pass
    await target.answer(text, parse_mode='HTML', reply_markup=kb)


@router.message(Command('history'))
async def cmd_history(message: Message, state: FSMContext = None, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    if tg_user is None:
        text = 'Привяжи аккаунт через /start' if lang == 'ru' else t('history.notLinked', lang)
        await message.answer(text)
        return
    await _show_page(message, tg_user, state, page=0, edit=False, lang=lang)


@router.callback_query(F.data.startswith('hist_page:'))
async def cb_hist_page(query: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if tg_user is None:
        await query.answer()
        return
    try:
        page = int(query.data.split(':')[1])
    except (ValueError, IndexError):
        page = 0
    await _show_page(query.message, tg_user, state, page=page, edit=True, lang=lang)
    await query.answer()


@router.callback_query(F.data.startswith('hist_open:'))
async def cb_hist_open(query: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if tg_user is None:
        await query.answer()
        return
    try:
        chat_id = int(query.data.split(':')[1])
        chat = await activate_chat(tg_user, chat_id)
        default_title = 'Чат' if lang == 'ru' else t('history.defaultChatTitle', lang)
        title = chat.title or default_title
        if state:
            await state.clear()
        text = (f'Чат <b>{title}</b> активирован. Продолжай диалог!' if lang == 'ru'
                else t('history.activated', lang, title=title))
        await query.message.edit_text(text, parse_mode='HTML')
    except Exception as e:
        logger.warning(f'hist_open error: {e}')
        text = 'Чат не найден.' if lang == 'ru' else t('history.notFound', lang)
        await query.message.edit_text(text)
    await query.answer()


@router.callback_query(F.data == 'hist_new')
async def cb_hist_new(query: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if tg_user:
        await clear_chat(tg_user)
    if state:
        await state.clear()
    text = 'Новый чат начат. Задай первый вопрос!' if lang == 'ru' else t('history.newChatStarted', lang)
    await query.message.edit_text(text)
    answer_text = 'Новый чат' if lang == 'ru' else t('history.newChatButton', lang)
    await query.answer(answer_text)


@router.callback_query(F.data == 'hist_noop')
async def cb_hist_noop(query: CallbackQuery):
    await query.answer()
