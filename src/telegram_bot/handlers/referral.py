import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)
router = Router()


def _get_referral_stats(user):
    from django.db.models import Sum
    from users.models import CustomUser
    referred_count = CustomUser.objects.filter(referrer=user).count()
    paid_count = (
        CustomUser.objects
        .filter(referrer=user, paymenthistory__status='success')
        .distinct()
        .count()
    )
    stars_earned = 0
    try:
        from users.models import ReferralEarning
        result = ReferralEarning.objects.filter(referrer=user).aggregate(total=Sum('stars_amount'))
        stars_earned = result['total'] or 0
    except Exception:
        pass
    return referred_count, paid_count, stars_earned


get_referral_stats = sync_to_async(_get_referral_stats, thread_sensitive=True)


@router.message(Command('referral'))
async def cmd_referral(message: Message, tg_user=None):
    if tg_user is None:
        return

    user = tg_user.user
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'aineron_bot')
    referral_link_bot = f'https://t.me/{bot_username}?start=ref_{user.referral_code}'
    referral_link_web = f'https://aineron.ru/?ref={user.referral_code}'

    referred_count, paid_count, stars_earned = await get_referral_stats(user)

    text = (
        f"<b>Реферальная программа</b>\n\n"
        f"Ваша ссылка:\n"
        f"<code>{referral_link_bot}</code>\n\n"
        f"Также работает:\n"
        f"<code>{referral_link_web}</code>\n\n"
        f"<b>Статистика:</b>\n"
        f"Приглашено: {referred_count}\n"
        f"Из них оплатили: {paid_count}\n"
        f"Заработано: {stars_earned} звёзд\n\n"
        f"За каждого оплатившего реферала вы получаете бонус звёзд!"
    )

    share_text = "Попробуй%20AI%20на%20aineron.ru!"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text='Поделиться ссылкой',
            url=f'https://t.me/share/url?url={referral_link_bot}&text={share_text}',
        )],
        [InlineKeyboardButton(text='Подробнее о программе', url='https://aineron.ru/account/referral/')],
    ])

    await message.answer(text, parse_mode='HTML', reply_markup=kb)
