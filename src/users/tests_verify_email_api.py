"""
Регресс на DRF-подтверждение email (/api/v1/auth/verify-email/, change-email).
Запуск: python manage.py test users.tests_verify_email_api
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from unittest import mock

User = get_user_model()


class VerifyEmailApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.victim = User.objects.create_user(
            username='v', email='v@t.ru', password='x' * 10,
            email_verification_code='111111',
        )
        self.me = User.objects.create_user(
            username='me', email='me@t.ru', password='x' * 10,
            email_verification_code='222222',
        )
        self.c = APIClient()

    def test_anonymous_cannot_verify(self):
        r = self.c.post('/api/v1/auth/verify-email/', {'code': '111111'}, format='json')
        self.assertIn(r.status_code, (401, 403))
        self.victim.refresh_from_db()
        self.assertFalse(self.victim.email_verified)

    def test_other_users_code_does_not_work(self):
        self.c.force_authenticate(self.me)
        r = self.c.post('/api/v1/auth/verify-email/', {'code': '111111'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.victim.refresh_from_db()
        self.assertFalse(self.victim.email_verified)

    def test_own_code_works(self):
        self.c.force_authenticate(self.me)
        r = self.c.post('/api/v1/auth/verify-email/', {'code': '222222'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.me.refresh_from_db()
        self.assertTrue(self.me.email_verified)

    def test_attempts_are_limited(self):
        self.c.force_authenticate(self.me)
        for _ in range(5):
            self.c.post('/api/v1/auth/verify-email/', {'code': '000000'}, format='json')
        r = self.c.post('/api/v1/auth/verify-email/', {'code': '222222'}, format='json')
        self.assertEqual(r.status_code, 429)
        self.me.refresh_from_db()
        self.assertFalse(self.me.email_verified)

    def test_change_email_resends_code(self):
        self.c.force_authenticate(self.me)
        with mock.patch('api.views.auth.send_verification_email', return_value=True) as send:
            r = self.c.post('/api/v1/auth/change-email/', {'email': 'new@t.ru'}, format='json')
        self.assertEqual(r.status_code, 200)
        send.assert_called_once()
        self.me.refresh_from_db()
        self.assertEqual(self.me.email, 'new@t.ru')

    def test_change_email_rejects_taken_and_invalid(self):
        self.c.force_authenticate(self.me)
        r = self.c.post('/api/v1/auth/change-email/', {'email': 'v@t.ru'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post('/api/v1/auth/change-email/', {'email': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_change_email_blocked_when_verified(self):
        self.me.verify_email()
        self.c.force_authenticate(self.me)
        r = self.c.post('/api/v1/auth/change-email/', {'email': 'new@t.ru'}, format='json')
        self.assertEqual(r.status_code, 400)
