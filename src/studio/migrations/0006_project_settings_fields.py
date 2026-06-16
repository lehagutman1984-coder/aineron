from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0005_studiocollaborator'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='coder_model',
            field=models.CharField(
                choices=[('fast', 'DeepSeek V3'), ('smart', 'Opus 4.8')],
                default='fast',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='studioproject',
            name='max_iterations',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='studioproject',
            name='max_stars_budget',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='studioproject',
            name='auto_deploy',
            field=models.BooleanField(default=False),
        ),
    ]
