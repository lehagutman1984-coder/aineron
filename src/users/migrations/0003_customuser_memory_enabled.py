from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_customuser_gitea_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='memory_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Глобальный переключатель долговременной памяти',
                verbose_name='Память включена',
            ),
        ),
    ]
