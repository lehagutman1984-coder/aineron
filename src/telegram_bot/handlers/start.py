import logging
from asgiref.sync import sync_to_async
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from django.utils import timezone

logger = logging.getLogger(__name__)
router = Router()


def _get_link_token(token_str):
    from telegram_bot.models import TelegramLinkToken
    try:
        return TelegramLinkToken.objects.select_related('user').get(token=token_str)
    except TelegramLinkToken.DoesNotExist:
        return None


def _create_tg_user(user, from_user):
    from telegram_bot.models import TelegramUser
    tg_user, _ = TelegramUser.objects.get_or_create(
        telegram_id=from_user.id,
        defaults={
            'user': user,
            'telegram_username': from_user.username or '',
            'telegram_first_name': from_user.first_name or '',
        },
    )
    if not tg_user.user_id or tg_user.user_id != user.id:
        tg_user.user = user
        tg_user.telegram_username = from_user.username or ''
        tg_user.telegram_first_name = from_user.first_name or ''
        tg_user.save(update_fields=['user', 'telegram_username', 'telegram_first_name'])
    return tg_user


def _mark_token_used(link_token):
    link_token.used = True
    link_token.save(update_fields=['used'])


get_link_token = sync_to_async(_get_link_token, thread_sensitive=True)
create_tg_user = sync_to_async(_create_tg_user, thread_sensitive=True)
mark_token_used = sync_to_async(_mark_token_used, thread_sensitive=True)


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = ''
    if message.text and ' ' in message.text:
        args = message.text.split(maxsplit=1)[1].strip()

    if args and not args.startswith('ref_'):
        link_token = await get_link_token(args)
        if link_token and link_token.is_valid:
            tg_user = await create_tg_user(link_token.user, message.from_user)
            await mark_token_used(link_token)

            get_balance = sync_to_async(lambda: link_token.user.pages_count, thread_sensitive=True)
            balance = await get_balance()

            await message.answer(
                f"<b>Аккаунт привязан!</b>\n\n"
                f"Привет, {message.from_user.first_name}!\n"
                f"Баланс: <b>{balance} звёзд</b>\n\n"
                f"Просто напиши мне любой вопрос — отвечу мгновенно.\n\n"
                f"<b>Команды:</b>\n"
                f"/models — выбрать модель\n"
                f"/balance — баланс и пополнение\n"
                f"/image &lt;промт&gt; — сгенерировать изображение\n"
                f"/newchat — начать новый чат\n"
                f"/settings — настройки\n"
                f"/help — справка"
            )
            logger.info(f'Telegram linked: user={link_token.user.email} tg_id={message.from_user.id}')
            return

        await message.answer(
            "Ссылка недействительна или устарела.\n\n"
            "Зайди на <b>aineron.ru</b> → Кабинет → Telegram и получи новую ссылку."
        )
        return

    await message.answer(
        "<b>Привет! Я AI-ассистент aineron.ru</b>\n\n"
        "Чтобы начать работу, привяжи аккаунт:\n\n"
        "1. Зайди на <b>aineron.ru</b>\n"
        "2. Кабинет → Telegram\n"
        "3. Нажми <b>«Подключить Telegram»</b> и перейди по ссылке\n\n"
        "После привязки тебе будут доступны все AI-модели, история чатов и баланс звёзд."
    )
