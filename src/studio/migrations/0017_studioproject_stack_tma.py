from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0016_studioproject_deploy_target'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studioproject',
            name='target_stack',
            field=models.CharField(
                choices=[
                    ('nextjs', 'Next.js'), ('react', 'React'),
                    ('vue', 'Vue'), ('html', 'HTML'), ('tma', 'Telegram Mini App'),
                ],
                default='nextjs',
                max_length=10,
            ),
        ),
    ]
