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

        data = [
            {
                'id': n.model_name or n.slug,
                'object': 'model',
                'owned_by': 'aineron.ru',
                'name': n.name,
                'description': n.description,
                'cost_per_1k_tokens': float(n.stars_per_1k_tokens) if n.stars_per_1k_tokens else None,
                'cost_per_message': n.cost_per_message,
            }
            for n in networks
            if n.model_name
        ]
        return Response({'object': 'list', 'data': data})
