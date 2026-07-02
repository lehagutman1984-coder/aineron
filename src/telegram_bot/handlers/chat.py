import asyncio
import logging
from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from telegram_bot import capabilities
from telegram_bot.keyboards import after_answer_kb, main_reply_kb
from telegram_bot.notify import (
    stream_draft_or_edit, set_status_reaction, send_rich_or_markdown,
)
from telegram_bot.rich import extract_first_code
from telegram_bot.utils import telegram_format, split_message, DIVIDER
from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()


class EditMsgFSM(StatesGroup):
    waiting_new_text = State()

POLL_INTERVAL = 2       # секунд между проверками
POLL_MAX_TRIES = 75     # 150 секунд максимум
STREAM_UPDATE_EVERY = 3 # обновлять превью каждые N итераций
EDIT_MIN_INTERVAL = 3.5 # минимум секунд между edit_text (Telegram rate limit)


def _get_default_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    network = NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order').first()
    if network is None:
        network = NeuralNetwork.objects.filter(is_active=True).order_by('order').first()
    return network


def _ensure_chat(tg_user, network):
    """Возвращает активный чат, создавая новый если нужно.

    При наличии active_project чат привязывается к проекту.
    Если активный проект изменился — создаём новый чат.
    """
    from aitext.models import Chat
    from telegram_bot.models import TelegramChat
    project = tg_user.active_project  # может быть None

    tc = TelegramChat.objects.filter(tg_user=tg_user, is_active=True).select_related('chat').first()
    if tc and tc.chat_id:
        chat = tc.chat
        # Если проект у чата не совпадает с active_project — создаём новый чат
        if chat.project_id != (project.id if project else None):
            TelegramChat.objects.filter(tg_user=tg_user, is_active=True).update(is_active=False)
            title = f'Telegram — {project.name}' if project else 'Telegram'
            chat = Chat.objects.create(user=tg_user.user, network=network, title=title, project=project)
            TelegramChat.objects.create(tg_user=tg_user, chat=chat, is_active=True)
        return chat

    title = f'Telegram — {project.name}' if project else 'Telegram'
    chat = Chat.objects.create(user=tg_user.user, network=network, title=title, project=project)
    if tc:
        tc.chat = chat
        tc.save(update_fields=['chat'])
    else:
        TelegramChat.objects.create(tg_user=tg_user, chat=chat, is_active=True)
    return chat


def _create_messages(chat, user_text, network, system_prompt='', extra_settings=None):
    from aitext.models import Message as AiMessage
    user_msg = AiMessage.objects.create(chat=chat, role='user', content=user_text)
    assistant_msg = AiMessage.objects.create(
        chat=chat, role='assistant',
        status=AiMessage.Status.PENDING,
        content='',
        settings=extra_settings or {},
    )
    return user_msg, assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMessage
    return AiMessage.objects.get(id=msg_id)


def _check_balance(user, cost_kopecks):
    return user.has_enough_kopecks(cost_kopecks)


get_default_network = sync_to_async(_get_default_network, thread_sensitive=True)
ensure_chat = sync_to_async(_ensure_chat, thread_sensitive=True)
create_messages = sync_to_async(_create_messages, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
check_balance = sync_to_async(_check_balance, thread_sensitive=True)


async def process_text(tg_message: Message, tg_user, text: str, attachment=None,
                       skip_billing: bool = False, chat_override=None):
    """Общий пайплайн: текст → AI → ответ с polling.

    skip_billing=True  — биллинг уже снят на стороне вызывающего (оргбиллинг).
    chat_override      — передать готовый объект Chat (напр., для изолированных групповых чатов).
    """
    from aitext.tasks import generate_ai_response

    network = await get_default_network(tg_user)
    if not network:
        await tg_message.answer("Нет доступных моделей. Обратитесь в поддержку.")
        return

    if not skip_billing:
        has_balance = await check_balance(tg_user.user, network.cost_kopecks)
        if not has_balance:
            from core.money import format_rub
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Telegram Stars (XTR)', callback_data='buy_stars')],
                [InlineKeyboardButton(text='Карта / СБП (Robokassa)', callback_data='buy_robokassa')],
                [InlineKeyboardButton(text='Пополнить на сайте', url='https://aineron.ru/account/billing/')],
            ])
            await tg_message.answer(
                f'<b>Недостаточно средств</b>\n{DIVIDER}\n'
                f'Нужно: <b>{format_rub(network.cost_kopecks)}</b>   У вас: {format_rub(tg_user.user.balance_kopecks)}\n\n'
                f'Пополните баланс:',
                parse_mode='HTML',
                reply_markup=kb,
            )
            await async_log_event(tg_user, 'error', network=network, reason='no_balance')
            return

    extra_settings = {'skip_star_billing': True} if skip_billing else {}
    chat = chat_override if chat_override is not None else await ensure_chat(tg_user, network)
    user_msg, assistant_msg = await create_messages(chat, text, network, tg_user.system_prompt, extra_settings)

    generate_ai_response.delay(assistant_msg.id, web_search=getattr(tg_user, 'web_search', False))

    # S1: реакция-статус «запрос принят» на сообщение пользователя
    await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, '👀')

    project = tg_user.active_project
    status_prefix = f'[{project.name}] ' if project else ''
    # S1: нативный стриминг через sendMessageDraft (fallback — edit с троттлингом)
    streamer = stream_draft_or_edit(tg_message, min_edit_interval=EDIT_MIN_INTERVAL)
    await streamer.start(f"{status_prefix}Генерирую ответ...")

    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            full_text = msg.plain_text or msg.content or ''
            markup = after_answer_kb(msg.id, copy_code=extract_first_code(full_text))
            delivered = False
            # S1: Rich Messages — таблицы, код, thinking-блоки (за флагом)
            if capabilities.available('rich_messages', tg_message.bot):
                try:
                    await send_rich_or_markdown(
                        tg_message.bot, tg_message.chat.id, full_text, reply_markup=markup,
                    )
                    if streamer.sent is not None:
                        try:
                            await streamer.sent.delete()
                        except Exception:
                            pass
                    delivered = True
                except Exception as e:
                    logger.warning(f'rich delivery failed, fallback to HTML: {e}')
            if not delivered:
                parts = split_message(telegram_format(full_text))
                await streamer.finish(parts, reply_markup=markup)
            await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
            await async_log_event(tg_user, 'message', network=network,
                                  cost_kopecks=network.cost_kopecks)
            return

        elif msg.status == 'failed':
            await streamer.fail("Ошибка генерации. Попробуйте ещё раз.")
            await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
            await async_log_event(tg_user, 'error', network=network, reason='generation_failed')
            return

        # Стриминг частичного ответа (draft или edit с троттлингом внутри стримера)
        if tg_user.streaming and i % STREAM_UPDATE_EVERY == 0:
            partial = (msg.plain_text or msg.content or '').strip()
            if partial:
                await streamer.update(partial)

    await streamer.fail("Превышено время ожидания. Попробуйте ещё раз.")
    await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
    await async_log_event(tg_user, 'error', network=network, reason='timeout')


@router.message(F.text.startswith('/newchat') | (F.text == 'Новый чат'))
async def cmd_newchat(message: Message, tg_user=None):
    if tg_user is None:
        return
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u, is_active=True).update(is_active=False)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await message.answer("Новый диалог начат. Напишите первый вопрос.", reply_markup=main_reply_kb())


@router.callback_query(F.data == 'newchat')
async def cb_newchat(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u, is_active=True).update(is_active=False)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await query.message.answer("Новый диалог начат. Напишите первый вопрос.")
    await query.answer()


@router.callback_query(F.data.startswith('regen:'))
async def cb_regen(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    msg_id = int(query.data.split(':')[1])

    def _get_original_text(m_id):
        from aitext.models import Message as AiMsg
        msg = AiMsg.objects.get(id=m_id)
        chat = msg.chat
        user_msg = chat.messages.filter(
            role='user', created_at__lt=msg.created_at
        ).order_by('-created_at').first()
        return user_msg.content if user_msg else None

    get_orig = sync_to_async(_get_original_text, thread_sensitive=True)
    text = await get_orig(msg_id)
    if text:
        await query.answer("Повторяю запрос...")
        await process_text(query.message, tg_user, text)
    else:
        await query.answer("Не могу найти исходный запрос.")


@router.callback_query(F.data.startswith('react_like:'))
async def cb_react_like(query: CallbackQuery, tg_user=None):
    """👍 — positive reaction, just acknowledge."""
    await query.answer("Рад помочь!")


@router.callback_query(F.data.startswith('react_dislike:'))
async def cb_react_dislike(query: CallbackQuery, tg_user=None):
    """👎 — negative reaction, regenerate with improvement hint."""
    if tg_user is None:
        await query.answer()
        return
    msg_id = int(query.data.split(':')[1])

    def _get_original_text(m_id):
        from aitext.models import Message as AiMsg
        msg = AiMsg.objects.get(id=m_id)
        chat = msg.chat
        user_msg = chat.messages.filter(
            role='user', created_at__lt=msg.created_at
        ).order_by('-created_at').first()
        return user_msg.content if user_msg else None

    get_orig = sync_to_async(_get_original_text, thread_sensitive=True)
    text = await get_orig(msg_id)
    if text:
        await query.answer("Пересматриваю ответ...")
        improved_prompt = f"{text}\n\n[Предыдущий ответ не устроил. Ответь подробнее и точнее.]"
        await process_text(query.message, tg_user, improved_prompt)
    else:
        await query.answer("Не могу найти исходный запрос.")


@router.callback_query(F.data.startswith('edit_msg:'))
async def cb_edit_msg(query: CallbackQuery, state: FSMContext, tg_user=None):
    """✏️ — ask user for new text, then regenerate."""
    if tg_user is None:
        await query.answer()
        return
    msg_id = int(query.data.split(':')[1])
    await state.set_state(EditMsgFSM.waiting_new_text)
    await state.update_data(original_msg_id=msg_id, edit_query_msg_id=query.message.message_id)
    await query.answer()
    await query.message.reply("Отправь новый текст запроса:")


@router.message(EditMsgFSM.waiting_new_text)
async def handle_edit_new_text(message: Message, state: FSMContext, tg_user=None):
    """Receive new text for edit, regenerate."""
    if tg_user is None:
        await state.clear()
        return
    new_text = (message.text or '').strip()
    if not new_text:
        await message.answer("Пустой текст — отмена редактирования.")
        await state.clear()
        return
    await state.clear()
    await process_text(message, tg_user, new_text)


@router.callback_query(F.data.startswith('del_msg:'))
async def cb_del_msg(query: CallbackQuery, tg_user=None):
    """🗑️ — delete the bot's message and mark DB message as deleted."""
    if tg_user is None:
        await query.answer()
        return
    msg_id = int(query.data.split(':')[1])

    @sync_to_async
    def _mark_deleted(m_id):
        from aitext.models import Message as AiMsg
        try:
            AiMsg.objects.filter(id=m_id, chat__user=tg_user.user).update(
                status=AiMsg.Status.FAILED,
                error_message='[Удалено пользователем]',
            )
        except Exception:
            pass

    await _mark_deleted(msg_id)
    try:
        await query.message.delete()
    except Exception:
        await query.answer("Не удалось удалить сообщение.")
    else:
        await query.answer("Удалено.")


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message, tg_user=None):
    if tg_user is None:
        return
    # S2: детект интента «задача по расписанию» — предложить создать AI-задачу
    try:
        from telegram_bot.handlers.tasks_cmd import looks_like_task_intent
        if looks_like_task_intent(message.text):
            from django.core.cache import cache
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            set_cached = sync_to_async(cache.set, thread_sensitive=True)
            await set_cached(f'tg_task_intent:{tg_user.telegram_id}', message.text, 600)
            await message.answer(
                'Похоже на задачу по расписанию. Могу выполнять её автоматически.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text='Создать AI-задачу', callback_data='task_intent'),
                ]]),
            )
    except Exception as e:
        logger.debug(f'task intent detect skipped: {e}')
    await process_text(message, tg_user, message.text)
