"""
GET  /v1/ab-tests/       — list A/B tests (staff only)
POST /v1/ab-tests/       — create test
GET  /v1/ab-tests/<pk>/results/ — variant stats from UsageEvent
"""
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from aitext.models import PromptABTest, UsageEvent


class ABTestListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        tests = PromptABTest.objects.select_related('network').order_by('-created_at')
        return Response([
            {
                'id': t.id,
                'name': t.name,
                'network': t.network.name,
                'network_id': t.network_id,
                'is_active': t.is_active,
                'sends_a': t.sends_a,
                'sends_b': t.sends_b,
                'created_at': t.created_at.isoformat(),
            }
            for t in tests
        ])

    def post(self, request):
        network_id = request.data.get('network_id')
        name = request.data.get('name', '').strip()
        prompt_a = request.data.get('prompt_a', '').strip()
        prompt_b = request.data.get('prompt_b', '').strip()
        if not all([network_id, name, prompt_a, prompt_b]):
            return Response({'error': 'network_id, name, prompt_a, prompt_b are required'}, status=400)

        from aitext.models import NeuralNetwork
        try:
            network = NeuralNetwork.objects.get(id=network_id)
        except NeuralNetwork.DoesNotExist:
            return Response({'error': 'Network not found'}, status=404)

        test = PromptABTest.objects.create(
            network=network, name=name,
            prompt_a=prompt_a, prompt_b=prompt_b,
            is_active=request.data.get('is_active', True),
        )
        return Response({'id': test.id, 'name': test.name}, status=status.HTTP_201_CREATED)


class ABTestResultsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        try:
            test = PromptABTest.objects.get(id=pk)
        except PromptABTest.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        # Count UsageEvents where meta has ab_test_id = pk
        events_a = UsageEvent.objects.filter(
            meta__ab_test_id=pk, meta__ab_variant='a'
        ).count()
        events_b = UsageEvent.objects.filter(
            meta__ab_test_id=pk, meta__ab_variant='b'
        ).count()

        return Response({
            'test': {
                'id': test.id,
                'name': test.name,
                'network': test.network.name,
                'is_active': test.is_active,
                'sends_a': test.sends_a,
                'sends_b': test.sends_b,
            },
            'usage_events': {
                'variant_a': events_a,
                'variant_b': events_b,
                'total': events_a + events_b,
            },
        })
