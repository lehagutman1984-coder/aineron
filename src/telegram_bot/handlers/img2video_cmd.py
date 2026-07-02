"""
/img2video <prompt> — image-to-video: фото → анимация через AI-модель (Kling/Veo/Sora).

Pipeline:
  1. /img2video <prompt> → FSM ожидает фото
  2. Пользователь присылает фото
  3. Бот скачивает фото → сохраняет → получает URL
  4. Создаёт запрос к video-модели с image_url в settings
  5. Polling результата → отправляет видео документом
"""
import asyncio
import logging
import os
import tempfile
import uuid

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, URLInputFile, BufferedInputFile
from asgiref.sync import sync_to_async
from django.conf import settings as djsettings

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 5
POLL_MAX_TRIES = 60  # 5 мин


class Img2VideoFSM(StatesGroup):
    waiting_photo = State()


def _get_img2video_network():
    """Find best video network that accepts image_url input."""
    from aitext.models import NeuralNetwork
    nets = NeuralNetwork.objects.filter(
        is_active=True, handle_video=True
    ).order_by('order')
    # Prefer Kling / Veo image-to-video models
    for net in nets:
        cfg = net.config_json or {}
        meta = cfg.get('metadata', {})
        if meta.get('supports_image_to_video') or meta.get('image_to_video'):
            return net
    # Fallback: any video model (may accept image_url field)
    return nets.first()


def _create_video_request(tg_user, network, prompt: str, image_url: str):
    from aitext.models import Chat, Message as AiMsg
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Img2Video: {prompt[:50]}',
        settings={'telegram_chat_id': tg_user.telegram_id},
    )
    user_msg = AiMsg.objects.create(
        chat=chat, role='user', content=prompt,
        settings={"image_url": image_url},
    )
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMsg
    return AiMsg.objects.prefetch_related('generated_images').get(id=msg_id)


def _save_photo_to_storage(file_bytes: bytes, user) -> str:
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    path = f'attachments/{user.id}/tg/img2video/{uuid.uuid4()}.jpg'
    saved = default_storage.save(path, ContentFile(file_bytes))
    site_url = getattr(djsettings, 'SITE_URL', 'https://aineron.ru').rstrip('/')
    media_url = djsettings.MEDIA_URL.rstrip('/')
    return f'{site_url}{media_url}/{saved}'


get_img2video_network = sync_to_async(_get_img2video_network, thread_sensitive=True)
create_video_request = sync_to_async(_create_video_request, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
save_photo = sync_to_async(_save_photo_to_storage, thread_sensitive=True)


@router.message(Command('img2video'))
async def cmd_img2video(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    prompt = message.text.removeprefix('/img2video').strip()
    if not prompt:
        await message.answer(
            '<b>Image-to-Video</b>\n\n'
            'Оживи своё фото — AI создаёт видео из изображения.\n\n'
            'Использование:\n'
            '<code>/img2video плавное движение камеры вперёд</code>\n\n'
            'После команды отправь фото.',
            parse_mode='HTML',
        )
        return

    network = await get_img2video_network()
    if not network:
        await message.answer(
            'Нет доступных видео-моделей. Попробуй позже или напиши /models.'
        )
        return

    if not tg_user.user.has_enough_kopecks(network.cost_kopecks):
        from core.money import format_rub
        await message.answer(
            f'Недостаточно средств.\n'
            f'Нужно: {format_rub(network.cost_kopecks)}, у вас: {format_rub(tg_user.user.balance_kopecks)}\n\n'
            '/balance — пополнить'
        )
        return

    await state.set_state(Img2VideoFSM.waiting_photo)
    await state.update_data(prompt=prompt, network_id=network.id)
    await message.answer(
        f'Промт: <i>{prompt}</i>\n\n'
        f'Отправь фото для анимации.\n'
        f'Модель: <b>{network.name}</b>',
        parse_mode='HTML',
    )


@router.message(Img2VideoFSM.waiting_photo, F.photo)
async def handle_img2video_photo(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await state.clear()
        return

    data = await state.get_data()
    prompt = data.get('prompt', '')
    network_id = data.get('network_id')
    await state.clear()

    if not prompt or not network_id:
        await message.answer('Сессия истекла. Начни заново: /img2video <промт>')
        return

    status_msg = await message.answer('Скачиваю фото и запускаю генерацию видео...')

    try:
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await message.bot.download_file(file_info.file_path, destination=tmp_path)
            with open(tmp_path, 'rb') as f:
                file_bytes = f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        image_url = await save_photo(file_bytes, tg_user.user)

        def _get_net(nid):
            from aitext.models import NeuralNetwork
            return NeuralNetwork.objects.get(id=nid)
        network = await sync_to_async(_get_net, thread_sensitive=True)(network_id)

        assistant_msg = await create_video_request(tg_user, network, prompt, image_url)

        from aitext.tasks import generate_ai_response
        generate_ai_response.delay(assistant_msg.id)

        await status_msg.edit_text(
            f'Генерирую видео ({network.name})...\n'
            f'Это займёт 3-8 минут. Промт: <i>{prompt}</i>',
            parse_mode='HTML',
        )

        for i in range(POLL_MAX_TRIES):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                msg = await get_message_state(assistant_msg.id)
            except Exception:
                continue

            if msg.status == 'completed':
                def _get_video(m):
                    return m.generated_images.first()
                gen_item = await sync_to_async(_get_video, thread_sensitive=True)(msg)

                if gen_item:
                    await status_msg.delete()
                    video_url = f"{djsettings.SITE_URL}{gen_item.image.url}"
                    try:
                        await message.answer_video(
                            URLInputFile(video_url),
                            caption=f'{network.name} · <i>{prompt}</i>',
                            parse_mode='HTML',
                        )
                    except Exception:
                        await message.answer(f'Видео готово: {video_url}')
                else:
                    await status_msg.edit_text('Видео готово, но не найдено. Смотри /account/files/')

                await async_log_event(tg_user, 'video', network=network, cost_kopecks=network.cost_kopecks)
                return

            elif msg.status == 'failed':
                await status_msg.edit_text('Ошибка генерации видео. Попробуй ещё раз.')
                await async_log_event(tg_user, 'error', network=network, reason='img2video_failed')
                return

            if i % 6 == 0 and i > 0:
                elapsed = i * POLL_INTERVAL
                try:
                    await status_msg.edit_text(
                        f'Генерирую видео... ({elapsed}с из ~300с)\n'
                        f'Промт: <i>{prompt}</i>',
                        parse_mode='HTML',
                    )
                except Exception:
                    pass

        await status_msg.edit_text('Превышено время ожидания (5 мин). Попробуй ещё раз.')

    except Exception as e:
        logger.error(f'img2video error: {e}')
        await status_msg.edit_text('Ошибка обработки. Попробуй ещё раз.')


@router.message(Img2VideoFSM.waiting_photo)
async def handle_img2video_not_photo(message: Message, state: FSMContext, tg_user=None):
    await state.clear()
    await message.answer('Ожидал фото — отменяю. Начни заново: /img2video <промт>')
