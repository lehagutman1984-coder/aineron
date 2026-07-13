from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)


def main_reply_kb(lang: str = 'ru') -> ReplyKeyboardMarkup:
    if lang == 'ru':
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text='Чат'),     KeyboardButton(text='Картинка'), KeyboardButton(text='Видео')],
                [KeyboardButton(text='Баланс'),  KeyboardButton(text='Модели'),   KeyboardButton(text='Настройки')],
                [KeyboardButton(text='Проекты'), KeyboardButton(text='История'),  KeyboardButton(text='Задачи')],
                [KeyboardButton(text='Исследование'), KeyboardButton(text='Помощь')],
            ],
            resize_keyboard=True,
            input_field_placeholder='Напишите вопрос или выберите раздел',
        )
    # Международный инстанс (G4): урезанный набор — только зарегистрированные
    # на intl-боте хендлеры (см. bot.py register_routers). Video/Projects/
    # История/Задачи/Исследование пока не переведены и не подключены.
    from telegram_bot.i18n import t
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t('menu.chat', lang)), KeyboardButton(text=t('menu.image', lang))],
            [KeyboardButton(text=t('menu.balance', lang)), KeyboardButton(text=t('menu.models', lang))],
            [KeyboardButton(text=t('menu.settings', lang)), KeyboardButton(text=t('menu.help', lang))],
        ],
        resize_keyboard=True,
    )


def after_answer_kb(message_id: int, has_tts: bool = True,
                    copy_code: str = '', lang: str = 'ru') -> InlineKeyboardMarkup:
    from telegram_bot.i18n import t
    row1 = [
        InlineKeyboardButton(text='👍', callback_data=f'react_like:{message_id}'),
        InlineKeyboardButton(text='👎', callback_data=f'react_dislike:{message_id}'),
        InlineKeyboardButton(text='↺', callback_data=f'regen:{message_id}'),
        InlineKeyboardButton(text=t('chat.newChatButton', lang), callback_data='newchat'),
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
                text=t('chat.copyCodeButton', lang),
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


def models_tabs_kb(active_tab: str, networks: list, current_id: int | None = None,
                   lang: str = 'ru') -> InlineKeyboardMarkup:
    """Three-tab keyboard: Текст / Изображения / Видео."""
    if lang == 'ru':
        tab_labels = {'text': 'Текст', 'image': 'Изображения', 'video': 'Видео'}
    else:
        from telegram_bot.i18n import t
        tab_labels = {
            'text': t('models.tabText', lang),
            'image': t('models.tabImage', lang),
            'video': t('models.tabVideo', lang),
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

    if active_tab == 'video' and networks:
        from telegram_bot.i18n import t as _t
        rows.append([InlineKeyboardButton(text=_t('models.videoSettingsButton', lang), callback_data='vset:o')])

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


def settings_kb(tg_user, lang: str = 'ru') -> InlineKeyboardMarkup:
    if lang == 'ru':
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
    from telegram_bot.i18n import t
    on, off = t('settings.on', lang), t('settings.off', lang)
    voice = on if tg_user.voice_responses else off
    search = on if tg_user.web_search else off
    streaming = on if tg_user.streaming else off
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t('settings.voiceReplies', lang)}: {voice}", callback_data='toggle:voice')],
        [InlineKeyboardButton(text=f"{t('settings.webSearch', lang)}: {search}", callback_data='toggle:search')],
        [InlineKeyboardButton(text=f"{t('settings.streaming', lang)}: {streaming}", callback_data='toggle:streaming')],
        [InlineKeyboardButton(text=t('settings.sysPromptButton', lang), callback_data='settings:sysprompt')],
        [InlineKeyboardButton(text=t('settings.changeModelButton', lang), callback_data='settings:model')],
        [InlineKeyboardButton(text=t('settings.languageButton', lang), callback_data='settings:language')],
    ])


# Названия языков на самих себе (не переводятся) — INTL_LOCALES из telegram_bot/i18n.py.
_LANGUAGE_NAMES = {
    'en': 'English',
    'fa': 'فارسی',
    'tr': 'Türkçe',
    'id': 'Indonesia',
    'ar': 'العربية',
}


def language_kb(current: str, lang: str) -> InlineKeyboardMarkup:
    """current — tg_user.language ('' значит «авто по клиенту Telegram»)."""
    from telegram_bot.i18n import t, INTL_LOCALES
    rows = []
    for code in INTL_LOCALES:
        label = f'· {_LANGUAGE_NAMES[code]} ·' if current == code else _LANGUAGE_NAMES[code]
        rows.append([InlineKeyboardButton(text=label, callback_data=f'lang:{code}')])
    auto_label_raw = t('language.auto', lang)
    auto_label = f'· {auto_label_raw} ·' if not current else auto_label_raw
    rows.append([InlineKeyboardButton(text=auto_label, callback_data='lang:auto')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
