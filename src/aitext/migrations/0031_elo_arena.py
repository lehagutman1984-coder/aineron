from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0030_persona_template_vars'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='neuralnetwork',
            name='elo_rating',
            field=models.FloatField(default=1500.0, verbose_name='Elo-рейтинг (Arena)'),
        ),
        migrations.AddField(
            model_name='neuralnetwork',
            name='elo_matches',
            field=models.PositiveIntegerField(default=0, verbose_name='Арена-матчей'),
        ),
        migrations.CreateModel(
            name='ModelMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt_snippet', models.CharField(blank=True, max_length=200, verbose_name='Промт (фрагмент)')),
                ('compare_chat_ids', models.JSONField(default=list, verbose_name='Chat IDs сравнения (anti-abuse)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('winner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='arena_wins',
                    to='aitext.neuralnetwork',
                    verbose_name='Победитель',
                )),
                ('loser', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='arena_losses',
                    to='aitext.neuralnetwork',
                    verbose_name='Проигравший',
                )),
                ('user', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='arena_matches',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Арена — матч',
                'verbose_name_plural': 'Арена — матчи',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='modelmatch',
            index=models.Index(fields=['winner'], name='arena_winner_idx'),
        ),
        migrations.AddIndex(
            model_name='modelmatch',
            index=models.Index(fields=['loser'], name='arena_loser_idx'),
        ),
    ]
