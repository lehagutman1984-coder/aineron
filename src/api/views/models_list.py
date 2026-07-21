from urllib.parse import urlparse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from aitext.models import NeuralNetwork


class ModelsListView(APIView):
    """GET /api/v1/models — список доступных моделей в OpenAI-формате."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Список моделей', tags=['Models'])
    def get(self, request):
        networks = NeuralNetwork.objects.filter(
            is_active=True,
            provider='openrouter',
        ).order_by('order', 'name')

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        owned_by = urlparse(site_url).netloc or 'aineron.ru'

        data = [
            {
                'id': n.model_name or n.slug,
                'object': 'model',
                'owned_by': owned_by,
                'name': n.name,
                'description': n.description,
                'cost_per_1k_tokens': float(n.stars_per_1k_tokens) if n.stars_per_1k_tokens else None,
                'cost_per_message': n.cost_per_message,
                'cost_kopecks': n.cost_kopecks,
                'kopecks_per_1k_tokens': float(n.kopecks_per_1k_tokens) if n.kopecks_per_1k_tokens else None,
            }
            for n in networks
            if n.model_name
        ]
        return Response({'object': 'list', 'data': data})
