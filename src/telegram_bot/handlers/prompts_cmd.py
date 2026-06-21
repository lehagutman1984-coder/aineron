import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()

CATEGORY_LABELS = {
    'code': 'Код',
    'translate': 'Перевод',
    'analyze': 'Анализ',
    'email': 'Письма',
    'study': 'Учёба',
    'creative': 'Творчество',
    'other': 'Другое',
}


def _get_prompt_categories():
    from aitext.models import PromptTemplate
    cats = PromptTemplate.objects.filter(is_public=True).values_list('category', flat=True).distinct()
    return list(cats)


def _get_prompts_by_category(category):
    from aitext.models import PromptTemplate
    return list(PromptTemplate.objects.filter(category=category, is_public=True)[:10])


def _get_prompt_by_id(pid):
    from aitext.models import PromptTemplate
    try:
        return PromptTemplate.objects.get(id=pid)
    except PromptTemplate.DoesNotExist:
        return None


get_prompt_categories = sync_to_async(_get_prompt_categories, thread_sensitive=True)
get_prompts_by_category = sync_to_async(_get_prompts_by_category, thread_sensitive=True)
get_prompt_by_id = sync_to_async(_get_prompt_by_id, thread_sensitive=True)


@router.message(Command('prompts'))
async def cmd_prompts(message: Message, tg_user=None):
    if tg_user is None:
        return

    categories = await get_prompt_categories()
    if not categories:
        await message.answer(
            "Библиотека промтов пока пуста.\n"
            "Добавьте промты на aineron.ru/prompts/"
        )
        return

    buttons = []
    for cat in categories[:8]:
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        buttons.append([InlineKeyboardButton(text=label, callback_data=f'prompts_cat:{cat}')])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("<b>Библиотека промтов</b>\n\nВыберите категорию:", parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith('prompts_cat:'))
async def cb_prompts_category(query: CallbackQuery, tg_user=None):
    category = query.data.split(':', 1)[1]
    prompts = await get_prompts_by_category(category)

    if not prompts:
        await query.answer('Промты не найдены.')
        return

    buttons = []
    for p in prompts:
        title = (p.title or p.content[:40])[:50]
        buttons.append([InlineKeyboardButton(text=title, callback_data=f'use_prompt:{p.id}')])

    cat_label = CATEGORY_LABELS.get(category, category.capitalize())
    kb = InlineKeyboardMarkup(inline_keyboard=buttons + [
        [InlineKeyboardButton(text='Назад', callback_data='prompts_back')]
    ])
    await query.message.edit_text(
        f"<b>{cat_label}</b>\n\nВыберите промт:",
        parse_mode='HTML',
        reply_markup=kb,
    )
    await query.answer()


@router.callback_query(F.data.startswith('use_prompt:'))
async def cb_use_prompt(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    prompt_id = int(query.data.split(':', 1)[1])
    prompt = await get_prompt_by_id(prompt_id)

    if not prompt:
        await query.answer('Промт не найден.')
        return

    await query.answer('Отправляю промт...')
    await query.message.answer(
        f"<b>{prompt.title}</b>\n\n{prompt.content[:3000]}",
        parse_mode='HTML',
    )
    from telegram_bot.handlers.chat import process_text
    await process_text(query.message, tg_user, prompt.content)


@router.callback_query(F.data == 'prompts_back')
async def cb_prompts_back(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    await cmd_prompts(query.message, tg_user)
    await query.answer()
