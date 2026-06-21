"""Sprint 4.2 — Inbound sync: webhook_secret + last_synced_at на коннекторе, repo_sha на файле."""

import secrets
from django.db import migrations, models


def generate_secrets(apps, schema_editor):
    """Автоматически заполняем webhook_secret для существующих коннекторов."""
    ProjectConnector = apps.get_model('aitext', 'ProjectConnector')
    for conn in ProjectConnector.objects.filter(webhook_secret=''):
        conn.webhook_secret = secrets.token_hex(32)
        conn.save(update_fields=['webhook_secret'])


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0015_pgvector_chunks'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectconnector',
            name='webhook_secret',
            field=models.CharField(
                max_length=64, blank=True, default='',
                verbose_name='Webhook secret (HMAC)',
            ),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='last_synced_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Последняя синхронизация'),
        ),
        migrations.AddField(
            model_name='projectfile',
            name='repo_sha',
            field=models.CharField(max_length=64, blank=True, verbose_name='Git blob SHA (для инкрементального синка)'),
        ),
        migrations.RunPython(generate_secrets, migrations.RunPython.noop),
    ]
