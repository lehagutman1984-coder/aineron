"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 21):
регрессионный тест — JWT (Telegram Mini App) больше не обходит shadow-ban.

Запуск: python manage.py test api.tests_jwt_shadow_ban
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def _jwt_client_for(user):
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
    return client


class JWTShadowBanTests(APITestCase):
    """/api/v1/keys/ — явно включает JWT в authentication_classes (keys.py,
    _SESSION_OR_JWT_AUTH), в отличие от /api/v1/usage/ (только Session+APIKey,
    JWT там не принят вообще — не годится для проверки именно JWT-пути)."""

    def test_shadow_banned_user_jwt_rejected(self):
        user = User.objects.create_user(
            username='banned@t.ru', email='banned@t.ru', password='x', email_verified=True,
        )
        user.shadow_banned = True
        user.save(update_fields=['shadow_banned'])
        client = _jwt_client_for(user)
        resp = client.get('/api/v1/keys/')
        self.assertIn(resp.status_code, (401, 403))

    def test_shadow_banned_but_real_payer_jwt_allowed(self):
        # has_made_real_payment() освобождает от бана по тому же правилу,
        # что и APIKeyAuthentication (не наказывать реально платившего).
        from users.models import PaymentHistory
        user = User.objects.create_user(
            username='payer@t.ru', email='payer@t.ru', password='x', email_verified=True,
        )
        user.shadow_banned = True
        user.save(update_fields=['shadow_banned'])
        PaymentHistory.objects.create(
            user=user, payment_type='pages', payment_method='test',
            invoice_id='t1', amount='1.00', amount_kopecks=100, status='success',
        )
        client = _jwt_client_for(user)
        resp = client.get('/api/v1/keys/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_normal_user_jwt_still_works(self):
        user = User.objects.create_user(
            username='normal@t.ru', email='normal@t.ru', password='x', email_verified=True,
        )
        client = _jwt_client_for(user)
        resp = client.get('/api/v1/keys/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
