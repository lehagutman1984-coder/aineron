"""S8 — Managed Bots: «Собери своего AI-бота за 2 минуты» (за флагом TG_MANAGED_BOTS).

Пользователь получает собственного бота (@his_name_bot) с персоной, базой
знаний (проект) и моделью. Токен добывается через getManagedBotToken
(Bot API 9.6); fallback — пользователь создаёт бота в BotFather и присылает
токен. Сообщения гостей оплачиваются с баланса владельца.
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot import capabilities
from telegram_bot.utils import DIVIDER, card

logger = logging.getLogger(__name__)
router = Router()

MAX_MANAGED_BOTS = 3


class MyBotFSM(StatesGroup):
    name = State()
    persona = State()
    greeting = State()
    token = State()


def _list_bots(tg_user):
    from telegram_bot.models import ManagedBot
    return list(ManagedBot.objects.filter(owner=tg_user).order_by('-created_at'))


def _create_bot(tg_user, data: dict, token: str, bot_username: str):
    from telegram_bot.models import ManagedBot
    return ManagedBot.objects.create(
        owner=tg_user,
        token=token,
        bot_username=bot_username,
        name=data.get('name', 'AI-агент')[:100],
        system_prompt=data.get('persona', ''),
        greeting=data.get('greeting') or 'Привет! Я AI-ассистент. Задайте вопрос.',
    )


def _delete_bot(tg_user, bot_id: int):
    from telegram_bot.models import ManagedBot
    bot = ManagedBot.objects.filter(owner=tg_user, pk=bot_id).first()
    if bot is None:
        return None
    token = bot.token
    bot.delete()
    return token


list_bots = sync_to_async(_list_bots, thread_sensitive=True)
create_bot = sync_to_async(_create_bot, thread_sensitive=True)
delete_bot = sync_to_async(_delete_bot, thread_sensitive=True)


async def _setup_managed_webhook(managed_bot) -> bool:
    """Ставит вебхук личного бота на наш мультиплексор."""
    from aiogram import Bot
    site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru').rstrip('/')
    url = f'{site_url}/telegram/managed/{managed_bot.pk}/webhook/'
    b = Bot(token=managed_bot.token)
    try:
        await b.set_webhook(
            url=url,
            secret_token=managed_bot.webhook_secret(),
            drop_pending_updates=True,
            allowed_updates=['message'],
        )
        return True
    except Exception as e:
        logger.warning(f'managed webhook setup failed: {e}')
        return False
    finally:
        await b.session.close()


@router.message(Command('mybot'))
async def cmd_mybot(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    if not capabilities.is_enabled('managed_bots'):
        await message.answer(
            'Персональные AI-боты скоро появятся — следите за новостями aineron.',
        )
        return

    bots = await list_bots(tg_user)
    rows = []
    lines = ['Соберите собственного AI-бота: имя, персона, приветствие — '
             'и ваш @бот отвечает гостям выбранной моделью.', '']
    if bots:
        lines.append('Ваши боты:')
        for b in bots:
            status = 'активен' if b.is_active else 'выключен'
            lines.append(f'@{b.bot_username} — {b.name} ({status}, '
                         f'{b.messages_count} сообщ.)')
            rows.append([InlineKeyboardButton(
                text=f'Удалить @{b.bot_username}',
                callback_data=f'mybot_del:{b.pk}',
            )])
    if len(bots) < MAX_MANAGED_BOTS:
        rows.insert(0, [InlineKeyboardButton(text='Создать бота', callback_data='mybot_new')])
    await message.answer(
        card('Персональный AI-бот', '\n'.join(lines),
             'Сообщения гостей оплачиваются с вашего баланса по цене модели.'),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
    )


@router.callback_query(F.data == 'mybot_new')
async def cb_mybot_new(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    bots = await list_bots(tg_user)
    if len(bots) >= MAX_MANAGED_BOTS:
        await query.answer(f'Максимум {MAX_MANAGED_BOTS} бота', show_alert=True)
        return
    await query.answer()
    await state.set_state(MyBotFSM.name)
    await query.message.answer('Шаг 1/4. Как назвать вашего AI-агента? (до 100 символов)')


@router.message(MyBotFSM.name)
async def on_mybot_name(message: Message, state: FSMContext):
    name = (message.text or '').strip()[:100]
    if not name:
        await message.answer('Пустое имя — попробуйте ещё раз.')
        return
    await state.update_data(name=name)
    await state.set_state(MyBotFSM.persona)
    await message.answer(
        'Шаг 2/4. Опишите персону: кто этот агент и как отвечает?\n\n'
        'Например: «Консультант интернет-магазина спортивного питания, '
        'отвечает дружелюбно и коротко, рекомендует товары из каталога».',
    )


@router.message(MyBotFSM.persona)
async def on_mybot_persona(message: Message, state: FSMContext):
    await state.update_data(persona=(message.text or '').strip()[:2000])
    await state.set_state(MyBotFSM.greeting)
    await message.answer(
        'Шаг 3/4. Приветствие для /start (или «-», чтобы оставить стандартное):',
    )


@router.message(MyBotFSM.greeting)
async def on_mybot_greeting(message: Message, state: FSMContext, tg_user=None):
    text = (message.text or '').strip()
    await state.update_data(greeting='' if text == '-' else text[:1000])

    # Пытаемся получить токен автоматически (Bot API 9.6)
    get_token = getattr(message.bot, 'get_managed_bot_token', None)
    if get_token is not None:
        try:
            data = await state.get_data()
            result = await get_token(user_id=message.from_user.id, name=data.get('name'))
            token = getattr(result, 'token', None)
            username = getattr(result, 'username', '') or ''
            if token:
                await _finalize(message, state, tg_user, token, username)
                return
        except Exception as e:
            logger.warning(f'get_managed_bot_token failed, fallback to BotFather: {e}')

    await state.set_state(MyBotFSM.token)
    await message.answer(
        card('Шаг 4/4. Токен бота',
             '1. Откройте @BotFather → /newbot\n'
             '2. Придумайте имя и username (например, my_shop_ai_bot)\n'
             '3. Пришлите сюда токен вида <code>123456:ABC-DEF...</code>',
             'Токен хранится только для работы вашего бота.'),
        parse_mode='HTML',
    )


@router.message(MyBotFSM.token)
async def on_mybot_token(message: Message, state: FSMContext, tg_user=None):
    token = (message.text or '').strip()
    if ':' not in token or len(token) < 20:
        await message.answer('Это не похоже на токен BotFather. Пришлите токен ещё раз.')
        return
    # Проверяем токен через getMe
    from aiogram import Bot
    username = ''
    try:
        b = Bot(token=token)
        me = await b.get_me()
        username = me.username or ''
        await b.session.close()
    except Exception:
        await message.answer('Токен не работает. Проверьте и пришлите ещё раз.')
        return
    try:
        await message.delete()  # не оставляем токен в чате
    except Exception:
        pass
    await _finalize(message, state, tg_user, token, username)


async def _finalize(message: Message, state: FSMContext, tg_user, token: str, username: str):
    data = await state.get_data()
    await state.clear()
    if tg_user is None:
        return
    managed = await create_bot(tg_user, data, token, username)
    ok = await _setup_managed_webhook(managed)
    if not ok:
        await message.answer(
            'Бот создан, но вебхук не установился — попробуйте /mybot позже '
            'или обратитесь в поддержку.',
        )
        return
    await message.answer(
        card('Ваш AI-бот запущен',
             f'<b>@{username}</b> — «{data.get("name")}»\n\n'
             f'Отправьте боту /start и проверьте ответы. Гости бота могут '
             f'писать без регистрации — сообщения оплачиваются с вашего баланса.',
             'Управление: /mybot'),
        parse_mode='HTML',
    )


@router.callback_query(F.data.startswith('mybot_del:'))
async def cb_mybot_del(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    bot_id = int(query.data.split(':')[1])
    token = await delete_bot(tg_user, bot_id)
    if token is None:
        await query.answer('Бот не найден')
        return
    # Снимаем вебхук удалённого бота
    try:
        from aiogram import Bot
        b = Bot(token=token)
        await b.delete_webhook(drop_pending_updates=True)
        await b.session.close()
    except Exception:
        pass
    await query.answer('Бот удалён')
    try:
        await query.message.delete()
    except Exception:
        pass
