# Рублёвый биллинг: пополнение баланса 1:1 (1 ₽ платежа = 1 ₽ на балансе).
# Legacy-настройка «цена за звезду» (по умолчанию была 10.00 ₽/звезда) при курсе
# миграции 1 звезда = 1 ₽ означала бы 10 ₽ за 1 ₽ баланса — приводим к 1.00.
from django.db import migrations


def forwards(apps, schema_editor):
    PageSaleSettings = apps.get_model('users', 'PageSaleSettings')
    PageSaleSettings.objects.filter(id=1).update(
        price_per_page=1.00,
        min_pages_for_purchase=10,
        max_pages_for_purchase=50000,
    )


def backwards(apps, schema_editor):
    PageSaleSettings = apps.get_model('users', 'PageSaleSettings')
    PageSaleSettings.objects.filter(id=1).update(
        price_per_page=10.00,
        min_pages_for_purchase=1,
        max_pages_for_purchase=100,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_backfill_kopecks'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
