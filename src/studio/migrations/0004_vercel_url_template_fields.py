from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('studio', '0003_pipelinestate_pause_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='vercel_deployment_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='studiotemplate',
            name='author',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='studio_templates', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='studiotemplate',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='studiotemplate',
            name='usage_count',
            field=models.IntegerField(default=0),
        ),
    ]
