import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import models_kb

logger = logging.getLogger(__name__)
router = Router()


def _get_text_networks():
    from aitext.models import NeuralNetwork
    return list(NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order')[:20])


def _set_network(tg_user, network_id):
    from aitext.models import NeuralNetwork
    net = NeuralNetwork.objects.get(id=network_id, provider='openrouter', is_active=True)
    tg_user.default_network = net
    tg_user.save(update_fields=['default_network'])
    return net


get_text_networks = sync_to_async(_get_text_networks, thread_sensitive=True)
set_network = sync_to_async(_set_network, thread_sensitive=True)


async def send_models(message: Message, tg_user):
    networks = await get_text_networks()
    if not networks:
        await message.answer("Нет доступных моделей.")
        return

    current_id = tg_user.default_network_id
    text = "<b>Выберите текстовую модель:</b>"
    await message.answer(text, parse_mode='HTML', reply_markup=models_kb(networks, current_id))


@router.message(or_f(Command('models'), F.text == 'Модели'))
async def cmd_models(message: Message, tg_user=None):
    if tg_user is None:
        return
    await send_models(message, tg_user)


@router.callback_query(F.data.startswith('setmodel:'))
async def cb_set_model(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    network_id = int(query.data.split(':')[1])
    try:
        net = await set_network(tg_user, network_id)
        await query.message.edit_text(f"Модель изменена: <b>{net.name}</b>", parse_mode='HTML')
    except Exception as e:
        await query.answer(f"Ошибка: {e}")
        return
    await query.answer(f"Выбрана: {net.name}")
