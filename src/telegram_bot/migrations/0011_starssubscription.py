from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('telegram_bot', '0010_aitask'),
    ]

    operations = [
        migrations.CreateModel(
            name='StarsSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_charge_id', models.CharField(blank=True, max_length=128, verbose_name='Последний telegram_payment_charge_id')),
                ('xtr_amount', models.PositiveIntegerField(default=0, verbose_name='Цена, XTR/мес')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Оплачено до')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tariff', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='users.tariff', verbose_name='Тариф')),
                ('tg_user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stars_subscription', to='telegram_bot.telegramuser', verbose_name='TG пользователь')),
            ],
            options={
                'verbose_name': 'Stars-подписка',
                'verbose_name_plural': 'Stars-подписки',
            },
        ),
    ]
