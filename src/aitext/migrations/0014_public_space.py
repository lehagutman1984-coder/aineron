from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0013_project_connector_commit'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_public',
            field=models.BooleanField(default=False, verbose_name='Публичный'),
        ),
        migrations.AddField(
            model_name='project',
            name='public_slug',
            field=models.CharField(blank=True, db_index=True, max_length=22, verbose_name='Публичный slug'),
        ),
        migrations.AddField(
            model_name='project',
            name='public_show_files',
            field=models.BooleanField(default=True, verbose_name='Показывать файлы базы знаний'),
        ),
        migrations.AddField(
            model_name='project',
            name='public_show_chats',
            field=models.BooleanField(default=False, verbose_name='Показывать чаты'),
        ),
    ]
