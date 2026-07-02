import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import DIVIDER

logger = logging.getLogger(__name__)
router = Router()


def _get_video_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_video_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_video_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') == 'video':
            return net
    return None


def _create_video_request(tg_user, network, prompt, telegram_chat_id):
    from aitext.models import Chat, Message as AiMsg
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Telegram video: {prompt[:50]}',
        settings={'telegram_chat_id': telegram_chat_id},
    )
    AiMsg.objects.create(chat=chat, role='user', content=prompt)
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


get_video_network = sync_to_async(_get_video_network, thread_sensitive=True)
create_video_request = sync_to_async(_create_video_request, thread_sensitive=True)


@router.message(Command('video'))
async def cmd_video(message: Message, tg_user=None):
    if tg_user is None:
        return

    prompt = message.text.removeprefix('/video').strip()
    if not prompt:
        await message.answer(
            f'<b>Aineron · Видео</b>\n{DIVIDER}\n'
            'Опишите видео:\n\n'
            '<code>/video закат над морем, медленный полёт камеры</code>',
            parse_mode='HTML',
        )
        return

    network = await get_video_network(tg_user)
    if not network:
        await message.answer('Нет доступных моделей для генерации видео. Выберите модель: /models')
        return

    if not tg_user.user.has_enough_kopecks(network.cost_kopecks):
        from core.money import format_rub
        await message.answer(
            f'<b>Недостаточно средств</b>\n{DIVIDER}\n'
            f'Нужно: <b>{format_rub(network.cost_kopecks)}</b>   У вас: {format_rub(tg_user.user.balance_kopecks)}\n\n'
            'Пополните баланс: /balance',
            parse_mode='HTML',
        )
        return

    # S1: реакция-статус «запрос принят» (результат придёт из Celery позже)
    from telegram_bot.notify import set_status_reaction
    await set_status_reaction(message.bot, message.chat.id, message.message_id, '👀')

    assistant_msg = await create_video_request(tg_user, network, prompt, message.chat.id)

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    from core.money import format_rub
    await message.answer(
        f'<b>Aineron · Видео</b>\n{DIVIDER}\n'
        f'Запрос принят.\n\n'
        f'Модель: <b>{network.name}</b>  ·  {format_rub(network.cost_kopecks)}\n'
        f'Готово через 5–15 минут — пришлю результат.',
        parse_mode='HTML',
    )
    await async_log_event(tg_user, 'video', network=network,
                          cost_kopecks=network.cost_kopecks)
