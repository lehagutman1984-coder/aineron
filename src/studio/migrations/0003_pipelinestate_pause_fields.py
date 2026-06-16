from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0002_studiotemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='studiopipelinestate',
            name='pause_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='current_task_id',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
