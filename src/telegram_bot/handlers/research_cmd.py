"""S3 — Deep Research с источниками в боте (TELEGRAM_SUPREMACY_PLAN).

/research <вопрос> — многошаговый пайплайн (реюз движка deep_research_task
с веба): декомпозиция вопроса → поиск Tavily → чтение источников → синтез
отчёта с цитатами [1][2]. Живой прогресс через DraftStreamer, доставка —
rich-сообщение + файл-экспорт .md. Цена фиксированная (RESEARCH_PRICE_KOPECKS)
с подтверждением перед запуском; при ошибке — возврат средств.
"""
import asyncio
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot.analytics import async_log_event
from telegram_bot.notify import stream_draft_or_edit, send_rich_or_markdown, set_status_reaction
from telegram_bot.utils import DIVIDER, card, telegram_format, split_message

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 3
POLL_MAX_TRIES = 110  # ~5.5 минут (soft_time_limit задачи — 300 сек)


class ResearchFSM(StatesGroup):
    confirming = State()


def _price_kopecks() -> int:
    return getattr(settings, 'RESEARCH_PRICE_KOPECKS', 1000)


def _start_research(tg_user, question: str):
    """Списание + создание Chat/Message/DeepResearch + постановка задачи.

    Возвращает (research_id, message_id) или (None, причина).
    """
    from aitext.models import Chat, Message as AiMsg, NeuralNetwork, DeepResearch
    from aitext.tasks import deep_research_task

    user = tg_user.user
    network = tg_user.default_network
    if network is None or not network.is_active:
        network = (
            NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks').first()
        )
    if network is None:
        return None, 'no_network'

    chat = Chat.objects.create(
        user=user, network=network,
        title=f'Research: {question[:60]}',
    )
    AiMsg.objects.create(chat=chat, role='user', content=question,
                         plain_text=question, status='completed')
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant', content='', plain_text='', status='pending',
    )
    research = DeepResearch.objects.create(
        chat=chat, message=assistant_msg, question=question,
    )

    # Идемпотентное списание фиксированной цены (reference research:{message_id})
    if not user.spend_kopecks(_price_kopecks(), type='spend',
                              reference=f'research:{assistant_msg.id}'):
        research.delete()
        chat.delete()
        return None, 'no_balance'

    deep_research_task.delay(research.id)
    return research.id, assistant_msg.id


def _get_research(research_id: int):
    from aitext.models import DeepResearch
    return DeepResearch.objects.select_related('message').get(pk=research_id)


def _refund(user, message_id: int):
    user.add_kopecks(_price_kopecks(), type='refund', reference=f'research:{message_id}')


start_research = sync_to_async(_start_research, thread_sensitive=True)
get_research = sync_to_async(_get_research, thread_sensitive=True)
refund = sync_to_async(_refund, thread_sensitive=True)


@router.message(Command('research'))
async def cmd_research(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    question = (message.text or '').removeprefix('/research').strip()
    await _ask_confirmation(message, state, tg_user, question)


async def _ask_confirmation(message: Message, state: FSMContext, tg_user, question: str):
    from core.money import format_rub

    if not question:
        await message.answer(
            card('Deep Research',
                 'Глубокое исследование с источниками: декомпозиция вопроса, '
                 'поиск по 5+ запросам, синтез отчёта с цитатами [1][2].\n\n'
                 'Задайте вопрос:\n'
                 '<code>/research как изменился рынок LLM в 2026 году</code>',
                 f'Цена: {format_rub(_price_kopecks())} за исследование'),
            parse_mode='HTML',
        )
        return

    price = _price_kopecks()
    if not tg_user.user.has_enough_kopecks(price):
        await message.answer(
            card('Недостаточно средств',
                 f'Deep Research стоит {format_rub(price)}. '
                 f'У вас: {format_rub(tg_user.user.balance_kopecks)}.\n\n'
                 'Пополните баланс: /balance'),
            parse_mode='HTML',
        )
        return

    await state.set_state(ResearchFSM.confirming)
    await state.update_data(question=question)
    await message.answer(
        card('Deep Research',
             f'<b>Вопрос:</b> {question}\n\n'
             f'Запущу многошаговое исследование с поиском источников '
             f'и отчётом с цитатами. Займёт 2–5 минут.',
             f'Цена: {format_rub(price)}'),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f'Запустить · {format_rub(price)}',
                                 callback_data='research_go'),
            InlineKeyboardButton(text='Отмена', callback_data='research_cancel'),
        ]]),
    )


@router.callback_query(F.data == 'research_cancel', ResearchFSM.confirming)
async def cb_research_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text('Исследование отменено.')
    await query.answer()


@router.callback_query(F.data == 'research_go', ResearchFSM.confirming)
async def cb_research_go(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    data = await state.get_data()
    question = data.get('question')
    await state.clear()
    if not question:
        await query.answer('Вопрос потерян — начните заново: /research')
        return
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    research_id, msg_id_or_reason = await start_research(tg_user, question)
    if research_id is None:
        reason = msg_id_or_reason
        text = ('Недостаточно средств. Пополните баланс: /balance'
                if reason == 'no_balance' else 'Нет доступных моделей. Обратитесь в поддержку.')
        await query.message.answer(text)
        return

    message_id = msg_id_or_reason
    await _watch_research(query.message, tg_user, research_id, message_id, question)


async def _watch_research(tg_message: Message, tg_user, research_id: int,
                          message_id: int, question: str):
    """Живой прогресс (эффект Perplexity) + финальная доставка отчёта."""
    from core.money import format_rub

    streamer = stream_draft_or_edit(tg_message, min_edit_interval=3.5)
    await streamer.start('Deep Research: планирую запросы...')

    last_step_count = 0
    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            research = await get_research(research_id)
        except Exception:
            continue

        if research.status == 'done':
            report_md = ''
            if research.message:
                report_md = research.message.plain_text or research.message.content or ''
            if not report_md.strip():
                await streamer.fail('Исследование завершилось без отчёта — средства возвращены.')
                await refund(tg_user.user, message_id)
                return

            # Доставка: rich-сообщение (или HTML-fallback) + файл-экспорт
            markup = None
            try:
                await send_rich_or_markdown(
                    tg_message.bot, tg_message.chat.id, report_md, reply_markup=markup,
                )
                if streamer.sent is not None:
                    try:
                        await streamer.sent.delete()
                    except Exception:
                        pass
            except Exception:
                parts = split_message(telegram_format(report_md))
                await streamer.finish(parts)

            try:
                doc = BufferedInputFile(
                    report_md.encode('utf-8'),
                    filename=f'research_{research_id}.md',
                )
                await tg_message.answer_document(
                    doc,
                    caption=f'Deep Research · {format_rub(_price_kopecks())}',
                )
            except Exception as e:
                logger.warning(f'research export failed: {e}')

            await async_log_event(tg_user, 'research',
                                  cost_kopecks=_price_kopecks(),
                                  research_id=research_id)
            return

        if research.status == 'error':
            await streamer.fail('Ошибка исследования — средства возвращены. Попробуйте позже.')
            await refund(tg_user.user, message_id)
            await async_log_event(tg_user, 'error', reason='research_failed',
                                  research_id=research_id)
            return

        # Прогресс: показываем последний шаг («Изучаю источник 4/9...»)
        steps = research.steps or []
        if len(steps) > last_step_count:
            last_step_count = len(steps)
            last = steps[-1]
            done = sum(1 for s in steps if s.get('kind') == 'search')
            progress_text = f'Deep Research · шаг {len(steps)}\n{last.get("text", "")}'
            if done:
                progress_text = f'Deep Research · поиск {done}\n{last.get("text", "")}'
            await streamer.update(progress_text)

    await streamer.fail('Исследование заняло слишком много времени — средства возвращены.')
    await refund(tg_user.user, message_id)
