"""
Celery-задачи Sandbox API: reconcile подвешенного биллинга и анти-abuse проверка.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='sandboxes.tasks.reconcile_sandbox_billing')
def reconcile_sandbox_billing():
    """Каждые 5 мин: закрыть сессии с истёкшим expires_at, которые клиент не
    остановил сам (упал, забыл, сеть). settle() идемпотентен — гонка с поздним
    DELETE безопасна."""
    from .models import SandboxSession
    from . import billing, client

    stale = SandboxSession.objects.filter(
        state__in=SandboxSession.ACTIVE_STATES,
        expires_at__lt=timezone.now(),
    )
    closed = 0
    for session in stale:
        duration = float(session.ttl_seconds)
        try:
            result = client.kill(str(session.id))
            if result.get('duration_seconds'):
                duration = float(result['duration_seconds'])
        except Exception as exc:
            # VM уже убита e2b-таймаутом — биллим полный TTL (резерв и был на него)
            logger.info('[sandbox] reconcile kill %s: %s', session.public_id, exc)
        billing.settle(session, duration)
        session.state = SandboxSession.State.EXPIRED
        session.save(update_fields=['state'])
        closed += 1
    if closed:
        logger.info('[sandbox] reconcile: closed %s stale sessions', closed)
    return closed


@shared_task(name='sandboxes.tasks.check_sandbox_abuse')
def check_sandbox_abuse():
    """Каждые 10 мин: пометить подозрительные сессии (долгие + активный exec —
    паттерн майнинга/прокси) и уведомить админа. Ничего не убивает автоматически —
    решение за человеком (админка, action Kill)."""
    from datetime import timedelta
    from django.core.mail import mail_admins
    from .models import SandboxSession

    threshold_min = int(getattr(settings, 'SANDBOX_ABUSE_RUNTIME_MIN', 20))
    threshold_exec = int(getattr(settings, 'SANDBOX_ABUSE_EXEC_COUNT', 50))
    suspects = SandboxSession.objects.filter(
        state__in=SandboxSession.ACTIVE_STATES,
        abuse_flagged=False,
        started_at__lt=timezone.now() - timedelta(minutes=threshold_min),
        exec_count__gt=threshold_exec,
    )
    flagged = list(suspects[:50])
    if not flagged:
        return 0
    SandboxSession.objects.filter(pk__in=[s.pk for s in flagged]).update(abuse_flagged=True)
    try:
        lines = '\n'.join(
            f'{s.public_id} user={s.user_id} exec={s.exec_count} started={s.started_at}'
            for s in flagged
        )
        mail_admins('[aineron] Sandbox abuse suspects', lines, fail_silently=True)
    except Exception:
        pass
    logger.warning('[sandbox] abuse check: flagged %s sessions', len(flagged))
    return len(flagged)


@shared_task(name='sandboxes.tasks.check_sandbox_runrate')
def check_sandbox_runrate():
    """Каждые 15 мин: алерт, если суммарный run-rate активных сессий превышает
    порог ₽/час — защита от неожиданного счёта E2B."""
    from django.core.mail import mail_admins
    from .models import SandboxSession
    from .billing import price_per_min_kopecks

    limit_rub = int(getattr(settings, 'SANDBOX_RUNRATE_ALERT_RUB', 500))
    if limit_rub <= 0:
        return 0
    active = SandboxSession.objects.filter(state__in=SandboxSession.ACTIVE_STATES)
    runrate_kopecks_hour = sum(price_per_min_kopecks(s.size) * 60 for s in active)
    runrate_rub = runrate_kopecks_hour / 100
    if runrate_rub > limit_rub:
        mail_admins(
            '[aineron] Sandbox run-rate alert',
            f'Активных сессий: {active.count()}, run-rate ≈ {runrate_rub:.0f} ₽/час '
            f'(порог {limit_rub}).',
            fail_silently=True,
        )
        logger.warning('[sandbox] run-rate alert: %.0f RUB/h', runrate_rub)
    return int(runrate_rub)
