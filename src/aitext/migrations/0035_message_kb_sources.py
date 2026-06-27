from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0034_chatsummary_updated_at_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='kb_sources',
            field=models.JSONField(blank=True, default=list, verbose_name='Источники базы знаний'),
        ),
    ]
