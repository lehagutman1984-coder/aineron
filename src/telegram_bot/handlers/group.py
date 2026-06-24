import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.db.models import F as DjF

from telegram_bot.analytics import async_log_event

logger = logging.getLogger(__name__)
router = Router()


def _get_tg_user(telegram_id):
    from telegram_bot.models import TelegramUser
    try:
        return TelegramUser.objects.select_related('user', 'default_network').get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


def _get_group_config(group_id: int):
    """Return (TelegramGroup | None) for the given chat id."""
    from telegram_bot.models import TelegramGroup
    try:
        return TelegramGroup.objects.select_related('organization').get(
            group_id=group_id, enabled=True
        )
    except TelegramGroup.DoesNotExist:
        return None


def _charge_org(organization, cost_stars: int) -> bool:
    """Deduct cost from org balance. Returns False if insufficient balance."""
    from decimal import Decimal
    from teams.models import Organization
    # Convert stars to rubles: 1 star ≈ 0.1 rub (adjust to your rate)
    STAR_TO_RUB = Decimal('0.10')
    cost_rub = Decimal(cost_stars) * STAR_TO_RUB
    updated = Organization.objects.filter(
        id=organization.id,
        balance_rub__gte=cost_rub,
    ).update(balance_rub=DjF('balance_rub') - cost_rub)
    return updated > 0


_get_tg_user_async = sync_to_async(_get_tg_user, thread_sensitive=True)
_get_group_config_async = sync_to_async(_get_group_config, thread_sensitive=True)
_charge_org_async = sync_to_async(_charge_org, thread_sensitive=True)


@router.message(F.chat.type.in_({'group', 'supergroup'}))
async def handle_group_message(message: Message, bot: Bot):
    if not message.text:
        return

    bot_user = await bot.get_me()
    is_reply_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot_user.id
    )
    is_mention = bool(
        bot_user.username and f'@{bot_user.username}' in message.text
    )

    if not is_reply_to_bot and not is_mention:
        return

    tg_user = await _get_tg_user_async(message.from_user.id)

    # Check if this group has org billing configured
    group_config = await _get_group_config_async(message.chat.id)

    if group_config:
        # Org billing: anyone in the group can use the bot, charged from org balance
        network = None
        if tg_user:
            network = tg_user.default_network
        if network is None:
            from aitext.models import NeuralNetwork
            def _default_net():
                return NeuralNetwork.objects.filter(is_active=True).order_by('order').first()
            network = await sync_to_async(_default_net, thread_sensitive=True)()

        if network is None:
            await message.reply('Нет доступных моделей.')
            return

        cost = network.cost_per_message if network else 5
        ok = await _charge_org_async(group_config.organization, cost)
        if not ok:
            await message.reply(
                f'Баланс организации <b>{group_config.organization.name}</b> исчерпан. '
                f'Пополните баланс: https://aineron.ru/dashboard/organization/',
                parse_mode='HTML',
            )
            return

        # Anonymous group member — route to per-user isolated chat
        if tg_user is None:
            text = message.text
            if bot_user.username:
                text = text.replace(f'@{bot_user.username}', '').strip()
            if not text:
                return

            def _get_or_create_group_chat(group_cfg, from_uid, net):
                from telegram_bot.models import TelegramGroupChat, TelegramUser
                from aitext.models import Chat
                try:
                    owner_tg = TelegramUser.objects.select_related('user', 'default_network').get(
                        user=group_cfg.organization.owner
                    )
                except TelegramUser.DoesNotExist:
                    return None, None

                gc, _ = TelegramGroupChat.objects.get_or_create(
                    group=group_cfg,
                    from_user_id=from_uid,
                    network=net,
                    defaults={'is_active': True},
                )
                if gc.chat_id and Chat.objects.filter(id=gc.chat_id).exists():
                    return owner_tg, gc.chat
                chat = Chat.objects.create(
                    user=owner_tg.user,
                    network=net,
                    title=f'Group {group_cfg.group_title[:30]} / user {from_uid}',
                )
                gc.chat = chat
                gc.save(update_fields=['chat'])
                return owner_tg, chat

            owner_tg, group_chat = await sync_to_async(
                _get_or_create_group_chat, thread_sensitive=True
            )(group_config, message.from_user.id, network)

            if owner_tg is None:
                await message.reply('Владелец организации ещё не зарегистрирован в боте.')
                return

            original_prompt = owner_tg.system_prompt
            if group_config.system_prompt:
                owner_tg.system_prompt = group_config.system_prompt
            from telegram_bot.handlers.chat import process_text as _pt
            await _pt(message, owner_tg, text, skip_billing=True, chat_override=group_chat)
            owner_tg.system_prompt = original_prompt
            return

    elif tg_user is None:
        await message.reply('Привяжи аккаунт aineron.ru: напиши /start боту @aineron_bot')
        return

    text = message.text
    if bot_user.username:
        text = text.replace(f'@{bot_user.username}', '').strip()
    if not text:
        return

    # Override system prompt with group's if set
    if group_config and group_config.system_prompt and tg_user:
        original_prompt = tg_user.system_prompt
        tg_user.system_prompt = group_config.system_prompt
        from telegram_bot.handlers.chat import process_text
        await process_text(message, tg_user, text, skip_billing=bool(group_config))
        tg_user.system_prompt = original_prompt
        return

    from telegram_bot.handlers.chat import process_text
    await process_text(message, tg_user, text, skip_billing=bool(group_config))
