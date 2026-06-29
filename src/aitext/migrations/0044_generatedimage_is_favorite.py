from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0043_generatedimage_likes'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='is_favorite',
            field=models.BooleanField(default=False, verbose_name='В избранном'),
        ),
    ]
