import logging
from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async
from telegram_bot.keyboards import star_packs_kb
from telegram_bot.utils import stars_estimate

logger = logging.getLogger(__name__)
router = Router()


async def send_balance(message: Message, tg_user):
    network = tg_user.default_network
    cost = network.cost_per_message if network else 0
    name = network.name if network else 'не выбрана'
    estimate = stars_estimate(tg_user.user.pages_count, cost) if cost else '—'

    text = (
        f"<b>Ваш баланс: {tg_user.user.pages_count} звёзд</b>\n\n"
        f"Текущая модель: {name}"
    )
    if cost:
        text += f" ({cost} зв./сообщение)\nХватит примерно на: {estimate} сообщений"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Пополнить на сайте', url='https://aineron.ru/account/billing/')],
        [InlineKeyboardButton(text='Купить через Telegram Stars', callback_data='buy_stars')],
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
