from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0002_organization_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='seats_count',
            field=models.PositiveIntegerField(default=5, verbose_name='Лимит мест'),
        ),
        migrations.AddField(
            model_name='organization',
            name='seat_monthly_stars',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='Звёзд в месяц на участника',
                help_text='0 = без лимита на участника',
            ),
        ),
        migrations.AddField(
            model_name='organizationmember',
            name='monthly_used',
            field=models.PositiveIntegerField(default=0, verbose_name='Использовано звёзд (мес.)'),
        ),
        migrations.AddField(
            model_name='organizationmember',
            name='monthly_reset_at',
            field=models.DateField(null=True, blank=True, verbose_name='Дата сброса квоты'),
        ),
    ]
