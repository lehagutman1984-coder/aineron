import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import models_tabs_kb

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_text_networks():
    from aitext.models import NeuralNetwork
    return list(NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order')[:20])


def _get_image_networks():
    from aitext.models import NeuralNetwork
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    result = []
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') != 'video':
            result.append(net)
    return result


def _get_video_networks():
    from aitext.models import NeuralNetwork
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    result = []
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') == 'video':
            result.append(net)
    return result


def _set_text_network(tg_user, network_id):
    from aitext.models import NeuralNetwork
    net = NeuralNetwork.objects.get(id=network_id, provider='openrouter', is_active=True)
    tg_user.default_network = net
    tg_user.save(update_fields=['default_network'])
    return net


def _set_image_network(tg_user, network_id):
    from aitext.models import NeuralNetwork
    net = NeuralNetwork.objects.get(id=network_id, provider='fal-ai', is_active=True)
    tg_user.default_image_network = net
    tg_user.save(update_fields=['default_image_network'])
    return net


def _set_video_network(tg_user, network_id):
    from aitext.models import NeuralNetwork
    net = NeuralNetwork.objects.get(id=network_id, provider='fal-ai', is_active=True)
    tg_user.default_video_network = net
    tg_user.save(update_fields=['default_video_network'])
    return net


get_text_networks = sync_to_async(_get_text_networks, thread_sensitive=True)
get_image_networks = sync_to_async(_get_image_networks, thread_sensitive=True)
get_video_networks = sync_to_async(_get_video_networks, thread_sensitive=True)
set_text_network = sync_to_async(_set_text_network, thread_sensitive=True)
set_image_network = sync_to_async(_set_image_network, thread_sensitive=True)
set_video_network = sync_to_async(_set_video_network, thread_sensitive=True)


# ---------------------------------------------------------------------------
# Helpers to build tab messages
# ---------------------------------------------------------------------------

TAB_TITLES = {
    'text': 'Текстовые модели',
    'image': 'Модели изображений',
    'video': 'Видео модели',
}


async def _send_tab(target, tg_user, tab: str, edit: bool = False):
    """Send or edit message with the given tab content."""
    if tab == 'text':
        networks = await get_text_networks()
        current_id = tg_user.default_network_id
    elif tab == 'image':
        networks = await get_image_networks()
        current_id = tg_user.default_image_network_id
    else:  # video
        networks = await get_video_networks()
        current_id = tg_user.default_video_network_id

    title = TAB_TITLES.get(tab, 'Модели')
    if not networks:
        text = f'<b>{title}</b>\n\nНет доступных моделей.'
    else:
        text = f'<b>{title}:</b>'

    kb = models_tabs_kb(tab, networks, current_id)

    if edit:
        await target.edit_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await target.answer(text, parse_mode='HTML', reply_markup=kb)


# ---------------------------------------------------------------------------
# Command /models
# ---------------------------------------------------------------------------

@router.message(or_f(Command('models'), F.text == 'Модели'))
async def cmd_models(message: Message, tg_user=None):
    if tg_user is None:
        return
    await _send_tab(message, tg_user, 'text', edit=False)


# ---------------------------------------------------------------------------
# Tab switch callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith('models_tab:'))
async def cb_models_tab(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    tab = query.data.split(':')[1]  # 'text' | 'image' | 'video'
    if tab not in ('text', 'image', 'video'):
        await query.answer('Неизвестная вкладка')
        return
    try:
        await _send_tab(query.message, tg_user, tab, edit=True)
    except Exception as e:
        logger.warning('cb_models_tab error: %s', e)
    await query.answer()


# ---------------------------------------------------------------------------
# Set model callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith('setmodel:'))
async def cb_set_model(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return

    parts = query.data.split(':')
    # New format: setmodel:<type>:<id>
    # Legacy format (text only): setmodel:<id>
    if len(parts) == 3:
        _, model_type, network_id_str = parts
        network_id = int(network_id_str)
    elif len(parts) == 2:
        model_type = 'text'
        network_id = int(parts[1])
    else:
        await query.answer('Неверный формат')
        return

    try:
        if model_type == 'text':
            net = await set_text_network(tg_user, network_id)
            label = 'Текстовая модель'
            tab = 'text'
        elif model_type == 'image':
            net = await set_image_network(tg_user, network_id)
            label = 'Модель изображений'
            tab = 'image'
        elif model_type == 'video':
            net = await set_video_network(tg_user, network_id)
            label = 'Видео модель'
            tab = 'video'
        else:
            await query.answer('Неизвестный тип модели')
            return
    except Exception as e:
        logger.error('cb_set_model error: %s', e)
        await query.answer(f'Ошибка: {e}')
        return

    await query.answer(f'Выбрана: {net.name}')
    # Refresh the tab view
    try:
        # Re-fetch tg_user to get updated FK ids
        def _reload(tg_user_obj):
            tg_user_obj.refresh_from_db()
            return tg_user_obj
        reload_tg_user = sync_to_async(_reload, thread_sensitive=True)
        tg_user = await reload_tg_user(tg_user)
        await _send_tab(query.message, tg_user, tab, edit=True)
    except Exception:
        await query.message.edit_text(
            f'{label} изменена: <b>{net.name}</b>', parse_mode='HTML'
        )
