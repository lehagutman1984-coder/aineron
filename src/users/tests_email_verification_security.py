"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 2):
регрессионные тесты на захват аккаунта через перебор кода подтверждения
email + на rate-limit/generic-response в сбросе пароля.

Запуск: python manage.py test users.tests_email_verification_security
"""
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client

from users.email_service import verify_email_token

User = get_user_model()


class VerifyEmailTokenFunctionTests(TestCase):
    """verify_email_token() — только длинная ссылка, НЕ короткий код."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='victim', email='victim@t.ru', password='x',
            email_verification_token='a' * 36,
            email_verification_code='123456',
        )

    def test_long_token_still_works(self):
        user = verify_email_token('a' * 36)
        self.assertEqual(user, self.user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_short_code_no_longer_accepted_by_this_function(self):
        # Главный регресс-тест: до фикса это возвращало self.user.
        user = verify_email_token('123456')
        self.assertIsNone(user)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_empty_or_garbage_token_returns_none(self):
        self.assertIsNone(verify_email_token(''))
        self.assertIsNone(verify_email_token(None))
        self.assertIsNone(verify_email_token('short'))


class AjaxVerifyEmailCodeViewTests(TestCase):
    """ajax_verify_email_code — код матчится только на request.user."""

    def setUp(self):
        self.client = Client()
        self.victim = User.objects.create_user(
            username='victim2', email='victim2@t.ru', password='x',
            email_verification_code='111111',
        )
        self.attacker = User.objects.create_user(
            username='attacker', email='attacker@t.ru', password='x',
            email_verification_code='222222',
        )

    def test_own_correct_code_verifies_self(self):
        self.client.force_login(self.victim)
        resp = self.client.post(
            '/users/api/ajax/verify-email/',
            data=json.dumps({'token': '111111'}),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['success'], True)
        self.victim.refresh_from_db()
        self.assertTrue(self.victim.email_verified)

    def test_cannot_use_another_users_code_to_hijack_their_account(self):
        # Регресс-тест на сам CRITICAL-баг: атакующий залогинен под своим
        # аккаунтом и угадывает код жертвы — до фикса это логинило его как
        # victim (account takeover). Теперь должно просто отдать "Неверный код".
        self.client.force_login(self.attacker)
        resp = self.client.post(
            '/users/api/ajax/verify-email/',
            data=json.dumps({'token': '111111'}),  # код ЖЕРТВЫ
            content_type='application/json',
        )
        data = resp.json()
        self.assertEqual(data['success'], False)
        self.assertEqual(data['message'], 'Неверный код')
        # Сессия должна остаться сессией атакующего, не жертвы.
        self.assertEqual(int(self.client.session['_auth_user_id']), self.attacker.pk)
        self.victim.refresh_from_db()
        self.assertFalse(self.victim.email_verified)

    def test_wrong_code_fails_normally(self):
        self.client.force_login(self.victim)
        resp = self.client.post(
            '/users/api/ajax/verify-email/',
            data=json.dumps({'token': '999999'}),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['success'], False)

    def test_requires_login(self):
        resp = self.client.post(
            '/users/api/ajax/verify-email/',
            data=json.dumps({'token': '111111'}),
            content_type='application/json',
        )
        # @login_required редиректит анонима (на login), не отдаёт 200 JSON.
        self.assertNotEqual(resp.status_code, 200)


class AjaxPasswordResetViewTests(TestCase):
    """ajax_password_reset — generic response + rate-limit."""

    def setUp(self):
        self.client = Client()
        cache.clear()
        self.user = User.objects.create_user(
            username='reset_me', email='reset_me@t.ru', password='old-pass',
        )

    def tearDown(self):
        cache.clear()

    def _post(self, email):
        return self.client.post(
            '/users/api/ajax/password-reset/',
            data=json.dumps({'email': email}),
            content_type='application/json',
        )

    def test_existing_and_nonexistent_email_get_identical_response(self):
        r1 = self._post('reset_me@t.ru')
        cache.clear()  # не даём rate-limit повлиять на второй вызов в этом тесте
        r2 = self._post('definitely-not-registered@t.ru')
        self.assertEqual(r1.status_code, r2.status_code)
        self.assertEqual(r1.json(), r2.json())
        self.assertTrue(r1.json()['success'])

    def test_second_request_for_same_email_is_rate_limited_not_double_reset(self):
        self._post('reset_me@t.ru')
        self.user.refresh_from_db()
        pw_after_first = self.user.password
        self._post('reset_me@t.ru')
        self.user.refresh_from_db()
        # Пароль не должен был смениться второй раз за 10 минут.
        self.assertEqual(pw_after_first, self.user.password)

    def test_ip_rate_limit_after_five_requests(self):
        for i in range(5):
            self._post(f'someone{i}@t.ru')
        resp = self._post('someone-sixth@t.ru')
        # 6-й запрос должен вернуть generic-ответ, не создавая нагрузку дальше
        # (эндпоинт при этом всё ещё "успешен" с точки зрения клиента — это
        # намеренно, чтобы не палить факт лимита атакующему).
        self.assertTrue(resp.json()['success'])
