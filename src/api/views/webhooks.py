"""
GET/POST /api/v1/webhooks/ — управление webhook-подписками.
DELETE   /api/v1/webhooks/{id}/
POST     /api/v1/webhooks/{id}/test/
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from api.models import Webhook, AuditLog
from api.services.webhooks import dispatch_event


def _ip(request):
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')


class WebhookListCreateView(APIView):
    """GET/POST /api/v1/webhooks/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Список webhooks', tags=['Webhooks'])
    def get(self, request):
        qs = Webhook.objects.filter(user=request.user)
        data = [_serialize(w) for w in qs]
        return Response(data)

    @extend_schema(summary='Создать webhook', tags=['Webhooks'])
    def post(self, request):
        url = request.data.get('url', '').strip()
        events = request.data.get('events', [])
        if not url:
            return Response({'error': {'message': "'url' is required", 'type': 'invalid_request_error', 'code': 'missing_url'}}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(events, list) or not events:
            return Response({'error': {'message': "'events' must be a non-empty list", 'type': 'invalid_request_error', 'code': 'invalid_events'}}, status=status.HTTP_400_BAD_REQUEST)

        valid_events = {e[0] for e in Webhook.EVENTS}
        invalid = [e for e in events if e not in valid_events]
        if invalid:
            return Response({'error': {'message': f'Unknown events: {invalid}', 'type': 'invalid_request_error', 'code': 'invalid_events'}}, status=status.HTTP_400_BAD_REQUEST)

        webhook = Webhook.objects.create(user=request.user, url=url, events=events)
        AuditLog.log(request.user, AuditLog.Action.WEBHOOK_CREATED, 'webhook', webhook.pk, ip_address=_ip(request))
        return Response(_serialize(webhook, show_secret=True), status=status.HTTP_201_CREATED)


class WebhookDetailView(APIView):
    """DELETE /api/v1/webhooks/{id}/"""
    permission_classes = [IsAuthenticated]

    def _get_webhook(self, request, pk):
        try:
            return Webhook.objects.get(pk=pk, user=request.user)
        except Webhook.DoesNotExist:
            return None

    @extend_schema(summary='Удалить webhook', tags=['Webhooks'])
    def delete(self, request, pk):
        webhook = self._get_webhook(request, pk)
        if not webhook:
            return Response({'error': {'message': 'Webhook not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)
        AuditLog.log(request.user, AuditLog.Action.WEBHOOK_DELETED, 'webhook', webhook.pk, metadata={'url': webhook.url}, ip_address=_ip(request))
        webhook.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookTestView(APIView):
    """POST /api/v1/webhooks/{id}/test/ — отправить тестовое событие."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Тестовый запрос webhook', tags=['Webhooks'])
    def post(self, request, pk):
        try:
            webhook = Webhook.objects.get(pk=pk, user=request.user)
        except Webhook.DoesNotExist:
            return Response({'error': {'message': 'Webhook not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)

        event = (webhook.events or ['batch.completed'])[0]
        dispatch_event(event, {'test': True, 'webhook_id': webhook.pk}, user=request.user)
        return Response({'ok': True, 'event': event})


def _serialize(webhook: Webhook, show_secret: bool = False) -> dict:
    d = {
        'id': webhook.pk,
        'url': webhook.url,
        'events': webhook.events,
        'is_active': webhook.is_active,
        'created_at': webhook.created_at.isoformat(),
        'last_triggered_at': webhook.last_triggered_at.isoformat() if webhook.last_triggered_at else None,
    }
    if show_secret:
        d['secret'] = webhook.secret
    return d
