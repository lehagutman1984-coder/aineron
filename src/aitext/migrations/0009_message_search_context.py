from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0008_project_chat_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='search_context',
            field=models.TextField(blank=True, default='', verbose_name='Результаты веб-поиска'),
        ),
    ]
