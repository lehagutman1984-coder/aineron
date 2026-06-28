from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0038_deep_research'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='params',
            field=models.JSONField(blank=True, null=True, verbose_name='Параметры генерации'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='seed',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Seed'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='model_name',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Модель'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='provider',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Провайдер'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='source',
            field=models.CharField(blank=True, default='chat', max_length=20, verbose_name='Источник'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children', to='aitext.generatedimage',
                verbose_name='Исходное медиа (для img2img)',
            ),
        ),
        migrations.AlterField(
            model_name='generatedimage',
            name='message',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generated_images', to='aitext.message',
                verbose_name='Сообщение',
            ),
        ),
    ]
