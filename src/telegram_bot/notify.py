import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='tg_notify')

# Message effect для приватных чатов (Bot API 7.4): «праздник» при успешной
# оплате и завершении долгих генераций. Fallback — обычное сообщение.
EFFECT_CELEBRATION = '5046509860389126442'


async def send_rich_or_markdown(bot, chat_id: int, md_text: str,
                                reply_markup=None, **kwargs):
    """S0/S1: отправка markdown-ответа rich-сообщением (Bot API 10.1) с
    fallback на HTML (telegram_format + split_message).

    Возвращает последний отправленный Message.
    """
    from telegram_bot import capabilities
    from telegram_bot.utils import telegram_format, split_message

    if capabilities.available('rich_messages', bot):
        try:
            from telegram_bot.rich import md_to_rich_blocks, blocks_to_payload
            blocks = md_to_rich_blocks(md_text)
            if blocks:
                return await bot.send_rich_message(
                    chat_id=chat_id,
                    blocks=blocks_to_payload(blocks),
                    reply_markup=reply_markup,
                    **kwargs,
                )
        except Exception as e:
            logger.warning(f'send_rich_or_markdown: rich path failed, fallback to HTML: {e}')

    parts = split_message(telegram_format(md_text))
    last = None
    for i, part in enumerate(parts):
        last = await bot.send_message(
            chat_id=chat_id, text=part, parse_mode='HTML',
            reply_markup=reply_markup if i == len(parts) - 1 else None,
            **kwargs,
        )
    return last


class DraftStreamer:
    """S0/S1: стриминг частичного ответа LLM.

    Нативный путь — sendMessageDraft (Bot API 9.5): токены появляются «как
    печатаются», без лимитов edit-троттлинга. Резервный путь — старый механизм
    edit_text с троттлингом (мин. интервал между правками). Любая ошибка
    нативного пути мгновенно и навсегда (в рамках объекта) переключает на fallback.
    """

    def __init__(self, tg_message, min_edit_interval: float = 3.5):
        from telegram_bot import capabilities
        self.tg_message = tg_message
        self.bot = tg_message.bot
        self.chat_id = tg_message.chat.id
        self.min_edit_interval = min_edit_interval
        self._use_draft = capabilities.available('native_streaming', self.bot)
        self.sent = None          # placeholder-сообщение (fallback-режим)
        self._last_edit = 0.0
        self._last_text = ''

    async def start(self, placeholder: str):
        """Показать начальный статус («Генерирую...» или пустой черновик)."""
        if self._use_draft:
            try:
                await self.bot.send_message_draft(chat_id=self.chat_id, text=placeholder)
                return
            except Exception as e:
                logger.warning(f'DraftStreamer: sendMessageDraft failed, fallback: {e}')
                self._use_draft = False
        self.sent = await self.tg_message.answer(placeholder)

    async def update(self, partial_text: str):
        """Обновить превью частичным текстом ответа."""
        if not partial_text or partial_text == self._last_text:
            return
        if self._use_draft:
            try:
                await self.bot.send_message_draft(
                    chat_id=self.chat_id, text=partial_text[:4000],
                )
                self._last_text = partial_text
                return
            except Exception as e:
                logger.warning(f'DraftStreamer: draft update failed, fallback: {e}')
                self._use_draft = False
                if self.sent is None:
                    try:
                        self.sent = await self.tg_message.answer('Генерирую ответ...')
                    except Exception:
                        return
        now = time.monotonic()
        if (self.sent is not None and len(partial_text) > 20
                and now - self._last_edit >= self.min_edit_interval):
            from telegram_bot.utils import telegram_format
            self._last_text = partial_text
            self._last_edit = now
            try:
                preview = telegram_format(partial_text[:3000]) + ' ...'
                await self.sent.edit_text(preview, parse_mode='HTML')
            except Exception:
                pass

    async def finish(self, html_parts: list, reply_markup=None, effect: bool = False):
        """Заменить превью финальным ответом (список HTML-частей ≤4096)."""
        effect_kwargs = {}
        if effect:
            effect_kwargs = {'message_effect_id': EFFECT_CELEBRATION}
        for i, part in enumerate(html_parts):
            markup = reply_markup if i == len(html_parts) - 1 else None
            if i == 0 and self.sent is not None:
                try:
                    await self.sent.edit_text(part, parse_mode='HTML', reply_markup=markup)
                    continue
                except Exception:
                    pass
            try:
                await self.tg_message.answer(part, parse_mode='HTML',
                                             reply_markup=markup, **effect_kwargs)
            except Exception:
                await self.tg_message.answer(part, parse_mode='HTML', reply_markup=markup)
            effect_kwargs = {}

    async def fail(self, text: str):
        """Показать ошибку вместо превью."""
        if self.sent is not None:
            try:
                await self.sent.edit_text(text)
                return
            except Exception:
                pass
        await self.tg_message.answer(text)


def stream_draft_or_edit(tg_message, min_edit_interval: float = 3.5) -> DraftStreamer:
    """Фабрика стримера: нативный sendMessageDraft или edit_text-fallback."""
    return DraftStreamer(tg_message, min_edit_interval=min_edit_interval)


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


def notify_user_rich(telegram_id: int, md_text: str, reply_markup=None) -> None:
    """Синхронная доставка markdown-текста rich-сообщением с HTML-fallback.

    Для Celery-задач (AI-задачи, research, сводки). Не падает при любой ошибке.
    """
    from django.conf import settings
    if not settings.TELEGRAM_BOT_ENABLED or not settings.TELEGRAM_BOT_TOKEN:
        return

    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        async with Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as b:
            try:
                await send_rich_or_markdown(b, telegram_id, md_text, reply_markup=reply_markup)
            except Exception as e:
                logger.warning(f'notify_user_rich failed for {telegram_id}: {e}')

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _executor.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
    except Exception as e:
        logger.error(f'notify_user_rich error: {e}')


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
