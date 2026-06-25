from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0018_projectdatabase'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PreviewSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(max_length=64, unique=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('reserved_stars', models.IntegerField(default=0)),
                ('settled', models.BooleanField(default=False)),
                ('stack', models.CharField(blank=True, max_length=32)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preview_sessions',
                    to='studio.studioproject',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'verbose_name': 'Preview Session'},
        ),
    ]
