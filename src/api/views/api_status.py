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
        description='Возвращает состояние сервисов: БД, Redis, AI-сервис.',
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

        # Preview service (E2B) — informational, не влияет на overall
        try:
            import os as _os
            import requests as _req
            _prev_url = _os.environ.get('PREVIEW_SERVICE_URL', '')
            _prev_token = _os.environ.get('PREVIEW_INTERNAL_TOKEN', '')
            if _prev_url and _prev_token:
                t0 = time.monotonic()
                _r = _req.get(
                    f'{_prev_url}/metrics',
                    headers={'X-Internal-Token': _prev_token},
                    timeout=3,
                )
                if _r.ok:
                    _m = _r.json()
                    checks['preview'] = {
                        'status': 'operational',
                        'latency_ms': round((time.monotonic() - t0) * 1000),
                        'p95_s': _m.get('p95_s'),
                        'hit_rate': _m.get('hit_rate'),
                        'slots_used': _m.get('slots_used'),
                        'max_concurrent': _m.get('max_concurrent'),
                    }
                else:
                    checks['preview'] = {'status': 'degraded', 'error': f'HTTP {_r.status_code}'}
            else:
                checks['preview'] = {'status': 'unknown'}
        except Exception as exc:
            checks['preview'] = {'status': 'unknown', 'error': str(exc)[:100]}

        # Sandbox API — informational, не влияет на overall
        try:
            from django.conf import settings as _settings
            if getattr(_settings, 'SANDBOX_API_ENABLED', False):
                from sandboxes.models import SandboxSession
                active = SandboxSession.objects.filter(
                    state__in=SandboxSession.ACTIVE_STATES,
                ).count()
                checks['sandboxes'] = {'status': 'operational', 'active_sessions': active}
        except Exception as exc:
            checks['sandboxes'] = {'status': 'unknown', 'error': str(exc)[:100]}

        return Response({
            'status': overall,
            'checks': checks,
            'timestamp': int(time.time()),
        })
