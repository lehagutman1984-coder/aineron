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
    NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage, FileAttachment,
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
        qs = (
            Chat.objects.filter(user=self.request.user)
            .select_related('network', 'network__category')
            .prefetch_related('messages')
            .order_by('-updated_at')
        )
        project_id = self.request.query_params.get('project_id')
        if project_id is not None:
            qs = qs.filter(project_id=project_id if project_id else None)
        return qs

    def create(self, request, *args, **kwargs):
        network_slug = request.data.get('network_slug')
        message_text = (request.data.get('message') or '').strip()
        files = request.data.get('files', [])
        settings = request.data.get('settings', {})
        attachment_ids = request.data.get('attachment_ids', [])
        web_search = bool(request.data.get('web_search', False))
        project_id = request.data.get('project_id')

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

        from aitext.models import Project
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id, user=request.user)
            except Project.DoesNotExist:
                pass

        chat = Chat.objects.create(
            user=request.user,
            network=network,
            project=project,
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

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id, web_search=web_search)

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
        attachment_ids = serializer.validated_data.get('attachment_ids', [])
        web_search = serializer.validated_data.get('web_search', False)

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

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id, web_search=web_search)

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
        web_search = bool(request.data.get('web_search', False))

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

        attachment_ids = request.data.get('attachment_ids', [])

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED,
        )
        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

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
        if chat.project_id:
            from aitext.models import Project
            try:
                proj = Project.objects.get(id=chat.project_id)
                if proj.system_prompt:
                    messages_for_api.append({"role": "system", "content": proj.system_prompt})
            except Project.DoesNotExist:
                pass
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

        # ── Шаг 1: веб-поиск СИНХРОННО до генератора ─────────────────────────
        # Делаем здесь, а не в generate(), чтобы гарантированно выполнился
        from aitext.tasks import WEB_SEARCH_MODEL
        search_context_text = ""
        if web_search:
            try:
                sc = get_laozhang_client()
                sr = sc.chat.completions.create(
                    model=WEB_SEARCH_MODEL,
                    messages=[{"role": "user", "content": (message_text or "информация")[:2000]}],
                    max_tokens=1500,
                )
                search_context_text = sr.choices[0].message.content.strip()
                logger.info(f"Web search OK for chat {chat.id}: {len(search_context_text)} chars")
            except Exception as se:
                logger.error(f"Web search FAILED for chat {chat.id}: {se}", exc_info=True)

            if search_context_text:
                assistant_message.search_context = search_context_text
                assistant_message.save(update_fields=['search_context'])
                messages_for_api.insert(0, {
                    "role": "system",
                    "content": (
                        "[Актуальные данные из интернета]\n"
                        "Ниже результаты поиска, только что полученные по запросу пользователя.\n"
                        "Используй их для точного и актуального ответа. "
                        "Ссылайся на конкретные факты. Отвечай на языке пользователя.\n\n"
                        f"{search_context_text[:3000]}\n\n"
                        "[Конец результатов поиска]"
                    ),
                })

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

            # Сообщаем фронтенду итог поиска (поиск уже выполнен синхронно выше)
            if web_search:
                yield _sse({
                    "type": "search_done",
                    "preview": search_context_text[:400],
                })

            full_text = ""
            try:
                # ── Шаг 2: основная модель (выбранная пользователем) ────────────
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
                    "search_context": search_context_text,
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


class RegenerateView(APIView):
    """Reset last assistant message and re-run AI generation."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        network = chat.network

        last_user = chat.messages.filter(role='user').order_by('-created_at').first()
        last_assistant = chat.messages.filter(role='assistant').order_by('-created_at').first()

        if not last_user or not last_assistant:
            return Response({
                'error': {
                    'message': 'Нет сообщений для повторной генерации',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        cost = network.cost_per_message

        if network.provider != 'fal-ai' and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        if network.provider != 'fal-ai':
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user, amount=cost,
                description=f"Повторная генерация в чате с {network.name}",
            )

        last_assistant.content = ''
        last_assistant.plain_text = ''
        last_assistant.status = Message.Status.PENDING
        last_assistant.error_message = None
        last_assistant.save()

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(last_assistant.id)

        return Response({
            'assistant_message_id': last_assistant.id,
            'new_balance': request.user.pages_count,
        })
