import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample
from api.models import APIKey

logger = logging.getLogger(__name__)


class APIKeyListCreateView(APIView):
    """GET /api/v1/keys/ — список ключей; POST — создать новый."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Список API-ключей',
        tags=['Keys'],
    )
    def get(self, request):
        keys = APIKey.objects.filter(user=request.user, is_active=True).order_by('-created_at')
        data = [
            {
                'id': k.pk,
                'name': k.name,
                'prefix': f'ak_{k.key_prefix}...',
                'is_active': k.is_active,
                'scopes': k.scopes or [],
                'created_at': k.created_at.isoformat(),
                'last_used_at': k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]
        return Response(data)

    @extend_schema(
        summary='Создать API-ключ',
        tags=['Keys'],
        examples=[
            OpenApiExample('Создать ключ', value={'name': 'My App'}, request_only=True),
        ],
    )
    def post(self, request):
        name = request.data.get('name', '').strip()
        if not name:
            return Response(
                {'error': {'message': 'name is required', 'type': 'invalid_request_error', 'code': 'missing_name'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(name) > 100:
            return Response(
                {'error': {'message': 'name must be ≤ 100 characters', 'type': 'invalid_request_error', 'code': 'invalid_name'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if APIKey.objects.filter(user=request.user, is_active=True).count() >= 10:
            return Response(
                {'error': {'message': 'Maximum 10 active API keys per user', 'type': 'invalid_request_error', 'code': 'key_limit_reached'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Дополнительные скоупы — выключены по умолчанию, включаются явно
        ALLOWED_SCOPES = {'sandboxes'}
        scopes = request.data.get('scopes', [])
        if not isinstance(scopes, list) or not set(map(str, scopes)) <= ALLOWED_SCOPES:
            return Response(
                {'error': {'message': f'scopes must be a subset of {sorted(ALLOWED_SCOPES)}', 'type': 'invalid_request_error', 'code': 'invalid_scopes'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key, plaintext = APIKey.generate(request.user, name, scopes=[str(s) for s in scopes])
        logger.info(f'[API] Создан ключ {api_key.pk} для {request.user.email}')
        return Response(
            {
                'id': api_key.pk,
                'name': api_key.name,
                'key': plaintext,  # показывается только один раз
                'prefix': f'ak_{api_key.key_prefix}...',
                'scopes': api_key.scopes or [],
                'created_at': api_key.created_at.isoformat(),
                'warning': 'Save this key now — it will not be shown again.',
            },
            status=status.HTTP_201_CREATED,
        )


class APIKeyDeleteView(APIView):
    """DELETE /api/v1/keys/{pk}/ — отозвать ключ."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Отозвать API-ключ', tags=['Keys'])
    def delete(self, request, pk):
        try:
            key = APIKey.objects.get(pk=pk, user=request.user, is_active=True)
        except APIKey.DoesNotExist:
            return Response(
                {'error': {'message': 'API key not found', 'type': 'invalid_request_error', 'code': 'not_found'}},
                status=status.HTTP_404_NOT_FOUND,
            )
        key.is_active = False
        key.save(update_fields=['is_active'])
        logger.info(f'[API] Отозван ключ {pk} пользователя {request.user.email}')
        return Response({'deleted': True, 'id': pk})
