from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0013_studioproject_design_md_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='studiopipelinestate',
            name='seen_error_hashes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='studiopipelinestate',
            name='autofix_count',
            field=models.IntegerField(default=0),
        ),
    ]
