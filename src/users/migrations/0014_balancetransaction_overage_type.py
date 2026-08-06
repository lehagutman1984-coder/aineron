from django.db import migrations, models


class Migration(migrations.Migration):
    """Additive, instance-agnostic (CLAUDE.md, «Два инстанса»): расширение
    choices у BalanceTransaction.type новым значением 'overage' — доплата за
    токены (TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 3, §3.5). Данные не трогает."""

    dependencies = [
        ('users', '0013_customuser_acquisition_utm'),
    ]

    operations = [
        migrations.AlterField(
            model_name='balancetransaction',
            name='type',
            field=models.CharField(choices=[('spend', 'Списание'), ('refund', 'Возврат'), ('topup', 'Пополнение'), ('subscription', 'Тариф'), ('promo', 'Промокод'), ('referral', 'Реферальный бонус'), ('xtr', 'Telegram Stars'), ('admin', 'Ручное начисление'), ('sandbox', 'Sandbox API'), ('overage', 'Доплата за токены')], max_length=20, verbose_name='Тип операции'),
        ),
    ]
