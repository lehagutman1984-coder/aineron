import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


def _get_referral_stats(user):
    from django.db.models import Sum
    from users.models import CustomUser, ReferralEarning
    referred_count = CustomUser.objects.filter(referrer=user).count()
    paid_count = (
        CustomUser.objects
        .filter(referrer=user, payments__status='success')
        .distinct()
        .count()
    )
    result = ReferralEarning.objects.filter(user=user).aggregate(total=Sum('amount_rub'))
    earned_rub = result['total'] or 0
    return referred_count, paid_count, earned_rub


get_referral_stats = sync_to_async(_get_referral_stats, thread_sensitive=True)


@router.message(Command('referral'))
async def cmd_referral(message: Message, tg_user=None):
    if tg_user is None:
        return

    user = tg_user.user
    lang = resolve_language(tg_user, message.from_user)
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'aineron_bot')
    site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
    referral_link_bot = f'https://t.me/{bot_username}?start=ref_{user.referral_code}'
    referral_link_web = f'{site_url}/?ref={user.referral_code}'

    referred_count, paid_count, earned_rub = await get_referral_stats(user)
    from core.money import format_money
    earned_label = format_money(int(earned_rub * 100))

    if lang == 'ru':
        text = (
            f"<b>Реферальная программа</b>\n\n"
            f"Ваша ссылка:\n"
            f"<code>{referral_link_bot}</code>\n\n"
            f"Также работает:\n"
            f"<code>{referral_link_web}</code>\n\n"
            f"<b>Статистика:</b>\n"
            f"Приглашено: {referred_count}\n"
            f"Из них оплатили: {paid_count}\n"
            f"Заработано: {earned_label}\n\n"
            f"За каждого оплатившего реферала вы получаете бонус на баланс!"
        )
    else:
        text = (
            f"<b>{t('referral.title', lang)}</b>\n\n"
            f"{t('referral.yourLink', lang)}\n"
            f"<code>{referral_link_bot}</code>\n\n"
            f"{t('referral.alsoWorks', lang)}\n"
            f"<code>{referral_link_web}</code>\n\n"
            f"<b>{t('referral.statsTitle', lang)}</b>\n"
            f"{t('referral.invited', lang)}: {referred_count}\n"
            f"{t('referral.paid', lang)}: {paid_count}\n"
            f"{t('referral.earned', lang)}: {earned_label}\n\n"
            f"{t('referral.footer', lang)}"
        )

    # S4: партнёрская программа Telegram — блок «Для каналов» (за флагом)
    from telegram_bot import capabilities
    if capabilities.is_enabled('affiliate'):
        if lang == 'ru':
            text += (
                "\n\n<b>Для каналов и блогеров</b>\n"
                "Бот участвует в партнёрской программе Telegram: подключите его "
                "в разделе «Заработок» вашего канала и получайте комиссию со "
                "всех Stars-платежей приведённых пользователей. Выплаты "
                "производит сам Telegram."
            )
        else:
            text += f"\n\n<b>{t('referral.affiliateTitle', lang)}</b>\n{t('referral.affiliateBody', lang)}"

    if lang == 'ru':
        share_text = "Попробуй%20AI%20на%20aineron.ru!"
        more_label = 'Подробнее о программе'
        share_label = 'Поделиться ссылкой'
    else:
        from urllib.parse import quote
        share_text = quote(t('referral.shareText', lang))
        more_label = t('referral.moreButton', lang)
        share_label = t('referral.shareButton', lang)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=share_label,
            url=f'https://t.me/share/url?url={referral_link_bot}&text={share_text}',
        )],
        [InlineKeyboardButton(text=more_label, url=f'{site_url}/account/referral/')],
    ])

    await message.answer(text, parse_mode='HTML', reply_markup=kb)
