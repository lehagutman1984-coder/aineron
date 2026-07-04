"""
Генерация уникального InvId для Robokassa.

Robokassa требует, чтобы InvId был положительным целым и уникальным в рамках
магазина (диапазон 1..2_147_483_647). Старый генератор `time_ms % 10_000_000`
имел маленькое пространство значений и мог коллизиться: два платежа в одну
миллисекунду -> одинаковый invoice_id -> PaymentHistory.objects.get(invoice_id=...)
падал MultipleObjectsReturned (500, потерянный платёж).

Здесь генерируем случайный id в большом пространстве и проверяем, что он ещё не
занят в PaymentHistory. Глобальный UNIQUE-constraint не вешаем намеренно: промо-
платежи используют общий invoice_id вида `promo-<pk>` (одинаковый у всех
пользователей), constraint бы их сломал.
"""
import random
import time

# С запасом ниже потолка Robokassa (2_147_483_647), чтобы IsTest/сервисные id не мешали.
_ROBOKASSA_MAX_INV_ID = 2_000_000_000
_ROBOKASSA_MIN_INV_ID = 1_000_000


def make_unique_invoice_id() -> int:
    """Уникальный (в пределах PaymentHistory) числовой InvId для Robokassa."""
    from users.models import PaymentHistory

    for _ in range(15):
        candidate = random.randint(_ROBOKASSA_MIN_INV_ID, _ROBOKASSA_MAX_INV_ID)
        if not PaymentHistory.objects.filter(invoice_id=str(candidate)).exists():
            return candidate

    # Практически недостижимо; детерминированный фолбэк с высокой энтропией.
    return int(time.time() * 1000) % _ROBOKASSA_MAX_INV_ID + random.randint(1, 99_999)
