import logging
import httpx
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import star_packs_kb
from telegram_bot.utils import stars_estimate

logger = logging.getLogger(__name__)
router = Router()

_RBK_PACKS = [
    ('stars_100',  '100 звёзд — 99 ₽'),
    ('stars_220',  '220 звёзд — 199 ₽ (+10%)'),
    ('stars_600',  '600 звёзд — 499 ₽ (+20%)'),
    ('stars_1500', '1500 звёзд — 999 ₽ (+25%)'),
]


@sync_to_async
def _get_week_spending(user):
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum
    from users.models import UserSpending
    week_ago = timezone.now() - timedelta(days=7)
    result = UserSpending.objects.filter(user=user, created_at__gte=week_ago).aggregate(total=Sum('amount'))
    return result['total'] or 0


async def send_balance(message: Message, tg_user):
    network = tg_user.default_network
    cost = network.cost_per_message if network else 0
    name = network.name if network else 'не выбрана'
    estimate = stars_estimate(tg_user.user.pages_count, cost) if cost else '—'
    week_total = await _get_week_spending(tg_user.user)

    text = (
        f"<b>Ваш баланс: {tg_user.user.pages_count} звёзд</b>\n\n"
        f"Текущая модель: {name}"
    )
    if cost:
        text += f" ({cost} зв./сообщение)\nХватит примерно на: {estimate} сообщений"
    if week_total:
        text += f"\n\n<i>За 7 дней потрачено: {week_total} зв.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Пополнить на сайте', url='https://aineron.ru/account/billing/')],
        [InlineKeyboardButton(text='Купить через Telegram Stars', callback_data='buy_stars')],
        [InlineKeyboardButton(text='Купить через Robokassa (карта/СБП)', callback_data='buy_robokassa')],
    ])
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


@router.message(or_f(Command('balance'), F.text == 'Баланс'))
async def cmd_balance(message: Message, tg_user=None):
    if tg_user is None:
        return
    await send_balance(message, tg_user)


@router.message(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Команды бота:</b>\n\n"
        "/models — список моделей и смена текущей\n"
        "/image &lt;промт&gt; — сгенерировать изображение\n"
        "/balance — баланс и пополнение\n"
        "/newchat — начать новый чат (сбросить контекст)\n"
        "/settings — настройки (голос, веб-поиск, промт)\n"
        "/prompts — библиотека готовых промтов\n"
        "/referral — реферальная программа\n"
        "/help — эта справка\n\n"
        "Просто напиши любой вопрос — я отвечу.",
        parse_mode='HTML',
    )


@router.callback_query(F.data == 'buy_stars')
async def cb_buy_stars(query: CallbackQuery, tg_user=None):
    await query.message.answer(
        "<b>Выберите пакет звёзд:</b>\n\n"
        "Оплата через Telegram Stars (XTR) — мгновенно, без карты.",
        parse_mode='HTML',
        reply_markup=star_packs_kb(),
    )
    await query.answer()


@router.callback_query(F.data == 'buy_robokassa')
async def cb_buy_robokassa(query: CallbackQuery, tg_user=None):
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f'rbk:{key}')]
        for key, label in _RBK_PACKS
    ]
    await query.message.answer(
        "<b>Выберите пакет звёзд (Robokassa):</b>\n\n"
        "Оплата картой российского банка, СБП, ЮMoney и другими способами.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await query.answer()


@router.callback_query(F.data.startswith('rbk:'))
async def cb_rbk_pack(query: CallbackQuery, tg_user=None):
    """Generate Robokassa payment URL and send as inline button."""
    if tg_user is None or not tg_user.user:
        await query.answer("Привяжите аккаунт через /start", show_alert=True)
        return

    pack_key = query.data.split(':', 1)[1]
    await query.answer("Формирую ссылку на оплату...")

    from django.conf import settings as dj_settings
    import hashlib, json, random, time, urllib.parse

    packs = {k: v for k, v in zip(
        [k for k, _ in _RBK_PACKS],
        [
            {'stars': 100,  'price': '99.00'},
            {'stars': 220,  'price': '199.00'},
            {'stars': 600,  'price': '499.00'},
            {'stars': 1500, 'price': '999.00'},
        ]
    )}
    pack = packs.get(pack_key)
    if not pack:
        await query.message.answer("Неверный пакет.")
        return

    ml = getattr(dj_settings, 'ROBOKASSA_LOGIN', '')
    pw1 = getattr(dj_settings, 'ROBOKASSA_PASS1', '')
    if not ml or not pw1:
        site_url = getattr(dj_settings, 'SITE_URL', 'https://aineron.ru')
        await query.message.answer(
            "Robokassa не настроена. Перейдите на сайт:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Пополнить на сайте', url=f"{site_url}/account/billing/")
            ]]),
        )
        return

    inv_id = int(time.time() * 1000) % 10_000_000 + random.randint(1, 999)
    out_sum = pack['price']
    stars = pack['stars']
    description = f"{stars} звёзд aineron.ru"

    receipt_data = {"items": [{"name": description[:128], "quantity": 1, "sum": float(out_sum), "tax": "none"}]}
    receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
    sig_str = f"{ml}:{out_sum}:{inv_id}:{receipt_json}:{pw1}"
    signature = hashlib.md5(sig_str.encode('cp1251')).hexdigest()

    site_url = getattr(dj_settings, 'SITE_URL', 'https://aineron.ru')
    params = {
        'MerchantLogin': ml,
        'OutSum': out_sum,
        'InvId': str(inv_id),
        'Description': description,
        'SignatureValue': signature,
        'IsTest': str(getattr(dj_settings, 'ROBOKASSA_TEST_MODE', 0)),
        'Culture': 'ru',
        'Encoding': 'utf-8',
        'SuccessURL': f"{site_url}/payment-success/",
        'FailURL': f"{site_url}/users/pages/payment-fail/",
        'Receipt': receipt_json,
    }
    pay_url = "https://auth.robokassa.ru/Merchant/Index.aspx?" + urllib.parse.urlencode(params)

    from users.models import PaymentHistory
    @sync_to_async
    def _create_payment():
        return PaymentHistory.objects.create(
            user=tg_user.user,
            payment_type='pages',
            invoice_id=str(inv_id),
            amount=float(out_sum),
            pages_count=stars,
            status='pending',
            description=description,
        )

    await _create_payment()

    await query.message.answer(
        f"<b>Оплата {stars} звёзд — {out_sum} ₽</b>\n\n"
        "Нажмите кнопку ниже для оплаты. После оплаты звёзды будут начислены автоматически.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f'Оплатить {out_sum} ₽', url=pay_url)
        ]]),
    )
