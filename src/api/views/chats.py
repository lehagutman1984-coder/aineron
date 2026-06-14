import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import (
    NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage,
)
from aitext.tasks import generate_ai_response
from users.models import UserSpending
from api.serializers.chats import (
    ChatListSerializer, ChatDetailSerializer,
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


class ChatDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatDetailSerializer

    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user).select_related('network', 'network__category')

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
