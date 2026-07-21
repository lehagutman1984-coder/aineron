"""S7 — топики-проекты в личке бота (Bot API 9.3+, за флагом TG_TOPICS).

Нативные «папки чатов» прямо в Telegram: /topics создаёт форум-топик на
каждый проект пользователя — у топика свой контекст, персона и модель
(через проект). Естественная навигация вместо /history-переключений.
"""
import html as html_mod
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot import capabilities
from telegram_bot.utils import card
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


def _list_projects(user):
    from aitext.models import Project
    return list(Project.objects.filter(user=user).order_by('-updated_at')[:15])


def _topic_for_project(tg_user, project_id):
    from telegram_bot.models import TelegramTopic
    return TelegramTopic.objects.filter(
        tg_user=tg_user, project_id=project_id, is_active=True,
    ).first()


def _save_topic(tg_user, topic_id: int, project, title: str):
    from telegram_bot.models import TelegramTopic
    topic, _ = TelegramTopic.objects.update_or_create(
        tg_user=tg_user, topic_id=topic_id,
        defaults={'project': project, 'title': title[:128], 'is_active': True},
    )
    return topic


def _resolve_topic_chat(tg_user, thread_id: int):
    """Chat для сообщений в топике: свой контекст, привязанный к проекту.

    Возвращает aitext.Chat или None (топик не наш).
    """
    from aitext.models import Chat
    from telegram_bot.models import TelegramTopic

    topic = (
        TelegramTopic.objects.select_related('project', 'chat')
        .filter(tg_user=tg_user, topic_id=thread_id, is_active=True).first()
    )
    if topic is None:
        return None
    if topic.chat_id and topic.chat is not None:
        return topic.chat

    network = tg_user.default_network
    if network is None:
        from aitext.models import NeuralNetwork
        network = NeuralNetwork.objects.filter(
            provider='openrouter', is_active=True).order_by('order').first()
    lang = resolve_language(tg_user, None)
    name = topic.title or topic.topic_id
    title = f'Топик — {name}' if lang == 'ru' else t('topics.chatTitle', lang, name=name)
    chat = Chat.objects.create(
        user=tg_user.user, network=network, title=title, project=topic.project,
    )
    topic.chat = chat
    topic.save(update_fields=['chat'])
    return chat


list_projects = sync_to_async(_list_projects, thread_sensitive=True)
topic_for_project = sync_to_async(_topic_for_project, thread_sensitive=True)
save_topic = sync_to_async(_save_topic, thread_sensitive=True)
resolve_topic_chat = sync_to_async(_resolve_topic_chat, thread_sensitive=True)


@router.message(Command('topics'))
async def cmd_topics(message: Message, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    if tg_user is None:
        text = 'Привяжите аккаунт через /start' if lang == 'ru' else t('topics.notLinked', lang)
        await message.answer(text)
        return
    if not capabilities.is_enabled('topics'):
        text = (
            'Топики-проекты скоро появятся. Пока используйте /projects '
            'для переключения контекста.'
        ) if lang == 'ru' else t('topics.comingSoon', lang)
        await message.answer(text)
        return
    if not capabilities.bot_supports(message.bot, 'create_forum_topic'):
        text = (
            'Эта версия бота не поддерживает топики — используйте /projects.'
            if lang == 'ru' else t('topics.unsupported', lang)
        )
        await message.answer(text)
        return

    projects = await list_projects(tg_user.user)
    if not projects:
        if lang == 'ru':
            body = card('Топики-проекты',
                        'У вас пока нет проектов. Создайте первый: /projects')
        else:
            body = card(t('topics.title', lang), t('topics.noProjects', lang))
        await message.answer(body, parse_mode='HTML')
        return

    rows = [
        [InlineKeyboardButton(text=p.name[:40], callback_data=f'topic_new:{p.pk}')]
        for p in projects
    ]
    if lang == 'ru':
        body = card('Топики-проекты',
                     'Выберите проект — создам для него отдельный топик в этом чате. '
                     'У каждого топика свой контекст, персона и база знаний проекта.')
    else:
        body = card(t('topics.title', lang), t('topics.chooseProject', lang))
    await message.answer(
        body,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith('topic_new:'))
async def cb_topic_new(query: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if tg_user is None:
        await query.answer()
        return
    project_id = int(query.data.split(':')[1])

    @sync_to_async
    def _get_project():
        from aitext.models import Project
        return Project.objects.filter(user=tg_user.user, pk=project_id).first()

    project = await _get_project()
    if project is None:
        text = 'Проект не найден' if lang == 'ru' else t('topics.projectNotFound', lang)
        await query.answer(text)
        return

    existing = await topic_for_project(tg_user, project_id)
    if existing:
        text = (f'Топик «{existing.title}» уже создан' if lang == 'ru'
                else t('topics.topicAlreadyExists', lang, title=existing.title))
        await query.answer(text, show_alert=True)
        return

    try:
        forum_topic = await query.bot.create_forum_topic(
            chat_id=query.message.chat.id, name=project.name[:128],
        )
        thread_id = forum_topic.message_thread_id
    except Exception as e:
        logger.warning(f'create_forum_topic failed: {e}')
        text = (
            'Не удалось создать топик. Убедитесь, что в чате с ботом включены темы.'
            if lang == 'ru' else t('topics.createFailed', lang)
        )
        await query.answer(text, show_alert=True)
        return

    await save_topic(tg_user, thread_id, project, project.name)
    answer_text = 'Топик создан' if lang == 'ru' else t('topics.created', lang)
    await query.answer(answer_text)
    try:
        if lang == 'ru':
            card_text = card(f'Проект «{html_mod.escape(project.name)}»',
                              'Пишите сюда — контекст, персона и база знаний этого '
                              'проекта подключены автоматически.')
        else:
            card_text = card(
                t('topics.projectCardTitle', lang, name=html_mod.escape(project.name)),
                t('topics.projectCardBody', lang),
            )
        await query.bot.send_message(
            chat_id=query.message.chat.id,
            message_thread_id=thread_id,
            text=card_text,
            parse_mode='HTML',
        )
    except Exception:
        pass
