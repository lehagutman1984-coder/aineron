import asyncio
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 3
POLL_MAX_TRIES = 30  # 90 секунд


def _get_image_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_image_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_image_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    # Исключаем видео-модели (они имеют config_json.metadata.output_type = "video")
    from django.db.models import Q
    nets = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        if cfg.get('metadata', {}).get('output_type') != 'video':
            return net
    return None


def _create_image_request(tg_user, network, prompt):
    from aitext.models import Chat, Message as AiMsg
    from telegram_bot.models import TelegramChat
    # Используем отдельный чат для изображений (не мешаем текстовому контексту)
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Telegram image: {prompt[:50]}',
    )
    user_msg = AiMsg.objects.create(chat=chat, role='user', content=prompt)
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMsg
    return AiMsg.objects.select_related('chat__user').prefetch_related('generated_images').get(id=msg_id)


get_image_network = sync_to_async(_get_image_network, thread_sensitive=True)
create_image_request = sync_to_async(_create_image_request, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)


@router.message(Command('image'))
async def cmd_image(message: Message, tg_user=None):
    if tg_user is None:
        return

    prompt = message.text.removeprefix('/image').strip()
    if not prompt:
        await message.answer(
            "Укажи описание изображения:\n"
            "<code>/image закат над морем в стиле аниме</code>",
            parse_mode='HTML',
        )
        return

    network = await get_image_network(tg_user)
    if not network:
        await message.answer("Нет доступных моделей для генерации изображений.")
        return

    if tg_user.user.pages_count < network.cost_per_message:
        await message.answer(
            f"Недостаточно звёзд.\n"
            f"Нужно: {network.cost_per_message}, у вас: {tg_user.user.pages_count}\n\n"
            f"Пополните баланс: /balance"
        )
        return

    status_msg = await message.answer(
        f"Генерирую изображение... (обычно 15-30 сек)\n"
        f"Модель: {network.name}"
    )

    assistant_msg = await create_image_request(tg_user, network, prompt)

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            def _get_first_image(m):
                return m.generated_images.first()

            get_img = sync_to_async(_get_first_image, thread_sensitive=True)
            image = await get_img(msg)

            if image:
                await status_msg.delete()
                img_url = f"{settings.SITE_URL}{image.image.url}"
                try:
                    await message.answer_photo(
                        URLInputFile(img_url),
                        caption=f"{network.name} · {network.cost_per_message} зв.",
                    )
                except Exception:
                    await message.answer(f"Изображение готово: {img_url}")
            else:
                await status_msg.edit_text("Изображение сгенерировано, но не найдено. Проверь /account/files/")
            await async_log_event(tg_user, 'image', network=network,
                                  cost=network.cost_per_message)
            return

        elif msg.status == 'failed':
            await status_msg.edit_text(
                "Ошибка генерации. Попробуй позже — звёзды возвращены."
            )
            await async_log_event(tg_user, 'error', network=network, reason='image_failed')
            return

        # Анимация ожидания
        if i % 5 == 0 and i > 0:
            dots = '.' * ((i // 5) % 4 + 1)
            try:
                await status_msg.edit_text(
                    f"Генерирую{dots} ({i * POLL_INTERVAL} сек)\n"
                    f"Модель: {network.name}"
                )
            except Exception:
                pass

    await status_msg.edit_text("Превышено время ожидания. Попробуй ещё раз.")
