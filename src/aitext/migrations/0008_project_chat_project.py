from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0007_prompttemplate_seed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('system_prompt', models.TextField(blank=True, verbose_name='Системный промт')),
                ('color', models.CharField(default='#0a7cff', max_length=7, verbose_name='Цвет (hex)')),
                ('icon', models.CharField(default='Folder', max_length=30, verbose_name='Иконка (Lucide)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='projects',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Проект',
                'verbose_name_plural': 'Проекты',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='chat',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chats',
                to='aitext.project',
                verbose_name='Проект',
            ),
        ),
    ]
