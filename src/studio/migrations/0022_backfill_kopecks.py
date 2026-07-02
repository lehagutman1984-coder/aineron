"""
Backfill копеек из legacy звёздных полей (×100) для StudioProject. См. BILLING_MIGRATION_PLAN.md.
"""
from django.db import migrations
from django.db.models import F


def forward(apps, schema_editor):
    StudioProject = apps.get_model('studio', 'StudioProject')
    StudioProject.objects.update(
        stars_reserved_kopecks=F('stars_reserved') * 100,
        stars_spent_kopecks=F('stars_spent') * 100,
        max_kopecks_budget=F('max_stars_budget') * 100,
    )


def reverse(apps, schema_editor):
    StudioProject = apps.get_model('studio', 'StudioProject')
    StudioProject.objects.update(
        stars_reserved_kopecks=0,
        stars_spent_kopecks=0,
        max_kopecks_budget=0,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0021_studioproject_max_kopecks_budget_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
