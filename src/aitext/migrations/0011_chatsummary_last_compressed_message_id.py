from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0010_usermemory_chatsummary'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsummary',
            name='last_compressed_message_id',
            field=models.BigIntegerField(
                blank=True,
                null=True,
                verbose_name='ID последнего сжатого сообщения',
            ),
        ),
    ]
