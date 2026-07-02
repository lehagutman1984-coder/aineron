import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from aitext.models import NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage
from aitext.tasks import generate_ai_response
from users.models import UserSpending

logger = logging.getLogger(__name__)


class CompareView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message_text = (request.data.get('message') or '').strip()
        network_slugs = request.data.get('network_slugs', [])

        if not message_text:
            return Response({
                'error': {'message': 'Введите текст запроса', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        if not isinstance(network_slugs, list) or len(network_slugs) < 2:
            return Response({
                'error': {'message': 'Выберите минимум 2 модели', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        if len(network_slugs) > 6:
            return Response({
                'error': {'message': 'Максимум 6 моделей для сравнения', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        # Deduplicate while preserving order
        seen: set = set()
        unique_slugs = [s for s in network_slugs if not (s in seen or seen.add(s))]

        networks_qs = NeuralNetwork.objects.filter(
            slug__in=unique_slugs, is_active=True
        ).prefetch_related('tariffs')
        networks_map = {n.slug: n for n in networks_qs}

        if len(networks_map) < len(unique_slugs):
            return Response({
                'error': {'message': 'Одна или несколько моделей не найдены', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        today = timezone.now().date()
        network_costs: dict = {}
        total_cost_kopecks = 0

        for slug in unique_slugs:
            network = networks_map[slug]
            cost_kopecks = network.cost_kopecks
            deduct = True

            if (network.unlimited and
                    network.tariffs.filter(id=request.user.tariff.id).exists() and
                    network.messages_limit > 0):
                usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                    user=request.user, network=network, date=today, defaults={'count': 0}
                )
                if usage.count < network.messages_limit:
                    deduct = False
                    usage.count += 1
                    usage.save()

            if network.provider != 'fal-ai' and deduct:
                total_cost_kopecks += cost_kopecks

            network_costs[slug] = (cost_kopecks, deduct)

        if not request.user.has_enough_kopecks(total_cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(total_cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        items = []
        for slug in unique_slugs:
            network = networks_map[slug]
            cost_kopecks, deduct = network_costs[slug]

            chat = Chat.objects.create(
                user=request.user,
                network=network,
                title=f"[Сравнение] {message_text[:40]}",
                settings={},
            )
            Message.objects.create(
                chat=chat, role='user', content=message_text,
                files=[], status=Message.Status.COMPLETED,
            )
            assistant_message = Message.objects.create(
                chat=chat, role='assistant', content='', status=Message.Status.PENDING,
            )

            if network.provider != 'fal-ai' and deduct:
                from aitext.billing import record_message_billing
                request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'compare:{assistant_message.id}')
                UserSpending.objects.create(
                    user=request.user, amount=cost_kopecks // 100, amount_kopecks=cost_kopecks,
                    description=f"Сравнение моделей: {network.name}",
                )
                record_message_billing(assistant_message, f'compare:{assistant_message.id}', cost_kopecks)

            chat.updated_at = timezone.now()
            chat.save(update_fields=['updated_at'])

            generate_ai_response.delay(assistant_message.id)

            items.append({
                'chat_id': chat.id,
                'network_slug': network.slug,
                'network_name': network.name,
                'network_avatar': network.avatar.url if network.avatar else None,
                'provider': network.provider,
                'assistant_message_id': assistant_message.id,
                'cost': cost_kopecks // 100,
                'cost_kopecks': cost_kopecks,
            })

        return Response({
            'items': items,
            'total_cost': total_cost_kopecks // 100,
            'total_cost_kopecks': total_cost_kopecks,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        }, status=201)
