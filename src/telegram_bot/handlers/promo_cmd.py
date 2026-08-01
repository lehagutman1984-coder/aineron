"""/promo <код> — погашение промокода на баланс прямо из Telegram.

До этого хендлера погашение было доступно только на вебе
(POST /api/v1/billing/promo/), из-за чего промокоды, розданные подписчикам
Telegram-каналов или проданные на Plati.market/Digiseller, нельзя было
активировать в самом боте. Общая логика — в users.promo.redeem_promo_code,
чтобы не расходиться с веб-эндпоинтом.
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

from telegram_bot.i18n import resolve_language

logger = logging.getLogger(__name__)
router = Router()


@sync_to_async
def _redeem(user, code, intl):
    from users.promo import redeem_promo_code
    return redeem_promo_code(user, code, intl=intl)


@router.message(Command('promo'))
async def cmd_promo(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    intl = lang != 'ru'

    code = message.text.removeprefix('/promo').strip()
    if not code:
        hint = (
            'Enter the code after the command, e.g.: /promo WELCOME50'
            if intl else
            'Введите код после команды, например: /promo WELCOME50'
        )
        await message.answer(hint)
        return

    result = await _redeem(tg_user.user, code, intl)
    if not result['ok']:
        await message.answer(result['message'])
        return

    from core.money import format_money
    balance_line = (
        f"New balance: {format_money(result['new_balance_kopecks'])}" if intl
        else f"Баланс: {format_money(result['new_balance_kopecks'])}"
    )
    await message.answer(f"{result['message']}\n{balance_line}")
