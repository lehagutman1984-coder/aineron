from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0001_initial'),
        ('telegram_bot', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='default_video_network',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='telegram_users_video',
                to='aitext.neuralnetwork',
                verbose_name='Дефолтная видео модель',
            ),
        ),
    ]
