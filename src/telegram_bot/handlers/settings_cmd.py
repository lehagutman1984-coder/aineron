import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import settings_kb, models_kb
from telegram_bot.utils import DIVIDER

logger = logging.getLogger(__name__)
router = Router()


class SettingsFSM(StatesGroup):
    waiting_system_prompt = State()


def _toggle_field(tg_user, field):
    setattr(tg_user, field, not getattr(tg_user, field))
    tg_user.save(update_fields=[field])
    return getattr(tg_user, field)


def _save_system_prompt(tg_user, text):
    tg_user.system_prompt = text
    tg_user.save(update_fields=['system_prompt'])


toggle_field = sync_to_async(_toggle_field, thread_sensitive=True)
save_system_prompt = sync_to_async(_save_system_prompt, thread_sensitive=True)


async def send_settings(message: Message, tg_user):
    model_name = tg_user.default_network.name if tg_user.default_network else '—'
    prompt_state = 'задан' if tg_user.system_prompt else 'не задан'
    text = (
        f'<b>Aineron · Настройки</b>\n{DIVIDER}\n'
        f'Модель:          {model_name}\n'
        f'Системный промт: {prompt_state}\n'
        f'{DIVIDER}\n'
        'Параметры:'
    )
    await message.answer(text, parse_mode='HTML', reply_markup=settings_kb(tg_user))


@router.message(or_f(Command('settings'), F.text == 'Настройки'))
async def cmd_settings(message: Message, tg_user=None):
    if tg_user is None:
        return
    await send_settings(message, tg_user)


@router.callback_query(F.data.startswith('toggle:'))
async def cb_toggle(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    field_map = {
        'voice': 'voice_responses',
        'search': 'web_search',
        'streaming': 'streaming',
    }
    key = query.data.split(':', 1)[1]
    field = field_map.get(key)
    if not field:
        return
    new_val = await toggle_field(tg_user, field)
    state = 'включено' if new_val else 'выключено'
    await query.answer(f'{key}: {state}')
    await query.message.edit_reply_markup(reply_markup=settings_kb(tg_user))


@router.callback_query(F.data == 'settings:sysprompt')
async def cb_set_sysprompt(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    current = tg_user.system_prompt or 'не задан'
    await query.message.answer(
        f'<b>Системный промт</b>\n{DIVIDER}\n'
        f'Текущий: <i>{current[:200]}</i>\n\n'
        'Отправьте новый промт или /cancel для отмены.',
        parse_mode='HTML',
    )
    await state.set_state(SettingsFSM.waiting_system_prompt)
    await query.answer()


@router.message(SettingsFSM.waiting_system_prompt)
async def on_system_prompt_input(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    if message.text == '/cancel':
        await state.clear()
        await message.answer("Отменено.")
        return
    await save_system_prompt(tg_user, message.text)
    await state.clear()
    await message.answer(
        f'<b>Промт сохранён</b>\n{DIVIDER}\n'
        f'<i>{(message.text or "")[:200]}</i>',
        parse_mode='HTML',
    )


@router.callback_query(F.data == 'settings:model')
async def cb_change_model(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    from telegram_bot.handlers.models_cmd import _send_tab
    await _send_tab(query.message, tg_user, 'text', edit=False)
    await query.answer()
