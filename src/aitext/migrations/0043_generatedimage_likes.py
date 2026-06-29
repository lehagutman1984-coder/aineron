from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0042_generatedimage_user_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='likes',
            field=models.IntegerField(default=0, verbose_name='Лайки'),
        ),
    ]
