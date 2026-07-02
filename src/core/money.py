"""
Единый источник истины для денежных величин платформы.

Инвариант: 1 звезда (legacy) = 1 рубль = 100 копеек.
Все балансы, цены и списания хранятся в копейках (int), чтобы избежать
ошибок округления Decimal и обеспечить дробное ценообразование.
"""
import math
from decimal import Decimal, ROUND_HALF_UP

KOPECKS_PER_RUB = 100


def get_min_charge_kopecks() -> int:
    """
    Минимальное списание за один запрос (защита от "пыли" — списаний в доли копейки).
    Читается из Django settings.MIN_CHARGE_KOPECKS (env MIN_CHARGE_KOPECKS, дефолт 10 = 0,10 ₽)
    через функцию, а не модульную константу — чтобы override_settings в тестах работал.
    """
    from django.conf import settings
    return int(getattr(settings, 'MIN_CHARGE_KOPECKS', 10))


def rub_to_kopecks(rub) -> int:
    """Decimal/str/int/float рублей -> целые копейки (округление до ближайшей копейки)."""
    return int(Decimal(str(rub)).scaleb(2).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def kopecks_to_rub(kopecks: int) -> Decimal:
    """Целые копейки -> Decimal рублей с 2 знаками после запятой."""
    return (Decimal(int(kopecks)) / KOPECKS_PER_RUB).quantize(Decimal('0.01'))


def format_rub(kopecks: int) -> str:
    """
    125000 -> '1 250 ₽' (целое число — без дробной части)
    150    -> '1,50 ₽'  (дробное — с копейками, запятая как разделитель)
    """
    rub = kopecks_to_rub(kopecks)
    if rub == rub.to_integral_value():
        return f'{int(rub):,}'.replace(',', ' ') + ' ₽'
    return f'{rub:.2f}'.replace('.', ',') + ' ₽'


def ceil_kopecks(value) -> int:
    """Округление вверх до целой копейки (никогда не занижаем списание)."""
    return int(math.ceil(Decimal(str(value))))


def apply_min_charge(kopecks: int) -> int:
    """Применяет пол минимального списания. kopecks должен быть >= 0."""
    if kopecks <= 0:
        return 0
    return max(get_min_charge_kopecks(), kopecks)
