from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0009_merge_0006_alter_0008_screenshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='ai_model',
            field=models.CharField(default='claude-sonnet-4-6', max_length=64),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='last_files_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='same_diff_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='last_error_signature',
            field=models.CharField(blank=True, default='', max_length=256),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='error_repeat_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
