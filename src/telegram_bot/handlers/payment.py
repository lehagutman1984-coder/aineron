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


# ─── S4: Stars-подписки (Bot API 8.0) ───
# Месячный период подписки в секундах — константа Telegram
STARS_SUBSCRIPTION_PERIOD = 2592000
# Наценка Stars-тарифа к рублёвой цене (комиссия Telegram, см. TARIFFS.md)
STARS_MARKUP = 1.18


def _tariff_xtr_price(tariff) -> int:
    """Цена тарифа в XTR: рубли → XTR по курсу TG_XTR_RATE_KOPECKS + наценка."""
    import math
    from django.conf import settings as dj
    rate = getattr(dj, 'TG_XTR_RATE_KOPECKS', 200)
    return max(1, math.ceil(float(tariff.price) * 100 / rate * STARS_MARKUP))


def _get_paid_tariffs():
    from users.models import Tariff
    return list(
        Tariff.objects.filter(is_active=True, is_free=False, is_trial=False)
        .order_by('price')
    )


def _activate_stars_subscription(tg_user, tariff_id: int, charge_id: str,
                                 xtr_amount: int, expires_at=None):
    """Активация/продление тарифа по Stars-подписке. Идемпотентно по charge_id."""
    from django.utils import timezone
    from datetime import datetime, timedelta, timezone as dt_tz
    from users.models import Tariff, PaymentHistory
    from telegram_bot.models import StarsSubscription

    # subscription_expiration_date может прийти unix-числом — нормализуем
    if isinstance(expires_at, (int, float)):
        try:
            expires_at = datetime.fromtimestamp(expires_at, tz=dt_tz.utc)
        except (ValueError, OverflowError, OSError):
            expires_at = None

    tariff = Tariff.objects.filter(pk=tariff_id, is_active=True).first()
    if tariff is None:
        return None

    # Идемпотентность повторного webhook: платёж с этим charge_id уже обработан
    if PaymentHistory.objects.filter(invoice_id=charge_id).exists():
        return tariff

    user = tg_user.user
    subscription = user.activate_paid_tariff(tariff, payment_data={'invoice_id': charge_id})

    # КРИТИЧНО: продление этой подписки делает Telegram (successful_payment
    # с is_recurring), а НЕ Robokassa. auto_renew=True отправил бы её в
    # process_pending_renewals → невалидный PreviousInvoiceID → исчерпание
    # попыток → return_to_free_tariff() с обнулением баланса пользователя.
    subscription.auto_renew = False
    subscription.robokassa_invoice_id = None
    subscription.save(update_fields=['auto_renew', 'robokassa_invoice_id'])

    sub, created = StarsSubscription.objects.update_or_create(
        tg_user=tg_user,
        defaults={
            'tariff': tariff,
            'xtr_amount': xtr_amount,
            'expires_at': expires_at or (timezone.now() + timedelta(days=30)),
            'is_active': True,
        },
    )
    # editUserStarSubscription требует charge_id ПЕРВОГО платежа подписки —
    # не перезаписываем его при recurring-продлениях
    if created or not sub.telegram_charge_id:
        sub.telegram_charge_id = charge_id
        sub.save(update_fields=['telegram_charge_id'])
    return tariff


activate_stars_subscription = sync_to_async(_activate_stars_subscription, thread_sensitive=True)
get_paid_tariffs = sync_to_async(_get_paid_tariffs, thread_sensitive=True)


@router.message(Command('subscribe'))
async def cmd_subscribe(message: Message, tg_user=None):
    """S4: тарифы как ежемесячные Stars-подписки — MRR прямо в Telegram."""
    from telegram_bot import capabilities
    from telegram_bot.utils import DIVIDER

    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    if not capabilities.is_enabled('stars_subscriptions'):
        await message.answer(
            'Подписки в Stars скоро появятся. Пока оформите тариф на сайте:\n'
            'https://aineron.ru/account/billing/',
        )
        return

    tariffs = await get_paid_tariffs()
    if not tariffs:
        await message.answer('Нет доступных тарифов. Загляните позже.')
        return

    rows = []
    lines = [f'<b>Aineron · Подписка в Telegram</b>', DIVIDER,
             'Ежемесячное продление в Stars, отмена в любой момент (/balance).', '']
    for t in tariffs:
        xtr = _tariff_xtr_price(t)
        lines.append(f'<b>{t.display_name}</b> — {int(t.price)} ₽ на баланс ежемесячно')
        rows.append([InlineKeyboardButton(
            text=f'{t.display_name} — {xtr} XTR/мес',
            callback_data=f'substars:{t.pk}',
        )])
    await message.answer(
        '\n'.join(lines), parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith('substars:'))
async def cb_substars(query: CallbackQuery, tg_user=None):
    from telegram_bot import capabilities

    if tg_user is None:
        await query.answer('Привяжите аккаунт через /start', show_alert=True)
        return
    if not capabilities.is_enabled('stars_subscriptions'):
        await query.answer('Функция временно недоступна', show_alert=True)
        return

    tariff_id = int(query.data.split(':')[1])
    tariffs = await get_paid_tariffs()
    tariff = next((t for t in tariffs if t.pk == tariff_id), None)
    if tariff is None:
        await query.answer('Тариф не найден')
        return

    xtr = _tariff_xtr_price(tariff)
    try:
        link = await query.bot.create_invoice_link(
            title=f'Подписка {tariff.display_name}',
            description=f'{int(tariff.price)} ₽ на баланс aineron.ru ежемесячно',
            payload=f'subtariff:{tariff.pk}:{xtr}',
            currency='XTR',
            prices=[LabeledPrice(label=f'{tariff.display_name} / месяц', amount=xtr)],
            subscription_period=STARS_SUBSCRIPTION_PERIOD,
        )
    except TypeError:
        # aiogram без subscription_period — деградация до разовой оплаты недопустима
        await query.answer('Подписки требуют обновления бота. Оформите на сайте.', show_alert=True)
        return
    except Exception as e:
        logger.error(f'create_invoice_link subscription failed: {e}')
        await query.answer('Не удалось создать подписку, попробуйте позже', show_alert=True)
        return

    await query.message.answer(
        f'<b>Подписка {tariff.display_name}</b>\n'
        f'{xtr} XTR в месяц · продление автоматическое, отмена в /balance',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f'Оформить за {xtr} XTR/мес', url=link),
        ]]),
    )
    await query.answer()


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, tg_user=None):
    from core.money import format_rub

    if tg_user is None:
        return
    payload = message.successful_payment.invoice_payload
    charge_id = message.successful_payment.telegram_payment_charge_id

    # S4: платёж по Stars-подписке (первый или recurring-продление)
    if payload.startswith('subtariff:'):
        try:
            _, tariff_id_s, xtr_s = payload.split(':')
            tariff_id, xtr = int(tariff_id_s), int(xtr_s)
        except ValueError:
            logger.warning(f'Malformed subscription payload: {payload}')
            return
        expires_at = getattr(message.successful_payment, 'subscription_expiration_date', None)
        tariff = await activate_stars_subscription(tg_user, tariff_id, charge_id, xtr, expires_at)
        if tariff is None:
            await message.answer('Тариф не найден — обратитесь в поддержку.')
            return
        is_recurring = bool(getattr(message.successful_payment, 'is_recurring', False))
        await async_log_event(tg_user, 'subscription',
                              cost_kopecks=int(tariff.price) * 100,
                              payload=payload, recurring=is_recurring)
        from telegram_bot.notify import EFFECT_CELEBRATION
        text = (
            f'<b>Подписка {tariff.display_name} '
            f'{"продлена" if is_recurring else "оформлена"}!</b>\n\n'
            f'Начислено: <b>{format_rub(int(tariff.price) * 100)}</b>\n'
            f'Продление автоматическое. Управление: /balance'
        )
        try:
            await message.answer(text, parse_mode='HTML', message_effect_id=EFFECT_CELEBRATION)
        except Exception:
            await message.answer(text, parse_mode='HTML')
        return

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
