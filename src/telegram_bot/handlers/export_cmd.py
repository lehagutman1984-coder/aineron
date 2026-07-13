"""
/export — экспортирует последний активный чат в Markdown и отправляет документом.
"""
import io
import logging
import re
from asgiref.sync import sync_to_async
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from django.utils.timezone import localtime
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def _build_md(chat, messages, lang: str = 'ru') -> str:
    title = chat.get_title()
    network_name = chat.network.name
    created = localtime(chat.created_at).strftime("%Y-%m-%d %H:%M")
    if lang == 'ru':
        model_label = "Модель"
        created_label = "Создан"
        you_label = "Вы"
    else:
        model_label = t('export.modelLabel', lang)
        created_label = t('export.createdLabel', lang)
        you_label = t('export.youLabel', lang)
    lines = [f"# {title}", f"**{model_label}:** {network_name}  ", f"**{created_label}:** {created}", "", "---", ""]
    for msg in messages:
        text = msg.plain_text or _strip_html(msg.content) or ""
        role = f"**{you_label}**" if msg.role == "user" else f"**{network_name}**"
        ts = localtime(msg.created_at).strftime("%H:%M")
        lines += [f"### {role} *{ts}*", "", text, ""]
    return "\n".join(lines)


def _get_export_data(tg_user):
    from telegram_bot.models import TelegramChat
    from aitext.models import Message as Msg

    tc = TelegramChat.objects.filter(tg_user=tg_user, is_active=True).select_related("chat__network").first()
    if not tc:
        return None, None
    chat = tc.chat
    messages = list(
        Msg.objects.filter(chat=chat, status=Msg.Status.COMPLETED).order_by("created_at").select_related("chat__network")
    )
    return chat, messages


@router.message(Command("export"))
async def export_handler(message: Message, tg_user=None, **kwargs):
    if not tg_user:
        return
    lang = resolve_language(tg_user, message.from_user)

    chat, messages = await sync_to_async(_get_export_data)(tg_user)
    if not chat:
        text = "У вас нет активного чата для экспорта." if lang == 'ru' else t('export.noActiveChat', lang)
        await message.answer(text, parse_mode="HTML")
        return
    if not messages:
        text = "В текущем чате нет сообщений для экспорта." if lang == 'ru' else t('export.noMessages', lang)
        await message.answer(text, parse_mode="HTML")
        return

    md_content = await sync_to_async(_build_md)(chat, messages, lang)
    file_bytes = md_content.encode("utf-8")

    safe_title = re.sub(r"[^\w\s-]", "", chat.get_title())[:40].strip() or "chat"
    safe_title = re.sub(r"\s+", "_", safe_title)
    filename = f"{safe_title}.md"

    if lang == 'ru':
        caption = f"📄 Экспорт чата <b>{chat.get_title()}</b> ({len(messages)} сообщений)"
    else:
        caption = f"📄 {t('export.caption', lang, title=chat.get_title(), count=len(messages))}"

    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename),
        caption=caption,
        parse_mode="HTML",
    )
