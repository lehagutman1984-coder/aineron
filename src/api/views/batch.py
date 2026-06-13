"""
Batch API — асинхронная пакетная обработка запросов.
POST   /api/v1/batches/         — создать пакет
GET    /api/v1/batches/         — список пакетов
GET    /api/v1/batches/{id}/    — статус пакета
GET    /api/v1/batches/{id}/results/ — результаты (NDJSON)
POST   /api/v1/batches/{id}/cancel/ — отмена
"""
import json
import logging

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from api.models import BatchJob, BatchJobItem, AuditLog

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 1000


def _ip(request):
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')


def _serialize_job(job: BatchJob) -> dict:
    return {
        'id': job.pk,
        'object': 'batch',
        'endpoint': job.endpoint,
        'completion_window': job.completion_window,
        'status': job.status,
        'request_counts': {
            'total': job.request_counts_total,
            'completed': job.request_counts_completed,
            'failed': job.request_counts_failed,
        },
        'metadata': job.metadata,
        'created_at': int(job.created_at.timestamp()),
        'in_progress_at': int(job.in_progress_at.timestamp()) if job.in_progress_at else None,
        'completed_at': int(job.completed_at.timestamp()) if job.completed_at else None,
        'cancelled_at': int(job.cancelled_at.timestamp()) if job.cancelled_at else None,
        'expires_at': int(job.expires_at.timestamp()) if job.expires_at else None,
    }


class BatchListCreateView(APIView):
    """GET/POST /api/v1/batches/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Список пакетных заданий', tags=['Batch'])
    def get(self, request):
        jobs = BatchJob.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response([_serialize_job(j) for j in jobs])

    @extend_schema(
        summary='Создать пакетное задание',
        tags=['Batch'],
        description='`requests` — массив объектов {custom_id, method, url, body}. Максимум 1000 запросов.',
    )
    def post(self, request):
        requests_data = request.data.get('requests', [])
        endpoint = request.data.get('endpoint', '/v1/chat/completions')
        completion_window = request.data.get('completion_window', '24h')
        metadata = request.data.get('metadata', {})

        if not isinstance(requests_data, list) or not requests_data:
            return Response({'error': {'message': "'requests' must be a non-empty list", 'type': 'invalid_request_error', 'code': 'missing_requests'}}, status=status.HTTP_400_BAD_REQUEST)
        if len(requests_data) > MAX_BATCH_SIZE:
            return Response({'error': {'message': f'Max {MAX_BATCH_SIZE} requests per batch', 'type': 'invalid_request_error', 'code': 'batch_too_large'}}, status=status.HTTP_400_BAD_REQUEST)

        api_key = getattr(request, 'api_key', None)
        org = getattr(api_key, 'organization', None) if api_key else None

        job = BatchJob.objects.create(
            user=request.user,
            api_key=api_key,
            organization=org,
            endpoint=endpoint,
            completion_window=completion_window,
            metadata=metadata,
            request_counts_total=len(requests_data),
            status=BatchJob.Status.VALIDATING,
            expires_at=timezone.now() + __import__('datetime').timedelta(hours=24),
        )

        items = [
            BatchJobItem(
                job=job,
                custom_id=str(r.get('custom_id', '')),
                method=str(r.get('method', 'POST')).upper(),
                url=str(r.get('url', endpoint)),
                body=r.get('body', {}),
            )
            for r in requests_data
        ]
        BatchJobItem.objects.bulk_create(items)

        # Запускаем обработку асинхронно
        try:
            from api.tasks import process_batch_job
            process_batch_job.delay(job.pk)
        except Exception as e:
            logger.warning(f'[Batch] Failed to enqueue job {job.pk}: {e}')

        AuditLog.log(request.user, AuditLog.Action.BATCH_CREATED, 'batch', job.pk, metadata={'total': len(requests_data)}, ip_address=_ip(request), organization=org)
        return Response(_serialize_job(job), status=status.HTTP_201_CREATED)


class BatchDetailView(APIView):
    """GET /api/v1/batches/{id}/"""
    permission_classes = [IsAuthenticated]

    def _get_job(self, request, pk):
        try:
            return BatchJob.objects.get(pk=pk, user=request.user)
        except BatchJob.DoesNotExist:
            return None

    @extend_schema(summary='Статус пакетного задания', tags=['Batch'])
    def get(self, request, pk):
        job = self._get_job(request, pk)
        if not job:
            return Response({'error': {'message': 'Batch not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_job(job))


class BatchResultsView(APIView):
    """GET /api/v1/batches/{id}/results/ — NDJSON поток результатов."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Результаты пакетного задания (NDJSON)', tags=['Batch'])
    def get(self, request, pk):
        try:
            job = BatchJob.objects.get(pk=pk, user=request.user)
        except BatchJob.DoesNotExist:
            return Response({'error': {'message': 'Batch not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)

        if job.status not in (BatchJob.Status.COMPLETED, BatchJob.Status.FAILED):
            return Response({'error': {'message': f'Batch is not completed yet (status: {job.status})', 'type': 'invalid_request_error', 'code': 'batch_not_completed'}}, status=status.HTTP_400_BAD_REQUEST)

        def generate():
            for item in job.items.all():
                row = {
                    'id': item.pk,
                    'custom_id': item.custom_id,
                    'status': item.status,
                    'response': item.response_body,
                    'error': item.error_message or None,
                }
                yield json.dumps(row, ensure_ascii=False) + '\n'

        return StreamingHttpResponse(generate(), content_type='application/x-ndjson')


class BatchCancelView(APIView):
    """POST /api/v1/batches/{id}/cancel/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Отменить пакетное задание', tags=['Batch'])
    def post(self, request, pk):
        try:
            job = BatchJob.objects.get(pk=pk, user=request.user)
        except BatchJob.DoesNotExist:
            return Response({'error': {'message': 'Batch not found', 'type': 'not_found', 'code': 'not_found'}}, status=status.HTTP_404_NOT_FOUND)

        if job.status in (BatchJob.Status.COMPLETED, BatchJob.Status.CANCELLED, BatchJob.Status.FAILED):
            return Response({'error': {'message': f'Cannot cancel batch with status: {job.status}', 'type': 'invalid_request_error', 'code': 'cannot_cancel'}}, status=status.HTTP_400_BAD_REQUEST)

        job.status = BatchJob.Status.CANCELLED
        job.cancelled_at = timezone.now()
        job.save(update_fields=['status', 'cancelled_at'])

        # Отменяем pending элементы
        BatchJobItem.objects.filter(job=job, status=BatchJobItem.Status.PENDING).update(
            status=BatchJobItem.Status.FAILED, error_message='Batch cancelled by user'
        )

        AuditLog.log(request.user, AuditLog.Action.BATCH_CANCELLED, 'batch', job.pk, ip_address=_ip(request))
        return Response(_serialize_job(job))
