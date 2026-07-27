from django.db import migrations


def deactivate_dead_model(apps, schema_editor):
    """BUG-E (TELEGRAM_SUPREMACY_PLAN_V2.md): model_name='deepseek-v3' отклоняется
    и laozhang.ai (503 no available channels), и apimart.ai в фолбэке (400 not a
    valid model ID) — рабочего провайдера нет ни на одном плече. Живые модели
    deepseek-v3.1 / deepseek-v3.2 (отдельные записи, другие slug) не затрагиваются.
    Instance-agnostic: если записи нет (например, ещё не засеяна) — no-op.
    """
    NeuralNetwork = apps.get_model('aitext', 'NeuralNetwork')
    NeuralNetwork.objects.filter(model_name='deepseek-v3', is_active=True).update(is_active=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0056_backfill_scoped_memory_keys'),
    ]

    operations = [
        migrations.RunPython(deactivate_dead_model, noop_reverse),
    ]
