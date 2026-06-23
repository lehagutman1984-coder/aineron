"""
POST /api/v1/messages — Anthropic Messages API-совместимый эндпоинт.
Конвертирует Anthropic-формат → OpenAI → ответ обратно в Anthropic-формат.
"""
import logging
import time
import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.tasks import get_laozhang_client
from api.exceptions import InsufficientStarsError
from api.services.billing import charge_for_tokens

logger = logging.getLogger(__name__)


def _resolve_network(model_id: str):
    try:
        return NeuralNetwork.objects.get(model_name=model_id, is_active=True, provider='openrouter')
    except NeuralNetwork.DoesNotExist:
        return None


def _anthropic_to_openai_messages(messages: list, system: str = None) -> list:
    """Конвертирует Anthropic messages → OpenAI messages."""
    result = []
    if system:
        result.append({'role': 'system', 'content': system})
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if isinstance(content, list):
            # Anthropic content blocks → строка
            text_parts = [
                block.get('text', '')
                for block in content
                if block.get('type') == 'text'
            ]
            content = '\n'.join(text_parts)
        result.append({'role': role, 'content': content})
    return result


class AnthropicMessagesView(APIView):
    """POST /api/v1/messages"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Messages (Anthropic-совместимый)',
        tags=['Anthropic'],
        description='Принимает формат Anthropic Messages API. Работает с Anthropic SDK.',
    )
    def post(self, request):
        data = request.data
        model_id = data.get('model', '')
        messages = data.get('messages', [])
        system = data.get('system', '')
        max_tokens = data.get('max_tokens', 32000)

        if not model_id:
            return Response(
                {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "'model' is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not messages:
            return Response(
                {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "'messages' is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        network = _resolve_network(model_id)
        if network is None:
            return Response(
                {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': f"Model '{model_id}' not found"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        api_key = getattr(request, 'api_key', None)

        if user.pages_count <= 0:
            return Response(
                {'type': 'error', 'error': {'type': 'overloaded_error', 'message': f'Insufficient balance: {user.pages_count} stars'}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        openai_messages = _anthropic_to_openai_messages(messages, system)
        client = get_laozhang_client()

        try:
            completion = client.chat.completions.create(
                model=network.model_name,
                messages=openai_messages,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f'[API] Ошибка anthropic endpoint для {user.email}: {e}')
            return Response(
                {'type': 'error', 'error': {'type': 'api_error', 'message': str(e)}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        usage_obj = completion.usage
        usage = {
            'prompt_tokens': usage_obj.prompt_tokens if usage_obj else 0,
            'completion_tokens': usage_obj.completion_tokens if usage_obj else 0,
            'total_tokens': usage_obj.total_tokens if usage_obj else 0,
        }

        try:
            charge_for_tokens(user, network, usage, api_key=api_key)
        except InsufficientStarsError as e:
            return Response(
                {'type': 'error', 'error': {'type': 'overloaded_error', 'message': str(e)}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        content_text = completion.choices[0].message.content or ''
        request_id = uuid.uuid4().hex[:12]

        # Anthropic-формат ответа
        result = {
            'id': f'msg_{request_id}',
            'type': 'message',
            'role': 'assistant',
            'content': [{'type': 'text', 'text': content_text}],
            'model': model_id,
            'stop_reason': 'end_turn',
            'stop_sequence': None,
            'usage': {
                'input_tokens': usage['prompt_tokens'],
                'output_tokens': usage['completion_tokens'],
            },
        }
        return Response(result)
