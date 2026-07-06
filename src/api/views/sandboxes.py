"""
Sandbox API — публичные эндпоинты /api/v1/sandboxes/ (SANDBOX_API_PLAN.md).

Изолированные microVM для исполнения недоверенного кода: create → exec/files →
logs → delete. Тонкий слой над preview-service: здесь авторизация, скоуп ключа,
квоты, биллинг (резерв → settle), идемпотентность и аудит.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from api.models import AuditLog
from api.serializers.sandboxes import (
    SandboxCreateSerializer,
    SandboxExecSerializer,
    SandboxTimeoutSerializer,
    SandboxWriteFilesSerializer,
    validate_sandbox_path,
)
from api.throttling import SandboxCreateThrottle, SandboxExecThrottle
from sandboxes import billing, client, quotas
from sandboxes.client import PreviewServiceError
from sandboxes.models import SandboxSession

logger = logging.getLogger(__name__)

_IDEM_TTL = 86400  # 24 ч


def _err(message: str, code: str, http_status: int) -> Response:
    return Response(
        {'error': {'message': message, 'type': 'invalid_request_error', 'code': code}},
        status=http_status,
    )


def _ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _session_payload(session: SandboxSession) -> dict:
    return {
        'id': session.public_id,
        'template': session.template,
        'size': session.size,
        'state': session.state,
        'public_host': session.public_host,
        'started_at': session.started_at.isoformat() if session.started_at else None,
        'expires_at': session.expires_at.isoformat() if session.expires_at else None,
        'stopped_at': session.stopped_at.isoformat() if session.stopped_at else None,
        'price_kopecks_per_min': billing.price_per_min_kopecks(session.size),
        'charged_kopecks': session.charged_kopecks,
        'metadata': session.metadata,
    }


class SandboxBaseView(APIView):
    """Общий гейт: флаг → shadow ban → скоуп ключа."""
    permission_classes = [IsAuthenticated]

    def gate(self, request) -> Response | None:
        if not getattr(settings, 'SANDBOX_API_ENABLED', False):
            return _err('Not found.', 'not_found', status.HTTP_404_NOT_FOUND)
        if getattr(request.user, 'shadow_banned', False):
            return _err('Account is not allowed to use sandboxes.',
                        'account_restricted', status.HTTP_403_FORBIDDEN)
        api_key = getattr(request, 'api_key', None)
        if api_key is not None and 'sandboxes' not in (api_key.scopes or []):
            return _err(
                'This API key does not have the "sandboxes" scope. '
                'Create a key with the scope enabled at /account/keys/.',
                'missing_scope', status.HTTP_403_FORBIDDEN,
            )
        return None

    def get_session(self, request, sandbox_id: str) -> SandboxSession | None:
        pk = SandboxSession.parse_public_id(sandbox_id)
        if pk is None:
            return None
        return SandboxSession.objects.filter(pk=pk, user=request.user).first()

    # ── идемпотентность (Idempotency-Key, как у Stripe) ────────────────────────

    def _idem_cache_key(self, request) -> str | None:
        raw = request.headers.get('Idempotency-Key', '').strip()
        if not raw or len(raw) > 255:
            return None
        digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return f'sandbox_idem:{request.user.pk}:{digest}'

    def idem_get(self, request):
        key = self._idem_cache_key(request)
        if not key:
            return None
        try:
            cached = cache.get(key)
        except Exception:
            return None
        if cached:
            return Response(cached['body'], status=cached['status'])
        return None

    def idem_store(self, request, response: Response):
        key = self._idem_cache_key(request)
        if not key:
            return
        try:
            cache.set(key, {'body': response.data, 'status': response.status_code}, _IDEM_TTL)
        except Exception:
            pass


class SandboxListCreateView(SandboxBaseView):
    """GET /api/v1/sandboxes/ — список; POST — создать песочницу."""
    throttle_classes = [SandboxCreateThrottle]

    @extend_schema(summary='Список песочниц', tags=['Sandboxes'])
    def get(self, request):
        gate = self.gate(request)
        if gate:
            return gate
        qs = SandboxSession.objects.filter(user=request.user)
        if request.query_params.get('all') != '1':
            qs = qs.filter(state__in=SandboxSession.ACTIVE_STATES)
        return Response({'data': [_session_payload(s) for s in qs[:100]]})

    @extend_schema(summary='Создать песочницу', tags=['Sandboxes'])
    def post(self, request):
        gate = self.gate(request)
        if gate:
            return gate

        cached = self.idem_get(request)
        if cached:
            return cached

        serializer = SandboxCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _err(str(serializer.errors), 'validation_error', status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        ttl = data.get('timeout_seconds') or int(getattr(settings, 'SANDBOX_DEFAULT_TTL', 300))

        allowed, active, limit = quotas.check_concurrent(request.user)
        if not allowed:
            return _err(
                f'Concurrent sandbox limit reached ({active}/{limit}). Stop a session first.',
                'concurrency_limit', status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cap_ok, used_min, cap_min = quotas.check_and_reserve_daily_cap(request.user.pk, ttl)
        if not cap_ok:
            return _err(
                f'Daily sandbox minutes cap reached ({used_min}/{cap_min} min). Try again tomorrow.',
                'daily_cap', status.HTTP_429_TOO_MANY_REQUESTS,
            )

        session = SandboxSession.objects.create(
            user=request.user,
            api_key=getattr(request, 'api_key', None),
            template=data['template'],
            size=data['size'],
            ttl_seconds=ttl,
            metadata=data.get('metadata') or {},
        )

        if not billing.reserve(request.user, session):
            quotas.refund_daily_cap(request.user.pk, ttl)
            session.state = SandboxSession.State.FAILED
            session.save(update_fields=['state'])
            need = billing.max_cost_kopecks(session.size, ttl)
            return _err(
                f'Insufficient balance: sandbox reserve is {need / 100:.2f} RUB '
                f'({ttl // 60} min × {billing.price_per_min_kopecks(session.size) / 100:.2f} RUB/min).',
                'insufficient_balance', status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            created = client.create(
                str(session.id), session.template, session.size, ttl,
                data.get('env') or {}, str(request.user.pk),
            )
        except PreviewServiceError as exc:
            billing.refund_full(session)
            quotas.refund_daily_cap(request.user.pk, ttl)
            if exc.status == 429:
                return _err(str(exc), 'capacity_limit', status.HTTP_429_TOO_MANY_REQUESTS)
            logger.error('[sandbox] create failed for %s: %s', session.public_id, exc)
            return _err('Sandbox provisioning failed. You have not been charged.',
                        'provisioning_error', status.HTTP_502_BAD_GATEWAY)

        session.state = SandboxSession.State.RUNNING
        session.public_host = created.get('public_host', '')
        session.started_at = timezone.now()
        session.expires_at = session.started_at + timezone.timedelta(seconds=ttl)
        session.save(update_fields=['state', 'public_host', 'started_at', 'expires_at'])

        AuditLog.log(request.user, AuditLog.Action.SANDBOX_CREATED, 'sandbox',
                     session.public_id,
                     metadata={'template': session.template, 'size': session.size, 'ttl': ttl},
                     ip_address=_ip(request))

        response = Response(_session_payload(session), status=status.HTTP_201_CREATED)
        self.idem_store(request, response)
        return response


class SandboxDetailView(SandboxBaseView):
    """GET /api/v1/sandboxes/{id}/ — статус; DELETE — остановить (kill + settle)."""

    @extend_schema(summary='Статус песочницы', tags=['Sandboxes'])
    def get(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        return Response(_session_payload(session))

    @extend_schema(summary='Остановить песочницу', tags=['Sandboxes'])
    def delete(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate

        cached = self.idem_get(request)
        if cached:
            return cached

        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        if session.state not in SandboxSession.ACTIVE_STATES:
            return Response({'deleted': True, 'id': session.public_id,
                             'charged_kopecks': session.charged_kopecks})

        duration = float(session.ttl_seconds)
        try:
            result = client.kill(str(session.id))
            if result.get('duration_seconds'):
                duration = float(result['duration_seconds'])
        except PreviewServiceError as exc:
            # VM могла умереть сама (e2b timeout) — закрываем по полному TTL
            logger.warning('[sandbox] kill %s: %s', session.public_id, exc)

        charged = billing.settle(session, duration)
        session.state = SandboxSession.State.STOPPED
        session.save(update_fields=['state'])

        AuditLog.log(request.user, AuditLog.Action.SANDBOX_DELETED, 'sandbox',
                     session.public_id,
                     metadata={'charged_kopecks': charged,
                               'duration_seconds': round(duration, 1)},
                     ip_address=_ip(request))

        response = Response({'deleted': True, 'id': session.public_id,
                             'duration_seconds': round(duration, 1),
                             'charged_kopecks': charged})
        self.idem_store(request, response)
        return response


class SandboxExecView(SandboxBaseView):
    """POST /api/v1/sandboxes/{id}/exec/ — выполнить команду или код."""
    throttle_classes = [SandboxExecThrottle]

    @extend_schema(summary='Выполнить команду в песочнице', tags=['Sandboxes'])
    def post(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        if session.state not in SandboxSession.ACTIVE_STATES:
            return _err(f'Sandbox is {session.state}', 'sandbox_not_running',
                        status.HTTP_409_CONFLICT)

        serializer = SandboxExecSerializer(data=request.data)
        if not serializer.is_valid():
            return _err(str(serializer.errors), 'validation_error', status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        try:
            result = client.exec_(str(session.id), {
                'command': data.get('command', ''),
                'code': data.get('code', ''),
                'language': data['language'],
                'timeout': data['timeout_seconds'],
                'cwd': data['cwd'],
                'background': data['background'],
            })
        except PreviewServiceError as exc:
            if exc.status == 404:
                return _err('Sandbox expired', 'sandbox_expired', status.HTTP_409_CONFLICT)
            return _err(f'Exec failed: {exc}', 'exec_error', status.HTTP_502_BAD_GATEWAY)

        SandboxSession.objects.filter(pk=session.pk).update(exec_count=F('exec_count') + 1)
        return Response(result)


class SandboxFilesView(SandboxBaseView):
    """POST /api/v1/sandboxes/{id}/files/ — записать; GET ?path= — прочитать/листинг."""

    @extend_schema(summary='Записать файлы в песочницу', tags=['Sandboxes'])
    def post(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        if session.state not in SandboxSession.ACTIVE_STATES:
            return _err(f'Sandbox is {session.state}', 'sandbox_not_running',
                        status.HTTP_409_CONFLICT)

        serializer = SandboxWriteFilesSerializer(data=request.data)
        if not serializer.is_valid():
            return _err(str(serializer.errors), 'validation_error', status.HTTP_400_BAD_REQUEST)

        try:
            result = client.write_files(str(session.id), serializer.validated_data['files'])
        except PreviewServiceError as exc:
            if exc.status == 404:
                return _err('Sandbox expired', 'sandbox_expired', status.HTTP_409_CONFLICT)
            return _err(f'Write failed: {exc}', 'files_error', status.HTTP_502_BAD_GATEWAY)
        return Response(result)

    @extend_schema(summary='Прочитать файл / листинг директории', tags=['Sandboxes'])
    def get(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)

        path = request.query_params.get('path', '')
        op = request.query_params.get('op', 'read')
        if op not in ('read', 'list'):
            return _err('op must be "read" or "list"', 'validation_error',
                        status.HTTP_400_BAD_REQUEST)
        try:
            validate_sandbox_path(path)
        except Exception as exc:
            return _err(str(exc), 'validation_error', status.HTTP_400_BAD_REQUEST)

        try:
            result = client.read_file(str(session.id), path, op=op)
        except PreviewServiceError as exc:
            if exc.status == 404:
                return _err('Sandbox expired', 'sandbox_expired', status.HTTP_409_CONFLICT)
            return _err(f'Read failed: {exc}', 'files_error', status.HTTP_502_BAD_GATEWAY)
        return Response(result)


class SandboxLogsView(SandboxBaseView):
    """GET /api/v1/sandboxes/{id}/logs/ — хвост лога background-процессов."""

    @extend_schema(summary='Логи песочницы', tags=['Sandboxes'])
    def get(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        try:
            lines = int(request.query_params.get('lines', 100))
        except ValueError:
            lines = 100
        try:
            result = client.logs(str(session.id), lines=max(1, min(lines, 500)))
        except PreviewServiceError as exc:
            if exc.status == 404:
                return _err('Sandbox expired', 'sandbox_expired', status.HTTP_409_CONFLICT)
            return _err(f'Logs failed: {exc}', 'logs_error', status.HTTP_502_BAD_GATEWAY)
        return Response({'id': session.public_id, 'lines': result.get('lines', [])})


class SandboxLogsStreamView(SandboxBaseView):
    """GET /api/v1/sandboxes/{id}/logs/stream/ — SSE-стрим лога (proxy к preview-service)."""
    from api.views.generations import EventStreamRenderer as _ESR
    renderer_classes = [_ESR]

    @extend_schema(summary='SSE-стрим логов песочницы', tags=['Sandboxes'])
    def get(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)

        import requests as _rq
        from django.http import StreamingHttpResponse

        base = getattr(settings, 'PREVIEW_SERVICE_URL', 'http://preview_service:8001').rstrip('/')
        headers = {
            'X-Internal-Token': getattr(settings, 'PREVIEW_INTERNAL_TOKEN', ''),
            'Accept': 'text/event-stream',
        }

        def _stream():
            try:
                with _rq.get(
                    f'{base}/sandbox/{session.id}/logs/stream',
                    headers=headers, stream=True, timeout=(5, 300),
                ) as resp:
                    for chunk in resp.iter_content(chunk_size=None):
                        if chunk:
                            yield chunk
            except Exception:
                yield b'event: close\ndata: {}\n\n'

        response = StreamingHttpResponse(_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class SandboxTimeoutView(SandboxBaseView):
    """POST /api/v1/sandboxes/{id}/timeout/ — новый TTL от текущего момента
    (продление резервирует дополнительные минуты в биллинге и дневном капе)."""

    @extend_schema(summary='Продлить/сократить TTL песочницы', tags=['Sandboxes'])
    def post(self, request, sandbox_id):
        gate = self.gate(request)
        if gate:
            return gate
        session = self.get_session(request, sandbox_id)
        if session is None:
            return _err('Sandbox not found', 'not_found', status.HTTP_404_NOT_FOUND)
        if session.state not in SandboxSession.ACTIVE_STATES:
            return _err(f'Sandbox is {session.state}', 'sandbox_not_running',
                        status.HTTP_409_CONFLICT)

        serializer = SandboxTimeoutSerializer(data=request.data)
        if not serializer.is_valid():
            return _err(str(serializer.errors), 'validation_error', status.HTTP_400_BAD_REQUEST)
        new_ttl = serializer.validated_data['timeout_seconds']

        # Общая длительность после продления не должна превысить SANDBOX_MAX_TTL
        already = (timezone.now() - session.started_at).total_seconds() if session.started_at else 0
        max_ttl = int(getattr(settings, 'SANDBOX_MAX_TTL', 3600))
        if already + new_ttl > max_ttl:
            return _err(f'Total sandbox lifetime must be ≤ {max_ttl}s', 'max_ttl',
                        status.HTTP_400_BAD_REQUEST)

        # Дорезервировать разницу, если новый горизонт дороже старого резерва
        import math
        total_minutes = math.ceil((already + new_ttl) / 60)
        need = total_minutes * billing.price_per_min_kopecks(session.size)
        extra = need - session.reserved_kopecks
        if extra > 0:
            cap_ok, used_min, cap_min = quotas.check_and_reserve_daily_cap(
                request.user.pk, extra // billing.price_per_min_kopecks(session.size) * 60 or 60,
            )
            if not cap_ok:
                return _err(f'Daily cap reached ({used_min}/{cap_min} min)', 'daily_cap',
                            status.HTTP_429_TOO_MANY_REQUESTS)
            ok = request.user.spend_kopecks(
                extra, type='sandbox',
                reference=f'sandbox:{session.pk}:extend:{total_minutes}',
            )
            if not ok:
                return _err('Insufficient balance for extension.', 'insufficient_balance',
                            status.HTTP_402_PAYMENT_REQUIRED)
            session.reserved_kopecks += extra

        try:
            client.set_timeout(str(session.id), new_ttl)
        except PreviewServiceError as exc:
            if exc.status == 404:
                return _err('Sandbox expired', 'sandbox_expired', status.HTTP_409_CONFLICT)
            return _err(f'Timeout update failed: {exc}', 'timeout_error',
                        status.HTTP_502_BAD_GATEWAY)

        session.expires_at = timezone.now() + timezone.timedelta(seconds=new_ttl)
        session.ttl_seconds = int(already + new_ttl)
        session.save(update_fields=['expires_at', 'ttl_seconds', 'reserved_kopecks'])
        return Response(_session_payload(session))
