"""
/img2video <prompt> — image-to-video: фото → анимация через AI-модель (Kling/Veo/Seedance).

Pipeline:
  1. /img2video <prompt> → FSM ожидает фото
  2. Пользователь присылает фото
  3. Бот скачивает фото → сохраняет → получает URL
  4. Создаёт запрос к video-модели с image_url в settings
  5. Polling результата → отправляет видео документом
"""
import logging
import os
import tempfile
import uuid

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, BufferedInputFile
from asgiref.sync import sync_to_async
from django.conf import settings as djsettings

from telegram_bot.analytics import async_log_event
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


class Img2VideoFSM(StatesGroup):
    waiting_photo = State()


def _get_img2video_network(tg_user=None):
    """Find best video network that accepts image_url input.

    Видео-модель определяется по metadata.output_type == 'video' (как в /models);
    handle_video здесь не подходит — это флаг «принимает видео-файлы на вход».
    """
    from aitext.models import NeuralNetwork
    nets = [
        net for net in NeuralNetwork.objects.filter(
            provider='fal-ai', is_active=True
        ).order_by('order')
        if (net.config_json or {}).get('metadata', {}).get('output_type') == 'video'
    ]
    if not nets:
        return None
    # Выбранная пользователем видео-модель (через /models)
    if tg_user is not None and tg_user.default_video_network_id:
        for net in nets:
            if net.id == tg_user.default_video_network_id:
                return net
    # Явная пометка image-to-video в metadata
    for net in nets:
        meta = (net.config_json or {}).get('metadata', {})
        if meta.get('supports_image_to_video') or meta.get('image_to_video'):
            return net
    # Модели, надёжно работающие с image_url через apimart
    for key in ('kling', 'seedance', 'veo'):
        for net in nets:
            if key in (net.model_name or '').lower():
                return net
    return nets[0]


def _create_video_request(tg_user, network, prompt: str, image_url: str, telegram_chat_id, extra_settings=None):
    from aitext.models import Chat, Message as AiMsg
    # Найдено при повторном ревью: было tg_user.telegram_id вместо
    # message.chat.id (единственный хендлер, отклонявшийся от конвенции
    # остальных push-путей — images.py/sticker_cmd.py и т.д. везде
    # используют message.chat.id). Сейчас безвредно (хендлер уже
    # приватный-only, для личного чата оба значения совпадают), но при
    # любом будущем изменении маршрутизации push ушёл бы не туда.
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Img2Video: {prompt[:50]}',
        settings={'telegram_chat_id': telegram_chat_id},
    )
    # Настройки из /videoset (длительность, качество, звук) + фото
    user_msg = AiMsg.objects.create(
        chat=chat, role='user', content=prompt,
        settings={**(extra_settings or {}), "image_url": image_url},
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


# F.chat.type == 'private' — см. images.py:cmd_image, тот же класс.
@router.message(Command('img2video'), F.chat.type == 'private')
async def cmd_img2video(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    prompt = message.text.removeprefix('/img2video').strip()
    if not prompt:
        if lang == 'ru':
            await message.answer(
                '<b>Image-to-Video</b>\n\n'
                'Оживи своё фото — AI создаёт видео из изображения.\n\n'
                'Использование:\n'
                '<code>/img2video плавное движение камеры вперёд</code>\n\n'
                'После команды отправь фото.',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('img2video.usageTitle', lang)}</b>\n\n"
                f"{t('img2video.usageDescription', lang)}\n\n"
                f"{t('img2video.usageLabel', lang)}\n"
                f"{t('img2video.usageExample', lang)}\n\n"
                f"{t('img2video.usageSendPhoto', lang)}",
                parse_mode='HTML',
            )
        return

    network = await get_img2video_network(tg_user)
    if not network:
        if lang == 'ru':
            await message.answer(
                'Нет доступных видео-моделей. Попробуй позже или напиши /models.'
            )
        else:
            await message.answer(t('img2video.noModels', lang))
        return

    from telegram_bot.handlers.video_cmd import get_stored_video_settings
    _, extra_rub = get_stored_video_settings(tg_user, network)
    total_kopecks = network.cost_kopecks + extra_rub * 100

    from telegram_bot.utils import needs_email_verification
    if needs_email_verification(tg_user.user):
        await message.answer(
            t('chat.emailNotVerifiedBody', lang) if lang != 'ru'
            else 'Подтвердите email — мы отправили код при регистрации. Введите его на сайте.'
        )
        return

    if not tg_user.user.has_enough_kopecks(total_kopecks):
        from core.money import format_money
        if lang == 'ru':
            await message.answer(
                f'Недостаточно средств.\n'
                f'Нужно: {format_money(total_kopecks)}, у вас: {format_money(tg_user.user.balance_kopecks)}\n\n'
                '/balance — пополнить'
            )
        else:
            await message.answer(
                t('img2video.insufficientFunds', lang,
                  need=format_money(total_kopecks), have=format_money(tg_user.user.balance_kopecks))
            )
        return

    await state.set_state(Img2VideoFSM.waiting_photo)
    await state.update_data(prompt=prompt, network_id=network.id)
    if lang == 'ru':
        await message.answer(
            f'Промт: <i>{prompt}</i>\n\n'
            f'Отправь фото для анимации.\n'
            f'Модель: <b>{network.name}</b>',
            parse_mode='HTML',
        )
    else:
        await message.answer(
            t('img2video.promptSaved', lang, prompt=prompt, name=network.name),
            parse_mode='HTML',
        )


@router.message(Img2VideoFSM.waiting_photo, F.photo)
async def handle_img2video_photo(message: Message, state: FSMContext, tg_user=None):
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
            await message.answer('Сессия истекла. Начни заново: /img2video <промт>')
        else:
            await message.answer(t('img2video.sessionExpired', lang))
        return

    if lang == 'ru':
        status_msg = await message.answer('Скачиваю фото и запускаю генерацию видео...')
    else:
        status_msg = await message.answer(t('img2video.downloading', lang))

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

        from telegram_bot.handlers.video_cmd import get_stored_video_settings
        stored_settings, _ = get_stored_video_settings(tg_user, network)

        assistant_msg = await create_video_request(
            tg_user, network, prompt, image_url, message.chat.id, extra_settings=stored_settings,
        )

        from aitext.tasks import generate_ai_response
        generate_ai_response.delay(assistant_msg.id)

        if lang == 'ru':
            await status_msg.edit_text(
                f'Генерирую видео ({network.name})...\n'
                f'Это займёт 3-8 минут. Промт: <i>{prompt}</i>',
                parse_mode='HTML',
            )
        else:
            await status_msg.edit_text(
                t('img2video.generating', lang, name=network.name, prompt=prompt),
                parse_mode='HTML',
            )

        # Найдено при повторном ревью: раньше здесь одновременно (а) стоял
        # telegram_chat_id в Chat.settings (push-доставка из Celery,
        # send_media_to_telegram) И (б) свой 15-минутный поллинг-цикл,
        # который САМ отправлял видео при status=='completed' — типичная
        # (не только пограничная) генерация укладывается в 15 минут,
        # получая ДВЕ отправки одного видео. Тот же класс, что уже решён
        # для /image и /video (BUG-H) — убираем поллинг, push остаётся
        # единственным путём доставки.
        await async_log_event(tg_user, 'video', network=network, cost_kopecks=network.cost_kopecks)
        if lang == 'ru':
            await status_msg.edit_text(
                f'Запрос принят: {network.name}.\n'
                f'Обычно занимает 3-8 минут — видео придёт отдельным сообщением.\n'
                f'Промт: <i>{prompt}</i>',
                parse_mode='HTML',
            )
        else:
            await status_msg.edit_text(
                t('img2video.generating', lang, name=network.name, prompt=prompt),
                parse_mode='HTML',
            )

    except Exception as e:
        logger.error(f'img2video error: {e}')
        if lang == 'ru':
            await status_msg.edit_text('Ошибка обработки. Попробуй ещё раз.')
        else:
            await status_msg.edit_text(t('img2video.processingError', lang))


@router.message(Img2VideoFSM.waiting_photo)
async def handle_img2video_not_photo(message: Message, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    await state.clear()
    if lang == 'ru':
        await message.answer('Ожидал фото — отменяю. Начни заново: /img2video <промт>')
    else:
        await message.answer(t('img2video.notPhotoCancelled', lang))
