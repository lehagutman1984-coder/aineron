"""S7 — Группы 2.0: /summary (суммаризация), /quiz (AI-квизы), /stat (B2B-расход).

Роутер подключается ПЕРЕД group.router (иначе catch-all группового хендлера
поглотит команды). /summary и /stat работают в зарегистрированных группах
(орг-биллинг); /quiz — в любой группе с привязанным пользователем.
"""
import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

from telegram_bot.utils import card

logger = logging.getLogger(__name__)
router = Router()

GROUP_TYPES = {'group', 'supergroup'}


def _get_group_config(group_id: int):
    from telegram_bot.models import TelegramGroup
    return TelegramGroup.objects.select_related('organization').filter(
        group_id=group_id, enabled=True,
    ).first()


def _cheap_network():
    from aitext.models import NeuralNetwork
    return (
        NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
        .order_by('cost_kopecks').first()
    )


def _llm(prompt: str, max_tokens: int = 1200, temperature: float = 0.4) -> str:
    from aitext.tasks import get_laozhang_client
    network = _cheap_network()
    if network is None or not network.model_name:
        return ''
    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or '').strip()
    except Exception as e:
        logger.warning(f'group2 llm failed: {e}')
        return ''


def _charge(group_config, tg_user) -> bool:
    """Списание за групповую AI-операцию: орг-баланс, иначе личный."""
    network = _cheap_network()
    cost = network.cost_kopecks if network else 100
    if group_config:
        from telegram_bot.handlers.group import _charge_org
        return _charge_org(group_config.organization, cost)
    if tg_user is not None:
        return tg_user.user.spend_kopecks(cost, type='spend')
    return False


def _fetch_log(group_config, hours: int, limit: int = 300):
    from datetime import timedelta
    from django.utils import timezone
    from telegram_bot.models import GroupMessageLog
    since = timezone.now() - timedelta(hours=hours)
    logs = list(
        GroupMessageLog.objects.filter(group=group_config, created_at__gte=since)
        .order_by('-created_at')[:limit]
    )
    logs.reverse()
    return logs


def _usage_stat(group_config, days: int = 30):
    """Расход по участникам: сообщения в изолированных чатах группы."""
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count
    from aitext.models import Message as AiMsg
    from telegram_bot.models import TelegramGroupChat

    since = timezone.now() - timedelta(days=days)
    group_chats = TelegramGroupChat.objects.filter(group=group_config)
    chat_owner = {gc.chat_id: gc.from_user_id for gc in group_chats if gc.chat_id}
    if not chat_owner:
        return []
    rows = (
        AiMsg.objects.filter(chat_id__in=chat_owner.keys(), role='user',
                             created_at__gte=since)
        .values('chat_id')
        .annotate(n=Count('id'))
    )
    per_user = {}
    for r in rows:
        uid = chat_owner.get(r['chat_id'])
        per_user[uid] = per_user.get(uid, 0) + r['n']
    return sorted(per_user.items(), key=lambda x: -x[1])[:10]


get_group_config = sync_to_async(_get_group_config, thread_sensitive=True)
llm = sync_to_async(_llm, thread_sensitive=True)
charge = sync_to_async(_charge, thread_sensitive=True)
fetch_log = sync_to_async(_fetch_log, thread_sensitive=True)
usage_stat = sync_to_async(_usage_stat, thread_sensitive=True)


@router.message(Command('summary'), F.chat.type.in_(GROUP_TYPES))
async def cmd_summary(message: Message, tg_user=None):
    """Суммаризация обсуждения за N часов (по умолчанию 8)."""
    group_config = await get_group_config(message.chat.id)
    if group_config is None:
        await message.reply(
            'Суммаризация доступна в группах, подключённых к организации '
            '(/reggroup). Владелец организации может подключить группу '
            'на aineron.ru/dashboard/organization/',
        )
        return

    parts = (message.text or '').split()
    try:
        hours = max(1, min(48, int(parts[1]))) if len(parts) > 1 else 8
    except ValueError:
        hours = 8

    logs = await fetch_log(group_config, hours)
    if len(logs) < 5:
        await message.reply(
            f'Слишком мало сообщений за {hours} ч для сводки '
            f'(бот собирает историю с момента подключения).',
        )
        return

    if not await charge(group_config, tg_user):
        await message.reply('Баланс организации исчерпан — пополните на сайте.')
        return

    dialogue = '\n'.join(f'{l.from_name}: {l.text}' for l in logs)
    status = await message.reply(f'Готовлю сводку за {hours} ч ({len(logs)} сообщений)...')
    summary = await llm(
        'Сделай структурированную сводку группового обсуждения: главные темы, '
        'решения и договорённости, открытые вопросы. Кратко, по-русски, '
        'с маркированными списками. Не упоминай, что ты AI.\n\n'
        f'Диалог:\n{dialogue[:12000]}',
    )
    if not summary:
        await status.edit_text('Не удалось подготовить сводку, попробуйте позже.')
        return
    from telegram_bot.utils import telegram_format, split_message
    parts_out = split_message(telegram_format(summary))
    summary_card = card(f'Сводка за {hours} ч', parts_out[0][:3800],
                        'Авто-сводку каждый день настроит владелец: /task в личке бота')
    try:
        await status.edit_text(summary_card, parse_mode='HTML')
    except Exception:
        # LLM мог вернуть невалидный для Telegram HTML — plain-text fallback
        await status.edit_text(f'Сводка за {hours} ч\n\n{summary[:3800]}')
    for extra in parts_out[1:]:
        try:
            await message.answer(extra, parse_mode='HTML')
        except Exception:
            await message.answer(extra)


@router.message(Command('quiz'), F.chat.type.in_(GROUP_TYPES))
async def cmd_quiz(message: Message, tg_user=None):
    """AI-квиз для группы: /quiz <тема> — 3 вопроса с вариантами."""
    topic = (message.text or '').split(maxsplit=1)
    topic = topic[1].strip() if len(topic) > 1 else ''
    if not topic:
        await message.reply('Использование: /quiz <тема>\nНапример: /quiz история Рима')
        return

    group_config = await get_group_config(message.chat.id)
    if tg_user is None and group_config is None:
        await message.reply('Привяжите аккаунт: напишите /start боту @aineron_bot')
        return
    if not await charge(group_config, tg_user):
        await message.reply('Недостаточно средств для генерации квиза.')
        return

    status = await message.reply(f'Готовлю квиз по теме «{topic[:60]}»...')
    raw = await llm(
        f'Составь квиз из 3 вопросов по теме «{topic}». Верни ТОЛЬКО JSON-массив:\n'
        '[{"question": "вопрос до 250 символов", "options": ["A", "B", "C", "D"], '
        '"correct": 0, "explanation": "почему, до 150 символов"}]\n'
        'Варианты — до 90 символов каждый. Вопросы интересные, не банальные. По-русски.',
        max_tokens=900, temperature=0.7,
    )
    questions = []
    try:
        start, end = raw.find('['), raw.rfind(']') + 1
        if start != -1 and end > start:
            questions = json.loads(raw[start:end])
    except Exception:
        pass
    if not questions:
        await status.edit_text('Не удалось сгенерировать квиз, попробуйте другую тему.')
        return

    try:
        await status.delete()
    except Exception:
        pass
    sent = 0
    for q in questions[:3]:
        try:
            options = [str(o)[:95] for o in q.get('options', [])][:10]
            correct = int(q.get('correct', 0))
            if len(options) < 2 or not (0 <= correct < len(options)):
                continue
            await message.answer_poll(
                question=str(q.get('question', ''))[:290],
                options=options,
                type='quiz',
                correct_option_id=correct,
                explanation=str(q.get('explanation', ''))[:190] or None,
                is_anonymous=False,
            )
            sent += 1
        except Exception as e:
            logger.warning(f'quiz poll failed: {e}')
    if not sent:
        await message.reply('Не удалось отправить квиз.')


@router.message(Command('stat'), F.chat.type.in_(GROUP_TYPES))
async def cmd_stat(message: Message, tg_user=None):
    """B2B: расход по участникам группы за 30 дней."""
    group_config = await get_group_config(message.chat.id)
    if group_config is None:
        await message.reply('Статистика доступна в группах с орг-биллингом (/reggroup).')
        return

    rows = await usage_stat(group_config)
    if not rows:
        await message.reply('Пока нет данных об использовании в этой группе.')
        return

    lines = []
    for i, (uid, count) in enumerate(rows, 1):
        lines.append(f'{i}. id{uid} — {count} запрос(ов)')
    await message.reply(
        card(f'Использование за 30 дней · {group_config.organization.name}',
             '\n'.join(lines),
             'Детальная аналитика: aineron.ru/dashboard/usage/'),
        parse_mode='HTML',
    )
