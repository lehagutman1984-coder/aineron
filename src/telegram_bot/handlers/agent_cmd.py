"""S9 — Agent Mode: /agent <задача> — многошаговый агент с инструментами.

«Сделай отчёт: найди данные, посчитай, сведи в таблицу» — одной командой.
Агент планирует шаги (веб-поиск, вычисления) и исполняет их в цикле LLM.
Живой прогресс через DraftStreamer, цена фиксированная (AGENT_PRICE_KOPECKS)
с подтверждением; при ошибке — возврат средств (внутри Celery-задачи).
"""
import asyncio
import html
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot.notify import stream_draft_or_edit, set_status_reaction
from telegram_bot.utils import card

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 3
POLL_MAX_TRIES = 90  # ~4.5 мин (soft_time_limit задачи — 240 сек)


class AgentFSM(StatesGroup):
    confirming = State()


def _price_kopecks() -> int:
    return getattr(settings, 'AGENT_PRICE_KOPECKS', 500)


def _create_run(user, goal: str):
    from telegram_bot.models import AgentRun
    return AgentRun.objects.create(user=user, goal=goal)


def _get_run(run_id: int):
    from telegram_bot.models import AgentRun
    return AgentRun.objects.get(pk=run_id)


create_run = sync_to_async(_create_run, thread_sensitive=True)
get_run = sync_to_async(_get_run, thread_sensitive=True)


@router.message(Command('agent'))
async def cmd_agent(message: Message, state: FSMContext, tg_user=None):
    from core.money import format_rub

    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    goal = (message.text or '').removeprefix('/agent').strip()
    if not goal:
        await message.answer(
            card('Agent Mode',
                 'Многошаговый AI-агент: сам ищет данные в интернете, '
                 'делает вычисления и собирает отчёт.\n\n'
                 'Опишите задачу:\n'
                 '<code>/agent сравни цены топ-5 видеокарт и посчитай стоимость '
                 'фермы из 8 штук</code>',
                 f'Цена: {format_rub(_price_kopecks())} за запуск'),
            parse_mode='HTML',
        )
        return

    price = _price_kopecks()
    if not tg_user.user.has_enough_kopecks(price):
        await message.answer(
            card('Недостаточно средств',
                 f'Agent Mode стоит {format_rub(price)}. '
                 f'У вас: {format_rub(tg_user.user.balance_kopecks)}.\n\n'
                 'Пополните баланс: /balance'),
            parse_mode='HTML',
        )
        return

    await state.set_state(AgentFSM.confirming)
    await state.update_data(goal=goal)
    await message.answer(
        card('Agent Mode',
             f'<b>Задача:</b> {html.escape(goal)}\n\n'
             f'Агент выполнит до 6 шагов (поиск, вычисления) и пришлёт отчёт. '
             f'Займёт 1–3 минуты.',
             f'Цена: {format_rub(price)}'),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f'Запустить · {format_rub(price)}',
                                 callback_data='agent_go'),
            InlineKeyboardButton(text='Отмена', callback_data='agent_cancel'),
        ]]),
    )


@router.callback_query(F.data == 'agent_cancel', AgentFSM.confirming)
async def cb_agent_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text('Запуск агента отменён.')
    await query.answer()


@router.callback_query(F.data == 'agent_go', AgentFSM.confirming)
async def cb_agent_go(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    data = await state.get_data()
    goal = data.get('goal')
    await state.clear()
    if not goal:
        await query.answer('Задача потеряна — начните заново: /agent')
        return
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    run = await create_run(tg_user.user, goal)
    from telegram_bot.tasks import run_agent
    run_agent.delay(run.pk)

    await set_status_reaction(query.bot, query.message.chat.id,
                              query.message.message_id, '👀')

    # Живой прогресс: доставку отчёта делает Celery (notify_user_rich),
    # здесь только транслируем шаги и убираем статус по завершении
    streamer = stream_draft_or_edit(query.message, min_edit_interval=3.5)
    await streamer.start('Agent Mode: планирую шаги...')

    last_steps = 0
    for _ in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            current = await get_run(run.pk)
        except Exception:
            continue

        steps = current.steps or []
        if len(steps) > last_steps:
            last_steps = len(steps)
            await streamer.update(
                f'Agent Mode · шаг {len(steps)}\n{steps[-1].get("text", "")}',
            )

        if current.status in ('done', 'error'):
            if streamer.sent is not None:
                try:
                    await streamer.sent.delete()
                except Exception:
                    pass
            await set_status_reaction(query.bot, query.message.chat.id,
                                      query.message.message_id, None)
            return

    # Отчёт придёт от Celery, даже если поллинг закончился раньше
    if streamer.sent is not None:
        try:
            await streamer.sent.edit_text('Agent Mode работает — отчёт придёт сообщением.')
        except Exception:
            pass