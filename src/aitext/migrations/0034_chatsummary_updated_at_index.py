from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0033_project_yjs_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatsummary',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
