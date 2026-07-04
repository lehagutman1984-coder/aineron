import django.db.models.deletion
from django.core.validators import MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Пропущенная миграция из aa99b22 (процентные скидочные промокоды) —
    поля были добавлены в models.py, но makemigrations не запускался, из-за
    чего /api/v1/billing/history/ падал 500: column ...promo_code_id does not exist.
    """

    dependencies = [
        ('users', '0006_page_sale_settings_rub'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='discount_percent',
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[MaxValueValidator(50)],
                verbose_name='Скидка на тариф, %',
                help_text='0 — обычный промокод (начисляет баланс). 1–50 — процентная скидка '
                          'на покупку тарифа: вводится при оплате, действует на первый платёж, '
                          'продление по полной цене. Безопасно по марже: Старт/Стандарт до 15%, '
                          'Про до 10%, Бизнес/Макс до 5–8%.',
            ),
        ),
        migrations.AlterField(
            model_name='promocode',
            name='stars',
            field=models.PositiveIntegerField(default=0, verbose_name='Начисление на баланс, ₽'),
        ),
        migrations.AddField(
            model_name='paymenthistory',
            name='promo_code',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='payments',
                to='users.promocode',
                verbose_name='Промокод (скидка)',
                help_text='Скидочный промокод, применённый к этому платежу. '
                          'Использование фиксируется после успешной оплаты.',
            ),
        ),
    ]
