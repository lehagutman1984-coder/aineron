import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
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

    # Resolve stars count from known packs or stars_custom:N format
    pack = STAR_PACKS.get(payload)
    if pack:
        stars_count = pack['stars']
    elif payload.startswith('stars_custom:'):
        try:
            stars_count = int(payload.split(':', 1)[1])
        except (ValueError, IndexError):
            logger.warning(f'Malformed custom payment payload: {payload}')
            return
    else:
        logger.warning(f'Unknown payment payload: {payload}')
        return

    def _add_stars(user, count):
        user.add_pages(count)
        return user.pages_count

    add_stars = sync_to_async(_add_stars, thread_sensitive=True)
    new_balance = await add_stars(tg_user.user, stars_count)

    logger.info(f'Telegram Stars payment: user={tg_user.user.email} pack={payload} stars={stars_count}')

    await message.answer(
        f"<b>Оплата прошла успешно!</b>\n\n"
        f"Начислено: <b>{stars_count} звёзд</b>\n"
        f"Текущий баланс: <b>{new_balance} звёзд</b>\n\n"
        f"Задавай вопросы — я готов!",
        parse_mode='HTML',
    )


# ──── FSM-based /buy command ────
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class PurchaseFSM(StatesGroup):
    choosing_method = State()
    choosing_package = State()
    custom_amount = State()


_BUY_PACKAGES = [
    ('100 звёзд', 100, 50),
    ('300 звёзд', 300, 130),
    ('1000 звёзд', 1000, 400),
]


def _method_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Telegram Stars (XTR)', callback_data='buy_method:xtr')],
        [InlineKeyboardButton(text='Банковская карта (сайт)', callback_data='buy_method:card')],
        [InlineKeyboardButton(text='Отмена', callback_data='buy_cancel')],
    ])


def _packages_kb(method):
    buttons = []
    for name, stars, xtr in _BUY_PACKAGES:
        label = f'{name} — {xtr} XTR' if method == 'xtr' else name
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f'buy_pkg:{stars}:{method}',
        )])
    buttons.append([InlineKeyboardButton(text='Своя сумма', callback_data=f'buy_pkg:custom:{method}')])
    buttons.append([InlineKeyboardButton(text='Назад', callback_data='buy_back')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command('buy'))
async def cmd_buy(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжи аккаунт через /start')
        return
    balance = tg_user.user.pages_count
    await message.answer(
        f'<b>Пополнение баланса</b>\n'
        f'Текущий баланс: <b>{balance} зв.</b>\n\n'
        f'Выбери способ оплаты:',
        parse_mode='HTML',
        reply_markup=_method_kb(),
    )
    await state.set_state(PurchaseFSM.choosing_method)


@router.callback_query(F.data.startswith('buy_method:'))
async def cb_buy_method(query: CallbackQuery, state: FSMContext):
    method = query.data.split(':')[1]
    await state.update_data(method=method)
    await query.message.edit_text('Выбери пакет звёзд:', reply_markup=_packages_kb(method))
    await state.set_state(PurchaseFSM.choosing_package)
    await query.answer()


@router.callback_query(F.data == 'buy_back')
async def cb_buy_back(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text('Выбери способ оплаты:', reply_markup=_method_kb())
    await state.set_state(PurchaseFSM.choosing_method)
    await query.answer()


@router.callback_query(F.data == 'buy_cancel')
async def cb_buy_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text('Покупка отменена.')
    await query.answer()


@router.callback_query(F.data.startswith('buy_pkg:'))
async def cb_buy_pkg(query: CallbackQuery, state: FSMContext, tg_user=None):
    parts = query.data.split(':')
    stars_str = parts[1]
    method = parts[2] if len(parts) > 2 else 'xtr'

    if stars_str == 'custom':
        await query.message.edit_text('Введи количество звёзд (от 10 до 10000):')
        await state.set_state(PurchaseFSM.custom_amount)
        await query.answer()
        return

    stars = int(stars_str)
    await state.clear()
    if method == 'card':
        from django.conf import settings as djsettings
        url = f'{djsettings.SITE_URL}/account/billing/'
        await query.message.edit_text(
            f'Для покупки <b>{stars} зв.</b> перейди на сайт:',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Открыть биллинг', url=url),
            ]]),
        )
    else:
        xtr = next((x for n, s, x in _BUY_PACKAGES if s == stars), max(1, stars // 2))
        await query.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f'{stars} звёзд aineron.ru',
            description=f'Пополнение баланса на {stars} звёзд',
            payload=f'stars_custom:{stars}',
            currency='XTR',
            prices=[LabeledPrice(label=f'{stars} звёзд', amount=xtr)],
        )
    await query.answer()


@router.message(PurchaseFSM.custom_amount)
async def on_custom_amount(message: Message, state: FSMContext, tg_user=None):
    try:
        stars = int(message.text.strip())
        if not (10 <= stars <= 10000):
            raise ValueError
    except ValueError:
        await message.answer('Введи число от 10 до 10000:')
        return
    data = await state.get_data()
    method = data.get('method', 'xtr')
    await state.clear()
    if method == 'card':
        from django.conf import settings as djsettings
        url = f'{djsettings.SITE_URL}/account/billing/'
        await message.answer(f'Для покупки {stars} зв. перейди на сайт: {url}')
    else:
        xtr = max(1, stars // 2)
        await message.bot.send_invoice(
            chat_id=message.from_user.id,
            title=f'{stars} звёзд aineron.ru',
            description=f'Пополнение баланса на {stars} звёзд',
            payload=f'stars_custom:{stars}',
            currency='XTR',
            prices=[LabeledPrice(label=f'{stars} звёзд', amount=xtr)],
        )
