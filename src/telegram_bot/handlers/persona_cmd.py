"""
/persona — AI персоны: выбор заготовленного системного промта.

Usage:
  /persona       — показать список персон
  /persona reset — сбросить активную персону
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


@sync_to_async
def _get_personas():
    from aitext.models import Persona
    return list(
        Persona.objects.filter(is_public=True, is_active=True).order_by('order', 'name')[:20]
    )


@sync_to_async
def _get_persona(persona_id):
    from aitext.models import Persona
    try:
        return Persona.objects.get(id=persona_id, is_active=True)
    except Persona.DoesNotExist:
        return None


@sync_to_async
def _apply_persona(tg_user, persona):
    """Set persona's system_prompt as the user's system_prompt."""
    tg_user.system_prompt = persona.system_prompt
    tg_user.save(update_fields=['system_prompt'])
    if persona.network_id and not tg_user.default_network_id:
        tg_user.default_network_id = persona.network_id
        tg_user.save(update_fields=['default_network'])


@sync_to_async
def _reset_persona(tg_user):
    tg_user.system_prompt = ''
    tg_user.save(update_fields=['system_prompt'])


def _personas_kb(personas, lang: str = 'ru'):
    rows = []
    for p in personas:
        rows.append([InlineKeyboardButton(
            text=p.name,
            callback_data=f'persona:{p.id}',
        )])
    reset_label = 'Сбросить персону' if lang == 'ru' else t('persona.resetButton', lang)
    rows.append([InlineKeyboardButton(text=reset_label, callback_data='persona:reset')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command('persona'))
async def cmd_persona(message: Message, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    if tg_user is None:
        await message.answer('Привяжи аккаунт через /start' if lang == 'ru' else t('menu.notLinkedShort', lang))
        return

    args = (message.text or '').split(maxsplit=1)
    if len(args) > 1 and args[1].strip().lower() == 'reset':
        await _reset_persona(tg_user)
        text = ('Персона сброшена. Теперь используется стандартный режим.' if lang == 'ru'
                else t('persona.resetDone', lang))
        await message.answer(text)
        return

    personas = await _get_personas()
    if not personas:
        if lang == 'ru':
            await message.answer(
                '<b>AI-персоны недоступны.</b>\n\nАдминистратор ещё не добавил ни одной персоны.',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('persona.unavailableTitle', lang)}</b>\n\n{t('persona.unavailableBody', lang)}",
                parse_mode='HTML',
            )
        return

    if lang == 'ru':
        current = tg_user.system_prompt[:60] if tg_user.system_prompt else 'нет'
        await message.answer(
            f'<b>AI-персоны</b>\n\n'
            f'Текущий системный промт: <i>{current}{"..." if len(tg_user.system_prompt) > 60 else ""}</i>\n\n'
            f'Выберите персону — она установит системный промт и изменит поведение бота:',
            parse_mode='HTML',
            reply_markup=_personas_kb(personas, lang),
        )
    else:
        current = tg_user.system_prompt[:60] if tg_user.system_prompt else t('persona.none', lang)
        suffix = '...' if tg_user.system_prompt and len(tg_user.system_prompt) > 60 else ''
        await message.answer(
            f"<b>{t('persona.title', lang)}</b>\n\n"
            f"{t('persona.currentPrompt', lang)}: <i>{current}{suffix}</i>\n\n"
            f"{t('persona.choose', lang)}",
            parse_mode='HTML',
            reply_markup=_personas_kb(personas, lang),
        )


@router.callback_query(F.data.startswith('persona:'))
async def cb_persona(callback: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, callback.from_user)
    key = callback.data.split(':', 1)[1]

    if key == 'reset':
        await _reset_persona(tg_user)
        text = ('Персона сброшена. Используется стандартный режим.' if lang == 'ru'
                else t('persona.resetDoneShort', lang))
        await callback.message.edit_text(text)
        await callback.answer()
        return

    try:
        persona_id = int(key)
    except ValueError:
        await callback.answer('Ошибка' if lang == 'ru' else t('persona.error', lang))
        return

    persona = await _get_persona(persona_id)
    if not persona:
        await callback.answer('Персона не найдена' if lang == 'ru' else t('persona.notFound', lang))
        return

    await _apply_persona(tg_user, persona)
    if lang == 'ru':
        await callback.message.edit_text(
            f'<b>Персона: {persona.name}</b>\n\n'
            f'{persona.description or ""}\n\n'
            f'<i>Системный промт установлен. Начните новый чат (/newchat) для чистого старта.</i>',
            parse_mode='HTML',
        )
        await callback.answer(f'Персона «{persona.name}» применена')
    else:
        await callback.message.edit_text(
            f"<b>{t('persona.appliedTitle', lang, name=persona.name)}</b>\n\n"
            f"{persona.description or ''}\n\n"
            f"<i>{t('persona.appliedBody', lang)}</i>",
            parse_mode='HTML',
        )
        await callback.answer(t('persona.appliedToast', lang, name=persona.name))
