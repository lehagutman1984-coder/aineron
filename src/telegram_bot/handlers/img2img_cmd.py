"""
/img2img <prompt> — image-to-image: фото → редактирование через AI-модель.

Пайплайн:
  1. /img2img <prompt> → FSM ожидает фото
  2. Пользователь присылает фото
  3. Бот скачивает фото → сохраняет в storage → получает URL
  4. Передаёт URL и промт в image-модель с supports_input_image=True
"""
import logging
import os
import tempfile
import uuid

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.conf import settings as djsettings

from telegram_bot.analytics import async_log_event
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


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
        # requires_input_images/supports_input_image также используются
        # image-to-VIDEO моделями (Vidu Q3 и т.п.) — без исключения
        # output_type='video' /img2img молча роутил запросы на видео-модель
        # (найдено 2026-07-27 при проверке /imgset для BUG-D, live: Vidu Q3
        # был единственным совпадением по этим флагам).
        if meta.get('output_type') == 'video':
            continue
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


def _create_img2img_request(tg_user, network, prompt: str, image_url: str, telegram_chat_id, user_settings=None):
    from aitext.models import Chat, Message as AiMsg
    # BUG-H: settings={'telegram_chat_id': ...} — без него Celery не может
    # push-доставить результат (см. images.py::_create_image_request), а
    # бот-сторонний поллинг (до фикса) обрывался по таймауту раньше реальной
    # ошибки/готовности на генерациях дольше 2 минут.
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Img2Img: {prompt[:50]}',
        settings={'telegram_chat_id': telegram_chat_id},
    )
    user_msg = AiMsg.objects.create(
        chat=chat, role='user', content=prompt,
        settings={**(user_settings or {}), "image_url": image_url},
    )
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


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
save_photo = sync_to_async(_save_photo_to_storage, thread_sensitive=True)


@router.message(Command('img2img'))
async def cmd_img2img(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    prompt = message.text.removeprefix('/img2img').strip()
    if not prompt:
        if lang == 'ru':
            await message.answer(
                '🎨 <b>Image-to-Image</b>\n\n'
                'Отредактируй существующее фото с помощью AI.\n\n'
                'Использование:\n'
                '<code>/img2img сделай стиль аниме</code>\n\n'
                'После команды отправь фото которое нужно изменить.',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('img2img.usageTitle', lang)}</b>\n\n"
                f"{t('img2img.usageDescription', lang)}\n\n"
                f"{t('img2img.usageLabel', lang)}\n"
                f"{t('img2img.usageExample', lang)}\n\n"
                f"{t('img2img.usageSendPhoto', lang)}",
                parse_mode='HTML',
            )
        return

    network = await get_img2img_network()
    if not network:
        if lang == 'ru':
            await message.answer('Нет доступных моделей для image-to-image. Попробуй позже.')
        else:
            await message.answer(t('img2img.noModels', lang))
        return

    from telegram_bot.handlers.images import get_stored_image_settings
    _, extra_rub = get_stored_image_settings(tg_user, network)
    total_kopecks = network.cost_kopecks + extra_rub * 100

    if not tg_user.user.has_enough_kopecks(total_kopecks):
        from core.money import format_money
        if lang == 'ru':
            await message.answer(
                f'Недостаточно средств.\n'
                f'Нужно: {format_money(total_kopecks)}, у вас: {format_money(tg_user.user.balance_kopecks)}\n\n'
                f'Пополните баланс: /balance'
            )
        else:
            await message.answer(
                t('img2img.insufficientFunds', lang,
                  need=format_money(total_kopecks), have=format_money(tg_user.user.balance_kopecks))
            )
        return

    await state.set_state(Img2ImgFSM.waiting_photo)
    await state.update_data(prompt=prompt, network_id=network.id)
    if lang == 'ru':
        await message.answer(
            f'✅ Промт сохранён: <i>{prompt}</i>\n\n'
            f'📸 Теперь отправь фото которое нужно изменить.\n'
            f'Модель: <b>{network.name}</b>',
            parse_mode='HTML',
        )
    else:
        await message.answer(
            t('img2img.promptSaved', lang, prompt=prompt, name=network.name),
            parse_mode='HTML',
        )


@router.message(Img2ImgFSM.waiting_photo, F.photo)
async def handle_img2img_photo(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await state.clear()
        return
    lang = resolve_language(tg_user, message.from_user)

    data = await state.get_data()
    prompt = data.get('prompt', '')
    network_id = data.get('network_id')
    await state.clear()

    if not prompt or not network_id:
        if lang == 'ru':
            await message.answer('Сессия истекла. Начни заново: /img2img <промт>')
        else:
            await message.answer(t('img2img.sessionExpired', lang))
        return

    if lang == 'ru':
        status_msg = await message.answer('⏳ Скачиваю фото и запускаю генерацию...')
    else:
        status_msg = await message.answer(t('img2img.downloading', lang))

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

        from telegram_bot.handlers.images import get_stored_image_settings
        stored_settings, extra_rub = get_stored_image_settings(tg_user, network)
        total_kopecks = network.cost_kopecks + extra_rub * 100

        # Create generation request — telegram_chat_id включает push-доставку
        # результата из Celery (BUG-H), поллинг ниже больше не нужен.
        assistant_msg = await create_img2img_request(
            tg_user, network, prompt, image_url, message.chat.id, user_settings=stored_settings,
        )

        from aitext.tasks import generate_ai_response
        generate_ai_response.delay(assistant_msg.id)

        if lang == 'ru':
            await status_msg.edit_text(
                f'🎨 Генерирую ({network.name})...\n'
                f'Промт: <i>{prompt}</i>\n\n'
                f'Пришлю результат, как только будет готово.',
                parse_mode='HTML',
            )
        else:
            await status_msg.edit_text(
                t('img2img.generating', lang, name=network.name, prompt=prompt)
                + '\n\n' + t('images.readyHint', lang),
                parse_mode='HTML',
            )
        await async_log_event(tg_user, 'image', network=network, cost_kopecks=total_kopecks)

    except Exception as e:
        logger.error(f'img2img error: {e}')
        if lang == 'ru':
            await status_msg.edit_text('Ошибка обработки. Попробуй ещё раз.')
        else:
            await status_msg.edit_text(t('img2img.processingError', lang))


@router.message(Img2ImgFSM.waiting_photo)
async def handle_img2img_not_photo(message: Message, state: FSMContext, tg_user=None):
    """Cancel FSM if user sends something other than a photo."""
    lang = resolve_language(tg_user, message.from_user)
    await state.clear()
    if lang == 'ru':
        await message.answer('Ожидал фото — отменяю. Начни заново: /img2img <промт>')
    else:
        await message.answer(t('img2img.notPhotoCancelled', lang))
