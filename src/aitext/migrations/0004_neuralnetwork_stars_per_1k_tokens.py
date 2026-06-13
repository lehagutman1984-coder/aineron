from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0003_alter_neuralnetwork_cost_per_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='neuralnetwork',
            name='stars_per_1k_tokens',
            field=models.DecimalField(
                decimal_places=4,
                default=0,
                help_text='Для токенного биллинга через API-ключи. 0 = авто-расчёт из cost_per_message.',
                max_digits=8,
                verbose_name='Звёзд за 1000 токенов (dev-API)',
            ),
        ),
    ]
