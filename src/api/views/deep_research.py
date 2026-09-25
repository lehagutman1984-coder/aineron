"""Sprint 2 — Deep Research Mode API views."""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import Chat, Message, DeepResearch
from api.error_messages import em
from api.permissions import IsEmailVerified


class DeepResearchStartView(APIView):
    """POST /v1/chats/<chat_id>/research/ — start a deep research job."""
    permission_classes = [IsAuthenticated, IsEmailVerified]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'error': 'question required'}, status=status.HTTP_400_BAD_REQUEST)

        if len(question) > 4000:
            return Response({'error': 'question too long (max 4000 chars)'}, status=status.HTTP_400_BAD_REQUEST)

        # Платная операция (2 LLM-вызова на модели чата + 5 веб-поисков): раньше веб-эндпоинт
        # был полностью бесплатным - платил только бот (/research). Предоплата, как в боте.
        from django.conf import settings as dj_settings
        from core.money import format_rub
        price = int(getattr(dj_settings, 'RESEARCH_PRICE_KOPECKS', 1000))

        # Create user message
        user_msg = Message.objects.create(
            chat=chat, role='user', content=question, plain_text=question, status='completed',
        )
        # Create placeholder assistant message
        assistant_msg = Message.objects.create(
            chat=chat, role='assistant', content='', plain_text='', status='pending',
        )

        # Атомарное списание; reference уникален по сообщению ассистента (идемпотентно).
        if not request.user.spend_kopecks(price, type='spend', reference=f'research:{assistant_msg.id}'):
            assistant_msg.delete()
            user_msg.delete()
            request.user.refresh_from_db(fields=['balance_kopecks'])
            from api.services.billing import top_up_url
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(price)}, у вас {format_rub(request.user.balance_kopecks)}. Пополните баланс: {top_up_url()}',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                    'required_kopecks': price,
                    'balance_kopecks': request.user.balance_kopecks,
                    'top_up_url': top_up_url(),
                }
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

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
            request.user.add_kopecks(price, type='refund', reference=f'research:{assistant_msg.id}')
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
