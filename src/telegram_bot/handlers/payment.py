import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()

# Telegram Stars (XTR) остаётся способом оплаты (требование Telegram для цифровых
# товаров), но начисляет РУБЛИ на единый баланс (1 звезда legacy = 1 ₽).
# Курс XTR не пересчитан относительно старых пакетов (см. BILLING_MIGRATION_PLAN.md,
# «Решение №3 — relabel») — суммы численно совпадают с прежними «100 звёзд» и т.д.,
# изменено только обозначение.
RUB_PACKS = {
    'stars_100': {'xtr': 50,  'rub': 100, 'label': '100 ₽ на баланс aineron'},
    'stars_220': {'xtr': 100, 'rub': 220, 'label': '220 ₽ на баланс aineron (+10% бонус)'},
    'stars_600': {'xtr': 250, 'rub': 600, 'label': '600 ₽ на баланс aineron (+20% бонус)'},
}


@router.callback_query(F.data.startswith('pack:'))
async def send_invoice(query: CallbackQuery):
    pack_key = query.data.split(':', 1)[1]
    pack = RUB_PACKS.get(pack_key)
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
    from core.money import format_rub

    if tg_user is None:
        return
    payload = message.successful_payment.invoice_payload
    charge_id = message.successful_payment.telegram_payment_charge_id

    # Resolve rubles amount from known packs or stars_custom:N format (N — рубли)
    pack = RUB_PACKS.get(payload)
    if pack:
        rub_amount = pack['rub']
    elif payload.startswith('stars_custom:'):
        try:
            rub_amount = int(payload.split(':', 1)[1])
        except (ValueError, IndexError):
            logger.warning(f'Malformed custom payment payload: {payload}')
            return
    else:
        logger.warning(f'Unknown payment payload: {payload}')
        return

    def _add_rub(user, rub, reference):
        user.add_kopecks(rub * 100, type='xtr', reference=reference)
        user.refresh_from_db(fields=['balance_kopecks'])
        return user.balance_kopecks

    add_rub = sync_to_async(_add_rub, thread_sensitive=True)
    new_balance_kopecks = await add_rub(tg_user.user, rub_amount, charge_id)

    logger.info(f'Telegram Stars payment: user={tg_user.user.email} pack={payload} rub={rub_amount} charge_id={charge_id}')
    await async_log_event(tg_user, 'payment', cost_kopecks=rub_amount * 100, payload=payload)

    # S1: message effect «праздник» при успешной оплате (fallback — без эффекта)
    from telegram_bot.notify import EFFECT_CELEBRATION
    success_text = (
        f"<b>Оплата прошла успешно!</b>\n\n"
        f"Начислено: <b>{format_rub(rub_amount * 100)}</b>\n"
        f"Текущий баланс: <b>{format_rub(new_balance_kopecks)}</b>\n\n"
        f"Задавай вопросы — я готов!"
    )
    try:
        await message.answer(success_text, parse_mode='HTML',
                             message_effect_id=EFFECT_CELEBRATION)
    except Exception:
        await message.answer(success_text, parse_mode='HTML')


# ──── FSM-based /buy command ────
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class PurchaseFSM(StatesGroup):
    choosing_method = State()
    choosing_package = State()
    custom_amount = State()


_BUY_PACKAGES = [
    ('100 ₽', 100, 50),
    ('300 ₽', 300, 130),
    ('1000 ₽', 1000, 400),
]


def _method_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Telegram Stars (XTR)', callback_data='buy_method:xtr')],
        [InlineKeyboardButton(text='Банковская карта (сайт)', callback_data='buy_method:card')],
        [InlineKeyboardButton(text='Отмена', callback_data='buy_cancel')],
    ])


def _packages_kb(method):
    buttons = []
    for name, rub, xtr in _BUY_PACKAGES:
        label = f'{name} — {xtr} XTR' if method == 'xtr' else name
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f'buy_pkg:{rub}:{method}',
        )])
    buttons.append([InlineKeyboardButton(text='Своя сумма', callback_data=f'buy_pkg:custom:{method}')])
    buttons.append([InlineKeyboardButton(text='Назад', callback_data='buy_back')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command('buy'))
async def cmd_buy(message: Message, state: FSMContext, tg_user=None):
    from core.money import format_rub

    if tg_user is None:
        await message.answer('Привяжи аккаунт через /start')
        return
    balance_kopecks = tg_user.user.balance_kopecks
    await message.answer(
        f'<b>Пополнение баланса</b>\n'
        f'Текущий баланс: <b>{format_rub(balance_kopecks)}</b>\n\n'
        f'Выбери способ оплаты:',
        parse_mode='HTML',
        reply_markup=_method_kb(),
    )
    await state.set_state(PurchaseFSM.choosing_method)


@router.callback_query(F.data.startswith('buy_method:'))
async def cb_buy_method(query: CallbackQuery, state: FSMContext):
    method = query.data.split(':')[1]
    await state.update_data(method=method)
    await query.message.edit_text('Выбери сумму пополнения:', reply_markup=_packages_kb(method))
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
    rub_str = parts[1]
    method = parts[2] if len(parts) > 2 else 'xtr'

    if rub_str == 'custom':
        await query.message.edit_text('Введи сумму пополнения в рублях (от 10 до 10000):')
        await state.set_state(PurchaseFSM.custom_amount)
        await query.answer()
        return

    rub = int(rub_str)
    await state.clear()
    if method == 'card':
        from django.conf import settings as djsettings
        url = f'{djsettings.SITE_URL}/account/billing/'
        await query.message.edit_text(
            f'Для пополнения на <b>{rub} ₽</b> перейди на сайт:',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Открыть биллинг', url=url),
            ]]),
        )
    else:
        xtr = next((x for n, r, x in _BUY_PACKAGES if r == rub), max(1, rub // 2))
        await query.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f'{rub} ₽ на баланс aineron.ru',
            description=f'Пополнение баланса на {rub} ₽',
            payload=f'stars_custom:{rub}',
            currency='XTR',
            prices=[LabeledPrice(label=f'{rub} ₽', amount=xtr)],
        )
    await query.answer()


@router.message(PurchaseFSM.custom_amount)
async def on_custom_amount(message: Message, state: FSMContext, tg_user=None):
    try:
        rub = int(message.text.strip())
        if not (10 <= rub <= 10000):
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
        await message.answer(f'Для пополнения на {rub} ₽ перейди на сайт: {url}')
    else:
        xtr = max(1, rub // 2)
        await message.bot.send_invoice(
            chat_id=message.from_user.id,
            title=f'{rub} ₽ на баланс aineron.ru',
            description=f'Пополнение баланса на {rub} ₽',
            payload=f'stars_custom:{rub}',
            currency='XTR',
            prices=[LabeledPrice(label=f'{rub} ₽', amount=xtr)],
        )
