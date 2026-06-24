"""
/reggroup <org_link_token> — регистрация Telegram-группы в организации.

Алгоритм:
  1. Пользователь создаёт ссылку-токен в ЛК → https://aineron.ru/dashboard/organization/
  2. Добавляет бота в группу, даёт права администратора
  3. Пишет в группе: /reggroup <token>
  4. Бот привязывает группу к организации и включает оргбиллинг
"""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()

BOT_LINK_TOKEN_PREFIX = 'TG-GROUP-'


def _register_group(group_id: int, group_title: str, token: str, registrant_tg_id: int):
    """Resolve token → org, create or update TelegramGroup. Returns (org_name, error)."""
    from teams.models import Organization
    from telegram_bot.models import TelegramGroup, TelegramUser, TelegramLinkToken

    # Find TelegramUser for the person running the command
    tg_user = None
    try:
        tg_user = TelegramUser.objects.get(telegram_id=registrant_tg_id)
    except TelegramUser.DoesNotExist:
        pass

    # Find org by token stored in Organization.meta['tg_group_token'] (JSONField lookup)
    org = Organization.objects.filter(meta__tg_group_token=token).first()

    if org is None:
        return None, 'Токен не найден. Создай токен в ЛК → Организация → Telegram-интеграция.'

    obj, created = TelegramGroup.objects.update_or_create(
        group_id=group_id,
        defaults={
            'group_title': group_title,
            'organization': org,
            'registered_by': tg_user,
            'enabled': True,
        }
    )
    return org.name, None


_register_group_async = sync_to_async(_register_group, thread_sensitive=True)


@router.message(Command('reggroup'))
async def cmd_reggroup(message: Message, tg_user=None):
    """Register this group with an organization."""
    if message.chat.type not in ('group', 'supergroup'):
        await message.answer('Эту команду можно использовать только в группах.')
        return

    # Check that user is admin in the group
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ('administrator', 'creator'):
            await message.reply('Только администраторы группы могут регистрировать группу.')
            return
    except Exception:
        pass

    token = message.text.removeprefix('/reggroup').strip()
    if not token:
        await message.reply(
            '<b>Регистрация группы в организации</b>\n\n'
            '1. Зайди в ЛК → Организация → Telegram-интеграция\n'
            '2. Создай токен подключения\n'
            '3. Введи в этой группе:\n'
            '<code>/reggroup ВАШ_ТОКЕН</code>\n\n'
            'После этого бот будет отвечать за счёт баланса организации.',
            parse_mode='HTML',
        )
        return

    org_name, error = await _register_group_async(
        message.chat.id,
        message.chat.title or '',
        token,
        message.from_user.id,
    )

    if error:
        await message.reply(f'Ошибка: {error}')
    else:
        await message.reply(
            f'Группа подключена к организации <b>{org_name}</b>.\n\n'
            'Теперь бот отвечает за счёт баланса организации. '
            'Упоминайте бота или отвечайте на его сообщения.',
            parse_mode='HTML',
        )
