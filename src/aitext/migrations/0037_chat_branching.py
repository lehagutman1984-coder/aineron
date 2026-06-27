import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0036_message_variants'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='parent_chat',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='branches',
                to='aitext.chat',
                verbose_name='Родительский чат',
            ),
        ),
        migrations.AddField(
            model_name='chat',
            name='branch_from_message_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='ID сообщения ветвления'),
        ),
    ]
