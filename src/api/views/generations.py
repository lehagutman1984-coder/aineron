"""Sprint 3 — SSE progress stream for media (video) generation.

Video-генерация выполняется синхронно внутри Celery-воркера (polling до 15-20 мин),
обновляя поля progress/status у placeholder-строки GeneratedImage. Этот эндпоинт в
web-процессе читает свежие значения из БД (Django autocommit — апдейты воркера видны
сразу) и стримит их фронту как Server-Sent Events.
"""
import json
import time

from django.db.models import Q
from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer

from api.authentication import CsrfExemptSessionAuthentication
from aitext.models import GeneratedImage


class EventStreamRenderer(BaseRenderer):
    """EventSource шлёт Accept: text/event-stream — без этого рендерера DRF
    отвечает 406 на этапе content negotiation, до вызова get()."""
    media_type = 'text/event-stream'
    format = 'sse'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, (bytes, str)):
            return data
        return json.dumps(data, ensure_ascii=False)


def _user_gens_q(user):
    return Q(message__chat__user=user) | Q(user=user)

# Опрашиваем БД каждые 2 сек; максимум 20 минут (600 итераций) на одно видео.
POLL_SECONDS = 2
MAX_ITERATIONS = 600


class GenerationProgressView(APIView):
    """GET /v1/generations/<pk>/progress/ — SSE-стрим прогресса генерации."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [EventStreamRenderer, JSONRenderer]

    def get(self, request, pk):
        # Проверяем владение до открытия стрима (404/403 нельзя отдать после старта SSE).
        gen = (
            GeneratedImage.objects
            .filter(_user_gens_q(request.user), pk=pk)
            .values('id', 'status', 'progress', 'image')
            .first()
        )
        if gen is None:
            return JsonResponse({'error': 'not found'}, status=404)

        user = request.user

        def event_stream():
            def _sse(payload):
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode('utf-8')

            # Немедленно отдаём текущее состояние (не ждём первого poll-интервала).
            row = gen
            for _ in range(MAX_ITERATIONS):
                status = row.get('status') or 'running'
                progress = int(row.get('progress') or 0)
                has_file = bool(row.get('image'))
                yield _sse({'progress': progress, 'status': status})

                if status in ('done', 'error') or (status == 'done' and has_file):
                    break

                time.sleep(POLL_SECONDS)
                row = (
                    GeneratedImage.objects
                    .filter(_user_gens_q(user), pk=pk)
                    .values('id', 'status', 'progress', 'image')
                    .first()
                )
                if row is None:
                    yield _sse({'progress': progress, 'status': 'error'})
                    break
            else:
                # Достигнут таймаут — отдаём финальное событие, чтобы фронт отцепился.
                yield _sse({'progress': int(row.get('progress') or 0) if row else 0, 'status': 'timeout'})

        resp = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
        resp['Cache-Control'] = 'no-cache'
        resp['X-Accel-Buffering'] = 'no'
        return resp
