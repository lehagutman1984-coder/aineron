"""
/imgset — настройки генерации изображений для текущей image-модели.

Зеркало video_settings_cmd.py (BUG-D из TELEGRAM_SUPREMACY_PLAN_V2.md):
настройки хранятся per-модель в TelegramUser.image_settings
({str(network_id): {field: value}}) и применяются в /image и /img2img —
кладутся в settings пользовательского сообщения, где их читает
validate_and_merge_settings в Celery-задаче (та же схема, что на сайте
и что у /videoset).

UI строится из config_json.ui_settings модели: select-поля — кнопки-циклы
(нажатие переключает на следующее значение), checkbox — тумблеры.
Текстовые поля (negative_prompt) и number-поля (seed) в боте не
редактируются — тот же принцип, что у /videoset.
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language
from telegram_bot.handlers.video_settings_cmd import (
    _editable_fields, _effective_value, _calc_extra_cost,
)

logger = logging.getLogger(__name__)
router = Router()


def _value_label(field: dict, value, lang: str = 'ru') -> str:
    """Копия video_settings_cmd._value_label с imageSettings.* namespace вместо
    videoSettings.* — общая версия захардкожена под видео-ключи локали."""
    if field.get('type') == 'checkbox':
        if lang == 'ru':
            return 'вкл' if value else 'выкл'
        return t('imageSettings.on', lang) if value else t('imageSettings.off', lang)
    for opt in field.get('options') or []:
        if str(opt.get('value')) == str(value):
            return str(opt.get('label', value))
    return str(value)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_stored(telegram_id: int, network_id: int) -> dict:
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.only('id', 'image_settings').get(telegram_id=telegram_id)
    return dict((tg.image_settings or {}).get(str(network_id), {}))


def _apply_change(telegram_id: int, network, field_name: str, kind: str) -> dict:
    """Read-modify-write настроек одной кнопки. Возвращает новый stored."""
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.get(telegram_id=telegram_id)
    all_settings = dict(tg.image_settings or {})
    stored = dict(all_settings.get(str(network.id), {}))

    config = network.config_json or {}
    api_defaults = config.get('api_defaults') or {}
    field = next((f for f in _editable_fields(config) if f['name'] == field_name), None)
    if field is None:
        return stored

    if kind == 'toggle':
        current = bool(_effective_value(field, stored, api_defaults))
        stored[field_name] = not current
    else:  # cycle
        options = field.get('options') or []
        values = [str(o.get('value')) for o in options]
        if not values:
            return stored
        current = str(_effective_value(field, stored, api_defaults))
        idx = (values.index(current) + 1) % len(values) if current in values else 0
        stored[field_name] = values[idx]

    all_settings[str(network.id)] = stored
    tg.image_settings = all_settings
    tg.save(update_fields=['image_settings'])
    return stored


def _reset_settings(telegram_id: int, network_id: int) -> dict:
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.get(telegram_id=telegram_id)
    all_settings = dict(tg.image_settings or {})
    all_settings.pop(str(network_id), None)
    tg.image_settings = all_settings
    tg.save(update_fields=['image_settings'])
    return {}


get_stored = sync_to_async(_get_stored, thread_sensitive=True)
apply_change = sync_to_async(_apply_change, thread_sensitive=True)
reset_settings = sync_to_async(_reset_settings, thread_sensitive=True)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _build_screen(network, stored: dict, lang: str = 'ru'):
    from core.money import format_money

    config = network.config_json or {}
    api_defaults = config.get('api_defaults') or {}
    fields = _editable_fields(config)

    extra = _calc_extra_cost(config, stored)
    total_kopecks = network.cost_kopecks + extra * 100

    if lang == 'ru':
        price_line = f'Цена за изображение: <b>{format_money(total_kopecks)}</b>'
        if extra:
            price_line += f' (базовая {format_money(network.cost_kopecks)} + опции {extra} ₽)'

        text = (
            f'<b>Aineron · Настройки изображений</b>\n{DIVIDER}\n'
            f'Модель: <b>{network.name}</b>\n'
            f'{price_line}\n\n'
        )
        text += (
            'У этой модели нет настраиваемых параметров.'
            if not fields else
            'Нажатие на кнопку переключает значение. Настройки сохраняются '
            'для этой модели и применяются в /image и /img2img.'
        )
    else:
        price_line = f"{t('imageSettings.priceLabel', lang)}: <b>{format_money(total_kopecks)}</b>"
        if extra:
            price_line += ' ' + t(
                'imageSettings.priceBreakdown', lang,
                base=format_money(network.cost_kopecks),
                extra=format_money(extra * 100),
            )

        hint_key = 'imageSettings.noFields' if not fields else 'imageSettings.hint'
        text = (
            f"<b>{t('imageSettings.title', lang)}</b>\n{DIVIDER}\n"
            f"{t('imageSettings.modelLabel', lang)}: <b>{network.name}</b>\n"
            f"{price_line}\n\n"
            f"{t(hint_key, lang)}"
        )

    rows = []
    for f in fields:
        value = _effective_value(f, stored, api_defaults)
        label = f"{f.get('label', f['name'])}: {_value_label(f, value, lang)}"
        action = 't' if f.get('type') == 'checkbox' else 'c'
        rows.append([InlineKeyboardButton(
            text=label[:60],
            callback_data=f"iset:{action}:{f['name']}"[:64],
        )])

    reset_label = 'Сбросить' if lang == 'ru' else t('imageSettings.resetButton', lang)
    back_label = 'К моделям' if lang == 'ru' else t('imageSettings.backButton', lang)
    footer = [InlineKeyboardButton(text=back_label, callback_data='models_tab:image')]
    if fields:
        footer.insert(0, InlineKeyboardButton(text=reset_label, callback_data='iset:r'))
    rows.append(footer)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render(target, tg_user, edit: bool, lang: str = 'ru'):
    from telegram_bot.handlers.images import get_image_network
    network = await get_image_network(tg_user)
    if network is None:
        if lang == 'ru':
            text = f'<b>Aineron · Настройки изображений</b>\n{DIVIDER}\nНет доступных image-моделей.'
        else:
            text = f"<b>{t('imageSettings.title', lang)}</b>\n{DIVIDER}\n{t('imageSettings.noModels', lang)}"
        if edit:
            await target.edit_text(text, parse_mode='HTML')
        else:
            await target.answer(text, parse_mode='HTML')
        return

    stored = await get_stored(tg_user.telegram_id, network.id)
    text, kb = _build_screen(network, stored, lang)
    if edit:
        await target.edit_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await target.answer(text, parse_mode='HTML', reply_markup=kb)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.message(Command('imgset'))
async def cmd_imgset(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await _render(message, tg_user, edit=False, lang=lang)


@router.callback_query(F.data == 'iset:o')
async def cb_iset_open(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    await query.answer()
    try:
        await _render(query.message, tg_user, edit=True, lang=lang)
    except Exception as e:
        logger.warning('iset open error: %s', e, exc_info=True)


@router.callback_query(F.data == 'iset:r')
async def cb_iset_reset(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    from telegram_bot.handlers.images import get_image_network
    network = await get_image_network(tg_user)
    if network is None:
        await query.answer('Нет image-модели' if lang == 'ru' else t('imageSettings.noImageModel', lang))
        return
    await reset_settings(tg_user.telegram_id, network.id)
    await query.answer('Настройки сброшены' if lang == 'ru' else t('imageSettings.settingsReset', lang))
    try:
        text, kb = _build_screen(network, {}, lang)
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.warning('iset reset render error: %s', e)


@router.callback_query(F.data.startswith('iset:c:') | F.data.startswith('iset:t:'))
async def cb_iset_change(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    parts = query.data.split(':', 2)
    if len(parts) != 3:
        await query.answer('Неверный формат' if lang == 'ru' else t('imageSettings.invalidFormat', lang))
        return
    kind = 'toggle' if parts[1] == 't' else 'cycle'
    field_name = parts[2]

    from telegram_bot.handlers.images import get_image_network
    network = await get_image_network(tg_user)
    if network is None:
        await query.answer('Нет image-модели' if lang == 'ru' else t('imageSettings.noImageModel', lang))
        return

    try:
        stored = await apply_change(tg_user.telegram_id, network, field_name, kind)
    except Exception as e:
        logger.warning('iset change error: %s', e, exc_info=True)
        await query.answer('Ошибка, попробуй ещё раз' if lang == 'ru' else t('imageSettings.changeError', lang))
        return

    await query.answer()
    try:
        text, kb = _build_screen(network, stored, lang)
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        # «message is not modified» — если значение не поменялось
        logger.debug('iset render skip: %s', e)
