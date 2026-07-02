"""
Backfill копеек из legacy звёздных полей (×100). См. BILLING_MIGRATION_PLAN.md.

NeuralNetwork.cost_kopecks/kopecks_per_1k_tokens — категория А (справочник цен).
UsageEvent.cost_kopecks — категория Б (аналитика, конвертируем ВСЕ строки для
непрерывности графиков расходов).
"""
from django.db import migrations
from django.db.models import F


def forward(apps, schema_editor):
    NeuralNetwork = apps.get_model('aitext', 'NeuralNetwork')
    UsageEvent = apps.get_model('aitext', 'UsageEvent')

    NeuralNetwork.objects.update(cost_kopecks=F('cost_per_message') * 100)
    NeuralNetwork.objects.filter(stars_per_1k_tokens__gt=0).update(
        kopecks_per_1k_tokens=F('stars_per_1k_tokens') * 100
    )
    UsageEvent.objects.update(cost_kopecks=F('cost') * 100)


def reverse(apps, schema_editor):
    NeuralNetwork = apps.get_model('aitext', 'NeuralNetwork')
    UsageEvent = apps.get_model('aitext', 'UsageEvent')

    NeuralNetwork.objects.update(cost_kopecks=0, kopecks_per_1k_tokens=0)
    UsageEvent.objects.update(cost_kopecks=0)


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0045_rename_aitext_proj_project_audit_idx_aitext_proj_project_5664bf_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
