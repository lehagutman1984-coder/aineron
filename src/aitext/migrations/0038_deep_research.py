from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0037_chat_branching'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeepResearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.TextField(verbose_name='Вопрос')),
                ('status', models.CharField(
                    choices=[('pending', 'Ожидает'), ('running', 'Выполняется'), ('done', 'Готово'), ('error', 'Ошибка')],
                    default='pending', max_length=10,
                )),
                ('steps', models.JSONField(blank=True, default=list, verbose_name='Шаги выполнения')),
                ('error', models.TextField(blank=True, verbose_name='Ошибка')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('chat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deep_researches', to='aitext.chat',
                )),
                ('message', models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='deep_research', to='aitext.message',
                )),
            ],
            options={
                'verbose_name': 'Глубокое исследование',
                'verbose_name_plural': 'Глубокие исследования',
                'ordering': ['-created_at'],
            },
        ),
    ]
