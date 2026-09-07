from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0058_message_token_usage'),
    ]

    operations = [
        migrations.AddField(
            model_name='neuralnetwork',
            name='is_new',
            field=models.BooleanField(
                default=False,
                help_text='Отображать в блоке "Новинки" на лендинге. Проставляется вручную '
                          '(в каталоге нет даты добавления модели) — снимайте флаг, когда модель перестаёт быть новой.',
                verbose_name='Новинка',
            ),
        ),
    ]
