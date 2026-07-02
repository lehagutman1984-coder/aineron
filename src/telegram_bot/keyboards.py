from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)


def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Чат'),     KeyboardButton(text='Картинка'), KeyboardButton(text='Видео')],
            [KeyboardButton(text='Баланс'),  KeyboardButton(text='Модели'),   KeyboardButton(text='Настройки')],
            [KeyboardButton(text='Проекты'), KeyboardButton(text='История'),  KeyboardButton(text='Помощь')],
        ],
        resize_keyboard=True,
        input_field_placeholder='Напишите вопрос или выберите раздел',
    )


def after_answer_kb(message_id: int, has_tts: bool = True,
                    copy_code: str = '') -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text='👍', callback_data=f'react_like:{message_id}'),
        InlineKeyboardButton(text='👎', callback_data=f'react_dislike:{message_id}'),
        InlineKeyboardButton(text='↺', callback_data=f'regen:{message_id}'),
        InlineKeyboardButton(text='Новый чат', callback_data='newchat'),
    ]
    if has_tts:
        row1.append(InlineKeyboardButton(text='🔊', callback_data=f'tts:{message_id}'))
    row2 = [
        InlineKeyboardButton(text='✏', callback_data=f'edit_msg:{message_id}'),
        InlineKeyboardButton(text='✕', callback_data=f'del_msg:{message_id}'),
    ]
    rows = [row1, row2]
    # S1: нативная кнопка «Скопировать» (Bot API 7.11) под ответами с кодом
    if copy_code:
        try:
            from aiogram.types import CopyTextButton
            rows.append([InlineKeyboardButton(
                text='Скопировать код',
                copy_text=CopyTextButton(text=copy_code[:256]),
            )])
        except Exception:
            pass
    return InlineKeyboardMarkup(inline_keyboard=rows)


def models_kb(networks: list, current_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, net in enumerate(networks):
        label = f'· {net.name} ·' if net.id == current_id else net.name
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
    tab_type = active_tab

    tab_row = []
    for tab_key, tab_name in tab_labels.items():
        label = f'[ {tab_name} ]' if tab_key == active_tab else tab_name
        tab_row.append(InlineKeyboardButton(text=label, callback_data=f'models_tab:{tab_key}'))

    rows = [tab_row]

    row = []
    for net in networks:
        label = f'· {net.name} ·' if net.id == current_id else net.name
        row.append(InlineKeyboardButton(text=label[:30], callback_data=f'setmodel:{tab_type}:{net.id}'))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def star_packs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='100 ₽ — 50 XTR', callback_data='pack:stars_100')],
        [InlineKeyboardButton(text='220 ₽ — 100 XTR  (+10%)', callback_data='pack:stars_220')],
        [InlineKeyboardButton(text='600 ₽ — 250 XTR  (+20%)', callback_data='pack:stars_600')],
    ])


def webapp_kb(site_url: str) -> InlineKeyboardMarkup:
    """Inline button that opens the Telegram Mini App."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text='Открыть в браузере',
            web_app=WebAppInfo(url=f'{site_url}/tg/'),
        )
    ]])


def settings_kb(tg_user) -> InlineKeyboardMarkup:
    voice = 'Вкл' if tg_user.voice_responses else 'Выкл'
    search = 'Вкл' if tg_user.web_search else 'Выкл'
    streaming = 'Вкл' if tg_user.streaming else 'Выкл'
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Голосовые ответы: {voice}', callback_data='toggle:voice')],
        [InlineKeyboardButton(text=f'Веб-поиск: {search}', callback_data='toggle:search')],
        [InlineKeyboardButton(text=f'Стриминг: {streaming}', callback_data='toggle:streaming')],
        [InlineKeyboardButton(text='Системный промт', callback_data='settings:sysprompt')],
        [InlineKeyboardButton(text='Сменить модель', callback_data='settings:model')],
    ])
