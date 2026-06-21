import logging
from asgiref.sync import sync_to_async
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
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


def _store_referral_code(telegram_id, referral_code):
    """Сохраняем реферальный код для нового пользователя когда он привяжет аккаунт."""
    from django.core.cache import cache
    cache.set(f'tg_ref:{telegram_id}', referral_code, 60 * 60 * 24 * 7)  # 7 дней


def _apply_referral(user, referral_code):
    """Применяем реферальный код если аккаунт ещё без реферера."""
    try:
        from users.models import CustomUser
        if user.referrer:
            return
        referrer = CustomUser.objects.filter(referral_code=referral_code).first()
        if referrer and referrer != user:
            user.referrer = referrer
            user.save(update_fields=['referrer'])
    except Exception:
        pass


get_link_token = sync_to_async(_get_link_token, thread_sensitive=True)
create_tg_user = sync_to_async(_create_tg_user, thread_sensitive=True)
mark_token_used = sync_to_async(_mark_token_used, thread_sensitive=True)
store_referral_code = sync_to_async(_store_referral_code, thread_sensitive=True)
apply_referral = sync_to_async(_apply_referral, thread_sensitive=True)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = ''
    if message.text and ' ' in message.text:
        args = message.text.split(maxsplit=1)[1].strip()

    if args and args.startswith('model_'):
        slug = args[6:]
        await message.answer(
            f'Открываю модель: https://aineron.ru/chat/{slug}/',
            parse_mode='HTML',
        )
        return

    if args and args.startswith('prompt_'):
        await message.answer(
            'Промт загружается, пиши свой запрос!',
            parse_mode='HTML',
        )
        return

    if args and args.startswith('ref_'):
        referral_code = args[4:]  # strip 'ref_'
        await store_referral_code(message.from_user.id, referral_code)
        # Показываем обычное приветствие с подсказкой
        await message.answer(
            "<b>Привет! Я AI-ассистент aineron.ru</b>\n\n"
            "Реферальный код применён автоматически при регистрации.\n\n"
            "Чтобы начать работу, привяжи аккаунт:\n\n"
            "1. Зайди на <b>aineron.ru</b>\n"
            "2. Кабинет → Telegram\n"
            "3. Нажми <b>«Подключить Telegram»</b> и перейди по ссылке\n\n"
            "После привязки тебе будут доступны все AI-модели и баланс звёзд."
        )
        return

    if args and not args.startswith('ref_'):
        link_token = await get_link_token(args)
        if link_token and link_token.is_valid:
            tg_user = await create_tg_user(link_token.user, message.from_user)
            await mark_token_used(link_token)
            # Применяем сохранённый реферальный код если есть
            get_cached_ref = sync_to_async(
                lambda: __import__('django.core.cache', fromlist=['cache']).cache.get(f'tg_ref:{message.from_user.id}'),
                thread_sensitive=True,
            )
            ref_code = await get_cached_ref()
            if ref_code:
                await apply_referral(link_token.user, ref_code)

            get_balance = sync_to_async(lambda: link_token.user.pages_count, thread_sensitive=True)
            balance = await get_balance()

            from telegram_bot.keyboards import main_reply_kb
            from telegram_bot.handlers.onboarding import start_onboarding
            await message.answer(
                f"<b>Аккаунт привязан!</b>\n\n"
                f"Привет, {message.from_user.first_name}!\n"
                f"Баланс: <b>{balance} звёзд</b>",
                parse_mode='HTML',
                reply_markup=main_reply_kb(),
            )
            await start_onboarding(message, state, tg_user)
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
