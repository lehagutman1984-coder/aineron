"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 3):
регрессионные тесты на SSRF-защиту вебхуков — создание отклоняет приватные/
локальные адреса, доставка (deliver_webhook) не ходит на них даже если
запись в БД уже существует (DNS rebinding / прямое редактирование).

Запуск: python manage.py test api.tests_webhooks_ssrf
"""
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from api.models import Webhook

User = get_user_model()


class WebhookCreateSSRFTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wh', email='wh@test.ru', password='x', email_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_loopback_https_url_rejected(self):
        resp = self.client.post('/api/v1/webhooks/', {
            'url': 'https://127.0.0.1/hook', 'events': ['batch.completed'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error']['code'], 'unsafe_url')
        self.assertFalse(Webhook.objects.filter(user=self.user).exists())

    def test_localhost_hostname_rejected(self):
        resp = self.client.post('/api/v1/webhooks/', {
            'url': 'https://localhost:8000/hook', 'events': ['batch.completed'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Webhook.objects.filter(user=self.user).exists())

    def test_plain_http_rejected_even_if_host_is_public(self):
        resp = self.client.post('/api/v1/webhooks/', {
            'url': 'http://example.com/hook', 'events': ['batch.completed'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_https_url_accepted(self):
        with mock.patch('api.views.webhooks.is_safe_url', return_value=True):
            resp = self.client.post('/api/v1/webhooks/', {
                'url': 'https://example.com/hook', 'events': ['batch.completed'],
            }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Webhook.objects.filter(user=self.user, url='https://example.com/hook').exists())


class DeliverWebhookSSRFTests(APITestCase):
    """deliver_webhook перепроверяет is_safe_url на доставке (DNS rebinding)."""

    def setUp(self):
        self.user = User.objects.create_user(username='wh2', email='wh2@test.ru', password='x')
        # Запись создаётся напрямую через ORM, в обход view-level проверки —
        # имитирует DNS rebinding (адрес стал приватным ПОСЛЕ создания).
        self.webhook = Webhook.objects.create(
            user=self.user, url='https://rebind.example.invalid/hook', events=['batch.completed'],
        )

    def test_unsafe_url_at_delivery_time_is_not_requested(self):
        from api.tasks import deliver_webhook
        # is_safe_url импортируется ВНУТРИ deliver_webhook (локальный import),
        # поэтому патчим источник (studio.security), не api.tasks — локальный
        # from-import резолвится заново на каждый вызов и увидит патч.
        with mock.patch('studio.security.is_safe_url', return_value=False), \
             mock.patch('api.tasks.requests.post') as mock_post:
            deliver_webhook(self.webhook.pk, 'batch.completed', {'x': 1})
        mock_post.assert_not_called()

    def test_safe_url_at_delivery_time_is_requested_without_redirects(self):
        from api.tasks import deliver_webhook
        mock_resp = mock.Mock(status_code=200)
        mock_resp.raise_for_status.return_value = None
        with mock.patch('studio.security.is_safe_url', return_value=True), \
             mock.patch('api.tasks.requests.post', return_value=mock_resp) as mock_post:
            deliver_webhook(self.webhook.pk, 'batch.completed', {'x': 1})
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs.get('allow_redirects'), False)
