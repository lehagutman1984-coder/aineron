from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0039_generatedimage_mediaasset_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='status',
            field=models.CharField(
                blank=True, default='done', max_length=20,
                choices=[
                    ('pending', 'В очереди'),
                    ('running', 'Генерируется'),
                    ('done', 'Готово'),
                    ('error', 'Ошибка'),
                ],
                verbose_name='Статус генерации',
            ),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='progress',
            field=models.IntegerField(default=100, verbose_name='Прогресс (%)'),
        ),
    ]
