# Hand-authored (server blocks makemigrations on prod container, see
# 0010_withdrawalrequest_payout_destination.py for the same convention).
# CustomUser.acquisition_utm_source/medium/campaign — метки первого захода
# (utm_source/utm_medium/utm_campaign), которые frontend/middleware.ts кладёт
# в cookie при заходе с соответствующими параметрами в URL. Фиксируются один
# раз при регистрации (см. users/attribution.py) — без них нельзя было связать
# конкретного платящего пользователя с каналом привлечения (GROWTH_PLAN_RU.md
# §2.5/§7#4): Метрика видела UTM в своих отчётах, но не в нашей БД.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_customuser_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='acquisition_utm_source',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                help_text='Например vc, dtf, sostav, habr, productradar, neurofolder, plati, '
                          'tg_<канал>. Фиксируется один раз при регистрации, дальше не меняется '
                          '— см. GROWTH_PLAN_RU.md §2.5.',
                verbose_name='UTM-источник при регистрации',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='acquisition_utm_medium',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='UTM-канал при регистрации'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='acquisition_utm_campaign',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='UTM-кампания при регистрации'),
        ),
    ]
