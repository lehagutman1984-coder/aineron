"""
/ai — AI-агенты и сценарии: готовые воркфлоу в 1 клик.

Usage:
  /ai              — показать меню сценариев
  /ai post <тема>  — написать пост для Telegram-канала
  /ai review       — код-ревью (присылаем код следующим сообщением)
  /ai email <тема> — написать деловое письмо
  /ai brief <тема> — составить бриф/ТЗ для задачи
  /ai summary      — краткое изложение (присылаем текст следующим сообщением)
  /ai translate <текст> — перевести на английский

/translate — перевести ответом на сообщение или /translate <текст>
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from asgiref.sync import sync_to_async

router = Router()


class ScenarioFSM(StatesGroup):
    waiting_code_input = State()
    waiting_summary_input = State()


SCENARIOS = [
    ('scenario:post',      '✍️ Пост для канала',      'Создать пост для Telegram-канала на тему:'),
    ('scenario:email',     '📧 Деловое письмо',        'Написать деловое письмо на тему:'),
    ('scenario:brief',     '📋 Бриф / ТЗ',            'Составить ТЗ для задачи:'),
    ('scenario:review',    '🔍 Код-ревью',             None),   # needs code input
    ('scenario:summary',   '📄 Краткое изложение',     None),   # needs text input
    ('scenario:translate', '🌐 Перевод на английский', 'Переведи на английский:'),
]

_PROMPTS = {
    'post': (
        "Ты — опытный SMM-копирайтер. Напиши цепляющий пост для Telegram-канала на тему: {topic}\n\n"
        "Требования:\n"
        "- 150-300 слов\n"
        "- Начни с сильного крючка (вопрос, факт, провокация)\n"
        "- 2-3 ключевые мысли с примерами\n"
        "- Призыв к действию в конце\n"
        "- Без хэштегов\n"
        "- Живой, разговорный стиль"
    ),
    'email': (
        "Ты — профессиональный бизнес-копирайтер. Напиши деловое письмо на тему: {topic}\n\n"
        "Требования:\n"
        "- Вежливый, но конкретный тон\n"
        "- Чёткая структура: приветствие → суть → что нужно → контакты\n"
        "- Не более 200 слов"
    ),
    'brief': (
        "Ты — опытный продакт-менеджер. Составь подробное ТЗ/бриф для задачи: {topic}\n\n"
        "Структура:\n"
        "1. Цель\n"
        "2. Целевая аудитория\n"
        "3. Требования (must-have и nice-to-have)\n"
        "4. Критерии успеха\n"
        "5. Ограничения и риски\n"
        "6. Примерные сроки"
    ),
    'review': (
        "Ты — опытный senior-разработчик. Проведи код-ревью следующего кода:\n\n```\n{code}\n```\n\n"
        "Анализируй:\n"
        "1. Корректность и баги\n"
        "2. Безопасность (SQL-инъекции, XSS, etc.)\n"
        "3. Производительность\n"
        "4. Читаемость и стиль\n"
        "5. Предложи конкретные улучшения с примерами кода"
    ),
    'summary': (
        "Сделай краткое изложение следующего текста (максимум 30% от оригинального объёма). "
        "Сохрани ключевые идеи и факты. Убери воду и повторения:\n\n{text}"
    ),
    'translate': (
        "Переведи точно и естественно на английский язык следующий текст. "
        "Сохрани тон и стиль оригинала:\n\n{text}"
    ),
}


def _scenarios_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(SCENARIOS), 2):
        row = []
        for cb_data, label, _ in SCENARIOS[i:i+2]:
            row.append(InlineKeyboardButton(text=label, callback_data=cb_data))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command('ai'))
async def cmd_ai(message: Message, state: FSMContext, tg_user=None):
    args = (message.text or '').split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "<b>AI-агенты: выберите сценарий</b>\n\n"
            "Или используйте сразу с аргументом:\n"
            "/ai post &lt;тема&gt;\n"
            "/ai email &lt;тема&gt;\n"
            "/ai brief &lt;тема&gt;\n"
            "/ai review — (затем пришлите код)\n"
            "/ai summary — (затем пришлите текст)\n"
            "/ai translate &lt;текст&gt;",
            parse_mode='HTML',
            reply_markup=_scenarios_kb(),
        )
        return

    cmd = args[1].lower()
    topic = args[2].strip() if len(args) > 2 else ''

    if cmd == 'review':
        await state.set_state(ScenarioFSM.waiting_code_input)
        await message.answer("Пришлите код для ревью:")
        return
    if cmd == 'summary':
        await state.set_state(ScenarioFSM.waiting_summary_input)
        await message.answer("Пришлите текст для краткого изложения:")
        return

    prompt_template = _PROMPTS.get(cmd)
    if not prompt_template:
        await message.answer(f"Неизвестный сценарий '{cmd}'. Доступные: post, email, brief, review, summary, translate")
        return
    if not topic:
        await message.answer(f"Укажите тему: /ai {cmd} <ваша тема>")
        return

    prompt = prompt_template.format(topic=topic, text=topic)
    await _run_scenario(message, tg_user, prompt)


@router.callback_query(F.data.startswith('scenario:'))
async def cb_scenario(callback: CallbackQuery, state: FSMContext, tg_user=None):
    key = callback.data.split(':', 1)[1]
    await callback.answer()

    if key == 'review':
        await state.set_state(ScenarioFSM.waiting_code_input)
        await callback.message.answer("Пришлите код для ревью:")
        return
    if key == 'summary':
        await state.set_state(ScenarioFSM.waiting_summary_input)
        await callback.message.answer("Пришлите текст для краткого изложения:")
        return

    # Prompt-only scenarios need a topic
    await state.update_data(scenario_key=key)
    scenario = next((s for s in SCENARIOS if s[0] == f'scenario:{key}'), None)
    label = scenario[1] if scenario else key
    await callback.message.answer(
        f"{label}\n\nВведите тему или запрос:",
    )
    await state.set_state(ScenarioFSM.waiting_summary_input)  # reuse for topic input
    await state.update_data(scenario_key=key, scenario_mode='topic')


@router.message(ScenarioFSM.waiting_code_input)
async def handle_code_input(message: Message, state: FSMContext, tg_user=None):
    code = message.text or ''
    await state.clear()
    if not code.strip():
        await message.answer("Пустой текст — отмена.")
        return
    prompt = _PROMPTS['review'].format(code=code)
    await _run_scenario(message, tg_user, prompt)


@router.message(ScenarioFSM.waiting_summary_input)
async def handle_summary_input(message: Message, state: FSMContext, tg_user=None):
    data = await state.get_data()
    scenario_mode = data.get('scenario_mode', 'text')
    scenario_key = data.get('scenario_key', 'summary')
    text = message.text or ''
    await state.clear()
    if not text.strip():
        await message.answer("Пустой текст — отмена.")
        return

    template = _PROMPTS.get(scenario_key, _PROMPTS['summary'])
    if scenario_mode == 'topic':
        prompt = template.format(topic=text, text=text)
    else:
        prompt = template.format(text=text, code=text, topic=text)
    await _run_scenario(message, tg_user, prompt)


async def _run_scenario(message: Message, tg_user, prompt: str):
    """Run an AI scenario and send the result to the user."""
    from telegram_bot.handlers.chat import process_text
    await process_text(message, tg_user, prompt)


_TRANSLATE_TARGETS = {
    'en': ('английский', 'на английский язык'),
    'ru': ('русский', 'на русский язык'),
    'zh': ('китайский', 'на китайский язык (Simplified)'),
    'de': ('немецкий', 'на немецкий язык'),
    'es': ('испанский', 'на испанский язык'),
    'fr': ('французский', 'на французский язык'),
}

_TRANSLATE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='EN', callback_data='tr:en'),
        InlineKeyboardButton(text='RU', callback_data='tr:ru'),
        InlineKeyboardButton(text='DE', callback_data='tr:de'),
    ],
    [
        InlineKeyboardButton(text='ES', callback_data='tr:es'),
        InlineKeyboardButton(text='FR', callback_data='tr:fr'),
        InlineKeyboardButton(text='ZH', callback_data='tr:zh'),
    ],
])


@router.message(Command('translate'))
async def cmd_translate(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжи аккаунт через /start')
        return

    # Text provided inline: /translate <text>
    parts = (message.text or '').split(maxsplit=1)
    inline_text = parts[1].strip() if len(parts) > 1 else ''

    # Or replying to a message
    reply_text = ''
    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ''

    source = inline_text or reply_text
    if not source:
        await message.answer(
            '<b>Перевод текста</b>\n\n'
            'Используй одним из способов:\n'
            '• Ответь на любое сообщение командой /translate\n'
            '• /translate &lt;текст&gt;',
            parse_mode='HTML',
        )
        return

    # If text is short or we know it's Russian, default to EN; otherwise ask
    await state.update_data(translate_source=source)
    await message.answer(
        f'<b>Перевести:</b>\n<i>{source[:200]}{"..." if len(source) > 200 else ""}</i>\n\nВыберите язык:',
        parse_mode='HTML',
        reply_markup=_TRANSLATE_KB,
    )


@router.callback_query(F.data.startswith('tr:'))
async def cb_translate(callback: CallbackQuery, state: FSMContext, tg_user=None):
    lang_code = callback.data.split(':', 1)[1]
    target = _TRANSLATE_TARGETS.get(lang_code)
    if not target:
        await callback.answer('Неизвестный язык')
        return

    data = await state.get_data()
    source = data.get('translate_source', '')
    await state.clear()

    if not source:
        await callback.answer('Текст не найден, попробуйте снова')
        return

    await callback.answer()
    lang_name, lang_phrase = target
    prompt = (
        f"Переведи точно и естественно {lang_phrase} следующий текст. "
        f"Сохрани тон и стиль оригинала:\n\n{source}"
    )
    await _run_scenario(callback.message, tg_user, prompt)
