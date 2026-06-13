from rest_framework.throttling import SimpleRateThrottle


class APIKeyRateThrottle(SimpleRateThrottle):
    """Rate limit per API key (fallback: per user)."""
    scope = 'api_key'
    cache_format = 'throttle_api_key_%(ident)s'

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'api_key', None)
        if api_key:
            ident = f'key_{api_key.pk}'
        elif request.user and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'ident': ident}
