from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0047_unified_memory_recall_research'),
        ('telegram_bot', '0015_agentrun'),
    ]

    operations = [
        migrations.AddField(
            model_name='aitask',
            name='kind',
            field=models.CharField(choices=[('llm', 'LLM-ответ'), ('research', 'Deep Research (мониторинг)')],
                                   default='llm', max_length=10, verbose_name='Тип задачи'),
        ),
        migrations.AddField(
            model_name='aitask',
            name='project',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='ai_tasks', to='aitext.project',
                                    verbose_name='Проект (для research-отчётов)'),
        ),
    ]
