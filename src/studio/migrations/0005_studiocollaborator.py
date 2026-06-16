from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('studio', '0004_vercel_url_template_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudioCollaborator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('viewer', 'Просмотр'), ('editor', 'Редактирование')],
                    default='viewer', max_length=10,
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='collaborators', to='studio.studioproject',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='studio_collabs', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'unique_together': {('project', 'user')}},
        ),
    ]
