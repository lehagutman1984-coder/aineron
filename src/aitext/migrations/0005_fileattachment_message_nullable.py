from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0004_neuralnetwork_stars_per_1k_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileattachment',
            name='message',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attachments',
                to='aitext.message',
                verbose_name='Сообщение',
            ),
        ),
    ]
