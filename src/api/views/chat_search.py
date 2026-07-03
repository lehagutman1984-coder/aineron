import re
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from aitext.models import Chat, Message


def _snippet(text: str, query: str, max_len: int = 150) -> str:
    """Extract a highlighted snippet around the first match."""
    if not text:
        return ""
    idx = text.lower().find(query.lower())
    if idx == -1:
        # Try word-by-word
        for word in query.split():
            if len(word) > 2:
                idx = text.lower().find(word.lower())
                if idx != -1:
                    break
    if idx == -1:
        return text[:max_len] + ("..." if len(text) > max_len else "")
    start = max(0, idx - 50)
    end = min(len(text), idx + max(len(query), 60) + 50)
    snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
    return snippet


class ChatSearchView(APIView):
    """
    GET /v1/chats/search/?q=<query>[&page=1][&page_size=10]

    Full-text search across user's chat history.
    Returns matched messages with chat info and text snippet.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"results": [], "count": 0, "has_more": False})

        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(20, max(5, int(request.query_params.get("page_size", 10))))
        except (ValueError, TypeError):
            page, page_size = 1, 10

        offset = (page - 1) * page_size

        # Postgres full-text search (russian + simple configs for latin words)
        try:
            search_query = SearchQuery(q, config="russian", search_type="websearch")
        except Exception:
            search_query = SearchQuery(q, search_type="websearch")

        vector = (
            SearchVector("plain_text", weight="A", config="russian")
            + SearchVector("content", weight="B", config="russian")
        )

        qs = (
            Message.objects.filter(
                chat__user=request.user,
                status=Message.Status.COMPLETED,
            )
            .annotate(rank=SearchRank(vector, search_query))
            .filter(rank__gte=0.005)
            .select_related("chat", "chat__network")
            .order_by("-rank", "-created_at")
        )

        # Fallback: icontains if FTS returns nothing
        total = qs.count()
        if total == 0:
            qs = (
                Message.objects.filter(
                    chat__user=request.user,
                    status=Message.Status.COMPLETED,
                )
                .filter(content__icontains=q)
                .select_related("chat", "chat__network")
                .order_by("-created_at")
            )
            total = qs.count()

        page_msgs = qs[offset : offset + page_size]

        results = []
        for msg in page_msgs:
            text = msg.plain_text or msg.content or ""
            results.append(
                {
                    "chat_id": msg.chat.id,
                    "chat_title": msg.chat.get_title(),
                    "network_name": msg.chat.network.name,
                    "network_slug": msg.chat.network.slug,
                    "message_id": msg.id,
                    "role": msg.role,
                    "snippet": _snippet(text, q),
                    "created_at": msg.created_at.isoformat(),
                }
            )

        # U2 (Total Recall): семантический слой поверх FTS — находит чаты
        # по смыслу, когда точных слов в тексте нет (первая страница)
        semantic = []
        if page == 1:
            try:
                from aitext.embeddings import recall_search
                seen_chats = {r["chat_id"] for r in results}
                for h in recall_search(request.user, q, top_k=3):
                    if h["chat_id"] in seen_chats:
                        continue
                    semantic.append(
                        {
                            "chat_id": h["chat_id"],
                            "chat_title": h["title"] or "Без названия",
                            "snippet": h["summary"][:150],
                            "semantic": True,
                            "updated_at": h["updated_at"].isoformat()
                            if hasattr(h["updated_at"], "isoformat") else None,
                        }
                    )
            except Exception:
                pass

        return Response(
            {
                "results": results,
                "semantic": semantic,
                "count": total,
                "page": page,
                "has_more": (offset + page_size) < total,
            }
        )
