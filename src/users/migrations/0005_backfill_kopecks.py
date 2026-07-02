"""
Backfill копеек из legacy звёздных полей (×100). См. BILLING_MIGRATION_PLAN.md.

Категория А (балансы/справочники) — конвертируем ×100:
  CustomUser.balance_kopecks, Tariff.balance_grant_kopecks/referral_bonus_kopecks, PromoCode.kopecks
Категория Б (аналитика) — конвертируем ВСЕ строки ×100 (непрерывность истории):
  UserSpending.amount_kopecks
Категория В (финансовый аудит) — НЕ конвертируем:
  PaymentHistory.amount_kopecks остаётся NULL для существующих записей.

Обратима: reverse зануляет новые поля, legacy-поля не трогает.
"""
from django.db import migrations
from django.db.models import F


def forward(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    Tariff = apps.get_model('users', 'Tariff')
    PromoCode = apps.get_model('users', 'PromoCode')
    UserSpending = apps.get_model('users', 'UserSpending')

    CustomUser.objects.update(balance_kopecks=F('pages_count') * 100)
    Tariff.objects.update(
        balance_grant_kopecks=F('pages_count') * 100,
        referral_bonus_kopecks=F('referral_bonus_stars') * 100,
    )
    PromoCode.objects.update(kopecks=F('stars') * 100)
    UserSpending.objects.update(amount_kopecks=F('amount') * 100)


def reverse(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    Tariff = apps.get_model('users', 'Tariff')
    PromoCode = apps.get_model('users', 'PromoCode')
    UserSpending = apps.get_model('users', 'UserSpending')

    CustomUser.objects.update(balance_kopecks=0)
    Tariff.objects.update(balance_grant_kopecks=0, referral_bonus_kopecks=0)
    PromoCode.objects.update(kopecks=0)
    UserSpending.objects.update(amount_kopecks=0)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_customuser_balance_kopecks_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
