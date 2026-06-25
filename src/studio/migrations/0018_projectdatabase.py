import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0017_studioproject_stack_tma'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectDatabase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(
                    choices=[
                        ('none', 'Без базы'),
                        ('aineron', 'Aineron Schema (бесплатно)'),
                        ('neon', 'Neon (ваш аккаунт)'),
                        ('external', 'Внешняя БД'),
                    ],
                    default='none',
                    max_length=20,
                )),
                ('aineron_schema', models.CharField(blank=True, max_length=128)),
                ('neon_project_id', models.CharField(blank=True, max_length=128)),
                ('neon_api_key_enc', models.TextField(blank=True)),
                ('external_conn_enc', models.TextField(blank=True)),
                ('provisioned', models.BooleanField(default=False)),
                ('credentials_enc', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preview_db',
                    to='studio.studioproject',
                )),
            ],
            options={
                'verbose_name': 'Project Database',
            },
        ),
    ]
