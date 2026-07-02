"""
POST /api/v1/chat/completions — OpenAI-совместимый эндпоинт.
Поддерживает stream=true (SSE) и обычный режим.
"""
import json
import logging
import time
import uuid

from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.tasks import get_laozhang_client
from api.exceptions import InsufficientStarsError
from api.services.billing import charge_for_tokens, refund_kopecks

logger = logging.getLogger(__name__)


def _resolve_network(model_id: str):
    """Маппинг model (строка) → NeuralNetwork. Проверяет model_name и slug."""
    try:
        return NeuralNetwork.objects.get(model_name=model_id, is_active=True, provider='openrouter')
    except NeuralNetwork.DoesNotExist:
        pass
    try:
        return NeuralNetwork.objects.get(slug=model_id, is_active=True, provider='openrouter')
    except NeuralNetwork.DoesNotExist:
        return None


def _build_openai_response(completion, model_id: str, request_id: str) -> dict:
    choice = completion.choices[0]
    usage = completion.usage
    return {
        'id': f'chatcmpl-{request_id}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model_id,
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': choice.message.content or '',
                },
                'finish_reason': choice.finish_reason or 'stop',
            }
        ],
        'usage': {
            'prompt_tokens': usage.prompt_tokens if usage else 0,
            'completion_tokens': usage.completion_tokens if usage else 0,
            'total_tokens': usage.total_tokens if usage else 0,
        },
    }


def _stream_completion(user, network, messages, kwargs, api_key):
    """Генератор SSE-чанков. Списывает звёзды после завершения стрима."""
    client = get_laozhang_client()
    request_id = uuid.uuid4().hex[:12]
    model_id = network.model_name

    prompt_tokens = 0
    completion_tokens = 0
    kopecks_charged = 0

    try:
        with client.chat.completions.create(stream=True, **kwargs) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                content = delta.content if delta else ''
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                chunk_data = {
                    'id': f'chatcmpl-{request_id}',
                    'object': 'chat.completion.chunk',
                    'created': int(time.time()),
                    'model': model_id,
                    'choices': [
                        {
                            'index': 0,
                            'delta': {'content': content or ''},
                            'finish_reason': finish_reason,
                        }
                    ],
                }
                yield f'data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n'

                # Токены приходят в последнем чанке (usage)
                if hasattr(chunk, 'usage') and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens or 0
                    completion_tokens = chunk.usage.completion_tokens or 0

        # Биллинг после завершения стрима
        total_tokens = prompt_tokens + completion_tokens
        usage = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
        }
        try:
            kopecks_charged = charge_for_tokens(user, network, usage, api_key=api_key)
        except InsufficientStarsError as e:
            logger.warning(f'[API] Нехватка баланса после стрима для {user.email}: {e}')

        yield 'data: [DONE]\n\n'

    except Exception as e:
        logger.error(f'[API] Ошибка стриминга для {user.email}: {e}')
        if kopecks_charged:
            refund_kopecks(user, kopecks_charged, reason='stream error')
        error_event = {
            'error': {
                'message': str(e),
                'type': 'api_error',
                'code': 'stream_error',
            }
        }
        yield f'data: {json.dumps(error_event)}\n\n'
        yield 'data: [DONE]\n\n'


class ChatCompletionsView(APIView):
    """POST /api/v1/chat/completions"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Chat Completions (OpenAI-совместимый)',
        tags=['Chat'],
        description='Принимает OpenAI-формат. Поддерживает stream=true.',
    )
    def post(self, request):
        data = request.data
        model_id = data.get('model', '')
        messages = data.get('messages', [])
        stream = data.get('stream', False)
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens')

        if not model_id:
            return Response(
                {'error': {'message': "'model' is required", 'type': 'invalid_request_error', 'code': 'missing_model'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not messages:
            return Response(
                {'error': {'message': "'messages' is required", 'type': 'invalid_request_error', 'code': 'missing_messages'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        network = _resolve_network(model_id)
        if network is None:
            return Response(
                {'error': {'message': f"Model '{model_id}' not found", 'type': 'invalid_request_error', 'code': 'model_not_found'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        api_key = getattr(request, 'api_key', None)

        # Предварительная проверка баланса (примерная, точное списание после ответа)
        if user.balance_kopecks <= 0:
            from core.money import format_rub
            return Response(
                {
                    'error': {
                        'message': f'Insufficient balance. Current balance: {format_rub(user.balance_kopecks)}.',
                        'type': 'insufficient_quota',
                        'code': 'insufficient_quota',
                    }
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_laozhang_client()
        kwargs = {
            'model': network.model_name,
            'messages': messages,
            'temperature': temperature,
        }
        if max_tokens:
            kwargs['max_tokens'] = max_tokens
        elif network.max_tokens > 0:
            kwargs['max_tokens'] = network.max_tokens

        if stream:
            gen = _stream_completion(user, network, messages, kwargs, api_key)
            response = StreamingHttpResponse(
                gen,
                content_type='text/event-stream',
                status=200,
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

        # Non-streaming
        kopecks_charged = 0
        try:
            completion = client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f'[API] Ошибка laozhang для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        usage_obj = completion.usage
        usage = {
            'prompt_tokens': usage_obj.prompt_tokens if usage_obj else 0,
            'completion_tokens': usage_obj.completion_tokens if usage_obj else 0,
            'total_tokens': usage_obj.total_tokens if usage_obj else 0,
        }

        try:
            kopecks_charged = charge_for_tokens(user, network, usage, api_key=api_key)
        except InsufficientStarsError as e:
            return Response(
                {'error': {'message': str(e), 'type': 'insufficient_quota', 'code': 'insufficient_quota'}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        request_id = uuid.uuid4().hex[:12]
        result = _build_openai_response(completion, model_id, request_id)
        return Response(result)
