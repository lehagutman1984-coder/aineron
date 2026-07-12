import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


class OnboardingFSM(StatesGroup):
    choosing_model = State()


def _get_top_text_networks():
    from aitext.models import NeuralNetwork
    nets = list(
        NeuralNetwork.objects.filter(
            provider='openrouter', is_active=True, is_popular=True,
        ).order_by('order')[:6]
    )
    if not nets:
        nets = list(
            NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order')[:6]
        )
    return nets


_get_top_text_networks_async = sync_to_async(_get_top_text_networks, thread_sensitive=True)


def _set_default_network(tg_user, network_id):
    from aitext.models import NeuralNetwork
    net = NeuralNetwork.objects.get(id=network_id)
    tg_user.default_network = net
    tg_user.save(update_fields=['default_network'])
    return net


_set_default_network_async = sync_to_async(_set_default_network, thread_sensitive=True)


def _model_choice_kb(nets, lang='ru'):
    buttons = [
        [InlineKeyboardButton(text=n.name, callback_data=f'onboard_model:{n.id}')]
        for n in nets
    ]
    buttons.append([InlineKeyboardButton(text=t('onboarding.skip', lang), callback_data='onboard_skip')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def start_onboarding(message: Message, state: FSMContext, tg_user, lang: str = 'ru'):
    """Called from start.py after successful account link."""
    nets = await _get_top_text_networks_async()
    await message.answer(
        f"<b>{t('onboarding.title', lang)}</b>\n{DIVIDER}\n{t('onboarding.chooseModel', lang)}",
        parse_mode='HTML',
        reply_markup=_model_choice_kb(nets, lang),
    )
    if state:
        await state.set_state(OnboardingFSM.choosing_model)
    await async_log_event(tg_user, 'onboarding', step='start')


@router.callback_query(F.data.startswith('onboard_model:'))
async def cb_onboard_model(query: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if tg_user is None:
        await query.answer()
        return
    try:
        network_id = int(query.data.split(':')[1])
    except (ValueError, IndexError):
        await query.answer(t('onboarding.error', lang))
        return
    net = await _set_default_network_async(tg_user, network_id)
    await query.answer(t('onboarding.selected', lang, name=net.name))
    await query.message.edit_text(
        f"<b>{t('onboarding.setTitle', lang)}</b>\n{DIVIDER}\n"
        f"<b>{net.name}</b>\n\n{t('onboarding.readyQuestion', lang)}",
        parse_mode='HTML',
    )
    if state:
        await state.clear()
    await async_log_event(tg_user, 'onboarding', step='model_chosen', model=net.name)


@router.callback_query(F.data == 'onboard_skip')
async def cb_onboard_skip(query: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    await query.answer()
    await query.message.edit_text(
        f"<b>{t('onboarding.doneTitle', lang)}</b>\n{DIVIDER}\n{t('onboarding.doneBody', lang)}",
        parse_mode='HTML',
    )
    if state:
        await state.clear()
