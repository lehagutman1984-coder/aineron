from django.db import migrations, models
import django.db.models.deletion
import aitext.models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0011_chatsummary_last_compressed_message_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255, verbose_name='Имя файла')),
                ('file', models.FileField(upload_to=aitext.models.project_file_upload_path, verbose_name='Файл')),
                ('file_size', models.PositiveIntegerField(default=0, verbose_name='Размер (байт)')),
                ('file_type', models.CharField(choices=[('pdf', 'PDF'), ('doc', 'Документ'), ('text', 'Текст'), ('code', 'Код'), ('other', 'Другой')], default='other', max_length=10, verbose_name='Тип файла')),
                ('extracted_text', models.TextField(blank=True, verbose_name='Извлечённый текст')),
                ('status', models.CharField(choices=[('processing', 'Обработка'), ('ready', 'Готов'), ('error', 'Ошибка')], default='processing', max_length=15, verbose_name='Статус')),
                ('enabled', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_files', to='aitext.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Файл базы знаний',
                'verbose_name_plural': 'Файлы базы знаний',
                'ordering': ['created_at'],
            },
        ),
    ]
