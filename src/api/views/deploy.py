"""Sprint 7.2 — Internal deploy view.

POST /api/v1/internal/deploy/ — запускает INTERNAL_DEPLOY_SCRIPT (deploy.sh).

Безопасность:
  - Гейт: request.user.is_staff / is_superuser (NOT project owner — см. план).
  - Флаг INTERNAL_DEPLOY_ENABLED=0 по умолчанию (RCE-смежная поверхность).
  - subprocess.run([script], shell=False) — без интерполяции пользовательского ввода.
  - Whitelist скрипта из settings (INTERNAL_DEPLOY_SCRIPT).
  - Таймаут 120 с.
  - Rate-limit ≤1/30 с через Django cache.
"""

import subprocess
import time
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEY = 'internal_deploy_last_ts'
_RATE_LIMIT_INTERVAL = 30  # seconds


class InternalDeployView(APIView):
    """POST /api/v1/internal/deploy/ — запускает whitelist-скрипт на сервере.

    Доступно только is_staff/is_superuser. Флаг INTERNAL_DEPLOY_ENABLED=0 by default.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── Capability gate ──────────────────────────────────────────────────
        if not getattr(settings, 'INTERNAL_DEPLOY_ENABLED', False):
            return Response({'error': 'internal deploy disabled'}, status=503)

        # ── Staff/superuser gate (NOT project owner) ─────────────────────────
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'forbidden'}, status=403)

        # ── Rate limit: at most 1 request per 30 seconds ─────────────────────
        last_ts = cache.get(_RATE_LIMIT_KEY)
        now = time.time()
        if last_ts is not None and (now - last_ts) < _RATE_LIMIT_INTERVAL:
            wait = int(_RATE_LIMIT_INTERVAL - (now - last_ts))
            return Response({'error': f'rate limited — try again in {wait}s'}, status=429)

        # ── Script whitelist ─────────────────────────────────────────────────
        script = getattr(settings, 'INTERNAL_DEPLOY_SCRIPT', '')
        if not script:
            return Response({'error': 'INTERNAL_DEPLOY_SCRIPT not configured'}, status=500)

        # ── Execute: shell=False, no user input interpolation ────────────────
        cache.set(_RATE_LIMIT_KEY, now, _RATE_LIMIT_INTERVAL * 2)
        logger.info(f'[7.2] Internal deploy triggered by {request.user.email}')

        try:
            result = subprocess.run(
                [script],
                shell=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            stdout_tail = result.stdout[-2000:]
            stderr_tail = result.stderr[-500:]
            success = result.returncode == 0
            logger.info(f'[7.2] deploy exit={result.returncode} by {request.user.email}')

            return Response({
                'success': success,
                'exit_code': result.returncode,
                'stdout': stdout_tail,
                'stderr': stderr_tail,
            })
        except subprocess.TimeoutExpired:
            logger.error('[7.2] deploy timed out after 120s')
            return Response({'error': 'deploy timed out (120s)'}, status=504)
        except FileNotFoundError:
            logger.error(f'[7.2] deploy script not found: {script}')
            return Response({'error': f'script not found: {script}'}, status=500)
        except Exception as e:
            logger.error(f'[7.2] deploy failed: {e}')
            return Response({'error': str(e)}, status=500)
