"""
Celery-задачи для API-приложения.
"""
import hashlib
import hmac
import json
import logging

import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [10, 60, 300]


@shared_task(bind=True, max_retries=3, name='api.tasks.deliver_webhook')
def deliver_webhook(self, webhook_id: int, event_type: str, payload: dict):
    """Доставляет одно webhook-событие с HMAC-подписью. Повтор через Celery retry."""
    from api.models import Webhook
    from studio.security import is_safe_url

    try:
        webhook = Webhook.objects.get(pk=webhook_id, is_active=True)
    except Webhook.DoesNotExist:
        return

    # 2026-10-01 (аудит безопасности, SSRF): url уже проверен is_safe_url при
    # создании (api/views/webhooks.py), но ПЕРЕПРОВЕРЯЕМ здесь тоже — защита
    # от DNS rebinding (hostname мог резолвиться в публичный IP на момент
    # создания и смениться на приватный к моменту доставки, которая может
    # случиться через retry спустя минуты). is_safe_url сам делает свежий
    # getaddrinfo при каждом вызове.
    if not is_safe_url(webhook.url):
        logger.error(f'[Webhook] {webhook.url} не прошёл is_safe_url на доставке (webhook_id={webhook_id}) — пропуск, retry не делаем')
        return

    body = json.dumps({'event': event_type, 'data': payload}, ensure_ascii=False).encode()
    sig = hmac.new(webhook.secret.encode(), body, digestmod=hashlib.sha256).hexdigest()
    headers = {
        'Content-Type': 'application/json',
        'X-Aineron-Signature': f'sha256={sig}',
        'X-Aineron-Event': event_type,
        'User-Agent': 'aineron.ru/webhooks/1.0',
    }

    try:
        # allow_redirects=False: редирект на внутренний адрес обходил бы
        # is_safe_url выше (он проверяет только исходный url).
        resp = requests.post(webhook.url, data=body, headers=headers, timeout=10, allow_redirects=False)
        resp.raise_for_status()
        Webhook.objects.filter(pk=webhook_id).update(last_triggered_at=timezone.now())
        logger.info(f'[Webhook] Delivered {event_type} to {webhook.url} status={resp.status_code}')
    except Exception as exc:
        attempt = self.request.retries
        delay = _RETRY_DELAYS[attempt] if attempt < len(_RETRY_DELAYS) else 300
        logger.warning(f'[Webhook] attempt {attempt + 1} failed for {webhook.url}: {exc}')
        raise self.retry(exc=exc, countdown=delay)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_batch_job(self, job_id: int):
    """Обрабатывает все элементы пакетного задания последовательно."""
    from api.models import BatchJob, BatchJobItem
    from api.exceptions import InsufficientStarsError
    from api.services.billing import (
        estimate_messages_tokens, estimate_text_tokens, release_reservation,
        reserve_for_request, settle_reservation,
    )
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client
    from core.model_limits import clamp_max_tokens

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

            # Резолвим сеть. Раньше при неизвестной модели запрос всё равно уходил
            # апстриму (подставлялась 'gpt-4o-mini') и НЕ биллился, а сбой
            # списания только логировался - бесплатная генерация. Теперь модель
            # обязана быть в каталоге (как в /chat/completions), иначе item падает
            # без вызова апстрима.
            network = None
            if model_id:
                network = NeuralNetwork.objects.filter(
                    model_name=model_id, is_active=True, provider='openrouter',
                ).first()
            if network is None:
                raise ValueError(f"model_not_found: model '{model_id}' is not available")

            # Rule S — см. api/views/chat.py для полного обоснования. По item,
            # не по всей джобе: один заблокированный item не должен ронять
            # остальные, тот же паттерн, что model_not_found/insufficient_quota
            # выше — ValueError ловится общим except ниже и метит только этот item.
            _batch_org = getattr(job.api_key, 'organization', None) if job.api_key else None
            if _batch_org is None and job.user.is_unpaid_free_user():
                from core import model_pricing
                if model_pricing.is_model_blocked_for_trial(network):
                    raise ValueError(f"requires_paid_plan: model '{model_id}' is not available on the trial plan")

            requested_max = clamp_max_tokens(
                max_tokens or (network.max_tokens if network.max_tokens > 0 else None),
                network.model_name,
            )
            # Резерв ДО вызова апстрима; при нехватке средств item падает как
            # insufficient_quota (апстрим не вызывается).
            try:
                res = reserve_for_request(
                    job.user, job.api_key, network, estimate_messages_tokens(messages), requested_max,
                )
            except InsufficientStarsError as billing_err:
                raise ValueError(f'insufficient_quota: {billing_err}')

            kwargs = {
                'model': model_id,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': res.max_tokens,
            }

            try:
                completion = client.chat.completions.create(**kwargs)
            except Exception:
                release_reservation(res, 'batch upstream error')
                raise
            usage_obj = completion.usage
            usage = {
                'prompt_tokens': usage_obj.prompt_tokens if usage_obj else 0,
                'completion_tokens': usage_obj.completion_tokens if usage_obj else 0,
                'total_tokens': usage_obj.total_tokens if usage_obj else 0,
            }
            _text = completion.choices[0].message.content or ''
            settle_reservation(res, usage, estimate_text_tokens(_text))

            response_body = {
                'id': f'chatcmpl-batch-{item.pk}',
                'object': 'chat.completion',
                'model': model_id,
                'choices': [
                    {
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': _text,
                        },
                        'finish_reason': completion.choices[0].finish_reason or 'stop',
                    }
                ],
                'usage': usage,
            }

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


@shared_task(name='api.tasks.reset_monthly_seats', ignore_result=True)
def reset_monthly_seats():
    """
    Run on the 1st of each month (registered via DatabaseScheduler).
    Resets OrganizationMember.monthly_used to 0 for all members.
    """
    from teams.models import OrganizationMember

    today = timezone.now().date()
    updated = OrganizationMember.objects.filter(
        organization__seat_monthly_stars__gt=0
    ).update(monthly_used=0, monthly_reset_at=today)
    logger.info(f'[Seats] Monthly quota reset for {updated} members')


@shared_task(bind=True, max_retries=0, ignore_result=True,
             name='api.tasks.reconcile_stuck_api_reservations')
def reconcile_stuck_api_reservations(self):
    """
    2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, №17):
    api:{request_id} резервы (reserve_for_request в api/services/billing.py,
    /v1/chat/completions и /v1/messages dev-API) не покрыты
    aitext.tasks.reconcile_stuck_spends — та ищет aitext.Message.status, а у
    api:-резервов своего Message вообще нет, они привязаны к TokenUsage.
    Падение воркера/процесса между reserve_for_request и
    settle_reservation/release_reservation замораживает worst-case резерв
    (prompt+max_tokens) у пользователя НАВСЕГДА — в отличие от платежей
    (Crypto Pay/Trybit), тут нет второго независимого пути проверки
    (ни вебхука, ни поллинга статуса).

    Детекция: BalanceTransaction(type='spend', reference начинается с 'api:')
    без (а) парной refund-транзакции с ТЕМ ЖЕ reference И (б) TokenUsage с
    совпадающим request_id (TokenUsage.request_id хранит ПЕРВЫЕ 8 символов
    12-символьного request_id — см. settle_reservation). По отдельности
    любой из двух признаков недостаточен: settle_reservation не создаёт
    refund-транзакцию, если факт совпал с резервом ровно (diff=0) — тогда
    есть TokenUsage, но нет refund, и это НЕ аномалия.

    Мониторинг-only, как reconcile_stuck_spends/reconcile_unsettled_overage
    рядом — алерт админам, не авто-возврат: решение по непроверенным данным
    остаётся за человеком.
    """
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone as tz
    from users.models import BalanceTransaction
    from api.models import TokenUsage
    from telegram_bot.notify import notify_admins
    from core.money import format_rub

    now = tz.now()
    # Те же границы, что у aitext.tasks.reconcile_stuck_spends: младше 20 минут
    # — запрос ещё может быть в процессе (ретраи апстрима), старше 6 часов —
    # вне окна, чтобы не пересканировать всю историю на каждый прогон.
    window_start = now - timedelta(hours=6)
    window_end = now - timedelta(minutes=20)

    candidates = BalanceTransaction.objects.filter(
        type=BalanceTransaction.Type.SPEND,
        reference__startswith='api:',
        created_at__gte=window_start,
        created_at__lt=window_end,
    )

    anomalies = []
    for tx in candidates.iterator():
        _, _, request_id = tx.reference.partition(':')
        if not request_id:
            continue
        has_refund = BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.REFUND, reference=tx.reference,
        ).exists()
        if has_refund:
            continue
        has_usage = TokenUsage.objects.filter(request_id=request_id[:8]).exists()
        if has_usage:
            continue
        # Не алертить один и тот же reference чаще раза в 6 часов.
        if not cache.add(f'monitor_stuck_api_reserve:{tx.reference}', 1, timeout=6 * 3600):
            continue
        anomalies.append(tx)

    if not anomalies:
        return

    lines = [f'api:-резервы без результата за 20мин–6ч: {len(anomalies)}']
    for tx in anomalies[:20]:
        lines.append(f'· {tx.reference} — {format_rub(abs(tx.amount_kopecks))}, user_id={tx.user_id}')
    if len(anomalies) > 20:
        lines.append(f'...и ещё {len(anomalies) - 20}')
    notify_admins('<b>Мониторинг: api-резервы без результата</b>\n' + '\n'.join(lines))
