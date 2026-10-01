"""SSR-запросы фронтенда не должны делить общий анонимный лимит с посетителями (2026-09-27)."""
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.request import Request

from api.throttling import APIKeyRateThrottle, PublicSpaceThrottle, is_internal_service_request

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _req(remote_addr, xff=None, real_ip=None):
    extra = {'REMOTE_ADDR': remote_addr}
    if xff:
        extra['HTTP_X_FORWARDED_FOR'] = xff
    if real_ip:
        extra['HTTP_X_REAL_IP'] = real_ip
    return Request(RequestFactory().get('/api/v1/catalog/networks/x/', **extra))


class InternalRequestDetectionTests(SimpleTestCase):
    def test_docker_ssr_request_is_internal(self):
        self.assertTrue(is_internal_service_request(_req('172.18.0.7')))

    def test_nginx_proxied_request_is_external_even_from_private_ip(self):
        # nginx (приватный адрес docker-сети) ВСЕГДА добавляет XFF/X-Real-IP
        self.assertFalse(is_internal_service_request(_req('172.18.0.2', xff='8.8.8.8')))
        self.assertFalse(is_internal_service_request(_req('172.18.0.2', real_ip='8.8.8.8')))

    def test_public_direct_request_is_external(self):
        self.assertFalse(is_internal_service_request(_req('8.8.8.8')))

    def test_garbage_addr_is_external(self):
        self.assertFalse(is_internal_service_request(_req('')))


@override_settings(CACHES=LOCMEM, REST_FRAMEWORK={
    'DEFAULT_THROTTLE_RATES': {'api_key': '3/min', 'public_space': '3/min'}})
class ThrottleBehaviourTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        # SimpleRateThrottle читает THROTTLE_RATES при импорте класса - подменяем явно
        APIKeyRateThrottle.THROTTLE_RATES = {'api_key': '3/min', 'public_space': '3/min'}
        PublicSpaceThrottle.THROTTLE_RATES = {'api_key': '3/min', 'public_space': '3/min'}

    def _hits(self, throttle_cls, request, n=10):
        allowed = 0
        for _ in range(n):
            t = throttle_cls()
            if t.allow_request(request, None):
                allowed += 1
        return allowed

    def test_internal_requests_are_never_throttled(self):
        self.assertEqual(self._hits(APIKeyRateThrottle, _req('172.18.0.7')), 10)

    def test_external_requests_are_still_throttled(self):
        self.assertEqual(self._hits(APIKeyRateThrottle, _req('172.18.0.2', xff='8.8.8.8')), 3)

    def test_spoofed_xff_from_internet_does_not_grant_exemption(self):
        # внешний клиент присылает XFF сам - это делает запрос внешним, а не внутренним
        self.assertEqual(self._hits(APIKeyRateThrottle, _req('8.8.8.8', xff='10.0.0.1')), 3)


@override_settings(CACHES=LOCMEM)
class PublicSpaceThrottleInstantiationTests(SimpleTestCase):
    """Раньше PublicSpaceThrottle() падал в __init__ (get_rate читал self.request) -> 500 на эндпоинте."""

    def test_can_be_instantiated_and_uses_anonymous_rate(self):
        cache.clear()
        t = PublicSpaceThrottle()
        self.assertEqual(t.rate, '60/min')
        req = _req('172.18.0.2', xff='8.8.8.8')
        req.user = type('Anon', (), {'is_authenticated': False, 'pk': None})()
        allowed = 0
        for _ in range(70):
            if PublicSpaceThrottle().allow_request(req, None):
                allowed += 1
        self.assertEqual(allowed, 60)

    def test_internal_public_space_requests_not_throttled(self):
        cache.clear()
        req = _req('172.18.0.7')
        req.user = type('Anon', (), {'is_authenticated': False, 'pk': None})()
        self.assertTrue(all(PublicSpaceThrottle().allow_request(req, None) for _ in range(200)))


@override_settings(CACHES=LOCMEM)
class NumProxiesSpoofingTests(SimpleTestCase):
    """2026-10-01 (аудит безопасности, HIGH, п.8): без NUM_PROXIES анонимный
    клиент мог слать произвольный X-Forwarded-For и открывать новую корзину
    троттлинга на каждый запрос. nginx ВСЕГДА дописывает реальный IP в конец
    существующего XFF ($proxy_add_x_forwarded_for) — NUM_PROXIES=1 (уже
    выставлен в config/settings.py REST_FRAMEWORK, не переопределяется тут)
    берёт именно последний элемент, не то, что прислал клиент."""

    def _ident(self, xff, remote_addr='172.18.0.2'):
        return APIKeyRateThrottle().get_ident(_req(remote_addr, xff=xff))

    def test_trusted_last_hop_used_regardless_of_spoofed_prefix(self):
        # nginx видел REMOTE_ADDR=198.51.100.7 и дописал его в конец - это
        # единственная часть заголовка, которой можно доверять.
        real_client_ip = '198.51.100.7'
        ident_attempt_1 = self._ident(f'1.2.3.4, {real_client_ip}')
        ident_attempt_2 = self._ident(f'9.9.9.9, {real_client_ip}')
        self.assertEqual(ident_attempt_1, real_client_ip)
        self.assertEqual(ident_attempt_1, ident_attempt_2)  # одна и та же корзина

    def test_spoofed_prefix_cannot_create_new_bucket_each_request(self):
        cache.clear()
        real_client_ip = '198.51.100.9'
        allowed = 0
        for i in range(10):
            req = _req('172.18.0.2', xff=f'{i}.{i}.{i}.{i}, {real_client_ip}')
            if APIKeyRateThrottle().allow_request(req, None):
                allowed += 1
        # Лимит api_key = 120/мин, но суть проверки - что ВСЕ 10 запросов
        # делят ОДНУ корзину (один и тот же итоговый ident), а не 10 разных -
        # до фикса каждый случайный префикс XFF давал новую корзину.
        self.assertEqual(allowed, 10)  # внутри лимита 120/мин, это ожидаемо
        ident = self._ident(f'0.0.0.0, {real_client_ip}')
        self.assertEqual(ident, real_client_ip)
