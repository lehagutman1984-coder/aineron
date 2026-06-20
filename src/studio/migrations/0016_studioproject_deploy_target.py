from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0015_studiotemplate_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='deploy_target',
            field=models.CharField(
                choices=[
                    ('none', 'Не деплоить'), ('vercel', 'Vercel'),
                    ('timeweb', 'Timeweb Cloud'), ('selectel', 'Selectel'),
                    ('tma', 'Telegram Mini App'),
                ],
                default='none',
                max_length=20,
            ),
        ),
    ]
