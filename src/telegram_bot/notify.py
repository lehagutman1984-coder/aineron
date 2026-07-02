import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='tg_notify')


def _send_sync(telegram_id: int, text: str, parse_mode: str = 'HTML') -> None:
    """Синхронная отправка уведомления — вызывается из Celery/Django views."""
    from django.conf import settings
    if not settings.TELEGRAM_BOT_ENABLED or not settings.TELEGRAM_BOT_TOKEN:
        return

    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
        async with Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as b:
            try:
                await b.send_message(chat_id=telegram_id, text=text, parse_mode=parse_mode)
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                logger.warning(f'Telegram notify failed for {telegram_id}: {e}')

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _executor.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
    except Exception as e:
        logger.error(f'Telegram notify error: {e}')


def notify_user(telegram_id: int, text: str) -> None:
    """Публичный интерфейс — использовать из Celery и views."""
    _send_sync(telegram_id, text)


def notify_user_if_linked(user) -> None:
    """Отправить уведомление если у пользователя привязан Telegram."""
    try:
        tg = user.telegram
        notify_user(tg.telegram_id, f"")
    except Exception:
        pass


def maybe_notify(user, text: str) -> None:
    """Отправить уведомление если привязан Telegram. Не падать при любой ошибке."""
    try:
        tg = getattr(user, 'telegram', None)
        if tg:
            notify_user(tg.telegram_id, text)
    except Exception as e:
        logger.warning(f'maybe_notify failed: {e}')


def maybe_notify_chat(telegram_chat_id: int, text: str) -> None:
    """Отправить текст в конкретный Telegram чат."""
    try:
        notify_user(telegram_chat_id, text)
    except Exception as e:
        logger.warning(f'maybe_notify_chat failed: {e}')


def send_media_to_telegram(telegram_chat_id: int, generated_image, network_name: str, cost_kopecks: int) -> None:
    """Отправить сгенерированное видео/изображение в Telegram чат."""
    from django.conf import settings
    from core.money import format_rub
    if not getattr(settings, 'TELEGRAM_BOT_ENABLED', False) or not getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
        return

    try:
        media_url = f"{settings.SITE_URL}{generated_image.image.url}"
    except Exception as e:
        logger.warning(f'send_media_to_telegram: cannot get URL: {e}')
        return

    is_video = getattr(generated_image, 'file_type', None) == 'video' or 'video' in (generated_image.image.name or '')
    caption = f'{network_name} · {format_rub(cost_kopecks)}'

    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from aiogram.types import URLInputFile
        from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
        async with Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as b:
            try:
                if is_video:
                    await b.send_video(
                        chat_id=telegram_chat_id,
                        video=URLInputFile(media_url, filename='video.mp4'),
                        caption=caption,
                    )
                else:
                    await b.send_photo(
                        chat_id=telegram_chat_id,
                        photo=URLInputFile(media_url),
                        caption=caption,
                    )
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                logger.warning(f'send_media_to_telegram failed for {telegram_chat_id}: {e}')

    try:
        _executor.submit(asyncio.run, _send())
    except Exception as e:
        logger.error(f'send_media_to_telegram error: {e}')
