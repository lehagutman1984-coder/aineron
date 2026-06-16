from django.db import migrations


def forwards(apps, schema_editor):
    StudioProject = apps.get_model('studio', 'StudioProject')
    mapping = {'fast': 'deepseek-v3.2', 'smart': 'claude-opus-4-8'}
    for p in StudioProject.objects.all():
        old = getattr(p, 'coder_model', None)
        p.ai_model = mapping.get(old, 'claude-sonnet-4-6')
        p.save(update_fields=['ai_model'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0010_ai_model_and_loop_fields'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='studioproject', name='coder_model'),
    ]
