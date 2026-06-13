"""
POST /api/v1/embeddings — OpenAI-совместимые эмбеддинги.
"""
import logging
import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.tasks import get_laozhang_client
from api.services.billing import charge_for_tokens

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small'


def _resolve_embedding_model(model_id: str):
    """Поиск модели эмбеддингов в БД или возврат дефолтной."""
    try:
        return NeuralNetwork.objects.get(model_name=model_id, is_active=True)
    except NeuralNetwork.DoesNotExist:
        return None


class EmbeddingsView(APIView):
    """POST /api/v1/embeddings"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Создать эмбеддинги (OpenAI-совместимый)',
        tags=['Embeddings'],
        description='Принимает OpenAI-формат. `input` — строка или массив строк.',
    )
    def post(self, request):
        data = request.data
        model_id = data.get('model', DEFAULT_EMBEDDING_MODEL)
        input_data = data.get('input')
        encoding_format = data.get('encoding_format', 'float')

        if not input_data:
            return Response(
                {'error': {'message': "'input' is required", 'type': 'invalid_request_error', 'code': 'missing_input'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(input_data, str):
            inputs = [input_data]
        elif isinstance(input_data, list):
            inputs = input_data
        else:
            return Response(
                {'error': {'message': "'input' must be a string or array", 'type': 'invalid_request_error', 'code': 'invalid_input'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        api_key = getattr(request, 'api_key', None)

        if user.pages_count <= 0:
            return Response(
                {'error': {'message': f'Insufficient balance: {user.pages_count} stars.', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_laozhang_client()
        try:
            response_obj = client.embeddings.create(
                model=model_id,
                input=inputs,
                encoding_format=encoding_format,
            )
        except Exception as e:
            logger.error(f'[API] Ошибка эмбеддингов для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Биллинг по токенам
        usage_obj = getattr(response_obj, 'usage', None)
        total_tokens = usage_obj.total_tokens if usage_obj else len(' '.join(inputs)) // 4
        usage = {'prompt_tokens': total_tokens, 'completion_tokens': 0, 'total_tokens': total_tokens}

        # Для эмбеддингов ищем сеть или биллим по минимуму
        network = _resolve_embedding_model(model_id)
        if network:
            try:
                charge_for_tokens(user, network, usage, api_key=api_key)
            except Exception:
                pass  # Не блокируем ответ из-за ошибки биллинга

        result = {
            'object': 'list',
            'data': [
                {
                    'object': 'embedding',
                    'index': i,
                    'embedding': item.embedding,
                }
                for i, item in enumerate(response_obj.data)
            ],
            'model': model_id,
            'usage': {
                'prompt_tokens': total_tokens,
                'total_tokens': total_tokens,
            },
        }
        return Response(result)
