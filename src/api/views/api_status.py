"""
GET /api/v1/status/ — публичная проверка состояния API.
"""
import logging
import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from aitext.tasks import get_laozhang_client

logger = logging.getLogger(__name__)


class APIStatusView(APIView):
    """GET /api/v1/status/"""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Статус API',
        tags=['Status'],
        description='Возвращает состояние сервисов: БД, Redis, upstream (laozhang.ai).',
    )
    def get(self, request):
        checks = {}
        overall = 'operational'

        # Проверка БД
        t0 = time.monotonic()
        try:
            from django.db import connection
            connection.ensure_connection()
            checks['database'] = {'status': 'operational', 'latency_ms': round((time.monotonic() - t0) * 1000)}
        except Exception as e:
            checks['database'] = {'status': 'degraded', 'error': str(e)}
            overall = 'degraded'

        # Проверка Redis (Celery broker)
        t0 = time.monotonic()
        try:
            from django.core.cache import cache
            cache.set('_status_check', '1', timeout=5)
            assert cache.get('_status_check') == '1'
            checks['cache'] = {'status': 'operational', 'latency_ms': round((time.monotonic() - t0) * 1000)}
        except Exception as e:
            checks['cache'] = {'status': 'degraded', 'error': str(e)}
            overall = 'degraded'

        # Upstream — просто проверяем доступность модели без реального запроса
        try:
            from aitext.models import NeuralNetwork
            count = NeuralNetwork.objects.filter(is_active=True).count()
            checks['upstream'] = {'status': 'operational', 'active_models': count}
        except Exception as e:
            checks['upstream'] = {'status': 'unknown', 'error': str(e)}

        return Response({
            'status': overall,
            'checks': checks,
            'timestamp': int(time.time()),
        })
