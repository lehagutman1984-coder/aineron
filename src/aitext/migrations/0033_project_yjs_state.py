from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0032_moderationlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='yjs_state',
            field=models.BinaryField(blank=True, null=True, verbose_name='Yjs документ (бинарный снапшот)'),
        ),
    ]
