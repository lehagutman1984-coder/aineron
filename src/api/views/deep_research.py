"""Sprint 2 — Deep Research Mode API views."""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import Chat, Message, DeepResearch
from api.error_messages import em


class DeepResearchStartView(APIView):
    """POST /v1/chats/<chat_id>/research/ — start a deep research job."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'error': 'question required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create user message
        user_msg = Message.objects.create(
            chat=chat, role='user', content=question, plain_text=question, status='completed',
        )
        # Create placeholder assistant message
        assistant_msg = Message.objects.create(
            chat=chat, role='assistant', content='', plain_text='', status='pending',
        )

        research = DeepResearch.objects.create(
            chat=chat, message=assistant_msg, question=question,
        )

        try:
            from aitext.tasks import deep_research_task
            deep_research_task.delay(research.id)
        except Exception as e:
            research.status = 'error'
            research.error = str(e)
            research.save(update_fields=['status', 'error'])
            return Response({'error': f'Could not enqueue task: {e}'}, status=502)

        chat.save(update_fields=['updated_at'])

        return Response({
            'research_id': research.id,
            'message_id': assistant_msg.id,
            'user_message_id': user_msg.id,
            'status': research.status,
        }, status=status.HTTP_201_CREATED)


class DeepResearchSaveView(APIView):
    """POST /v1/research/<research_id>/save/ — U3: сохранить отчёт в базу
    знаний проекта (ProjectFile source='research', индексируется в RAG)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, research_id):
        research = get_object_or_404(
            DeepResearch, id=research_id, chat__user=request.user,
        )
        if research.status != 'done':
            return Response({'error': em('research_not_finished')}, status=400)
        if getattr(research.chat, 'project_id', None) is None:
            return Response({'error': em('research_chat_no_project')}, status=400)

        from aitext.tasks import save_research_to_kb
        pf = save_research_to_kb(research.id)
        if pf is None:
            return Response({'error': em('research_no_report')}, status=400)
        return Response({
            'file_id': pf.id,
            'filename': pf.filename,
            'already_saved': research.saved_file_id == pf.id and research.saved_file_id is not None,
        })


class DeepResearchStatusView(APIView):
    """GET /v1/research/<research_id>/ — poll research status and steps."""
    permission_classes = [IsAuthenticated]

    def get(self, request, research_id):
        research = get_object_or_404(DeepResearch, id=research_id, chat__user=request.user)
        data = {
            'id': research.id,
            'status': research.status,
            'steps': research.steps,
            'error': research.error,
            'message_id': research.message_id,
            'created_at': research.created_at,
            'finished_at': research.finished_at,
        }
        if research.status == 'done' and research.message:
            data['content'] = research.message.content
            data['plain_text'] = research.message.plain_text
        return Response(data)
