from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0012_agent_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='design_md_content',
            field=models.TextField(blank=True, default=''),
        ),
    ]
