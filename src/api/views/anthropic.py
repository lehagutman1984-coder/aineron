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
from api.permissions import IsEmailVerified
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.tasks import get_laozhang_client
from api.exceptions import InsufficientStarsError
from api.services.billing import (
    estimate_messages_tokens,
    estimate_text_tokens,
    insufficient_error_payload,
    release_reservation,
    reserve_for_request,
    settle_reservation,
)

logger = logging.getLogger(__name__)


def _resolve_network(model_id: str):
    try:
        return NeuralNetwork.objects.get(model_name=model_id, is_active=True, provider='openrouter')
    except NeuralNetwork.DoesNotExist:
        return None


def _anthropic_system_to_text(system) -> str:
    """system может быть строкой ИЛИ списком content-блоков (Anthropic
    поддерживает список блоков с cache_control и т.п.) — раньше список
    уходил в OpenAI messages как есть (сырой list вместо строки), что ломает
    провайдера. Берём только текстовые блоки, как и для обычных сообщений."""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return '\n'.join(
            block.get('text', '') for block in system
            if isinstance(block, dict) and block.get('type') == 'text'
        )
    return ''


def _anthropic_to_openai_messages(messages: list, system=None) -> list:
    """Конвертирует Anthropic messages → OpenAI messages.

    2026-10-01 (аудит, HIGH): раньше (а) блок, который не был dict'ом, падал
    на block.get(...) с AttributeError → 500; (б) image-блоки молча
    выбрасывались — модель отвечала без картинки, а запрос всё равно
    списывался по полной цене, как будто картинка была учтена. image теперь
    конвертируется в OpenAI image_url (апстрим — тот же мультимодальный
    OpenAI-совместимый контракт, что и у /v1/chat/completions). tool_use/
    tool_result блоки по-прежнему пропускаются — tools отклоняется отдельной
    проверкой выше (честная ошибка вместо тихой потери)."""
    result = []
    system_text = _anthropic_system_to_text(system)
    if system_text:
        result.append({'role': 'system', 'content': system_text})
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if isinstance(content, list):
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get('type')
                if btype == 'text':
                    parts.append({'type': 'text', 'text': block.get('text', '')})
                elif btype == 'image':
                    source = block.get('source') or {}
                    media_type = source.get('media_type', 'image/jpeg')
                    data_b64 = source.get('data', '')
                    if source.get('type') == 'base64' and data_b64:
                        parts.append({'type': 'image_url', 'image_url': {
                            'url': f'data:{media_type};base64,{data_b64}',
                        }})
                    elif source.get('type') == 'url' and source.get('url'):
                        parts.append({'type': 'image_url', 'image_url': {'url': source['url']}})
                # tool_use/tool_result — пропускаются (tools отклоняется выше).
            content = parts if parts else ''
        result.append({'role': role, 'content': content})
    return result


_FINISH_REASON_TO_STOP_REASON = {
    'stop': 'end_turn',
    'length': 'max_tokens',
    'tool_calls': 'tool_use',
    'content_filter': 'end_turn',
}


class AnthropicMessagesView(APIView):
    """POST /api/v1/messages"""
    permission_classes = [IsAuthenticated, IsEmailVerified]

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
        # 2026-10-01 (аудит, HIGH): stream/tools раньше молча игнорировались
        # (200 OK без единого предупреждения) — контрактный баг для эндпоинта,
        # продающегося как совместимый с Anthropic SDK: клиент решал, что
        # стриминг/вызов функций сработал, получал обычный синхронный текстовый
        # ответ без каких-либо вызовов инструментов и был ЗА НЕГО списан по
        # полной цене. Честная ошибка лучше тихого несоответствия контракту —
        # до реализации настоящей поддержки (translate Anthropic tools↔OpenAI
        # tool_calls, Anthropic SSE event-формат для стрима, оба требуют
        # отдельной задачи, не точечного фикса).
        if data.get('stream'):
            return Response(
                {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "'stream' is not yet supported on this endpoint"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data.get('tools') or data.get('tool_choice'):
            return Response(
                {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "'tools' is not yet supported on this endpoint"}},
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
        organization = getattr(api_key, 'organization', None) if api_key else None

        # Rule S — см. api/views/chat.py для полного обоснования (тот же
        # dev-API-путь, тот же пробел: политика "не предлагать дорогую модель
        # пробному" отсутствовала здесь, хотя реальные деньги уже защищены
        # атомарным reserve_for_request ниже).
        if organization is None and user.is_unpaid_free_user():
            from core import model_pricing
            if model_pricing.is_model_blocked_for_trial(network):
                from aitext.token_metering import trial_block_message
                return Response(
                    {'type': 'error', 'error': {
                        'type': 'insufficient_permissions',
                        'message': trial_block_message(network, user.get_language()),
                    }},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        openai_messages = _anthropic_to_openai_messages(messages, system)
        client = get_laozhang_client()

        from core.model_limits import clamp_max_tokens
        max_tokens = clamp_max_tokens(max_tokens, network.model_name)

        # Резерв средств ДО обращения к апстриму (см. api/services/billing.py):
        # раньше проверялся только `balance <= 0`, а списание шло после ответа.
        try:
            res = reserve_for_request(
                user, api_key, network, estimate_messages_tokens(openai_messages), max_tokens,
            )
        except InsufficientStarsError as e:
            return Response(
                {'type': 'error', 'error': insufficient_error_payload(e)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            completion = client.chat.completions.create(
                model=network.model_name,
                messages=openai_messages,
                max_tokens=res.max_tokens,
            )
        except Exception as e:
            release_reservation(res, 'upstream error')
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

        content_text = completion.choices[0].message.content or ''
        settle_reservation(res, usage, estimate_text_tokens(content_text))
        request_id = uuid.uuid4().hex[:12]
        # 2026-10-01 (аудит): раньше stop_reason был всегда 'end_turn' —
        # ответ, обрезанный по max_tokens, выглядел для SDK как естественно
        # завершённый, а не как усечённый.
        finish_reason = getattr(completion.choices[0], 'finish_reason', None)
        stop_reason = _FINISH_REASON_TO_STOP_REASON.get(finish_reason, 'end_turn')

        # Anthropic-формат ответа
        result = {
            'id': f'msg_{request_id}',
            'type': 'message',
            'role': 'assistant',
            'content': [{'type': 'text', 'text': content_text}],
            'model': model_id,
            'stop_reason': stop_reason,
            'stop_sequence': None,
            'usage': {
                'input_tokens': usage['prompt_tokens'],
                'output_tokens': usage['completion_tokens'],
            },
        }
        response = Response(result)
        for _h, _v in res.headers().items():
            response[_h] = _v
        return response
