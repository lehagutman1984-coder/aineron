from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication без проверки CSRF — для DRF API с CORS-защитой."""
    def enforce_csrf(self, request):
        pass


class APIKeyAuthentication(BaseAuthentication):
    """Bearer ak_... аутентификация для /api/v1/ эндпоинтов."""

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer ak_'):
            return None  # передаём другим бэкендам (SessionAuthentication)

        raw_key = auth_header[len('Bearer '):]

        from api.models import APIKey
        api_key = APIKey.authenticate(raw_key)
        if api_key is None:
            raise AuthenticationFailed({
                'error': {
                    'message': 'Invalid API key.',
                    'type': 'invalid_request_error',
                    'code': 'invalid_api_key',
                }
            })

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])

        request.api_key = api_key
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return 'Bearer realm="aineron.ru API"'
