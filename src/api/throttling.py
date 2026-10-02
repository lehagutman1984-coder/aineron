import ipaddress

from rest_framework.throttling import SimpleRateThrottle


def is_internal_service_request(request) -> bool:
    """Запрос от внутреннего сервиса (SSR Next.js, Celery, бот), а не от внешнего клиента.

    Внешний трафик идёт через nginx, который ВСЕГДА добавляет X-Forwarded-For и X-Real-IP;
    серверные запросы фронтенда (DJANGO_INTERNAL_URL=http://web:8000) идут напрямую, без этих
    заголовков, с приватного адреса docker-сети. Подделать приватный REMOTE_ADDR из интернета
    нельзя (TCP-соединение).

    Зачем: все SSR-страницы (каталог, блог, юр. документы, публичные пространства) берут данные
    у Django ОДНИМ адресом - контейнера фронтенда, и анонимный лимит по IP (120/мин) становился
    общим для ВСЕХ посетителей сайта. При всплеске трафика или обходе роботом API отвечал 429,
    serverFetch возвращал null, и страницы моделей отдавали 404 (воспроизведено на проде
    2026-09-27: ~40 быстрых запросов к /models/<slug> подряд, затем 404)."""
    meta = request.META
    if meta.get('HTTP_X_FORWARDED_FOR') or meta.get('HTTP_X_REAL_IP'):
        return False
    try:
        return ipaddress.ip_address(meta.get('REMOTE_ADDR', '')).is_private
    except ValueError:
        return False


class APIKeyRateThrottle(SimpleRateThrottle):
    """Rate limit per API key (fallback: per user)."""
    scope = 'api_key'
    cache_format = 'throttle_api_key_%(ident)s'

    def allow_request(self, request, view):
        if is_internal_service_request(request):
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'api_key', None)
        if api_key:
            ident = f'key_{api_key.pk}'
        elif request.user and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'ident': ident}


class SandboxCreateThrottle(APIKeyRateThrottle):
    """Создание песочниц: 10/мин на ключ/пользователя."""
    scope = 'sandbox_create'
    cache_format = 'throttle_sandbox_create_%(ident)s'


class SandboxExecThrottle(APIKeyRateThrottle):
    """Exec в песочницах: 30/мин на ключ/пользователя."""
    scope = 'sandbox_exec'
    cache_format = 'throttle_sandbox_exec_%(ident)s'


class GenerationLikeThrottle(APIKeyRateThrottle):
    """2026-10-02 (аудит безопасности, LOW): лайк публичной генерации был
    анонимным, без выделенного лимита (жил только на общем 120/мин
    api_key-throttle по IP) - 20/мин специально для этого low-value действия
    ощутимо снижает скорость накрутки, не трогая общий лимит остального API."""
    scope = 'generation_like'
    cache_format = 'throttle_generation_like_%(ident)s'


class PublicSpaceThrottle(SimpleRateThrottle):
    """60 req/min per IP для анонимов, 300/min для авторизованных."""
    scope = 'public_space'
    cache_format = 'throttle_public_space_%(ident)s'

    def allow_request(self, request, view):
        if is_internal_service_request(request):
            return True
        # Ставка зависит от того, авторизован ли пользователь, - известно только здесь.
        # Раньше get_rate() читал self.request, которого в __init__ ещё нет: AttributeError,
        # и ЛЮБОЙ запрос к /api/v1/public/spaces/<slug>/ отвечал 500 (на обоих инстансах).
        authenticated = bool(getattr(request, 'user', None) and request.user.is_authenticated)
        self.rate = '300/min' if authenticated else '60/min'
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'ident': ident}

    def get_rate(self):
        return '60/min'
