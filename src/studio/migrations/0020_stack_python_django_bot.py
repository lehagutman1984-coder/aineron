from django.db import migrations, models

NEW_STACK_CHOICES = [
    ('nextjs', 'Next.js'), ('react', 'React'), ('vue', 'Vue'), ('html', 'HTML'),
    ('tma', 'Telegram Mini App'),
    ('python', 'Python (FastAPI/Flask)'),
    ('django', 'Django'),
    ('telegram_bot', 'Telegram Bot'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0019_previewsession'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studioproject',
            name='target_stack',
            field=models.CharField(
                choices=NEW_STACK_CHOICES,
                default='nextjs',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='studiotemplate',
            name='stack',
            field=models.CharField(
                choices=NEW_STACK_CHOICES,
                default='nextjs',
                max_length=20,
            ),
        ),
    ]
