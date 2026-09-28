import logging
from aitext.limits import claim_free_slot
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from api.permissions import IsEmailVerified
from rest_framework.response import Response

from aitext.models import NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage
from aitext.tasks import generate_ai_response
from users.models import UserSpending

logger = logging.getLogger(__name__)


class CompareView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

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

        # 2026-09-28: Model Arena принимала fal-ai (медиа) модели без гейта has_made_real_payment
        # — единственное место рядом с обычным чатом/файлами, где его не было (там он есть
        # везде: chats.py/files.py/image_compare.py). Отклоняем весь запрос сразу, если среди
        # выбранных моделей есть хоть одна медиа и пользователь ни разу не платил.
        # 2026-09-28 (ревью, раунд 2): узкий predicate provider=='fal-ai' полагался на
        # конвенцию сеятельных команд (все медиа-модели сегодня заведены с этим provider,
        # проверено на обеих БД: 0 расхождений) — но ручное редактирование в админке могло
        # бы создать медиа-модель с другим provider, полностью обходящую гейт здесь и в
        # legacy create_chat/send_message. Широкий predicate — тот же, что уже в
        # files.py/chats.py — не зависит от этой конвенции.
        _is_media_network = lambda n: n.provider == 'fal-ai' or (n.config_json or {}).get('metadata', {}).get('output_type') in ('image', 'video')
        if any(_is_media_network(n) for n in networks_map.values()) and not request.user.can_generate_media():
            return Response({
                'error': {
                    'message': 'Генерация изображений и видео доступна только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

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
                if claim_free_slot(usage, network.messages_limit):
                    deduct = False

            if network.provider != 'fal-ai' and deduct:
                total_cost_kopecks += cost_kopecks

            network_costs[slug] = (cost_kopecks, deduct)

        # Rule S (free_tier_guard, ITEM 1 часть B): дорогая модель вообще не предлагается
        # пробному (никогда не плативше­му) пользователю.
        if request.user.is_unpaid_free_user():
            from core.model_pricing import is_model_blocked_for_trial
            blocked = [
                networks_map[slug] for slug in unique_slugs
                if networks_map[slug].provider != 'fal-ai' and network_costs[slug][1]
                and is_model_blocked_for_trial(networks_map[slug])
            ]
            if blocked:
                from aitext.token_metering import trial_block_message
                return Response({
                    'error': {
                        'message': trial_block_message(blocked[0], request.user.get_language()),
                        'type': 'insufficient_permissions',
                        'code': 'requires_paid_plan',
                    }
                }, status=402)

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
                if not request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'compare:{assistant_message.id}'):
                    # Гонка с параллельным запросом: средств уже нет - без оплаты не генерируем.
                    chat.delete()
                    continue
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

        if not items:
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(total_cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        return Response({
            'items': items,
            'total_cost': total_cost_kopecks // 100,
            'total_cost_kopecks': total_cost_kopecks,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        }, status=201)
