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
