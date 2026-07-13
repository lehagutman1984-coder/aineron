"""
/memory — просмотр и управление Persistent Memory бота.

Команды:
  /memory         — список активных воспоминаний
  /memory add <текст>  — добавить факт вручную
  /memory clear   — очистить все воспоминания
"""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


def _list_memories(user):
    from aitext.models import UserMemory
    mems = UserMemory.objects.filter(user=user, is_active=True).order_by('-created_at')[:30]
    return list(mems)


def _add_memory(user, content: str):
    from aitext.models import UserMemory
    key = content[:80].lower()
    obj, created = UserMemory.objects.update_or_create(
        user=user,
        content_key=key,
        defaults={
            'content': content,
            'category': UserMemory.Category.FACT,
            'source': 'user',
            'is_active': True,
        }
    )
    return created


def _clear_memories(user):
    from aitext.models import UserMemory
    count, _ = UserMemory.objects.filter(user=user, is_active=True).update(is_active=False), None
    return count


list_memories_async = sync_to_async(_list_memories, thread_sensitive=True)
add_memory_async = sync_to_async(_add_memory, thread_sensitive=True)
clear_memories_async = sync_to_async(_clear_memories, thread_sensitive=True)


CATEGORY_ICONS = {
    'profile': '👤',
    'preference': '⭐',
    'project': '📁',
    'fact': '💡',
    'skill': '🔧',
}


@router.message(Command('memory'))
async def cmd_memory(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)

    args = message.text.removeprefix('/memory').strip()

    if args.startswith('add '):
        content = args[4:].strip()
        if not content:
            usage = ('Использование: <code>/memory add Я предпочитаю Python</code>' if lang == 'ru'
                      else t('memory.usage', lang))
            await message.answer(usage, parse_mode='HTML')
            return
        created = await add_memory_async(tg_user.user, content)
        if created:
            text = f'Запомнил: <i>{content}</i>' if lang == 'ru' else t('memory.remembered', lang, content=content)
        else:
            text = f'Обновил: <i>{content}</i>' if lang == 'ru' else t('memory.updated', lang, content=content)
        await message.answer(text, parse_mode='HTML')
        return

    if args == 'clear':
        await clear_memories_async(tg_user.user)
        await message.answer('Память очищена.' if lang == 'ru' else t('memory.cleared', lang))
        return

    # List memories
    mems = await list_memories_async(tg_user.user)
    if not mems:
        if lang == 'ru':
            await message.answer(
                '<b>Память пуста</b>\n\n'
                'AI запоминает факты о тебе автоматически в процессе разговора.\n\n'
                'Добавить вручную: <code>/memory add Я работаю Python-разработчиком</code>',
                parse_mode='HTML',
            )
        else:
            await message.answer(
                f"<b>{t('memory.emptyTitle', lang)}</b>\n\n{t('memory.emptyBody', lang)}",
                parse_mode='HTML',
            )
        return

    if lang == 'ru':
        lines = ['<b>Что я помню о тебе:</b>\n']
    else:
        lines = [f"<b>{t('memory.listTitle', lang)}</b>\n"]
    for m in mems:
        icon = CATEGORY_ICONS.get(m.category, '•')
        lines.append(f'{icon} {m.content}')

    if lang == 'ru':
        lines.append(f'\n<i>Всего: {len(mems)} фактов</i>')
        lines.append('\n/memory clear — очистить всё')
        lines.append('/memory add &lt;текст&gt; — добавить факт')
    else:
        lines.append(f"\n<i>{t('memory.totalCount', lang, count=len(mems))}</i>")
        lines.append(f"\n{t('memory.clearHint', lang)}")
        lines.append(t('memory.addHint', lang))

    await message.answer('\n'.join(lines), parse_mode='HTML')
