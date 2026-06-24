"""
/search <query> — поиск по истории чатов пользователя.
"""
import logging
from asgiref.sync import sync_to_async
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()

MAX_RESULTS = 5


def _search_messages(user, query: str):
    from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
    from aitext.models import Message as Msg

    try:
        sq = SearchQuery(query, config="russian", search_type="websearch")
        vector = (
            SearchVector("plain_text", weight="A", config="russian")
            + SearchVector("content", weight="B", config="russian")
        )
        qs = (
            Msg.objects.filter(chat__user=user, status=Msg.Status.COMPLETED)
            .annotate(rank=SearchRank(vector, sq))
            .filter(rank__gte=0.005)
            .select_related("chat", "chat__network")
            .order_by("-rank", "-created_at")[:MAX_RESULTS]
        )
        results = list(qs)
    except Exception:
        # Fallback to icontains
        results = list(
            Msg.objects.filter(
                chat__user=user,
                status=Msg.Status.COMPLETED,
                content__icontains=query,
            )
            .select_related("chat", "chat__network")
            .order_by("-created_at")[:MAX_RESULTS]
        )
    return results


@router.message(Command("search"))
async def search_handler(message: Message, tg_user=None, **kwargs):
    if not tg_user:
        return
    user = await sync_to_async(lambda: tg_user.user)()
    args = (message.text or "").removeprefix("/search").strip()
    if len(args) < 2:
        await message.answer(
            "🔍 Введите запрос: <code>/search ваш запрос</code>\n\n"
            "Например: <code>/search python декоратор</code>",
            parse_mode="HTML",
        )
        return

    results = await sync_to_async(_search_messages)(user, args)
    if not results:
        await message.answer(
            f"🔍 По запросу <b>{args}</b> ничего не найдено.\n\n"
            "Попробуйте другие слова.",
            parse_mode="HTML",
        )
        return

    lines = [f"🔍 <b>Результаты поиска</b> по «{args}»:\n"]
    for i, msg in enumerate(results, 1):
        chat = msg.chat
        text = msg.plain_text or msg.content or ""
        # Get snippet
        idx = text.lower().find(args.lower())
        if idx >= 0:
            start = max(0, idx - 30)
            snippet = text[start : start + 100].strip()
        else:
            snippet = text[:100].strip()
        if len(text) > 100:
            snippet += "..."

        role_label = "Вы" if msg.role == "user" else chat.network.name
        title = chat.get_title()
        date = msg.created_at.strftime("%d.%m.%Y")
        lines.append(
            f"{i}. <b>{title}</b>\n"
            f"   <i>{role_label} · {date}</i>\n"
            f"   {snippet}\n"
        )

    lines.append("\n💡 Продолжите чат на <a href='https://aineron.ru/chat/'>aineron.ru</a>")
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
