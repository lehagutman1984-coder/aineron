# Hand-authored (server blocks makemigrations on prod container, see
# aitext/migrations/0053_prompttemplate_translations.py for the same convention).
# card_number -> payout_destination: aineron.net вывод реферальных начислений
# идёт на крипто-кошелёк (USDT TRC-20 / TON), а не на банковскую карту —
# старое имя поля и max_length=20 не годились для адресов кошельков.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_legaldocument_translations'),
    ]

    operations = [
        migrations.RenameField(
            model_name='withdrawalrequest',
            old_name='card_number',
            new_name='payout_destination',
        ),
        migrations.AlterField(
            model_name='withdrawalrequest',
            name='payout_destination',
            field=models.CharField(
                max_length=128,
                verbose_name='Реквизиты для вывода',
                help_text='Номер карты (aineron.ru) или адрес крипто-кошелька USDT/TON (aineron.net)',
            ),
        ),
    ]
