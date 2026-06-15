from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='gitea_username',
            field=models.CharField(blank=True, max_length=64, verbose_name='Gitea username'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='gitea_password',
            field=models.CharField(blank=True, max_length=128, verbose_name='Gitea password'),
        ),
    ]
