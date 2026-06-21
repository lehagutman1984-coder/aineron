import asyncio
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 10        # seconds between status checks
POLL_MAX_TRIES = 120      # 120 × 10s = 20 minutes max
PROGRESS_EVERY = 3        # update progress message every N polls (~30 sec)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_video_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_video_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_video_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    # Fallback: first active video model
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') == 'video':
            return net
    return None


def _create_video_request(tg_user, network, prompt):
    from aitext.models import Chat, Message as AiMsg
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Telegram video: {prompt[:50]}',
    )
    AiMsg.objects.create(chat=chat, role='user', content=prompt)
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMsg
    return AiMsg.objects.select_related('chat__user').prefetch_related('generated_images').get(id=msg_id)


def _get_first_video(msg):
    """Return first generated image/video record attached to this message."""
    return msg.generated_images.first()


get_video_network = sync_to_async(_get_video_network, thread_sensitive=True)
create_video_request = sync_to_async(_create_video_request, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
get_first_video = sync_to_async(_get_first_video, thread_sensitive=True)


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

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
        await message.answer(
            'Нет доступных моделей для генерации видео.\n'
            'Выберите модель: /models'
        )
        return

    if tg_user.user.pages_count < network.cost_per_message:
        await message.answer(
            f'Недостаточно звёзд.\n'
            f'Нужно: {network.cost_per_message}, у вас: {tg_user.user.pages_count}\n\n'
            f'Пополните баланс: /balance'
        )
        return

    status_msg = await message.answer(
        f'Генерирую видео... (обычно 5-15 мин)\n'
        f'Модель: {network.name}\n'
        f'Стоимость: {network.cost_per_message} зв.',
        parse_mode='HTML',
    )

    assistant_msg = await create_video_request(tg_user, network, prompt)

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)

        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            video_record = await get_first_video(msg)

            await status_msg.delete()

            if video_record and video_record.image:
                video_url = f'{settings.SITE_URL}{video_record.image.url}'
            else:
                video_url = None

            if video_url:
                try:
                    await message.answer_video(
                        URLInputFile(video_url, filename='video.mp4'),
                        caption=f'{network.name} · {network.cost_per_message} зв.',
                    )
                except Exception:
                    try:
                        await message.answer_document(
                            URLInputFile(video_url, filename='video.mp4'),
                            caption=f'{network.name} · {network.cost_per_message} зв.',
                        )
                    except Exception:
                        await message.answer(f'Видео готово: {video_url}')
            else:
                await message.answer(
                    'Видео сгенерировано. Смотри в кабинете: /account/files/'
                )
            return

        elif msg.status == 'failed':
            await status_msg.edit_text(
                'Ошибка генерации видео. Попробуй позже — звёзды возвращены.'
            )
            return

        # Progress update every PROGRESS_EVERY polls
        if i > 0 and i % PROGRESS_EVERY == 0:
            elapsed = i * POLL_INTERVAL
            minutes = elapsed // 60
            seconds = elapsed % 60
            dots = '.' * ((i // PROGRESS_EVERY) % 4 + 1)
            elapsed_str = f'{minutes} мин {seconds} сек' if minutes else f'{seconds} сек'
            try:
                await status_msg.edit_text(
                    f'Генерирую видео{dots} ({elapsed_str})\n'
                    f'Модель: {network.name}'
                )
            except Exception:
                pass

    await status_msg.edit_text(
        'Превышено время ожидания (20 мин). Возможно видео ещё генерируется — '
        'проверь через несколько минут в /account/files/'
    )
