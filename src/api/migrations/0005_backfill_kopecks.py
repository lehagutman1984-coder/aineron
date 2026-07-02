"""
Backfill копеек из legacy звёздных полей (×100) для TokenUsage. См. BILLING_MIGRATION_PLAN.md.
Категория Б (аналитика) — конвертируем ВСЕ строки для непрерывности истории.
"""
from django.db import migrations
from django.db.models import F


def forward(apps, schema_editor):
    TokenUsage = apps.get_model('api', 'TokenUsage')
    TokenUsage.objects.update(cost_kopecks=F('stars_charged') * 100)


def reverse(apps, schema_editor):
    TokenUsage = apps.get_model('api', 'TokenUsage')
    TokenUsage.objects.update(cost_kopecks=0)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_tokenusage_cost_kopecks_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
