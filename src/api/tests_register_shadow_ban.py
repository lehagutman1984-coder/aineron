"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт MEDIUM
"RegisterView не ставит shadow-ban по IP"): регрессионный тест — DRF-путь
регистрации (/api/v1/auth/register/, реальный путь фронта) теперь ставит
shadow_banned=True при повторной регистрации с уже использованного IP, как и
legacy-путь.

Запуск: python manage.py test api.tests_register_shadow_ban
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from users.models import UserIPAddress

User = get_user_model()

REMOTE_ADDR = '203.0.113.5'  # TEST-NET-3, документационный диапазон


class RegisterShadowBanTests(APITestCase):
    def test_second_registration_from_same_ip_gets_shadow_banned(self):
        resp1 = self.client.post('/api/v1/auth/register/', {
            'email': 'first@t.ru', 'password': 'supersecret123',
        }, format='json', REMOTE_ADDR=REMOTE_ADDR)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        first = User.objects.get(email='first@t.ru')
        self.assertFalse(first.shadow_banned)

        self.client.logout()
        resp2 = self.client.post('/api/v1/auth/register/', {
            'email': 'second@t.ru', 'password': 'supersecret123',
        }, format='json', REMOTE_ADDR=REMOTE_ADDR)
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        second = User.objects.get(email='second@t.ru')
        self.assertTrue(second.shadow_banned)

    def test_first_registration_from_fresh_ip_not_banned(self):
        resp = self.client.post('/api/v1/auth/register/', {
            'email': 'alone@t.ru', 'password': 'supersecret123',
        }, format='json', REMOTE_ADDR='203.0.113.9')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='alone@t.ru')
        self.assertFalse(user.shadow_banned)
        self.assertTrue(UserIPAddress.objects.filter(user=user, ip_address='203.0.113.9').exists())
