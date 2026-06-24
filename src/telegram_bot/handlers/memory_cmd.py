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

    args = message.text.removeprefix('/memory').strip()

    if args.startswith('add '):
        content = args[4:].strip()
        if not content:
            await message.answer('Использование: <code>/memory add Я предпочитаю Python</code>', parse_mode='HTML')
            return
        created = await add_memory_async(tg_user.user, content)
        if created:
            await message.answer(f'Запомнил: <i>{content}</i>', parse_mode='HTML')
        else:
            await message.answer(f'Обновил: <i>{content}</i>', parse_mode='HTML')
        return

    if args == 'clear':
        await clear_memories_async(tg_user.user)
        await message.answer('Память очищена.')
        return

    # List memories
    mems = await list_memories_async(tg_user.user)
    if not mems:
        await message.answer(
            '<b>Память пуста</b>\n\n'
            'AI запоминает факты о тебе автоматически в процессе разговора.\n\n'
            'Добавить вручную: <code>/memory add Я работаю Python-разработчиком</code>',
            parse_mode='HTML',
        )
        return

    lines = ['<b>Что я помню о тебе:</b>\n']
    for m in mems:
        icon = CATEGORY_ICONS.get(m.category, '•')
        lines.append(f'{icon} {m.content}')

    lines.append(f'\n<i>Всего: {len(mems)} фактов</i>')
    lines.append('\n/memory clear — очистить всё')
    lines.append('/memory add &lt;текст&gt; — добавить факт')

    await message.answer('\n'.join(lines), parse_mode='HTML')
