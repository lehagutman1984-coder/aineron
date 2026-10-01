"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 14):
регрессионные тесты — Bearer API-ключ больше не может управлять ключами
(эскалация скоупа) и Telegram-привязкой; сессия продолжает работать.

Запуск: python manage.py test api.tests_key_management_auth_scope
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from api.models import APIKey

User = get_user_model()


class KeyManagementAuthScopeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='keyowner', email='keyowner@test.ru', password='x', email_verified=True,
        )
        self.existing_key, self.raw_key = APIKey.generate(self.user, 'leaked-key')

    def test_leaked_api_key_cannot_list_keys(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.raw_key}')
        resp = self.client.get('/api/v1/keys/')
        self.assertIn(resp.status_code, (401, 403))

    def test_leaked_api_key_cannot_create_new_key(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.raw_key}')
        resp = self.client.post('/api/v1/keys/', {'name': 'escalated', 'scopes': ['sandboxes']}, format='json')
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(APIKey.objects.filter(user=self.user).count(), 1)  # только исходный

    def test_leaked_api_key_cannot_delete_keys(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.raw_key}')
        resp = self.client.delete(f'/api/v1/keys/{self.existing_key.pk}/')
        self.assertIn(resp.status_code, (401, 403))
        self.existing_key.refresh_from_db()
        self.assertTrue(self.existing_key.is_active)

    def test_session_can_still_manage_keys(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/keys/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.post('/api/v1/keys/', {'name': 'from-session'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_leaked_api_key_cannot_create_telegram_link_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.raw_key}')
        resp = self.client.post('/api/v1/telegram/link-token/')
        self.assertIn(resp.status_code, (401, 403))

    def test_session_can_still_create_telegram_link_token(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/telegram/link-token/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('link', resp.data)
