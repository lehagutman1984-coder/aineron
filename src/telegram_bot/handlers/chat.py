import asyncio
import logging
from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from telegram_bot.keyboards import after_answer_kb, main_reply_kb
from telegram_bot.utils import telegram_format, split_message

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 2      # секунд между проверками
POLL_MAX_TRIES = 75    # 150 секунд максимум
STREAM_UPDATE_EVERY = 3  # обновлять превью каждые N итераций


def _get_default_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    return NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order').first()


def _ensure_chat(tg_user, network):
    from aitext.models import Chat
    from telegram_bot.models import TelegramChat
    tg_chat, created = TelegramChat.objects.get_or_create(tg_user=tg_user)
    if not tg_chat.chat_id:
        chat = Chat.objects.create(user=tg_user.user, network=network, title='Telegram')
        tg_chat.chat = chat
        tg_chat.save(update_fields=['chat'])
    return tg_chat.chat


def _create_messages(chat, user_text, network, system_prompt=''):
    from aitext.models import Message as AiMessage
    user_msg = AiMessage.objects.create(chat=chat, role='user', content=user_text)
    assistant_msg = AiMessage.objects.create(
        chat=chat, role='assistant',
        status=AiMessage.Status.PENDING,
        content='',
    )
    return user_msg, assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMessage
    return AiMessage.objects.get(id=msg_id)


def _check_balance(user, cost):
    return user.pages_count >= cost


get_default_network = sync_to_async(_get_default_network, thread_sensitive=True)
ensure_chat = sync_to_async(_ensure_chat, thread_sensitive=True)
create_messages = sync_to_async(_create_messages, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
check_balance = sync_to_async(_check_balance, thread_sensitive=True)


async def process_text(tg_message: Message, tg_user, text: str):
    """Общий пайплайн: текст → AI → ответ с polling."""
    from aitext.tasks import generate_ai_response

    network = await get_default_network(tg_user)
    if not network:
        await tg_message.answer("Нет доступных моделей. Обратитесь в поддержку.")
        return

    has_balance = await check_balance(tg_user.user, network.cost_per_message)
    if not has_balance:
        await tg_message.answer(
            f"Недостаточно звёзд.\n"
            f"Нужно: {network.cost_per_message}, у вас: {tg_user.user.pages_count}\n\n"
            f"Пополните баланс: /balance"
        )
        return

    chat = await ensure_chat(tg_user, network)
    user_msg, assistant_msg = await create_messages(chat, text, network, tg_user.system_prompt)

    # Запускаем генерацию
    generate_ai_response.delay(assistant_msg.id, web_search=tg_user.web_search)

    sent = await tg_message.answer("Генерирую ответ...")

    # Polling с промежуточным streaming-эффектом
    last_content = ''
    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            full_text = msg.plain_text or msg.content or ''
            parts = split_message(telegram_format(full_text))
            for j, part in enumerate(parts):
                if j == 0:
                    try:
                        await sent.edit_text(part, parse_mode='HTML',
                                             reply_markup=after_answer_kb(msg.id))
                    except Exception:
                        await tg_message.answer(part, parse_mode='HTML',
                                                reply_markup=after_answer_kb(msg.id))
                else:
                    await tg_message.answer(part, parse_mode='HTML',
                                            reply_markup=after_answer_kb(msg.id))
            return

        elif msg.status == 'failed':
            await sent.edit_text("Ошибка генерации. Попробуй ещё раз.")
            return

        # Промежуточный streaming-эффект (если включён)
        if tg_user.streaming and i % STREAM_UPDATE_EVERY == 0:
            partial = (msg.plain_text or msg.content or '').strip()
            if partial and partial != last_content and len(partial) > 20:
                last_content = partial
                try:
                    preview = telegram_format(partial[:3000]) + ' ...'
                    await sent.edit_text(preview, parse_mode='HTML')
                except Exception:
                    pass

    await sent.edit_text("Превышено время ожидания. Попробуй ещё раз.")


@router.message(F.text.startswith('/newchat') | (F.text == 'Новый чат'))
async def cmd_newchat(message: Message, tg_user=None):
    if tg_user is None:
        return
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u).update(chat=None)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await message.answer("Начинаю новый чат. Напиши первый вопрос.", reply_markup=main_reply_kb())


@router.callback_query(F.data == 'newchat')
async def cb_newchat(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u).update(chat=None)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await query.message.answer("Начинаю новый чат. Напиши первый вопрос.")
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


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message, tg_user=None):
    if tg_user is None:
        return
    # Кнопки reply-keyboard
    if message.text in ('Баланс',):
        from telegram_bot.handlers.balance import send_balance
        await send_balance(message, tg_user)
        return
    if message.text in ('Модели',):
        from telegram_bot.handlers.models_cmd import send_models
        await send_models(message, tg_user)
        return
    if message.text in ('Настройки',):
        from telegram_bot.handlers.settings_cmd import send_settings
        await send_settings(message, tg_user)
        return

    await process_text(message, tg_user, message.text)
