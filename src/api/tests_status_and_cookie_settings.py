"""
2026-10-02 (аудит безопасности, LOW):
- APIStatusView раньше отдавал str(e) наружу на публичном (AllowAny) эндпоинте
  при сбое проверки БД/кэша/апстрима.
- SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE/SECURE_PROXY_SSL_HEADER не были
  выставлены вовсе.
"""
from unittest import mock

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient


class APIStatusLeakTests(TestCase):
    def test_database_error_does_not_leak_exception_text(self):
        secret_looking_error = RuntimeError('connection to host "internal-db-7.private" failed: password authentication failed for user "neiro_user"')
        with mock.patch('django.db.connection.ensure_connection', side_effect=secret_looking_error):
            resp = APIClient().get('/api/v1/status/')
        self.assertEqual(resp.status_code, 200)
        body_text = resp.content.decode()
        self.assertNotIn('internal-db-7.private', body_text)
        self.assertNotIn('neiro_user', body_text)
        self.assertEqual(resp.json()['checks']['database']['error'], 'unavailable')
        self.assertEqual(resp.json()['status'], 'degraded')

    def test_healthy_status_unaffected(self):
        resp = APIClient().get('/api/v1/status/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['checks']['database']['status'], 'operational')


class CookieSecuritySettingsTests(TestCase):
    """Значения зависят от DEBUG - в тестовом окружении DEBUG обычно 0/False
    (прод-подобный дефолт settings.py), проверяем именно это сочетание."""

    def test_secure_proxy_ssl_header_set(self):
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_cookie_secure_flags_follow_debug(self):
        self.assertEqual(settings.SESSION_COOKIE_SECURE, not settings.DEBUG)
        self.assertEqual(settings.CSRF_COOKIE_SECURE, not settings.DEBUG)
