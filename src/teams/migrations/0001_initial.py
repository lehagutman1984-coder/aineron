from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('inn', models.CharField(blank=True, max_length=12, verbose_name='ИНН')),
                ('kpp', models.CharField(blank=True, max_length=9, verbose_name='КПП')),
                ('legal_address', models.TextField(blank=True, verbose_name='Юридический адрес')),
                ('balance_rub', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Баланс (руб.)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создана')),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='owned_organizations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Владелец',
                )),
            ],
            options={
                'verbose_name': 'Организация',
                'verbose_name_plural': 'Организации',
            },
        ),
        migrations.CreateModel(
            name='OrganizationMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('owner', 'Владелец'), ('admin', 'Администратор'), ('member', 'Участник')],
                    default='member',
                    max_length=20,
                    verbose_name='Роль',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Добавлен')),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='teams.organization',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='org_memberships',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Участник организации',
                'verbose_name_plural': 'Участники организации',
                'unique_together': {('organization', 'user')},
            },
        ),
        migrations.CreateModel(
            name='OrganizationInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(verbose_name='Email приглашённого')),
                ('token', models.CharField(blank=True, max_length=64, unique=True, verbose_name='Токен')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Истекает')),
                ('is_accepted', models.BooleanField(default=False, verbose_name='Принято')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invites',
                    to='teams.organization',
                )),
            ],
            options={
                'verbose_name': 'Приглашение в организацию',
                'verbose_name_plural': 'Приглашения в организацию',
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=50, unique=True, verbose_name='Номер счёта')),
                ('amount_rub', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Сумма (руб.)')),
                ('status', models.CharField(
                    choices=[('pending', 'Ожидает оплаты'), ('paid', 'Оплачен'), ('cancelled', 'Отменён')],
                    default='pending',
                    max_length=20,
                    verbose_name='Статус',
                )),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='Оплачен')),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invoices',
                    to='teams.organization',
                )),
            ],
            options={
                'verbose_name': 'Счёт',
                'verbose_name_plural': 'Счета',
                'ordering': ['-created_at'],
            },
        ),
    ]
