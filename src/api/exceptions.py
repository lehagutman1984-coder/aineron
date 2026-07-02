from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def openai_exception_handler(exc, context):
    """Возвращает ошибки в формате OpenAI: {"error": {"message", "type", "code"}}."""
    response = exception_handler(exc, context)

    if response is None:
        return None

    error_data = response.data

    # Если уже в нашем формате (из AuthenticationFailed с dict)
    if isinstance(error_data, dict) and 'error' in error_data:
        return response

    # Нормализуем DRF-ответ в OpenAI-формат
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        error_type = 'authentication_error'
        code = 'invalid_api_key'
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        error_type = 'permission_error'
        code = 'insufficient_permissions'
    elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        error_type = 'requests'
        code = 'rate_limit_exceeded'
    elif response.status_code == status.HTTP_402_PAYMENT_REQUIRED:
        error_type = 'insufficient_quota'
        code = 'insufficient_quota'
    else:
        error_type = 'invalid_request_error'
        code = 'invalid_request'

    message = _extract_message(error_data)
    response.data = {
        'error': {
            'message': message,
            'type': error_type,
            'code': code,
        }
    }
    return response


def _extract_message(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return '; '.join(str(x) for x in data)
    if isinstance(data, dict):
        for key in ('detail', 'message', 'non_field_errors'):
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    return '; '.join(str(x) for x in val)
                return str(val)
        return '; '.join(f'{k}: {v}' for k, v in data.items())
    return str(data)


class InsufficientStarsError(Exception):
    """Недостаточно средств на балансе для выполнения запроса (имя класса — API-контракт, не переименовывать)."""
    pass
