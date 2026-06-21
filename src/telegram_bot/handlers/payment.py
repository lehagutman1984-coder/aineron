import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message,
    LabeledPrice, PreCheckoutQuery,
)
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()

STAR_PACKS = {
    'stars_100': {'xtr': 50,  'stars': 100, 'label': '100 звёзд aineron'},
    'stars_220': {'xtr': 100, 'stars': 220, 'label': '220 звёзд aineron (+10% бонус)'},
    'stars_600': {'xtr': 250, 'stars': 600, 'label': '600 звёзд aineron (+20% бонус)'},
}


@router.callback_query(F.data.startswith('pack:'))
async def send_invoice(query: CallbackQuery):
    pack_key = query.data.split(':', 1)[1]
    pack = STAR_PACKS.get(pack_key)
    if not pack:
        await query.answer('Неверный пакет.')
        return

    await query.message.answer_invoice(
        title=pack['label'],
        description='Для использования AI-нейросетей на aineron.ru',
        payload=pack_key,
        currency='XTR',
        prices=[LabeledPrice(label=pack['label'], amount=pack['xtr'])],
    )
    await query.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, tg_user=None):
    if tg_user is None:
        return
    payload = message.successful_payment.invoice_payload
    pack = STAR_PACKS.get(payload)
    if not pack:
        logger.warning(f'Unknown payment payload: {payload}')
        return

    def _add_stars(user, count):
        user.add_pages(count)
        return user.pages_count

    add_stars = sync_to_async(_add_stars, thread_sensitive=True)
    new_balance = await add_stars(tg_user.user, pack['stars'])

    logger.info(f'Telegram Stars payment: user={tg_user.user.email} pack={payload} stars={pack["stars"]}')

    await message.answer(
        f"<b>Оплата прошла успешно!</b>\n\n"
        f"Начислено: <b>{pack['stars']} звёзд</b>\n"
        f"Текущий баланс: <b>{new_balance} звёзд</b>\n\n"
        f"Задавай вопросы — я готов!",
        parse_mode='HTML',
    )
