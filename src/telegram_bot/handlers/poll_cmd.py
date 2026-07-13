"""
§7.13 Telegram polls → AI-анализ — /poll FSM.

Flow:
  /poll → ask question → ask options (comma-separated) → send Telegram poll
  → user closes poll → bot receives PollAnswer updates → AI summary dispatched
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, Poll, PollAnswer
from asgiref.sync import sync_to_async
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


class PollStates(StatesGroup):
    waiting_question = State()
    waiting_options = State()


@sync_to_async
def _create_poll_session(tg_user, question: str, options: list, telegram_poll_id: str, chat_id: int):
    from telegram_bot.models import PollSession
    return PollSession.objects.create(
        tg_user=tg_user,
        question=question,
        options=options,
        vote_counts=[0] * len(options),
        telegram_poll_id=telegram_poll_id,
        chat_id=chat_id,
    )


@sync_to_async
def _get_poll_session(telegram_poll_id: str):
    from telegram_bot.models import PollSession
    try:
        return PollSession.objects.get(telegram_poll_id=telegram_poll_id, status='active')
    except PollSession.DoesNotExist:
        return None


@sync_to_async
def _record_vote(session_id: int, option_ids: list):
    """Increment vote_counts for given option indices atomically."""
    from telegram_bot.models import PollSession
    from django.db import transaction
    with transaction.atomic():
        session = PollSession.objects.select_for_update().get(pk=session_id)
        counts = list(session.vote_counts)
        for idx in option_ids:
            if 0 <= idx < len(counts):
                counts[idx] += 1
        session.vote_counts = counts
        session.save(update_fields=['vote_counts'])


@sync_to_async
def _close_poll_session(telegram_poll_id: str):
    from telegram_bot.models import PollSession
    updated = PollSession.objects.filter(telegram_poll_id=telegram_poll_id, status='active').update(status='closed')
    if updated:
        try:
            return PollSession.objects.get(telegram_poll_id=telegram_poll_id)
        except PollSession.DoesNotExist:
            return None
    return None


@router.message(Command('poll'))
async def cmd_poll(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await state.set_state(PollStates.waiting_question)
    if lang == 'ru':
        await message.answer(
            '<b>Создать AI-опрос</b>\n\nВведите вопрос опроса:',
            parse_mode='HTML',
        )
    else:
        await message.answer(
            f"<b>{t('poll.createTitle', lang)}</b>\n\n{t('poll.askQuestion', lang)}",
            parse_mode='HTML',
        )


@router.message(PollStates.waiting_question)
async def poll_got_question(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await state.update_data(poll_question=message.text or '')
    await state.set_state(PollStates.waiting_options)
    if lang == 'ru':
        await message.answer(
            'Введите варианты ответа через запятую (2–10 вариантов):\n\n'
            '<i>Пример: Да, Нет, Затрудняюсь ответить</i>',
            parse_mode='HTML',
        )
    else:
        await message.answer(
            f"{t('poll.askOptions', lang)}\n\n<i>{t('poll.optionsExample', lang)}</i>",
            parse_mode='HTML',
        )


@router.message(PollStates.waiting_options)
async def poll_got_options(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    raw = message.text or ''
    options = [o.strip() for o in raw.split(',') if o.strip()]
    if len(options) < 2:
        await message.answer(
            'Нужно минимум 2 варианта ответа, введите их через запятую.' if lang == 'ru'
            else t('poll.needMoreOptions', lang)
        )
        return
    if len(options) > 10:
        await message.answer(
            'Максимум 10 вариантов. Сократите список.' if lang == 'ru'
            else t('poll.tooManyOptions', lang)
        )
        return

    data = await state.get_data()
    question = data.get('poll_question', '')
    await state.clear()

    # Send native Telegram poll
    sent = await message.answer_poll(
        question=question[:300],
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
    )

    tg_poll_id = sent.poll.id if sent.poll else ''
    await _create_poll_session(tg_user, question, options, tg_poll_id, message.chat.id)
    if lang == 'ru':
        await message.answer(
            'Опрос отправлен! После завершения я сделаю AI-анализ результатов.\n'
            'Закройте опрос через меню Telegram, когда будете готовы.',
        )
    else:
        await message.answer(t('poll.sent', lang))


@router.poll()
async def on_poll_closed(poll: Poll):
    """Called when a poll is stopped (is_closed=True)."""
    if not poll.is_closed:
        return
    session = await _get_poll_session(poll.id)
    if not session:
        return
    # Sync final counts from Telegram
    counts = [opt.voter_count for opt in poll.options]
    from django.db import close_old_connections
    close_old_connections()
    from telegram_bot.models import PollSession
    await sync_to_async(PollSession.objects.filter(pk=session.pk).update)(
        vote_counts=counts, status='closed'
    )
    from telegram_bot.tasks import summarize_poll
    summarize_poll.delay(session.pk)


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer):
    """Track individual answers for live counts."""
    session = await _get_poll_session(poll_answer.poll_id)
    if not session:
        return
    await _record_vote(session.pk, poll_answer.option_ids)
