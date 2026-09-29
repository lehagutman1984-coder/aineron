"""
Тесты смены пароля из личного кабинета (POST /api/v1/auth/change-password/).

Покрывает: успешную смену (+ сессия не разлогинивается благодаря
update_session_auth_hash), неверный текущий пароль, слабый новый пароль,
анонимный доступ запрещён.
"""
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

User = get_user_model()

# teams.middleware резолвит org_branding через cache на КАЖДОМ запросе — без
# него APIClient.post требует живой Redis (недоступен при локальном запуске
# тестов вне Docker). Тот же паттерн, что и в tests_crypto.py.
_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}


def make_user(email='security@test.ru', password='old-password-123'):
    user = User.objects.create_user(username=email.split('@')[0], email=email, password=password)
    return user


@override_settings(CACHES=_LOCMEM_CACHE)
class PasswordChangeTests(APITestCase):
    URL = '/api/v1/auth/change-password/'

    def test_requires_authentication(self):
        # SessionAuthentication (не Basic/JWT) не шлёт WWW-Authenticate, поэтому
        # DRF отвечает 403, а не 401, - тот же код, что у остальных authenticated
        # вьюх в этом файле (LoginView/MeView и т.п.), не специфика этой вьюхи.
        resp = self.client.post(self.URL, {'current_password': 'x', 'new_password': 'y' * 10}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_wrong_current_password_rejected(self):
        user = make_user()
        self.client.login(username=user.username, password='old-password-123')
        resp = self.client.post(self.URL, {
            'current_password': 'totally-wrong', 'new_password': 'new-password-456',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error']['code'], 'invalid_current_password')
        user.refresh_from_db()
        self.assertTrue(user.check_password('old-password-123'))

    def test_weak_new_password_rejected(self):
        user = make_user()
        self.client.login(username=user.username, password='old-password-123')
        resp = self.client.post(self.URL, {
            'current_password': 'old-password-123', 'new_password': '123',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error']['code'], 'weak_password')
        user.refresh_from_db()
        self.assertTrue(user.check_password('old-password-123'))

    def test_successful_change_updates_password_and_keeps_session(self):
        user = make_user()
        self.client.login(username=user.username, password='old-password-123')
        resp = self.client.post(self.URL, {
            'current_password': 'old-password-123', 'new_password': 'brand-new-password-789',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['ok'])

        user.refresh_from_db()
        self.assertTrue(user.check_password('brand-new-password-789'))
        self.assertFalse(user.check_password('old-password-123'))

        # update_session_auth_hash должен был отработать - сессия всё ещё валидна,
        # следующий authenticated-запрос этим же клиентом не должен требовать re-login.
        me_resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me_resp.status_code, 200)

    def test_missing_fields_rejected(self):
        user = make_user()
        self.client.login(username=user.username, password='old-password-123')
        resp = self.client.post(self.URL, {'current_password': 'old-password-123'}, format='json')
        self.assertEqual(resp.status_code, 400)
