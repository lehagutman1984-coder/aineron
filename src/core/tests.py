from decimal import Decimal
from django.test import SimpleTestCase, override_settings

from core.money import (
    apply_min_charge,
    ceil_kopecks,
    format_rub,
    get_min_charge_kopecks,
    kopecks_to_rub,
    rub_to_kopecks,
)


class MoneyRoundTripTests(SimpleTestCase):
    def test_rub_to_kopecks_and_back(self):
        self.assertEqual(rub_to_kopecks('125'), 12500)
        self.assertEqual(rub_to_kopecks('1.50'), 150)
        self.assertEqual(rub_to_kopecks(Decimal('0.01')), 1)
        self.assertEqual(kopecks_to_rub(12500), Decimal('125.00'))
        self.assertEqual(kopecks_to_rub(150), Decimal('1.50'))

    def test_format_rub_whole_number_has_no_decimals(self):
        self.assertEqual(format_rub(12500), '125 ₽')
        self.assertEqual(format_rub(0), '0 ₽')

    def test_format_rub_fractional_uses_comma(self):
        self.assertEqual(format_rub(150), '1,50 ₽')
        self.assertEqual(format_rub(35), '0,35 ₽')

    def test_format_rub_thousands_separator(self):
        self.assertEqual(format_rub(1250000), '12 500 ₽')

    def test_ceil_kopecks_never_rounds_down(self):
        self.assertEqual(ceil_kopecks(10.1), 11)
        self.assertEqual(ceil_kopecks(10.0), 10)
        self.assertEqual(ceil_kopecks('9.001'), 10)


class MinChargeTests(SimpleTestCase):
    def test_default_min_charge_is_10_kopecks(self):
        self.assertEqual(get_min_charge_kopecks(), 10)

    def test_apply_min_charge_floors_small_amounts(self):
        self.assertEqual(apply_min_charge(1), 10)
        self.assertEqual(apply_min_charge(0), 0)
        self.assertEqual(apply_min_charge(500), 500)

    @override_settings(MIN_CHARGE_KOPECKS=50)
    def test_apply_min_charge_respects_override(self):
        self.assertEqual(apply_min_charge(1), 50)
        self.assertEqual(apply_min_charge(100), 100)
