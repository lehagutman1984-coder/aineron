"""Sprint 5 — Multi-model image compare.

POST /api/v1/images/compare/
    Body: { "prompt": "...", "models": ["flux-...", "dall-e-3", ...], "settings": {...} }
    Создаёт по одному чату на каждую выбранную image-модель, кладёт настройки на
    user-сообщение и запускает generate_ai_response в Celery (как обычный чат-flow).
    Биллинг fal-ai выполняется внутри задачи, поэтому здесь — только paid-tier gate.

    Returns: { "items": [ { chat_id, network_slug, network_name, network_avatar,
                            provider, assistant_message_id, cost } ], "new_balance" }

Фронт опрашивает GET /v1/messages/<assistant_message_id>/status/ (ответ модели —
HTML c <img>), а голосование «Выбрать лучшее» идёт через существующий /v1/arena/vote/.
"""
import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.authentication import CsrfExemptSessionAuthentication
from aitext.models import NeuralNetwork, Chat, Message
from aitext.tasks import generate_ai_response

logger = logging.getLogger(__name__)


class ImageCompareView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = (request.data.get('prompt') or '').strip()
        # Принимаем и 'models', и 'network_slugs' для совместимости.
        slugs = request.data.get('models') or request.data.get('network_slugs') or []
        gen_settings = request.data.get('settings') or {}

        if not prompt:
            return Response({
                'error': {'message': 'Введите описание изображения', 'type': 'invalid_request_error', 'code': None}
            }, status=400)
        if not isinstance(slugs, list) or len(slugs) < 2:
            return Response({
                'error': {'message': 'Выберите минимум 2 модели', 'type': 'invalid_request_error', 'code': None}
            }, status=400)
        if len(slugs) > 4:
            return Response({
                'error': {'message': 'Максимум 4 модели для сравнения', 'type': 'invalid_request_error', 'code': None}
            }, status=400)
        if not isinstance(gen_settings, dict):
            gen_settings = {}

        # Дедупликация с сохранением порядка.
        seen: set = set()
        unique_slugs = [s for s in slugs if not (s in seen or seen.add(s))]

        if len(unique_slugs) < 2:
            return Response({
                'error': {'message': 'Выберите минимум 2 разные модели', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        networks_qs = NeuralNetwork.objects.filter(
            slug__in=unique_slugs, is_active=True, provider='fal-ai'
        )
        networks_map = {n.slug: n for n in networks_qs}

        if len(networks_map) < len(unique_slugs):
            return Response({
                'error': {'message': 'Одна или несколько моделей не найдены или не являются image-моделями', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        # Видео-модели не для image-compare.
        for slug in unique_slugs:
            n = networks_map[slug]
            if n.handle_video or (n.config_json or {}).get('metadata', {}).get('output_type') == 'video':
                return Response({
                    'error': {'message': f'Модель «{n.name}» генерирует видео, а не изображения', 'type': 'invalid_request_error', 'code': None}
                }, status=400)

        # Медиа-генерация — только на платных тарифах (как в обычном чат-flow).
        if getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Генерация изображений доступна только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        items = []
        for slug in unique_slugs:
            network = networks_map[slug]

            chat = Chat.objects.create(
                user=request.user,
                network=network,
                title=f"[Сравнение] {prompt[:40]}",
                settings={},
            )
            # validate_and_merge_settings отбрасывает поля вне ui_settings конкретной
            # модели, поэтому один общий settings безопасен для разных моделей.
            Message.objects.create(
                chat=chat, role='user', content=prompt,
                files=[], status=Message.Status.COMPLETED, settings=dict(gen_settings),
            )
            assistant_message = Message.objects.create(
                chat=chat, role='assistant', content='', status=Message.Status.PENDING,
            )

            chat.updated_at = timezone.now()
            chat.save(update_fields=['updated_at'])

            generate_ai_response.delay(assistant_message.id)

            items.append({
                'chat_id': chat.id,
                'network_slug': network.slug,
                'network_name': network.name,
                'network_avatar': network.get_avatar(),
                'provider': network.provider,
                'assistant_message_id': assistant_message.id,
                'cost': network.cost_per_message,
                'cost_kopecks': network.cost_kopecks,
            })

        return Response({
            'items': items,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        }, status=201)
