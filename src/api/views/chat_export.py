import re
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from aitext.models import Chat, Message


def _strip_html(html: str) -> str:
    """Remove HTML tags, decode common entities."""
    text = re.sub(r"<[^>]+>", "", html or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return text.strip()


def _build_markdown(chat: Chat, messages) -> str:
    title = chat.get_title()
    network_name = chat.network.name
    created = localtime(chat.created_at).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {title}",
        f"**Модель:** {network_name}  ",
        f"**Создан:** {created}",
        "",
        "---",
        "",
    ]
    for msg in messages:
        text = msg.plain_text or _strip_html(msg.content) or ""
        role_label = "**Вы**" if msg.role == "user" else f"**{network_name}**"
        ts = localtime(msg.created_at).strftime("%H:%M")
        lines.append(f"### {role_label} *{ts}*")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _build_html(chat: Chat, messages) -> str:
    title = chat.get_title()
    network_name = chat.network.name
    created = localtime(chat.created_at).strftime("%Y-%m-%d %H:%M")

    msg_html_parts = []
    for msg in messages:
        content = msg.content or ""
        text = msg.plain_text or _strip_html(content) or ""
        role_label = "Вы" if msg.role == "user" else network_name
        role_class = "user" if msg.role == "user" else "assistant"
        ts = localtime(msg.created_at).strftime("%H:%M")
        # Use HTML content for assistant (already rendered), plain for user
        display = content if msg.role == "assistant" else f"<p>{text}</p>"
        msg_html_parts.append(
            f'<div class="message {role_class}">'
            f'<div class="meta"><strong>{role_label}</strong> <span class="time">{ts}</span></div>'
            f'<div class="body">{display}</div>'
            f"</div>"
        )

    msgs_joined = "\n".join(msg_html_parts)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 20px; color: #111; }}
  h1 {{ font-size: 1.4em; }}
  .meta-info {{ color: #666; font-size: 0.9em; margin-bottom: 24px; }}
  .message {{ margin: 16px 0; }}
  .message .meta {{ font-size: 0.8em; color: #888; margin-bottom: 4px; }}
  .message.user .body {{ background: #f0f4ff; border-radius: 8px; padding: 10px 14px; }}
  .message.assistant .body {{ background: #f9f9f9; border-radius: 8px; padding: 10px 14px; }}
  .time {{ font-weight: normal; }}
  pre {{ background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.85em; }}
  code {{ background: #eee; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta-info">Модель: <strong>{network_name}</strong> &nbsp;·&nbsp; Создан: {created}</div>
{msgs_joined}
</body>
</html>"""


class ChatExportView(APIView):
    """
    GET /v1/chats/<pk>/export/?format=md|html

    Export a chat as Markdown (default) or HTML file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chat = get_object_or_404(Chat, pk=pk, user=request.user)
        fmt = (request.query_params.get("format") or "md").lower()
        messages = chat.messages.filter(
            status=Message.Status.COMPLETED
        ).order_by("created_at")

        safe_title = re.sub(r"[^\w\s-]", "", chat.get_title())[:50].strip() or "chat"
        safe_title = re.sub(r"\s+", "_", safe_title)

        if fmt == "html":
            content = _build_html(chat, messages)
            response = HttpResponse(content, content_type="text/html; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{safe_title}.html"'
        else:
            content = _build_markdown(chat, messages)
            response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{safe_title}.md"'

        return response
