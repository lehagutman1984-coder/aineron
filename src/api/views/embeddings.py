"""
POST /api/v1/embeddings — OpenAI-совместимые эмбеддинги.
"""
import logging
import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.permissions import IsEmailVerified
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.providers import get_embedding_client
from decimal import Decimal

from api.exceptions import InsufficientStarsError
from api.services.billing import (
    estimate_text_tokens,
    insufficient_error_payload,
    release_reservation,
    reserve_for_request,
    settle_reservation,
)

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small'

# Бесплатная модель эмбеддингов (OpenRouter, $0) — доступна всем через API без
# учёта баланса и без биллинга. Не входит в каталог NeuralNetwork/вкладку
# «Бесплатные» (эмбеддинги нельзя «чатить», это отдельная developer-фича).
FREE_EMBEDDING_MODEL = 'nvidia/llama-nemotron-embed-vl-1b-v2:free'


class _EmbeddingPricing:
    """Прайс модели эмбеддингов. В каталоге NeuralNetwork эмбеддингов нет (на
    проде проверено 2026-09-25), поэтому раньше `network is None` -> списание
    молча пропускалось и эндпоинт был бесплатным для любой платной модели.
    Ставки - копейки за 1000 токенов, с запасом над себестоимостью апстрима
    (text-embedding-3-small ~0,16 коп/1k, -large ~1 коп/1k)."""

    def __init__(self, model_name: str, kopecks_per_1k: str):
        self.model_name = model_name
        self.kopecks_per_1k_tokens = Decimal(kopecks_per_1k)
        self.cost_kopecks = 0
        self.cost_per_message = 1
        self.pk = None


EMBEDDING_PRICES = {
    'text-embedding-3-small': '1',
    'text-embedding-3-large': '4',
    'text-embedding-ada-002': '1',
}


def _resolve_embedding_model(model_id: str):
    """Модель эмбеддингов с ценой или None, если модель платно не продаётся."""
    price = EMBEDDING_PRICES.get(model_id)
    if price is None:
        return None
    return _EmbeddingPricing(model_id, price)


class EmbeddingsView(APIView):
    """POST /api/v1/embeddings"""
    permission_classes = [IsAuthenticated, IsEmailVerified]

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
        is_free_model = model_id == FREE_EMBEDDING_MODEL

        network = None
        if not is_free_model:
            network = _resolve_embedding_model(model_id)
            if network is None:
                return Response(
                    {'error': {'message': f"Embedding model '{model_id}' not found. Available: "
                                          f"{', '.join(sorted(EMBEDDING_PRICES))}",
                               'type': 'invalid_request_error', 'code': 'model_not_found'}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Резерв ДО обращения к апстриму (без баланса запрос не уходит).
        res = None
        if not is_free_model:
            prompt_est = sum(estimate_text_tokens(x if isinstance(x, str) else str(x)) for x in inputs)
            try:
                res = reserve_for_request(user, api_key, network, prompt_est, 1)
            except InsufficientStarsError as e:
                return Response(
                    {'error': insufficient_error_payload(e)},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        if is_free_model:
            from aitext.providers import get_openrouter_free_client
            client = get_openrouter_free_client()
        else:
            # apimart(осн.)/cometapi(резерв) — отдельный primary от текста
            # (get_laozhang_client()), см. providers.py::get_embedding_client.
            client = get_embedding_client()
        try:
            response_obj = client.embeddings.create(
                model=model_id,
                input=inputs,
                encoding_format=encoding_format,
            )
        except Exception as e:
            if res is not None:
                release_reservation(res, 'upstream error')
            logger.error(f'[API] Ошибка эмбеддингов для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Биллинг по токенам
        usage_obj = getattr(response_obj, 'usage', None)
        total_tokens = usage_obj.total_tokens if usage_obj else len(' '.join(inputs)) // 4
        usage = {'prompt_tokens': total_tokens, 'completion_tokens': 0, 'total_tokens': total_tokens}

        # Расчёт: возврат неиспользованной части резерва (бесплатная модель - без списаний).
        if res is not None:
            settle_reservation(res, usage, total_tokens)

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
        response = Response(result)
        if res is not None:
            for _h, _v in res.headers().items():
                response[_h] = _v
        return response
