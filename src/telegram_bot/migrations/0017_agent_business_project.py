from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0047_unified_memory_recall_research'),
        ('telegram_bot', '0016_aitask_research'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentrun',
            name='project',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='agent_runs', to='aitext.project',
                                    verbose_name='Проект (инструменты KB)'),
        ),
        migrations.AddField(
            model_name='businessconnection',
            name='project',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='business_connections', to='aitext.project',
                                    verbose_name='Проект (база знаний секретаря)'),
        ),
    ]
