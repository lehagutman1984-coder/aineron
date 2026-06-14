from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0005_fileattachment_message_nullable'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PromptTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название')),
                ('content', models.TextField(verbose_name='Текст промта')),
                ('category', models.CharField(
                    choices=[
                        ('code', 'Код'), ('translate', 'Перевод'), ('analyze', 'Анализ'),
                        ('email', 'Письма'), ('study', 'Учёба'), ('creative', 'Творчество'), ('other', 'Другое'),
                    ],
                    default='other', max_length=50, verbose_name='Категория',
                )),
                ('icon', models.CharField(default='FileText', max_length=50, verbose_name='Иконка (Lucide)')),
                ('is_public', models.BooleanField(default=True, verbose_name='Публичный')),
                ('order', models.IntegerField(default=0, verbose_name='Порядок')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prompt_templates',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Шаблон промта',
                'verbose_name_plural': 'Шаблоны промтов',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
