# Hand-authored (server blocks makemigrations on prod container, see
# 0010_withdrawalrequest_payout_destination.py for the same convention).
# CustomUser.language — язык интерфейса пользователя, заполняется фронтендом
# из текущей locale при регистрации. Нужен для локализации сообщений об
# ошибках AI-генерации вне request-цикла (Celery-задачи aitext/tasks.py) —
# CustomUser раньше вообще не хранил язык (в отличие от TelegramUser.language).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_add_fa_tr_id_ar_translation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='language',
            field=models.CharField(
                blank=True,
                choices=[
                    ('ru', 'Русский'),
                    ('en', 'English'),
                    ('fa', 'Persian'),
                    ('tr', 'Turkish'),
                    ('id', 'Indonesian'),
                    ('ar', 'Arabic'),
                ],
                help_text='Заполняется фронтендом из текущей locale при регистрации. Пусто — '
                           'фолбэк на INTL_DEFAULT_LOCALE (INTL_MODE=1) или ru (см. get_language())',
                max_length=8,
                verbose_name='Язык интерфейса',
            ),
        ),
    ]
