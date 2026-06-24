from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0031_elo_arena'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ModerationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('input_excerpt', models.CharField(max_length=200)),
                ('flagged', models.BooleanField(default=False)),
                ('categories', models.JSONField(default=dict)),
                ('scores', models.JSONField(default=dict)),
                ('action', models.CharField(choices=[('allowed', 'Разрешено'), ('blocked', 'Заблокировано')], default='allowed', max_length=10)),
                ('source', models.CharField(default='web_chat', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderation_logs', to=settings.AUTH_USER_MODEL)),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='aitext.message')),
            ],
            options={
                'verbose_name': 'Лог модерации',
                'verbose_name_plural': 'Логи модерации',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='moderationlog',
            index=models.Index(fields=['flagged', 'created_at'], name='modlog_flagged_idx'),
        ),
    ]
