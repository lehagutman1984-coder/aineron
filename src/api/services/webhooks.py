"""
Сервис доставки webhook-событий с HMAC-подписью и повторными попытками.
"""
import hashlib
import hmac
import json
import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [10, 60, 300]  # секунды между попытками
TIMEOUT = 10


def _deliver(webhook, event_type: str, payload: dict, attempt: int = 0):
    """Доставка одного события. Вызывается из фонового потока."""
    from api.models import Webhook

    body = json.dumps({'event': event_type, 'data': payload}, ensure_ascii=False).encode()
    signature = hmac.new(webhook.secret.encode(), body, digestmod=hashlib.sha256).hexdigest()
    headers = {
        'Content-Type': 'application/json',
        'X-Aineron-Signature': f'sha256={signature}',
        'X-Aineron-Event': event_type,
        'User-Agent': 'aineron.ru/webhooks/1.0',
    }

    try:
        resp = requests.post(webhook.url, data=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        logger.info(f'[Webhook] Delivered {event_type} to {webhook.url}, status={resp.status_code}')
        Webhook.objects.filter(pk=webhook.pk).update(last_triggered_at=__import__('django.utils.timezone', fromlist=['timezone']).timezone.now())
    except Exception as e:
        logger.warning(f'[Webhook] Attempt {attempt + 1} failed for {webhook.url}: {e}')
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAYS[attempt]
            time.sleep(delay)
            _deliver(webhook, event_type, payload, attempt + 1)
        else:
            logger.error(f'[Webhook] All {MAX_RETRIES} attempts failed for {webhook.url}')


def dispatch_event(event_type: str, payload: dict, user=None, organization=None):
    """
    Отправляет событие всем подходящим активным вебхукам.
    Каждый вебхук обрабатывается в отдельном фоновом потоке.
    """
    from api.models import Webhook

    qs = Webhook.objects.filter(is_active=True)
    if user:
        qs = qs.filter(user=user)
    elif organization:
        qs = qs.filter(organization=organization)

    for webhook in qs:
        if event_type not in (webhook.events or []):
            continue
        t = threading.Thread(target=_deliver, args=(webhook, event_type, payload), daemon=True)
        t.start()
