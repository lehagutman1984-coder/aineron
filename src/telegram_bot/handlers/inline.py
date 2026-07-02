import hashlib
import logging
from aiogram import Router
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InlineQueryResultPhoto,
    InputTextMessageContent, ChosenInlineResult,
)
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()


def _get_tg_user(telegram_id):
    from telegram_bot.models import TelegramUser
    try:
        return TelegramUser.objects.select_related('user', 'default_network').get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


_get_tg_user_async = sync_to_async(_get_tg_user, thread_sensitive=True)


def _create_inline_message(tg_user, text):
    from aitext.models import Chat, Message as AiMsg, NeuralNetwork
    network = tg_user.default_network
    if not network:
        network = NeuralNetwork.objects.filter(
            provider='openrouter', is_active=True,
        ).order_by('order').first()
    if not network:
        return None
    if not tg_user.user.has_enough_kopecks(network.cost_kopecks):
        return None
    chat = Chat.objects.create(
        user=tg_user.user, network=network,
        title=f'Inline: {text[:40]}',
    )
    AiMsg.objects.create(chat=chat, role='user', content=text)
    assistant_msg = AiMsg.objects.create(
        chat=chat, role='assistant',
        status=AiMsg.Status.PENDING, content='',
    )
    return assistant_msg


_create_inline_message_async = sync_to_async(_create_inline_message, thread_sensitive=True)


@router.inline_query()
async def handle_inline(query: InlineQuery):
    text = query.query.strip()
    tg_user = await _get_tg_user_async(query.from_user.id)

    if not tg_user:
        result = InlineQueryResultArticle(
            id='auth',
            title='Привяжи аккаунт aineron.ru',
            description='Нажми чтобы узнать как',
            input_message_content=InputTextMessageContent(
                message_text='Для использования: напиши /start боту @aineron_bot и привяжи аккаунт aineron.ru'
            ),
        )
        await query.answer([result], cache_time=10, is_personal=True)
        return

    if not text:
        # Inline 2.0: пустой запрос — свои свежие генерации, шаринг одним тапом
        results = [InlineQueryResultArticle(
            id='hint',
            title='Задай вопрос AI',
            description='Введи запрос после @aineron_bot',
            input_message_content=InputTextMessageContent(
                message_text='Введи запрос после @aineron_bot для получения ответа AI'
            ),
        )]

        def _recent_images(user):
            from django.conf import settings as dj
            from django.db.models import Q
            from aitext.models import GeneratedImage
            gens = (
                GeneratedImage.objects
                .filter(Q(message__chat__user=user) | Q(user=user), media_type='image')
                .exclude(image='').order_by('-created_at')[:5]
            )
            site = getattr(dj, 'SITE_URL', 'https://aineron.ru')
            urls = []
            for g in gens:
                try:
                    urls.append((g.pk, f'{site}{g.image.url}', (g.prompt or '')[:80]))
                except Exception:
                    continue
            return urls

        try:
            images = await sync_to_async(_recent_images, thread_sensitive=True)(tg_user.user)
            for pk, url, prompt in images:
                results.append(InlineQueryResultPhoto(
                    id=f'gen{pk}',
                    photo_url=url,
                    thumbnail_url=url,
                    caption=f'Создано в aineron: {prompt}' if prompt else 'Создано в aineron',
                ))
        except Exception as e:
            logger.debug(f'inline gallery skipped: {e}')

        await query.answer(results, cache_time=5, is_personal=True)
        return

    result_id = hashlib.md5(f'{query.from_user.id}:{text}'.encode()).hexdigest()[:8]
    model_name = tg_user.default_network.name if tg_user.default_network else 'AI'

    result = InlineQueryResultArticle(
        id=result_id,
        title=f'Спросить {model_name}',
        description=text[:100],
        input_message_content=InputTextMessageContent(
            message_text=f'<i>Генерирую ответ...</i>\n\n<b>Вопрос:</b> {text[:200]}',
            parse_mode='HTML',
        ),
    )
    await query.answer([result], cache_time=0, is_personal=True)


@router.chosen_inline_result()
async def handle_chosen_inline(result: ChosenInlineResult):
    """Start actual AI generation after user picks the inline result."""
    tg_user = await _get_tg_user_async(result.from_user.id)
    if not tg_user or not result.inline_message_id:
        return
    text = result.query
    assistant_msg = await _create_inline_message_async(tg_user, text)
    if assistant_msg:
        from aitext.tasks import generate_ai_response
        generate_ai_response.delay(assistant_msg.id)
        await async_log_event(tg_user, 'inline', query=text[:100])
