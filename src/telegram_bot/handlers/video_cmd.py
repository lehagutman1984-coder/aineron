import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

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
            'Укажи описание видео:\n'
            '<code>/video закат над морем, медленный полёт камеры</code>',
            parse_mode='HTML',
        )
        return

    network = await get_video_network(tg_user)
    if not network:
        await message.answer('Нет доступных моделей для генерации видео. Выбери модель: /models')
        return

    if tg_user.user.pages_count < network.cost_per_message:
        await message.answer(
            f'Недостаточно звёзд.\n'
            f'Нужно: {network.cost_per_message}, у вас: {tg_user.user.pages_count}\n\n'
            f'Пополните баланс: /balance'
        )
        return

    assistant_msg = await create_video_request(tg_user, network, prompt, message.chat.id)

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    # Возвращаем ответ сразу — без polling внутри webhook
    await message.answer(
        f'Видео поставлено в очередь.\n'
        f'Модель: <b>{network.name}</b> · {network.cost_per_message} зв.\n\n'
        f'Пришлю когда готово (обычно 5-15 мин).',
        parse_mode='HTML',
    )
