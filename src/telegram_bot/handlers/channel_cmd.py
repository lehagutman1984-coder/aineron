"""S11 — Канал-мейкер: AI-контент-завод для админов Telegram-каналов.

/channel — мастер подключения: бот проверяет свои админ-права в канале,
пользователь задаёт тему и расписание → создаётся AITask с deliver_chat_id
канала (движок S2 публикует посты по расписанию, веб-поиск даёт свежие факты).
B2B-выручка: каждый пост оплачивается по цене сообщения модели.
"""
import html
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import card

logger = logging.getLogger(__name__)
router = Router()

SCHEDULES = {
    'daily9': {'label': 'Ежедневно в 09:00', 'schedule_type': 'daily', 'time': '09:00'},
    'daily18': {'label': 'Ежедневно в 18:00', 'schedule_type': 'daily', 'time': '18:00'},
    'weekly_mon': {'label': 'Еженедельно, пн 10:00', 'schedule_type': 'weekly',
                   'time': '10:00', 'weekday': 0},
    'weekly_fri': {'label': 'Еженедельно, пт 17:00', 'schedule_type': 'weekly',
                   'time': '17:00', 'weekday': 4},
}


class ChannelFSM(StatesGroup):
    waiting_channel = State()
    waiting_topic = State()
    waiting_schedule = State()


@router.message(Command('channel'))
async def cmd_channel(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    await state.set_state(ChannelFSM.waiting_channel)
    await message.answer(
        card('Канал-мейкер',
             'AI будет публиковать посты в ваш канал по расписанию: '
             'свежие факты из веб-поиска, готовый текст, без вашего участия.\n\n'
             '1. Добавьте бота администратором канала (право «Публикация сообщений»)\n'
             '2. Пришлите сюда @username канала или перешлите любой пост из него',
             'Каждый пост оплачивается по цене сообщения модели.'),
        parse_mode='HTML',
    )


@router.message(ChannelFSM.waiting_channel)
async def on_channel_input(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await state.clear()
        return

    # Канал: пересланный пост или @username
    channel_ref = None
    forward_chat = getattr(message, 'forward_from_chat', None)
    if forward_chat is not None and forward_chat.type == 'channel':
        channel_ref = forward_chat.id
    else:
        text = (message.text or '').strip()
        if text.startswith('@') and len(text) > 2:
            channel_ref = text
        elif text.lstrip('-').isdigit():
            channel_ref = int(text)

    if channel_ref is None:
        await message.answer(
            'Не понял. Пришлите @username канала или перешлите пост из него. '
            'Отмена: /cancel',
        )
        return

    # Проверяем канал и права бота
    try:
        chat = await message.bot.get_chat(channel_ref)
        if chat.type != 'channel':
            await message.answer('Это не канал. Пришлите @username канала.')
            return
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat.id, me.id)
        can_post = getattr(member, 'can_post_messages', False) or member.status == 'creator'
        if member.status not in ('administrator', 'creator') or not can_post:
            await message.answer(
                'Бот не администратор канала или без права «Публикация сообщений». '
                'Выдайте права и пришлите канал ещё раз.',
            )
            return
    except Exception as e:
        logger.warning(f'channel check failed: {e}')
        await message.answer(
            'Не удалось проверить канал. Убедитесь, что бот добавлен '
            'администратором, и пришлите @username ещё раз.',
        )
        return

    await state.update_data(channel_id=chat.id, channel_title=chat.title or str(chat.id))
    await state.set_state(ChannelFSM.waiting_topic)
    await message.answer(
        f'Канал «{html.escape(chat.title or "")}» подключён.\n\n'
        f'О чём писать посты? Опишите тему и стиль, например:\n'
        f'«новости AI для предпринимателей, деловой тон, 3–5 абзацев, '
        f'в конце — практический вывод»',
        parse_mode='HTML',
    )


@router.message(ChannelFSM.waiting_topic)
async def on_channel_topic(message: Message, state: FSMContext, tg_user=None):
    topic = (message.text or '').strip()
    if not topic:
        await message.answer('Пустая тема — попробуйте ещё раз.')
        return
    await state.update_data(topic=topic[:800])
    await state.set_state(ChannelFSM.waiting_schedule)
    rows = [[InlineKeyboardButton(text=cfg['label'], callback_data=f'chsched:{key}')]
            for key, cfg in SCHEDULES.items()]
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='chsched:cancel')])
    await message.answer(
        'Как часто публиковать?',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith('chsched:'), ChannelFSM.waiting_schedule)
async def cb_channel_schedule(query: CallbackQuery, state: FSMContext, tg_user=None):
    key = query.data.split(':', 1)[1]
    if key == 'cancel' or tg_user is None:
        await state.clear()
        await query.message.edit_text('Подключение канала отменено.')
        await query.answer()
        return
    cfg = SCHEDULES.get(key)
    if cfg is None:
        await query.answer('Неизвестное расписание')
        return

    data = await state.get_data()
    await state.clear()
    channel_id = data.get('channel_id')
    channel_title = data.get('channel_title', '')
    topic = data.get('topic', '')
    if not channel_id or not topic:
        await query.answer('Данные потеряны — начните заново: /channel')
        return

    # Лимит активных задач по тарифу — как у обычных AI-задач
    from telegram_bot.handlers.tasks_cmd import active_count, task_limit, create_task
    count = await active_count(tg_user.user)
    limit = await task_limit(tg_user.user)
    if count >= limit:
        await query.answer()
        await query.message.edit_text(
            card('Лимит задач',
                 f'Активных задач: {count} из {limit} по тарифу. '
                 f'Освободите слот (/tasks) или улучшите тариф: /balance'),
            parse_mode='HTML',
        )
        return

    parsed = {
        'title': f'Канал {channel_title}'[:120],
        'prompt': (
            f'Напиши готовый пост для Telegram-канала «{channel_title}». '
            f'Тема и стиль: {topic}. Используй свежие факты из веб-поиска. '
            f'Пост должен быть самодостаточным: цепляющее начало, суть, вывод. '
            f'Без хештегов и без упоминания, что ты AI.'
        ),
        'schedule_type': cfg['schedule_type'],
        'time': cfg['time'],
        'weekday': cfg.get('weekday'),
        'use_web_search': True,
    }
    task = await create_task(tg_user.user, parsed)

    # Доставка в канал, а не в личку
    @sync_to_async
    def _set_channel():
        from telegram_bot.models import AITask
        AITask.objects.filter(pk=task.pk).update(deliver_chat_id=channel_id)

    await _set_channel()
    await query.answer('Канал подключён')
    await query.message.edit_text(
        card('Канал-мейкер запущен',
             f'<b>{html.escape(channel_title)}</b>\n'
             f'Тема: {html.escape(topic[:200])}\n'
             f'Расписание: {cfg["label"].lower()}\n\n'
             f'Первый пост выйдет по расписанию. Управление: /tasks '
             f'(кнопка «Сейчас» — опубликовать немедленно)'),
        parse_mode='HTML',
    )
    await async_log_event(tg_user, 'task_run', task_id=task.pk, action='channel_created')


@router.message(Command('cancel'), ChannelFSM.waiting_channel)
@router.message(Command('cancel'), ChannelFSM.waiting_topic)
async def cmd_channel_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Подключение канала отменено.')
