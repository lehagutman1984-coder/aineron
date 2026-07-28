import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


def _get_image_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_image_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_image_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    # Исключаем видео-модели (они имеют config_json.metadata.output_type = "video")
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') != 'video':
            return net
    return None


def get_stored_image_settings(tg_user, network) -> tuple[dict, int]:
    """Настройки /imgset для модели + доплата в рублях (чистая функция)."""
    stored = dict((getattr(tg_user, 'image_settings', None) or {}).get(str(network.id), {}))
    if not stored:
        return {}, 0
    from telegram_bot.handlers.video_settings_cmd import _calc_extra_cost
    return stored, _calc_extra_cost(network.config_json or {}, stored)


def _create_image_request(tg_user, network, prompt, telegram_chat_id, user_settings=None):
    from aitext.models import Chat, Message as AiMsg
    # BUG-H: без settings={'telegram_chat_id': ...} Celery не может доставить
    # готовое изображение push'ем (tasks.py читает именно это поле) — раньше
    # доставка держалась только на бот-стороннем поллинге в 90 секунд, и любая
    # генерация дольше этого срока приходила голой ссылкой уже после того, как
    # бот сказал пользователю «таймаут» (см. TELEGRAM_SUPREMACY_PLAN_V2.md).
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Telegram image: {prompt[:50]}',
        settings={'telegram_chat_id': telegram_chat_id},
    )
    AiMsg.objects.create(chat=chat, role='user', content=prompt, settings=user_settings or {})
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


get_image_network = sync_to_async(_get_image_network, thread_sensitive=True)
create_image_request = sync_to_async(_create_image_request, thread_sensitive=True)


@router.message(Command('image'))
async def cmd_image(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)

    prompt = message.text.removeprefix('/image').strip()
    if not prompt:
        await message.answer(
            f"<b>{t('images.title', lang)}</b>\n{DIVIDER}\n"
            f"{t('images.describe', lang)}\n\n{t('images.example', lang)}",
            parse_mode='HTML',
        )
        return

    network = await get_image_network(tg_user)
    if not network:
        await message.answer(t('images.noModels', lang))
        return

    stored_settings, extra_rub = get_stored_image_settings(tg_user, network)
    total_kopecks = network.cost_kopecks + extra_rub * 100

    if not tg_user.user.has_enough_kopecks(total_kopecks):
        from core.money import format_money
        await message.answer(
            f"<b>{t('images.insufficientTitle', lang)}</b>\n{DIVIDER}\n"
            f"{t('images.need', lang)}: <b>{format_money(total_kopecks)}</b>   "
            f"{t('images.have', lang)}: {format_money(tg_user.user.balance_kopecks)}\n\n"
            f"{t('images.topUp', lang)}",
            parse_mode='HTML',
        )
        return

    # S1: реакция-статус «запрос принят» (результат придёт из Celery позже —
    # push-доставка, та же схема, что у /video, см. _create_image_request)
    from telegram_bot.notify import set_status_reaction
    await set_status_reaction(message.bot, message.chat.id, message.message_id, '👀')

    assistant_msg = await create_image_request(
        tg_user, network, prompt, message.chat.id, user_settings=stored_settings,
    )

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    from core.money import format_money
    settings_line = t('images.settingsApplied', lang) if stored_settings else ''
    await message.answer(
        f"<b>{t('images.title', lang)}</b>\n{DIVIDER}\n"
        f"{t('images.requestAccepted', lang)}\n\n"
        f"{t('images.modelLabel', lang)}: <b>{network.name}</b>  ·  {format_money(total_kopecks)}{settings_line}\n"
        f"{t('images.readyHint', lang)}",
        parse_mode='HTML',
    )
    await async_log_event(tg_user, 'image', network=network, cost_kopecks=total_kopecks)
