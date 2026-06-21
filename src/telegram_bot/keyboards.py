from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Новый чат'), KeyboardButton(text='Баланс')],
            [KeyboardButton(text='Модели'), KeyboardButton(text='Настройки')],
        ],
        resize_keyboard=True,
        input_field_placeholder='Введи вопрос или команду...',
    )


def after_answer_kb(message_id: int, has_tts: bool = True) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text='Повторить', callback_data=f'regen:{message_id}'),
         InlineKeyboardButton(text='Новый чат', callback_data='newchat')],
    ]
    if has_tts:
        buttons[0].append(InlineKeyboardButton(text='Озвучить', callback_data=f'tts:{message_id}'))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def models_kb(networks: list, current_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, net in enumerate(networks):
        label = f'[{net.name}]' if net.id == current_id else net.name
        row.append(InlineKeyboardButton(text=label[:30], callback_data=f'setmodel:{net.id}'))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def models_tabs_kb(active_tab: str, networks: list, current_id: int | None = None) -> InlineKeyboardMarkup:
    """Three-tab keyboard: Текст / Изображения / Видео."""
    tab_labels = {
        'text': 'Текст',
        'image': 'Изображения',
        'video': 'Видео',
    }
    # Map tab → callback type prefix for setmodel
    tab_type = active_tab  # 'text' | 'image' | 'video'

    # Tab row
    tab_row = []
    for tab_key, tab_name in tab_labels.items():
        label = f'[ {tab_name} ]' if tab_key == active_tab else tab_name
        tab_row.append(InlineKeyboardButton(text=label, callback_data=f'models_tab:{tab_key}'))

    rows = [tab_row]

    # Model buttons
    row = []
    for net in networks:
        label = f'[{net.name}]' if net.id == current_id else net.name
        row.append(InlineKeyboardButton(text=label[:30], callback_data=f'setmodel:{tab_type}:{net.id}'))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def star_packs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='100 звёзд — 50 XTR', callback_data='pack:stars_100')],
        [InlineKeyboardButton(text='220 звёзд — 100 XTR (+10%)', callback_data='pack:stars_220')],
        [InlineKeyboardButton(text='600 звёзд — 250 XTR (+20%)', callback_data='pack:stars_600')],
    ])


def settings_kb(tg_user) -> InlineKeyboardMarkup:
    voice = 'Вкл' if tg_user.voice_responses else 'Выкл'
    search = 'Вкл' if tg_user.web_search else 'Выкл'
    streaming = 'Вкл' if tg_user.streaming else 'Выкл'
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Голосовые ответы: {voice}', callback_data='toggle:voice')],
        [InlineKeyboardButton(text=f'Веб-поиск: {search}', callback_data='toggle:search')],
        [InlineKeyboardButton(text=f'Streaming: {streaming}', callback_data='toggle:streaming')],
        [InlineKeyboardButton(text='Системный промт', callback_data='settings:sysprompt')],
        [InlineKeyboardButton(text='Сменить модель', callback_data='settings:model')],
    ])
