from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0029_project_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add variables JSONField to PromptTemplate
        migrations.AddField(
            model_name='prompttemplate',
            name='variables',
            field=models.JSONField(blank=True, default=list, verbose_name='Переменные шаблона'),
        ),
        # Create Persona model
        migrations.CreateModel(
            name='Persona',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Имя персоны')),
                ('slug', models.SlugField(max_length=120, unique=True, verbose_name='Slug')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Описание')),
                ('system_prompt', models.TextField(verbose_name='Системный промт')),
                ('avatar_url', models.URLField(blank=True, verbose_name='URL аватара')),
                ('is_public', models.BooleanField(default=False, verbose_name='Публичная (системная)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('order', models.IntegerField(default=0, verbose_name='Порядок')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('network', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='personas',
                    to='aitext.neuralnetwork',
                    verbose_name='Модель по умолчанию',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='personas',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Владелец (null = системная)',
                )),
            ],
            options={
                'verbose_name': 'AI-персона',
                'verbose_name_plural': 'AI-персоны',
                'ordering': ['order', 'name'],
            },
        ),
    ]
