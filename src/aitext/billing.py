"""
Утилиты pre-charge биллинга текстовых сообщений (web polling-флоу).

Веб-view списывает средства ДО запуска generate_ai_response. Чтобы задача могла
(а) вернуть деньги при окончательном провале генерации и (б) не списать второй
раз при включённом TEXT_BILLING_ENABLED, факт списания фиксируется в settings
сообщения ассистента: billing_reference + billing_kopecks.
"""


def record_message_billing(message, reference: str, cost_kopecks: int):
    """Сохранить на сообщении ассистента reference и сумму выполненного списания."""
    s = dict(message.settings or {})
    s['billing_reference'] = reference
    s['billing_kopecks'] = int(cost_kopecks)
    message.settings = s
    message.save(update_fields=['settings'])


def refund_message_billing(message) -> bool:
    """
    Вернуть средства, списанные на вебе за это сообщение. Идемпотентно:
    reference совпадает со spend-записью, но type='refund' — повторный вызов
    (ретрай Celery) станет no-op по unique(type, reference).

    2026-09-28 (ревью, раунд 3): единая точка провала генерации (вызывается на
    каждом failure-пути Celery-задачи) — заодно освобождает атомарный резерв
    доплаты (TOKEN_OVERAGE_RESERVE_ENABLED, message.settings
    ['overage_reserve_reference']), если он был сделан. Без этого резерв
    остался бы списанным без возврата на сообщении, которое так и не
    сгенерировалось (та же дыра, что чинилась для flat-списания раньше —
    просто для нового вида резерва).
    """
    from aitext.token_metering import release_overage_reservation

    s = message.settings or {}
    reserve_ref = s.get('overage_reserve_reference')
    if reserve_ref:
        release_overage_reservation(message.chat.user, reserve_ref)

    ref = s.get('billing_reference')
    kop = int(s.get('billing_kopecks') or 0)
    if not ref or kop <= 0:
        return False
    return message.chat.user.add_kopecks(kop, type='refund', reference=ref)


def refund_org_billing(message) -> bool:
    """
    Вернуть организации средства, списанные ДО генерации в group.py::_charge_org
    (Telegram-группы на org-биллинге). У Organization нет ledger с unique-constraint
    как у CustomUser.BalanceTransaction, поэтому идемпотентность обеспечивается
    флагом org_refunded в settings сообщения — вызывающая сторона (generate_ai_response)
    сама гарантирует не более одного вызова на сообщение (только на is_final_attempt),
    флаг — вторая линия защиты на случай повторной обработки того же message_id.

    2026-09-28 (ревью, раунд 3): раньше проверка флага (`s.get('org_refunded')`)
    и его запись были отдельными шагами БЕЗ блокировки строки — два конкурентных
    вызова для одного message_id (повторная доставка того же Celery-таска) могли
    оба пройти проверку до того, как один из них выставит флаг, и организация
    получила бы двойной возврат. select_for_update() внутри atomic() сериализует
    конкурентные вызовы: второй, после коммита первого, увидит org_refunded=True
    уже выставленным и вернёт False.
    """
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from django.db.models import F
    from teams.models import Organization

    with transaction.atomic():
        locked = type(message).objects.select_for_update().get(pk=message.pk)
        s = locked.settings or {}
        org_billing = s.get('org_billing') or {}
        org_id = org_billing.get('organization_id')
        cost_rub = org_billing.get('cost_rub')
        if not org_id or not cost_rub or s.get('org_refunded'):
            return False

        try:
            amount = Decimal(str(cost_rub))
        except InvalidOperation:
            return False

        updated = Organization.objects.filter(id=org_id).update(
            balance_rub=F('balance_rub') + amount
        )
        if updated:
            new_settings = dict(s)
            new_settings['org_refunded'] = True
            locked.settings = new_settings
            locked.save(update_fields=['settings'])
            message.settings = new_settings  # держим объект вызывающей стороны в консистентном виде
    return bool(updated)
