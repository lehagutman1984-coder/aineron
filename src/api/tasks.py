"""
Celery-задачи для API-приложения.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_batch_job(self, job_id: int):
    """Обрабатывает все элементы пакетного задания последовательно."""
    from api.models import BatchJob, BatchJobItem
    from api.services.billing import charge_for_tokens
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client

    try:
        job = BatchJob.objects.get(pk=job_id)
    except BatchJob.DoesNotExist:
        logger.error(f'[Batch] Job {job_id} not found')
        return

    if job.status == BatchJob.Status.CANCELLED:
        return

    job.status = BatchJob.Status.IN_PROGRESS
    job.in_progress_at = timezone.now()
    job.save(update_fields=['status', 'in_progress_at'])

    client = get_laozhang_client()
    completed = 0
    failed = 0

    for item in job.items.filter(status=BatchJobItem.Status.PENDING):
        if BatchJob.objects.filter(pk=job_id, status=BatchJob.Status.CANCELLED).exists():
            break

        item.status = BatchJobItem.Status.IN_PROGRESS
        item.save(update_fields=['status'])

        try:
            body = item.body or {}
            model_id = body.get('model', '')
            messages = body.get('messages', [])
            temperature = body.get('temperature', 0.7)
            max_tokens = body.get('max_tokens')

            # Резолвим сеть
            network = None
            if model_id:
                try:
                    network = NeuralNetwork.objects.get(model_name=model_id, is_active=True)
                except NeuralNetwork.DoesNotExist:
                    pass

            kwargs = {'model': model_id or 'gpt-4o-mini', 'messages': messages, 'temperature': temperature}
            if max_tokens:
                kwargs['max_tokens'] = max_tokens
            elif network and network.max_tokens > 0:
                kwargs['max_tokens'] = network.max_tokens

            completion = client.chat.completions.create(**kwargs)
            usage_obj = completion.usage
            usage = {
                'prompt_tokens': usage_obj.prompt_tokens if usage_obj else 0,
                'completion_tokens': usage_obj.completion_tokens if usage_obj else 0,
                'total_tokens': usage_obj.total_tokens if usage_obj else 0,
            }

            response_body = {
                'id': f'chatcmpl-batch-{item.pk}',
                'object': 'chat.completion',
                'model': model_id,
                'choices': [
                    {
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': completion.choices[0].message.content or '',
                        },
                        'finish_reason': completion.choices[0].finish_reason or 'stop',
                    }
                ],
                'usage': usage,
            }

            if network:
                try:
                    charge_for_tokens(job.user, network, usage, api_key=job.api_key)
                except Exception as billing_err:
                    logger.warning(f'[Batch] Billing failed for item {item.pk}: {billing_err}')

            item.response_body = response_body
            item.status = BatchJobItem.Status.COMPLETED
            item.completed_at = timezone.now()
            item.save(update_fields=['response_body', 'status', 'completed_at'])
            completed += 1

        except Exception as e:
            logger.error(f'[Batch] Item {item.pk} failed: {e}')
            item.status = BatchJobItem.Status.FAILED
            item.error_message = str(e)
            item.completed_at = timezone.now()
            item.save(update_fields=['status', 'error_message', 'completed_at'])
            failed += 1

    # Финальный статус
    final_status = BatchJob.Status.COMPLETED if failed == 0 else BatchJob.Status.FAILED
    job.status = final_status
    job.completed_at = timezone.now()
    job.request_counts_completed = completed
    job.request_counts_failed = failed
    job.save(update_fields=['status', 'completed_at', 'request_counts_completed', 'request_counts_failed'])

    # Отправляем webhook-событие
    try:
        from api.services.webhooks import dispatch_event
        event = 'batch.completed' if final_status == BatchJob.Status.COMPLETED else 'batch.failed'
        dispatch_event(event, {'batch_id': job.pk, 'completed': completed, 'failed': failed}, user=job.user)
    except Exception:
        pass

    logger.info(f'[Batch] Job {job_id} done: {completed} ok, {failed} failed')
