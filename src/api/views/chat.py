"""
POST /api/v1/chat/completions — OpenAI-совместимый эндпоинт.
Поддерживает stream=true (SSE) и обычный режим.

Биллинг: резерв -> генерация -> расчёт (см. api/services/billing.py).
Средства резервируются ДО обращения к апстриму; без баланса генерации нет.
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
from api.permissions import IsEmailVerified
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
    message = {
        'role': 'assistant',
        'content': choice.message.content,
    }
    # 2026-09-06: tool_calls раньше не прокидывались в ответ — клиенты,
    # использующие tools/tool_choice (см. PASSTHROUGH_PARAMS ниже), получали
    # 200 OK без единого вызова функции, даже если апстрим его вернул.
    if getattr(choice.message, 'tool_calls', None):
        message['tool_calls'] = [tc.model_dump() for tc in choice.message.tool_calls]
    return {
        'id': f'chatcmpl-{request_id}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model_id,
        'choices': [
            {
                'index': 0,
                'message': message,
                'finish_reason': choice.finish_reason or 'stop',
            }
        ],
        'usage': {
            'prompt_tokens': usage.prompt_tokens if usage else 0,
            'completion_tokens': usage.completion_tokens if usage else 0,
            'total_tokens': usage.total_tokens if usage else 0,
        },
    }


def _stream_completion(res, kwargs):
    """
    Генератор SSE-чанков. Средства уже зарезервированы (res) до старта стрима;
    после завершения возвращаем неиспользованную часть, а при обрыве/ошибке
    считаем по фактически отданному тексту (fail-closed) либо возвращаем резерв
    целиком, если клиент не получил ни одного символа.
    """
    user = res.user
    client = get_laozhang_client()
    request_id = res.request_id
    model_id = res.network.model_name

    usage = {}
    streamed_text = []

    try:
        with client.chat.completions.create(stream=True, **kwargs) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                content = delta.content if delta else ''
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                if content:
                    streamed_text.append(content)

                delta_out = {'content': content or ''}
                if delta is not None and getattr(delta, 'tool_calls', None):
                    delta_out = {'tool_calls': [tc.model_dump() for tc in delta.tool_calls]}
                    streamed_text.append(str(delta_out['tool_calls']))

                chunk_data = {
                    'id': f'chatcmpl-{request_id}',
                    'object': 'chat.completion.chunk',
                    'created': int(time.time()),
                    'model': model_id,
                    'choices': [
                        {
                            'index': 0,
                            'delta': delta_out,
                            'finish_reason': finish_reason,
                        }
                    ],
                }
                yield f'data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n'

                # Токены приходят в последнем чанке (usage)
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens or 0,
                        'completion_tokens': chunk.usage.completion_tokens or 0,
                        'total_tokens': chunk.usage.total_tokens or 0,
                    }

        # Расчёт после завершения стрима (возврат разницы / доплата перерасхода)
        settle_reservation(res, usage, estimate_text_tokens(''.join(streamed_text)))
        yield 'data: [DONE]\n\n'

    except Exception as e:
        logger.error(f'[API] Ошибка стриминга для {user.email}: {e}')
        # Клиенту ничего не отдали - возвращаем резерв; иначе считаем по отданному.
        if streamed_text:
            settle_reservation(res, usage, estimate_text_tokens(''.join(streamed_text)))
        else:
            release_reservation(res, 'stream error')
        error_event = {
            'error': {
                'message': str(e),
                'type': 'api_error',
                'code': 'stream_error',
            }
        }
        yield f'data: {json.dumps(error_event)}\n\n'
        yield 'data: [DONE]\n\n'
    finally:
        # Клиент оборвал соединение (GeneratorExit) либо иной BaseException:
        # резерв не должен «зависнуть» и не должен вернуться целиком за уже
        # сгенерированный (и оплаченный нами) текст.
        if not res.closed:
            if streamed_text:
                settle_reservation(res, usage, estimate_text_tokens(''.join(streamed_text)))
            else:
                release_reservation(res, 'client disconnected')


class ChatCompletionsView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

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

        client = get_laozhang_client()
        kwargs = {
            'model': network.model_name,
            'messages': messages,
            'temperature': temperature,
        }
        from core.model_limits import clamp_max_tokens
        # Клиент управляет max_tokens (или БД-дефолт network.max_tokens), но
        # всегда клампится к потолку модели — иначе на моделях с дорогим
        # выходом (Claude и т.п.) при плоской ошибке пересчёта можно запросить
        # произвольно длинный ответ дешевле реальной себестоимости.
        requested_max = clamp_max_tokens(
            max_tokens or (network.max_tokens if network.max_tokens > 0 else None),
            network.model_name,
        )

        # Резерв средств ДО обращения к апстриму (инцидент 2026-09-25: проверка
        # `balance <= 0` + списание после ответа давали бесплатные ответы Opus
        # при балансе в несколько рублей). max_tokens сужается под баланс; если
        # не хватает даже на минимальный ответ - 402 без вызова апстрима.
        # `n` (несколько вариантов ответа) умножает выходные токены - резервируем
        # под все варианты, иначе перерасход над резервом остался бы неоплаченным.
        try:
            n_choices = int(data.get('n', 1))
        except (TypeError, ValueError):
            n_choices = 0
        if not 1 <= n_choices <= 4:
            return Response(
                {'error': {'message': "'n' must be an integer between 1 and 4", 'type': 'invalid_request_error', 'code': 'invalid_n'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            res = reserve_for_request(
                user, api_key, network, estimate_messages_tokens(messages), requested_max * n_choices,
            )
        except InsufficientStarsError as e:
            return Response(
                {'error': insufficient_error_payload(e)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        kwargs['max_tokens'] = max(1, res.max_tokens // n_choices)

        # 2026-09-06: раньше эти стандартные OpenAI-параметры молча
        # игнорировались (200 OK без единого предупреждения) — контрактный
        # баг для эндпоинта, продающегося как OpenAI-совместимый. Прокидываем
        # 1:1 в апстрим (apimart/cometapi), если клиент их передал.
        for _param in ('top_p', 'seed', 'stop', 'n', 'tools', 'tool_choice',
                       'response_format', 'presence_penalty', 'frequency_penalty'):
            if _param in data:
                kwargs[_param] = data[_param]

        if stream:
            # usage в последнем чанке нужен для точного расчёта (без него
            # settle_reservation считает по оценке, а не по факту апстрима).
            kwargs['stream_options'] = {'include_usage': True}
            gen = _stream_completion(res, kwargs)
            response = StreamingHttpResponse(
                gen,
                content_type='text/event-stream',
                status=200,
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            for _h, _v in res.headers().items():
                response[_h] = _v
            return response

        # Non-streaming
        try:
            completion = client.chat.completions.create(**kwargs)
        except Exception as e:
            release_reservation(res, 'upstream error')
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
            _text = completion.choices[0].message.content or ''
        except Exception:
            _text = ''
        settle_reservation(res, usage, estimate_text_tokens(_text))

        response = Response(_build_openai_response(completion, model_id, res.request_id))
        for _h, _v in res.headers().items():
            response[_h] = _v
        return response
