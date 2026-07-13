"""
/sticker <prompt> — генерация AI-стикера (PNG 512×512 с прозрачным фоном).

Pipeline:
  1. /sticker <prompt> → находим image-модель (DALL-E / Flux)
  2. Добавляем суффикс: "transparent background, sticker style, cute, clean"
  3. Генерация → скачиваем PNG → конвертируем в WEBP ≤512KB
  4. Отправляем как стикер через answer_sticker()
  5. Hint: «Хочешь стикерпак? Жми /sticker ещё раз»
"""
import asyncio
import io
import logging
import os
import tempfile

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 3
POLL_MAX_TRIES = 40

STICKER_SUFFIX = (
    ', transparent background, white background, sticker style, cute, '
    'clean lines, digital art, high quality'
)


def _get_image_network():
    from aitext.models import NeuralNetwork
    nets = NeuralNetwork.objects.filter(is_active=True).order_by('order')
    for net in nets:
        cfg = net.config_json or {}
        meta = cfg.get('metadata', {})
        out_type = meta.get('output_type', '')
        if out_type == 'image' and not meta.get('requires_input_images'):
            return net
    return None


def _create_image_request(tg_user, network, prompt: str):
    from aitext.models import Chat, Message as AiMsg
    chat = Chat.objects.create(
        user=tg_user.user,
        network=network,
        title=f'Sticker: {prompt[:40]}',
    )
    AiMsg.objects.create(chat=chat, role='user', content=prompt)
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMsg
    return AiMsg.objects.prefetch_related('generated_images').get(id=msg_id)


get_image_network = sync_to_async(_get_image_network, thread_sensitive=True)
create_image_request = sync_to_async(_create_image_request, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)


def _convert_to_sticker_png(image_bytes: bytes) -> bytes:
    """Resize image to 512×512 PNG, max 512KB."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        img = img.resize((512, 512), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='PNG', optimize=True)
        return out.getvalue()
    except Exception as e:
        logger.warning(f'sticker convert failed: {e}')
        return image_bytes


@router.message(Command('sticker'))
async def cmd_sticker(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    prompt = message.text.removeprefix('/sticker').strip()
    if not prompt:
        if lang == 'ru':
            await message.answer(
                '<b>AI-стикер</b>\n\n'
                'Создай стикер из любого описания!\n\n'
                'Использование:\n'
                '<code>/sticker милый котик в шапке детектива</code>',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('sticker.usageTitle', lang)}</b>\n\n"
                f"{t('sticker.usageDescription', lang)}\n\n"
                f"{t('sticker.usageLabel', lang)}\n"
                f"{t('sticker.usageExample', lang)}",
                parse_mode='HTML',
            )
        return

    network = await get_image_network()
    if not network:
        if lang == 'ru':
            await message.answer('Нет доступных моделей для генерации изображений.')
        else:
            await message.answer(t('sticker.noModels', lang))
        return

    if not tg_user.user.has_enough_kopecks(network.cost_kopecks):
        from core.money import format_money
        if lang == 'ru':
            await message.answer(
                f'Недостаточно средств. Нужно: {format_money(network.cost_kopecks)}, у вас: {format_money(tg_user.user.balance_kopecks)}\n'
                '/balance — пополнить'
            )
        else:
            await message.answer(
                t('sticker.insufficientFunds', lang,
                  need=format_money(network.cost_kopecks), have=format_money(tg_user.user.balance_kopecks))
            )
        return

    full_prompt = prompt + STICKER_SUFFIX
    assistant_msg = await create_image_request(tg_user, network, full_prompt)

    from aitext.tasks import generate_ai_response
    generate_ai_response.delay(assistant_msg.id)

    if lang == 'ru':
        status_msg = await message.answer(f'Рисую стикер: <i>{prompt}</i>...', parse_mode='HTML')
    else:
        status_msg = await message.answer(t('sticker.drawing', lang, prompt=prompt), parse_mode='HTML')

    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            def _get_img(m):
                return m.generated_images.first()
            gen_img = await sync_to_async(_get_img, thread_sensitive=True)(msg)

            if gen_img:
                await status_msg.delete()
                from django.conf import settings as djsettings
                import httpx
                img_url = f"{djsettings.SITE_URL}{gen_img.image.url}"
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(img_url)
                        resp.raise_for_status()
                        img_bytes = resp.content

                    sticker_bytes = await asyncio.get_event_loop().run_in_executor(
                        None, _convert_to_sticker_png, img_bytes
                    )

                    await message.answer_sticker(
                        BufferedInputFile(sticker_bytes, filename='sticker.png')
                    )
                    if lang == 'ru':
                        await message.answer(
                            f'Стикер готов! Ещё стикер: <code>/sticker ваш промт</code>',
                            parse_mode='HTML',
                        )
                    else:
                        await message.answer(t('sticker.ready', lang), parse_mode='HTML')
                except Exception as e:
                    logger.error(f'sticker send error: {e}')
                    if lang == 'ru':
                        await message.answer(f'Стикер создан: {img_url}')
                    else:
                        await message.answer(t('sticker.resultReady', lang, url=img_url))

                await async_log_event(tg_user, 'image', network=network, cost_kopecks=network.cost_kopecks)
            else:
                if lang == 'ru':
                    await status_msg.edit_text('Стикер создан, но не найден. Попробуй ещё раз.')
                else:
                    await status_msg.edit_text(t('sticker.notFound', lang))
            return

        elif msg.status == 'failed':
            if lang == 'ru':
                await status_msg.edit_text('Ошибка генерации. Попробуй ещё раз.')
            else:
                await status_msg.edit_text(t('sticker.error', lang))
            return

        if i % 5 == 0 and i > 0:
            try:
                if lang == 'ru':
                    await status_msg.edit_text(f'Рисую стикер ({i * POLL_INTERVAL}с)...', parse_mode='HTML')
                else:
                    await status_msg.edit_text(t('sticker.drawingDots', lang, sec=i * POLL_INTERVAL), parse_mode='HTML')
            except Exception:
                pass

    if lang == 'ru':
        await status_msg.edit_text('Превышено время ожидания. Попробуй ещё раз.')
    else:
        await status_msg.edit_text(t('sticker.timeout', lang))
