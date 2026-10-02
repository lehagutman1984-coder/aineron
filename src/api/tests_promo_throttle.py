"""
2026-10-02 (аудит безопасности, LOW): ApplyPromoView/PromoCheckView не имели
отдельного троттла на перебор коротких человекочитаемых промокодов (жили
только на общем 120/мин). PromoCodeThrottle (20/мин, на пользователя) закрывает
это, разделяя бюджет между обоими эндпоинтами (общий scope).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import PromoCode

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM)
class PromoThrottleTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # троттлинг в кэше, не в БД - не откатывается между тестами
        self.user = User.objects.create_user(username='pthrottle', email='pthrottle@t.ru', password='x')
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        PromoCode.objects.create(code='NOPE', stars=1, usage_limit=1000)

    def _external_call(self, url, data):
        # is_internal_service_request() (api/throttling.py) пропускает запросы
        # без X-Forwarded-For/X-Real-IP с приватного REMOTE_ADDR - ровно так
        # выглядит запрос тестового клиента по умолчанию. Подставляем внешний
        # IP, как это сделал бы nginx, иначе троттл всегда байпасится.
        return self.client.post(
            url, data, format='json',
            HTTP_X_FORWARDED_FOR='203.0.113.9', REMOTE_ADDR='203.0.113.9',
        )

    def test_check_endpoint_throttled_after_burst(self):
        for _ in range(20):
            resp = self._external_call('/api/v1/billing/promo/check/', {'code': 'NOPE'})
            self.assertNotEqual(resp.status_code, 429)
        resp = self._external_call('/api/v1/billing/promo/check/', {'code': 'NOPE'})
        self.assertEqual(resp.status_code, 429)

    def test_apply_and_check_share_the_same_budget(self):
        """Один scope на оба эндпоинта - нельзя удвоить бюджет чередованием."""
        for _ in range(10):
            self._external_call('/api/v1/billing/promo/check/', {'code': 'NOPE'})
        for _ in range(10):
            self._external_call('/api/v1/billing/promo/', {'code': 'NOPE'})
        resp = self._external_call('/api/v1/billing/promo/check/', {'code': 'NOPE'})
        self.assertEqual(resp.status_code, 429)
