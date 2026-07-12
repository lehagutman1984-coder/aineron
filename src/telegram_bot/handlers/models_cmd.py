import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import models_tabs_kb
from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

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
# Tab messages
# ---------------------------------------------------------------------------

def _tab_titles(lang):
    return {
        'text': t('models.textModels', lang),
        'image': t('models.imageModels', lang),
        'video': t('models.videoModels', lang),
    }


async def _send_tab(target, tg_user, tab: str, edit: bool = False, lang: str = 'ru'):
    if tab == 'text':
        networks = await get_text_networks()
        current_id = tg_user.default_network_id
        current_name = tg_user.default_network.name if tg_user.default_network else '—'
    elif tab == 'image':
        networks = await get_image_networks()
        current_id = tg_user.default_image_network_id
        current_name = tg_user.default_image_network.name if tg_user.default_image_network else '—'
    else:
        networks = await get_video_networks()
        current_id = tg_user.default_video_network_id
        current_name = tg_user.default_video_network.name if tg_user.default_video_network else '—'

    title = _tab_titles(lang).get(tab, t('models.genericTitle', lang))

    if not networks:
        text = f'<b>Aineron · {title}</b>\n{DIVIDER}\n{t("models.noModels", lang)}'
    else:
        text = (
            f'<b>Aineron · {title}</b>\n{DIVIDER}\n'
            f'{t("models.current", lang)}: <b>{current_name}</b>\n\n'
            f'{t("models.choose", lang)}'
        )

    kb = models_tabs_kb(tab, networks, current_id, lang=lang)

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
    lang = resolve_language(tg_user, message.from_user)
    await _send_tab(message, tg_user, 'text', edit=False, lang=lang)


# ---------------------------------------------------------------------------
# Tab switch callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith('models_tab:'))
async def cb_models_tab(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    tab = query.data.split(':')[1]
    if tab not in ('text', 'image', 'video'):
        await query.answer(t('models.unknownTab', lang))
        return
    # Сначала снимаем «часики» с кнопки, потом рисуем вкладку
    await query.answer()
    try:
        await _send_tab(query.message, tg_user, tab, edit=True, lang=lang)
    except Exception as e:
        logger.warning('cb_models_tab error: %s', e, exc_info=True)
        try:
            await query.message.answer(t('models.tabOpenFailed', lang))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Set model callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith('setmodel:'))
async def cb_set_model(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)

    parts = query.data.split(':')
    if len(parts) == 3:
        _, model_type, network_id_str = parts
        network_id = int(network_id_str)
    elif len(parts) == 2:
        model_type = 'text'
        network_id = int(parts[1])
    else:
        await query.answer(t('models.invalidFormat', lang))
        return

    try:
        if model_type == 'text':
            net = await set_text_network(tg_user, network_id)
            tab = 'text'
        elif model_type == 'image':
            net = await set_image_network(tg_user, network_id)
            tab = 'image'
        elif model_type == 'video':
            net = await set_video_network(tg_user, network_id)
            tab = 'video'
        else:
            await query.answer(t('models.unknownModelType', lang))
            return
    except Exception as e:
        logger.error('cb_set_model error: %s', e)
        await query.answer(f"{t('models.errorPrefix', lang)}: {e}")
        return

    await query.answer(t('models.selected', lang, name=net.name))
    try:
        # refresh_from_db() сбрасывает кэш FK — доступ к default_*_network в
        # async-коде после него ронял SynchronousOnlyOperation. Перечитываем
        # объект целиком с select_related, как это делает AuthMiddleware.
        def _reload(telegram_id):
            from telegram_bot.models import TelegramUser
            return TelegramUser.objects.select_related(
                'user', 'default_network', 'default_image_network', 'default_video_network',
            ).get(telegram_id=telegram_id)
        reload_tg_user = sync_to_async(_reload, thread_sensitive=True)
        tg_user = await reload_tg_user(tg_user.telegram_id)
        await _send_tab(query.message, tg_user, tab, edit=True, lang=lang)
    except Exception:
        await query.message.edit_text(
            f"<b>{t('models.modelChangedTitle', lang)}</b>\n{DIVIDER}\n<b>{net.name}</b>",
            parse_mode='HTML',
        )
