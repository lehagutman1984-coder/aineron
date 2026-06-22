from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0022_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectfile',
            name='summary',
            field=models.TextField(blank=True, verbose_name='Summary файла (для file-level embeddings)'),
        ),
    ]
