"""
Сервис доставки webhook-событий с HMAC-подписью и повторными попытками.
Доставка выполняется через Celery-таск (api/tasks.py deliver_webhook).
"""
import hashlib
import hmac
import json
import logging

logger = logging.getLogger(__name__)

TIMEOUT = 10


def build_signed_body(secret: str, event_type: str, payload: dict):
    """Возвращает (body_bytes, signature_header_value)."""
    body = json.dumps({'event': event_type, 'data': payload}, ensure_ascii=False).encode()
    sig = hmac.new(secret.encode(), body, digestmod=hashlib.sha256).hexdigest()
    return body, f'sha256={sig}'


def dispatch_event(event_type: str, payload: dict, user=None, organization=None):
    """
    Ставит доставку каждого подходящего webhook в очередь Celery.
    """
    from api.models import Webhook
    from api.tasks import deliver_webhook

    qs = Webhook.objects.filter(is_active=True)
    if user:
        qs = qs.filter(user=user)
    elif organization:
        qs = qs.filter(organization=organization)

    for webhook in qs:
        if event_type not in (webhook.events or []):
            continue
        deliver_webhook.apply_async(
            args=[webhook.pk, event_type, payload],
            countdown=0,
        )
