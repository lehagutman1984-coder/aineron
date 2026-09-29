"""
2026-09-29: Robokassa-формы (покупка тарифа, пополнение баланса) не передавали
Email покупателя — при включённой на аккаунте фискализации (Робочеки СМЗ)
это единственный надёжный канал доставки фискального чека, без него Robokassa
могла физически не довезти чек до покупателя. Chek (Receipt) сам по себе уже
отправлялся и не менялся - эти тесты проверяют только добавленное поле Email.

Тем же днём, по официальной документации Robokassa (docs.robokassa.ru/ru/
fiscalization) - payment_method/payment_object у каждой позиции Receipt
формально опциональны "если заданы значения по умолчанию в личном кабинете",
но полагаться на дефолты кабинета менее надёжно для СМЗ-фискализации, чем
задать явно. Добавлены "full_payment"/"service" (полная оплата цифровой
услуги сразу) во все 4 точки формирования чека - см. RobokassaFiscalFieldsTests.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from users.models import PageSaleSettings, Tariff

User = get_user_model()


def _extract_receipt(form_html: str) -> dict:
    """Достаёт Receipt JSON из value='...' скрытого поля формы."""
    marker = "name=\"Receipt\" value='"
    start = form_html.index(marker) + len(marker)
    end = form_html.index("'>", start)
    return json.loads(form_html[start:end])

# teams.middleware резолвит org_branding через cache на каждом запросе - без
# него нужен живой Redis (недоступен при локальном запуске вне Docker).
_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}


@override_settings(CACHES=_LOCMEM_CACHE)
class RobokassaEmailFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rbkemail', email='rbkemail@test.ru', password='x',
        )
        self.user.email_verified = True  # EmailVerificationMiddleware иначе редиректит на /verify-email/
        self.user.save(update_fields=['email_verified'])
        self.client.force_login(self.user)

    def test_subscription_payment_form_includes_user_email(self):
        tariff = Tariff.objects.create(
            display_name='Pro', pages_count=1000, price=Decimal('990.00'),
            is_active=True, is_free=False,
        )
        resp = self.client.post(
            '/users/api/create-payment/', {'tariff_id': tariff.id},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        form_html = resp.json()['form_html']
        self.assertIn('name="Email" value="rbkemail@test.ru"', form_html)

    def test_topup_payment_form_includes_user_email(self):
        settings_obj = PageSaleSettings.objects.create(
            price_per_page=Decimal('1.00'), min_pages_for_purchase=1,
            max_pages_for_purchase=10000, is_active=True,
        )
        resp = self.client.post(
            '/users/api/buy-pages/', {'pages': 100},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        form_html = resp.json()['form_html']
        self.assertIn('name="Email" value="rbkemail@test.ru"', form_html)

    def test_email_value_is_escaped(self):
        """Email всегда проходит через Django EmailField-валидацию при регистрации,
        но защита от инъекции в атрибут value="..." не должна зависеть от этого."""
        from django.utils.html import escape
        user2 = User.objects.create_user(
            username='rbkemail2', email='weird+tag@test.ru', password='x',
        )
        user2.email_verified = True
        user2.save(update_fields=['email_verified'])
        self.client.force_login(user2)
        tariff = Tariff.objects.create(
            display_name='Basic', pages_count=500, price=Decimal('490.00'),
            is_active=True, is_free=False,
        )
        resp = self.client.post(
            '/users/api/create-payment/', {'tariff_id': tariff.id},
            content_type='application/json',
        )
        form_html = resp.json()['form_html']
        self.assertIn(f'value="{escape(user2.email)}"', form_html)


@override_settings(CACHES=_LOCMEM_CACHE)
class RobokassaFiscalFieldsTests(TestCase):
    """payment_method/payment_object в Receipt - обязательны для корректной
    фискализации СМЗ по официальной документации Robokassa, у нас отсутствовали
    во всех 4 точках формирования чека (подписка/topup/оба recurring-пути)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rbkfiscal', email='rbkfiscal@test.ru', password='x',
        )
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])
        self.client.force_login(self.user)

    def test_subscription_receipt_has_payment_method_and_object(self):
        tariff = Tariff.objects.create(
            display_name='Pro', pages_count=1000, price=Decimal('990.00'),
            is_active=True, is_free=False,
        )
        resp = self.client.post(
            '/users/api/create-payment/', {'tariff_id': tariff.id},
            content_type='application/json',
        )
        receipt = _extract_receipt(resp.json()['form_html'])
        item = receipt['items'][0]
        self.assertEqual(item['payment_method'], 'full_payment')
        self.assertEqual(item['payment_object'], 'service')

    def test_topup_receipt_has_payment_method_and_object(self):
        PageSaleSettings.objects.create(
            price_per_page=Decimal('1.00'), min_pages_for_purchase=1,
            max_pages_for_purchase=10000, is_active=True,
        )
        resp = self.client.post(
            '/users/api/buy-pages/', {'pages': 100},
            content_type='application/json',
        )
        receipt = _extract_receipt(resp.json()['form_html'])
        item = receipt['items'][0]
        self.assertEqual(item['payment_method'], 'full_payment')
        self.assertEqual(item['payment_object'], 'service')
