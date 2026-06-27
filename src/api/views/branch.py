"""Sprint 7 — Conversation Branching: create a branch chat from any message."""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import Chat, Message


class BranchChatView(APIView):
    """POST /v1/chats/<id>/branch/ — создаёт новый чат-ветку от указанного сообщения."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        message_id = request.data.get('message_id')
        if not message_id:
            return Response(
                {'error': {'message': 'message_id обязателен', 'type': 'invalid_request_error', 'code': None}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        branch_msg = get_object_or_404(Message, id=message_id, chat=chat)

        new_chat = Chat.objects.create(
            user=request.user,
            network=chat.network,
            project=chat.project,
            title=f"Ветка: {chat.get_title()[:60]}",
            settings=chat.settings,
            parent_chat=chat,
            branch_from_message_id=message_id,
        )

        messages_to_copy = chat.messages.filter(
            created_at__lte=branch_msg.created_at,
        ).order_by('created_at')

        for msg in messages_to_copy:
            Message.objects.create(
                chat=new_chat,
                role=msg.role,
                content=msg.content,
                plain_text=msg.plain_text or '',
                files=msg.files,
                status=msg.status,
                kb_sources=msg.kb_sources,
                variants=msg.variants,
            )

        return Response({'chat_id': new_chat.id, 'title': new_chat.get_title()}, status=status.HTTP_201_CREATED)
