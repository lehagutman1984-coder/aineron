from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0028_promptabtest'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[('active', 'Активный'), ('paused', 'Пауза'), ('done', 'Завершён')],
                default='active',
                max_length=10,
                verbose_name='Статус',
            ),
        ),
    ]
