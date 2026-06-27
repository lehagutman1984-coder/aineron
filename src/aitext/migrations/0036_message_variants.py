from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0035_message_kb_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='variants',
            field=models.JSONField(blank=True, default=list, verbose_name='Варианты ответа'),
        ),
    ]
