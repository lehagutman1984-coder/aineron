"""
/videoset — настройки видео-генерации для текущей видео-модели.

Настройки хранятся per-модель в TelegramUser.video_settings
({str(network_id): {field: value}}) и применяются в /video и /img2video:
они кладутся в settings пользовательского сообщения, где их читает
validate_and_merge_settings в Celery-задаче (та же схема, что на сайте).

UI строится из config_json.ui_settings модели: select-поля — кнопки-циклы
(нажатие переключает на следующее значение), checkbox — тумблеры.
Текстовые поля (negative_prompt) в боте не редактируются.
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.utils import DIVIDER
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# Config helpers (чистые функции — БД не трогают)
# ---------------------------------------------------------------------------

def _editable_fields(config: dict) -> list[dict]:
    """Select/checkbox поля из ui_settings — то, что можно крутить кнопками."""
    fields = []
    for section in (config.get('ui_settings') or {}).get('sections', []):
        for f in section.get('fields', []):
            if f.get('type') in ('select', 'checkbox') and f.get('name'):
                fields.append(f)
    return fields


def _effective_value(field: dict, stored: dict, api_defaults: dict):
    name = field['name']
    if name in stored:
        return stored[name]
    if name in api_defaults:
        return api_defaults[name]
    options = field.get('options') or []
    return options[0]['value'] if options else None


def _value_label(field: dict, value, lang: str = 'ru') -> str:
    if field.get('type') == 'checkbox':
        if lang == 'ru':
            return 'вкл' if value else 'выкл'
        return t('videoSettings.on', lang) if value else t('videoSettings.off', lang)
    for opt in field.get('options') or []:
        if str(opt.get('value')) == str(value):
            return str(opt.get('label', value))
    return str(value)


def _calc_extra_cost(config: dict, stored: dict) -> int:
    """Доплата за настройки в рублях (та же логика, что при списании)."""
    if not stored:
        return 0
    from aitext.fal_utils import validate_and_merge_settings
    try:
        _, errors, extra = validate_and_merge_settings(config, stored)
        return 0 if errors else int(extra)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_video_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_video_network_id:
        net = tg_user.default_video_network
        cfg = net.config_json or {}
        if net.is_active and cfg.get('metadata', {}).get('output_type') == 'video':
            return net
    for net in NeuralNetwork.objects.filter(provider='fal-ai', is_active=True).order_by('order'):
        if (net.config_json or {}).get('metadata', {}).get('output_type') == 'video':
            return net
    return None


def _get_stored(telegram_id: int, network_id: int) -> dict:
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.only('id', 'video_settings').get(telegram_id=telegram_id)
    return dict((tg.video_settings or {}).get(str(network_id), {}))


def _apply_change(telegram_id: int, network, field_name: str, kind: str) -> dict:
    """Read-modify-write настроек одной кнопки. Возвращает новый stored."""
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.get(telegram_id=telegram_id)
    all_settings = dict(tg.video_settings or {})
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
    tg.video_settings = all_settings
    tg.save(update_fields=['video_settings'])
    return stored


def _reset_settings(telegram_id: int, network_id: int) -> dict:
    from telegram_bot.models import TelegramUser
    tg = TelegramUser.objects.get(telegram_id=telegram_id)
    all_settings = dict(tg.video_settings or {})
    all_settings.pop(str(network_id), None)
    tg.video_settings = all_settings
    tg.save(update_fields=['video_settings'])
    return {}


get_video_network = sync_to_async(_get_video_network, thread_sensitive=True)
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
        price_line = f'Цена за видео: <b>{format_money(total_kopecks)}</b>'
        if extra:
            price_line += f' (базовая {format_money(network.cost_kopecks)} + опции {extra} ₽)'

        text = (
            f'<b>Aineron · Настройки видео</b>\n{DIVIDER}\n'
            f'Модель: <b>{network.name}</b>\n'
            f'{price_line}\n\n'
            'Нажатие на кнопку переключает значение. Настройки сохраняются '
            'для этой модели и применяются в /video и /img2video.'
        )
    else:
        price_line = f"{t('videoSettings.priceLabel', lang)}: <b>{format_money(total_kopecks)}</b>"
        if extra:
            price_line += ' ' + t(
                'videoSettings.priceBreakdown', lang,
                base=format_money(network.cost_kopecks),
                extra=format_money(extra * 100),
            )

        text = (
            f"<b>{t('videoSettings.title', lang)}</b>\n{DIVIDER}\n"
            f"{t('videoSettings.modelLabel', lang)}: <b>{network.name}</b>\n"
            f"{price_line}\n\n"
            f"{t('videoSettings.hint', lang)}"
        )

    rows = []
    for f in fields:
        value = _effective_value(f, stored, api_defaults)
        label = f"{f.get('label', f['name'])}: {_value_label(f, value, lang)}"
        action = 't' if f.get('type') == 'checkbox' else 'c'
        rows.append([InlineKeyboardButton(
            text=label[:60],
            callback_data=f"vset:{action}:{f['name']}"[:64],
        )])

    reset_label = 'Сбросить' if lang == 'ru' else t('videoSettings.resetButton', lang)
    back_label = 'К моделям' if lang == 'ru' else t('videoSettings.backButton', lang)
    rows.append([
        InlineKeyboardButton(text=reset_label, callback_data='vset:r'),
        InlineKeyboardButton(text=back_label, callback_data='models_tab:video'),
    ])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render(target, tg_user, edit: bool, lang: str = 'ru'):
    network = await get_video_network(tg_user)
    if network is None:
        if lang == 'ru':
            text = f'<b>Aineron · Настройки видео</b>\n{DIVIDER}\nНет доступных видео-моделей.'
        else:
            text = f"<b>{t('videoSettings.title', lang)}</b>\n{DIVIDER}\n{t('videoSettings.noModels', lang)}"
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

@router.message(Command('videoset'))
async def cmd_videoset(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    await _render(message, tg_user, edit=False, lang=lang)


@router.callback_query(F.data == 'vset:o')
async def cb_vset_open(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    await query.answer()
    try:
        await _render(query.message, tg_user, edit=True, lang=lang)
    except Exception as e:
        logger.warning('vset open error: %s', e, exc_info=True)


@router.callback_query(F.data == 'vset:r')
async def cb_vset_reset(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    network = await get_video_network(tg_user)
    if network is None:
        await query.answer('Нет видео-модели' if lang == 'ru' else t('videoSettings.noVideoModel', lang))
        return
    await reset_settings(tg_user.telegram_id, network.id)
    await query.answer('Настройки сброшены' if lang == 'ru' else t('videoSettings.settingsReset', lang))
    try:
        text, kb = _build_screen(network, {}, lang)
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.warning('vset reset render error: %s', e)


@router.callback_query(F.data.startswith('vset:c:') | F.data.startswith('vset:t:'))
async def cb_vset_change(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    parts = query.data.split(':', 2)
    if len(parts) != 3:
        await query.answer('Неверный формат' if lang == 'ru' else t('videoSettings.invalidFormat', lang))
        return
    kind = 'toggle' if parts[1] == 't' else 'cycle'
    field_name = parts[2]

    network = await get_video_network(tg_user)
    if network is None:
        await query.answer('Нет видео-модели' if lang == 'ru' else t('videoSettings.noVideoModel', lang))
        return

    try:
        stored = await apply_change(tg_user.telegram_id, network, field_name, kind)
    except Exception as e:
        logger.warning('vset change error: %s', e, exc_info=True)
        await query.answer('Ошибка, попробуй ещё раз' if lang == 'ru' else t('videoSettings.changeError', lang))
        return

    await query.answer()
    try:
        text, kb = _build_screen(network, stored, lang)
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        # «message is not modified» — если значение не поменялось
        logger.debug('vset render skip: %s', e)
