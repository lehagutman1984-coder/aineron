"""
/img2img <prompt> — image-to-image: фото → редактирование через AI-модель.

Пайплайн:
  1. /img2img <prompt> → FSM ожидает фото
  2. Пользователь присылает фото
  3. Бот скачивает фото → сохраняет в storage → получает URL
  4. Передаёт URL и промт в image-модель с supports_input_image=True
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
from aiogram.types import Message, URLInputFile
from asgiref.sync import sync_to_async
from django.conf import settings as djsettings

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 3
POLL_MAX_TRIES = 40  # 2 мин


class Img2ImgFSM(StatesGroup):
    waiting_photo = State()


def _get_img2img_network():
    """Find best image-to-image capable network."""
    from aitext.models import NeuralNetwork
    # Prefer networks with supports_input_image in metadata
    nets = NeuralNetwork.objects.filter(is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        meta = cfg.get('metadata', {})
        if meta.get('supports_input_image') or meta.get('requires_input_images'):
            return net
    # Fallback: use default image network (GPT Image or Flux support img2img via image_url)
    for net in nets:
        cfg = net.config_json or {}
        meta = cfg.get('metadata', {})
        out_type = meta.get('output_type', '')
        if out_type == 'image' and meta.get('requires_input_images') is not True:
            return net
    return None


def _create_img2img_request(tg_user, network, prompt: str, image_url: str):
    from aitext.models import Chat, Message as AiMsg
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Img2Img: {prompt[:50]}',
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
    """Save photo bytes to storage, return public URL."""
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    path = f'attachments/{user.id}/tg/img2img/{uuid.uuid4()}.jpg'
    saved = default_storage.save(path, ContentFile(file_bytes))
    # Build absolute URL
    site_url = getattr(djsettings, 'SITE_URL', 'https://aineron.ru').rstrip('/')
    media_url = djsettings.MEDIA_URL.rstrip('/')
    return f'{site_url}{media_url}/{saved}'


get_img2img_network = sync_to_async(_get_img2img_network, thread_sensitive=True)
create_img2img_request = sync_to_async(_create_img2img_request, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
save_photo = sync_to_async(_save_photo_to_storage, thread_sensitive=True)


@router.message(Command('img2img'))
async def cmd_img2img(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    prompt = message.text.removeprefix('/img2img').strip()
    if not prompt:
        await message.answer(
            '🎨 <b>Image-to-Image</b>\n\n'
            'Отредактируй существующее фото с помощью AI.\n\n'
            'Использование:\n'
            '<code>/img2img сделай стиль аниме</code>\n\n'
            'После команды отправь фото которое нужно изменить.',
            parse_mode='HTML',
        )
        return

    network = await get_img2img_network()
    if not network:
        await message.answer('Нет доступных моделей для image-to-image. Попробуй позже.')
        return

    if tg_user.user.pages_count < network.cost_per_message:
        await message.answer(
            f'Недостаточно звёзд.\n'
            f'Нужно: {network.cost_per_message}, у вас: {tg_user.user.pages_count}\n\n'
            f'Пополните баланс: /balance'
        )
        return

    await state.set_state(Img2ImgFSM.waiting_photo)
    await state.update_data(prompt=prompt, network_id=network.id)
    await message.answer(
        f'✅ Промт сохранён: <i>{prompt}</i>\n\n'
        f'📸 Теперь отправь фото которое нужно изменить.\n'
        f'Модель: <b>{network.name}</b>',
        parse_mode='HTML',
    )


@router.message(Img2ImgFSM.waiting_photo, F.photo)
async def handle_img2img_photo(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await state.clear()
        return

    data = await state.get_data()
    prompt = data.get('prompt', '')
    network_id = data.get('network_id')
    await state.clear()

    if not prompt or not network_id:
        await message.answer('Сессия истекла. Начни заново: /img2img <промт>')
        return

    status_msg = await message.answer('⏳ Скачиваю фото и запускаю генерацию...')

    try:
        # Download photo
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        ext = '.jpg'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
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

        # Save to storage and get URL
        image_url = await save_photo(file_bytes, tg_user.user)

        # Get network
        def _get_net(nid):
            from aitext.models import NeuralNetwork
            return NeuralNetwork.objects.get(id=nid)
        network = await sync_to_async(_get_net, thread_sensitive=True)(network_id)

        # Create generation request
        assistant_msg = await create_img2img_request(tg_user, network, prompt, image_url)

        from aitext.tasks import generate_ai_response
        generate_ai_response.delay(assistant_msg.id)

        await status_msg.edit_text(
            f'🎨 Генерирую ({network.name})...\n'
            f'Промт: <i>{prompt}</i>',
            parse_mode='HTML',
        )

        # Poll for result
        for i in range(POLL_MAX_TRIES):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                msg = await get_message_state(assistant_msg.id)
            except Exception:
                continue

            if msg.status == 'completed':
                def _get_img(m):
                    return m.generated_images.first()
                get_img = sync_to_async(_get_img, thread_sensitive=True)
                image = await get_img(msg)

                if image:
                    await status_msg.delete()
                    img_url = f"{djsettings.SITE_URL}{image.image.url}"
                    try:
                        await message.answer_photo(
                            URLInputFile(img_url),
                            caption=f'🎨 {network.name} · <i>{prompt}</i>',
                            parse_mode='HTML',
                        )
                    except Exception:
                        await message.answer(f'Готово: {img_url}')
                else:
                    await status_msg.edit_text('Изображение готово, но не найдено. Проверь /account/files/')

                await async_log_event(tg_user, 'image', network=network, cost=network.cost_per_message)
                return

            elif msg.status == 'failed':
                await status_msg.edit_text('Ошибка генерации. Попробуй ещё раз.')
                await async_log_event(tg_user, 'error', network=network, reason='img2img_failed')
                return

            if i % 5 == 0 and i > 0:
                dots = '.' * ((i // 5) % 4 + 1)
                try:
                    await status_msg.edit_text(
                        f'🎨 Генерирую{dots} ({i * POLL_INTERVAL}с)\n'
                        f'Промт: <i>{prompt}</i>',
                        parse_mode='HTML',
                    )
                except Exception:
                    pass

        await status_msg.edit_text('Превышено время ожидания. Попробуй ещё раз.')

    except Exception as e:
        logger.error(f'img2img error: {e}')
        await status_msg.edit_text('Ошибка обработки. Попробуй ещё раз.')


@router.message(Img2ImgFSM.waiting_photo)
async def handle_img2img_not_photo(message: Message, state: FSMContext, tg_user=None):
    """Cancel FSM if user sends something other than a photo."""
    await state.clear()
    await message.answer('Ожидал фото — отменяю. Начни заново: /img2img <промт>')
