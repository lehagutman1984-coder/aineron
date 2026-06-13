"""
POST /api/v1/images/generations — OpenAI-совместимая генерация изображений.
Проксирует на laozhang.ai через images.generate API.
"""
import logging
import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from aitext.models import NeuralNetwork
from aitext.fal_utils import get_laozhang_image_client, save_media_from_url
from api.exceptions import InsufficientStarsError

logger = logging.getLogger(__name__)


def _resolve_image_network(model_id: str):
    try:
        return NeuralNetwork.objects.get(model_name=model_id, is_active=True, provider='fal-ai')
    except NeuralNetwork.DoesNotExist:
        return None


class ImageGenerationsView(APIView):
    """POST /api/v1/images/generations"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Генерация изображений (OpenAI-совместимый)',
        tags=['Images'],
    )
    def post(self, request):
        data = request.data
        model_id = data.get('model', '')
        prompt = data.get('prompt', '').strip()
        n = int(data.get('n', 1))
        size = data.get('size', '1024x1024')
        response_format = data.get('response_format', 'url')

        if not prompt:
            return Response(
                {'error': {'message': "'prompt' is required", 'type': 'invalid_request_error', 'code': 'missing_prompt'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        network = _resolve_image_network(model_id) if model_id else None
        if network is None:
            # Попытка найти любую активную модель изображений
            network = NeuralNetwork.objects.filter(is_active=True, provider='fal-ai').first()
        if network is None:
            return Response(
                {'error': {'message': f"Image model '{model_id}' not found", 'type': 'invalid_request_error', 'code': 'model_not_found'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        cost = network.cost_per_message * n

        if user.pages_count < cost:
            return Response(
                {
                    'error': {
                        'message': f'Insufficient balance. Need {cost} stars, have {user.pages_count}.',
                        'type': 'insufficient_quota',
                        'code': 'insufficient_quota',
                    }
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        # Списываем заранее (как в web-чате)
        user.spend_pages(cost)
        stars_returned = False

        try:
            client = get_laozhang_image_client()
            # Формируем kwargs из config_json defaults + запроса
            config = network.config_json or {}
            api_defaults = config.get('api_defaults', {}).copy()
            api_defaults['prompt'] = prompt
            if size:
                api_defaults['size'] = size
            api_defaults['n'] = n

            response_obj = client.images.generate(
                model=network.model_name,
                **{k: v for k, v in api_defaults.items() if k != 'model'},
            )

            urls = []
            for img in response_obj.data:
                img_url = img.url if hasattr(img, 'url') else None
                if img_url:
                    urls.append(img_url)

            if not urls:
                user.add_pages(cost)
                stars_returned = True
                return Response(
                    {'error': {'message': 'No images returned from upstream', 'type': 'api_error', 'code': 'no_images'}},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            result_data = [{'url': u} for u in urls]
            return Response({'created': int(__import__('time').time()), 'data': result_data})

        except Exception as e:
            if not stars_returned:
                user.add_pages(cost)
            logger.error(f'[API] Ошибка генерации изображения для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'generation_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
