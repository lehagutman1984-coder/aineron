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
    """
    s = message.settings or {}
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
    """
    s = message.settings or {}
    org_billing = s.get('org_billing') or {}
    org_id = org_billing.get('organization_id')
    cost_rub = org_billing.get('cost_rub')
    if not org_id or not cost_rub or s.get('org_refunded'):
        return False

    from decimal import Decimal, InvalidOperation
    from django.db.models import F
    from teams.models import Organization

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
        message.settings = new_settings
        message.save(update_fields=['settings'])
    return bool(updated)
