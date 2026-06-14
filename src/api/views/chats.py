import json
import logging
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import (
    NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage,
)
from aitext.tasks import generate_ai_response, get_laozhang_client
from aitext.code_formatter import CodeFormatter
from users.models import UserSpending
from api.serializers.chats import (
    ChatListSerializer, ChatDetailSerializer, ChatUpdateSerializer,
    MessageSerializer, SendMessageSerializer,
)

logger = logging.getLogger(__name__)


class ChatListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return ChatListSerializer

    def get_queryset(self):
        return (
            Chat.objects.filter(user=self.request.user)
            .select_related('network', 'network__category')
            .prefetch_related('messages')
            .order_by('-updated_at')
        )

    def create(self, request, *args, **kwargs):
        network_slug = request.data.get('network_slug')
        message_text = (request.data.get('message') or '').strip()
        files = request.data.get('files', [])
        settings = request.data.get('settings', {})

        if not network_slug:
            return Response({'error': {'message': 'Не указана нейросеть', 'type': 'invalid_request_error', 'code': None}}, status=400)
        if not message_text and not files:
            return Response({'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}}, status=400)

        network = get_object_or_404(NeuralNetwork, slug=network_slug, is_active=True)
        cost = network.cost_per_message
        deduct_stars = True

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        chat = Chat.objects.create(
            user=request.user,
            network=network,
            title=message_text[:50] if message_text else f"{network.name} - {timezone.now().strftime('%d.%m.%Y %H:%M')}",
            settings=settings,
        )

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED, settings=settings,
        )

        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user, amount=cost,
                description=f"Сообщение в чате с {network.name}",
            )

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id)

        return Response({
            'chat_id': chat.id,
            'user_message_id': user_message.id,
            'assistant_message_id': assistant_message.id,
            'new_balance': request.user.pages_count,
        }, status=201)


class ChatDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user).select_related('network', 'network__category')

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return ChatUpdateSerializer
        return ChatDetailSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        chat = self.get_object()
        chat.delete()
        return Response(status=204)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_text = serializer.validated_data['message'].strip()
        files = serializer.validated_data['files']
        settings = serializer.validated_data['settings']

        if not message_text and not files:
            return Response({'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}}, status=400)

        network = chat.network
        cost = network.cost_per_message
        deduct_stars = True

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED, settings=settings,
        )

        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user, amount=cost,
                description=f"Сообщение в чате с {network.name}",
            )

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id)

        return Response({
            'user_message_id': user_message.id,
            'assistant_message_id': assistant_message.id,
            'new_balance': request.user.pages_count,
        }, status=201)


class MessageStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, message_id):
        message = get_object_or_404(
            Message, id=message_id, chat__user=request.user
        )
        return Response(MessageSerializer(message).data)


class StreamMessageView(APIView):
    """SSE streaming endpoint for text models. fal-ai returns 400."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        network = chat.network

        if network.provider == 'fal-ai':
            return Response({
                'error': {
                    'message': 'Streaming не поддерживается для моделей генерации изображений',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        if not network.model_name:
            return Response({
                'error': {'message': 'У нейросети не указана модель', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        message_text = (request.data.get('message') or '').strip()
        files = request.data.get('files', [])

        if not message_text and not files:
            return Response({
                'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        cost = network.cost_per_message
        deduct_stars = True

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED,
        )
        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        if deduct_stars:
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user, amount=cost,
                description=f"Сообщение в чате с {network.name}",
            )

        new_balance = request.user.pages_count
        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        # Build message history for API (mirrors tasks.py logic)
        max_input_tokens = network.max_input_tokens
        history_qs = (
            chat.messages
            .filter(status=Message.Status.COMPLETED)
            .exclude(id=user_message.id)
            .order_by('-created_at')[:20]
        )
        history = list(reversed(history_qs))

        messages_for_api = []
        if network.has_prompt and network.prompt:
            messages_for_api.append({"role": "system", "content": network.prompt})

        for msg in history:
            if msg.role == 'user':
                content_text = msg.content or ""
                extracted = msg.extracted_content or ""
                if max_input_tokens > 0:
                    if len(content_text) > max_input_tokens:
                        content_text = content_text[:max_input_tokens] + "..."
                    if extracted and len(extracted) > max_input_tokens:
                        extracted = extracted[:max_input_tokens] + "..."
                if extracted:
                    combined = f"{content_text}\n\n{extracted}" if content_text else extracted
                    messages_for_api.append({"role": "user", "content": combined})
                elif content_text:
                    messages_for_api.append({"role": "user", "content": content_text})
            elif msg.role == 'assistant':
                assistant_text = msg.plain_text or msg.content
                if assistant_text:
                    if max_input_tokens > 0 and len(assistant_text) > max_input_tokens:
                        assistant_text = assistant_text[:max_input_tokens] + "..."
                    messages_for_api.append({"role": "assistant", "content": assistant_text})

        messages_for_api.append({"role": "user", "content": message_text or "Привет"})

        # Capture values for the generator closure
        user = request.user
        user_msg_id = user_message.id
        assist_msg_id = assistant_message.id
        model_name = network.model_name
        max_tokens = network.max_tokens

        def _sse(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode('utf-8')

        def generate():
            yield _sse({
                "type": "init",
                "user_message_id": user_msg_id,
                "assistant_message_id": assist_msg_id,
                "new_balance": new_balance,
            })

            full_text = ""
            try:
                client = get_laozhang_client()
                kwargs = {
                    "model": model_name,
                    "messages": messages_for_api,
                    "temperature": 0.7,
                    "stream": True,
                }
                if max_tokens > 0:
                    kwargs["max_tokens"] = max_tokens

                stream = client.chat.completions.create(**kwargs)
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        full_text += delta.content
                        yield _sse({"type": "token", "text": delta.content})

                formatted_html = CodeFormatter.format_ai_response(full_text)
                assistant_message.content = formatted_html
                assistant_message.plain_text = full_text
                assistant_message.status = Message.Status.COMPLETED
                assistant_message.save()

                yield _sse({
                    "type": "done",
                    "content": formatted_html,
                    "plain_text": full_text,
                })

            except Exception as e:
                logger.error(f"SSE streaming error for message {assist_msg_id}: {e}")
                if deduct_stars:
                    user.add_pages(cost)
                    logger.info(f"Refunded {cost} stars to {user.email} after streaming error")
                assistant_message.status = Message.Status.FAILED
                assistant_message.error_message = "Ошибка при генерации ответа. Попробуйте ещё раз."
                assistant_message.save()
                yield _sse({
                    "type": "error",
                    "message": "Ошибка при генерации ответа. Попробуйте ещё раз.",
                })

        resp = StreamingHttpResponse(generate(), content_type='text/event-stream; charset=utf-8')
        resp['Cache-Control'] = 'no-cache'
        resp['X-Accel-Buffering'] = 'no'
        return resp
