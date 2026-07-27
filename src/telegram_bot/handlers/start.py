import logging
from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from django.utils import timezone

from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()

NEW_USER_CB = 'start_new'
HAS_ACCOUNT_CB = 'start_has_account'


def _choice_kb(lang, referral_code=''):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t('start.newUserButton', lang),
            callback_data=f'{NEW_USER_CB}:{referral_code}',
        )],
        [InlineKeyboardButton(text=t('start.hasAccountButton', lang), callback_data=HAS_ACCOUNT_CB)],
    ])


def _get_link_token(token_str):
    from telegram_bot.models import TelegramLinkToken
    try:
        return TelegramLinkToken.objects.select_related('user').get(token=token_str)
    except TelegramLinkToken.DoesNotExist:
        return None


def _create_tg_user(user, from_user, lang=''):
    from telegram_bot.models import TelegramUser
    tg_user, _ = TelegramUser.objects.get_or_create(
        telegram_id=from_user.id,
        defaults={
            'user': user,
            'telegram_username': from_user.username or '',
            'telegram_first_name': from_user.first_name or '',
            'language': lang,
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
    from django.core.cache import cache
    cache.set(f'tg_ref:{telegram_id}', referral_code, 60 * 60 * 24 * 7)


def _apply_referral(user, referral_code):
    try:
        from users.models import CustomUser
        if user.referrer:
            return
        referrer = CustomUser.objects.filter(referral_code__iexact=referral_code).first()
        if referrer and referrer != user:
            user.referrer = referrer
            user.save(update_fields=['referrer'])
    except Exception:
        pass


def _create_standalone_account(from_user, lang='', referral_code=None):
    """
    BUG-I: self-serve регистрация прямо в боте, без предварительного
    аккаунта на сайте. Email и username — детерминированные placeholder'ы
    на базе telegram_id (глобально уникален, де-дуп не нужен). Пароль не
    задаётся (create_user(password=None) -> set_unusable_password()) —
    вход по email/паролю на сайте для такого аккаунта недоступен, пока
    пользователь не привяжет реальный email.
    """
    import secrets
    import string
    from django.db import IntegrityError, transaction
    from django.db.models import F
    from users.models import CustomUser
    from telegram_bot.models import TelegramUser

    email = f'tg{from_user.id}@telegram.local'
    username = f'tg{from_user.id}'
    user = CustomUser.objects.filter(email=email).first()
    created = False
    if user is None:
        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(username=username, email=email, password=None)
            created = True
        except IntegrityError:
            # Гонка: параллельный /start (повтор вебхука) уже создал аккаунт.
            user = CustomUser.objects.filter(email=email).first()

    referral_applied = False
    if created:
        alphabet = string.ascii_uppercase + string.digits
        user.referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))
        if lang:
            user.language = lang
        if referral_code:
            referrer = CustomUser.objects.filter(
                referral_code__iexact=referral_code
            ).exclude(pk=user.pk).first()
            if referrer:
                user.referrer = referrer
                CustomUser.objects.filter(pk=referrer.pk).update(
                    referral_clicks=F('referral_clicks') + 1
                )
                referral_applied = True
        user.save(update_fields=['referral_code', 'referrer', 'language'])

    tg_user, _ = TelegramUser.objects.get_or_create(
        telegram_id=from_user.id,
        defaults={
            'user': user,
            'telegram_username': from_user.username or '',
            'telegram_first_name': from_user.first_name or '',
            'language': lang,
        },
    )
    return tg_user, created, referral_applied


get_link_token = sync_to_async(_get_link_token, thread_sensitive=True)
create_tg_user = sync_to_async(_create_tg_user, thread_sensitive=True)
mark_token_used = sync_to_async(_mark_token_used, thread_sensitive=True)
store_referral_code = sync_to_async(_store_referral_code, thread_sensitive=True)
apply_referral = sync_to_async(_apply_referral, thread_sensitive=True)
create_standalone_account = sync_to_async(_create_standalone_account, thread_sensitive=True)


async def _announce_new_account(message: Message, state: FSMContext, tg_user, from_user, lang, referral_applied=False):
    """message — куда отвечать (может быть чужое сообщение с кнопками при
    вызове из callback); from_user — реальный кликнувший/написавший пользователь."""
    from telegram_bot.keyboards import main_reply_kb
    from telegram_bot.handlers.onboarding import start_onboarding
    from core.money import format_money

    if lang == 'ru':
        get_balance = sync_to_async(lambda: tg_user.user.pages_count, thread_sensitive=True)
        balance = await get_balance()
    else:
        get_kopecks = sync_to_async(lambda: tg_user.user.balance_kopecks, thread_sensitive=True)
        balance = format_money(await get_kopecks())

    body = f"{t('start.dashboardWelcome', lang, name=from_user.first_name or '')}\n\n"
    if referral_applied:
        body += f"{t('start.refApplied', lang)}\n\n"
    body += t('start.balanceLine', lang, balance=balance)

    await message.answer(
        f"<b>{t('start.createdTitle', lang)}</b>\n{DIVIDER}\n{body}",
        parse_mode='HTML',
        reply_markup=main_reply_kb(lang),
    )
    await start_onboarding(message, state, tg_user, lang=lang)
    logger.info(f'Telegram standalone account created: user={tg_user.user.email} tg_id={from_user.id}')


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    args = ''
    if message.text and ' ' in message.text:
        args = message.text.split(maxsplit=1)[1].strip()

    # Already linked and no special args — show dashboard
    if tg_user and not args:
        from telegram_bot.keyboards import main_reply_kb
        from core.money import format_money
        if lang == 'ru':
            get_balance = sync_to_async(lambda: tg_user.user.pages_count, thread_sensitive=True)
            balance = await get_balance()
        else:
            get_kopecks = sync_to_async(lambda: tg_user.user.balance_kopecks, thread_sensitive=True)
            balance = format_money(await get_kopecks())
        await message.answer(
            f"<b>{t('start.dashboardTitle', lang)}</b>\n{DIVIDER}\n"
            f"{t('start.dashboardWelcome', lang, name=message.from_user.first_name)}\n\n"
            f"{t('start.balanceLine', lang, balance=balance)}\n\n"
            f"{t('start.dashboardHint', lang)}",
            parse_mode='HTML',
            reply_markup=main_reply_kb(lang),
        )
        return

    if args and args.startswith('model_'):
        slug = args[6:]
        from django.conf import settings as dj_settings
        site_url = getattr(dj_settings, 'SITE_URL', 'https://aineron.ru')
        await message.answer(
            t('start.openingModel', lang, url=f'{site_url}/chat/{slug}/'),
            parse_mode='HTML',
        )
        return

    if args and args.startswith('prompt_'):
        await message.answer(
            t('start.promptLoading', lang),
            parse_mode='HTML',
        )
        return

    if args and args.startswith('ref_'):
        referral_code = args[4:]
        await store_referral_code(message.from_user.id, referral_code)
        if tg_user:
            await message.answer(
                f"<b>{t('start.dashboardTitle', lang)}</b>\n{DIVIDER}\n{t('start.refApplied', lang)}",
                parse_mode='HTML',
            )
            return
        # Ещё не привязан — либо новый пользователь (создаём аккаунт сразу
        # с этим реферальным кодом), либо уже есть аккаунт на сайте (тогда
        # код применится через кэш при линковке, см. ветку link_token ниже).
        await message.answer(
            f"<b>{t('start.dashboardTitle', lang)}</b>\n{DIVIDER}\n{t('start.introBody', lang)}",
            parse_mode='HTML',
            reply_markup=_choice_kb(lang, referral_code),
        )
        return

    if args and not args.startswith('ref_'):
        link_token = await get_link_token(args)
        if link_token and link_token.is_valid:
            tg_user = await create_tg_user(link_token.user, message.from_user, lang)
            await mark_token_used(link_token)
            get_cached_ref = sync_to_async(
                lambda: __import__('django.core.cache', fromlist=['cache']).cache.get(f'tg_ref:{message.from_user.id}'),
                thread_sensitive=True,
            )
            ref_code = await get_cached_ref()
            if ref_code:
                await apply_referral(link_token.user, ref_code)

            from core.money import format_money
            if lang == 'ru':
                get_balance = sync_to_async(lambda: link_token.user.pages_count, thread_sensitive=True)
                balance = await get_balance()
            else:
                get_kopecks = sync_to_async(lambda: link_token.user.balance_kopecks, thread_sensitive=True)
                balance = format_money(await get_kopecks())

            from telegram_bot.keyboards import main_reply_kb
            from telegram_bot.handlers.onboarding import start_onboarding
            await message.answer(
                f"<b>{t('start.linkedTitle', lang)}</b>\n{DIVIDER}\n"
                f"{t('start.dashboardWelcome', lang, name=message.from_user.first_name)}\n\n"
                f"{t('start.balanceLine', lang, balance=balance)}",
                parse_mode='HTML',
                reply_markup=main_reply_kb(lang),
            )
            await start_onboarding(message, state, tg_user, lang=lang)
            logger.info(f'Telegram linked: user={link_token.user.email} tg_id={message.from_user.id}')
            return

        await message.answer(
            f"<b>{t('start.linkInvalidTitle', lang)}</b>\n{DIVIDER}\n{t('start.linkInvalidBody', lang)}",
            parse_mode='HTML',
        )
        return

    await message.answer(
        f"<b>{t('start.dashboardTitle', lang)}</b>\n{DIVIDER}\n{t('start.introBody', lang)}",
        parse_mode='HTML',
        reply_markup=_choice_kb(lang),
    )


@router.callback_query(F.data.startswith(f'{NEW_USER_CB}:'))
async def cb_new_account(callback: CallbackQuery, state: FSMContext, tg_user=None):
    lang = resolve_language(tg_user, callback.from_user)
    if tg_user:
        # Уже привязан — кнопка нажата на устаревшей клавиатуре, ничего не делаем.
        await callback.answer()
        return
    referral_code = callback.data.split(':', 1)[1] or None
    new_tg_user, created, referral_applied = await create_standalone_account(
        callback.from_user, lang, referral_code=referral_code,
    )
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _announce_new_account(
        callback.message, state, new_tg_user, callback.from_user, lang,
        referral_applied=referral_applied,
    )


@router.callback_query(F.data == HAS_ACCOUNT_CB)
async def cb_has_account(callback: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, callback.from_user)
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"<b>{t('start.dashboardTitle', lang)}</b>\n{DIVIDER}\n{t('auth.notLinked', lang)}",
        parse_mode='HTML',
    )
