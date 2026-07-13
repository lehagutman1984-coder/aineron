import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from telegram_bot.i18n import t, resolve_language

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


def _category_label(category: str, lang: str) -> str:
    if lang == 'ru':
        return CATEGORY_LABELS.get(category, category.capitalize())
    if category in CATEGORY_LABELS:
        return t(f'prompts.category{category.capitalize()}', lang)
    return category.capitalize()


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


async def send_prompts_menu(message: Message, tg_user, lang: str = 'ru'):
    categories = await get_prompt_categories()
    if not categories:
        if lang == 'ru':
            await message.answer(
                "Библиотека промтов пока пуста.\n"
                "Добавьте промты на aineron.ru/prompts/"
            )
        else:
            from django.conf import settings
            site_url = getattr(settings, 'SITE_URL', 'https://aineron.net')
            await message.answer(t('prompts.emptyLibrary', lang, url=f'{site_url}/prompts/'))
        return

    buttons = []
    for cat in categories[:8]:
        label = _category_label(cat, lang)
        buttons.append([InlineKeyboardButton(text=label, callback_data=f'prompts_cat:{cat}')])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    if lang == 'ru':
        await message.answer("<b>Библиотека промтов</b>\n\nВыберите категорию:", parse_mode='HTML', reply_markup=kb)
    else:
        await message.answer(
            f"<b>{t('prompts.title', lang)}</b>\n\n{t('prompts.chooseCategory', lang)}",
            parse_mode='HTML',
            reply_markup=kb,
        )


@router.message(Command('prompts'))
async def cmd_prompts(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await send_prompts_menu(message, tg_user, lang)


@router.callback_query(F.data.startswith('prompts_cat:'))
async def cb_prompts_category(query: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    category = query.data.split(':', 1)[1]
    prompts = await get_prompts_by_category(category)

    if not prompts:
        await query.answer('Промты не найдены.' if lang == 'ru' else t('prompts.notFound', lang))
        return

    buttons = []
    for p in prompts:
        title = (p.title or p.content[:40])[:50]
        buttons.append([InlineKeyboardButton(text=title, callback_data=f'use_prompt:{p.id}')])

    cat_label = _category_label(category, lang)
    back_label = 'Назад' if lang == 'ru' else t('prompts.back', lang)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons + [
        [InlineKeyboardButton(text=back_label, callback_data='prompts_back')]
    ])
    choose_prompt = 'Выберите промт:' if lang == 'ru' else t('prompts.choosePrompt', lang)
    await query.message.edit_text(
        f"<b>{cat_label}</b>\n\n{choose_prompt}",
        parse_mode='HTML',
        reply_markup=kb,
    )
    await query.answer()


@router.callback_query(F.data.startswith('use_prompt:'))
async def cb_use_prompt(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    prompt_id = int(query.data.split(':', 1)[1])
    prompt = await get_prompt_by_id(prompt_id)

    if not prompt:
        await query.answer('Промт не найден.' if lang == 'ru' else t('prompts.promptNotFound', lang))
        return

    await query.answer('Отправляю промт...' if lang == 'ru' else t('prompts.sending', lang))
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
    lang = resolve_language(tg_user, query.from_user)
    await send_prompts_menu(query.message, tg_user, lang)
    await query.answer()
