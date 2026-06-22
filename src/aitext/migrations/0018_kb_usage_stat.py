from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0017_projectchunk_indexes_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='KBUsageStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hits', models.PositiveIntegerField(default=0, verbose_name='Использований в контексте')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='Последнее использование')),
                ('file', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_stat',
                    to='aitext.projectfile',
                    verbose_name='Файл',
                )),
            ],
            options={
                'verbose_name': 'Статистика использования файла',
                'verbose_name_plural': 'Статистика использования файлов',
            },
        ),
    ]
